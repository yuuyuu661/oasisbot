from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncpg
from datetime import datetime

app = FastAPI()

# ★ ここを追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lacesite-production.up.railway.app"
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
                (p.base_stamina + p.train_stamina) AS stamina
            FROM race_entries e
            JOIN oasistchi_pets p ON p.id = e.pet_id
            WHERE e.schedule_id = $1
              AND e.race_date = $2
              AND e.guild_id = $3
              AND e.status = 'selected'
            ORDER BY e.created_at
        """, race["id"], race["race_date"], guild_id)

        pets = [{
            "pet_id": e["pet_id"],
            "name": e["name"],
            "adult_key": e["adult_key"],
            "speed": e["speed"],
            "power": e["power"],
            "stamina": e["stamina"],
            "condition": "normal",
            "odds": None
        } for e in entries]

        return {
            "race_date": race_date,
            "race_time": race["race_time"],
            "locked": locked,
            "pets": pets
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
                p.speed,
                p.power,
                p.stamina
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




