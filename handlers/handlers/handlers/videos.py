
import asyncio
import logging
import re
from urllib.request import Request, urlopen

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.database import db
from handlers.categories import CATEGORIES
from modules.keyboards import navigation_keyboard


def youtube_video_id(link):
    patterns = [
        r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*?[&?]v=([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube-nocookie\.com/embed/([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)

    match = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", link)
    return match.group(1) if match else None


def get_thumbnail(video_id):
    if not video_id:
        return None

    for quality in ("maxresdefault", "hqdefault", "mqdefault"):
        image_url = (
            f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        )

        try:
            request = Request(
                image_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            with urlopen(request, timeout=8) as response:
                data = response.read()

            if data and len(data) > 1000:
                return data

        except Exception:
            logging.warning(
                "Не удалось получить превью для %s (%s)",
                video_id,
                quality,
            )

    return None


async def send_video_card(
    message,
    video,
    user_id,
    back_data="home",
):
    link = (video["link"] or video["url"] or "").strip()
    video_id = youtube_video_id(link)

    description = (video["description"] or "").strip()
    title = (video["title"] or "Без названия").strip()
    duration = (video["duration"] or "Не указана").strip()

    caption = (
        f"🎬 {title}\n\n"
        f"{description}\n\n"
        f"⏱ Длительность: {duration}"
    )

    with db() as conn:
        favorite = conn.execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND video_id=?",
            (user_id, video["id"]),
        ).fetchone()

    favorite_text = (
        "⭐ Убрать из избранного"
        if favorite
        else "⭐ В избранное"
    )

    buttons = []

    if link:
        buttons.append([
            InlineKeyboardButton("▶️ Смотреть видео", url=link)
        ])

    buttons.append([
        InlineKeyboardButton(
            favorite_text,
            callback_data=f"fav:{video['id']}",
        ),
        InlineKeyboardButton(
            "📖 Подробнее",
            callback_data=f"video:{video['id']}",
        ),
    ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data=f"back:{back_data}",
        ),
        InlineKeyboardButton(
            "🏠 Главное меню",
            callback_data="home",
        ),
    ])

    keyboard = InlineKeyboardMarkup(buttons)

    thumbnail = None
    if video_id:
        thumbnail = await asyncio.to_thread(
            get_thumbnail,
            video_id,
        )

    try:
        if thumbnail:
            await message.reply_photo(
                photo=thumbnail,
                caption=caption[:1024],
                reply_markup=keyboard,
            )
        else:
            text = caption
            if link:
                text += f"\n\n▶️ Ссылка: {link}"

            await message.reply_text(
                text[:4000],
                reply_markup=keyboard,
                disable_web_page_preview=False,
            )

    except Exception:
        logging.exception(
            "Ошибка отправки карточки видео %s",
            video["id"],
        )

        fallback = f"🎬 {title}\n\n{description}"
        if link:
            fallback += f"\n\n▶️ {link}"

        await message.reply_text(
            fallback[:4000],
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )


async def show_video_list(
    query,
    context,
    category=None,
    search=None,
    favorites=False,
):
    user_id = query.from_user.id

    if category:
        back_data = f"cat:{category}"
    elif favorites:
        back_data = "favorites"
    elif search is not None:
        back_data = "search"
    else:
        back_data = "home"

    context.user_data["last_view"] = back_data

    with db() as conn:
        if category:
            videos = conn.execute(
                "SELECT * FROM videos WHERE category=? ORDER BY id DESC",
                (category,),
            ).fetchall()
            heading = CATEGORIES.get(category, "Видео")

        elif favorites:
            videos = conn.execute(
                """
                SELECT v.*
                FROM videos v
                JOIN favorites f ON v.id = f.video_id
                WHERE f.user_id=?
                ORDER BY v.id DESC
                """,
                (user_id,),
            ).fetchall()
            heading = "⭐ Избранное"

        elif search is not None:
            term = f"%{search.lower()}%"
            videos = conn.execute(
                """
                SELECT * FROM videos
                WHERE lower(title) LIKE ?
                   OR lower(description) LIKE ?
                   OR lower(keywords) LIKE ?
                ORDER BY id DESC
                """,
                (term, term, term),
            ).fetchall()
            heading = f"🔎 Результаты поиска: {search}"

        else:
            return

    if not videos:
        await query.message.reply_text(
            f"{heading}\n\nВ этом разделе пока нет видео.",
            reply_markup=navigation_keyboard(back_data),
        )
        return

    await query.message.reply_text(
        f"{heading}\n\nНайдено видео: {len(videos)}",
        reply_markup=navigation_keyboard(back_data),
    )

    for video in videos:
        await send_video_card(
            query.message,
            video,
            user_id,
            back_data=back_data,
        )

