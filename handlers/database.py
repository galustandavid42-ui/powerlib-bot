
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "powerlib.db")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'general',
                duration TEXT DEFAULT '',
                link TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                keywords TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                UNIQUE(user_id, video_id)
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(videos)"
            ).fetchall()
        }

        migrations = {
            "title": "ALTER TABLE videos ADD COLUMN title TEXT NOT NULL DEFAULT ''",
            "description": "ALTER TABLE videos ADD COLUMN description TEXT NOT NULL DEFAULT ''",
            "category": "ALTER TABLE videos ADD COLUMN category TEXT NOT NULL DEFAULT 'general'",
            "duration": "ALTER TABLE videos ADD COLUMN duration TEXT DEFAULT ''",
            "link": "ALTER TABLE videos ADD COLUMN link TEXT NOT NULL DEFAULT ''",
            "url": "ALTER TABLE videos ADD COLUMN url TEXT NOT NULL DEFAULT ''",
            "keywords": "ALTER TABLE videos ADD COLUMN keywords TEXT DEFAULT ''",
        }

        for column, sql in migrations.items():
            if column not in columns:
                conn.execute(sql)

        conn.execute("""
            UPDATE videos
            SET link = url
            WHERE (link IS NULL OR link = '')
              AND url IS NOT NULL AND url != ''
        """)

        conn.execute("""
            UPDATE videos
            SET url = link
            WHERE (url IS NULL OR url = '')
              AND link IS NOT NULL AND link != ''
        """)

