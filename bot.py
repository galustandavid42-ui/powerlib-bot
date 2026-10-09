
import os
import re
import sqlite3
import logging
from urllib.request import Request, urlopen

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
DB_PATH = "powerlib.db"

CATEGORIES = {
    "squat": "🟥 Присед",
    "bench": "🟦 Жим",
    "deadlift": "🟩 Тяга",
    "general": "⚙️ Общее",
    "nutrition": "🥗 Питание и восстановление",
    "competition": "🏆 Соревнования",
    "problems": "🩹 Проблемы и ошибки",
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'general',
                duration TEXT DEFAULT '',
                link TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                keywords TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                UNIQUE(user_id, video_id)
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(videos)"
            ).fetchall()
        }

        if "link" not in columns:
            conn.execute(
                "ALTER TABLE videos ADD COLUMN link TEXT NOT NULL DEFAULT ''"
            )

        if "url" not in columns:
            conn.execute(
                "ALTER TABLE videos ADD COLUMN url TEXT NOT NULL DEFAULT ''"
            )

        if "keywords" not in columns:
            conn.execute(
                "ALTER TABLE videos ADD COLUMN keywords TEXT DEFAULT ''"
            )

        conn.execute("""
            UPDATE videos
            SET link = url
            WHERE (link IS NULL OR link = '')
              AND url IS NOT NULL AND url != ''
        """)

        conn.execute("""
            UPDATE videos
            SET url = link
            WHERE (url IS NULL OR url = '')
              AND link IS NOT NULL AND link != ''
        """)


def is_admin(user_id):
    return ADMIN_ID and str(user_id) == ADMIN_ID


def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟥 Присед", callback_data="cat:squat"),
            InlineKeyboardButton("🟦 Жим", callback_data="cat:bench"),
        ],
        [
            InlineKeyboardButton("🟩 Тяга", callback_data="cat:deadlift"),
            InlineKeyboardButton("⚙️ Общее", callback_data="cat:general"),
        ],
        [
            InlineKeyboardButton(
                "🥗 Питание и восстановление",
                callback_data="cat:nutrition",
            )
        ],
        [
            InlineKeyboardButton(
                "🏆 Соревнования", callback_data="cat:competition"
            )
        ],
        [
            InlineKeyboardButton(
                "🩹 Проблемы и ошибки", callback_data="cat:problems"
            )
        ],
        [
            InlineKeyboardButton("🔎 Поиск", callback_data="search"),
            InlineKeyboardButton("⭐ Избранное", callback_data="favorites"),
        ],
    ])


def youtube_video_id(link):
    """Извлекает ID ролика из распространённых ссылок YouTube."""
    match = re.search(
        r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))"
        r"([A-Za-z0-9_-]{11})",
        link,
    )
    return match.group(1) if match else None


def get_thumbnail(video_id):
    """Проверяет, доступна ли миниатюра YouTube."""
    if not video_id:
        return None

    for quality in ("maxresdefault", "hqdefault"):
        url = (
            f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        )
        try:
            request = Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urlopen(request, timeout=5) as response:
                image_data = response.read()

            if image_data and len(image_data) > 1000:
                return image_data
        except Exception:
            logging.warning(
                "Не удалось получить превью YouTube (%s)",
                quality,
            )

    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏋️ POWERLIB — библиотека видео о пауэрлифтинге\n\n"
        "Выбирай раздел, чтобы найти нужные материалы.\n"
        "Для поиска нажми «🔎 Поиск» и отправь ключевое слово.",
        reply_markup=main_keyboard(),
    )


