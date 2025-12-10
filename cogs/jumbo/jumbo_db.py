# cogs/jumbo/jumbo_db.py

import asyncpg
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
        """購入期限後にクローズ"""
        await self.db.conn.execute("""
            UPDATE jumbo_config
            SET is_open = FALSE
            WHERE guild_id=$1
        """, guild_id)

    async def reset_config(self, guild_id: str):
        """設定の完全リセット"""
        await self.db.conn.execute(
            "DELETE FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )

    # ============================================================
    # 番号生成・保存
    # ============================================================

    async def add_number(self, guild_id: str, user_id: str, number: str):
        """購入番号を保存（被りなし）"""
        try:
            await self.db.conn.execute("""
                INSERT INTO jumbo_entries (guild_id, user_id, number)
                VALUES ($1, $2, $3)
            """, guild_id, user_id, number)
            return True
        except asyncpg.UniqueViolationError:
            return False  # 重複した場合は False

    async def get_all_numbers(self, guild_id: str):
        """ギルド内の全番号取得"""
        return await self.db.conn.fetch("""
            SELECT * FROM jumbo_entries
            WHERE guild_id=$1
            ORDER BY number ASC
        """, guild_id)

    async def get_user_numbers(self, guild_id: str, user_id: str):
        """ユーザーが買った全番号"""
        return await self.db.conn.fetch("""
            SELECT number FROM jumbo_entries
            WHERE guild_id=$1 AND user_id=$2
            ORDER BY number ASC
        """, guild_id, user_id)

    async def clear_entries(self, guild_id: str):
        """全番号リセット"""
        await self.db.conn.execute("""
            DELETE FROM jumbo_entries WHERE guild_id=$1
        """, guild_id)

    # ============================================================
    # 当選番号関連
    # ============================================================

    async def set_winner(self, guild_id: str, rank: int, number: str, user_id: str):
        """当選番号を記録"""
        await self.db.conn.execute("""
            INSERT INTO jumbo_winners (guild_id, rank, number, user_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id, rank, number)
            DO NOTHING;
        """, guild_id, rank, number, user_id)

    async def get_winners_by_rank(self, guild_id: str, rank: int):
        """等級ごとの当選一覧"""
        return await self.db.conn.fetch("""
            SELECT * FROM jumbo_winners
            WHERE guild_id=$1 AND rank=$2
            ORDER BY number ASC
        """, guild_id, rank)

    async def get_all_winners(self, guild_id: str):
        """全等級の当選結果"""
        return await self.db.conn.fetch("""
            SELECT * FROM jumbo_winners
            WHERE guild_id=$1
            ORDER BY rank ASC, number ASC
        """, guild_id)

    async def clear_winners(self, guild_id: str):
        """当選履歴リセット"""
        await self.db.conn.execute("""
            DELETE FROM jumbo_winners WHERE guild_id=$1
        """, guild_id)
