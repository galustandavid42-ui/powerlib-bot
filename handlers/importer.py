```python
import asyncio
import logging
import re
from urllib.parse import urlparse, parse_qs

import yt_dlp

from handlers.database import db
from handlers.categories import CATEGORIES


MAX_LINKS = 20

CATEGORY_KEYWORDS = {
    "squat": ("присед", "squat"),
    "bench": ("жим", "bench", "bench press"),
    "deadlift": ("тяга", "становая", "deadlift"),
    "nutrition": ("питание", "еда", "nutrition", "diet", "recovery"),
    "competition": ("соревнован", "чемпионат", "competition", "meet"),
    "problems": ("ошибк", "боль", "травм", "mistake", "injury"),
}


def normalize_youtube_url(url):
    url = url.strip()
    parsed = urlparse(url)

    if parsed.hostname not in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
    ):
        return None

    if parsed.hostname.endswith("youtu.be"):
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
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


async def import_videos(message, links):
    results = []

    for url in links:
        normalized = normalize_youtube_url(url)

        if not normalized:
            results.append(f"❌ Некорректная ссылка: {url}")
            continue

        try:
            info = await asyncio.to_thread(get_video_info, normalized)

            title = (info.get("title") or "").strip()
            description = (info.get("description") or "").strip()
            duration_seconds = info.get("duration")
            duration = ""

            if duration_seconds is not None:
                minutes, seconds = divmod(int(duration_seconds), 60)
                hours, minutes = divmod(minutes, 60)
                duration = (
                    f"{hours}:{minutes:02}:{seconds:02}"
                    if hours
                    else f"{minutes}:{seconds:02}"
                )

            category = choose_category(title, description)
            thumbnail = info.get("thumbnail") or ""
            channel = info.get("channel") or info.get("uploader") or ""

            with db() as conn:
                existing = conn.execute(
                    "SELECT id FROM videos WHERE link = ? OR url = ?",
                    (normalized, normalized),
                ).fetchone()

                if existing:
                    results.append(f"⏭ Уже есть в каталоге: {title}")
                    continue

                conn.execute(
                    """
                    INSERT INTO videos
                    (title, description, category, duration, link, url, keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title or normalized,
                        description,
                        category,
                        duration,
                        normalized,
                        normalized,
                        channel,
                    ),
                )

            results.append(
                f"✅ {title or normalized}\n"
                f"Категория: {CATEGORIES.get(category, category)}\n"
                f"Длительность: {duration or 'не указана'}\n"
                f"Превью: {'есть' if thumbnail else 'нет'}"
            )

        except Exception:
            logging.exception("Ошибка импорта видео: %s", url)
            results.append(f"❌ Не удалось получить данные: {url}")

    await message.reply_text(
        "Результат импорта:\n\n" + "\n\n".join(results)
    )
```