async def show_video_list(
    query, context, category=None, search=None, favorites=False
):
    user_id = query.from_user.id

    with db() as conn:
        if category:
            videos = conn.execute(
                "SELECT * FROM videos WHERE category=? ORDER BY id DESC",
                (category,),
            ).fetchall()
            heading = f"{CATEGORIES.get(category, 'Видео')}\n\n"

        elif favorites:
            videos = conn.execute("""
                SELECT v.* FROM videos v
                JOIN favorites f ON v.id = f.video_id
                WHERE f.user_id = ?
                ORDER BY v.id DESC
            """, (user_id,)).fetchall()
            heading = "⭐ Избранное\n\n"

        elif search is not None:
            term = f"%{search.lower()}%"
            videos = conn.execute("""
                SELECT * FROM videos
                WHERE lower(title) LIKE ?
                   OR lower(description) LIKE ?
                   OR lower(keywords) LIKE ?
                ORDER BY id DESC
            """, (term, term, term)).fetchall()
            heading = f"🔎 Результаты поиска: {search}\n\n"

        else:
            return

    if not videos:
        await query.message.reply_text(
            heading + "Пока здесь нет видео.",
            reply_markup=main_keyboard(),
        )
        return

    buttons = [
        [
            InlineKeyboardButton(
                video["title"][:60],
                callback_data=f"video:{video['id']}",
            )
        ]
        for video in videos
    ]
    buttons.append([
        InlineKeyboardButton(
            "🏠 Главное меню", callback_data="home"
        )
    ])

    await query.message.reply_text(
        heading + f"Найдено видео: {len(videos)}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def send_video_details(query, video, favorite):
    link = (video["link"] or video["url"] or "").strip()
    text = (
        f"🎬 {video['title']}\n\n"
        f"{video['description']}\n\n"
        f"📂 Раздел: "
        f"{CATEGORIES.get(video['category'], video['category'])}\n"
        f"⏱ Длительность: {video['duration'] or 'не указана'}\n\n"
        f"▶️ Смотреть: {link or 'ссылка не указана'}"
    )

    label = (
        "⭐ Убрать из избранного"
        if favorite
        else "⭐ В избранное"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                label, callback_data=f"fav:{video['id']}"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 Главное меню", callback_data="home"
            )
        ],
    ])

    video_id = youtube_video_id(link)
    thumbnail = await __import__("asyncio").to_thread(
        get_thumbnail, video_id
    ) if video_id else None

    if thumbnail:
        await query.message.reply_photo(
            photo=thumbnail,
            caption=text[:1024],
            reply_markup=keyboard,
        )
    else:
        await query.message.reply_text(
            text,
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )


async def button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        await query.message.reply_text(
            "🏋️ Главное меню", reply_markup=main_keyboard()
        )

    elif data.startswith("cat:"):
        await show_video_list(
            query, context, category=data.split(":", 1)[1]
        )

    elif data == "search":
        context.user_data["waiting_search"] = True
        await query.message.reply_text(
            "🔎 Напиши слово или фразу для поиска."
        )

    elif data == "favorites":
        await show_video_list(
            query, context, favorites=True
        )

    elif data.startswith("video:"):
        video_id = int(data.split(":", 1)[1])

        with db() as conn:
            video = conn.execute(
                "SELECT * FROM videos WHERE id=?",
                (video_id,),
            ).fetchone()
            favorite = conn.execute(
                "SELECT 1 FROM favorites "
                "WHERE user_id=? AND video_id=?",
                (query.from_user.id, video_id),
            ).fetchone()

        if not video:
            await query.message.reply_text("Видео не найдено.")
            return

        await send_video_details(query, video, favorite)

    elif data.startswith("fav:"):
        video_id = int(data.split(":", 1)[1])
        user_id = query.from_user.id

        with db() as conn:
            existing = conn.execute(
                "SELECT 1 FROM favorites "
                "WHERE user_id=? AND video_id=?",
                (user_id, video_id),
            ).fetchone()

            if existing:
                conn.execute(
                    "DELETE FROM favorites "
                    "WHERE user_id=? AND video_id=?",
                    (user_id, video_id),
                )
                message = "Удалено из избранного."
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO favorites "
                    "(user_id, video_id) VALUES (?, ?)",
                    (user_id, video_id),
                )
                message = "Добавлено в избранное."

        await query.message.reply_text(message)


async def addvideo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "⛔ Эта команда доступна только администратору."
        )
        return

    context.user_data["add_video"] = {"step": "title"}
    await update.message.reply_text(
        "Добавление видео.\n\n"
        "Шаг 1/6: отправь название видео.\n"
        "Для отмены отправь /cancel"
    )


