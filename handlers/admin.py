```python
import logging
import sqlite3

from telegram import Update
from telegram.ext import ContextTypes

from handlers.config import ADMIN_ID
from handlers.database import db
from handlers.categories import CATEGORIES
from modules.keyboards import main_keyboard


def is_admin(user_id):
    return bool(ADMIN_ID) and int(user_id) == int(ADMIN_ID)


async def addvideo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("add_video", None)
    context.user_data.pop("waiting_search", None)
    await update.effective_message.reply_text(
        "Действие отменено.",
        reply_markup=main_keyboard(),
    )


async def handle_admin_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    message = update.effective_message
    user = update.effective_user

    if message is None or message.text is None or user is None:
        return False

    state = context.user_data.get("add_video")
    if not state:
        return False

    if not is_admin(user.id):
        context.user_data.pop("add_video", None)
        await message.reply_text("⛔ Нет доступа.")
        return True

    text = message.text.strip()
    step = state["step"]

    if step == "title":
        state["title"] = text
        state["step"] = "description"
        await message.reply_text("Шаг 2/6. Отправь описание видео.")

    elif step == "description":
        state["description"] = text
        state["step"] = "category"
        categories_text = "\n".join(
            f"{key} — {value}" for key, value in CATEGORIES.items()
        )
        await message.reply_text(
            "Шаг 3/6. Отправь код категории:\n\n" + categories_text
        )

    elif step == "category":
        if text not in CATEGORIES:
            await message.reply_text(
                "Неизвестная категория. Доступны: "
                + ", ".join(CATEGORIES.keys())
            )
            return True

        state["category"] = text
        state["step"] = "duration"
        await message.reply_text(
            "Шаг 4/6. Укажи длительность, например 12:35. "
            "Если не знаешь — отправь символ —"
        )

    elif step == "duration":
        state["duration"] = "" if text == "—" else text
        state["step"] = "link"
        await message.reply_text("Шаг 5/6. Отправь ссылку на видео.")

    elif step == "link":
        if not text.startswith(("https://", "http://")):
            await message.reply_text(
                "Ссылка должна начинаться с https:// или http://"
            )
            return True

        state["link"] = text
        state["step"] = "keywords"
        await message.reply_text(
            "Шаг 6/6. Отправь ключевые слова через запятую. "
            "Если не нужны — отправь символ —"
        )

    elif step == "keywords":
        keywords = "" if text == "—" else text

        try:
            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO videos
                    (title, description, category, duration, link, url, keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state["title"],
                        state["description"],
                        state["category"],
                        state["duration"],
                        state["link"],
                        state["link"],
                        keywords,
                    ),
                )
        except sqlite3.Error:
            logging.exception("Не удалось сохранить видео")
            await message.reply_text(
                "❌ Не удалось сохранить видео. Проверь Console на FadeHost."
            )
            return True

        title = state["title"]
        context.user_data.pop("add_video", None)
        await message.reply_text(
            f"✅ Видео «{title}» добавлено!",
            reply_markup=main_keyboard(),
        )

    return True
```
