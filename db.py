import os
import asyncpg
from dotenv import load_dotenv
import asyncio
import time
import random
from datetime import datetime, timezone, timedelta, date
import uuid
import json

JST = timezone(timedelta(hours=9))

load_dotenv()

RACE_TIMES = ["09:00", "12:00", "15:00", "18:00", "21:00"]
DISTANCES = ["短距離", "マイル", "中距離", "長距離"]
SURFACES = ["芝", "ダート"]
CONDITIONS = ["良", "稍重", "重", "不良"]
ENTRY_OPEN_MINUTES = 60  # レース開始60分前に締切


class Database:
    def __init__(self):
        self.pool = None
        self.dsn = os.getenv("DATABASE_URL")
        self._lock = asyncio.Lock()
        # バッジJSON
        self.badge_file = os.path.join(
            os.path.dirname(__file__),
            "data",
            "user_badges.json"
        )
        os.makedirs(os.path.dirname(self.badge_file), exist_ok=True)
        if not os.path.exists(self.badge_file):
            with open(self.badge_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    # ←←← ここに追加する！！！
    # =========================
    # バッジ用：内部ヘルパー
    # =========================
    def _load_badges(self) -> dict:
        with open(self.badge_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_badges(self, data: dict):
        with open(self.badge_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------
    #   DB接続
    # ------------------------------------------------------
    async def connect(self):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=1,
                max_size=10
            )

    async def _ensure_pool(self):
        if self.pool is None:
            await self.connect()


    # ------------------------------------------------------
    #   初期化（テーブル自動作成）
    # ------------------------------------------------------
    async def init_db(self):
        await self.connect()

        # Users テーブル（ギルド別通貨管理）
        await self._execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
        """)

        # 給料ロールテーブル
        await self._execute("""
            CREATE TABLE IF NOT EXISTS role_salaries (
                role_id TEXT PRIMARY KEY,
                salary INTEGER NOT NULL
            );
        """)

        # Settings テーブル（1行固定）
        await self._execute("""
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
        await self._execute("""
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
        await self._execute("""
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
        col_check = await self._fetch("""
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
                await self._execute(
                    f"ALTER TABLE settings ADD COLUMN {col} {col_type};"
                )

        # ホテル設定テーブル
        await self._execute("""
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
        await self._execute("""
            CREATE TABLE IF NOT EXISTS hotel_tickets (
                user_id TEXT,
                guild_id TEXT,
                tickets INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
        """)

        # ホテルルーム管理テーブル
        await self._execute("""
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
        await self._execute("""
            CREATE TABLE IF NOT EXISTS oasistchi_users (
                user_id TEXT PRIMARY KEY,
                slots INTEGER NOT NULL DEFAULT 1
            );
        """)

        # おあしすっち本体
        await self._execute("""
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
        # =========================
        # レース設定（ギルド別）
        # =========================
        await self._execute("""
        CREATE TABLE IF NOT EXISTS race_settings (
            guild_id TEXT PRIMARY KEY,
            result_channel_id TEXT
        );
        """)

        # ==================================================
        # おあしすっち：図鑑 / 通知（永続化）
        # ==================================================

        # 図鑑（成体履歴）
        await self._execute("""
            CREATE TABLE IF NOT EXISTS oasistchi_dex (
                user_id TEXT NOT NULL,
                adult_key TEXT NOT NULL,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, adult_key)
            );
        """)

        # 通知設定
        await self._execute("""
            CREATE TABLE IF NOT EXISTS oasistchi_notify (
                user_id TEXT PRIMARY KEY,
                notify_poop BOOLEAN NOT NULL DEFAULT TRUE,
                notify_food BOOLEAN NOT NULL DEFAULT TRUE,
                notify_pet_ready BOOLEAN NOT NULL DEFAULT TRUE
            );
        """)

        # 既存DBにカラム補完（すでにテーブルがある場合）
        col_check = await self._fetch("""
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
                await self._execute(f"ALTER TABLE oasistchi_notify ADD COLUMN {col} {col_type};")

        # -----------------------------------------
        # settings テーブルに race_result_channel_id を追加
        # -----------------------------------------
        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'settings'
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "race_result_channel_id" not in existing_cols:
            print("🛠 settings テーブルに race_result_channel_id を追加します")
            await self._execute("""
                ALTER TABLE settings
                ADD COLUMN race_result_channel_id TEXT
            """)
            print("✅ race_result_channel_id 追加完了")

        # =========================
        # レース関連テーブル
        # =========================
        await self._execute("""
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

        await self._execute("""
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

        await self._execute("""
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
        # =========================
        # 馬券関連テーブル（パリミュチュエル方式）
        # =========================

        # 個別馬券
        await self._execute("""
        CREATE TABLE IF NOT EXISTS race_bets (
            id SERIAL PRIMARY KEY,
            guild_id TEXT NOT NULL,
            race_date DATE NOT NULL,
            schedule_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            pet_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        # レースごとの総プール
        await self._execute("""
        CREATE TABLE IF NOT EXISTS race_pools (
            guild_id TEXT NOT NULL,
            race_date DATE NOT NULL,
            schedule_id INTEGER NOT NULL,
            total_pool INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, race_date, schedule_id)
        );
        """)

        # -----------------------------------------
        # race_entries に status カラムがなければ追加
        # -----------------------------------------
        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_entries';
        """)
        existing_cols = {r["column_name"] for r in col_check}

        if "status" not in existing_cols:
            print("🛠 race_entries に status カラムを追加します…")
            await self._execute("""
                ALTER TABLE race_entries
                ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
            """)
            print("✅ status カラム追加完了")

        # --------------------------------------------------
        # おあしすっち：レース用カラム補完
        # --------------------------------------------------
        col_check = await self._fetch("""
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
            await self._execute("""
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
                await self._execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )

        # settings テーブルに guild_id がなければ追加
        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'settings';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "guild_id" not in existing_cols:
            print("🛠 settings テーブルに guild_id カラムを追加します…")
            await self._execute("""
                ALTER TABLE settings
                ADD COLUMN guild_id TEXT;
            """)



        # --------------------------------------------------
        # おあしすっち：ステータス（特訓用）カラム補完
        # --------------------------------------------------
        col_check = await self._fetch("""
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
                await self._execute(
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
                await self._execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )

        # --------------------------------------------------
        # おあしすっち：時間管理用カラム補完
        # --------------------------------------------------
        col_check = await self._fetch("""
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
                await self._execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )

        # --------------------------------------------------
        # おあしすっち：通知予定時刻カラム（★再起動耐性）
        # --------------------------------------------------
        col_check = await self._fetch("""
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
                await self._execute(
                    f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};"
                )
        # -----------------------------------------
        # oasistchi_pets カラム補完
        # -----------------------------------------
        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "fixed_adult_key" not in existing_cols:
            print("🛠 oasistchi_pets に fixed_adult_key カラムを追加します…")
            await self._execute("""
                ALTER TABLE oasistchi_pets
                ADD COLUMN fixed_adult_key TEXT;
            """)
            print("✅ fixed_adult_key カラム追加完了")

        # --------------------------------------------------
        # レース関連カラム補完2.2
        # --------------------------------------------------

        # race_schedules
        cols = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_schedules';
        """)
        race_schedule_cols = {r["column_name"] for r in cols}

        if "race_finished" not in race_schedule_cols:
            print("🛠 race_schedules に race_finished を追加します…")
            await self._execute("""
                ALTER TABLE race_schedules
                ADD COLUMN race_finished BOOLEAN DEFAULT FALSE;
            """)
            print("✅ race_finished 追加完了")

        # race_entries
        cols = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_entries';
        """)
        race_entry_cols = {r["column_name"] for r in cols}

        if "rank" not in race_entry_cols:
            print("🛠 race_entries に rank を追加します…")
            await self._execute("""
                ALTER TABLE race_entries
                ADD COLUMN rank INTEGER;
            """)
            print("✅ rank 追加完了")

        if "score" not in race_entry_cols:
            print("🛠 race_entries に score を追加します…")
            await self._execute("""
                ALTER TABLE race_entries
                ADD COLUMN score REAL;
            """)
            print("✅ score 追加完了")


        

        
        # -----------------------------------------
        # race_schedules に lottery_done が無ければ追加
        # -----------------------------------------
        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_schedules';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "lottery_done" not in existing_cols:
            print("🛠 race_schedules に lottery_done カラムを追加します…")
            await self._execute("""
                ALTER TABLE race_schedules
                ADD COLUMN lottery_done BOOLEAN DEFAULT FALSE;
            """)
            print("✅ lottery_done カラム追加完了")

        await self._execute("""
            UPDATE race_schedules
            SET lottery_done = FALSE
            WHERE lottery_done IS NULL;
        """)
        # -----------------------------------------
        # race_schedules に locked が無ければ追加
        # -----------------------------------------
        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_schedules';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "locked" not in existing_cols:
            print("🛠 race_schedules に locked カラムを追加します…")
            await self._execute("""
                ALTER TABLE race_schedules
                ADD COLUMN locked BOOLEAN DEFAULT FALSE;
            """)
            print("✅ locked カラム追加完了")

        # NULL対策（念のため）
        await self._execute("""
            UPDATE race_schedules
            SET locked = FALSE
            WHERE locked IS NULL;
        """)

        # -----------------------------------------
        # race_schedules テーブルに レース用
        # -----------------------------------------
        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_schedules';
        """)

        existing_cols = {row["column_name"] for row in col_check}

        if "race_date" not in existing_cols:
            print("🛠 race_schedules テーブルに race_date カラムを追加します…")
            await self._execute("""
                ALTER TABLE race_schedules
                ADD COLUMN race_date DATE;
            """)

            # 既存データがあれば今日の日付を入れる
            await self._execute("""
                UPDATE race_schedules
                SET race_date = CURRENT_DATE
                WHERE race_date IS NULL;
            """)

            print("✅ race_date カラム追加完了")
        # --------------------------------------------------
        # おあしすっち：通知時刻の正規化（安全版）
        # --------------------------------------------------
        now = time.time()

        col_check = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'oasistchi_pets';
        """)
        cols = {row["column_name"] for row in col_check}

        # 💩 うんち：次回チェック時刻が未設定の個体
        if "next_poop_check_at" in cols:
            await self._execute("""
                UPDATE oasistchi_pets
                SET next_poop_check_at = $1
                WHERE next_poop_check_at = 0;
            """, now + 3600)

        # 🤚 なでなで：last_pet があるのに予定時刻が無い個体
        if "pet_ready_at" in cols:
            await self._execute("""
                UPDATE oasistchi_pets
                SET pet_ready_at = last_pet + 10800
                WHERE last_pet > 0 AND pet_ready_at = 0;
            """)
        

        col_check = await self._fetch("""
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
                await self._execute(f"ALTER TABLE oasistchi_pets ADD COLUMN {col} {col_type};")
        # 初期設定が無ければ作成
        exists = await self._execute("""
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
        col_check = await self._fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'hotel_settings';
        """)
        existing_cols = {row["column_name"] for row in col_check}

        if "category_ids" not in existing_cols:
            await self._execute("""
                ALTER TABLE hotel_settings ADD COLUMN category_ids TEXT[];
            """)
            await self._execute("""
                UPDATE hotel_settings SET category_ids = ARRAY[]::TEXT[] WHERE category_ids IS NULL;
            """)

        # ==================================================
        #テーブル初期化
        # ==================================================
        await self.init_jumbo_tables()
        await self.ensure_race_schedule_columns()
        await self.ensure_race_entry_columns()
        await self.ensure_race_schedule_time_text()
        await self.init_race_tables()


    # ------------------------------------------------------
    #   ユーザー残高（ギルド別管理）
    # ------------------------------------------------------
    async def get_user(self, user_id, guild_id):
        await self._ensure_pool()
        await self._execute("""
            INSERT INTO users (user_id, guild_id, balance)
            VALUES ($1, $2, 0)
            ON CONFLICT (user_id, guild_id) DO NOTHING
        """, user_id, guild_id)
        return await self._fetchrow(
            "SELECT * FROM users WHERE user_id=$1 AND guild_id=$2",
            user_id, guild_id
        )

    async def set_balance(self, user_id, guild_id, amount):
        await self._ensure_pool()
        async with self._lock:
            await self._execute(
                """
                INSERT INTO users (user_id, guild_id, balance)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET balance = $3
                """,
                user_id, guild_id, amount
            )


    async def add_balance(self, user_id, guild_id, amount):
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO users (user_id, guild_id, balance)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET balance = users.balance + $3
                RETURNING balance
            """, user_id, guild_id, amount)

    async def remove_balance(self, user_id, guild_id, amount):
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                UPDATE users
                SET balance = GREATEST(0, balance - $3)
                WHERE user_id=$1 AND guild_id=$2
                RETURNING balance
            """, user_id, guild_id, amount) or 0


    async def get_all_balances(self, guild_id):
        await self._ensure_pool()
        return await self._fetch(
            "SELECT * FROM users WHERE guild_id=$1 ORDER BY balance DESC",
            guild_id
        )

    # ------------------------------------------------------
    #   給料ロール関連
    # ------------------------------------------------------
    async def set_salary(self, role_id, salary):
        await self._execute("""
            INSERT INTO role_salaries (role_id, salary)
            VALUES ($1, $2)
            ON CONFLICT (role_id)
            DO UPDATE SET salary=$2;
        """, role_id, salary)

    async def get_salaries(self):
        return await self._fetch("SELECT * FROM role_salaries")

    # ------------------------------------------------------
    #   Settings
    # ------------------------------------------------------
    async def get_settings(self):
        await self._ensure_pool()
        return await self._fetchrow(
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
        await self._execute(sql, *values)

    # ------------------------------------------------------
    #   ホテルチケット管理
    # ------------------------------------------------------
    async def get_tickets(self, user_id, guild_id):
        row = await self._fetchrow(
            "SELECT tickets FROM hotel_tickets WHERE user_id=$1 AND guild_id=$2",
            user_id, guild_id
        )
        if not row:
            # 自動作成
            await self._execute(
                "INSERT INTO hotel_tickets (user_id, guild_id, tickets) VALUES ($1, $2, 0)",
                user_id, guild_id
            )
            return 0
        return row["tickets"]

    async def add_tickets(self, user_id, guild_id, amount):
        current = await self.get_tickets(user_id, guild_id)
        new_amount = current + amount
        await self._execute(
            "UPDATE hotel_tickets SET tickets=$1 WHERE user_id=$2 AND guild_id=$3",
            new_amount, user_id, guild_id
        )
        return new_amount

    async def remove_tickets(self, user_id, guild_id, amount):
        current = await self.get_tickets(user_id, guild_id)
        new_amount = max(0, current - amount)
        await self._execute(
            "UPDATE hotel_tickets SET tickets=$1 WHERE user_id=$2 AND guild_id=$3",
            new_amount, user_id, guild_id
        )
        return new_amount

    # ------------------------------------------------------
    #   ホテルルーム管理
    # ------------------------------------------------------
    async def save_room(self, channel_id, guild_id, owner_id, expire_at):
        await self._execute("""
            INSERT INTO hotel_rooms (channel_id, guild_id, owner_id, expire_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (channel_id)
            DO UPDATE SET expire_at=$4;
        """, channel_id, guild_id, owner_id, expire_at)

    async def delete_room(self, channel_id):
        await self._execute(
            "DELETE FROM hotel_rooms WHERE channel_id=$1",
            channel_id
        )

    async def get_room(self, channel_id):
        return await self._fetchrow(
            "SELECT * FROM hotel_rooms WHERE channel_id=$1",
            channel_id
        )
    # ------------------------------------------------------
    #   バックアップ用スナップショット
    #   users（残高）と hotel_tickets（チケット）をまとめてJSON化
    # ------------------------------------------------------
    async def export_user_snapshot(self) -> dict:
        """全ユーザーの残高・チケットをまとめて取得してJSON用dictで返す"""

        users_rows = await self._fetch(
            "SELECT user_id, guild_id, balance FROM users"
        )
        tickets_rows = await self._fetch(
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
            await self._execute("TRUNCATE TABLE users")
            await self._execute("TRUNCATE TABLE hotel_tickets")

        # users の復元
        for row in snapshot.get("users", []):
            user_id = str(row["user_id"])
            guild_id = str(row["guild_id"])
            balance = int(row["balance"])

            exists = await self._fetchrow(
                "SELECT 1 FROM users WHERE user_id=$1 AND guild_id=$2",
                user_id, guild_id,
            )
            if exists:
                await self._execute(
                    "UPDATE users SET balance=$1 WHERE user_id=$2 AND guild_id=$3",
                    balance, user_id, guild_id,
                )
            else:
                await self._execute(
                    "INSERT INTO users (user_id, guild_id, balance) VALUES ($1, $2, $3)",
                    user_id, guild_id, balance,
                )

        # hotel_tickets の復元
        for row in snapshot.get("tickets", []):
            user_id = str(row["user_id"])
            guild_id = str(row["guild_id"])
            tickets = int(row["tickets"])

            exists = await self._fetchrow(
                "SELECT 1 FROM hotel_tickets WHERE user_id=$1 AND guild_id=$2",
                user_id, guild_id,
            )
            if exists:
                await self._execute(
                    "UPDATE hotel_tickets SET tickets=$1 WHERE user_id=$2 AND guild_id=$3",
                    tickets, user_id, guild_id,
                )
            else:
                await self._execute(
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
        await self._ensure_pool()

        # 開催設定
        await self._execute("""
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
        await self._execute("""
            CREATE TABLE IF NOT EXISTS jumbo_entries (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                number VARCHAR(6) NOT NULL,
                PRIMARY KEY (guild_id, number)
            );
        """)

        # 当選者
        await self._execute("""
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
        await self._ensure_pool()
        await self._execute("""
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
        await self._ensure_pool()
        return await self._fetchrow(
            "SELECT * FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )

    async def jumbo_close_config(self, guild_id):
        await self._ensure_pool()
        await self._execute("""
            UPDATE jumbo_config SET is_open=FALSE WHERE guild_id=$1
        """, guild_id)

    async def jumbo_reset_config(self, guild_id):
        await self._ensure_pool()
        await self._execute(
            "DELETE FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )

    async def jumbo_set_panel_message(self, guild_id, channel_id, message_id):
        await self._ensure_pool()
        await self._execute("""
            UPDATE jumbo_config
            SET panel_channel_id=$2,
                panel_message_id=$3
            WHERE guild_id=$1
        """, guild_id, channel_id, message_id)

    # --------------------------------------------------
    #   購入番号
    # --------------------------------------------------
    async def jumbo_add_number(self, guild_id, user_id, number):
        await self._ensure_pool()
        try:
            await self._execute("""
                INSERT INTO jumbo_entries (guild_id, user_id, number)
                VALUES ($1, $2, $3)
            """, guild_id, user_id, number)
            return True
        except asyncpg.exceptions.UniqueViolationError:
            return False

    async def jumbo_get_user_numbers(self, guild_id, user_id):
        await self._ensure_pool()
        return await self._fetch("""
            SELECT number FROM jumbo_entries
            WHERE guild_id=$1 AND user_id=$2
            ORDER BY number ASC
        """, guild_id, user_id)

    async def jumbo_get_all_entries(self, guild_id):
        await self._ensure_pool()
        return await self._fetch("""
            SELECT guild_id, user_id, number
            FROM jumbo_entries
            WHERE guild_id=$1
        """, guild_id)

    async def jumbo_clear_entries(self, guild_id):
        await self._ensure_pool()
        await self._execute(
            "DELETE FROM jumbo_entries WHERE guild_id=$1",
            guild_id
        )

    async def jumbo_count_entries(self, guild_id):
        await self._ensure_pool()
        row = await self._fetchrow(
            "SELECT COUNT(*) AS cnt FROM jumbo_entries WHERE guild_id=$1",
            guild_id
        )
        return row["cnt"] if row else 0

    # --------------------------------------------------
    #   当選番号・当選者
    # --------------------------------------------------
    async def jumbo_set_winning_number(self, guild_id, winning_number):
        await self._ensure_pool()
        result = await self._execute("""
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
        await self._ensure_pool()
        await self._execute("""
            INSERT INTO jumbo_winners
                (guild_id, rank, number, user_id, match_count, prize)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
        """, guild_id, rank, number, user_id, match_count, prize)

    async def jumbo_get_winners(self, guild_id):
        await self._ensure_pool()
        return await self._fetch("""
            SELECT * FROM jumbo_winners
            WHERE guild_id=$1
            ORDER BY rank ASC, number ASC
        """, guild_id)

    async def jumbo_clear_winners(self, guild_id):
        await self._ensure_pool()
        await self._execute(
            "DELETE FROM jumbo_winners WHERE guild_id=$1",
            guild_id
        )
    # --------------------------------------------------
    #   ジャンボ購入枚数
    # --------------------------------------------------
    async def jumbo_count_user_entries(self, guild_id, user_id):
        await self._ensure_pool()
        row = await self._fetchrow("""
            SELECT COUNT(*) AS cnt
            FROM jumbo_entries
            WHERE guild_id=$1 AND user_id=$2
        """, guild_id, user_id)
        return row["cnt"] if row else 0
    # ------------------------------------------------------
    #   ジャンボ：ユーザーの所持口数
    # ------------------------------------------------------
    async def jumbo_get_user_count(self, guild_id: str, user_id: str) -> int:
        await self._ensure_pool()
        row = await self._fetchrow(
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
        row = await self._fetchrow(
            "SELECT paid_ranks FROM jumbo_config WHERE guild_id = $1",
            guild_id
        )
        return row["paid_ranks"] if row and row["paid_ranks"] else []


    # ================================
    # ジャンボ：給付済み等級更新
    # ================================
    async def jumbo_add_paid_rank(self, guild_id: str, rank: int):
        await self._execute("""
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
        await self._ensure_pool()
        row = await self._fetchrow(
            "SELECT * FROM oasistchi_users WHERE user_id=$1",
            user_id
        )
        if not row:
            await self._execute(
                "INSERT INTO oasistchi_users (user_id, slots) VALUES ($1, 1)",
                user_id
            )
            row = await self._fetchrow(
                "SELECT * FROM oasistchi_users WHERE user_id=$1",
                user_id
            )
        return row


    async def add_oasistchi_slot(self, user_id: str, amount: int = 1):
        await self.get_oasistchi_user(user_id)
        await self._execute(
            "UPDATE oasistchi_users SET slots = slots + $2 WHERE user_id=$1",
            user_id, amount
        )

    # -------------------------------
    # おあしすっち：取得
    # -------------------------------
    async def get_oasistchi_pets(self, user_id: str):
        await self._ensure_pool()
        return await self._fetch(
            "SELECT * FROM oasistchi_pets WHERE user_id=$1 ORDER BY id ASC",
            user_id
        )


    # -------------------------------
    # おあしすっち：追加（たまご購入）
    # -------------------------------
    async def add_oasistchi_egg(
        self,
        user_id: str,
        egg_type: str,
        *,
        fixed_adult_key: str | None = None
    ):
        now = time.time()
        await self._execute("""
            INSERT INTO oasistchi_pets (
                user_id,
                stage,
                egg_type,
                fixed_adult_key,
                growth,
                hunger,
                happiness,
                poop,
                last_interaction,
                last_growth_tick,
                last_poop_tick,
                next_poop_check_at
            ) VALUES (
                $1,
                'egg',
                $2,
                $3,
                0::REAL,
                100,
                50,
                FALSE,
                $4::REAL,
                $4::REAL,
                $4::REAL,
                ($4 + 3600)::REAL
            )
        """,
        user_id,
        egg_type,
        fixed_adult_key,
        now)

    # ==================================================
    # おあしすっち：たまご購入（完全安全版）
    # ==================================================
    async def purchase_oasistchi_egg_safe(
        self,
        user_id: str,
        guild_id: str,
        egg_type: str,
        price: int,
        *,
        fixed_adult_key: str | None = None
    ):
        await self._ensure_pool()

        async with self._lock:
            async with self.pool.acquire() as conn:
                async with conn.transaction():

                    # ① 残高取得（ロック）
                    row = await conn.fetchrow(
                        """
                        SELECT balance
                        FROM users
                        WHERE user_id=$1 AND guild_id=$2
                        FOR UPDATE
                        """,
                        user_id,
                        guild_id
                    )

                    if not row:
                        raise RuntimeError("ユーザーが存在しません")

                    if row["balance"] < price:
                        raise RuntimeError("残高不足")

                    # ② 残高減算
                    await conn.execute(
                        """
                        UPDATE users
                        SET balance = balance - $1
                        WHERE user_id=$2 AND guild_id=$3
                        """,
                        price, user_id, guild_id
                    )

                    # ③ たまご追加
                    now = time.time()
                    await conn.execute(
                        """
                        INSERT INTO oasistchi_pets (
                            user_id,
                            stage,
                            egg_type,
                            fixed_adult_key,
                            growth,
                            hunger,
                            happiness,
                            poop,
                            last_interaction,
                            last_growth_tick,
                            last_poop_tick,
                            next_poop_check_at
                        ) VALUES (
                            $1,
                            'egg',
                            $2,
                            $3,
                            0,
                            100,
                            50,
                            FALSE,
                            $4::REAL,
                            $4::REAL,
                            $4::REAL,
                            ($4::REAL + 3600)
                        )
                        """,
                        user_id,
                        egg_type,
                        fixed_adult_key,
                        now
                    )

    # ==================================================
    # おあしすっち：かぶりなし たまご（完全安全）
    # ==================================================
    async def purchase_unique_egg_safe(
        self,
        user_id: str,
        guild_id: str,
        price: int,
        adult_catalog: list[dict]
    ):
        """
        ・残高チェック
        ・残高減算
        ・未所持 adult 抽選
        ・卵追加
        を1トランザクションで行う
        """
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            async with conn.transaction():

                # -------------------------
                # 残高ロック
                # -------------------------
                row = await conn.fetchrow(
                    """
                    SELECT balance
                    FROM users
                    WHERE user_id=$1 AND guild_id=$2
                    FOR UPDATE
                    """,
                    user_id, guild_id
                )

                if not row or row["balance"] < price:
                    raise RuntimeError("残高が足りません")

                # -------------------------
                # 所持済み成体取得（ロック不要）
                # -------------------------
                owned_rows = await conn.fetch(
                "SELECT adult_key FROM oasistchi_dex WHERE user_id=$1",
                    user_id
                )
                owned = {r["adult_key"] for r in owned_rows}

                candidates = [
                    a for a in adult_catalog
                    if a["key"] not in owned
                ]

                if not candidates:
                    raise RuntimeError("すべてのおあしすっちを所持済みです")

                adult = random.choice(candidates)
                egg_type = random.choice(adult["groups"])
                now = time.time()

                # -------------------------
                # 残高減算
                # -------------------------
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $1
                    WHERE user_id=$2 AND guild_id=$3
                    """,
                    price, user_id, guild_id
                )

                # -------------------------
                # 卵追加（固定成体）
                # -------------------------
                await conn.execute(
                    """
                    INSERT INTO oasistchi_pets (
                        user_id, stage, egg_type, fixed_adult_key,
                        growth, hunger, happiness, poop,
                        last_interaction,
                        last_growth_tick,
                        last_poop_tick,
                        next_poop_check_at
                    ) VALUES (
                        $1, 'egg', $2, $3,
                        0::REAL,
                        100,
                        50,
                        FALSE,
                        $4::REAL,
                        $4::REAL,
                        $4::REAL,
                        ($4 + 3600)::REAL
                    )
                    """,
                    user_id,
                    egg_type,
                    adult["key"],
                    now
                )

                return adult, egg_type



    # ==================================================
    # おあしすっち：育成枠購入（完全安全）
    # ==================================================
    async def purchase_oasistchi_slot_safe(
        self,
        user_id: str,
        guild_id: str,
        base_price: int,
        max_slots: int = 10
    ) -> int:
        """
        ・残高チェック
        ・現在の育成枠チェック
        ・価格計算（5枠以上で2倍）
        ・残高減算
        ・育成枠 +1
        を1トランザクションで行う

        return: 購入後の slots 数
        """
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            async with conn.transaction():

                # -------------------------
                # 残高ロック
                # -------------------------
                bal = await conn.fetchrow(
                    """
                    SELECT balance
                    FROM users
                    WHERE user_id=$1 AND guild_id=$2
                    FOR UPDATE
                    """,
                    user_id, guild_id
                )

                if not bal:
                    raise RuntimeError("残高情報が見つかりません")

                # -------------------------
                # 育成枠ロック
                # -------------------------
                row = await conn.fetchrow(
                    """
                    SELECT slots
                    FROM oasistchi_users
                    WHERE user_id=$1
                    FOR UPDATE
                    """,
                    user_id
                )

                # 初回ユーザー対策
                if not row:
                    await conn.execute(
                        "INSERT INTO oasistchi_users (user_id, slots) VALUES ($1, 1)",
                        user_id
                    )
                    slots = 1
                else:
                    slots = row["slots"]

                if slots >= max_slots:
                    raise RuntimeError("育成枠は最大まで拡張されています")

                # -------------------------
                # 価格計算
                # -------------------------
                price = base_price * 2 if slots >= 5 else base_price

                if bal["balance"] < price:
                    raise RuntimeError("残高が足りません")

                # -------------------------
                # 残高減算
                # -------------------------
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $1
                    WHERE user_id=$2 AND guild_id=$3
                    """,
                    price, user_id, guild_id
                )

                # -------------------------
                # 育成枠 +1
                # -------------------------
                await conn.execute(
                    """
                    UPDATE oasistchi_users
                    SET slots = slots + 1
                    WHERE user_id=$1
                    """,
                    user_id
                )

                return slots + 1



    # -------------------------------
    # おあしすっち：更新
    # -------------------------------
    async def update_oasistchi_pet(self, pet_id: int, **fields):
        await self._ensure_pool()
        async with self._lock:

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

            await self._execute(sql, *vals)

    # ----------------------------------------
    # おあしすっち：全ペット取得（poop_check用）
    # ----------------------------------------
    async def get_all_oasistchi_pets(self):
        await self._ensure_pool()
        return await self._fetch(
            "SELECT * FROM oasistchi_pets"
        )

    async def get_oasistchi_pet(self, pet_id: int):
        await self._ensure_pool()
        async with self._lock:
            return await self._fetchrow(
                "SELECT * FROM oasistchi_pets WHERE id=$1",
                pet_id
            )

    # -------------------------------
    # おあしすっち：図鑑（取得）
    # -------------------------------
    async def get_oasistchi_owned_adult_keys(self, user_id: str) -> set[str]:
        await self._ensure_pool()
        async with self._lock:
            rows = await self._fetch(
                "SELECT adult_key FROM oasistchi_dex WHERE user_id=$1",
                user_id
            )
            return {r["adult_key"] for r in rows}

    # -------------------------------
    # おあしすっち：図鑑（追加）
    # -------------------------------
    async def add_oasistchi_dex(self, user_id: str, adult_key: str):
        await self._ensure_pool()
        async with self._lock:
            await self._execute(
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
        await self._ensure_pool()
        row = await self._fetchrow("SELECT 1 FROM oasistchi_notify WHERE user_id=$1", user_id)
        return row is not None

    # -------------------------------
    # おあしすっち：通知設定（更新）
    # -------------------------------
    async def set_oasistchi_notify_all(self, user_id: str, on: bool):
        await self._ensure_pool()

        if on:
            await self._execute("""
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
            await self._execute("DELETE FROM oasistchi_notify WHERE user_id=$1", user_id)

    async def delete_oasistchi_pet(self, pet_id: int):
        await self._ensure_pool()
        async with self._lock:
            await self._execute(
                "DELETE FROM oasistchi_pets WHERE id=$1",
                pet_id
            )
    async def get_race_schedules(self, guild_id: str):
        return await self._fetch(
            """
            SELECT *
            FROM race_schedules
            WHERE guild_id = $1
            ORDER BY race_time
            """,
            str(guild_id)
        )


    async def get_race_entries_by_schedule(self, race_date, schedule_id, guild_id: str):
        await self._ensure_pool()
        return await self._fetch("""
            SELECT * FROM race_entries
            WHERE race_date = $1
              AND schedule_id = $2
              AND guild_id = $3
            ORDER BY created_at
        """, race_date, schedule_id, str(guild_id))

    async def save_race_result(
        self, race_date, schedule_id, user_id, pet_id, position, reward
    ):
        await self._execute(
            """
            INSERT INTO race_results
            (race_date, schedule_id, user_id, pet_id, position, reward)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            race_date, schedule_id, user_id, pet_id, position, reward
        )

    async def get_race_results(self, race_date, schedule_id):
        return await self._fetch(
            """
            SELECT * FROM race_results
            WHERE race_date = $1 AND schedule_id = $2
            ORDER BY position
            """,
            race_date, schedule_id
        )

    async def mark_pet_race_candidate(self, pet_id: int, user_id: int):
      await self._execute(
            """
            UPDATE oasistchi_pets
            SET race_candidate = TRUE
            WHERE id = $1 AND user_id = $2
            """,
            pet_id,
            user_id
        )


    async def get_oasistchi_notify_settings(self, user_id: str) -> dict | None:
        await self._ensure_pool()
        row = await self._fetchrow(
            "SELECT notify_poop, notify_food, notify_pet_ready FROM oasistchi_notify WHERE user_id=$1",
            user_id
        )
        return dict(row) if row else None

    async def get_today_race_schedules(self, race_date: date, guild_id: str):
        return await self._fetch("""
            SELECT *
            FROM race_schedules
            WHERE race_date = $1
              AND guild_id = $2
            ORDER BY race_time
        """, race_date, guild_id)

    async def generate_today_races(self, guild_id: str, race_date: date):
        cols = await self._fetch("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'race_schedules'
            ORDER BY ordinal_position;
        """)
        print("[RACE DEBUG] race_schedules columns:")
        for c in cols:
            print(f"  {c['column_name']} | nullable={c['is_nullable']}")
        # 念のため同日分を削除（再生成耐性）
        await self._execute("""
            DELETE FROM race_schedules
            WHERE race_date = $1
              AND guild_id = $2;
        """, race_date, str(guild_id))

        for i, race_time in enumerate(RACE_TIMES, start=1):
            await self._execute("""
                INSERT INTO race_schedules (
                    guild_id,
                    race_no,
                    race_time,
                    entry_open_minutes,
                    max_entries,
                    entry_fee,
                    created_at,
                    race_date,
                    distance,
                    surface,
                    condition
                )
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8, $9, $10);
            """,
            str(guild_id),          # ← ★ これが必須
            i,                      # race_no
            race_time,
            ENTRY_OPEN_MINUTES,
            8,
            50000,
            race_date,
            random.choice(DISTANCES),
            random.choice(SURFACES),
            random.choice(CONDITIONS),
            )

    async def has_today_race_schedules(self, race_date: date, guild_id: str) -> bool:
        return await self._fetchval("""
            SELECT EXISTS(
                SELECT 1
                FROM race_schedules
                WHERE race_date = $1
                  AND guild_id = $2
            )
        """, race_date, guild_id)

    # -----------------------------------------
    # race_schedules テーブル カラム補完
    # -----------------------------------------
    async def ensure_race_schedule_columns(self):
        cols = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_schedules';
        """)
        existing = {c["column_name"] for c in cols}

        alter_sqls = []

        if "guild_id" not in existing:
            alter_sqls.append("ADD COLUMN guild_id TEXT")

        if "race_date" not in existing:
            alter_sqls.append("ADD COLUMN race_date DATE")

        if "distance" not in existing:
            alter_sqls.append("ADD COLUMN distance TEXT")

        if "surface" not in existing:
            alter_sqls.append("ADD COLUMN surface TEXT")

        if "condition" not in existing:
            alter_sqls.append("ADD COLUMN condition TEXT")

        if alter_sqls:
            sql = "ALTER TABLE race_schedules " + ", ".join(alter_sqls) + ";"
            print("🛠 race_schedules カラム補完:", sql)
            await self._execute(sql)

    # -----------------------------------------
    # race_entries テーブル カラム補完
    # -----------------------------------------
    async def ensure_race_entry_columns(self):
        cols = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'race_entries';
        """)
        existing = {c["column_name"] for c in cols}

        alter_sqls = []

        if "guild_id" not in existing:
            alter_sqls.append("ADD COLUMN guild_id TEXT")

        if "entry_fee" not in existing:
            alter_sqls.append("ADD COLUMN entry_fee INTEGER DEFAULT 50000")

        if alter_sqls:
            sql = "ALTER TABLE race_entries " + ", ".join(alter_sqls) + ";"
            print("🛠 race_entries カラム補完:", sql)
            await self._execute(sql)
            
    # -----------------------------------------
    # 型修正用の補完
    # -----------------------------------------
    async def ensure_race_schedule_time_text(self):
        col = await self._fetchrow("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'race_schedules'
              AND column_name = 'race_time';
        """)

        if col and col["data_type"] != "text":
            print("🛠 race_schedules.race_time を TEXT に変更します")
            await self._execute("""
                ALTER TABLE race_schedules
                ALTER COLUMN race_time TYPE TEXT
                USING race_time::text;
            """)
    # -----------------------------------------
    # レース関係関数
    # -----------------------------------------
    async def get_race_entries_pending(self, guild_id: str, race_date, schedule_id: int):
        await self._ensure_pool()
        return await self._fetch("""
            SELECT *
            FROM race_entries
            WHERE guild_id = $1
              AND race_date = $2
              AND schedule_id = $3
              AND status = 'pending'
            ORDER BY created_at
        """, str(guild_id), race_date, schedule_id)
    # -----------------------------------------
    # 参加済みを取得
    # -----------------------------------------

    async def get_today_selected_pet_ids(self, race_date: date):
        rows = await self._fetch("""
            SELECT pet_id FROM race_entries
            WHERE race_date = $1
              AND status = 'selected'
        """, race_date)
        return {r["pet_id"] for r in rows}

    # -----------------------------------------
    # ステータス更新
    # -----------------------------------------

    async def update_race_entry_status(self, entry_id: int, status: str):
        await self._execute("""
            UPDATE race_entries
            SET status = $2
            WHERE id = $1
        """, entry_id, status)

    # -----------------------------------------
    # 返金
    # -----------------------------------------
    async def refund_entry(self, user_id: str, guild_id: str, amount: int):
        await self.add_balance(user_id, guild_id, amount)
    # -----------------------------------------
    # 同日・他レースエントリー無効化
    # -----------------------------------------

    async def cancel_other_entries(
        self,
        pet_id: int,
        race_date: date,
        exclude_schedule_id: int
    ):
        await self._execute("""
            UPDATE race_entries
            SET status = 'cancelled'
            WHERE pet_id = $1
              AND race_date = $2
              AND schedule_id != $3
              AND status = 'pending'
        """, pet_id, race_date, exclude_schedule_id)

    # =====================================================
    # レース：同一ユーザーの重複エントリーチェック
    # =====================================================
    async def has_user_entry_for_race(self, schedule_id: int, user_id: str) -> bool:
        row = await self._fetchrow("""
            SELECT 1
            FROM race_entries
            WHERE schedule_id = $1
              AND user_id = $2
            LIMIT 1;
        """, schedule_id, user_id)

        return row is not None
    # =====================================================
    # おあしすっち出走済みかチェック
    # =====================================================
    async def has_pet_selected_today(self, pet_id: int, race_date: date) -> bool:
        row = await self._fetchrow("""
            SELECT 1
            FROM race_entries
            WHERE pet_id = $1
              AND race_date = $2
              AND status = 'selected'
            LIMIT 1;
        """, pet_id, race_date)
        return row is not None
        
    # =====================================================
    # 同一ユーザーが同日出走したかチェック
    # =====================================================

    async def has_user_selected_today(self, user_id: str, race_date: date) -> bool:
        row = await self._fetchrow("""
            SELECT 1
            FROM race_entries
            WHERE user_id = $1
              AND race_date = $2
              AND status = 'selected'
            LIMIT 1;
        """, user_id, race_date)
        return row is not None

    # =====================================================
    # エントリー追加（確定時）
    # =====================================================

    async def insert_race_entry(
        self,
        schedule_id: int,
        guild_id: str,
        user_id: str,
        pet_id: int,
        race_date,          # date 型
        entry_fee: int,
        paid: bool,
    ):
        await self._execute("""
            INSERT INTO race_entries (
                race_date,
                schedule_id,
                guild_id,
                user_id,
                pet_id,
                entry_fee,
                paid,
                status,
                created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', NOW());
        """,
        race_date,
        schedule_id,
        guild_id,
        user_id,
        pet_id,
        entry_fee,
        paid
        )
    # =====================================================
    # 返金対象をまとめて取得
    # =====================================================

    async def get_refund_entries(self, schedule_id: int):
        return await self._fetch("""
            SELECT user_id, guild_id, entry_fee
            FROM race_entries
            WHERE schedule_id = $1
              AND status = 'cancelled'
        """, schedule_id)



    # =====================================================
    # 抽選済みフラグ
    # =====================================================
    async def mark_race_lottery_done(self, race_id: int):
        await self._execute("""
            UPDATE race_schedules
            SET lottery_done = TRUE,
                locked = TRUE
            WHERE id = $1
        """, race_id)


    # =====================================================
    # かぶりなしたまご
    # =====================================================

    async def _ensure_column(self, table: str, column: str, coldef: str):
        rows = await self._fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = $1;
        """, table)

        existing = {r["column_name"] for r in rows}
        if column not in existing:
            print(f"🛠 {table} テーブルに {column} カラムを追加します…")
            await self._execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef};")
            print(f"✅ {column} カラム追加完了")


    # -------------------------------
    # おあしすっち：転生
    # -------------------------------
    async def rebirth_oasistchi(self, pet_id: int):
        base_speed = random.randint(30, 50)
        base_stamina = random.randint(30, 50)
        base_power = random.randint(30, 50)

        await self._execute("""
            UPDATE oasistchi_pets
            SET
                base_speed = $1,
                base_stamina = $2,
                base_power = $3,
                train_speed = 0,
                train_stamina = 0,
                train_power = 0,
                training_count = 0
            WHERE id = $4
              AND stage = 'adult'
        """,
        base_speed,
        base_stamina,
        base_power,
        pet_id)

    # -------------------------------
    # おあしすっち：特訓リセット
    # -------------------------------
    async def reset_training_oasistchi(self, pet_id: int):
        await self._execute("""
            UPDATE oasistchi_pets
            SET
                train_speed = 0,
                train_stamina = 0,
                train_power = 0,
                training_count = 0
            WHERE id = $1
              AND stage = 'adult'
        """, pet_id)


    # --------------------------------------------------
    # 出走確定エントリー取得
    # --------------------------------------------------
    async def get_selected_entries(self, schedule_id: int):
        return await self._fetch("""
            SELECT *
            FROM race_entries
            WHERE schedule_id = $1
              AND status = 'selected'
        """, schedule_id)

    # --------------------------------------------------
    # レース結果保存
    # --------------------------------------------------
    async def update_race_entry_result(
        self,
        schedule_id: int,
        pet_id: int,
        rank: int,
        score: float
    ):
        await self._execute("""
            UPDATE race_entries
            SET rank = $1,
                score = $2
            WHERE schedule_id = $3
              AND pet_id = $4
        """, rank, score, schedule_id, pet_id)

    # --------------------------------------------------
    # レース完了
    # --------------------------------------------------
    async def mark_race_finished(self, race_id: int):
        await self._ensure_pool()
        await self._execute("""
            UPDATE race_schedules
            SET race_finished = TRUE
            WHERE id = $1
        """, race_id)

    # --------------------------------------------------
    # 未完了レース取得（日付）
    # --------------------------------------------------
    async def get_unfinished_races_by_date(self, race_date: date, guild_id: str):
        await self._ensure_pool()
        return await self._fetch("""
            SELECT *
            FROM race_schedules
            WHERE race_date = $1
              AND guild_id = $2
              AND race_finished = FALSE
            ORDER BY race_time
        """, race_date, str(guild_id))

    # --------------------------------------------------
    # 未完了レース存在チェック
    # --------------------------------------------------
    async def has_unfinished_race(self, race_id: int) -> bool:
        await self._ensure_pool()
        row = await self._fetchrow("""
            SELECT 1
            FROM race_schedules
            WHERE id = $1
              AND race_finished = FALSE
        """, race_id)
        return row is not None

    async def get_race_entries_by_status(self, race_id: int, status: str):
        await self._ensure_pool()
        return await self._fetch("""
            SELECT *
            FROM race_entries
            WHERE schedule_id = $1
              AND status = $2
        """, race_id, status)


    # ======================================================
    #   レースWeb機能（おあしすっち）※衝突回避版
    # ======================================================
    async def init_race_tables(self):
        await self._ensure_pool()

        # ★ race_schedules / race_entries（抽選用）と衝突するので別名にする
        await self._execute("""
            CREATE TABLE IF NOT EXISTS web_races (
                race_id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL,
                race_time TIMESTAMP NOT NULL,
                status TEXT NOT NULL,
                result_channel_id TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        await self._execute("""
            CREATE TABLE IF NOT EXISTS web_race_entries (
                race_id TEXT NOT NULL,
                pet_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                pet_key TEXT NOT NULL,
                condition TEXT NOT NULL,
                speed INTEGER NOT NULL,
                power INTEGER NOT NULL,
                stamina INTEGER NOT NULL,
                odds REAL NOT NULL,
                PRIMARY KEY (race_id, pet_id)
            );
        """)

        await self._execute("""
            CREATE TABLE IF NOT EXISTS web_race_bets (
                race_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                pet_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
    # --------------------------------------------------
    # API用：出走馬（selected）を oasistchi_pets とJOINして返す
    # speed/power/stamina は「base + train」を優先して0を回避
    # --------------------------------------------------
    async def get_selected_pets_for_api(self, guild_id: str, race_date: date, schedule_id: int):
        await self._ensure_pool()

        rows = await self._fetch("""
            SELECT
                e.pet_id,
                p.name,
                p.adult_key,

                -- まず speed/stamina/power が入っていればそれを使う
                -- 0なら base + train を採用（実運用で0が返ってくるのを潰す）
                CASE
                    WHEN COALESCE(p.speed, 0) > 0 THEN p.speed
                    ELSE COALESCE(p.base_speed, 0) + COALESCE(p.train_speed, 0)
                END AS speed,

                CASE
                    WHEN COALESCE(p.power, 0) > 0 THEN p.power
                    ELSE COALESCE(p.base_power, 0) + COALESCE(p.train_power, 0)
                END AS power,

                CASE
                    WHEN COALESCE(p.stamina, 0) > 0 THEN p.stamina
                    ELSE COALESCE(p.base_stamina, 0) + COALESCE(p.train_stamina, 0)
                END AS stamina

            FROM race_entries e
            JOIN oasistchi_pets p
              ON p.id = e.pet_id
            WHERE e.guild_id   = $1
              AND e.race_date  = $2
              AND e.schedule_id = $3
              AND e.status = 'selected'
            ORDER BY e.created_at ASC
        """, str(guild_id), race_date, schedule_id)

        # dict化
        return [
            {
                "pet_id": int(r["pet_id"]),
                "name": r["name"] or "NoName",
                "adult_key": r["adult_key"] or "unknown",
                "speed": int(r["speed"] or 0),
                "power": int(r["power"] or 0),
                "stamina": int(r["stamina"] or 0),
            }
            for r in rows
        ]
    
    # ======================================================
    #   レース機能（おあしすっち）
    # ======================================================
    async def run_race_lottery(
        self,
        guild_id: str,
        race_date: date,
        schedule_id: int
    ):
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            async with conn.transaction():

                # 二重実行防止
                race = await conn.fetchrow("""
                    SELECT lottery_done
                    FROM race_schedules
                    WHERE id = $1
                    FOR UPDATE
                """, schedule_id)

                if not race or race["lottery_done"]:
                    return {"selected": [], "cancelled": []}

                # pending取得（同じconn）
                entries = await conn.fetch("""
                    SELECT *
                    FROM race_entries
                    WHERE guild_id = $1
                      AND race_date = $2
                      AND schedule_id = $3
                      AND status = 'pending'
                    ORDER BY created_at
                """, str(guild_id), race_date, schedule_id)

                if len(entries) < 2:
                    return {"selected": [], "cancelled": []}

                max_entries = min(8, len(entries))
                selected = random.sample(entries, max_entries)
                selected_ids = {e["id"] for e in selected}
                cancelled = []

                for e in entries:
                    if e["id"] in selected_ids:
                        await conn.execute("""
                            UPDATE race_entries
                            SET status = 'selected'
                            WHERE id = $1
                        """, e["id"])
                    else:
                        await conn.execute("""
                            UPDATE race_entries
                            SET status = 'cancelled'
                            WHERE id = $1
                        """, e["id"])
                        cancelled.append(e)

                await conn.execute("""
                    UPDATE race_schedules
                    SET lottery_done = TRUE,
                        locked = TRUE
                    WHERE id = $1
                """, schedule_id)

                return {
                    "selected": selected,
                    "cancelled": cancelled
                }

    # =========================
    # レース設定取得
    # =========================
    async def get_race_settings(self, guild_id: str):
        await self._ensure_pool()
        return await self._fetchrow(
            "SELECT * FROM race_settings WHERE guild_id=$1",
            str(guild_id)
        )

    # =========================
    # レース結果チャンネル設定
    # =========================
    async def set_race_result_channel(self, guild_id: str, channel_id: str):
        await self._ensure_pool()
        await self._execute("""
            INSERT INTO race_settings (guild_id, result_channel_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET result_channel_id=$2
        """, str(guild_id), str(channel_id))



    async def get_user_badges(self, user_id: str, guild_id: str | None = None) -> list[str]:
        async with self._lock:
            data = self._load_badges()

            if guild_id:
                return data.get(guild_id, {}).get(user_id, [])
            else:
                # guild未指定なら全guild分まとめる（保険）
                badges = []
                for g in data.values():
                    badges.extend(g.get(user_id, []))
                return list(set(badges))


    async def add_user_badge(self, user_id: str, guild_id: str, badge: str):
        async with self._lock:
            data = self._load_badges()

            guild = data.setdefault(guild_id, {})
            badges = guild.setdefault(user_id, [])

            if badge not in badges:
                badges.append(badge)

            self._save_badges(data)

    async def remove_user_badge(self, user_id: str, guild_id: str, badge: str):
        async with self._lock:
            data = self._load_badges()

            if guild_id in data and user_id in data[guild_id]:
                if badge in data[guild_id][user_id]:
                    data[guild_id][user_id].remove(badge)

            self._save_badges(data)

    async def _fetch(self, query, *args, conn=None):
        await self._ensure_pool()
        if conn:
            return await conn.fetch(query, *args)
        async with self.pool.acquire() as c:
            return await c.fetch(query, *args)

    async def _fetchrow(self, query, *args, conn=None):
        await self._ensure_pool()
        if conn:
            return await conn.fetchrow(query, *args)
        async with self.pool.acquire() as c:
            return await c.fetchrow(query, *args)

    async def _fetchval(self, query, *args, conn=None):
        await self._ensure_pool()
        if conn:
            return await conn.fetchval(query, *args)
        async with self.pool.acquire() as c:
            return await c.fetchval(query, *args)

    async def _execute(self, query, *args, conn=None):
        await self._ensure_pool()
        if conn:
            return await conn.execute(query, *args)
        async with self.pool.acquire() as c:
            return await c.execute(query, *args)

    async def get_latest_open_race(self, guild_id):
        return await self._fetchrow("""
            SELECT *
            FROM race_schedules
            WHERE guild_id = $1
              AND lottery_done = TRUE
              AND race_finished = FALSE
            ORDER BY race_date DESC, race_no DESC
            LIMIT 1
        """, guild_id)





























