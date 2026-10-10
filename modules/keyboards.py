
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.categories import CATEGORIES


def main_keyboard():
    """Главное меню POWERLIB."""
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
                "🏆 Соревнования",
                callback_data="cat:competition",
            )
        ],
        [
            InlineKeyboardButton(
                "🩹 Проблемы и ошибки",
                callback_data="cat:problems",
            )
        ],
        [
            InlineKeyboardButton("🔎 Поиск", callback_data="search"),
            InlineKeyboardButton("⭐ Избранное", callback_data="favorites"),
        ],
    ])


def navigation_keyboard(back_data="home"):
    """Кнопки возврата и перехода в главное меню."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"back:{back_data}",
            ),
            InlineKeyboardButton(
                "🏠 Главное меню",
                callback_data="home",
            ),
        ]
    ])
