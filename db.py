import os
import asyncpg
from dotenv import load_dotenv
import asyncio

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

    async def _ensure_conn(self):
        if self.conn is None:
            await self.connect()

    # ------------------------------------------------------
    #   初期化（テーブル自動作成）
    # ------------------------------------------------------
    async def init_db(self):
        await self.connect()

        # Users テーブル（ギルド別通貨管理）
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
        """)

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
                admin_roles TEXT[],         -- 通貨管理ロールID配列
                currency_unit TEXT,         -- 通貨単位
                log_pay TEXT,               -- 通貨ログ
                log_manage TEXT,            -- 管理ログ
                log_interview TEXT,         -- 面接ログ
                log_salary TEXT,            -- 給料ログ
                log_hotel TEXT,             -- ホテルログ
                log_backup TEXT             -- バックアップ用チャンネル
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

        # 初期設定が無ければ作成
        exists = await self.conn.execute("""
            INSERT INTO settings
                (id, admin_roles, currency_unit,
                 log_pay, log_manage, log_interview, log_salary, log_hotel, log_backup)
            VALUES
                (1, ARRAY[]::TEXT[], 'rrc',
                 NULL, NULL, NULL, NULL, NULL, NULL)
            ON CONFLICT (id) DO NOTHING;
        """)

        print("🔧 Settings 初期化行を作成しました")

        # db.py の init_db() 内、hotel_settings 作成の後あたりに追記
        col_check = await self.conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'hotel_settings';
        """)
        existing_cols = {row["column_name"] for row in col_check}

        if "category_ids" not in existing_cols:
            await self.conn.execute("""
                ALTER TABLE hotel_settings ADD COLUMN category_ids TEXT[];
            """)
            await self.conn.execute("""
                UPDATE hotel_settings SET category_ids = ARRAY[]::TEXT[] WHERE category_ids IS NULL;
            """)

        # ==================================================
        # 年末ジャンボ（JUMBO）テーブル初期化
        # ==================================================
        await self.init_jumbo_tables()


    # ------------------------------------------------------
    #   ユーザー残高（ギルド別管理）
    # ------------------------------------------------------
    async def get_user(self, user_id, guild_id):
        await self._ensure_conn()

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
            # 自動作成
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
    # ------------------------------------------------------
    #   バックアップ用スナップショット
    #   users（残高）と hotel_tickets（チケット）をまとめてJSON化
    # ------------------------------------------------------
    async def export_user_snapshot(self) -> dict:
        """全ユーザーの残高・チケットをまとめて取得してJSON用dictで返す"""

        users_rows = await self.conn.fetch(
            "SELECT user_id, guild_id, balance FROM users"
        )
        tickets_rows = await self.conn.fetch(
            "SELECT user_id, guild_id, tickets FROM hotel_tickets"
        )

        users = []
        for r in users_rows:
            users.append(
                {
                    "user_id": str(r["user_id"]),
                    "guild_id": str(r["guild_id"]),
                    "balance": int(r["balance"]),
                }
            )

        tickets = []
        for r in tickets_rows:
            tickets.append(
                {
                    "user_id": str(r["user_id"]),
                    "guild_id": str(r["guild_id"]),
                    "tickets": int(r["tickets"]),
                }
            )

        return {
            "version": 1,
            "users": users,
            "tickets": tickets,
        }

    # ------------------------------------------------------
    #   スナップショットからの復元
    #   overwrite=True のときは全削除してから上書き
    # ------------------------------------------------------
    async def import_user_snapshot(self, snapshot: dict, overwrite: bool = False):
        """export_user_snapshot で出力したJSONから復元する"""

        if overwrite:
            # 全削除してから入れ直す
            await self.conn.execute("TRUNCATE TABLE users")
            await self.conn.execute("TRUNCATE TABLE hotel_tickets")

        # users の復元
        for row in snapshot.get("users", []):
            user_id = str(row["user_id"])
            guild_id = str(row["guild_id"])
            balance = int(row["balance"])

            exists = await self.conn.fetchrow(
                "SELECT 1 FROM users WHERE user_id=$1 AND guild_id=$2",
                user_id, guild_id,
            )
            if exists:
                await self.conn.execute(
                    "UPDATE users SET balance=$1 WHERE user_id=$2 AND guild_id=$3",
                    balance, user_id, guild_id,
                )
            else:
                await self.conn.execute(
                    "INSERT INTO users (user_id, guild_id, balance) VALUES ($1, $2, $3)",
                    user_id, guild_id, balance,
                )

        # hotel_tickets の復元
        for row in snapshot.get("tickets", []):
            user_id = str(row["user_id"])
            guild_id = str(row["guild_id"])
            tickets = int(row["tickets"])

            exists = await self.conn.fetchrow(
                "SELECT 1 FROM hotel_tickets WHERE user_id=$1 AND guild_id=$2",
                user_id, guild_id,
            )
            if exists:
                await self.conn.execute(
                    "UPDATE hotel_tickets SET tickets=$1 WHERE user_id=$2 AND guild_id=$3",
                    tickets, user_id, guild_id,
                )
            else:
                await self.conn.execute(
                    "INSERT INTO hotel_tickets (user_id, guild_id, tickets) "
                    "VALUES ($1, $2, $3)",
                    user_id, guild_id, tickets,
                )

