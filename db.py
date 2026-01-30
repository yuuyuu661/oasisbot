import os
import asyncpg
from dotenv import load_dotenv
import asyncio
import time
import random
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

load_dotenv()

RACE_TIMES = ["09:00", "12:00", "15:00", "19:00", "22:00"]
DISTANCES = ["短距離", "マイル", "中距離", "長距離"]
SURFACES = ["芝", "ダート"]
CONDITIONS = ["良", "稍重", "重", "不良"]

class Database:
    def __init__(self):
        self.conn = None
        self.dsn = os.getenv("DATABASE_URL")
        self._lock = asyncio.Lock()

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
        # 既存 settings テーブルのカラム補完
        # -----------------------------------------
        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'settings';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        ADD_COLUMNS = {
            "log_pay": "TEXT",
            "log_manage": "TEXT",
            "log_interview": "TEXT",
            "log_salary": "TEXT",
            "log_hotel": "TEXT",
            "log_backup": "TEXT",
            "oasistchi_race_reset_date": "DATE",
        }

        for col, col_type in ADD_COLUMNS.items():
            if col not in existing_cols:
                print(f"🛠 settings テーブルに {col} カラムを追加します…")
                await self.conn.execute(
                    f"ALTER TABLE settings ADD COLUMN {col} {col_type};"
                )

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
        # ==================================================
        # おあしすっち（OASISTCHI）テーブル
        # ==================================================

        # ユーザーごとの育成枠
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS oasistchi_users (
                user_id TEXT PRIMARY KEY,
                slots INTEGER NOT NULL DEFAULT 1
            );
        """)

        # おあしすっち本体
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS oasistchi_pets (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,

                stage TEXT NOT NULL,              -- egg / adult
                egg_type TEXT,
                adult_key TEXT,
                name TEXT,

                growth REAL DEFAULT 0,
                hunger INTEGER DEFAULT 100,
                happiness INTEGER DEFAULT 50,
                poop BOOLEAN DEFAULT FALSE,

               notified_hatch BOOLEAN DEFAULT FALSE,

                last_pet REAL DEFAULT 0,
                last_interaction REAL DEFAULT 0,
                last_tick REAL DEFAULT 0,
                last_hunger_tick REAL DEFAULT 0,
                last_unhappy_tick REAL DEFAULT 0,

                notify_pet BOOLEAN DEFAULT FALSE,
                notify_care BOOLEAN DEFAULT FALSE,
                notify_food BOOLEAN DEFAULT FALSE,

                training_count INTEGER DEFAULT 0
            );
        """)

        # ==================================================
        # おあしすっち：図鑑 / 通知（永続化）
        # ==================================================

        # 図鑑（成体履歴）
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS oasistchi_dex (
                user_id TEXT NOT NULL,
                adult_key TEXT NOT NULL,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, adult_key)
            );
        """)

        # 通知設定
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS oasistchi_notify (
                user_id TEXT PRIMARY KEY,
                notify_poop BOOLEAN NOT NULL DEFAULT TRUE,
                notify_food BOOLEAN NOT NULL DEFAULT TRUE,
                notify_pet_ready BOOLEAN NOT NULL DEFAULT TRUE
            );
        """)

        # 既存DBにカラム補完（すでにテーブルがある場合）
        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_notify';
        """)
        existing_cols = {row["column_name"] for row in col_check}

        NOTIFY_COLUMNS = {
            "notify_poop": "BOOLEAN NOT NULL DEFAULT TRUE",
            "notify_food": "BOOLEAN NOT NULL DEFAULT TRUE",
            "notify_pet_ready": "BOOLEAN NOT NULL DEFAULT TRUE",
        }
        for col, col_type in NOTIFY_COLUMNS.items():
            if col not in existing_cols:
                await self.conn.execute(f"ALTER TABLE oasistchi_notify ADD COLUMN {col} {col_type};")

        # =========================
        # レース関連テーブル
        # =========================
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS race_schedules (
            id SERIAL PRIMARY KEY,
            race_no INTEGER NOT NULL,
            race_time TIME NOT NULL,
            entry_open_minutes INTEGER NOT NULL,
            max_entries INTEGER NOT NULL DEFAULT 8,
            entry_fee INTEGER NOT NULL DEFAULT 50000,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS race_entries (
            id SERIAL PRIMARY KEY,
            race_date DATE NOT NULL,
            schedule_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            pet_id INTEGER NOT NULL,
            paid BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (race_date, schedule_id, pet_id)
        );
        """)

        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS race_results (
            id SERIAL PRIMARY KEY,
            race_date DATE NOT NULL,
            schedule_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            pet_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            reward INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (race_date, schedule_id, pet_id)
        );
        """)
        

        # --------------------------------------------------
        # おあしすっち：レース用カラム補完
        # --------------------------------------------------
        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        # --------------------------------------------------
        # おあしすっち：特訓回数カラム補完（★今回の修正点）
        # --------------------------------------------------
        if "training_count" not in existing_cols:
            print("🛠 oasistchi_pets に training_count カラムを追加します…")
            await self.conn.execute("""
                ALTER TABLE oasistchi_pets
                ADD COLUMN training_count INTEGER NOT NULL DEFAULT 0;
            """)

        ADD_COLUMNS = {
            "raced_today": "BOOLEAN DEFAULT FALSE",
            "race_candidate": "BOOLEAN DEFAULT FALSE",
        }

        for col, col_type in ADD_COLUMNS.items():
            if col not in existing_cols:
                print(f"🛠 oasistchi_pets に {col} カラムを追加します…")
                await self.conn.execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )


        # --------------------------------------------------
        # おあしすっち：ステータス（特訓用）カラム補完
        # --------------------------------------------------
        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        ADD_COLUMNS = {
            "base_speed": "INTEGER DEFAULT 0",
            "base_stamina": "INTEGER DEFAULT 0",
            "base_power": "INTEGER DEFAULT 0",
            "train_speed": "INTEGER DEFAULT 0",
            "train_stamina": "INTEGER DEFAULT 0",
            "train_power": "INTEGER DEFAULT 0",
        }

        for col, col_type in ADD_COLUMNS.items():
            if col not in existing_cols:
                await self.conn.execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )
        # --------------------------------------------------
        # おあしすっち：ステータス用カラム補完
        # --------------------------------------------------
        ADD_STATUS_COLUMNS = {
            "speed": "INTEGER DEFAULT 0",
            "stamina": "INTEGER DEFAULT 0",
            "power": "INTEGER DEFAULT 0",
        }

        for col, col_type in ADD_STATUS_COLUMNS.items():
            if col not in existing_cols:
                print(f"🛠 oasistchi_pets に {col} カラムを追加します…")
                await self.conn.execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )

        # --------------------------------------------------
        # おあしすっち：時間管理用カラム補完
        # --------------------------------------------------
        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        TIME_COLUMNS = {
            "last_poop_tick": "REAL DEFAULT 0",
            "last_growth_tick": "REAL DEFAULT 0",
            "last_hunger_tick": "REAL DEFAULT 0",
            "last_unhappy_tick": "REAL DEFAULT 0",
        }

        for col, col_type in TIME_COLUMNS.items():
            if col not in existing_cols:
                print(f"🛠 oasistchi_pets に {col} カラムを追加します…")
                await self.conn.execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )

        # --------------------------------------------------
        # おあしすっち：通知予定時刻カラム（★再起動耐性）
        # --------------------------------------------------
        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)
        existing_cols = {row["column_name"] for row in col_check}

        NOTIFY_TIME_COLUMNS = {
            "next_poop_check_at": "REAL DEFAULT 0",
            "poop_notified_at": "REAL DEFAULT 0",
            "pet_ready_at": "REAL DEFAULT 0",
            "pet_ready_notified_at": "REAL DEFAULT 0",
        }

        for col, col_type in NOTIFY_TIME_COLUMNS.items():
            if col not in existing_cols:
                print(f"🛠 oasistchi_pets に {col} カラムを追加します…")
                await self.conn.execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )

        # -----------------------------------------
        # race_schedules テーブルに レース用
        # -----------------------------------------
        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_schedules';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "race_date" not in existing_cols:
            print("🛠 race_schedules テーブルに race_date カラムを追加します…")
            await self.conn.execute("""
                ALTER TABLE race_schedules
                ADD COLUMN race_date DATE;
            """)

            # 既存データがあれば今日の日付を入れる
            await self.conn.execute("""
                UPDATE race_schedules
                SET race_date = CURRENT_DATE
                WHERE race_date IS NULL;
            """)

            print("✅ race_date カラム追加完了")
        # --------------------------------------------------
        # おあしすっち：通知時刻の正規化（安全版）
        # --------------------------------------------------
        now = time.time()

        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)
        cols = {row["column_name"] for row in col_check}

        # 💩 うんち：次回チェック時刻が未設定の個体
        if "next_poop_check_at" in cols:
            await self.conn.execute("""
                UPDATE oasistchi_pets
                SET next_poop_check_at = $1
                WHERE next_poop_check_at = 0;
            """, now + 3600)

        # 🤚 なでなで：last_pet があるのに予定時刻が無い個体
        if "pet_ready_at" in cols:
            await self.conn.execute("""
                UPDATE oasistchi_pets
                SET pet_ready_at = last_pet + 10800
                WHERE last_pet > 0 AND pet_ready_at = 0;
            """)
        

        col_check = await self.conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)
        existing_cols = {row["column_name"] for row in col_check}

        ALERT_COLUMNS = {
            "poop_alerted": "BOOLEAN NOT NULL DEFAULT FALSE",
            "hunger_alerted": "BOOLEAN NOT NULL DEFAULT FALSE",
            "pet_ready_alerted_for": "REAL NOT NULL DEFAULT 0",
        }
        for col, col_type in ALERT_COLUMNS.items():
            if col not in existing_cols:
                print(f"🛠 oasistchi_pets に {col} カラムを追加します…")
                await self.conn.execute(f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};")
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
        await self._ensure_conn()
        async with self._lock:
            return await self.conn.fetchrow(
                "SELECT * FROM settings WHERE id = 1"
            )

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

    # ================================
    # ジャンボ：給付済み等級取得
    # ================================
    async def jumbo_get_paid_ranks(self, guild_id: str) -> list[int]:
        row = await self.conn.fetchrow(
            "SELECT paid_ranks FROM jumbo_config WHERE guild_id = $1",
            guild_id
        )
        return row["paid_ranks"] if row and row["paid_ranks"] else []


    # ================================
    # ジャンボ：給付済み等級更新
    # ================================
    async def jumbo_add_paid_rank(self, guild_id: str, rank: int):
        await self.conn.execute("""
            UPDATE jumbo_config
            SET paid_ranks = (
                SELECT ARRAY(
                    SELECT DISTINCT unnest(coalesce(paid_ranks, '{}') || $2::INTEGER)
                )
            )
            WHERE guild_id = $1
        """, guild_id, rank)

    # -------------------------------
    # おあしすっち：ユーザー
    # -------------------------------
    async def get_oasistchi_user(self, user_id: str):
        await self._ensure_conn()
        row = await self.conn.fetchrow(
            "SELECT * FROM oasistchi_users WHERE user_id=$1",
            user_id
        )
        if not row:
            await self.conn.execute(
                "INSERT INTO oasistchi_users (user_id, slots) VALUES ($1, 1)",
                user_id
            )
            row = await self.conn.fetchrow(
                "SELECT * FROM oasistchi_users WHERE user_id=$1",
                user_id
            )
        return row


    async def add_oasistchi_slot(self, user_id: str, amount: int = 1):
        await self.get_oasistchi_user(user_id)
        await self.conn.execute(
            "UPDATE oasistchi_users SET slots = slots + $2 WHERE user_id=$1",
            user_id, amount
        )

    # -------------------------------
    # おあしすっち：取得
    # -------------------------------
    async def get_oasistchi_pets(self, user_id: str):
        await self._ensure_conn()
        return await self.conn.fetch(
            "SELECT * FROM oasistchi_pets WHERE user_id=$1 ORDER BY id ASC",
            user_id
        )


    # -------------------------------
    # おあしすっち：追加（たまご購入）
    # -------------------------------
    async def add_oasistchi_egg(self, user_id: str, egg_type: str):
        now = time.time()
        await self.conn.execute("""
            INSERT INTO oasistchi_pets (
                user_id, stage, egg_type,
                growth, hunger, happiness, poop,
                last_interaction,
                last_growth_tick,
                last_poop_tick,
                next_poop_check_at
            ) VALUES (
                $1, 'egg', $2,
                0::REAL,          -- ← 明示
                100,
                50,
                FALSE,
                $3::REAL,
                $3::REAL,
                $3::REAL,
                ($3 + 3600)::REAL
            )
        """, user_id, egg_type, now)

    # -------------------------------
    # おあしすっち：更新
    # -------------------------------
    async def update_oasistchi_pet(self, pet_id: int, **fields):
        await self._ensure_conn()

        cols = []
        vals = []
        idx = 1

        for k, v in fields.items():
            cols.append(f"{k} = ${idx}")
            vals.append(v)
            idx += 1

        sql = f"""
            UPDATE oasistchi_pets
            SET {', '.join(cols)}
            WHERE id = ${idx}
        """
        vals.append(pet_id)

        await self.conn.execute(sql, *vals)

    # ----------------------------------------
    # おあしすっち：全ペット取得（poop_check用）
    # ----------------------------------------
    async def get_all_oasistchi_pets(self):
        await self._ensure_conn()
        return await self.conn.fetch(
            "SELECT * FROM oasistchi_pets"
        )

    async def get_oasistchi_pet(self, pet_id: int):
        await self._ensure_conn()
        return await self.conn.fetchrow(
            "SELECT * FROM oasistchi_pets WHERE id=$1",
            pet_id
        )

    # -------------------------------
    # おあしすっち：図鑑（取得）
    # -------------------------------
    async def get_oasistchi_owned_adult_keys(self, user_id: str) -> set[str]:
        await self._ensure_conn()
        rows = await self.conn.fetch(
            "SELECT adult_key FROM oasistchi_dex WHERE user_id=$1",
            user_id
        )
        return {r["adult_key"] for r in rows}

    # -------------------------------
    # おあしすっち：図鑑（追加）
    # -------------------------------
    async def add_oasistchi_dex(self, user_id: str, adult_key: str):
        await self._ensure_conn()
        await self.conn.execute(
            """
            INSERT INTO oasistchi_dex (user_id, adult_key)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            user_id, adult_key
        )

    # -------------------------------
    # おあしすっち：通知設定（取得）
    # -------------------------------
    async def get_oasistchi_notify_all(self, user_id: str) -> bool:
        await self._ensure_conn()
        row = await self.conn.fetchrow(
            "SELECT notify_all FROM oasistchi_notify WHERE user_id=$1",
            user_id
        )
        return row["notify_all"] if row else True

    # -------------------------------
    # おあしすっち：通知設定（更新）
    # -------------------------------
    async def set_oasistchi_notify_all(self, user_id: str, on: bool):
        await self._ensure_conn()

        if on:
            await self.conn.execute("""
                INSERT INTO oasistchi_notify (user_id, notify_poop, notify_food, notify_pet_ready)
                VALUES ($1, TRUE, TRUE, TRUE)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    notify_poop=TRUE,
                    notify_food=TRUE,
                    notify_pet_ready=TRUE
            """, user_id)
        else:
            # 設定してない状態＝通知なし
            await self.conn.execute("DELETE FROM oasistchi_notify WHERE user_id=$1", user_id)

    async def delete_oasistchi_pet(self, pet_id: int):
        await self._ensure_conn()
        await self.conn.execute(
            "DELETE FROM oasistchi_pets WHERE id=$1",
            pet_id
        )
    async def get_race_schedules(self):
        return await self.conn.fetch(
            "SELECT * FROM race_schedules ORDER BY race_time"
        )

    async def add_race_entry(self, race_date, schedule_id, user_id, pet_id):
        await self.conn.execute(
            """
            INSERT INTO race_entries (race_date, schedule_id, user_id, pet_id)
            VALUES ($1, $2, $3, $4)
            """,
            race_date, schedule_id, user_id, pet_id
        )

    async def get_race_entries(self, race_date, schedule_id):
        return await self.conn.fetch(
            """
            SELECT * FROM race_entries
            WHERE race_date = $1 AND schedule_id = $2
            ORDER BY created_at
            """,
            race_date, schedule_id
        )

    async def save_race_result(
        self, race_date, schedule_id, user_id, pet_id, position, reward
    ):
        await self.conn.execute(
            """
            INSERT INTO race_results
            (race_date, schedule_id, user_id, pet_id, position, reward)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            race_date, schedule_id, user_id, pet_id, position, reward
        )

    async def get_race_results(self, race_date, schedule_id):
        return await self.conn.fetch(
            """
            SELECT * FROM race_results
            WHERE race_date = $1 AND schedule_id = $2
            ORDER BY position
            """,
            race_date, schedule_id
        )

    async def mark_pet_race_candidate(self, pet_id: int, user_id: int):
      await self.conn.execute(
            """
            UPDATE oasistchi_pets
            SET race_candidate = TRUE
            WHERE id = $1 AND owner_id = $2
            """,
            pet_id,
            user_id
        )


    async def get_oasistchi_notify_settings(self, user_id: str) -> dict | None:
        await self._ensure_conn()
        row = await self.conn.fetchrow(
            "SELECT notify_poop, notify_food, notify_pet_ready FROM oasistchi_notify WHERE user_id=$1",
            user_id
        )
        return dict(row) if row else None

    async def get_today_race_schedules(self):
        return await self.conn.fetch("""
            SELECT *
            FROM race_schedules
            WHERE race_date = CURRENT_DATE
            ORDER BY race_no;
        """)

    async def generate_today_races(self, race_date: date):
        # 念のため同日分を削除（再生成耐性）
        await self.conn.execute("""
            DELETE FROM race_schedules
            WHERE race_date = $1;
        """, race_date)

        for i, race_time in enumerate(RACE_TIMES, start=1):
            await self.conn.execute("""
                INSERT INTO race_schedules (
                    race_no,
                    race_time,
                    distance,
                    surface,
                    condition,
                    race_date
                )
                VALUES ($1, $2, $3, $4, $5, $6);
            """,
            i,
            race_time,
            random.choice(DISTANCES),
            random.choice(SURFACES),
            random.choice(CONDITIONS),
            race_date
            )

    async def has_today_race_schedules(self, race_date: date) -> bool:
        row = await self.conn.fetchrow("""
            SELECT 1
            FROM race_schedules
            WHERE race_date = $1
            LIMIT 1
        """, race_date)

        return row is not None




















