
import asyncio
import logging
import re
import sqlite3
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

from handlers.config import BOT_TOKEN as TOKEN, ADMIN_ID, validate_config
from handlers.database import db, init_db
from handlers.categories import CATEGORIES
from modules.keyboards import (
    main_keyboard as modular_main_keyboard,
    navigation_keyboard as modular_navigation_keyboard,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


# ---------------- KEYBOARDS ----------------

def main_keyboard():
    return modular_main_keyboard()


def navigation_keyboard(back_data="home"):
    return modular_navigation_keyboard(back_data)


# ---------------- ACCESS ----------------

def is_admin(user_id):
    return ADMIN_ID and str(user_id) == str(ADMIN_ID)


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last_view"] = "home"

    await update.message.reply_text(
        "🏋️ POWERLIB\n"
        "Библиотека видео о пауэрлифтинге.\n\n"
        "Выбирай раздел. Видео будут показаны с превью, "
        "описанием и кнопкой просмотра.",
        reply_markup=main_keyboard(),
    )


# ---------------- YOUTUBE PREVIEWS ----------------

def youtube_video_id(link):
    patterns = [
        r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*?[&?]v=([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube-nocookie\.com/embed/([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)

    match = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", link)
    return match.group(1) if match else None


def get_thumbnail(video_id):
    if not video_id:
        return None

    for quality in ("maxresdefault", "hqdefault", "mqdefault"):
        image_url = (
            f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        )

        try:
            request = Request(
                image_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            with urlopen(request, timeout=8) as response:
                data = response.read()

            if data and len(data) > 1000:
                return data

        except Exception:
            logging.warning(
                "Не удалось получить превью для %s (%s)",
                video_id,
                quality,
            )

    return None


# ---------------- VIDEO CARDS ----------------

async def send_video_card(message, video, user_id, back_data="home"):
    link = (video["link"] or video["url"] or "").strip()
    video_id = youtube_video_id(link)

    description = (video["description"] or "").strip()
    title = (video["title"] or "Без названия").strip()
    duration = (video["duration"] or "Не указана").strip()

    caption = (
        f"🎬 {title}\n\n"
        f"{description}\n\n"
        f"⏱ Длительность: {duration}"
    )

    with db() as conn:
        favorite = conn.execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND video_id=?",
            (user_id, video["id"]),
        ).fetchone()

    favorite_text = (
        "⭐ Убрать из избранного"
        if favorite
        else "⭐ В избранное"
    )

    buttons = []

    if link:
        buttons.append([
            InlineKeyboardButton("▶️ Смотреть видео", url=link)
        ])

    buttons.append([
        InlineKeyboardButton(
            favorite_text,
            callback_data=f"fav:{video['id']}",
        ),
        InlineKeyboardButton(
            "📖 Подробнее",
            callback_data=f"video:{video['id']}",
        ),
    ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data=f"back:{back_data}",
        ),
        InlineKeyboardButton(
            "🏠 Главное меню",
            callback_data="home",
        ),
    ])

    keyboard = InlineKeyboardMarkup(buttons)

    thumbnail = None
    if video_id:
        thumbnail = await asyncio.to_thread(get_thumbnail, video_id)

    try:
        if thumbnail:
            await message.reply_photo(
                photo=thumbnail,
                caption=caption[:1024],
                reply_markup=keyboard,
            )
        else:
            text = caption
            if link:
                text += f"\n\n▶️ Ссылка: {link}"

            await message.reply_text(
                text[:4000],
                reply_markup=keyboard,
                disable_web_page_preview=False,
            )

    except Exception:
        logging.exception(
            "Ошибка отправки карточки видео %s",
            video["id"],
        )

        fallback = f"🎬 {title}\n\n{description}"
        if link:
            fallback += f"\n\n▶️ {link}"

        await message.reply_text(
            fallback[:4000],
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )


# ---------------- VIDEO LISTS ----------------

async def show_video_list(
    query,
    context,
    category=None,
    search=None,
    favorites=False,
):
    user_id = query.from_user.id

    if category:
        back_data = f"cat:{category}"
    elif favorites:
        back_data = "favorites"
    elif search is not None:
        back_data = "search"
    else:
        back_data = "home"

    context.user_data["last_view"] = back_data

    with db() as conn:
        if category:
            videos = conn.execute(
                "SELECT * FROM videos WHERE category=? ORDER BY id DESC",
                (category,),
            ).fetchall()
            heading = CATEGORIES.get(category, "Видео")

        elif favorites:
            videos = conn.execute(
                """
                SELECT v.*
                FROM videos v
                JOIN favorites f ON v.id = f.video_id
                WHERE f.user_id=?
                ORDER BY v.id DESC
                """,
                (user_id,),
            ).fetchall()
            heading = "⭐ Избранное"

        elif search is not None:
            term = f"%{search.lower()}%"
            videos = conn.execute(
                """
                SELECT * FROM videos
                WHERE lower(title) LIKE ?
                   OR lower(description) LIKE ?
                   OR lower(keywords) LIKE ?
                ORDER BY id DESC
                """,
                (term, term, term),
            ).fetchall()
            heading = f"🔎 Результаты поиска: {search}"

        else:
            return

    if not videos:
        await query.message.reply_text(
            f"{heading}\n\nВ этом разделе пока нет видео.",
            reply_markup=navigation_keyboard(back_data),
        )
        return

    await query.message.reply_text(
        f"{heading}\n\nНайдено видео: {len(videos)}",
        reply_markup=navigation_keyboard(back_data),
    )

    for video in videos:
        await send_video_card(
            query.message,
            video,
            user_id,
            back_data=back_data,
        )


# ---------------- BUTTONS ----------------

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        context.user_data.pop("waiting_search", None)
        context.user_data["last_view"] = "home"

        await query.message.reply_text(
            "🏋️ Главное меню",
            reply_markup=main_keyboard(),
        )

    elif data.startswith("back:"):
        destination = data.split(":", 1)[1]

        if destination == "home":
            context.user_data["last_view"] = "home"
            context.user_data.pop("waiting_search", None)

            await query.message.reply_text(
                "🏋️ Главное меню",
                reply_markup=main_keyboard(),
            )

        elif destination.startswith("cat:"):
            category = destination.split(":", 1)[1]
            await show_video_list(
                query,
                context,
                category=category,
            )

        elif destination == "favorites":
            await show_video_list(
                query,
                context,
                favorites=True,
            )

        elif destination == "search":
            context.user_data["waiting_search"] = True

            await query.message.reply_text(
                "🔎 Отправь слово или фразу для поиска.",
                reply_markup=navigation_keyboard("home"),
            )

    elif data.startswith("cat:"):
        category = data.split(":", 1)[1]
        await show_video_list(
            query,
            context,
            category=category,
        )

    elif data == "search":
        context.user_data["waiting_search"] = True
        context.user_data["last_view"] = "search"

        await query.message.reply_text(
            "🔎 Отправь слово или фразу для поиска.\n"
            "Например: постановка ног, мост, хват, разминка.",
            reply_markup=navigation_keyboard("home"),
        )

    elif data == "favorites":
        await show_video_list(
            query,
            context,
            favorites=True,
        )

    elif data.startswith("video:"):
        video_id = int(data.split(":", 1)[1])

        with db() as conn:
            video = conn.execute(
                "SELECT * FROM videos WHERE id=?",
                (video_id,),
            ).fetchone()

        if not video:
            await query.message.reply_text(
                "Видео не найдено.",
                reply_markup=navigation_keyboard(),
            )
            return

        back_data = context.user_data.get("last_view", "home")

        await send_video_card(
            query.message,
            video,
            query.from_user.id,
            back_data=back_data,
        )

    elif data.startswith("fav:"):
        video_id = int(data.split(":", 1)[1])
        user_id = query.from_user.id

        with db() as conn:
            existing = conn.execute(
                """
                SELECT 1 FROM favorites
                WHERE user_id=? AND video_id=?
                """,
                (user_id, video_id),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    DELETE FROM favorites
                    WHERE user_id=? AND video_id=?
                    """,
                    (user_id, video_id),
                )
                message = (
                    "Убрано из избранного. "
                    "Обнови раздел, чтобы увидеть изменения."
                )
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO favorites (user_id, video_id)
                    VALUES (?, ?)
                    """,
                    (user_id, video_id),
                )
                message = "Добавлено в избранное."

        await query.message.reply_text(
            message,
            reply_markup=navigation_keyboard(
                context.user_data.get("last_view", "home")
            ),
        )


# ---------------- ADD VIDEO ----------------

async def addvideo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "⛔ Команда доступна только администратору."
        )
        return

    context.user_data["add_video"] = {"step": "title"}

    await update.message.reply_text(
        "➕ Добавление видео в POWERLIB\n\n"
        "Шаг 1/6. Отправь название видео.\n"
        "Для отмены: /cancel"
    )


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.pop("add_video", None)
    context.user_data.pop("waiting_search", None)

    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=main_keyboard(),
    )


async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if context.user_data.get("waiting_search"):
        context.user_data.pop("waiting_search", None)

        query = type(
            "SearchQuery",
            (),
            {
                "from_user": update.effective_user,
                "message": update.message,
            },
        )()

        await show_video_list(
            query,
            context,
            search=text,
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
            "Шаг 2/6. Отправь описание видео: "
            "что именно разбирается в ролике."
        )

    elif step == "description":
        state["description"] = text
        state["step"] = "category"

        await update.message.reply_text(
            "Шаг 3/6. Отправь код категории:\n\n"
            + "\n".join(
                f"{key} — {value}"
                for key, value in CATEGORIES.items()
            )
        )

    elif step == "category":
        if text not in CATEGORIES:
            await update.message.reply_text(
                "Неизвестная категория. Выбери код:\n"
                + ", ".join(CATEGORIES.keys())
            )
            return

        state["category"] = text
        state["step"] = "duration"

        await update.message.reply_text(
            "Шаг 4/6. Укажи длительность, например 12:35.\n"
            "Если не знаешь — отправь символ —"
        )

    elif step == "duration":
        state["duration"] = "" if text == "—" else text
        state["step"] = "link"

        await update.message.reply_text(
            "Шаг 5/6. Отправь ссылку на видео."
        )

    elif step == "link":
        if not text.startswith(("https://", "http://")):
            await update.message.reply_text(
                "Отправь корректную ссылку, начинающуюся с https://"
            )
            return

        state["link"] = text
        state["step"] = "keywords"

        await update.message.reply_text(
            "Шаг 6/6. Отправь ключевые слова через запятую.\n"
            "Например: техника, присед, глубина.\n"
            "Если не нужны — отправь символ —"
        )

    elif step == "keywords":
        state["keywords"] = "" if text == "—" else text

        try:
            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO videos
                    (title, description, category, duration,
                     link, url, keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state["title"],
                        state["description"],
                        state["category"],
                        state["duration"],
                        state["link"],
                        state["link"],
                        state["keywords"],
                    ),
                )

        except sqlite3.Error:
            logging.exception("Не удалось сохранить видео")

            await update.message.reply_text(
                "❌ Не удалось сохранить видео. "
                "Посмотри ошибку в Console на FadeHost."
            )
            return

        title = state["title"]
        context.user_data.pop("add_video", None)

        await update.message.reply_text(
            f"✅ Видео «{title}» добавлено!",
            reply_markup=main_keyboard(),
        )


# ---------------- HELP ----------------

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "/start — главное меню\n"
        "/addvideo — добавить видео (администратор)\n"
        "/cancel — отменить действие\n"
        "/help — помощь"
    )


# ---------------- START BOT ----------------

def main():
    validate_config()
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", addvideo))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    logging.info("POWERLIB запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()
