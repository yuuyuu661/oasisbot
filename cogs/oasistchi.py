import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
import os
import random
from PIL import Image
from io import BytesIO
import asyncio
from PIL import Image, ImageSequence
from datetime import datetime, timezone, timedelta, time as dtime
JST = timezone(timedelta(hours=9))


def get_today_jst_date():
    JST = timezone(timedelta(hours=9))
    """JST基準の今日の日付を返す"""
    return datetime.now(JST).date()

def today_jst_str() -> str:
    JST = timezone(timedelta(hours=9))
    return datetime.now(JST).strftime("%Y-%m-%d")

# =========================
# ここだけ環境に合わせて
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # oasisbot/cogs
ASSET_BASE = os.path.join(BASE_DIR, "assets", "oasistchi")
GAUGE_DIR = os.path.join(ASSET_BASE, "gauge")

EGG_COLORS = [
    ("red", "🔴 あかいたまご"),
    ("blue", "🔵 あおいたまご"),
    ("green", "🟢 みどりたまご"),
    ("yellow", "🟡 きいろたまご"),
    ("purple", "🟣 むらさきたまご"),
]

EGG_CATALOG = [
    {
        "key": key,
        "name": name,
        "icon": os.path.join(ASSET_BASE, "egg", key, "idle.gif")
    }
    for key, name in EGG_COLORS
]
ADULT_CATALOG = [
    {"key": "cyan","name": "ちゃん","groups": ["blue"]},
    {"key": "eru","name": "エル","groups": ["green"]},
    {"key": "inpure","name": "いんぷれ","groups": ["purple"]},
    {"key": "kirigiri","name": "きりぎり","groups": ["yellow"]},
    {"key": "kiza","name": "きっざにあ","groups": ["red"]},
    {"key": "konkuri","name": "こんくり","groups": ["blue"]},
    {"key": "kurisu","name": "クリス","groups": ["green"]},
    {"key": "misui","name": "みすい","groups": ["purple"]},
    {"key": "nino","name": "にの","groups": ["yellow"]},
    {"key": "numaru","name": "ぬまるん","groups": ["red"]},
    {"key": "saotome","name": "さおとめ","groups": ["blue"]},
    {"key": "sato","name": "さとー","groups": ["green"]},
    {"key": "yuina","name": "ゆいな","groups": ["purple"]},
    {"key": "zenten","name": "ぜんてん","groups": ["yellow"]},
    {"key": "eng","name": "えんじぇる","groups": ["red"]},
    {"key": "yama","name": "やまだ","groups": ["blue"]},
    {"key": "kono","name": "この","groups": ["green"]},
    {"key": "hiro","name": "ヒロ","groups": ["purple"]},
    {"key": "mio","name": "mio","groups": ["yellow"]},
    {"key": "bul","name": "おいら","groups": ["red"]},
    {"key": "yabo","name": "やぼう","groups": ["blue"]},
    {"key": "hana","name": "はなこ","groups": ["green"]},
    {"key": "inu","name": "いぬ","groups": ["purple"]},
    {"key": "saku","name": "さく","groups": ["yellow"]},
    {"key": "ouki","name": "おうき","groups": ["red"]},
    {"key": "aka","name": "あかり","groups": ["blue"]},
    {"key": "shiba","name": "しば","groups": ["green"]},
    {"key": "ero","name": "えろこ","groups": ["purple"]},
    {"key": "gero","name": "ゲロ","groups": ["yellow"]},
    {"key": "san","name": "サンダー","groups": ["red"]},  
    {"key": "jinsei","name": "loser","groups": ["red"]},
    {"key": "kaeko","name": "かえこ","groups": ["blue"]},
    {"key": "remi","name": "れみたん","groups": ["green"]},
    {"key": "tonbo","name": "トンボ","groups": ["purple"]},
    {"key": "yuyu","name": "ゆゆ","groups": ["yellow"]},
    {"key": "naruse","name": "なるせ","groups": ["purple"]},
    {"key": "rapi","name": "ラピ","groups": ["yellow"]},
    {"key": "rei","name": "れい","groups": ["red"]},  
    {"key": "tumu","name": "つむ","groups": ["blue"]},
    {"key": "urufu","name": "うるふ","groups": ["green"]},
    
    {"key": "cyoumi","name": "ちょうみりょう","groups": ["purple"]},
    {"key": "erechima","name": "ういえれ","groups": ["yellow"]},
    {"key": "tenshi","name": "てんし","groups": ["red"]},  
    {"key": "muku","name": "むく","groups": ["blue"]},
    {"key": "shigu","name": "シグ","groups": ["green"]},


]


TRAIN_RESULTS = [
    (1, "今回はダメかも..."),
    (2, "今回はまあまあ..."),
    (3, "今回はかなりいい！"),
    (4, "今回はすばらしい！"),
    (5, "今回は大成功だ！！！"),
]

RACE_TIMES = ["09:00", "12:00", "15:00", "19:00", "22:00"]
RACE_RESULT_CHANNEL_ID = 1466693608366276793

DISTANCES = ["短距離", "マイル", "中距離", "長距離"]
SURFACES = ["芝", "ダート"]
CONDITIONS = ["良", "稍重", "重", "不良"]
MAX_ENTRIES = 8

def now_ts() -> float:
    return time.time()

