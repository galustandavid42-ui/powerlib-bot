
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()

try:
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else 0
except ValueError:
    ADMIN_ID = 0


def validate_config():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN в переменных окружения."
        )

    if not ADMIN_ID:
        raise RuntimeError(
            "Не задан корректный ADMIN_ID в переменных окружения."
        )

