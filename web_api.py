from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncpg
from datetime import datetime
import math
import random
import hmac
import hashlib

WEB_SECRET = os.getenv("WEB_SECRET")

if not WEB_SECRET:
    raise ValueError("WEB_SECRET が設定されていません")

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


def calc_ability(speed, power, stamina):
    # 今はシンプル固定重み
    return 1.25*speed + 1.0*power + 1.0*stamina

def softmax_probabilities(abilities, k=K_VALUE):
    weighted = [a**k for a in abilities]
    total = sum(weighted)
    return [w/total for w in weighted]

def probs_to_odds(probs):
    odds = []
    for p in probs:
        if p <= 0:
            odds.append(99.9)
        else:
            o = (1 - HOUSE_TAKE) / p
            o = max(1.4, min(80.0, o))
            odds.append(round(o, 1))
    return odds

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

# =========================
# 🔐 トークン検証API
# =========================
@app.get("/api/verify")
async def verify(user: str, guild: str, race: str, token: str):

    # ① トークン検証
    if not verify_token(user, guild, race, token):
        raise HTTPException(status_code=403, detail="Invalid token")

    # ② レース存在確認（念のため）
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        race_row = await conn.fetchrow("""
            SELECT id
            FROM race_schedules
            WHERE id = $1
              AND guild_id = $2
        """, int(race), guild)

        if not race_row:
            raise HTTPException(status_code=404, detail="Race not found")

    finally:
        await conn.close()

    return {
        "status": "ok",
        "user": user,
        "guild": guild,
        "race": race
    }

app = FastAPI()

# ★ ここを追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lacesite-production.up.railway.app",
        "https://oasisbot-production.up.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/api/race/{guild_id}/{race_date}/{race_no}")
async def get_race_entries(guild_id: str, race_date: str, race_no: int):

    try:
        race_date_obj = datetime.strptime(race_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        race = await conn.fetchrow("""
            SELECT *
            FROM race_schedules
            WHERE race_date = $1
              AND race_no = $2
              AND guild_id = $3
        """, race_date_obj, race_no, guild_id)

        if not race:
            raise HTTPException(status_code=404, detail="Race not found")

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

            ability = calc_ability(speed, power, stamina)

            processed.append({
                "pet_id": e["pet_id"],
                "name": e["name"],
                "adult_key": e["adult_key"],
                "speed": round(speed),
                "power": round(power),
                "stamina": round(stamina),
                "ability": ability,
                "ratio": ratio
            })

        if not processed:
            return {
                "schedule_id": race["id"],
                "race_date": race_date,
                "race_time": race["race_time"],
                "locked": locked,
                "pets": [],  # ← 空配列にする
                "distance": race["distance"],
                "surface": race["surface"]
            }

        # ===== 勝率計算 =====
        abilities = [p["ability"] for p in processed]
        probs = softmax_probabilities(abilities)
        odds_list = probs_to_odds(probs)

        pets = []
        for i, p in enumerate(processed):
            label, css_class = get_condition_label(
                int((p["ratio"] - 0.8) / 0.2 * 100)
            )

            pets.append({
                "pet_id": p["pet_id"],
                "name": p["name"],
                "adult_key": p["adult_key"],
                "speed": p["speed"],
                "power": p["power"],
                "stamina": p["stamina"],
                "condition_label": label,
                "condition_class": css_class,
                "condition_ratio": round(p["ratio"], 2),
                "odds": odds_list[i]
            })

        return {
            "schedule_id": race["id"],
            "race_date": race_date,
            "race_time": race["race_time"],
            "locked": locked,
            "pets": pets,
            "distance": race["distance"],
            "surface": race["surface"]
        }

    finally:
        await conn.close()
# =========================
# ★ ここに追加する ★
# 最新レース取得API
# =========================
@app.get("/api/race/latest/{guild_id}")
async def get_latest_race(guild_id: str):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # 抽選済み＆未完了の最新レース
        race = await conn.fetchrow("""
            SELECT *
            FROM race_schedules
            WHERE guild_id = $1
              AND lottery_done = TRUE
              AND race_finished = FALSE
            ORDER BY race_date DESC, race_no DESC
            LIMIT 1
        """, guild_id)

        if not race:
            return {
                "locked": False,
                "pets": []
            }

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
              AND e.status = 'selected'
            ORDER BY e.created_at
        """, race["id"])

        pets = [{
            "pet_id": e["pet_id"],
            "name": e["name"],
            "adult_key": e["adult_key"],
            "speed": e["speed"],
            "power": e["power"],
            "stamina": e["stamina"],
            "condition": "normal"
        } for e in entries]

        return {
            "schedule_id": race["id"],
            "race_no": race["race_no"],
            "race_date": str(race["race_date"]),
            "race_time": race["race_time"],
            "locked": True,
            "pets": pets
        }

    finally:
        await conn.close()



