def build_growth_gauge_file(growth: float) -> discord.File:
    """
    孵化ゲージ画像を返す（切り捨て）
    growth: 0.0 ～ 100.0
    """

    if growth >= 100:
        gauge = 10
    else:
        gauge = int(growth // 10)

    gauge = max(0, min(10, gauge))

    filename = f"gauge_{gauge:02}.png"
    path = os.path.join(GAUGE_DIR, filename)

    return discord.File(path, filename="growth.png")

def gauge_emoji(value: int, max_value: int = 100, emoji: str = "😊", steps: int = 10):
    count = max(0, min(steps, round(value / max_value * steps)))
    return emoji * max(1, count)

def growth_rate_per_hour(stage: str) -> float:
    if stage == "egg":
        return 100.0 / 12.0     # 12時間
    return 0.0

def get_pet_file(pet: dict, state: str) -> discord.File:
    """
    state: "idle" | "pet" | "clean" | "poop"
    """
    if pet["stage"] == "adult":
        key = pet["adult_key"]
        path = os.path.join(ASSET_BASE, "adult", key, f"{state}.gif")
    else:
        egg = pet.get("egg_type", "red")
        path = os.path.join(ASSET_BASE, "egg", egg, f"{state}.gif")
    return discord.File(path, filename="pet.gif")

def calc_effective_stats(pet: dict):
    """
    レース用 実効ステータス計算
    ・幸福度による減衰（0〜100%）
    ・根性（最大10%）判定込み
    """

    # 幸福度を安全に 0〜100 に丸める
    happiness = max(0, min(100, pet.get("happiness", 100)))
    rate = happiness / 100.0

    base_speed = pet["base_speed"] + pet["train_speed"]
    base_stamina = pet["base_stamina"] + pet["train_stamina"]
    base_power = pet["base_power"] + pet["train_power"]

    speed = base_speed * rate
    stamina = base_stamina * rate
    power = base_power * rate

    # 🔥 根性判定（幸福度10%ごとに1%）
    guts_chance = happiness // 10  # 0〜10 (%)
    guts = False

    if random.randint(1, 100) <= guts_chance:
        speed *= 1.1
        stamina *= 1.1
        power *= 1.1
        guts = True

    return {
        "speed": int(speed),
        "stamina": int(stamina),
        "power": int(power),
        "guts": guts,
        "rate": rate,              # デバッグ・表示用
        "guts_chance": guts_chance # ログ・演出用
    }
    
def get_condition_text(self, happiness: int) -> str:
    if happiness >= 80:
        return "好調 😄"
    elif happiness >= 50:
        return "普通 😐"
    else:
        return "不調 😰"
        
def generate_initial_stats():
    """
    孵化時ステータス生成
    各ステータス 30〜50
    """
    return {
        "speed": random.randint(30, 50),
        "stamina": random.randint(30, 50),
        "power": random.randint(30, 50),
    }

def format_status(base: int, train: int, emoji: str, name: str):
    total = base + train
    return f"{emoji} {name} {total}({base}+{train})"


# =========================
# GIF duration helper
# =========================
GIF_DURATION_CACHE: dict[str, float] = {}

def get_gif_duration_seconds(path: str, fallback: float = 2.0) -> float:
    """
    GIFの総再生時間（1ループ分）を秒で返す。
    取得できない場合は fallback を返す。
    """
    if path in GIF_DURATION_CACHE:
        return GIF_DURATION_CACHE[path]

    try:
        with Image.open(path) as im:
            total_ms = 0
            n = getattr(im, "n_frames", 1)

            for i in range(n):
                im.seek(i)
                total_ms += int(im.info.get("duration", 100))  # ms（無い時の保険）

            sec = total_ms / 1000.0

            # 安全ガード：短すぎ/長すぎを抑制（好みで調整OK）
            sec = max(0.8, min(8.0, sec))

            GIF_DURATION_CACHE[path] = sec
            return sec

    except Exception as e:
        print(f"[WARN] get_gif_duration_seconds failed: {path} {e!r}")
        GIF_DURATION_CACHE[path] = fallback
        return fallback

# =========================
# 図鑑（Dex）関連
# =========================
# -------------------------
# 所持判定
# -------------------------
def get_owned_adults(data: dict, uid: str) -> set[str]:
    owned = set()
    for pet in data["users"].get(uid, {}).get("pets", []):
        if pet.get("stage") == "adult":
            owned.add(pet["adult_key"])
    return owned

# -------------------------
# idle.gif → 代表フレーム
# -------------------------
def load_idle_frame(path: str, size=(96, 96)) -> Image.Image:
    with Image.open(path) as im:
        frame = next(ImageSequence.Iterator(im)).convert("RGBA")
        return frame.resize(size)

# -------------------------
# 黒塗り（シルエット化）
# -------------------------
def make_silhouette(img: Image.Image) -> Image.Image:
    sil = img.copy()
    px = sil.load()

    for y in range(sil.height):
        for x in range(sil.width):
            r, g, b, a = px[x, y]
            if a > 0:
                px[x, y] = (0, 0, 0, a)

    return sil

# -------------------------
# タイル画像生成（核心）
# -------------------------
def build_dex_tile_image(adults: list[dict], owned: set[str]):
    cols = 5
    tile = 96
    pad = 16

    rows = (len(adults) + cols - 1) // cols
    w = cols * tile + (cols - 1) * pad
    h = rows * tile + (rows - 1) * pad

    canvas = Image.new("RGBA", (w, h), (30, 30, 30, 255))

    for i, a in enumerate(adults):
        x = (i % cols) * (tile + pad)
        y = (i // cols) * (tile + pad)

        path = os.path.join(
            ASSET_BASE,
            "adult",
            a["key"],
            "idle.gif"
        )
        img = load_idle_frame(path)

        if a["key"] not in owned:
            img = make_silhouette(img)

        canvas.paste(img, (x, y), img)

    from io import BytesIO
    buf = BytesIO()
    canvas.save(buf, "PNG")
    buf.seek(0)
    return buf

# -------------------------
# たまご表示関数
# -------------------------
def get_pet_display_name(pet: dict) -> str:
    """
    autocomplete / 表示用の名前
    ・成体 → pet["name"]
    ・たまご → 「🔴 あかいたまご」など
    """
    if pet.get("stage") == "adult":
        return pet.get("name", "おあしすっち")

    # たまご
    egg_type = pet.get("egg_type", "red")
    for key, label in EGG_COLORS:
        if key == egg_type:
            return label

    return "🥚 たまご"
# -------------------------
# 通知名前判定
# -------------------------
def get_pet_notify_name(pet: dict) -> str:
    """
    通知用のおあしすっち名
    例：
    ・🧬 やまだ
    ・🔴 あかいたまご
    """
    if pet.get("stage") == "adult":
        return f"🧬 {pet.get('name', 'おあしすっち')}"

    # たまご
    egg_type = pet.get("egg_type", "red")
    for key, label in EGG_COLORS:
        if key == egg_type:
            return label

    return "🥚 おあしすっち"
# -------------------------
# レーススコア計算
# -------------------------

def calc_race_score(stats: dict) -> float:
    """
    スピード重視、スタミナ補正、パワー少し
    """
    return (
        stats["speed"] * 1.0 +
        stats["stamina"] * 0.6 +
        stats["power"] * 0.4 +
        random.uniform(-5, 5)  # ブレ
    )
# -------------------------
# レースコンディション
# -------------------------  
def get_race_condition(happiness: int) -> tuple[str, str, int]:
    """
    幸福度からレースコンディションを返す
    return: (label, emoji, face_count)
    """
    happiness = max(0, min(100, int(happiness)))
    face_count = max(1, min(10, round(happiness / 10)))  # 😊1〜10

    if face_count == 10:
        return "絶好調", "✨🔥", face_count
    elif 7 <= face_count <= 9:
        return "良好", "😊", face_count
    elif 4 <= face_count <= 6:
        return "普通", "🙂", face_count
    else:
        return "不調", "😨", face_count
# -------------------------
# 順位決定
# -------------------------
def decide_race_order(pets: list[dict]):
    results = []

    for pet in pets:
        stats = calc_effective_stats(pet)
        score = calc_race_score(stats)

        results.append({
            "pet_id": pet["id"],
            "user_id": pet["user_id"],
            "name": pet["name"],
            "score": score,
            "stats": stats,                 # speed / stamina / power / guts
            "happiness": pet.get("happiness", 0),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# -------------------------
# レース予定関数
# -------------------------

def build_race_schedule_embed(schedules: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title="🗓 本日のレース予定",
        description="本日開催されるレース一覧です。",
        color=discord.Color.blue()
    )

    for s in schedules:
        embed.add_field(
            name=f"第{s['race_no']}レース（🕘 {s['race_time']}）",
            value=(
                f"🏁 距離：{s['distance']}\n"
                f"🏟 バ場：{s['surface']}\n"
                f"🌧 状態：{s['condition']}"
            ),
            inline=False
        )

    embed.set_footer(text="※ レース参加は各おあしすっちから行えます")
    return embed
# =========================
# Cog
# =========================
class OasistchiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self._race_lock = asyncio.Lock()

    async def cog_load(self):
        self.poop_check.start()
        self.race_tick.start()
        self.oasistchi_tick.start()

    async def cog_unload(self):
        self.poop_check.cancel()
        self.race_tick.cancel()
        self.oasistchi_tick.cancel()




    # =========================
    # レース結果
    # =========================
    def build_race_result_embed(self, race: dict, results: list[dict]) -> discord.Embed:
        embed = discord.Embed(
            title=f"🏁 第{race['race_no']}レース 結果発表！",
            description=f"{race['distance']}｜{race['surface']}｜{race['condition']}",
            color=discord.Color.gold()
        )

        medals = ["🥇", "🥈", "🥉"]

        for i, r in enumerate(results):
            medal = medals[i] if i < 3 else f"{i+1}位"

            stats = r["stats"]
            line = (
                f"**{medal} {r['name']}**\n"
                f"スコア：**{r['score']:.1f}**\n"
                f"🏃{stats['speed']} 🫀{stats['stamina']} 💥{stats['power']}\n"
                f"😊×{stats['guts_chance']}"
            )

            if stats["guts"]:
                line += " ｜🔥 **根性発動！**"

            embed.add_field(
                name="\u200b",
                value=line,
                inline=False
            )

        embed.set_footer(text="幸福度と根性が勝敗に影響します")
        return embed
    # =========================
    # 表示用 state 解決
    # =========================



    def resolve_pet_state(self, pet: dict, default: str = "idle") -> str:
        now = time.time()

        state = pet.get("display_state")
        until = pet.get("display_until", 0) or 0

        if state and now < until:
            return state

        if pet.get("poop"):
            return "poop"

        return default

    @tasks.loop(minutes=5)
    async def oasistchi_tick(self):
        if not self.bot.is_ready():
            return

        if self._race_lock.locked():
            return

        async with self._race_lock:
            pets = await self.db.get_all_oasistchi_pets()
            for pet in pets:
                try:
                    await self.process_time_tick(pet)
                except Exception as e:
                    print(f"[OASISTCHI TICK ERROR] pet_id={pet['id']} err={e}")


    async def trigger_race_daily_process(self):
        db = self.bot.db
        now = datetime.now(JST)
        today = now.date()

        # -------------------------
        # ① 今日のレース生成
        # -------------------------
        try:
            
            guild_id = str(self.bot.guilds[0].id)  # もしくは race["guild_id"] 等
            if not await db.has_today_race_schedules(today):
                await db.generate_today_races(guild_id, today)
                print(f"[RACE] {today} のレースを生成しました")
        except Exception as e:
            print(f"[RACE ERROR] generate failed: {e}")
            return

        # -------------------------
        # ② 抽選チェック
        # -------------------------
        races = await db.get_today_race_schedules(today)

        for race in races:
            if race.get("lottery_done") is True:
                continue

            race_time_raw = race["race_time"]

            # race_time が "HH:MM" 文字列の場合
            if isinstance(race_time_raw, str):
                h, m = map(int, race_time_raw.split(":"))
                race_time = dtime(hour=h, minute=m)
            else:
                race_time = race_time_raw

            entry_close = (
                datetime.combine(today, race_time, JST)
                - timedelta(minutes=race["entry_open_minutes"])
            )

            # ⛔ 締切前は抽選しない
            if now < entry_close:
                continue

            # 🔥 ここを必ず入れる
            pending_count = await db.conn.fetchval("""
                SELECT COUNT(*)
                FROM race_entries
                WHERE guild_id = $1
                  AND race_date = $2
                  AND schedule_id = $3
                  AND status = 'pending'
            """,
                str(race["guild_id"]),
                race["race_date"],
                race["id"],
            )

            # ⛔ pending が2未満なら抽選しない（中止処理もしない）
            if pending_count < 2:
                continue

            try:
                await self.run_race_lottery(race)
                await db.mark_race_lottery_done(race["id"])
                print(f"[RACE] 抽選完了 race_id={race['id']} selected={pending_count}")
            except Exception as e:
                print(f"[RACE ERROR] lottery failed: {e}")





    # =========================
    # レース処理（正規版・完成）
    # =========================
    async def send_race_result_embed(self, race: dict, results: list[dict]):
        channel = await self.get_race_result_channel()
        if channel is None:
            print("[RACE] result channel not found")
            return

        embed = discord.Embed(
            title=f"🏁 第{race['race_no']}レース 結果",
            description=(
                f"🕘 {race['race_time']}｜"
                f"{race['distance']}｜"
                f"{race['surface']}｜"
                f"{race['condition']}"
            ),
            color=discord.Color.gold()
        )

        medals = ["🥇", "🥈", "🥉"]

        for i, r in enumerate(results, start=1):
            medal = medals[i - 1] if i <= 3 else f"{i}着"
            guts = "🔥 根性" if r["stats"].get("guts") else ""

            embed.add_field(
                name=f"{medal} {r['name']}",
                value=(
                    f"<@{r['user_id']}>\n"
                    f"🏃 スピード {r['stats']['speed']}\n"
                    f"🫀 スタミナ {r['stats']['stamina']}\n"
                    f"💥 パワー {r['stats']['power']} {guts}\n"
                    f"📊 score {r['score']:.1f}"
                ),
                inline=False
            )

        await channel.send(embed=embed)

    # =========================
    # レース処理（正規版・完成）
    # =========================

    async def send_race_entry_panel(self, race: dict, selected_entries: list[dict]):
        """
        出走決定パネルをDiscordに送信する

        race: race_schedules の row(dict)
        selected_entries: status='selected' の race_entries
        """

        channel = await self.get_race_result_channel(race)
        if channel is None:
            print("[RACE] 出走決定チャンネルが見つかりません")
            return

        # 念のためシャッフル（＝枠番ランダム）
        entries = selected_entries[:]
        random.shuffle(entries)

        embed = discord.Embed(
            title=f"🏇 第{race['race_no']}レース 出走決定（{race['race_time']}）",
            description=(
                f"{race['distance']}｜{race['surface']}｜{race['condition']}\n"
                f"出走頭数：{len(entries)} / 8"
            ),
            color=discord.Color.green()
        )

        for frame_no, entry in enumerate(entries, start=1):
            # ペット取得
            pet = await self.db.get_oasistchi_pet(entry["pet_id"])
            if not pet:
                continue

            condition = self.get_condition_text(pet["happiness"])

            # ステータス（表示用）
            speed = pet["speed"]
            stamina = pet["stamina"]
            power = pet["power"]

            embed.add_field(
                name=f"【枠番 {frame_no}】🐣 {pet['name']}",
                value=(
                    f"👤 <@{entry['user_id']}>\n"
                    f"📉 コンディション：{condition}\n\n"
                    f"🏃 スピード：{speed}\n"
                    f"🫀 スタミナ：{stamina}\n"
                    f"💥 パワー：{power}"
                ),
                inline=False
            )

        embed.set_footer(text="このあとWebサイトでレースを観戦・投票できます")

        await channel.send(embed=embed)

    # =========================
    # ★ レース用チャンネル取得（追加）
    # =========================
    async def get_race_result_channel(self):
        channel = self.bot.get_channel(RACE_RESULT_CHANNEL_ID)
        if channel:
            return channel

        try:
            channel = await self.bot.fetch_channel(RACE_RESULT_CHANNEL_ID)
            return channel
        except Exception as e:
            print(f"[RACE] チャンネル取得失敗: {e}")
            return None
    
    # =========================
    # レース処理（正規版・完成） ※1本化版
    # =========================
    async def run_race_lottery(self, race: dict):
        async with self.db._lock:
            db = self.db
            race_id = race["id"]
            race_date = race["race_date"]
            guild_id = str(race["guild_id"])

            max_entries = int(race.get("max_entries", 8))
            entry_fee = int(race.get("entry_fee", 0))

            # ① 抽選対象は pending のみ
            entries = await db.conn.fetch("""
                SELECT *
                FROM race_entries
                WHERE race_date = $1
                 AND schedule_id = $2
                  AND status = 'pending'
            """, race_date, race_id)

            # 中止判定（pending 基準）
            if len(entries) < 2:
                for e in entries:
                    await db.update_race_entry_status(e["id"], "cancelled")
                    await db.refund_entry(e["user_id"], guild_id, entry_fee)
                print(f"[RACE] レース {race_id} 中止（参加1体以下）")
                return

            # ② 当日すでに出走確定(selected)の pet は除外
            already_selected = await db.get_today_selected_pet_ids(race_date)
            candidates = [e for e in entries if e["pet_id"] not in already_selected]

            # 有効候補が2未満なら中止（このレースで成立しない）
            if len(candidates) < 2:
                for e in entries:
                    await db.update_race_entry_status(e["id"], "cancelled")
                    await db.refund_entry(e["user_id"], guild_id, entry_fee)
                print(f"[RACE] レース {race_id} 中止（有効候補不足）")
                return

            # ③ 抽選（最大8体）
            winners = random.sample(candidates, k=min(max_entries, len(candidates)))
            winner_ids = {w["id"] for w in winners}

            selected = []
            cancelled = []

            # ④ status更新＋返金（落選者/除外者も返金）
            for e in entries:
                if e["id"] in winner_ids:
                    selected.append(e)
                    await db.update_race_entry_status(e["id"], "selected")
                    # 同じpetの同日別レース pending をキャンセル（保険）
                    await db.cancel_other_entries(e["pet_id"], race_date, race_id)
                else:
                    cancelled.append(e)
                    await db.update_race_entry_status(e["id"], "cancelled")
                    await db.refund_entry(e["user_id"], guild_id, entry_fee)

            print(f"[RACE] 抽選完了 race_id={race_id} selected={len(selected)} cancelled={len(cancelled)}")

            # =========================
            # ★ ここで DB から selected を取り直す
            # =========================
            selected = await db.conn.fetch("""
                SELECT *
                FROM race_entries
                WHERE race_date = $1
                  AND schedule_id = $2
                          AND status = 'selected'
            """, race_date, race_id)

            if len(selected) < 2:
                print("[RACE] selected が2体未満のため出走決定パネルを送信しません")
                return

            # ⑤ 出走決定パネル（Discord）
            await self.send_race_entry_panel(race, selected)

            # ⑥ 出走ペット取得
            pets = []
            for e in selected:
                pet = await db.get_oasistchi_pet(e["pet_id"])
                if pet:
                    pets.append(dict(pet))

            # ⑦ 順位決定
            results = decide_race_order(pets)

            # ⑧ 結果Embed（※ここで1回だけ送る）
            await self.send_race_result_embed(race, results)
            print("[RACE] run_race_lottery END")
            return


    # =========================
    # レース通知
    # =========================
    async def notify_race_result(self, race, selected, cancelled):
        channel = self.bot.get_channel(RACE_RESULT_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            title=f"🏁 第{race['race_no']}レース 抽選結果",
            description="出走が確定したおあしすっちはこちら！",
            color=discord.Color.gold()
        )

        lines = []
        for i, e in enumerate(selected, start=1):
            user = self.bot.get_user(int(e["user_id"]))
            mention = user.mention if user else f"<@{e['user_id']}>"
            lines.append(f"**第{i}ゲート** {mention} 🐣 ID:{e['pet_id']}")

        embed.add_field(name="出走メンバー", value="\n".join(lines), inline=False)
        await channel.send(embed=embed)
        
        # 落選者へDM（任意）
        for e in cancelled:
            try:
                user = self.bot.get_user(int(e["user_id"]))
                if user is None:
                    user = await self.bot.fetch_user(int(e["user_id"]))

                if user:
                    await user.send(
                        f"🏁 **第{race['race_no']}レース 落選のお知らせ**\n"
                        f"エントリーしたレースには落選しました。\n"
                        f"💰 参加費は返却されています。"
                    )
            except Exception as dm_err:
                print(f"[RACE DM ERROR] user_id={e['user_id']} err={dm_err!r}")

    


    # 共通：時間差分処理
    # =========================
    async def process_time_tick(self, pet: dict):
        now = time.time()
        db = self.bot.db
        updates: dict = {}

        uid = str(pet["user_id"])
        notify = await db.get_oasistchi_notify_settings(uid)  # Noneなら通知しない（孵化以外）
        # -------------------------
        # 通知設定：デフォルトON
        # -------------------------
        if notify is None:
            notify = {
                "notify_poop": True,
                "notify_food": True,
                "notify_pet_ready": True,
            }

        # 送信トリガー
        trigger_hatch = False
        trigger_poop = False
        trigger_hunger = False
        trigger_pet_ready = False

        # =========================
        # 予測値（updates反映後の値）で判定したいので helper
        # =========================
        def get_new(key, default=None):
            return updates.get(key, pet.get(key, default))

        # -------------------
        # 空腹度（2時間ごと / adult）
        # -------------------
        if pet["stage"] == "adult":
            elapsed = now - pet.get("last_hunger_tick", now)
            ticks = int(elapsed // 7200)
            if ticks > 0:
                new_hunger = max(0, pet.get("hunger", 100) - ticks * 10)
                updates["hunger"] = new_hunger
                updates["last_hunger_tick"] = now

        # -------------------
        # 幸福度ダウン（空腹度5以下で1時間ごと）
        # -------------------
        if pet["stage"] == "adult":
            hunger_after = int(
                updates.get("hunger", pet.get("hunger", 100))
            )

            if hunger_after <= 5:
                last_unhappy = pet.get("last_unhappy_tick", now)
                if last_unhappy is None:
                    last_unhappy = now

                elapsed = now - last_unhappy
                ticks = int(elapsed // 3600)  # 1時間ごと

                if ticks > 0:
                    base_happiness = int(
                        updates.get("happiness", pet.get("happiness", 50))
                    )
                    new_happiness = max(0, base_happiness - ticks * 2)

                    updates["happiness"] = new_happiness
                    updates["last_unhappy_tick"] = now


        # -------------------
        # うんち（1時間ごと）
        # -------------------
        next_check = pet.get("next_poop_check_at", 0)

        if now >= next_check and not pet.get("poop", False):
            chance = 0.4 if pet["stage"] == "adult" else 0.3

            if random.random() < chance:
                updates["poop"] = True
                trigger_poop = True
                updates["poop_notified_at"] = now

            # 次回チェックは必ず1時間後
            updates["next_poop_check_at"] = now + 3600

        # -------------------
        # 孵化成長（1時間単位）
        # -------------------
        if pet["stage"] == "egg":
            before = pet.get("growth", 0.0)
            after = before

            elapsed = now - pet.get("last_growth_tick", now)
            hours = int(elapsed // 3600)

            if hours > 0:
                rate = 100 / 12
                mult = 0.5 if get_new("poop", False) else 1.0
                gain = rate * hours * mult

                after = min(100.0, before + gain)
                updates["growth"] = after
                updates["last_growth_tick"] = now

            # 孵化通知（1回のみ・ON/OFF無関係）
            if before < 100.0 and after >= 100.0 and not pet.get("notified_hatch", False):
                trigger_hatch = True
                updates["notified_hatch"] = True

        # =========================
        # ここから通知系（状態変化ベース）
        # =========================

        # (1) 💩 うんち通知：poop が False→True になった瞬間（通知設定がある人だけ）
        poop_before = pet.get("poop", False)
        poop_after = bool(get_new("poop", poop_before))

        if poop_after and not poop_before:
            # うんち発生
            if not pet.get("poop_alerted", False):
                trigger_poop = True
                updates["poop_alerted"] = True

        # お世話で poop=False に戻ったら、次回また通知できるよう解除
        if (not poop_after) and pet.get("poop_alerted", False):
            updates["poop_alerted"] = False

        # (2) 🍖 空腹通知：hunger が 50以下になった瞬間（通知設定がある人だけ）
        if pet["stage"] == "adult":
            hunger_after = int(get_new("hunger", pet.get("hunger", 100)))

            if hunger_after <= 50 and not pet.get("hunger_alerted", False):
                trigger_hunger = True
                updates["hunger_alerted"] = True

            if hunger_after > 50 and pet.get("hunger_alerted", False):
                updates["hunger_alerted"] = False

        # (3) 🤚 なでなで通知：3時間CTが明けた瞬間（通知設定がある人だけ）
        pet_ready_at = pet.get("pet_ready_at", 0)
        pet_ready_notified_at = pet.get("pet_ready_notified_at", 0)

        if pet_ready_at > 0 and now >= pet_ready_at and pet_ready_notified_at < pet_ready_at:
            trigger_pet_ready = True
            updates["pet_ready_notified_at"] = now

        # =========================
        # DB更新
        # =========================
        if updates:
            await db.update_oasistchi_pet(pet["id"], **updates)

        # =========================
        # DM通知（DB更新後に送る）
        # =========================
        # fetch_user は失敗することがあるので try/except
        async def safe_dm(text: str):
            try:
                user_obj = await self.bot.fetch_user(int(uid))
                await user_obj.send(text)
            except:
                pass

        # 通知用の表示名を作る（ここで1回だけ）
        pet_name = get_pet_notify_name(pet)

        # A) 孵化通知：常に送る（1回のみ）
        if trigger_hatch:
            await safe_dm(
                f"🐣 **{pet_name}** が孵化できるよ！\n"
                "`/おあしすっち` で確認してね！"
            )

        # B) ON/OFF系：設定がある人だけ
        if trigger_poop and notify.get("notify_poop", False):
            await safe_dm(
                f"💩 **{pet_name}** がうんちしたよ！\n"
                "`/おあしすっち` でお世話してね！"
            )

        if trigger_hunger and notify.get("notify_food", False):
            await safe_dm(
                f"🍖 **{pet_name}** がおなかすいてるみたい…\n"
                "`/おあしすっち` でごはんをあげてね！"
            )

        if trigger_pet_ready and notify.get("notify_pet_ready", False):
            await safe_dm(
                f"🤚 **{pet_name}** をなでなでできるよ！\n"
                "`/おあしすっち` でなでなでしてあげてね！"
            )

    # -----------------------------
    # 管理者：パネル設置
    # -----------------------------
    @app_commands.command(name="おあしすっちパネル設置")
    async def panel_setup(
        self,
        interaction: discord.Interaction,
        title: str,
        body: str,
        egg_price: int,
        slot_price: int
    ):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        # =============================
        # ★ レース生成＋抽選トリガー
        # =============================
        await self.trigger_race_daily_process()

        # -----------------------------
        # パネル表示
        # -----------------------------
        embed = discord.Embed(
            title=title,
            description=body,
            color=discord.Color.orange()
        )

        view = OasistchiPanelRootView(
            egg_price=int(egg_price),
            slot_price=int(slot_price)
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        # -----------------------------
        # 初回トリガー：全ペット time_tick
        # -----------------------------
        pets = await self.bot.db.get_all_oasistchi_pets()

        for pet in pets:
            try:
                await self.process_time_tick(pet)
            except Exception as e:
                print(f"[OASISTCHI INIT TICK ERROR] pet_id={pet['id']} err={e}")

    # -----------------------------
    # ユーザー：おあしすっち表示（既存）
    # -----------------------------
    @app_commands.command(name="おあしすっち")
    @app_commands.describe(pet="表示したいおあしすっち")
    async def oasistchi(
        self,
        interaction: discord.Interaction,
        pet: str | None = None
    ):
        await interaction.response.defer(ephemeral=True)
        db = interaction.client.db
        uid = str(interaction.user.id)

        pets = await db.get_oasistchi_pets(uid)
        if not pets:
            return await interaction.followup.send(
                "まだおあしすっちを持っていません。",
                ephemeral=True
            )

        # pet は autocomplete 経由の「文字列ID」のみ許可
        if pet is not None:
            # 自分のペット一覧を先に取得
            my_pet_ids = {str(p["id"]) for p in pets}

            # プルダウン由来でない入力はすべて拒否
            if pet not in my_pet_ids:
                return await interaction.followup.send(
                    "❌ プルダウンから選択してください。",
                    ephemeral=True
                )

            pet_id = int(pet)
            pet = await db.get_oasistchi_pet(pet_id)

        else:
            pet = dict(pets[0])


        await self.process_time_tick(pet)

        # 最新状態を取り直す
        pet = await db.get_oasistchi_pet(pet["id"])

        embed = self.make_status_embed(pet)
        pet_file = self.get_pet_image(pet)
        gauge_file = build_growth_gauge_file(pet["growth"])
        view = CareView(uid, pet["id"], pet)

        await interaction.followup.send(
            embed=embed,
            view=view,
            files=[pet_file, gauge_file],
            ephemeral=True
        )

    def make_status_embed(self, pet: dict):
        name = pet.get("name", "おあしすっち")

        embed = discord.Embed(
            title=f"🐣 {name}",
            color=discord.Color.green()
        )

        embed.add_field(
            name="空腹度",
            value=gauge_emoji(pet.get("hunger", 100), emoji="🍗"),
            inline=False
        )

        embed.add_field(
            name="幸福度",
            value=gauge_emoji(pet.get("happiness", 100), emoji="😊"),
            inline=False
        )

        if pet["stage"] == "egg":
            embed.set_image(url="attachment://pet.gif")
            embed.set_thumbnail(url="attachment://growth.png")
            return embed

        # 🧬 成体のみステータス表示
        if pet["stage"] == "adult":
            stats_text = "\n".join([
                format_status(pet["base_speed"], pet["train_speed"], "🏃", "スピード"),
                format_status(pet["base_stamina"], pet["train_stamina"], "🫀", "スタミナ"),
                format_status(pet["base_power"], pet["train_power"], "💥", "パワー"),
            ])
            training_count = pet.get("training_count", 0)

            stats_text += f"\n\n🏋️ 特訓回数：{training_count} / 30"

            embed.add_field(
                name="📊 ステータス",
                value=stats_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📊 ステータス",
                value="🥚 孵化するとステータスが確認できます",
                inline=False
            )

        embed.set_image(url="attachment://pet.gif")
        embed.set_thumbnail(url="attachment://growth.png")

        return embed

    def get_pet_image(self, pet: dict, state: str = "idle"):
        state = self.resolve_pet_state(pet, state)

        if pet["stage"] == "adult":
            key = pet["adult_key"]
            path = os.path.join(ASSET_BASE, "adult", key, f"{state}.gif")
        else:
            egg = pet.get("egg_type", "red")
            path = os.path.join(ASSET_BASE, "egg", egg, f"{state}.gif")

        return discord.File(path, filename="pet.gif")

    @oasistchi.autocomplete("pet")
    async def oasistchi_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ):
        db = interaction.client.db
        uid = str(interaction.user.id)

        pets = await db.get_oasistchi_pets(uid)
        if not pets:
            return []

        # 同色卵の番号付け用
        egg_counter: dict[str, int] = {}
        adult_counter: dict[str, int] = {}

        choices = []

        for pet in pets:
            base_name = get_pet_display_name(pet)

            if pet.get("stage") == "egg":
                egg_type = pet.get("egg_type", "egg")
                egg_counter[egg_type] = egg_counter.get(egg_type, 0) + 1
                display = f"{base_name} #{egg_counter[egg_type]}"

            else:
                # 🧬 成体：名前ごとに連番
                name = pet.get("name", "おあしすっち")
                adult_counter[name] = adult_counter.get(name, 0) + 1
                display = f"🧬 {name} #{adult_counter[name]}"

            if current.lower() in display.lower():
                choices.append(
                    app_commands.Choice(
                        name=display,
                        value=str(pet["id"])   # ← 中身は常に pet_id（超重要）
                    )
                )

        return choices[:25]

    # -----------------------------
    # うんち抽選（60分）
    # -----------------------------
    @tasks.loop(minutes=10)
    async def poop_check(self):
        if not self.bot.is_ready():
            return

        db = self.bot.db
        pets = await db.get_all_oasistchi_pets()

        for pet in pets:
            await self.process_time_tick(pet)

    # -----------------------------
    # レース作成
    # -----------------------------

    @tasks.loop(minutes=1)
    async def race_tick(self):
        if not self.bot.is_ready():
            return

        async with self._race_lock:
            try:
                await self.trigger_race_daily_process()
            except Exception as e:
                print(f"[RACE TICK ERROR] {e!r}")


# =========================
# ボタンView
# =========================
class OasistchiPanelRootView(discord.ui.View):
    """
    全員に見える「入口」パネル
    ・たまご購入 → 押した人だけ購入UI（ephemeral）
    ・課金       → 押した人だけ課金UI（ephemeral）
    """
    def __init__(self, egg_price: int, slot_price: int):
        super().__init__(timeout=None)
        self.egg_price = egg_price
        self.slot_price = slot_price

    @discord.ui.button(label="🥚 たまご購入", style=discord.ButtonStyle.green,custom_id="oasistchi:open_buy")
    async def open_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EggSelectView(
            egg_price=self.egg_price,
            slot_price=self.slot_price
        )
        embed, file = view.build_panel_embed()

        await interaction.response.send_message(
            embed=embed,
            view=view,
            files=[file],
            ephemeral=True
        )

    @discord.ui.button(label="💳 課金", style=discord.ButtonStyle.primary,custom_id="oasistchi:open_charge")
    async def open_charge(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChargeSelectView(slot_price=self.slot_price)

        await interaction.response.send_message(
            "課金メニューを選択してください。",
            view=view,
            ephemeral=True
        )



    @discord.ui.button(label="🔔 通知設定", style=discord.ButtonStyle.secondary,custom_id="oasistchi:open_notify")
    async def open_notify(self, interaction, button):
        view = NotifySelectView()
        await interaction.response.send_message(
            "通知設定を選んでください。",
           view=view,
            ephemeral=True
        )

    @discord.ui.button(label="レース予定", style=discord.ButtonStyle.primary)
    async def show_race_schedule(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db

        today = get_today_jst_date()
        schedules = await db.get_today_race_schedules(today)
        
        if not schedules:
            return await interaction.followup.send(
                "本日のレース予定はまだ生成されていません。",
                ephemeral=True
            )

        schedules = [dict(s) for s in schedules]

        embed = build_race_schedule_embed(schedules)
        await interaction.followup.send(embed=embed, ephemeral=True)

# =========================
# プルダウン View
# =========================

class ChargeSelectView(discord.ui.View):
    def __init__(self, slot_price: int):
        super().__init__(timeout=60)
        self.slot_price = int(slot_price)
        self.add_item(ChargeSelect(self.slot_price))


class ChargeSelect(discord.ui.Select):
    def __init__(self, slot_price: int):
        self.slot_price = slot_price
        options = [
            discord.SelectOption(
                label="育成枠を1つ増築,6枠以降は200,000rrc",
                description=f"{slot_price} rrc",
                value="slot"
            ),
            discord.SelectOption(
                label="🧬 転生アイテム",
                description="個体値を再抽選（100,000rrc）",
                value="rebirth"
            ),
            discord.SelectOption(
                label="🏋️ 特訓リセット",
                description="特訓回数を0に戻す（50,000rrc）",
                value="train_reset"
            ),
            discord.SelectOption(
                label="🥚 かぶりなし たまご",
                description="未所持のみ孵化（300,000rrc）",
                value="unique_egg"
            ),
        ]
        super().__init__(
            placeholder="課金内容を選択",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        uid = str(interaction.user.id)

        # ① 育成枠
        if value == "slot":
            view = ConfirmPurchaseView(
                kind="slot",
                label="育成枠を増築",
                price=self.slot_price,
                egg_key=None,
                slot_price=self.slot_price
            )
            return await interaction.response.send_message(
                f"育成枠を **{self.slot_price:,} rrc** で増築しますか？",
                ephemeral=True,
                view=view
            )

        # ② 転生 / 特訓リセット
        elif value in ("rebirth", "train_reset"):
            price = 100_000 if value == "rebirth" else 50_000

            # ===== ① 成体おあしすっちを取得 =====
            pets = await interaction.client.db.get_oasistchi_pets(uid)

            options = [
                discord.SelectOption(
                    label=f"{p['name'] or 'ななし'}（ID:{p['id']}）",
                    value=str(p["id"])
                )
                for p in pets
                if p["stage"] == "adult"
            ]

            if not options:
                return await interaction.response.send_message(
                    "❌ 成体のおあしすっちがいません。",
                    ephemeral=True
                )

            # ===== ② options を渡して View を作る =====
            view = PaidPetSelectView(
                uid=uid,
                kind=value,
                price=price,
                slot_price=self.slot_price,
                options=options,   # ←★ここが超重要
            )

            return await interaction.response.send_message(
                "対象のおあしすっちを選択してください。",
                ephemeral=True,
                view=view
            )

        elif value == "unique_egg":
            view = ConfirmPurchaseView(
                kind="unique_egg",
                label="🥚 かぶりなし たまご",
                price=300_000,
                egg_key=None,
                slot_price=self.slot_price
            )

            return await interaction.response.send_message(
                "🥚 **かぶりなし たまご** を購入しますか？\n"
                "※ 未所持のおあしすっちのみが生まれます。",
                ephemeral=True,
                view=view
            )

class NotifySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(NotifySelect())

class NotifySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="なでなで・お世話・ごはん通知オン", value="on"),
            discord.SelectOption(label="なでなで・お世話・ごはん通知オフ", value="off"),
        ]
        super().__init__(
            placeholder="通知設定を選択",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        db = interaction.client.db
        uid = str(interaction.user.id)

        on = self.values[0] == "on"

        # pets取得（存在チェック）
        pets = await db.get_oasistchi_pets(uid)
        if not pets:
            return await interaction.response.send_message("おあしすっちを持っていません。", ephemeral=True)

        # 全ペットの通知を一括更新（DBメソッド作る）
        await db.set_oasistchi_notify_all(uid, on)

        await interaction.response.send_message(
            f"🔔 通知を **{'オン' if on else 'オフ'}** にしました。",
            ephemeral=True
        )
# =========================
# 購入パネル View
# =========================
class EggSelectView(discord.ui.View):
    """
    ⬅➡ でたまご切替
    購入で 1匹登録
    課金で 育成枠増築（確認付き）
    """
    def __init__(self, egg_price: int, slot_price: int):
        super().__init__(timeout=60)  # ephemeralなら60推奨
        self.egg_price = int(egg_price)
        self.slot_price = int(slot_price)
        self.index = 0

    def current(self) -> dict:
        return EGG_CATALOG[self.index]

    def build_panel_embed(self) -> tuple[discord.Embed, discord.File]:
        egg = self.current()

        embed = discord.Embed(
            title="たまご購入",
            description=(
                f"**選択中：{egg['name']}**\n"
                f"たまご価格：**{self.egg_price} rrc**\n\n"
                "⬅➡でたまごを切り替えて購入してね。"
            ),
            color=discord.Color.orange()
        )

        embed.set_image(url="attachment://egg_icon.png")
        file = discord.File(egg["icon"], filename="egg_icon.png")
        return embed, file

    async def refresh(self, interaction: discord.Interaction):
        embed, file = self.build_panel_embed()
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    # -------- buttons --------
    @discord.ui.button(label="⬅", style=discord.ButtonStyle.gray)
    async def left(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(EGG_CATALOG)
        await self.refresh(interaction)

    @discord.ui.button(label="➡", style=discord.ButtonStyle.gray)
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(EGG_CATALOG)
        await self.refresh(interaction)

    @discord.ui.button(label="購入", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 購入確認（ephemeral）→ OKなら確定
        egg = self.current()
        view = ConfirmPurchaseView(
            kind="egg",
            label=f"{egg['name']} を購入",
            price=self.egg_price,
            egg_key=egg["key"],
            slot_price=self.slot_price
        )
        await interaction.response.send_message(
            f"**{egg['name']}** を **{self.egg_price}** で購入しますか？",
            ephemeral=True,
            view=view
        )

# =========================
# Confirm View（購入 / 増築）
# =========================
class ConfirmPurchaseView(discord.ui.View):
    def __init__(self, kind: str, label: str, price: int, egg_key: str | None, slot_price: int):
        super().__init__(timeout=60)
        self.kind = kind            # "egg" or "slot"
        self.label = label
        self.price = int(price)
        self.egg_key = egg_key
        self.slot_price = slot_price
        self._confirmed = False

    @discord.ui.button(label="購入する", style=discord.ButtonStyle.green)
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self._confirmed:
            return
        self._confirmed = True

        await interaction.response.defer(ephemeral=True)

        bot = interaction.client
        user = interaction.user
        guild = interaction.guild
        uid = str(user.id)
        gid = str(guild.id)

        if guild is None:
            return await interaction.edit_original_response(
                content="❌ サーバー内でのみ購入できます。",
                view=None
            )

        db = bot.db

        try:
            # =========================
            # 🥚 通常たまご
            # =========================
            if self.kind == "egg":
                pets = await db.get_oasistchi_pets(uid)
                user_row = await db.get_oasistchi_user(uid)

                if len(pets) >= user_row["slots"]:
                    return await interaction.edit_original_response(
                        content="❌ 育成枠がいっぱいです。",
                        view=None
                    )

                await db.purchase_oasistchi_egg_safe(
                    user_id=uid,
                    guild_id=gid,
                    egg_type=self.egg_key or "red",
                    price=self.price
                )

                unit = (await db.get_settings())["currency_unit"]

                return await interaction.edit_original_response(
                    content=(
                        f"✅ **たまごを購入しました！**\n"
                        f"消費: **{self.price:,} {unit}**\n"
                        "`/おあしすっち` で確認できます"
                    ),
                    view=None
                )

            # =========================
            # 🧺 育成枠
            # =========================
            elif self.kind == "slot":
                new_slots = await db.purchase_oasistchi_slot_safe(
                    user_id=uid,
                    guild_id=gid,
                    base_price=self.slot_price,
                    max_slots=10
                )

                unit = (await db.get_settings())["currency_unit"]

                return await interaction.edit_original_response(
                    content=(
                        "✅ **育成枠を1つ増築しました！**\n"
                        f"現在の育成枠: **{new_slots} / 10**\n"
                        f"消費: **{self.slot_price:,} {unit}**"
                    ),
                    view=None
                )

            # =========================
            # 🥚 かぶりなし
            # =========================
            elif self.kind == "unique_egg":

                # -------------------------
                # 育成枠チェック
                # -------------------------
                pets = await db.get_oasistchi_pets(uid)
                user_row = await db.get_oasistchi_user(uid)

                if len(pets) >= user_row["slots"]:
                    return await interaction.edit_original_response(
                        content="❌ 育成枠がいっぱいです。先にお別れするか、育成枠を増やしてください。",
                        view=None
                    )



                adult, egg_type = await db.purchase_unique_egg_safe(
                    user_id=uid,
                    guild_id=gid,
                    price=self.price,
                    adult_catalog=ADULT_CATALOG
                )

                return await interaction.edit_original_response(
                    content=(
                        "🥚 **かぶりなし たまごを入手しました！**\n"
                        "このたまごからは、未所持のおあしすっちが必ず生まれます。\n"
                        "`/おあしすっち` で確認してください。"
                    ),
                    view=None
                )

            # =========================
            # 保険
            # =========================
            else:
                return await interaction.edit_original_response(
                    content="❌ 不明な購入種別です。",
                    view=None
                )

        except Exception as e:
            print("[PURCHASE ERROR]", repr(e))
            return await interaction.edit_original_response(
                content=f"❌ エラーが発生しました：{e}",
                view=None
            )     
# =========================
# お世話ボタン（既存そのまま）
# =========================
class CareView(discord.ui.View):
    def __init__(self, uid: str, pet_id: int, pet: dict):
        super().__init__(timeout=None)
        self.uid = uid
        self.pet_id = pet_id
        self.pet = pet

        for child in list(self.children):
            label = getattr(child, "label", "")

            # 🥚 たまごのときに隠す
            if pet["stage"] == "egg" and label in {
                "🍖 ごはん",
                "🏁 レース参加",
                "💔 お別れ",
                "🏋️ 特訓",      # ← 特訓ボタン想定
            }:
                self.remove_item(child)

            # 🧬 成体のとき孵化は隠す
            if pet["stage"] == "adult" and label == "🐣 孵化":
                self.remove_item(child)

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.uid

    @discord.ui.button(label="なでなで", style=discord.ButtonStyle.primary)
    async def pet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        await interaction.response.defer()
        db = interaction.client.db
        pet = await db.get_oasistchi_pet(self.pet_id)
        now = now_ts()

        # ④ クールタイム判定（defer後は followup を使う）
        # if now - pet.get("last_pet", 0) < 10800:
        #     await interaction.followup.send(
        #         "まだなでなでできません。（3時間クールタイム）",
        #         ephemeral=True
        #     )
        #     return

        # ⑤ ステータス更新
        new_happiness = min(100, pet["happiness"] + 10)
        new_growth = min(100.0, pet["growth"] + 5.0)

        await db.update_oasistchi_pet(
            self.pet_id,
            happiness=new_happiness,
            growth=new_growth,
            last_pet=now,
            pet_ready_at=now + 10800,      # ← 次になでなで可能な時刻
            pet_ready_notified_at=0,       # ← 通知リセット
            last_interaction=now,
            last_unhappy_tick=now,
        )
        pet = await db.get_oasistchi_pet(self.pet_id)

        # ⑥ いったん pet.gif を表示（元メッセージ編集）
        cog = interaction.client.get_cog("OasistchiCog")
        egg = pet.get("egg_type", "red")

        embed = cog.make_status_embed(pet)
        pet_file = get_pet_file(pet, "pet")
        gauge_file = build_growth_gauge_file(pet["growth"])

        # defer後なので edit_original_response を使う
        await interaction.edit_original_response(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

        # ⑦ GIF時間待つ
        pet_gif_path = os.path.join(ASSET_BASE, "egg", egg, "pet.gif")
        wait_seconds = get_gif_duration_seconds(pet_gif_path, fallback=2.0)
        await asyncio.sleep(wait_seconds)

        pet = await db.get_oasistchi_pet(self.pet_id)



        # ⑧ idle に戻す（また元メッセージ編集）
        embed = cog.make_status_embed(pet)
        cog = interaction.client.get_cog("OasistchiCog")
        pet_file = cog.get_pet_image(pet, "idle")
        
        gauge_file = build_growth_gauge_file(pet["growth"])

        await interaction.edit_original_response(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

    @discord.ui.button(label="お世話", style=discord.ButtonStyle.success)
    async def care(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )
        db = interaction.client.db
        pet = await db.get_oasistchi_pet(self.pet_id)
        now = now_ts()

        if not pet.get("poop"):
            return await interaction.response.send_message(
                "今はお世話しなくて大丈夫！",
                ephemeral=True
            )

        # -------------------------
        # うんち処理
        # -------------------------
        new_happiness = min(100, pet["happiness"] + 5)

        await db.update_oasistchi_pet(
            self.pet_id,
            poop=False,
            happiness=new_happiness,
            next_poop_check_at=now + 3600,  
            poop_notified_at=0,
            last_interaction=now,
            last_unhappy_tick=now,
        )

        cog = interaction.client.get_cog("OasistchiCog")
        egg = pet.get("egg_type", "red")
        pet = await db.get_oasistchi_pet(self.pet_id)

        # -------------------------
        # ① clean.gif を表示（メインメッセージ編集）
        # -------------------------
        embed = cog.make_status_embed(pet)
        pet_file = get_pet_file(pet, "clean")
        gauge_file = build_growth_gauge_file(pet["growth"])

        await interaction.response.edit_message(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

        # （任意）ephemeralで通知したいなら followup を使う
        await interaction.followup.send("🧹 きれいにしました！", ephemeral=True)

        # -------------------------
        # ② clean.gif の長さだけ待つ
        # -------------------------
        clean_gif_path = os.path.join(ASSET_BASE, "egg", egg, "clean.gif")
        wait_seconds = get_gif_duration_seconds(clean_gif_path, fallback=2.0)
        await asyncio.sleep(wait_seconds)
        pet = await db.get_oasistchi_pet(self.pet_id)

        # -------------------------
        # ③ idle に戻す
        # -------------------------
        embed = cog.make_status_embed(pet)
        cog = interaction.client.get_cog("OasistchiCog")
        pet_file = cog.get_pet_image(pet, "idle")
        gauge_file = build_growth_gauge_file(pet["growth"])

        await interaction.edit_original_response(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

    @discord.ui.button(label="🍖 ごはん", style=discord.ButtonStyle.success)
    async def feed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        db = interaction.client.db
        pet = await db.get_oasistchi_pet(self.pet_id)

        if pet["stage"] != "adult":
            return await interaction.response.send_message(
                "まだごはんは食べられません。",
                ephemeral=True
            )

        if pet.get("hunger", 100) >= 100:
            return await interaction.response.send_message(
                "🍖 いまはおなかいっぱいみたい。",
                ephemeral=True
            )

        await interaction.response.defer()

        await db.update_oasistchi_pet(
            self.pet_id,
            hunger=100,
            last_interaction=now_ts(),
        )

        cog = interaction.client.get_cog("OasistchiCog")

        # ------------------
        # eat.gif 表示
        # ------------------
        embed = cog.make_status_embed(pet)

        await interaction.edit_original_response(
            embed=embed,
            attachments=[
                get_pet_file(pet, "eat"),
                build_growth_gauge_file(pet["growth"]),
            ],
            view=self
        )

        eat_path = os.path.join(
            ASSET_BASE, "adult", pet["adult_key"], "eat.gif"
        )
        await asyncio.sleep(get_gif_duration_seconds(eat_path, 2.0))

        # ------------------
        # idle に戻す（★必ず作り直す）
        # ------------------
        embed = cog.make_status_embed(pet)

        await interaction.edit_original_response(
            embed=embed,
            attachments=[
                get_pet_file(pet, "idle"),
                build_growth_gauge_file(pet["growth"]),
            ],
            view=self
        )
    @discord.ui.button(label="🧠 特訓", style=discord.ButtonStyle.primary)
    async def training(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        pet = await interaction.client.db.get_oasistchi_pet(self.pet_id)

        # 成体のみ
        if pet["stage"] != "adult":
            return await interaction.response.send_message(
                "❌ 特訓できるのは成体のみです。",
                ephemeral=True
            )

        view = TrainingView(self.pet_id) 
        await interaction.response.send_message(
            "🏋️ どのステータスを特訓しますか？\n選択後「決定」を押してください。",
            view=view,
            ephemeral=True
        )
    @discord.ui.button(label="🔄 更新", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        pet = await interaction.client.db.get_oasistchi_pet(self.pet_id)
        cog = interaction.client.get_cog("OasistchiCog")

        embed = cog.make_status_embed(pet)
        cog = interaction.client.get_cog("OasistchiCog")
        pet_file = cog.get_pet_image(pet, "idle")
        
        gauge_file = build_growth_gauge_file(pet["growth"])

        await interaction.response.edit_message(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

    @discord.ui.button(label="🐣 孵化", style=discord.ButtonStyle.success)
    async def hatch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        db = interaction.client.db
        pet = await db.get_oasistchi_pet(self.pet_id)

        if pet["stage"] != "egg" or pet["growth"] < 100.0:
            return await interaction.response.send_message(
                "まだ孵化できません。",
                ephemeral=True
            )

        egg_type = pet["egg_type"]

        candidates = [
            a for a in ADULT_CATALOG
            if egg_type in a["groups"]
        ]

        if not candidates:
            return await interaction.response.send_message(
                "このたまごに対応する成体が登録されていません。",
                ephemeral=True
            )

        # ★ここが重要
        if pet.get("fixed_adult_key"):
            adult = next(
                a for a in ADULT_CATALOG
                if a["key"] == pet["fixed_adult_key"]
            )
        else:
            adult = random.choice(candidates)

        hatch_gif = os.path.join(ASSET_BASE, "egg", pet["egg_type"], "hatch.gif")
        await interaction.response.defer()
        # ② 孵化GIFを表示
        await interaction.edit_original_response(
            content="✨ 孵化中…！",
            attachments=[discord.File(hatch_gif, filename="pet.gif")],
            view=None
        )

        # ③ GIFの長さだけ待つ
        await asyncio.sleep(get_gif_duration_seconds(hatch_gif, 3.0))
        now = now_ts()
        # -------------------------
        # ステータス初期値生成（孵化時のみ）
        # -------------------------
        stats = generate_initial_stats()
        await db.update_oasistchi_pet(
            self.pet_id,
            stage="adult",
            adult_key=adult["key"],
            name=adult["name"],

            base_speed=stats["speed"],
            base_stamina=stats["stamina"],
            base_power=stats["power"],

            train_speed=0,
            train_stamina=0,
            train_power=0,
            
            training_count=0,

            growth=0.0,
            hunger=100,
            poop=False,
            last_hunger_tick=now,
            last_unhappy_tick=now,
            last_interaction=now,
        )
        pet = await db.get_oasistchi_pet(self.pet_id)
        await db.add_oasistchi_dex(
             self.uid,
             adult["key"]
         )


        cog = interaction.client.get_cog("OasistchiCog")
        embed = cog.make_status_embed(pet)
        cog = interaction.client.get_cog("OasistchiCog")
        pet_file = cog.get_pet_image(pet, "idle")
        
        gauge_file = build_growth_gauge_file(pet["growth"])

        await interaction.edit_original_response(
            content=None,
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

    @discord.ui.button(label="📘 図鑑", style=discord.ButtonStyle.secondary)
    async def open_dex(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db
        uid = str(interaction.user.id)

        owned_keys = await db.get_oasistchi_owned_adult_keys(uid)  # ←DBメソッド
        if owned_keys is None:
            owned_keys = []

        owned = set(owned_keys)

        image = build_dex_tile_image(ADULT_CATALOG, owned)

        embed = discord.Embed(
            title="📘 おあしすっち図鑑",
            description=f"所持数：{len(owned)} / {len(ADULT_CATALOG)}",
            color=discord.Color.blurple()
        )
        embed.set_image(url="attachment://dex.png")

        await interaction.followup.send(
            embed=embed,
            file=discord.File(image, filename="dex.png"),
            ephemeral=True
        )

    @discord.ui.button(label="🏁 レース参加", style=discord.ButtonStyle.danger)
    async def race_entry(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        if not self.is_owner(interaction):
            return await interaction.followup.send(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        db = interaction.client.db
        pet = self.pet

        # ★ 今日のレース予定を取得
        today = get_today_jst_date()
        schedules = await db.get_today_race_schedules(today)

        if not schedules:
            return await interaction.followup.send(
                "本日のレース予定がありません。",
                ephemeral=True
            )

        condition, condition_emoji, face_count = get_race_condition(
            pet.get("happiness", 0)
        )

        ENTRY_FEE = 0

        embed = discord.Embed(
            title="🏁 レース出走確認",
            description="この状態でレースに出走しますか？",
            color=discord.Color.red()
        )

        embed.add_field(
            name="🐣 参加おあしすっち",
            value=f"**{pet['name']}**",
            inline=False
        )

        embed.add_field(
            name="🧠 コンディション",
            value=f"{condition_emoji} **{condition}**（😊×{face_count}）",
            inline=False
        )

        embed.add_field(
            name="💰 参加費",
            value=f"{ENTRY_FEE:,}",
            inline=False
        )

        view = RaceEntryConfirmView(
            pet=pet,
            entry_fee=ENTRY_FEE,
            schedules=schedules
        )

        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )

# =========================
# お別れビュー
# =========================

    @discord.ui.button(label="💔 お別れ", style=discord.ButtonStyle.danger)
    async def farewell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
           return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        await interaction.response.send_message(
            "本当にお別れしますか？\nこの操作は取り消せません。",
            ephemeral=True,
            view=FarewellConfirmView(self.pet_id)
        )


class FarewellConfirmView(discord.ui.View):
    def __init__(self, pet_id: int):
        super().__init__(timeout=30)
        self.pet_id = pet_id

    @discord.ui.button(label="はい、お別れする", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db

        await db.delete_oasistchi_pet(self.pet_id)

        await interaction.response.edit_message(
            content="🌱 おあしすっちは旅立っていきました…",
            view=None
        )

    @discord.ui.button(label="やっぱりやめる", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="キャンセルしました。",
            view=None
        )

class TrainingSelectView(discord.ui.View):
    def __init__(self, pet_id: int):
        super().__init__(timeout=60)
        self.pet_id = pet_id
        self.add_item(TrainingSelect(pet_id))

class TrainingSelect(discord.ui.Select):
    def __init__(self, pet_id: int):
        self.pet_id = pet_id

        options = [
            discord.SelectOption(label="🏃 スピード", value="speed"),
            discord.SelectOption(label="🫀 スタミナ", value="stamina"),
            discord.SelectOption(label="💥 パワー", value="power"),
        ]

        super().__init__(
            placeholder="特訓するステータスを選択",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        db = interaction.client.db
        pet = await db.get_oasistchi_pet(self.pet_id)

        # 🏋️ 特訓回数制限（30回）
        if pet.get("training_count", 0) >= 30:
            return await interaction.response.send_message(
                "🏋️ このおあしすっちはもう十分に特訓したようだ…",
                ephemeral=True
            )

        stat = self.values[0]

        # 🎲 特訓結果抽選（上限なし）
        gain, text = random.choice(TRAIN_RESULTS)

        # DB反映
        await db.update_oasistchi_pet(
            self.pet_id,
            **{
                f"train_{stat}": pet.get(f"train_{stat}", 0) + gain,
                "training_count": pet.get("training_count", 0) + 1,
            }
        )

        await interaction.response.send_message(
            f"{text}\n**{stat} +{gain}**\n"
            f"🏋️ 特訓回数：{pet.get('training_count', 0) + 1} / 30",
            ephemeral=True
        )


class OasisBot(commands.Bot):
    async def setup_hook(self):
        # 永続Viewを登録
        self.add_view(
            OasistchiPanelRootView(
                egg_price=0,   # ← 実際の値は使われない
                slot_price=0
            )
        )

class TrainingView(discord.ui.View):
    def __init__(self, pet_id: int):
        super().__init__(timeout=60)
        self.pet_id = pet_id
        self.selected_stat: str | None = None

        self.add_item(TrainingSelect(self))
        self.add_item(TrainingConfirmButton(self))

class TrainingSelect(discord.ui.Select):
    def __init__(self, view: TrainingView):
        self.view_ref = view

        options = [
            discord.SelectOption(label="🏃 スピード", value="speed"),
            discord.SelectOption(label="🫀 スタミナ", value="stamina"),
            discord.SelectOption(label="💥 パワー", value="power"),
        ]

        super().__init__(
            placeholder="特訓するステータスを選択",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.selected_stat = self.values[0]

        await interaction.response.send_message(
            f"✅ **{self.values[0]}** を特訓対象に選びました。\n"
            "下の「決定」ボタンを押してください。",
            ephemeral=True
        )

class TrainingConfirmButton(discord.ui.Button):
    def __init__(self, view: TrainingView):
        super().__init__(
            label="🏋️ 決定",
            style=discord.ButtonStyle.success
        )
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if not self.view_ref.selected_stat:
            return await interaction.response.send_message(
                "❌ 先に特訓するステータスを選んでください。",
                ephemeral=True
            )

        db = interaction.client.db
        pet = await db.get_oasistchi_pet(self.view_ref.pet_id)

        # 特訓回数制限
        if pet.get("training_count", 0) >= 30:
            return await interaction.response.send_message(
                "🏋️ このおあしすっちはもう十分に特訓したようだ…",
                ephemeral=True
            )

        stat = self.view_ref.selected_stat
        gain, text = random.choice(TRAIN_RESULTS)

        await db.update_oasistchi_pet(
            self.view_ref.pet_id,
            **{
                f"train_{stat}": pet.get(f"train_{stat}", 0) + gain,
                "training_count": pet.get("training_count", 0) + 1,
            }
        )

        await interaction.response.send_message(
            f"{text}\n"
            f"**{stat} +{gain}**\n"
            f"🏋️ 特訓回数：{pet.get('training_count', 0) + 1} / 30",
            ephemeral=True
        )
    # -----------------------------------------
    # 課金要素
    # -----------------------------------------
class PaidPetSelectView(discord.ui.View):
    def __init__(
        self,
        uid: str,
        kind: str,
        price: int,
        slot_price: int,
        options: list[discord.SelectOption] 
    ):
        super().__init__(timeout=60)
        self.uid = uid
        self.kind = kind
        self.price = price
        self.slot_price = slot_price

        self.add_item(PaidPetSelect(self, options))

class PaidPetSelect(discord.ui.Select):
    def __init__(
        self,
        view: "PaidPetSelectView",
        options: list[discord.SelectOption]
    ):
        self.view_ref = view
        super().__init__(
            placeholder="対象のおあしすっちを選択",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        pet_id = self.values[0]

        view = PaidPetConfirmView(
            uid=self.view_ref.uid,
            pet_id=int(pet_id),
            kind=self.view_ref.kind,
            price=self.view_ref.price,
            slot_price=self.view_ref.slot_price
        )

        label = "🧬 転生" if self.view_ref.kind == "rebirth" else "🏋️ 特訓リセット"

        await interaction.response.send_message(
            f"{label} を実行しますか？\nこの操作は取り消せません。",
            ephemeral=True,
            view=view
        )
class PaidPetConfirmView(discord.ui.View):
    """
    課金ペット最終確認View
    ・転生（baseステ再抽選）
    ・特訓リセット（trainステ＆回数リセット）
    """
    def __init__(
        self,
        uid: str,
        pet_id: int,
        kind: str,
        price: int,
        slot_price: int
    ):
        super().__init__(timeout=30)
        self.uid = uid
        self.pet_id = pet_id
        self.kind = kind            # "rebirth" or "train_reset"
        self.price = price
        self.slot_price = slot_price
        self._confirmed = False     # 二重実行防止

    # ---------------------------------
    # 実行
    # ---------------------------------
    @discord.ui.button(label="✅ 実行する", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self._confirmed:
            return await interaction.response.send_message(
                "すでに処理済みです。",
                ephemeral=True
            )

        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message(
                "❌ この操作はあなたのものではありません。",
                ephemeral=True
            )

        self._confirmed = True
        button.disabled = True
        await interaction.response.edit_message(view=self)

        db = interaction.client.db
        guild = interaction.guild
        gid = str(guild.id)
        uid = self.uid

        # -------------------------
        # 残高チェック
        # -------------------------
        settings = await db.get_settings()
        unit = settings["currency_unit"]

        user_row = await db.get_user(uid, gid)
        balance = user_row["balance"]

        if balance < self.price:
            return await interaction.followup.send(
                f"❌ 残高が足りません。\n"
                f"現在: **{balance:,} {unit}** / 必要: **{self.price:,} {unit}**",
                ephemeral=True
            )

        # -------------------------
        # ペット取得・所有確認
        # -------------------------
        pet = await db.get_oasistchi_pet(self.pet_id)

        if not pet or str(pet["user_id"]) != uid:
            return await interaction.followup.send(
                "❌ 対象のおあしすっちが見つかりません。",
                ephemeral=True
            )

        if pet["stage"] != "adult":
            return await interaction.followup.send(
                "❌ 成体のおあしすっちのみ使用できます。",
                ephemeral=True
            )

        # -------------------------
        # 課金（ここで1回だけ）
        # -------------------------
        await db.remove_balance(uid, gid, self.price)

        # -------------------------
        # 処理分岐
        # -------------------------
        if self.kind == "rebirth":
            stats = generate_initial_stats()

            await db.update_oasistchi_pet(
                self.pet_id,
                base_speed=stats["speed"],
                base_stamina=stats["stamina"],
                base_power=stats["power"],
            )

            await interaction.followup.send(
                f"🧬 **転生完了！**\n"
                f"🐣 **{pet['name']}** の個体値が再抽選されました。\n\n"
                f"🏃 {stats['speed']} / 🫀 {stats['stamina']} / 💥 {stats['power']}",
                ephemeral=True
            )
            return

        if self.kind == "train_reset":
            await db.update_oasistchi_pet(
                self.pet_id,
                train_speed=0,
                train_stamina=0,
                train_power=0,
                training_count=0,
            )

            await interaction.followup.send(
                f"🏋️ **特訓リセット完了！**\n"
                f"🐣 **{pet['name']}** は再び特訓できるようになりました。\n"
                f"🏋️ 特訓回数：0 / 30",
                ephemeral=True
            )
            return

        # 保険
        await interaction.followup.send(
            "❌ 不明な課金処理です。",
            ephemeral=True
        )

    # ---------------------------------
    # キャンセル
    # ---------------------------------
    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="操作をキャンセルしました。",
            view=None
        )

        # レース
class RaceEntryConfirmView(discord.ui.View):
    def __init__(self, pet: dict, entry_fee: int, schedules: list[dict]):
        super().__init__(timeout=120)

        self.pet = pet
        self.entry_fee = entry_fee
        self.schedules = schedules

        self.selected_race: dict | None = None
        self._confirmed = False  # 二重押し防止

        self.add_item(RaceSelect(self, schedules))

    # -----------------------------------------
    # ✅ エントリー確定
    # -----------------------------------------
    @discord.ui.button(label="✅ エントリー確定", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        # レース未選択防止
        if not self.selected_race:
            return await interaction.response.send_message(
                "❌ レースを選択してください。",
                ephemeral=True
           )

       # ★ ここでボタンを無効化
        button.disabled = True
        await interaction.response.edit_message(view=self)


        db = interaction.client.db
        pet = self.pet
        race = self.selected_race

        schedule_id = race["id"]
        race_date = race["race_date"]
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        # ① 同一レースに同一ユーザーが既にエントリーしていないか
        if await db.has_user_entry_for_race(schedule_id, uid):
            return await interaction.followup.send(
                "❌ このレースにはすでにエントリーしています。",
                ephemeral=True
            )

        # ② 同一ユーザーが本日すでに出走確定していないか
        if await db.has_user_selected_today(uid, race_date):
            return await interaction.followup.send(
                "❌ 本日はすでに別のレースに出走しています。",
                ephemeral=True
            )

        # ③ エントリー保存（pending）
        guild_id = str(interaction.guild.id)

        await db.insert_race_entry(
            schedule_id=schedule_id,
            guild_id=guild_id,
            user_id=str(interaction.user.id),
            pet_id=self.pet["id"],
            race_date=race_date,
            entry_fee=50000,   # race_schedules と同じ値
            paid=True
        )
        await db.remove_balance(uid, guild_id, self.entry_fee)

        # ④ 同一おあしすっちの他レースエントリーを無効化
        await db.cancel_other_entries(
            pet_id=pet["id"],
            race_date=race_date,
            exclude_schedule_id=schedule_id
        )

        # ⑤ 完了通知
        await interaction.followup.send(
            f"🏁 **レースエントリー完了！**\n"
            f"🐣 **{pet['name']}** が\n"
            f"🕘 **{race['race_time']} のレース** にエントリーしました。",
            ephemeral=True
        )

        self.stop()

    # =========================
    # キャンセル
    # =========================
    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("操作をキャンセルしました。", ephemeral=True)
        self.stop()

class RaceSelect(discord.ui.Select):
    def __init__(self, parent_view: RaceEntryConfirmView, schedules: list[dict]):
        self.parent_view = parent_view

        options = [
            discord.SelectOption(
                label=f"第{r['race_no']}レース {r['race_time']}",
                description=f"{r['distance']}｜{r['surface']}｜{r['condition']}",
                value=str(r["id"])
            )
            for r in schedules
        ]

        super().__init__(
            placeholder="参加するレースを選択",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        race_id = int(self.values[0])
        race = next(r for r in self.parent_view.schedules if r["id"] == race_id)

        self.parent_view.selected_race = race

        await interaction.response.send_message(
            f"🗓 **第{race['race_no']}レース（{race['race_time']}）** を選択しました。",
            ephemeral=True
        )




async def setup(bot):
    cog = OasistchiCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))










