# ======================================================
#   年末ジャンボ（JUMBO）機能
# ======================================================

    # --------------------------------------------------
    #   テーブル初期化（init_db から呼ばれる想定）
    # --------------------------------------------------
    async def init_jumbo_tables(self):
        await self._ensure_conn()

        # 開催設定
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jumbo_config (
                guild_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                deadline TIMESTAMP NOT NULL,
                is_open BOOLEAN NOT NULL DEFAULT TRUE,
                winning_number VARCHAR(6),
                prize_paid BOOLEAN DEFAULT FALSE,
                panel_channel_id TEXT,
                panel_message_id TEXT
            );
        """)

        # 購入番号
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jumbo_entries (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                number VARCHAR(6) NOT NULL,
                PRIMARY KEY (guild_id, number)
            );
        """)

        # 当選者
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jumbo_winners (
                guild_id TEXT NOT NULL,
                rank INTEGER NOT NULL,
                number VARCHAR(6) NOT NULL,
                user_id TEXT NOT NULL,
                match_count INTEGER,
                prize BIGINT DEFAULT 0,
                PRIMARY KEY (guild_id, rank, number)
            );
        """)

    # --------------------------------------------------
    #   開催設定
    # --------------------------------------------------
    async def jumbo_set_config(self, guild_id, title, description, deadline):
        await self._ensure_conn()
        await self.conn.execute("""
            INSERT INTO jumbo_config
                (guild_id, title, description, deadline, is_open)
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                title=$2,
                description=$3,
                deadline=$4,
                is_open=TRUE;
        """, guild_id, title, description, deadline)

    async def jumbo_get_config(self, guild_id):
        await self._ensure_conn()
        return await self.conn.fetchrow(
            "SELECT * FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )

    async def jumbo_close_config(self, guild_id):
        await self._ensure_conn()
        await self.conn.execute("""
            UPDATE jumbo_config SET is_open=FALSE WHERE guild_id=$1
        """, guild_id)

    async def jumbo_reset_config(self, guild_id):
        await self._ensure_conn()
        await self.conn.execute(
            "DELETE FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )

    async def jumbo_set_panel_message(self, guild_id, channel_id, message_id):
        await self._ensure_conn()
        await self.conn.execute("""
            UPDATE jumbo_config
            SET panel_channel_id=$2,
                panel_message_id=$3
            WHERE guild_id=$1
        """, guild_id, channel_id, message_id)

    # --------------------------------------------------
    #   購入番号
    # --------------------------------------------------
    async def jumbo_add_number(self, guild_id, user_id, number):
        await self._ensure_conn()
        try:
            await self.conn.execute("""
                INSERT INTO jumbo_entries (guild_id, user_id, number)
                VALUES ($1, $2, $3)
            """, guild_id, user_id, number)
            return True
        except asyncpg.exceptions.UniqueViolationError:
            return False

    async def jumbo_get_user_numbers(self, guild_id, user_id):
        await self._ensure_conn()
        return await self.conn.fetch("""
            SELECT number FROM jumbo_entries
            WHERE guild_id=$1 AND user_id=$2
            ORDER BY number ASC
        """, guild_id, user_id)

    async def jumbo_get_all_entries(self, guild_id):
        await self._ensure_conn()
        return await self.conn.fetch("""
            SELECT guild_id, user_id, number
            FROM jumbo_entries
            WHERE guild_id=$1
        """, guild_id)

    async def jumbo_clear_entries(self, guild_id):
        await self._ensure_conn()
        await self.conn.execute(
            "DELETE FROM jumbo_entries WHERE guild_id=$1",
            guild_id
        )

    async def jumbo_count_entries(self, guild_id):
        await self._ensure_conn()
        row = await self.conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM jumbo_entries WHERE guild_id=$1",
            guild_id
        )
        return row["cnt"] if row else 0

    # --------------------------------------------------
    #   当選番号・当選者
    # --------------------------------------------------
    async def jumbo_set_winning_number(self, guild_id, winning_number):
        await self._ensure_conn()
        result = await self.conn.execute("""
            UPDATE jumbo_config
            SET winning_number=$2,
                prize_paid=FALSE
            WHERE guild_id=$1
        """, guild_id, winning_number)

        if result == "UPDATE 0":
            raise RuntimeError("ジャンボが未開催です")

    async def jumbo_add_winner(
        self, guild_id, rank, number, user_id, match_count, prize
    ):
        await self._ensure_conn()
        await self.conn.execute("""
            INSERT INTO jumbo_winners
                (guild_id, rank, number, user_id, match_count, prize)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
        """, guild_id, rank, number, user_id, match_count, prize)

    async def jumbo_get_winners(self, guild_id):
        await self._ensure_conn()
        return await self.conn.fetch("""
            SELECT * FROM jumbo_winners
            WHERE guild_id=$1
            ORDER BY rank ASC, number ASC
        """, guild_id)

    async def jumbo_clear_winners(self, guild_id):
        await self._ensure_conn()
        await self.conn.execute(
            "DELETE FROM jumbo_winners WHERE guild_id=$1",
            guild_id
        )
    # --------------------------------------------------
    #   ジャンボ購入枚数
    # --------------------------------------------------
    async def jumbo_count_user_entries(self, guild_id, user_id):
        await self._ensure_conn()
        row = await self.conn.fetchrow("""
            SELECT COUNT(*) AS cnt
            FROM jumbo_entries
            WHERE guild_id=$1 AND user_id=$2
        """, guild_id, user_id)
        return row["cnt"] if row else 0
    # ------------------------------------------------------
    #   ジャンボ：ユーザーの所持口数
    # ------------------------------------------------------
    async def jumbo_get_user_count(self, guild_id: str, user_id: str) -> int:
        await self._ensure_conn()
        row = await self.conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM jumbo_entries
            WHERE guild_id = $1 AND user_id = $2
            """,
            guild_id,
            user_id,
        )
        return row["cnt"] if row else 0
