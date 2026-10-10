
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard():
    """Главное меню POWERLIB."""
    keyboard = [
        [InlineKeyboardButton("🏋️ Присед", callback_data="category:squat")],
        [InlineKeyboardButton("🛏️ Жим лёжа", callback_data="category:bench")],
        [InlineKeyboardButton("⚡ Становая тяга", callback_data="category:deadlift")],
    ]

    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    """Кнопка возврата в главное меню."""
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data="back:main")]
    ]

    return InlineKeyboardMarkup(keyboard)

