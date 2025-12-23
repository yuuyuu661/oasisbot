# cogs/jumbo/jumbo_db.py

import asyncpg
from asyncpg.exceptions import UniqueViolationError
from datetime import datetime


class JumboDB:
    """
    年末ジャンボ専用 DB 管理クラス
    Databaseクラス（bot.db）を内部で利用する。
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db   # 既存の Database クラスを利用

    # ============================================================
    # ★ テーブル初期化（自動生成）
    # ============================================================

    async def init_tables(self):
        """年末ジャンボ用テーブルを作成（存在しなければ）"""

        # ------------------------------
        # 開催設定
        # ------------------------------
        await self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS jumbo_config (
                guild_id        TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL,
                deadline        TIMESTAMP NOT NULL,
                is_open         BOOLEAN NOT NULL DEFAULT TRUE,
                prize_paid      BOOLEAN DEFAULT FALSE
            );
        """)

        # ★ 既存DB救済（後付けカラム）
        await self.db.conn.execute("""
            ALTER TABLE jumbo_config
            ADD COLUMN IF NOT EXISTS winning_number VARCHAR(6);
        """)

        await self.db.conn.execute("""
            ALTER TABLE jumbo_config
            ADD COLUMN IF NOT EXISTS prize_paid BOOLEAN DEFAULT FALSE;
        """)

        # ------------------------------
        # 購入番号
        # ------------------------------
        await self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS jumbo_entries (
                guild_id TEXT NOT NULL,
                user_id  TEXT NOT NULL,
                number   VARCHAR(6) NOT NULL,
                PRIMARY KEY (guild_id, number)
            );
        """)

        # ------------------------------
        # 当選結果（CREATEは1回だけ）
        # ------------------------------
        await self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS jumbo_winners (
                guild_id TEXT NOT NULL,
                rank     INT NOT NULL,
                number   VARCHAR(6) NOT NULL,
                user_id  TEXT NOT NULL,
                PRIMARY KEY (guild_id, rank, number)
            );
        """)

        # ★ 既存DB救済（後付けカラム）
        await self.db.conn.execute("""
            ALTER TABLE jumbo_winners
            ADD COLUMN IF NOT EXISTS match_count INT;
        """)

        await self.db.conn.execute("""
            ALTER TABLE jumbo_winners
            ADD COLUMN IF NOT EXISTS prize BIGINT DEFAULT 0;
        """)

    # ============================================================
    # 開催設定
    # ============================================================

    async def set_config(self, guild_id: str, title: str, description: str, deadline: datetime):
        """開催設定を保存"""
        await self.db.conn.execute("""
            INSERT INTO jumbo_config (guild_id, title, description, deadline, is_open)
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                title = $2,
                description = $3,
                deadline = $4,
                is_open = TRUE;
        """, guild_id, title, description, deadline)

    async def get_config(self, guild_id: str):
        return await self.db.conn.fetchrow(
            "SELECT * FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )

    async def close_config(self, guild_id: str):
        await self.db.conn.execute("""
            UPDATE jumbo_config
            SET is_open = FALSE
            WHERE guild_id=$1
        """, guild_id)

    async def reset_config(self, guild_id: str):
        await self.db.conn.execute(
            "DELETE FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )

    # ============================================================
    # 番号生成・保存
    # ============================================================

    async def add_number(self, guild_id: str, user_id: str, number: str):
        try:
            await self.db.conn.execute("""
                INSERT INTO jumbo_entries (guild_id, user_id, number)
                VALUES ($1, $2, $3)
            """, guild_id, user_id, number)
            return True
        except UniqueViolationError:
            return False
        except Exception as e:
            print("[JUMBO add_number ERROR]:", e)
            return False

    async def get_user_numbers(self, guild_id: str, user_id: str):
        return await self.db.conn.fetch("""
            SELECT number FROM jumbo_entries
            WHERE guild_id=$1 AND user_id=$2
            ORDER BY number ASC
        """, guild_id, user_id)

    async def get_all_entries(self, guild_id: str):
        return await self.db.conn.fetch("""
            SELECT guild_id, user_id, number
            FROM jumbo_entries
            WHERE guild_id=$1
        """, guild_id)

    async def clear_entries(self, guild_id: str):
        await self.db.conn.execute("""
            DELETE FROM jumbo_entries WHERE guild_id=$1
        """, guild_id)

    # ============================================================
    # 当選結果
    # ============================================================

    async def set_winner(
        self,
        guild_id: str,
        rank: int,
        number: str,
        user_id: str,
        match_count: int,
        prize: int
    ):
        await self.db.conn.execute("""
            INSERT INTO jumbo_winners
                (guild_id, rank, number, user_id, match_count, prize)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (guild_id, rank, number)
            DO NOTHING;
        """, guild_id, rank, number, user_id, match_count, prize)

    async def get_all_winners(self, guild_id: str):
        return await self.db.conn.fetch("""
            SELECT * FROM jumbo_winners
            WHERE guild_id=$1
            ORDER BY rank ASC, number ASC
        """, guild_id)

    async def clear_winners(self, guild_id: str):
        await self.db.conn.execute("""
            DELETE FROM jumbo_winners WHERE guild_id=$1
        """)

    # ============================================================
    # 当選番号設定
    # ============================================================

    async def set_winning_number(self, guild_id: str, winning_number: str):
        result = await self.db.conn.execute("""
            UPDATE jumbo_config
            SET winning_number = $2,
                prize_paid = FALSE
            WHERE guild_id = $1
        """, guild_id, winning_number)

        if result == "UPDATE 0":
            raise RuntimeError(
                "ジャンボが未開催です。先に /年末ジャンボ開催 を実行してください。"
            )
