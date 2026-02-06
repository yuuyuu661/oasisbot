from fastapi import FastAPI, HTTPException
import os
import asyncpg
from datetime import datetime

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/api/race/{guild_id}/{race_date}/{race_no}")
async def get_race_entries(guild_id: str, race_date: str, race_no: int):

    try:
        race_date_obj = datetime.strptime(race_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    async with asyncpg.connect(DATABASE_URL) as conn:

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
                p.speed,
                p.power,
                p.stamina
            FROM race_entries e
            JOIN oasistchi_pets p ON p.id = e.pet_id
            WHERE e.schedule_id = $1
              AND e.race_date = $2
              AND e.guild_id = $3
              AND e.status = 'selected'
            ORDER BY e.created_at
            LIMIT 8
        """, race["id"], race_date_obj, guild_id)

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
