from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncpg
from datetime import datetime
import math
import random
import hmac
import hashlib
from pydantic import BaseModel
from datetime import timedelta, timezone
from fastapi.middleware.cors import CORSMiddleware

JST = timezone(timedelta(hours=9))
UNIT_PRICE = 1000
MAX_UNITS = 100
MAX_AMOUNT = UNIT_PRICE * MAX_UNITS  # 100,000rrc
TEST_MODE = True

WEB_SECRET = "9f3a7c4d8b2e1f0a6c8d9e7f1a2b3c4d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a5"

print("🔐 WEB_SECRET loaded (WEB)")



# ===== レース用計算ロジック =====

K_VALUE = 2.5
HOUSE_TAKE = 0.20  # 控除率20%

def apply_condition_multiplier(speed, power, stamina, happiness):
    """
    幸福度 0〜100 → 発揮率 0.8〜1.0
    0でも最低80%は出す（競馬寄り）
    """
    h = max(0, min(100, happiness))

    ratio = 0.8 + (h / 100.0) * 0.2
    # happiness 0 → 0.8
    # happiness 50 → 0.9
    # happiness 100 → 1.0

    return (
        speed * ratio,
        power * ratio,
        stamina * ratio,
        ratio
    )


# =========================
# 🎯 パリミュチュエル計算式
# =========================
def calculate_odds(total_pool: int, pet_pool: int, take_rate: float = 0.10):
    """
    total_pool: レース全体の投票総額
    pet_pool:   そのペットへの投票総額
    take_rate:  控除率（例 0.10 = 10%）
    """

    if total_pool <= 0:
        return 1.5  # まだ誰も賭けてない場合の初期値

    if pet_pool <= 0:
        return 1.5  # そのペットにまだ票がない場合は最大表示


    payout_pool = total_pool * (1 - take_rate)
    odds = payout_pool / pet_pool

    # 最小1.1倍、最大10倍に制限
    return round(max(1.0, odds), 2)

def get_race_phase(race):
    now = datetime.now(JST)

    race_date = race["race_date"]
    race_time = race["race_time"]

    # ★ 完全安全変換
    if isinstance(race_time, str):
        try:
            race_time = datetime.strptime(race_time, "%H:%M:%S").time()
        except ValueError:
            race_time = datetime.strptime(race_time, "%H:%M").time()

    race_datetime = datetime.combine(
        race_date,
        race_time,
        JST
    )

    entry_close = race_datetime - timedelta(hours=1)
    race_end = race_datetime + timedelta(hours=1)

    if now < entry_close:
        return "entry"
    elif entry_close <= now < race_datetime:
        return "betting"
    elif race_datetime <= now < race_end:
        return "racing"
    else:
        return "closed"

def get_condition_label(happiness: int):
    if happiness >= 80:
        return "好調", "good"
    elif happiness >= 50:
        return "普通", "normal"
    else:
        return "不調", "bad"

# =========================
# 🔐 トークン検証
# =========================
def verify_token(user_id: str, guild_id: str, race_id: str, token: str):
    message = f"{user_id}:{guild_id}:{race_id}"
    expected = hmac.new(
        WEB_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, token)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL が設定されていません")

# =========================
# 🔥 POOL作成 + schema補完
# =========================
@app.on_event("startup")
async def ensure_schema():
    app.state.pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10
    )

    async with app.state.pool.acquire() as conn:
        async def ensure_column(table, column, definition):
            exists = await conn.fetchval("""
                SELECT 1
                FROM information_schema.columns
                WHERE table_name=$1
                  AND column_name=$2
            """, table, column)
            if not exists:
                print(f"🔧 Adding {column} to {table}...")
                await conn.execute(f"""
                    ALTER TABLE {table}
                    ADD COLUMN {column} {definition}
                """)
                print(f"✅ {column} added to {table}")

        # race_bets の不足カラムを補完
        await ensure_column("race_bets", "guild_id", "TEXT")
        await ensure_column("race_bets", "schedule_id", "INTEGER")
        await ensure_column("race_bets", "race_date", "DATE")

@app.on_event("shutdown")
async def shutdown():
    await app.state.pool.close()

