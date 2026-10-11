
import logging
import re

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from handlers.config import BOT_TOKEN, ADMIN_ID, validate_config
from handlers.database import init_db
from handlers.start import start, help_command
from handlers.buttons import button_handler
from handlers.search import handle_search
from handlers.admin import addvideo, cancel, handle_admin_text
from handlers.importer import import_videos
from modules.keyboards import main_keyboard


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def importvideos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if user.id != ADMIN_ID:
        await message.reply_text(
            "⛔ Импорт доступен только администратору."
        )
        return

    context.user_data["waiting_import"] = True

    await message.reply_text(
        "📥 Массовый импорт POWERLIB\n\n"
        "Отправь одним сообщением до 20 ссылок на YouTube.\n"
        "Каждая ссылка должна быть на отдельной строке.\n\n"
        "Для отмены используй /cancel."
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

    if context.user_data.get("waiting_import"):
        if user.id != ADMIN_ID:
            context.user_data.pop("waiting_import", None)
            await message.reply_text("⛔ Нет доступа.")
            return

        context.user_data.pop("waiting_import", None)

        links = re.findall(r"https?://[^\s<>]+", text)
        links = [link.rstrip(".,;!?)\"]'") for link in links]

        if not links:
            await message.reply_text(
                "Не нашёл ссылок. Отправь ссылки на YouTube."
            )
            return

        if len(links) > 20:
            await message.reply_text(
                f"Получено {len(links)} ссылок. "
                "Обработаю первые 20; остальные отправь отдельно."
            )
            links = links[:20]

        await message.reply_text(
            f"⏳ Начинаю импорт: {len(links)} ссылок. "
            "Это может занять некоторое время."
        )
        await import_videos(message, links)
        return

    if context.user_data.get("waiting_search"):
        context.user_data.pop("waiting_search", None)
        await handle_search(message, user, context, text)
        return

    handled = await handle_admin_text(update, context)
    if handled:
        return

    await message.reply_text(
        "Выбери раздел в меню или нажми 🔎 Поиск.",
        reply_markup=main_keyboard(),
    )


def main():
    validate_config()
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", addvideo))
    app.add_handler(CommandHandler("importvideos", importvideos))
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