async def cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    context.user_data.pop("add_video", None)
    context.user_data.pop("waiting_search", None)
    await update.message.reply_text("Действие отменено.")


async def text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if context.user_data.get("waiting_search"):
        context.user_data.pop("waiting_search", None)
        term = f"%{text.lower()}%"

        with db() as conn:
            videos = conn.execute("""
                SELECT * FROM videos
                WHERE lower(title) LIKE ?
                   OR lower(description) LIKE ?
                   OR lower(keywords) LIKE ?
                ORDER BY id DESC
            """, (term, term, term)).fetchall()

        if not videos:
            await update.message.reply_text(
                "Ничего не найдено. Попробуй другое слово.",
                reply_markup=main_keyboard(),
            )
            return

        buttons = [
            [
                InlineKeyboardButton(
                    video["title"][:60],
                    callback_data=f"video:{video['id']}",
                )
            ]
            for video in videos
        ]
        buttons.append([
            InlineKeyboardButton(
                "🏠 Главное меню", callback_data="home"
            )
        ])

        await update.message.reply_text(
            f"🔎 Найдено видео: {len(videos)}",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    state = context.user_data.get("add_video")

    if not state:
        await update.message.reply_text(
            "Выбери раздел в меню или нажми 🔎 Поиск.",
            reply_markup=main_keyboard(),
        )
        return

    if not is_admin(user_id):
        context.user_data.pop("add_video", None)
        await update.message.reply_text("⛔ Нет доступа.")
        return

    step = state["step"]

    if step == "title":
        state["title"] = text
        state["step"] = "description"
        await update.message.reply_text(
            "Шаг 2/6: отправь краткое описание — что происходит в видео."
        )

    elif step == "description":
        state["description"] = text
        state["step"] = "category"
        await update.message.reply_text(
            "Шаг 3/6: отправь код раздела:\n\n"
            + "\n".join(
                f"{key} — {value}"
                for key, value in CATEGORIES.items()
            )
        )

    elif step == "category":
        if text not in CATEGORIES:
            await update.message.reply_text(
                "Не понял раздел. Отправь один код из списка: "
                + ", ".join(CATEGORIES.keys())
            )
            return

        state["category"] = text
        state["step"] = "duration"
        await update.message.reply_text(
            "Шаг 4/6: отправь длительность, например 12:35, или —"
        )

    elif step == "duration":
        state["duration"] = "" if text == "—" else text
        state["step"] = "link"
        await update.message.reply_text(
            "Шаг 5/6: отправь ссылку на видео (https://...)"
        )

    elif step == "link":
        if not text.startswith(("https://", "http://")):
            await update.message.reply_text(
                "Нужна ссылка, начинающаяся с https:// или http://"
            )
            return

        state["link"] = text
        state["step"] = "keywords"
        await update.message.reply_text(
            "Шаг 6/6: отправь ключевые слова через запятую или —"
        )

    elif step == "keywords":
        state["keywords"] = "" if text == "—" else text

        try:
            with db() as conn:
                conn.execute("""
                    INSERT INTO videos
                        (title, description, category, duration,
                         link, url, keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    state["title"],
                    state["description"],
                    state["category"],
                    state["duration"],
                    state["link"],
                    state["link"],
                    state["keywords"],
                ))
        except sqlite3.Error:
            logging.exception("Ошибка сохранения видео")
            await update.message.reply_text(
                "❌ Не удалось сохранить видео. "
                "Проверь Console на FadeHost."
            )
            return

        title = state["title"]
        context.user_data.pop("add_video", None)
        await update.message.reply_text(
            f"✅ Видео «{title}» добавлено в POWERLIB!",
            reply_markup=main_keyboard(),
        )


async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "/start — открыть меню\n"
        "/addvideo — добавить видео (только администратор)\n"
        "/cancel — отменить текущее действие"
    )


def main():
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN в переменных окружения.")
    if not ADMIN_ID:
        raise RuntimeError("Не задан ADMIN_ID в переменных окружения.")

    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", addvideo))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
    )

    print("POWERLIB запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()
    
