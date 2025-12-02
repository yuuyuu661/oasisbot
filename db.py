# db.py
import asyncpg

class Database:
    def __init__(self):
        self.pool = None

    async def init_db(self):
        self.pool = await asyncpg.create_pool()

        async with self.pool.acquire() as con:

            # users（ギルド別通貨管理）
            await con.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT,
                    guild_id TEXT,
                    balance BIGINT DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                );
            """)

            # role_salaries（給料もギルド別）
            await con.execute("""
                CREATE TABLE IF NOT EXISTS role_salaries (
                    role_id TEXT,
                    guild_id TEXT,
                    salary BIGINT DEFAULT 0,
                    PRIMARY KEY (role_id, guild_id)
                );
            """)

            # settings（ギルド別設定）
            await con.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    guild_id TEXT PRIMARY KEY,
                    admin_roles TEXT,
                    log_pay TEXT,
                    log_manage TEXT,
                    log_salary TEXT,
                    currency_unit TEXT DEFAULT 'rrc'
                );
            """)

    # ---------------------------
    # Users / Balance
    # ---------------------------
    async def get_user(self, user_id, guild_id):
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                "SELECT * FROM users WHERE user_id=$1 AND guild_id=$2",
                user_id, guild_id
            )
            if row:
                return dict(row)

            await con.execute(
                "INSERT INTO users (user_id, guild_id, balance) VALUES ($1, $2, 0)",
                user_id, guild_id
            )
            return {"user_id": user_id, "guild_id": guild_id, "balance": 0}

    async def add_balance(self, user_id, guild_id, amount):
        async with self.pool.acquire() as con:
            await con.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id=$2 AND guild_id=$3",
                amount, user_id, guild_id
            )

    async def remove_balance(self, user_id, guild_id, amount):
        async with self.pool.acquire() as con:
            await con.execute(
                "UPDATE users SET balance = GREATEST(balance - $1, 0) WHERE user_id=$2 AND guild_id=$3",
                amount, user_id, guild_id
            )

    async def set_balance(self, user_id, guild_id, amount):
        async with self.pool.acquire() as con:
            await con.execute(
                """
                INSERT INTO users (user_id, guild_id, balance)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET balance=$3
                """,
                user_id, guild_id, amount
            )

    async def get_all_balances(self, guild_id):
        async with self.pool.acquire() as con:
            rows = await con.fetch(
                "SELECT * FROM users WHERE guild_id=$1 ORDER BY balance DESC",
                guild_id
            )
            return [dict(r) for r in rows]

    # ---------------------------
    # Salary
    # ---------------------------
    async def set_salary(self, role_id, guild_id, salary):
        async with self.pool.acquire() as con:
            await con.execute(
                """
                INSERT INTO role_salaries (role_id, guild_id, salary)
                VALUES ($1, $2, $3)
                ON CONFLICT (role_id, guild_id)
                DO UPDATE SET salary=$3
                """,
                role_id, guild_id, salary
            )

    async def get_salaries(self, guild_id):
        async with self.pool.acquire() as con:
            rows = await con.fetch(
                "SELECT * FROM role_salaries WHERE guild_id=$1",
                guild_id
            )
            return [dict(r) for r in rows]

    # ---------------------------
    # Settings
    # ---------------------------
    async def ensure_settings(self, guild_id):
        async with self.pool.acquire() as con:
            await con.execute(
                """
                INSERT INTO settings (guild_id)
                VALUES ($1)
                ON CONFLICT (guild_id) DO NOTHING
                """,
                guild_id
            )

    async def get_settings(self, guild_id):
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                "SELECT * FROM settings WHERE guild_id=$1",
                guild_id
            )
            if not row:
                await self.ensure_settings(guild_id)
                row = await con.fetchrow(
                    "SELECT * FROM settings WHERE guild_id=$1",
                    guild_id
                )
            d = dict(row)
            d["admin_roles"] = d["admin_roles"].split(",") if d["admin_roles"] else []
            return d

    async def update_settings(self, guild_id, **kwargs):
        set_parts = []
        values = []
        idx = 1

        if "admin_roles" in kwargs:
            kwargs["admin_roles"] = ",".join(kwargs["admin_roles"])

        for key, value in kwargs.items():
            set_parts.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1

        sql = f"UPDATE settings SET {', '.join(set_parts)} WHERE guild_id = ${idx}"
        values.append(guild_id)

        async with self.pool.acquire() as con:
            await con.execute(sql, *values)
