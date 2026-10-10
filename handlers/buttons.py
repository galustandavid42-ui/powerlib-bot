from telegram import Update
from telegram.ext import ContextTypes

from handlers.database import db
from handlers.categories import CATEGORIES
from handlers.videos import show_video_list, send_video_card
from modules.keyboards import main_keyboard, navigation_keyboard


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        context.user_data.pop("waiting_search", None)
        context.user_data["last_view"] = "home"

        await query.message.reply_text(
            "🏋️ Главное меню",
            reply_markup=main_keyboard(),
        )

    elif data.startswith("back:"):
        destination = data.split(":", 1)[1]

        if destination == "home":
            context.user_data["last_view"] = "home"
            context.user_data.pop("waiting_search", None)

            await query.message.reply_text(
                "🏋️ Главное меню",
                reply_markup=main_keyboard(),
            )

        elif destination.startswith("cat:"):
            category = destination.split(":", 1)[1]
            await show_video_list(query, context, category=category)

        elif destination == "favorites":
            await show_video_list(query, context, favorites=True)

        elif destination == "search":
            context.user_data["waiting_search"] = True
            await query.message.reply_text(
                "🔎 Отправь слово или фразу для поиска.",
                reply_markup=navigation_keyboard("home"),
            )

    elif data.startswith("cat:"):
        category = data.split(":", 1)[1]

        if category not in CATEGORIES:
            await query.message.reply_text("Неизвестная категория.")
            return

        await show_video_list(query, context, category=category)

    elif data == "search":
        context.user_data["waiting_search"] = True
        context.user_data["last_view"] = "search"

        await query.message.reply_text(
            "🔎 Отправь слово или фразу для поиска.\n"
            "Например: постановка ног, мост, хват, разминка.",
            reply_markup=navigation_keyboard("home"),
        )

    elif data == "favorites":
        await show_video_list(query, context, favorites=True)

    elif data.startswith("video:"):
        video_id = int(data.split(":", 1)[1])

        with db() as conn:
            video = conn.execute(
                "SELECT * FROM videos WHERE id=?",
                (video_id,),
            ).fetchone()

        if not video:
            await query.message.reply_text(
                "Видео не найдено.",
                reply_markup=navigation_keyboard(),
            )
            return

        back_data = context.user_data.get("last_view", "home")

        await send_video_card(
            query.message,
            video,
            query.from_user.id,
            back_data=back_data,
        )

    elif data.startswith("fav:"):
        video_id = int(data.split(":", 1)[1])
        user_id = query.from_user.id

        with db() as conn:
            existing = conn.execute(
                """
                SELECT 1 FROM favorites
                WHERE user_id=? AND video_id=?
                """,
                (user_id, video_id),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    DELETE FROM favorites
                    WHERE user_id=? AND video_id=?
                    """,
                    (user_id, video_id),
                )
                message = "Убрано из избранного. Обнови раздел, чтобы увидеть изменения."
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO favorites (user_id, video_id)
                    VALUES (?, ?)
                    """,
                    (user_id, video_id),
                )
                message = "Добавлено в избранное."

        await query.message.reply_text(
            message,
            reply_markup=navigation_keyboard(
                context.user_data.get("last_view", "home")
            ),
        )
