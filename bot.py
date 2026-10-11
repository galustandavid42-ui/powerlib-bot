
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
from handlers.admin import addvideo, cancel
from handlers.importer import import_videos
from modules.keyboards import main_keyboard


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


async def importvideos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.info("IMPORTVIDEOS: получена команда")

    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        logger.warning("IMPORTVIDEOS: отсутствует user или message")
        return

    if user.id != ADMIN_ID:
        logger.warning(
            "IMPORTVIDEOS: отказ в доступе для user_id=%s",
            user.id,
        )
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

    logger.info("IMPORTVIDEOS: ожидание ссылок от администратора")


async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.pop("waiting_import", None)
    context.user_data.pop("waiting_search", None)

    logger.info("CANCEL: сброшены состояния ожидания")

    await cancel(update, context)


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
        links = [link.rstrip(".,;!?)\"']") for link in links]

        if not links:
            await message.reply_text(
                "❌ Не нашёл ссылок.\n"
                "Отправь ссылки на YouTube, по одной на строке."
            )
            return

        if len(links) > 20:
            await message.reply_text(
                f"Получено {len(links)} ссылок. "
                "Обработаю первые 20."
            )
            links = links[:20]

        status_message = await message.reply_text(
            f"⏳ Начинаю импорт: {len(links)} ссылок.\n"
            "Получение информации с YouTube может занять время."
        )

        logger.info("IMPORTVIDEOS: начинаю обработку %s ссылок", len(links))

        try:
            await import_videos(message, links)
            logger.info("IMPORTVIDEOS: обработка завершена")

        except Exception:
            logger.exception("IMPORTVIDEOS: ошибка при обработке ссылок")
            await status_message.reply_text(
                "❌ Во время импорта произошла ошибка.\n"
                "Посмотри последние строки консоли FadeHost."
            )

        return

    if context.user_data.get("waiting_search"):
        context.user_data.pop("waiting_search", None)

        try:
            await handle_search(message, user, context, text)
        except Exception:
            logger.exception("Ошибка поиска")
            await message.reply_text(
                "❌ Ошибка поиска. Попробуй ещё раз."
            )

        return

    try:
        handled = await __import__(
            "handlers.admin",
            fromlist=["handle_admin_text"],
        ).handle_admin_text(update, context)

        if handled:
            return

    except Exception:
        logger.exception("Ошибка обработки команды администратора")
        await message.reply_text(
            "❌ Ошибка обработки сообщения. Подробности в консоли."
        )
        return

    await message.reply_text(
        "Выбери раздел в меню или нажми 🔎 Поиск.",
        reply_markup=main_keyboard(),
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Необработанная ошибка при обработке обновления",
        exc_info=context.error,
    )


def main():
    validate_config()
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", addvideo))
    app.add_handler(CommandHandler("importvideos", importvideos))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("POWERLIB запускается")
    app.run_polling()


if __name__ == "__main__":
    main()
