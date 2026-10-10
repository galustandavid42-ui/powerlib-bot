```python
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from handlers.config import BOT_TOKEN, validate_config
from handlers.database import init_db
from handlers.start import start, help_command
from handlers.buttons import button_handler
from handlers.search import handle_search
from handlers.admin import addvideo, cancel, handle_admin_text
from modules.keyboards import main_keyboard


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
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
