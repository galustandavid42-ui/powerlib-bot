

import asyncio
import logging
import re
import sqlite3
from urllib.parse import urlparse, parse_qs

import yt_dlp


MAX_LINKS = 20

CATEGORY_KEYWORDS = {
    "squat": ("присед", "squat"),
    "bench": ("жим", "bench"),
    "deadlift": ("тяга", "становая", "deadlift"),
    "nutrition": ("питание", "еда", "nutrition", "recovery"),
    "competition": ("соревнован", "чемпионат", "competition", "meet"),
    "problems": ("ошибк", "боль", "травм", "mistake", "injury"),
}


def normalize_youtube_url(url):
    url = url.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host not in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
    ):
        return None

    if host.endswith("youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        video_id = parse_qs(parsed.query).get("v", [""])[0]

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None

    return f"https://www.youtube.com/watch?v={video_id}"


def choose_category(title, description):
    text = f"{title} {description}".lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(word in text for word in keywords):
            return category

    return "general"


def get_video_info(url):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 1,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


async def import_videos(message, links):
    results = []

    for raw_url in links[:MAX_LINKS]:
        normalized = normalize_youtube_url(raw_url)

        if not normalized:
            results.append(f"❌ Некорректная ссылка: {raw_url}")
            continue

        try:
            info = await asyncio.to_thread(
                get_video_info, normalized
            )

            title = (info.get("title") or normalized).strip()
            description = (
                info.get("description") or ""
            ).strip()
            seconds = info.get("duration")

            if seconds is not None:
                minutes, seconds = divmod(int(seconds), 60)
                hours, minutes = divmod(minutes, 60)
                duration = (
                    f"{hours}:{minutes:02}:{seconds:02}"
                    if hours
                    else f"{minutes}:{seconds:02}"
                )
            else:
                duration = ""

            category = choose_category(title, description)

            # Используем ту же функцию подключения к БД,
            # что и остальные функции POWERLIB.
            from handlers.database import db

            with db() as conn:
                existing = conn.execute(
                    """
                    SELECT id FROM videos
                    WHERE link = ? OR url = ?
                    """,
                    (normalized, normalized),
                ).fetchone()

                if existing:
                    results.append(
                        f"⏭ Уже есть в каталоге: {title}"
                    )
                    continue

                conn.execute(
                    """
                    INSERT INTO videos
                    (title, description, category, duration,
                     link, url, keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        description,
                        category,
                        duration,
                        normalized,
                        normalized,
                        info.get("channel")
                        or info.get("uploader")
                        or "",
                    ),
                )

            results.append(
                f"✅ {title}\n"
                f"Категория: {category}\n"
                f"Длительность: {duration or 'не указана'}"
            )

        except sqlite3.Error:
            logging.exception("Ошибка базы при импорте %s", normalized)
            results.append(f"❌ Ошибка базы данных: {normalized}")

        except Exception:
            logging.exception("Ошибка импорта %s", normalized)
            results.append(f"❌ Не удалось обработать: {normalized}")

    if len(links) > MAX_LINKS:
        results.append(
            f"⚠️ Обработаны первые {MAX_LINKS} ссылок."
        )

    # Telegram ограничивает длину одного сообщения.
    output = "📥 Результат импорта:\n\n"
    for result in results:
        if len(output) + len(result) + 2 > 3900:
            await message.reply_text(output)
            output = ""
        output += result + "\n\n"

    if output.strip():
        await message.reply_text(output)
