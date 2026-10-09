import os
import sqlite3
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "powerlib.db")

CATEGORIES = {
    "squat": ("🟥 Присед", "Все материалы по приседу"),
    "bench": ("🟦 Жим", "Все материалы по жиму"),
    "deadlift": ("🟩 Тяга", "Все материалы по тяге"),
    "general": ("⚙️ Общее", "Материалы, которые не подходят к другим разделам"),
    "nutrition": ("🥗 Питание и восстановление", "Питание, сон и восстановление"),
    "competition": ("🏆 Соревнования", "Подготовка и выступление на стартах"),
    "problems": ("🩹 Проблемы и ошибки", "Разбор проблем и способов их исправления"),
}

def connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            duration TEXT DEFAULT '',
            url TEXT NOT NULL,
            keywords TEXT DEFAULT ''
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, video_id)
        )
    """)
    con.commit()
    return con

def main_keyboard():
    rows = [
        [InlineKeyboardButton("🟥 Присед", callback_data="cat:squat"),
         InlineKeyboardButton("🟦 Жим", callback_data="cat:bench")],
        [InlineKeyboardButton("🟩 Тяга", callback_data="cat:deadlift"),
         InlineKeyboardButton("⚙️ Общее", callback_data="cat:general")],
        [InlineKeyboardButton("🥗 Питание и восстановление", callback_data="cat:nutrition")],
        [InlineKeyboardButton("🏆 Соревнования", callback_data="cat:competition")],
        [InlineKeyboardButton("🩹 Проблемы и ошибки", callback_data="cat:problems")],
        [InlineKeyboardButton("🔎 Поиск", callback_data="search"),
         InlineKeyboardButton("⭐ Избранное", callback_data="favorites")],
    ]
    return InlineKeyboardMarkup(rows)

def video_keyboard(video_id, user_id, back_to):
    con = connect()
    saved = con.execute(
        "SELECT 1 FROM favorites WHERE user_id=? AND video_id=?",
        (user_id, video_id)
    ).fetchone() is not None
    con.close()
    star = "⭐ В избранном" if saved else "☆ Добавить в избранное"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Смотреть видео", callback_data=f"watch:{video_id}")],
        [InlineKeyboardButton(star, callback_data=f"fav:{video_id}:{back_to}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=back_to)],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏋️ <b>POWERLIB</b>\n\n"
        "Твоя библиотека знаний о силовом тренинге.\n\n"
        "Выбери раздел или найди нужный материал."
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n/start — открыть меню\n/search — поиск по библиотеке\n"
        "/add — инструкция по добавлению видео (доступно после настройки администратора)"
    )

async def show_category(query, category):
    name, subtitle = CATEGORIES[category]
    con = connect()
    videos = con.execute(
        "SELECT id, title, description, duration FROM videos WHERE category=? ORDER BY id DESC",
        (category,)
    ).fetchall()
    con.close()
    if not videos:
        text = f"<b>{escape(name)}</b>\n\n{escape(subtitle)}\n\nПока здесь нет видео. Материалы появятся после добавления в библиотеку."
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="home")]])
        )
        return
    buttons = []
    for vid, title, desc, duration in videos:
        label = title if len(title) <= 55 else title[:52] + "..."
        buttons.append([InlineKeyboardButton(f"🎥 {label}", callback_data=f"video:{vid}:cat:{category}")])
    buttons.append([InlineKeyboardButton("🔎 Поиск в этом разделе", callback_data=f"searchcat:{category}")])
    buttons.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="home")])
    await query.edit_message_text(
        f"<b>{escape(name)}</b>\n\n{escape(subtitle)}\n\nВыбери видео:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_video(query, video_id, user_id, back_to):
    con = connect()
    row = con.execute(
        "SELECT title, category, description, duration, url FROM videos WHERE id=?",
        (video_id,)
    ).fetchone()
    con.close()
    if not row:
        await query.edit_message_text("Это видео больше не найдено.", reply_markup=main_keyboard())
        return
    title, category, description, duration, url = row
    category_name = CATEGORIES.get(category, ("📚 Материал", ""))[0]
    duration_line = f"\n⏱ {escape(duration)}" if duration else ""
    text = (
        f"🎥 <b>{escape(title)}</b>\n\n{escape(description)}\n\n"
        f"{escape(category_name)}{duration_line}"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=video_keyboard(video_id, user_id, back_to)
    )

async def show_favorites(query, user_id):
    con = connect()
    rows = con.execute("""
        SELECT v.id, v.title, v.category
        FROM videos v JOIN favorites f ON v.id=f.video_id
        WHERE f.user_id=? ORDER BY v.title COLLATE NOCASE
    """, (user_id,)).fetchall()
    con.close()
    if not rows:
        await query.edit_message_text(
            "⭐ <b>Избранное</b>\n\nЗдесь будут видео, которые ты сохранишь.\n\n"
            "Нажми ☆ рядом с видео, чтобы добавить его сюда.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏋️ Перейти к библиотеке", callback_data="home")]])
        )
        return
    buttons = []
    for vid, title, category in rows:
        label = title if len(title) <= 55 else title[:52] + "..."
        buttons.append([InlineKeyboardButton(f"🎥 {label}", callback_data=f"video:{vid}:favorites")])
    buttons.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="home")])
    await query.edit_message_text("⭐ <b>Избранное</b>\n\nТвои сохранённые видео:", parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def begin_search(update: Update, context: ContextTypes.DEFAULT_TYPE, category=None):
    context.user_data["search_category"] = category
    context.user_data["awaiting_search"] = True
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🔎 Напиши слово или фразу для поиска.\n\nНапример: глубина, стартовая позиция, восстановление.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="home")]])
        )
    else:
        await update.message.reply_text("🔎 Напиши слово или фразу для поиска.")

async def run_search(message, context, user_id, term):
    category = context.user_data.pop("search_category", None)
    context.user_data["awaiting_search"] = False
    pattern = f"%{term.strip()}%"
    con = connect()
    if category:
        rows = con.execute("""
            SELECT id, title, category FROM videos
            WHERE category=? AND (title LIKE ? OR description LIKE ? OR keywords LIKE ?)
            ORDER BY id DESC LIMIT 30
        """, (category, pattern, pattern, pattern)).fetchall()
    else:
        rows = con.execute("""
            SELECT id, title, category FROM videos
            WHERE title LIKE ? OR description LIKE ? OR keywords LIKE ?
            ORDER BY id DESC LIMIT 30
        """, (pattern, pattern, pattern)).fetchall()
    con.close()
    if not rows:
        await message.reply_text(f"По запросу «{term}» ничего не найдено.", reply_markup=main_keyboard())
        return
    buttons = []
    for vid, title, cat in rows:
        label = title if len(title) <= 48 else title[:45] + "..."
        buttons.append([InlineKeyboardButton(f"{CATEGORIES.get(cat, ('📚',))[0]} {label}",
                                             callback_data=f"video:{vid}:search")])
    buttons.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="home")])
    await message.reply_text(f"🔎 Результаты по запросу «{escape(term)}»:", parse_mode="HTML",
                             reply_markup=InlineKeyboardMarkup(buttons))

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_search"):
        await run_search(update.message, context, update.effective_user.id, update.message.text)
    else:
        await update.message.reply_text("Открой меню командой /start.", reply_markup=main_keyboard())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "home":
        await query.edit_message_text(
            "🏋️ <b>POWERLIB</b>\n\nТвоя библиотека знаний о силовом тренинге.\n\nВыбери раздел:",
            parse_mode="HTML", reply_markup=main_keyboard()
        )
    elif data.startswith("cat:"):
        await show_category(query, data.split(":", 1)[1])
    elif data == "favorites":
        await show_favorites(query, user_id)
    elif data == "search":
        await begin_search(update, context)
    elif data.startswith("searchcat:"):
        await begin_search(update, context, data.split(":", 1)[1])
    elif data.startswith("video:"):
        parts = data.split(":")
        video_id = int(parts[1])
        origin = parts[2] if len(parts) > 2 else "home"
        back_to = f"cat:{parts[3]}" if origin == "cat" and len(parts) > 3 else origin
        await show_video(query, video_id, user_id, back_to)
    elif data.startswith("fav:"):
        _, vid_s, back_to = data.split(":", 2)
        vid = int(vid_s)
        con = connect()
        exists = con.execute("SELECT 1 FROM favorites WHERE user_id=? AND video_id=?", (user_id, vid)).fetchone()
        if exists:
            con.execute("DELETE FROM favorites WHERE user_id=? AND video_id=?", (user_id, vid))
        else:
            con.execute("INSERT OR IGNORE INTO favorites(user_id, video_id) VALUES (?, ?)", (user_id, vid))
        con.commit()
        con.close()
        await show_video(query, vid, user_id, back_to)
    elif data.startswith("watch:"):
        vid = int(data.split(":")[1])
        con = connect()
        row = con.execute("SELECT url FROM videos WHERE id=?", (vid,)).fetchone()
        con.close()
        if row:
            await query.message.reply_text(f"▶️ Ссылка на видео:\n{row[0]}")
        else:
            await query.message.reply_text("Видео не найдено.")
    else:
        await query.edit_message_text("Неизвестная команда.", reply_markup=main_keyboard())

def main():
    if not TOKEN:
        raise SystemExit("Укажи токен в переменной окружения BOT_TOKEN.")
    connect().close()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", begin_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(callbacks))
    print("POWERLIB is running.")
    app.run_polling()

if __name__ == "__main__":
    main()
