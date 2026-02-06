# web_api.py
from fastapi import FastAPI, HTTPException
from datetime import date
from db import Database

app = FastAPI()
@app.get("/health")
async def health():
    return {"status": "ok"}
db = Database()


@app.on_event("startup")
async def startup():
    # Botと同じDBを使う
    await db.connect()


@app.get("/api/race/{guild_id}/{race_date}/{schedule_id}")
async def get_race_candidates(
    guild_id: str,
    race_date: str,
    schedule_id: int
):
    """
    出走確定したおあしすっち（最大8体）を返す
    Webの「〇券購入」画面用
    """

    try:
        race_date = date.fromisoformat(race_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid race_date")

    # 出走確定エントリー取得
    entries = await db.get_selected_entries(schedule_id)

    pets = []
    for e in entries:
        pet = await db.get_oasistchi_pet(e["pet_id"])
        if not pet:
            continue

        pets.append({
            "pet_id": pet["id"],
            "name": pet["name"],
            "adult_key": pet["adult_key"],
            "condition": pet["condition"] if "condition" in pet else "normal",
            "stats": {
                "speed": pet["speed"],
                "power": pet["power"],
                "stamina": pet["stamina"],
            },
            # Web側でそのまま使えるパス
            "gif": f"/static/pets/{pet['adult_key']}.gif",
        })

    return {
        "race_date": race_date.isoformat(),
        "schedule_id": schedule_id,
        "count": len(pets),
        "pets": pets

    }
