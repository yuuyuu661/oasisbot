from fastapi import FastAPI, HTTPException
from datetime import date
import os
import asyncpg
from datetime import date, datetime

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

# DB接続（API専用・readonly）
async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

@app.get("/api/race/{race_date}/{schedule_id}")
async def get_race_entries(race_date: str, schedule_id: int):
    try:
        race_date_obj = datetime.strptime(race_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    conn = await get_conn()
    try:
        # レース情報取得
        race = await conn.fetchrow("""
            SELECT *
            FROM race_schedules
            WHERE race_date = $1
              AND id = $2
        """, race_date_obj, schedule_id)

        if not race:
            raise HTTPException(status_code=404, detail="Race not found")

        # ロック判定
        locked = race["lottery_done"] is True and race["race_finished"] is False

        # 出走おあしすっち取得（抽選済み）
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
              AND e.race_date = $2
              AND e.status = 'selected'
            ORDER BY e.created_at
            LIMIT 8
        """, schedule_id, race_date_obj)

        pets = []
        for e in entries:
            pets.append({
                "pet_id": e["pet_id"],
                "name": e["name"],
                "adult_key": e["adult_key"],
                "speed": e["speed"],
                "power": e["power"],
                "stamina": e["stamina"],
                "condition": "normal",  # ←後で本物にする
                "odds": None            # ←Web側で計算
            })

        return {
            "race_date": race_date,
            "race_time": race["race_time"],
            "locked": locked,
            "pets": pets
        }

    finally:
        await conn.close()

