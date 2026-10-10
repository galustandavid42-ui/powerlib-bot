
from handlers.database import db


def toggle_favorite(user_id: int, video_id: int) -> str:
    """Добавляет видео в избранное или удаляет его оттуда."""

    with db() as conn:
        video = conn.execute(
            "SELECT id FROM videos WHERE id = ?",
            (video_id,),
        ).fetchone()

        if not video:
            return "Видео не найдено."

        existing = conn.execute(
            """
            SELECT 1 FROM favorites
            WHERE user_id = ? AND video_id = ?
            """,
            (user_id, video_id),
        ).fetchone()

        if existing:
            conn.execute(
                """
                DELETE FROM favorites
                WHERE user_id = ? AND video_id = ?
                """,
                (user_id, video_id),
            )
            return (
                "Убрано из избранного. "
                "Обнови раздел, чтобы увидеть изменения."
            )

        conn.execute(
            """
            INSERT OR IGNORE INTO favorites (user_id, video_id)
            VALUES (?, ?)
            """,
            (user_id, video_id),
        )

        return "Добавлено в избранное."
