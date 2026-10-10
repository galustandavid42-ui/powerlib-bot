
from types import SimpleNamespace

from handlers.videos import show_video_list


async def handle_search(message, user, context, text):
    """Показывает результаты поиска видео."""
    query = SimpleNamespace(
        from_user=user,
        message=message,
    )

    await show_video_list(
        query,
        context,
        search=text.strip(),
    )
