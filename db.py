import os
import asyncpg
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()


class Database:
    def __init__(self):
        self.conn = None
        self.dsn = os.getenv("DATABASE_URL")

    # ------------------------------------------------------
    #   DB接続
    # ------------------------------------------------------
    async def connect(self):
        if self.conn is None:
            self.conn = await asyncpg.connect(self.dsn)

    # ------------------------------------------------------
    #   初期化（テーブル自動作成）
    # ------------------------------------------------------
class Database:
    def __init__(self):
        self.conn = None
        self.dsn = os.getenv("DATABASE_URL")

    # ------------------------------------------------------
    #   DB接続
    # ------------------------------------------------------
    async def connect(self):
        if self.conn is None:
            self.conn = await asyncpg.connect(self.dsn)

    # ------------------------------------------------------
    #   初期化（テーブル自動作成）
    # ------------------------------------------------------
    async def init_db(self):
        await self.connect()

        # Users テーブル（ギルド別通貨管理）
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
            """
        )

        # --------------------------------------------------
        # users テーブル：プレミアム演出用カラム追加
        # --------------------------------------------------
        col_check = await self.conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users';
            """
        )

        existing_cols = {row["column_name"] for row in col_check}

        if "premium_until" not in existing_cols:
            await self.conn.execute(
                """
                ALTER TABLE users
                ADD COLUMN premium_until TIMESTAMP;
                """
            )

        if "grad_color_1" not in existing_cols:
            await self.conn.execute(
                """
                ALTER TABLE users
                ADD COLUMN grad_color_1 TEXT;
                """
            )

        if "grad_color_2" not in existing_cols:
            await self.conn.execute(
                """
                ALTER TABLE users
                ADD COLUMN grad_color_2 TEXT;
                """
            )

        # 給料ロールテーブル
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS role_salaries (
                role_id TEXT PRIMARY KEY,
                salary INTEGER NOT NULL
            );
            """
        )

        # Settings テーブル
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                admin_roles TEXT[],
                currency_unit TEXT,
                log_pay TEXT,
                log_manage TEXT,
                log_salary TEXT
            );
            """
        )


        # 給料ロールテーブル
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS role_salaries (
                role_id TEXT PRIMARY KEY,
                salary INTEGER NOT NULL
            );
        """)

        # Settings テーブル（1行固定）
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                admin_roles TEXT[],
                currency_unit TEXT,
                log_pay TEXT,
                log_manage TEXT,
                log_salary TEXT
            );
        """)

        # サブスク設定テーブル
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS subscription_settings (
                guild_id TEXT PRIMARY KEY,
                standard_role TEXT,
                standard_price INTEGER,
                regular_role TEXT,
                regular_price INTEGER,
                premium_role TEXT,
                premium_price INTEGER,
                log_channel TEXT
            );
        """)

        # 面接設定テーブル
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interview_settings (
                guild_id TEXT PRIMARY KEY,
                interviewer_role TEXT,
                wait_role TEXT,
                done_role TEXT,
                reward_amount INTEGER,
                log_channel TEXT
            );
        """)
        # -----------------------------------------
        # 既存 settings テーブルに log_backup カラムが無ければ追加
        # -----------------------------------------
        col_check = await self.conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'settings';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "log_backup" not in existing_cols:
            print("🛠 settings テーブルに log_backup カラムを追加します…")
            await self.conn.execute("""
                ALTER TABLE settings ADD COLUMN log_backup TEXT;
            """)
            # NULL 初期化（念のため）
            await self.conn.execute("""
                UPDATE settings SET log_backup = NULL WHERE id = 1;
            """)
            print("✅ log_backup カラム追加完了")

        # ホテル設定テーブル
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS hotel_settings (
                guild_id TEXT PRIMARY KEY,
                manager_role TEXT,
                log_channel TEXT,
                sub_role TEXT,
                ticket_price_1 INTEGER,
                ticket_price_10 INTEGER,
                ticket_price_30 INTEGER
            );
        """)

        # ホテルチケット所持テーブル
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS hotel_tickets (
                user_id TEXT,
                guild_id TEXT,
                tickets INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
        """)

        # ホテルルーム管理テーブル
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS hotel_rooms (
                channel_id TEXT PRIMARY KEY,
                guild_id TEXT,
                owner_id TEXT,
                expire_at TIMESTAMP
            );
        """)

        # =============================
        # スロット：セッション管理
        # =============================
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS slot_sessions (
                session_id   TEXT PRIMARY KEY,
                guild_id     TEXT NOT NULL,
                channel_id   TEXT NOT NULL,
                host_id      TEXT NOT NULL,

                rate         INTEGER NOT NULL,
                fee          INTEGER NOT NULL,

                total_pool   INTEGER NOT NULL DEFAULT 0,
                turn_index   INTEGER NOT NULL DEFAULT 0,
                status       TEXT NOT NULL, -- waiting / playing / finished
                created_at   TIMESTAMP DEFAULT NOW()
            );
        """)

        # =============================
        # スロット：参加者キュー
        # =============================
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS slot_players (
                session_id TEXT,
                user_id    TEXT,
                position   INTEGER,
                joined_at  TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (session_id, user_id)
            );
        """)

        # =====================================================
        # ギャンブル機能のテーブル（ここが重要）
        # =====================================================

        # ギャンブル進行中データ
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gamble_current (
                guild_id   TEXT PRIMARY KEY,
                starter_id TEXT,
                opponent_id TEXT,
                title      TEXT,
                content    TEXT,
                expire_at  TIMESTAMP,
                status     TEXT,   -- 'waiting' / 'betting' / 'closed'
                winner     TEXT    -- 'A' or 'B' or NULL
            );
        """)

        # ギャンブルベット一覧
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gamble_bets (
                guild_id TEXT,
                user_id  TEXT,
                side     TEXT,     -- 'A' or 'B'
                amount   INTEGER
            );
        """)
        # =============================
        # ★ 年末ジャンボ テーブル追加 ↓
        # =============================

        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS jumbo_entries (
            guild_id TEXT,
            user_id TEXT,
            number TEXT,
            purchased_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (guild_id, number)
        )
        """)

        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS jumbo_config (
            guild_id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            deadline TIMESTAMP,
            is_open BOOLEAN
        )
        """)

        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS jumbo_winners (
            guild_id TEXT,
            rank INT,
            number TEXT,
            user_id TEXT,
            PRIMARY KEY (guild_id, rank, number)
        )
        """)

        # ------------------------------------------------------
        # settings の初期行作成
        # ------------------------------------------------------
        exists = await self.conn.fetchval("SELECT id FROM settings WHERE id = 1")
        if exists is None:
            await self.conn.execute("""
                INSERT INTO settings
                    (id, admin_roles, currency_unit, log_pay, log_manage, log_salary)
                VALUES
                    (1, ARRAY[]::TEXT[], 'spt', NULL, NULL, NULL);
            """)
            print("🔧 Settings 初期化行を作成しました")

    # ------------------------------------------------------
    #   ユーザー残高（ギルド別管理）
    # ------------------------------------------------------
    async def get_user(self, user_id, guild_id):
        row = await self.conn.fetchrow(
            "SELECT * FROM users WHERE user_id=$1 AND guild_id=$2",
            user_id, guild_id
        )
        if not row:
            await self.conn.execute(
                "INSERT INTO users (user_id, guild_id, balance) VALUES ($1, $2, 0)",
                user_id, guild_id
            )
            row = await self.conn.fetchrow(
                "SELECT * FROM users WHERE user_id=$1 AND guild_id=$2",
                user_id, guild_id
            )
        return row

    async def set_balance(self, user_id, guild_id, amount):
        await self.get_user(user_id, guild_id)
        await self.conn.execute(
            "UPDATE users SET balance=$1 WHERE user_id=$2 AND guild_id=$3",
            amount, user_id, guild_id
        )

    async def add_balance(self, user_id, guild_id, amount):
        user = await self.get_user(user_id, guild_id)
        new_amount = user["balance"] + amount
        await self.set_balance(user_id, guild_id, new_amount)
        return new_amount

    async def remove_balance(self, user_id, guild_id, amount):
        user = await self.get_user(user_id, guild_id)
        new_amount = max(0, user["balance"] - amount)
        await self.set_balance(user_id, guild_id, new_amount)
        return new_amount

    async def get_all_balances(self, guild_id):
        return await self.conn.fetch(
            "SELECT * FROM users WHERE guild_id=$1 ORDER BY balance DESC",
            guild_id
        )

    # ------------------------------------------------------
    #   給料ロール関連
    # ------------------------------------------------------
    async def set_salary(self, role_id, salary):
        await self.conn.execute("""
            INSERT INTO role_salaries (role_id, salary)
            VALUES ($1, $2)
            ON CONFLICT (role_id)
            DO UPDATE SET salary=$2;
        """, role_id, salary)

    async def get_salaries(self):
        return await self.conn.fetch("SELECT * FROM role_salaries")

    # ------------------------------------------------------
    #   Settings
    # ------------------------------------------------------
    async def get_settings(self):
        return await self.conn.fetchrow("SELECT * FROM settings WHERE id = 1")

    async def update_settings(self, **kwargs):
        columns = []
        values = []
        idx = 1

        for key, value in kwargs.items():
            columns.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1

        sql = f"UPDATE settings SET {', '.join(columns)} WHERE id = 1"
        await self.conn.execute(sql, *values)

    # ------------------------------------------------------
    #   ホテルチケット管理
    # ------------------------------------------------------
    async def get_tickets(self, user_id, guild_id):
        row = await self.conn.fetchrow(
            "SELECT tickets FROM hotel_tickets WHERE user_id=$1 AND guild_id=$2",
            user_id, guild_id
        )
        if not row:
            await self.conn.execute(
                "INSERT INTO hotel_tickets (user_id, guild_id, tickets) VALUES ($1, $2, 0)",
                user_id, guild_id
            )
            return 0
        return row["tickets"]

    async def add_tickets(self, user_id, guild_id, amount):
        current = await self.get_tickets(user_id, guild_id)
        new_amount = current + amount
        await self.conn.execute(
            "UPDATE hotel_tickets SET tickets=$1 WHERE user_id=$2 AND guild_id=$3",
            new_amount, user_id, guild_id
        )
        return new_amount

    async def remove_tickets(self, user_id, guild_id, amount):
        current = await self.get_tickets(user_id, guild_id)
        new_amount = max(0, current - amount)
        await self.conn.execute(
            "UPDATE hotel_tickets SET tickets=$1 WHERE user_id=$2 AND guild_id=$3",
            new_amount, user_id, guild_id
        )
        return new_amount

    # ------------------------------------------------------
    #   ホテルルーム管理
    # ------------------------------------------------------
    async def save_room(self, channel_id, guild_id, owner_id, expire_at):
        await self.conn.execute("""
            INSERT INTO hotel_rooms (channel_id, guild_id, owner_id, expire_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (channel_id)
            DO UPDATE SET expire_at=$4;
        """, channel_id, guild_id, owner_id, expire_at)

    async def delete_room(self, channel_id):
        await self.conn.execute(
            "DELETE FROM hotel_rooms WHERE channel_id=$1",
            channel_id
        )

    async def get_room(self, channel_id):
        return await self.conn.fetchrow(
            "SELECT * FROM hotel_rooms WHERE channel_id=$1",
            channel_id
        )

    # --------------------------------------------------
    # プレミアム付与（days=None で永久）
    # --------------------------------------------------
    async def set_premium(self, user_id, guild_id, days: int | None = 30):
        await self.get_user(user_id, guild_id)

        if days is None:
            premium_until = None
        else:
            premium_until = datetime.utcnow() + timedelta(days=days)

        await self.conn.execute(
            """
            UPDATE users
            SET premium_until = $3
            WHERE user_id = $1
              AND guild_id = $2
            """,
            user_id,
            guild_id,
            premium_until
        )

    # --------------------------------------------------
    # プレミアム判定
    # --------------------------------------------------
    async def is_premium(self, user_id, guild_id) -> bool:
        row = await self.get_user(user_id, guild_id)

        premium_until = row.get("premium_until")
        if not premium_until:
            return False

        return premium_until > datetime.utcnow()

    # --------------------------------------------------
    # グラデーション色保存
    # --------------------------------------------------
    async def set_gradient_color(
        self,
        user_id,
        guild_id,
        c1: str | None = None,
        c2: str | None = None
    ):
        await self.get_user(user_id, guild_id)

        await self.conn.execute(
            """
            UPDATE users
            SET grad_color_1 = COALESCE($3, grad_color_1),
                grad_color_2 = COALESCE($4, grad_color_2)
            WHERE user_id = $1
              AND guild_id = $2
            """,
            user_id,
            guild_id,
            c1,
            c2
        )

    # --------------------------------------------------
    # グラデーション色取得
    # --------------------------------------------------
    async def get_gradient_color(self, user_id, guild_id):
        row = await self.get_user(user_id, guild_id)

        return (
            row.get("grad_color_1"),
            row.get("grad_color_2"),
        )


# =============================
# スロットDB操作
# =============================

async def create_slot_session(self, session_id, guild_id, channel_id, host_id, rate, fee):
    await self.conn.execute("""
        INSERT INTO slot_sessions
            (session_id, guild_id, channel_id, host_id, rate, fee, status)
        VALUES
            ($1, $2, $3, $4, $5, $6, 'waiting')
    """, session_id, guild_id, channel_id, host_id, rate, fee)


async def add_slot_player(self, session_id, user_id, position):
    await self.conn.execute("""
        INSERT INTO slot_players (session_id, user_id, position)
        VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING
    """, session_id, user_id, position)


async def get_slot_players(self, session_id):
    return await self.conn.fetch("""
        SELECT user_id FROM slot_players
        WHERE session_id = $1
        ORDER BY position
    """, session_id)


async def update_slot_turn(self, session_id, turn_index, total_pool):
    await self.conn.execute("""
        UPDATE slot_sessions
        SET turn_index = $2,
            total_pool = $3
        WHERE session_id = $1
    """, session_id, turn_index, total_pool)


async def finish_slot_session(self, session_id):
    await self.conn.execute("""
        UPDATE slot_sessions
        SET status = 'finished'
        WHERE session_id = $1
    """, session_id)



