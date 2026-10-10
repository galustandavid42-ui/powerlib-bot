
from telegram import Update
from telegram.ext import ContextTypes

from modules.keyboards import main_keyboard


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["last_view"] = "home"

    await update.effective_message.reply_text(
        "🏋️ POWERLIB\n"
        "Библиотека видео о пауэрлифтинге.\n\n"
        "Выбирай раздел. Видео будут показаны с превью, "
        "описанием и кнопкой просмотра.",
        reply_markup=main_keyboard(),
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "/start — главное меню\n"
        "/addvideo — добавить видео (администратор)\n"
        "/cancel — отменить действие\n"
        "/help — помощь"
    )
