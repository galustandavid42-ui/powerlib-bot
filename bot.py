```python
import logging
import sqlite3
from types import SimpleNamespace

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from handlers.config import BOT_TOKEN, ADMIN_ID, validate_config
from handlers.database import db, init_db
from handlers.categories import CATEGORIES
from handlers.start import start, help_command
from handlers.buttons import button_handler
from handlers.videos import show_video_list
from modules.keyboards import main_keyboard


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def is_admin(user_id):
    return bool(ADMIN_ID) and int(user_id) == ADMIN_ID


async def addvideo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "⛔ Команда доступна только администратору."
        )
        return

    context.user_data["add_video"] = {"step": "title"}

    await update.effective_message.reply_text(
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

    await update.effective_message.reply_text(
        "Действие отменено.",
        reply_markup=main_keyboard(),
    )


async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    if message is None or message.text is None or user is None:
        return

    text = message.text.strip()
    user_id = user.id

    if context.user_data.get("waiting_search"):
        context.user_data.pop("waiting_search", None)

        query = SimpleNamespace(
            from_user=user,
            message=message,
        )

        await show_video_list(
            query,
            context,
            search=text,
        )
        return

    state = context.user_data.get("add_video")

    if not state:
        await message.reply_text(
            "Выбери раздел в меню или нажми 🔎 Поиск.",
            reply_markup=main_keyboard(),
        )
        return

    if not is_admin(user_id):
        context.user_data.pop("add_video", None)
        await message.reply_text("⛔ Нет доступа.")
        return

    step = state["step"]

    if step == "title":
        state["title"] = text
        state["step"] = "description"

        await message.reply_text(
            "Шаг 2/6. Отправь описание видео: "
            "что именно разбирается в ролике."
        )

    elif step == "description":
        state["description"] = text
        state["step"] = "category"

        categories_text = "\n".join(
            f"{key} — {value}"
            for key, value in CATEGORIES.items()
        )

        await message.reply_text(
            "Шаг 3/6. Отправь код категории:\n\n"
            f"{categories_text}"
        )

    elif step == "category":
        if text not in CATEGORIES:
            await message.reply_text(
                "Неизвестная категория. Выбери код:\n"
                + ", ".join(CATEGORIES.keys())
            )
            return

        state["category"] = text
        state["step"] = "duration"

        await message.reply_text(
            "Шаг 4/6. Укажи длительность, например 12:35.\n"
            "Если не знаешь — отправь символ —"
        )

    elif step == "duration":
        state["duration"] = "" if text == "—" else text
        state["step"] = "link"

        await message.reply_text(
            "Шаг 5/6. Отправь ссылку на видео."
        )

    elif step == "link":
        if not text.startswith(("https://", "http://")):
            await message.reply_text(
                "Отправь ссылку, начинающуюся с https:// или http://"
            )
            return

        state["link"] = text
        state["step"] = "keywords"

        await message.reply_text(
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
                    (
                        title,
                        description,
                        category,
                        duration,
                        link,
                        url,
                        keywords
                    )
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

            await message.reply_text(
                "❌ Не удалось сохранить видео. "
                "Посмотри ошибку в Console на FadeHost."
            )
            return

        title = state["title"]
        context.user_data.pop("add_video", None)

        await message.reply_text(
            f"✅ Видео «{title}» добавлено!",
            reply_markup=main_keyboard(),
        )


def main():
    validate_config()
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

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
```