@app.get("/api/race/by-id/{guild_id}/{schedule_id}")
async def get_race_by_id(guild_id: str, schedule_id: int):

    async with app.state.pool.acquire() as conn:

        race = await conn.fetchrow("""
            SELECT *
            FROM race_schedules
            WHERE guild_id = $1
              AND id = $2
        """, guild_id, schedule_id)

        if not race:
            raise HTTPException(status_code=404, detail="Race not found")

        phase = get_race_phase(race)

        # =========================
        # 出走馬取得
        # =========================
        entries = await conn.fetch("""
            SELECT
                e.pet_id,
                p.name,
                p.adult_key,
                (p.base_speed + p.train_speed) AS speed,
                (p.base_power + p.train_power) AS power,
                (p.base_stamina + p.train_stamina) AS stamina,
                p.happiness,
                p.passive_skill
            FROM race_entries e
            JOIN oasistchi_pets p ON p.id = e.pet_id
            WHERE e.schedule_id = $1
              AND e.guild_id = $2
              AND e.status = 'selected'
            ORDER BY e.created_at
        """, schedule_id, guild_id)

        # =========================
        # 🔥 全体プール取得
        # =========================
        total_pool_row = await conn.fetchrow("""
            SELECT total_pool
            FROM race_pools
            WHERE guild_id = $1
              AND race_date = $2
              AND schedule_id = $3
        """, guild_id, race["race_date"], race["id"])

        total_pool = total_pool_row["total_pool"] if total_pool_row else 0

        # =========================
        # 🔥 ペット別プール取得
        # =========================
        pet_pool_rows = await conn.fetch("""
            SELECT pet_id, total_amount
            FROM race_pet_pools
            WHERE guild_id = $1
              AND race_date = $2
              AND schedule_id = $3
        """, guild_id, race["race_date"], race["id"])

        pet_pools = {r["pet_id"]: r["total_amount"] for r in pet_pool_rows}

        pets = []

        for e in entries:

            # ペットのプール額
            pet_pool = pet_pools.get(e["pet_id"], 0)

            # オッズ計算
            odds = calculate_odds(total_pool, pet_pool, take_rate=0.10)

            # コンディション表示
            label, cls = get_condition_label(e["happiness"])

            pets.append({
                "pet_id": e["pet_id"],
                "name": e["name"],
                "adult_key": e["adult_key"],
                "speed": e["speed"],
                "power": e["power"],
                "stamina": e["stamina"],
                "condition_label": label,
                "condition_class": cls,
                "passive_skill": e["passive_skill"],
                "odds": odds
            })

        return {
            "schedule_id": race["id"],
            "race_date": str(race["race_date"]),
            "race_time": race["race_time"],
            "distance": race["distance"],
            "surface": race["surface"],
            "phase": phase,
            "locked": race["lottery_done"],
            "pets": pets
        }

# =========================
# 🔐 トークン検証API
# =========================
@app.get("/api/verify")
async def verify(user: str, guild: str, race: str, token: str):

    if not verify_token(user, guild, race, token):
        raise HTTPException(status_code=403, detail="Invalid token")

    async with app.state.pool.acquire() as conn:
        race_row = await conn.fetchrow("""
            SELECT id
            FROM race_schedules
            WHERE id = $1
              AND guild_id = $2
        """, int(race), guild)

        if not race_row:
            raise HTTPException(status_code=404, detail="Race not found")

    return {
        "status": "ok",
        "user": user,
        "guild": guild,
        "race": race
    }





@app.get("/api/race/{guild_id}/{race_date}/{race_no}")
async def get_race_entries(guild_id: str, race_date: str, race_no: int):

    try:
        race_date_obj = datetime.strptime(race_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    async with app.state.pool.acquire() as conn:

        race = await conn.fetchrow("""
            SELECT *
            FROM race_schedules
            WHERE race_date = $1
              AND race_no = $2
              AND guild_id = $3
        """, race_date_obj, race_no, guild_id)

        if not race:
            raise HTTPException(status_code=404, detail="Race not found")

        phase = get_race_phase(race)

        

        locked = race["lottery_done"] is True and race["race_finished"] is False

        entries = await conn.fetch("""
            SELECT
                e.pet_id,
                p.name,
                p.adult_key,
                (p.base_speed + p.train_speed) AS speed,
                (p.base_power + p.train_power) AS power,
                (p.base_stamina + p.train_stamina) AS stamina,
                p.happiness
            FROM race_entries e
            JOIN oasistchi_pets p ON p.id = e.pet_id
            WHERE e.schedule_id = $1
              AND e.race_date = $2
              AND e.guild_id = $3
              AND e.status = 'selected'
            ORDER BY e.created_at
        """, race["id"], race["race_date"], guild_id)

        processed = []

        for e in entries:
            base_speed = e["speed"]
            base_power = e["power"]
            base_stamina = e["stamina"]
            happiness = e["happiness"]

            speed, power, stamina, ratio = apply_condition_multiplier(
                base_speed, base_power, base_stamina, happiness
            )

            processed.append({
                "pet_id": e["pet_id"],
                "name": e["name"],
                "adult_key": e["adult_key"],
                "speed": round(speed),
                "power": round(power),
                "stamina": round(stamina),
                "ratio": ratio
            })

        if not processed:
            return {
                "schedule_id": race["id"],
                "race_date": race_date,
                "race_time": race["race_time"],
                "locked": locked,
                "phase": phase,   # ← ★ これ追加
                "pets": [],
                "distance": race["distance"],
                "surface": race["surface"]
            }

        # ===== プール取得 =====
        total_pool_row = await conn.fetchrow("""
            SELECT total_pool
            FROM race_pools
            WHERE guild_id = $1
              AND race_date = $2
              AND schedule_id = $3
        """, guild_id, race["race_date"], race["id"])

        total_pool = total_pool_row["total_pool"] if total_pool_row else 0

        pet_pool_rows = await conn.fetch("""
            SELECT pet_id, total_amount
            FROM race_pet_pools
            WHERE guild_id = $1
              AND race_date = $2
              AND schedule_id = $3
        """, guild_id, race["race_date"], race["id"])

        pet_pools = {r["pet_id"]: r["total_amount"] for r in pet_pool_rows}

        pets = []
        for p in processed:
            pet_id = p["pet_id"]
            pet_pool = pet_pools.get(pet_id, 0)

            odds = calculate_odds(total_pool, pet_pool, take_rate=0.10)

            pets.append({
                "pet_id": pet_id,
                "name": p["name"],
                "adult_key": p["adult_key"],
                "speed": p["speed"],
                "power": p["power"],
                "stamina": p["stamina"],
                "condition_label": "—",
                "condition_class": "normal",
                "condition_ratio": 1.0,
                "odds": odds
            })

        return {
            "schedule_id": race["id"],
            "race_date": race_date,
            "race_time": race["race_time"],
            "locked": locked,
            "phase": phase,      # ← ★ ここ追加
            "pets": pets,
            "distance": race["distance"],
            "surface": race["surface"]
        }

@app.get("/api/balance")
async def get_balance(
    user: str,
    guild: str,
    race: int,
    token: str
):
    # トークン検証
    if not verify_token(user, guild, str(race), token):
        raise HTTPException(status_code=403, detail="Invalid token")

    async with app.state.pool.acquire() as conn:
        balance = await conn.fetchval("""
            SELECT balance
            FROM users
            WHERE user_id = $1
              AND guild_id = $2
        """, user, guild)

        if balance is None:
            raise HTTPException(status_code=400, detail="ユーザー未登録")

        return {"balance": balance}

# =========================
# ★ ここに追加する ★
# 最新レース取得API
# =========================

@app.get("/api/race/latest/{guild_id}")
async def get_latest_race(guild_id: str):
    async with app.state.pool.acquire() as conn:
        race = await conn.fetchrow("""
            SELECT *
            FROM race_schedules
            WHERE guild_id = $1
            ORDER BY race_date DESC, race_no DESC
            LIMIT 1
        """, guild_id)

        if not race:
            return {"exists": False}

        phase = get_race_phase(race)

        return {
            "exists": True,
            "phase": phase,
            "schedule_id": race["id"],
            "race_no": race["race_no"],
            "race_date": str(race["race_date"]),
            "race_time": race["race_time"]
        }

# =========================
# レース順位API
# =========================
@app.get("/api/race/result/{guild_id}/{race_date}/{schedule_id}")
async def get_race_result(guild_id: str, race_date: str, schedule_id: int):

    # 🔥 ここが重要
    try:
        race_date_obj = datetime.strptime(race_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT re.pet_id,
                   re.rank,
                   re.score,
                   p.name,
                   p.base_speed,
                   p.train_speed,
                   p.base_stamina,
                   p.train_stamina,
                   p.base_power,
                   p.train_power
            FROM race_entries re
            JOIN oasistchi_pets p
              ON p.id = re.pet_id
            WHERE re.guild_id = $1
              AND re.race_date = $2
              AND re.schedule_id = $3
              AND re.status = 'selected'
            ORDER BY re.rank ASC
        """, guild_id, race_date_obj, schedule_id)

        return {
            "results": [dict(r) for r in rows]
        }
# =========================
# 3連単用順位API
# =========================
@app.get("/api/trifecta/odds")
async def get_trifecta_odds(
    guild: str,
    race_date: str,
    schedule_id: int,
    first: int,
    second: int,
    third: int
):
    odds = await db.get_trifecta_odds(
        guild,
        race_date,
        schedule_id,
        first,
        second,
        third
    )

    if odds is None:
        return {"status": "no_bets"}

    return {
        "status": "ok",
        "odds": odds
    }

# =========================
# 🎫 馬券購入API
# =========================

class BetRequest(BaseModel):
    user: str
    guild: str
    race: int
    pet_id: int
    amount: int
    token: str


@app.post("/api/bet")
async def place_bet(data: BetRequest):

    UNIT_PRICE = 1000
    MAX_UNITS = 100
    MAX_AMOUNT = UNIT_PRICE * MAX_UNITS  # 100,000rrc

    # ① トークン検証
    if not verify_token(data.user, data.guild, str(data.race), data.token):
        raise HTTPException(status_code=403, detail="Invalid token")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    # 🔒 1000rrc単位チェック
    if data.amount % UNIT_PRICE != 0:
        raise HTTPException(status_code=400, detail="1口1000rrc単位です")

    async with app.state.pool.acquire() as conn:
        async with conn.transaction():

            # ② レース確認
            race = await conn.fetchrow("""
                SELECT *
                FROM race_schedules
                WHERE id = $1
                  AND guild_id = $2
            """, data.race, data.guild)

            if not race:
                raise HTTPException(status_code=404, detail="Race not found")

            if race["lottery_done"] and not TEST_MODE:
                raise HTTPException(status_code=400, detail="Betting closed")

            # ③ 現在の購入合計取得
            total_user_bet = await conn.fetchval("""
                SELECT COALESCE(SUM(amount),0)
                FROM race_bets
                WHERE guild_id = $1
                  AND schedule_id = $2
                  AND user_id = $3
            """, data.guild, race["id"], data.user)

            new_total = total_user_bet + data.amount

            if new_total > MAX_AMOUNT:
                raise HTTPException(
                    status_code=400,
                    detail="このレースでは最大100口まで購入できます"
                )

            # ④ 残高取得
            balance = await conn.fetchval("""
                SELECT balance
                FROM users
                WHERE user_id = $1
                  AND guild_id = $2
            """, data.user, data.guild)

            if balance is None:
                raise HTTPException(status_code=400, detail="ユーザー未登録")

            if balance < data.amount:
                raise HTTPException(status_code=400, detail="残高不足")

            # ⑤ 残高減算
            await conn.execute("""
                UPDATE users
                SET balance = balance - $1
                WHERE user_id = $2
                  AND guild_id = $3
            """, data.amount, data.user, data.guild)

            # ⑥ bet追加
            await conn.execute("""
                INSERT INTO race_bets
                (race_id, guild_id, race_date, schedule_id, user_id, pet_id, amount)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """,
                str(race["id"]),   # TEXT
                str(data.guild),   # TEXT
                race["race_date"], # DATE
                race["id"],        # INTEGER
                str(data.user),    # TEXT
                data.pet_id,       # ← ★ここはそのまま整数
                data.amount        # INTEGER
            )
            # ⑦ 全体プール更新
            await conn.execute("""
                INSERT INTO race_pools
                (guild_id, race_date, schedule_id, total_pool)
                VALUES ($1,$2,$3,$4)
                ON CONFLICT (guild_id, race_date, schedule_id)
                DO UPDATE SET total_pool = race_pools.total_pool + $4
            """,
                data.guild,
                race["race_date"],
                race["id"],
                data.amount
            )

            # ⑧ 個別プール更新
            await conn.execute("""
                INSERT INTO race_pet_pools
                (guild_id, race_date, schedule_id, pet_id, total_amount)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (guild_id, race_date, schedule_id, pet_id)
                DO UPDATE SET total_amount = race_pet_pools.total_amount + $5
            """,
                data.guild,
                race["race_date"],
                race["id"],
                data.pet_id,
                data.amount
            )

            # ⑨ 最新オッズ取得
            total_pool = await conn.fetchval("""
                SELECT total_pool
                FROM race_pools
                WHERE guild_id = $1
                  AND race_date = $2
                  AND schedule_id = $3
            """, data.guild, race["race_date"], race["id"])

            pet_pool = await conn.fetchval("""
                SELECT total_amount
                FROM race_pet_pools
                WHERE guild_id = $1
                  AND race_date = $2
                  AND schedule_id = $3
                  AND pet_id = $4
            """, data.guild, race["race_date"], race["id"], data.pet_id)

            odds = calculate_odds(total_pool, pet_pool, take_rate=0.10)

            return {
                "status": "ok",
                "new_odds": odds,
                "user_total_bet": new_total,
                "remaining_units": (MAX_AMOUNT - new_total) // UNIT_PRICE,
                "remaining_balance": balance - data.amount
            }
