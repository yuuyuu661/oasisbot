import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
import os
import random
import hmac
import hashlib
from PIL import Image
from io import BytesIO
import asyncio
from PIL import Image, ImageSequence
from datetime import datetime, timezone, timedelta, time as dtime
from db import PASSIVE_SKILLS
JST = timezone(timedelta(hours=9))
import traceback

WEB_SECRET = "9f3a7c4d8b2e1f0a6c8d9e7f1a2b3c4d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4"

def today_jst_date():
    return datetime.now(JST).date()
def get_today_jst_date():
    JST = timezone(timedelta(hours=9))
    """JST基準の今日の日付を返す"""
    return datetime.now(JST).date()

def today_jst_str() -> str:
    JST = timezone(timedelta(hours=9))
    return datetime.now(JST).strftime("%Y-%m-%d")

def generate_token(user_id: int, guild_id: int, race_id: int):
    message = f"{user_id}:{guild_id}:{race_id}"
    return hmac.new(
        WEB_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

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
    {"key": "kiza","name": "きっざにあ","groups": ["red"]},
    {"key": "konkuri","name": "こんくり","groups": ["blue"]},
    {"key": "kurisu","name": "クリス","groups": ["green"]},
    {"key": "nino","name": "にの","groups": ["yellow"]},
    {"key": "numaru","name": "ぬまるん","groups": ["red"]},
    {"key": "yuina","name": "ゆいな","groups": ["purple"]},
    {"key": "zenten","name": "ぜんてん","groups": ["yellow"]},
    {"key": "eng","name": "えんじぇる","groups": ["red"]},
    {"key": "yama","name": "やまだ","groups": ["blue"]},
    {"key": "kono","name": "この","groups": ["green"]},
    {"key": "hiro","name": "ヒロ","groups": ["purple"]},
    {"key": "mio","name": "mio","groups": ["yellow"]},
    {"key": "bul","name": "おいら","groups": ["red"]},
    {"key": "hana","name": "はなこ","groups": ["green"]},
    {"key": "inu","name": "いぬ","groups": ["purple"]},
    {"key": "ouki","name": "おうき","groups": ["red"]},
    {"key": "aka","name": "あかり","groups": ["blue"]},
    {"key": "shiba","name": "しば","groups": ["green"]},
    {"key": "ero","name": "えろこ","groups": ["purple"]},
    {"key": "gero","name": "ゲロ","groups": ["yellow"]},
    {"key": "san","name": "サンダー","groups": ["red"]},  
    {"key": "jinsei","name": "loser","groups": ["red"]},

    {"key": "tonbo","name": "トンボ","groups": ["purple"]},
    {"key": "yuyu","name": "ゅゅ","groups": ["yellow"]},
    {"key": "rei","name": "れい","groups": ["red"]},  
    {"key": "tumu","name": "つむ","groups": ["blue"]},
    {"key": "urufu","name": "うるふ","groups": ["green"]},
    
    {"key": "cyoumi","name": "ちょうみりょう","groups": ["purple"]},
    {"key": "erechima","name": "ういえれ","groups": ["yellow"]},
    {"key": "shigu","name": "シグ","groups": ["green"]},

    {"key": "liu","name": "リウたん","groups": ["yellow"]},
    {"key": "minmin","name": "みんみん","groups": ["red"]},  
    {"key": "puchia","name": "ぷちあ","groups": ["blue"]},
    {"key": "pyon","name": "ぴょん","groups": ["green"]},

    {"key": "dyun","name": "でゅんでゅん","groups": ["purple"]},
    {"key": "ichigo","name": "いちご","groups": ["yellow"]},
    {"key": "suu","name": "すーちゃん","groups": ["red"]},  
    {"key": "take","name": "たけのこ","groups": ["blue"]},
    {"key": "tokimi","name": "トキミノ","groups": ["green"]},

    {"key": "cyama","name": "ちゃま","groups": ["purple"]},
    {"key": "ika","name": "いか","groups": ["yellow"]},
    {"key": "kare","name": "カレー","groups": ["red"]},  
    {"key": "lv","name": "lv","groups": ["blue"]},
    {"key": "mata","name": "まったり","groups": ["green"]},

    {"key": "noa","name": "のあ","groups": ["purple"]},
    {"key": "raise","name": "きみのよめ","groups": ["yellow"]},
    {"key": "syuu","name": "しゅうや","groups": ["red"]},  
    {"key": "takana","name": "たかな","groups": ["blue"]},
    {"key": "yomo","name": "よもチ","groups": ["green"]},

    {"key": "bachio","name": "ばっちお","groups": ["purple"]},
    {"key": "cry","name": "cry","groups": ["yellow"]},
    {"key": "hyou","name": "メビウス","groups": ["red"]},  
    {"key": "jyaku","name": "弱","groups": ["blue"]},
    {"key": "kuko","name": "くこ","groups": ["green"]},

    {"key": "nyao","name": "にゃおっす","groups": ["purple"]},
    {"key": "rana","name": "らな","groups": ["yellow"]},
    {"key": "sana","name": "sana","groups": ["red"]},  
    {"key": "taida","name": "怠惰","groups": ["blue"]},
    {"key": "uruha","name": "うるは","groups": ["green"]},

    {"key": "syoa","name": "しょあ","groups": ["blue"]},
    {"key": "ivu","name": "いゔ","groups": ["yellow"]},






]


TRAIN_RESULTS = [
    (1, "今回はダメかも..."),
    (2, "今回はまあまあ..."),
    (3, "今回はかなりいい！"),
    (4, "今回はすばらしい！"),
    (5, "今回は大成功だ！！！"),
]

def get_passive_display(passive_key: str | None) -> str:
    if not passive_key:
        return "なし"

    data = PASSIVE_SKILLS.get(passive_key)
    if not data:
        return "なし"

    return f"{data['emoji']} {data['label']}"
RACE_TIMES = ["09:00", "12:00", "15:00", "18:00", "21:00"]

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

def get_condition_text(happiness: int) -> str:
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

    return "   たまご"
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
        return f"   {pet.get('name', 'おあしすっち')}"

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
# 能力値計算
# -------------------------
def calc_race_ability(pet: dict, race: dict) -> float:
    """
    距離・コンディション込みの能力値
    """

    # 実効ステータス（幸福度・根性込み）
    stats = calc_effective_stats(pet)

    speed = stats["speed"]
    stamina = stats["stamina"]
    power = stats["power"]

    distance = race["distance"]

    if distance == "短距離":
        ability = 1.25*speed + 1.00*power + 0.85*stamina
    elif distance == "マイル":
        ability = 1.10*speed + 1.00*power + 1.00*stamina
    elif distance == "中距離":
        ability = 0.95*speed + 1.00*power + 1.15*stamina
    else:  # 長距離
        ability = 0.85*speed + 0.95*power + 1.30*stamina

    return ability

# -------------------------
# オッズ変換
# -------------------------  

def calc_odds_from_probs(probs: list[float], house_rate: float = 0.85):
    odds = []
    for p in probs:
        if p <= 0:
            odds.append(99.9)
        else:
            o = house_rate / p
            o = max(1.1, min(99.9, o))
            odds.append(round(o, 1))
    return odds

# -------------------------
# 勝率計算
# -------------------------  

def calc_win_probabilities(pets: list[dict], race: dict, k: float = 2.5):
    abilities = []

    for pet in pets:
        ability = calc_race_ability(pet, race)
        abilities.append(ability ** k)

    total = sum(abilities)

    probs = [a / total for a in abilities]
    return probs
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
        print("🔥 cog_load 呼ばれた")


        if not self.poop_check.is_running():
            self.poop_check.start()

        if not self.oasistchi_tick.is_running():
            self.oasistchi_tick.start()

        if not self.race_lottery_watcher.is_running():
            self.race_lottery_watcher.start()


        if not self.trifecta_purchase_dm_watcher.is_running():
            self.trifecta_purchase_dm_watcher.start()

    async def cog_unload(self):
        self.poop_check.cancel()
        self.race_tick.cancel()
        self.oasistchi_tick.cancel()
        self.race_lottery_watcher.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if not hasattr(self.bot, "_race_started"):
            self.bot._race_started = True

            print("🏇 Race loop starting...")

            await asyncio.sleep(2)

            if not self.race_tick.is_running():
                self.race_tick.start()




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
                line += " ｜   **根性発動！**"

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

        # ロックしない（取得だけ）
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

        # 🔑 Bot が参加している全 guild を処理
        for guild in self.bot.guilds:
            guild_id = str(guild.id)

            # =========================
            # ① 今日のレース生成
            # =========================
            try:
                async with db._lock:
                    if not await db.has_today_race_schedules(today, guild_id):
                        await db.generate_today_races(guild_id, today)
                        print(f"[RACE] {today} のレースを生成しました guild={guild_id}")
            except Exception as e:
                print(f"[RACE ERROR] generate failed guild={guild_id}: {e}")
                continue

            # =========================
            # ② レース一覧取得
            # =========================
            async with db._lock:
                races = await db.get_today_race_schedules(today, guild_id)

            # =========================
            # ③ 抽選判定ループ
            # =========================
            for race in races:
                if race.get("lottery_done"):
                    continue

                race_time_raw = race["race_time"]
                if isinstance(race_time_raw, str):
                    h, m = map(int, race_time_raw.split(":"))
                    race_time = dtime(hour=h, minute=m)
                else:
                    race_time = race_time_raw

                entry_close = (
                    datetime.combine(today, race_time, JST)
                    - timedelta(minutes=race["entry_open_minutes"])
                )

                if now < entry_close:
                    continue

                # =========================
                # ④ pending 数チェック
                # =========================
                async with db._lock:
                    pending_count = await db._fetchval(
                        """
                        SELECT COUNT(*)
                        FROM race_entries
                        WHERE guild_id = $1
                          AND race_date = $2
                          AND schedule_id = $3
                          AND status = 'pending'
                        """,
                        guild_id,
                        race["race_date"],
                        race["id"],
                    )

                if pending_count < 2:
                    continue

                # ⑤ 抽選実行
                #try:
                #    await db.run_race_lottery(
                #        guild_id,
                #        race["race_date"],
                #        race["id"]
                #   )

                #    print(f"[RACE] 抽選完了 race_id={race['id']} guild={guild_id}")

                #except Exception as e:
                #    print(f"[RACE ERROR] lottery failed race_id={race['id']} guild={guild_id}: {e}")





    # =========================
    # レース処理（正規版・完成）
    # =========================
    async def send_race_result_embed(self, race: dict, results: list[dict]):
        channel = await self.get_race_result_channel(str(race["guild_id"]))
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

            # -------------------------
            # 最終オッズ表示
            # -------------------------
            odds_text = ""
            if r.get("final_odds", 0) > 0:
                odds_text = f"\n📈 最終オッズ {r['final_odds']}倍"

            # -------------------------
            # パッシブ表示
            # -------------------------
            passive_text = ""

            if r.get("passive_skill"):
                display = get_passive_display(r["passive_skill"])
                passive_text = f"\n✨ パッシブ：{display}"

            embed.add_field(
                name=f"{medal} {r['name']}",
                value=(
                    f"<@{r['user_id']}>\n"
                    f"🏃 スピード {r['stats']['speed']}\n"
                    f"🫀 スタミナ {r['stats']['stamina']}\n"
                    f"💥 パワー {r['stats']['power']} {guts}\n"
                    f"📊 score {r['score']:.1f}"
                    f"{odds_text}"
                    f"{passive_text}"
                ),
                inline=False
            )
        await channel.send(embed=embed)
        # 🔐 連投防止フラグ
        await self.bot.db._execute("""
            UPDATE race_schedules
            SET result_sent = TRUE
            WHERE id = $1
       """, race["id"])

    # =========================
    # レース処理（正規版・完成）
    # =========================

    async def send_race_entry_panel(self, race: dict, selected_entries: list[dict]):
        print("[RACE DEBUG] send_race_entry_panel ENTERED")

        guild_id = str(race["guild_id"])
        channel = await self.get_race_result_channel(guild_id)

        print(f"[RACE DEBUG] channel={channel}")

        if channel is None:
            print("[RACE DEBUG] channel is None -> return")
            return

        print("[RACE DEBUG] sending race entry panel...")

        # 念のためシャッフル（枠番ランダム）
        entries = [dict(e) for e in selected_entries] 
        random.shuffle(entries)
        for i, entry in enumerate(entries, start=1):
            entry["gate"] = i

        embed = discord.Embed(
            title=f"🏇 第{race['race_no']}レース 出走決定（{race['race_time']}）",
            description=(
                f"{race['distance']}｜{race['surface']}｜{race['condition']}\n"
                f"出走頭数：{len(entries)} / 8"
            ),
            color=discord.Color.green()
        )

        for frame_no, entry in enumerate(entries, start=1):
            try:
                pet = await self.db.get_oasistchi_pet(entry["pet_id"])
                if not pet:
                    continue

                passive_key = pet.get("passive_skill")


                if passive_key and passive_key in PASSIVE_SKILLS:
                    skill = PASSIVE_SKILLS[passive_key]
                    passive_text = f"{skill['emoji']} {skill['label']}"
                else:
                    passive_text = "なし"

                # ★ 関数をそのまま呼ぶ（self.get_condition_text じゃない）
                condition = get_condition_text(int(pet.get("happiness", 0)))

                # ★ speed/stamina/power は無いので base+train
                speed = int(pet.get("base_speed", 0)) + int(pet.get("train_speed", 0))
                stamina = int(pet.get("base_stamina", 0)) + int(pet.get("train_stamina", 0))
                power = int(pet.get("base_power", 0)) + int(pet.get("train_power", 0))

                name = pet.get("name", "おあしすっち")


                embed.add_field(
                    name=f"【枠番 {frame_no}】🐣 {name}",
                    value=(
                        f"👤 <@{entry['user_id']}>\n"
                        f"📉 コンディション：{condition}\n\n"
                        f"🏃 スピード：{speed}\n"
                        f"🫀 スタミナ：{stamina}\n"
                        f"💥 パワー：{power}\n"
                        f"✨ パッシブ：{passive_text}"
                    ),
                    inline=False
                )

            except Exception as e:
                print(f"[RACE PANEL ERROR] frame={frame_no} pet_id={entry.get('pet_id')} err={e!r}")
                continue

        embed.set_footer(text="このあとレース結果が発表されます")
        await channel.send(embed=embed)

    # =========================
    # ★ レース用チャンネル取得（正規）
    # =========================
    async def get_race_result_channel(self, guild_id: str):
        row = await self.db.get_race_settings(guild_id)
        if not row:
            return None

        channel_id = row.get("result_channel_id")
        if not channel_id:
            return None

        return self.bot.get_channel(int(channel_id))
    

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


    # =========================
    # レース抽選タスク（完全防御版）
    # =========================
    @tasks.loop(seconds=30)
    async def race_lottery_watcher(self):

        try:
            now = datetime.now(JST)
            today = now.date()

            for guild in self.bot.guilds:
                guild_id = str(guild.id)

                try:
                    races = await self.bot.db.get_today_race_schedules(today, guild_id)
                except Exception as e:
                    print(f"[RACE ERROR] get_today_race_schedules guild={guild_id} err={e!r}")
                    continue

                for race in races:

                    try:
                        # -------------------------
                        # race_time 安全変換
                        # -------------------------
                        race_time_raw = race.get("race_time")

                        if isinstance(race_time_raw, str):
                            h, m = map(int, race_time_raw.split(":"))
                            race_time = dtime(hour=h, minute=m)
                        else:
                            race_time = race_time_raw

                        race_dt = datetime.combine(today, race_time, tzinfo=JST)

                        close_dt = race_dt - timedelta(
                            minutes=race.get("entry_open_minutes", 10)
                        )

                        # =========================
                        # ① 抽選
                        # =========================
                        if not race.get("lottery_done") and now >= close_dt:

                            print(f"[RACE LOTTERY] race_id={race.get('id')}")

                            result = await self.bot.db.run_race_lottery(
                                guild_id=guild_id,
                                race_date=today,
                                schedule_id=race["id"]
                            )

                            if not result:
                                print(f"[RACE ERROR] lottery returned None race_id={race.get('id')}")
                                continue

                            selected_entries = result.get("selected", [])

                            if len(selected_entries) >= 2:
                                await self.send_race_entry_panel(
                                    race,
                                    selected_entries
                                )
                            else:
                                print(f"[RACE WARNING] less than 2 selected race_id={race.get('id')}")

                            continue  # 抽選処理終了


                        # =========================
                        # ② レース確定（開始時刻）
                        # =========================
                        if race.get("lottery_done") and not race.get("reward_paid", False):

                            if now >= race_dt:

                                print(f"[RACE START] race_id={race.get('id')}")

                                await self.bot.db.finalize_race(
                                    guild_id=guild_id,
                                    race_date=today,
                                    schedule_id=race["id"],
                                    distance=race.get("distance")
                                )

                        # =========================
                        # ③ 結果パネル（10分後）
                        # =========================
                        if race.get("reward_paid", False) and not race.get("result_sent", False):

                            result_dt = race_dt + timedelta(minutes=10)

                            if now >= result_dt:

                                print(f"[RACE RESULT SEND] race_id={race.get('id')}")

                                results = await self.bot.db._fetch("""
                                    SELECT re.user_id,
                                           re.pet_id,
                                           re.rank,
                                           re.score,
                                           p.name,
                                           p.base_speed,
                                           p.train_speed,
                                           p.base_stamina,
                                           p.train_stamina,
                                           p.base_power,
                                           p.train_power,
                                           p.passive_skill
                                    FROM race_entries re
                                    JOIN oasistchi_pets p
                                      ON p.id = re.pet_id
                                    WHERE re.schedule_id = $1
                                      AND re.status = 'selected'
                                    ORDER BY re.rank ASC
                                """, race["id"])

                                if not results:
                                    print(f"[RACE WARNING] no results race_id={race.get('id')}")
                                    continue
                                print("RESULTS DEBUG:", results)

                                # =========================
                                # 💰 完全プール式 払い戻し
                                # =========================


                                winner_pet_id = results[0]["pet_id"]

                                # 総投票額
                                total_pool_row = await self.bot.db._fetchrow("""
                                    SELECT SUM(amount) AS total
                                    FROM race_bets
                                    WHERE schedule_id = $1
                                """, race["id"])

                                total_pool = (total_pool_row["total"] if total_pool_row else 0) or 0


                                # 勝ち馬への総投票額

                                winner_pool_row = await self.bot.db._fetchrow("""
                                    SELECT SUM(amount) AS total
                                    FROM race_bets
                                    WHERE schedule_id = $1
                                      AND pet_id = $2
                                """, race["id"], int(winner_pet_id))


                                winner_pool = (winner_pool_row["total"] if winner_pool_row else 0) or 0

                                print(f"[POOL] total={total_pool} winner_pool={winner_pool}")

                                # 払戻原資
                                payout_pool = total_pool

                                if winner_pool > 0:


                                    winning_bets = await self.bot.db._fetch("""
                                        SELECT user_id, amount
                                        FROM race_bets
                                        WHERE schedule_id = $1
                                          AND pet_id = $2
                                    """, race["id"], int(winner_pet_id))

                                    for bet in winning_bets:

                                        payout = int(payout_pool * (bet["amount"] / winner_pool))

                                        print(
                                            f"[PAYOUT] race={race['id']} "
                                            f"user={bet['user_id']} "
                                            f"bet={bet['amount']} "
                                            f"payout={payout}"
                                        )


                                        await self.bot.db.add_balance(
                                            int(bet["user_id"]),
                                            int(race["guild_id"]),
                                            payout
                                        )


                                        try:
                                            user_obj = await self.bot.fetch_user(int(bet["user_id"]))


                                            await user_obj.send(
                                                f"🎉 **的中！**\n"
                                                f"🏁 第{race['race_no']}レース\n\n"
                                                f"🎫 購入額：{bet['amount']:,} rrc\n"
                                                f"💰 払戻：{payout:,} rrc"
                                            )

                                        except Exception as e:
                                            print(f"[PAYOUT DM ERROR] {e!r}")

                                else:
                                    print(f"[NO WINNERS] race_id={race['id']} winner_pool=0")


                                # =========================
                                # 🎯 3連単 払い戻し
                                # =========================

                                if len(results) >= 3:

                                    first_id  = results[0]["pet_id"]
                                    second_id = results[1]["pet_id"]
                                    third_id  = results[2]["pet_id"]



                                    pool_row = await self.bot.db._fetchrow("""
                                        SELECT total_pool
                                        FROM race_trifecta_pools
                                        WHERE schedule_id = $1
                                    """, race["id"])

                                    total_tri_pool = pool_row["total_pool"] if pool_row else 0


                                    combo_pool = await self.bot.db._fetchval("""
                                        SELECT COALESCE(SUM(amount),0)
                                        FROM race_trifecta_bets
                                        WHERE schedule_id = $1
                                          AND first_pet_id = $2
                                          AND second_pet_id = $3
                                          AND third_pet_id = $4
                                    """, race["id"], first_id, second_id, third_id)

                                    print(f"[TRI POOL] total={total_tri_pool} combo={combo_pool}")

                                    if total_tri_pool > 0 and combo_pool > 0:

                                        payout_pool = total_tri_pool

                                        winning_bets = await self.bot.db._fetch("""
                                            SELECT user_id, amount
                                            FROM race_trifecta_bets
                                            WHERE schedule_id = $1
                                              AND first_pet_id = $2
                                              AND second_pet_id = $3
                                              AND third_pet_id = $4
                                        """, race["id"], first_id, second_id, third_id)

                                        for bet in winning_bets:

                                            payout = int(payout_pool * (bet["amount"] / combo_pool))

                                            print(
                                                f"[TRIFECTA PAYOUT] race={race['id']} "
                                                f"user={bet['user_id']} "
                                                f"bet={bet['amount']} "
                                               f"payout={payout}"
                                            )

                                            await self.bot.db.add_balance(
                                                str(bet["user_id"]),
                                                str(race["guild_id"]),
                                                payout
                                            )

                                            try:
                                                user_obj = await self.bot.fetch_user(int(bet["user_id"]))
                                                await user_obj.send(
                                                    f"🎯 **3連単的中！**\n"
                                                    f"🏁 第{race['race_no']}レース\n\n"
                                                    f"💰 払戻：{payout:,} rrc"
                                                )
                                            except Exception as e:
                                                print(f"[TRIFECTA DM ERROR] {e!r}")

                                        await self.bot.db._execute("""
                                                UPDATE race_trifecta_pools
                                                SET total_pool = 0
                                                WHERE schedule_id = $1
                                            """, race["id"])

                                    else:
                                        print(f"[TRIFECTA NO WINNER] race_id={race['id']}")

                                        if total_tri_pool > 0:

                                            # 🔥 次レースへcarry加算
                                            await self.bot.db._execute("""
                                                UPDATE race_trifecta_carry
                                                SET carry_over = carry_over + $1
                                                WHERE guild_id = $2
                                            """, total_tri_pool, guild_id)

                                            # 🔥 今レースのプールをクリア（重要）
                                            await self.bot.db._execute("""
                                                UPDATE race_trifecta_pools
                                                SET total_pool = 0
                                                WHERE schedule_id = $1
                                            """, race["id"])

                                            print(f"[TRIFECTA CARRY ADD] +{total_tri_pool}")


                                # =========================
                                # 結果整形（最終オッズ＋パッシブ付き）
                                # =========================

                                formatted = []

                                for r in results:

                                    # -------------------------
                                    # ステータス合算
                                    # -------------------------
                                    stats = {
                                        "speed": (r["base_speed"] or 0) + (r["train_speed"] or 0),
                                        "stamina": (r["base_stamina"] or 0) + (r["train_stamina"] or 0),
                                        "power": (r["base_power"] or 0) + (r["train_power"] or 0),
                                        "guts": r.get("guts", False),
                                    }

                                    # -------------------------
                                    # その馬への総投票額取得
                                    # -------------------------
                                    pet_pool_row = await self.bot.db._fetchrow("""
                                        SELECT SUM(amount) AS total
                                        FROM race_bets
                                        WHERE schedule_id = $1
                                          AND pet_id = $2
                                    """, race["id"], r["pet_id"])

                                    pet_pool = (pet_pool_row["total"] if pet_pool_row else 0) or 0

                                    # -------------------------
                                    # 最終オッズ計算
                                    # -------------------------
                                    if pet_pool > 0:
                                        final_odds = round(total_pool / pet_pool, 2)
                                    else:
                                        final_odds = 0

                                    formatted.append({
                                        "user_id": r["user_id"],
                                        "name": r["name"],
                                        "score": r["score"],
                                        "stats": stats,
                                        "final_odds": final_odds,
                                        "pet_id": r["pet_id"],
                                        "passive_skill": r.get("passive_skill")
                                    })

                                await self.send_race_result_embed(race, formatted)

                                await self.bot.db._execute("""
                                    UPDATE race_schedules
                                    SET race_finished = TRUE,
                                        result_sent = TRUE
                                    WHERE id = $1
                                """, race["id"])



                    except Exception as race_err:
                        print(f"[RACE LOOP ERROR] race_id={race.get('id')} err={race_err!r}")

                        traceback.print_exc()

                        continue

        except Exception as fatal:
            print(f"[RACE WATCHER FATAL] {fatal!r}")


    # =========================
    # 3連単通知ループ
    # =========================

    @tasks.loop(seconds=10)
    async def trifecta_purchase_dm_watcher(self):

        rows = await self.bot.db.get_unnotified_trifecta_bets()

        for r in rows:

            pets = await self.bot.db._fetch("""
                SELECT id, name
                FROM oasistchi_pets
                WHERE id = ANY($1::int[])
            """, [r["first_pet_id"], r["second_pet_id"], r["third_pet_id"]])

            pet_map = {p["id"]: p["name"] for p in pets}

            units = r["amount"] // 10000

            try:
                user = await self.bot.fetch_user(int(r["user_id"]))

                await user.send(
                    "🎯 **3連単購入完了**\n\n"
                    f"🥇1着 {pet_map.get(r['first_pet_id'],'?')}\n"
                    f"🥈2着 {pet_map.get(r['second_pet_id'],'?')}\n"
                    f"🥉3着 {pet_map.get(r['third_pet_id'],'?')}\n\n"
                    f"🎫 購入口数 {units}口"
                )

            except Exception as e:
                print("[TRIFECTA BUY DM ERROR]", e)
                continue

            await self.bot.db.mark_trifecta_dm_sent(r["id"])






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
            updates["next_poop_check_at"] = now + 10800

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
        slot_price: int,
    ):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

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
    # 管理者：レース結果チャンネル設定
    # -----------------------------
    @app_commands.command(name="レース結果チャンネル設定")
    @app_commands.describe(channel="レース結果を送信するチャンネル")
    async def set_race_result_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild.id)

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.followup.send(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        await self.bot.db.set_race_result_channel(
            guild_id,
            str(channel.id)
        )

        await interaction.followup.send(
            f"✅ レース結果チャンネルを {channel.mention} に設定しました。",
            ephemeral=True
        )


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
        await interaction.followup.send(
            "🐣 おあしすっちを確認中…",
            ephemeral=True
        )
        db = interaction.client.db
        uid = str(interaction.user.id)

        pets = await db.get_oasistchi_pets(uid)
        if not pets:
            return await interaction.followup.send(
                "まだおあしすっちを持っていません。",
                ephemeral=True
            )

        selected_pet = dict(pets[0])

        # -------------------------
        # 選択ペット決定
        # -------------------------
        if pet is not None:
            my_pet_ids = {str(p["id"]) for p in pets}

            if pet not in my_pet_ids:
                return await interaction.followup.send(
                    "❌ プルダウンから選択してください。",
                    ephemeral=True
                )

            selected_pet = next(p for p in pets if str(p["id"]) == pet)
        else:
            selected_pet = dict(pets[0])

        # -------------------------
        # ここからは selected_pet だけ使う
        # -------------------------
        embed = self.make_status_embed(selected_pet)
        view = CareView(uid, selected_pet["id"], selected_pet)
        # =========================
        # ✨ ランクアップ条件判定
        # =========================
        can_rankup = (
            selected_pet["stage"] == "adult"
            and selected_pet.get("growth", 0) >= 100
        )

        if can_rankup:
            view.add_item(RankUpButton(selected_pet["id"]))

        pet_file = self.get_pet_image(selected_pet)
        gauge_file = build_growth_gauge_file(selected_pet["growth"])

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
            passive_key = pet.get("passive_skill")
            passive_text = get_passive_display(passive_key)

            stats_text += f"\n✨ パッシブスキル：{passive_text}"

            # 説明文追加
            if passive_key and passive_key in PASSIVE_SKILLS:
                description = PASSIVE_SKILLS[passive_key].get("description", "")
                if description:
                    stats_text += f"\n> {description}"

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
        async with db._lock:
            pets = await db.get_all_oasistchi_pets()

        for pet in pets:
            await self.process_time_tick(pet)


    # -----------------------------
    # レース作成
    # -----------------------------

    @tasks.loop(minutes=1)
    async def race_tick(self):
        print("🔥 race_tick 動いた")
        print("[RACE TICK] tick")

        async with self._race_lock:
            try:
                await self.trigger_race_daily_process()
            except Exception as e:
                print(f"[RACE TICK ERROR] {e!r}")


    @race_tick.before_loop
    async def before_race_tick(self):
        print("[RACE TICK] waiting for ready...")
        await self.bot.wait_until_ready()
        print("[RACE TICK] started")

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

# =========================
# レース予定4.7
# =========================

    @discord.ui.button(
        label="レース予定",
        style=discord.ButtonStyle.primary,
        custom_id="oasistchi:race_schedule"
    )
    async def show_race_schedule(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db

        today = today_jst_date()
        guild_id = str(interaction.guild.id)

        schedules = await db.get_today_race_schedules(today, guild_id)

        if not schedules:
            return await interaction.followup.send(
                "本日のレース予定はまだ生成されていません。",
                ephemeral=True
            )

        # normalだけ抽出
        normal_schedules = [
            dict(s)
            for s in schedules
            if s.get("race_tier", "normal") == "normal"
        ]

        if not normal_schedules:
            return await interaction.followup.send(
                "本日の通常レース予定はありません。",
                ephemeral=True
            )

        embed = build_race_schedule_embed(normal_schedules)
        await interaction.followup.send(embed=embed, ephemeral=True)


# =========================
# 上位レース予定4.7
# =========================
    @discord.ui.button(
        label="上位レース予定",
        style=discord.ButtonStyle.danger,
        custom_id="oasistchi:elite_race_schedule"
    )
    async def show_elite_race_schedule(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db

        today = today_jst_date()
        guild_id = str(interaction.guild.id)

        schedules = await db.get_today_race_schedules(today, guild_id)

        if not schedules:
            return await interaction.followup.send(
                "本日の上位レース予定はまだ生成されていません。",
                ephemeral=True
            )

        # eliteだけ抽出
        elite_schedules = [
            dict(s)
            for s in schedules
            if s.get("race_class", "normal") == "elite"
        ]

        if not elite_schedules:
            return await interaction.followup.send(
                "本日の上位レース予定はありません。",
                ephemeral=True
            )

        embed = build_race_schedule_embed(elite_schedules)
        embed.title = "🏆 上位レース予定"

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )




    @discord.ui.button(label="🌐 レースサイト", style=discord.ButtonStyle.primary)
    async def race_site_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        guild_id = interaction.guild.id

        race = await interaction.client.db.get_latest_open_race(str(guild_id))

        # レースが存在しない
        if not race:
            url = f"https://racetest-production.up.railway.app/index.html?guild={guild_id}"
            return await interaction.followup.send(
                f"🌐 レースサイトはこちら\n{url}",
                ephemeral=True
            )

        # 🔥 ここが重要
        race_id = race["id"]

        # 文字列で渡す（HMAC安定）
        token = generate_token(str(user_id), str(guild_id), str(race_id))

        url = (
            "https://racetest-production.up.railway.app/index.html"
            f"?guild={guild_id}"
            f"&user={user_id}"
            f"&race={race_id}"
            f"&token={token}"
        )

        await interaction.followup.send(
            f"🌐 レースサイトはこちら\n{url}",
            ephemeral=True
        )


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
                label="   かぶりなし たまご",
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

            # ⭐ 現在枠数取得
            user = await interaction.client.db.get_oasistchi_user(uid)
            current_slots = user["slots"]

            # ⭐ 表示用価格
            display_price = self.slot_price * 2 if current_slots >= 5 else self.slot_price

            view = ConfirmPurchaseView(
                kind="slot",
                label="育成枠を増築",
                price=self.slot_price,   # ← 実際の価格はそのまま
                egg_key=None,
                slot_price=self.slot_price
            )

            return await interaction.response.send_message(
                f"育成枠を **{display_price:,} rrc** で増築しますか？",
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
                new_slots, actual_price = await db.purchase_oasistchi_slot_safe(
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
                        f"消費: **{actual_price:,} {unit}**"
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
# お世話ボタン（既存そのまま）4.7
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
                "🏆 上位レース参加",
                "   お別れ",
                "🏋️ 特訓",      # ← 特訓ボタン想定
            }:
                self.remove_item(child)

            # 🧬 成体のとき孵化は隠す
            if pet["stage"] == "adult" and label == "🐣 孵化":
                self.remove_item(child)


        # ⭐ ここに追加（forの外）
        if pet["stage"] == "adult":
            self.add_item(ExploreButton(self.pet_id))



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
        if now - pet.get("last_pet", 0) < 10800:
            await interaction.followup.send(
                "まだなでなでできません。（3時間クールタイム）",
                ephemeral=True
            )
            return
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
            "  ️ どのステータスを特訓しますか？\n選択後「決定」を押してください。",
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
        today = today_jst_date()
        guild_id = str(interaction.guild.id)

        schedules = await db.get_today_race_schedules(today, guild_id)

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

    @discord.ui.button(label="🏆 上位レース参加", style=discord.ButtonStyle.danger)
    async def elite_race_entry(
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

        today = today_jst_date()
        guild_id = str(interaction.guild.id)

        schedules = await db.get_today_race_schedules(today, guild_id)

        if not schedules:
            return await interaction.followup.send(
                "本日の上位レース予定がありません。",
                ephemeral=True
            )

        # elite のみ抽出
        elite_schedules = [
            dict(s)
            for s in schedules
            if s.get("race_class", "normal") == "elite"
        ]

        if not elite_schedules:
            return await interaction.followup.send(
                "本日の上位レースはありません。",
                ephemeral=True
            )

        condition, condition_emoji, face_count = get_race_condition(
            pet.get("happiness", 0)
        )

        ENTRY_FEE = 100000

        embed = discord.Embed(
            title="🏆 上位レース出走確認",
            description="この状態で上位レースに出走しますか？",
            color=discord.Color.gold()
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
            schedules=elite_schedules
        )

        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )

    # =========================
    # エントリー状況3.9
    # =========================
    @discord.ui.button(label="📋 エントリー状況", style=discord.ButtonStyle.secondary)
    async def entry_status(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        today = today_jst_date()

        # 今日のレース
        schedules = await db.get_today_race_schedules(today, guild_id)

        # 自分のエントリー
        entries = await db.get_user_entries(uid)

        # schedule_id -> entry
        entry_map = {e["schedule_id"]: e for e in entries}

        embed = discord.Embed(
            title="🧪 本日のレースエントリー状況",
            description=f"📅 {today}",
            color=discord.Color.blue()
        )

        view = EntryCancelView(entries)

        for i, race in enumerate(schedules, start=1):

            schedule_id = race["id"]

            race_time = race["race_time"]
            distance = race["distance"]
            surface = race["surface"]

            if schedule_id in entry_map:

                e = entry_map[schedule_id]

                if e["status"] == "pending":
                    status_text = "🕒 抽選待ち"
                elif e["status"] == "selected":
                    status_text = "🏇 出走確定"
                else:
                    status_text = e["status"]

                value = (
                    f"{e['pet_name']}\n"
                    f"{distance}\n"
                    f"{surface}\n"
                    f"{status_text}"
                )

            else:
                value = "エントリー無し"

            embed.add_field(
                name=f"第{i}レース｜🕘 {race_time}",
                value=value,
                inline=False
            )

        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="🏆 上位エントリー状況", style=discord.ButtonStyle.secondary)
    async def elite_entry_status(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        today = today_jst_date()

        # 今日の全レース
        schedules = await db.get_today_race_schedules(today, guild_id)

        # eliteだけ抽出
        elite_schedules = [
            dict(s)
            for s in schedules
            if s.get("race_class", "normal") == "elite"
        ]

        if not elite_schedules:
            return await interaction.followup.send(
                "本日の上位レースはありません。",
                ephemeral=True
            )

        # 自分のエントリー
        entries = await db.get_user_entries(uid)

        # schedule_id -> entry
        entry_map = {e["schedule_id"]: e for e in entries}

        embed = discord.Embed(
            title="🏆 本日の上位レースエントリー状況",
            description=f"📅 {today}",
            color=discord.Color.gold()
        )

        # eliteだけのキャンセル候補
        elite_schedule_ids = {r["id"] for r in elite_schedules}
        elite_entries = [
            e for e in entries
            if e["schedule_id"] in elite_schedule_ids
        ]

        view = EntryCancelView(elite_entries)

        for i, race in enumerate(elite_schedules, start=1):
            schedule_id = race["id"]
            race_time = race["race_time"]
            distance = race["distance"]
            surface = race["surface"]

            if schedule_id in entry_map:
                e = entry_map[schedule_id]

                if e["status"] == "pending":
                    status_text = "🕒 抽選待ち"
                elif e["status"] == "selected":
                    status_text = "🏇 出走確定"
                else:
                    status_text = e["status"]

                value = (
                    f"{e['pet_name']}\n"
                    f"{distance}\n"
                    f"{surface}\n"
                    f"{status_text}"
                )
            else:
                value = "エントリー無し"

            embed.add_field(
                name=f"🏆 上位第{i}レース｜🕘 {race_time}",
                value=value,
                inline=False
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


# ⭐ 探索テーブル3.19
EXPLORE_TABLE = [
    (0.0005, 100000),
    (0.0020, 30000),
    (0.0100, 10000),
    (0.0300, 5000),
    (0.1000, 2000),
    (0.1500, 1000),
    (0.2000, 500),
    (0.1075, 100),
    (0.4000, 0),   # ← これ追加
]
EXPLORE_RANK = {
    100000: "UR",
    30000: "SSR",
    10000: "SR",
    5000: "R",
    2000: "UC",
    1000: "C",
    500: "N",
    100: "N",
    0: "MISS"
}
EXPLORE_COLOR = {
    "UR": 0xff00ff,
    "SSR": 0xffd700,
    "SR": 0x9b59b6,
    "R": 0x3498db,
    "UC": 0x2ecc71,
    "C": 0xffffff,
    "N": 0x95a5a6,
    "MISS": 0x2c3e50
}

EXPLORE_FLAVOR = {
    100000: [
        "{name}は奥地で巨大な宝石鉱脈を発見して持ち帰ってきた！(+100,000rrc)",
        "{name}は古代遺跡の最深部で財宝を見つけて持ち帰ってきた！(+100,000rrc)",
        "{name}は誰も辿り着けなかった洞窟で宝の山を見つけてきた！(+100,000rrc)",
        "{name}は探索中に伝説の財宝を発見して持ち帰ってきた！(+100,000rrc)",
        "{name}は地中深くで光り輝く秘宝を掘り当ててきた！(+100,000rrc)",
        "{name}はブロッコリー畑を見つけてきた…なぜか誰かに高値で売れた！(+100,000rrc)",
        "{name}は探索中にしばの隠し資産を見つけて持ち帰ってきた！(+100,000rrc)",
        "{name}はしばの金庫らしきものを発見して中身を持ち帰ってきた！(+100,000rrc)",
        "{name}は探索中にアカリに評価され、その報酬を持ち帰ってきた！(+100,000rrc)",
        "{name}はアカリの評価を受けて、推し○を持ち帰ってきた！(+100,000rrc)",
        "{name}は探索中に看守長の保管庫を見つけて中身を持ち帰ってきた！(+100,000rrc)",
        "{name}はおうきの監視をかいくぐり、牢獄の財宝を持ち帰ってきた！(+100,000rrc)",
        "{name}はおうきの作った密造酒を持ち帰ってきた！(+100,000rrc)",
        "{name}は探索中にoasis銀行の裏口を見つけてリリコインを持ち帰ってきた！(+100,000rrc)",
        "{name}は犬の管理する資産の一部を発見して持ち帰ってきた！(+100,000rrc)",
        "{name}は探索中にシステムのバグを見つけ、山田に口止め料をもらった！(+100,000rrc)",
        "{name}はデバッグ用の山田の資金データを発見して持ち帰ってきた！(+100,000rrc)",
        "{name}は探索中にれみえるの導きで財宝を見つけてきた！(+100,000rrc)",
        "{name}はれみえるの置き土産を見つけて持ち帰ってきた！(+100,000rrc)",
        "{name}は探索中にカカオトークえろ子の愚痴を聞かされたお礼をもらった！中身は大金だった！(+100,000rrc)",
        "{name}はカカオトークえろ子の承認欲求で大バズりした！(+100,000rrc)",
    ],

    30000: [
        "{name}はエメラルドの原石を洞窟の奥から持ち帰ってきた。(+30,000rrc)",
        "{name}はルビーの結晶を岩壁から削り出してきた。(+30,000rrc)",
        "{name}はサファイアの塊を地下水路で見つけてきた。(+30,000rrc)",
        "{name}はダイヤモンドの欠片を砂漠の地中から掘り出してきた。(+30,000rrc)",
        "{name}はアメジストの結晶群を洞窟で見つけてきた。(+30,000rrc)",
        "{name}はトパーズの原石を岩場から持ち帰ってきた。(+30,000rrc)",
        "{name}はオパールの塊を地面の奥から見つけてきた。(+30,000rrc)",
        "{name}はガーネットの結晶を崖の隙間から取り出してきた。(+30,000rrc)",
        "{name}はアクアマリンを地下の水辺で拾ってきた。(+30,000rrc)",
        "{name}はラピスラズリの塊を古い遺跡で見つけてきた。(+30,000rrc)",

        "{name}はドラゴンの牙を焼けた洞窟の奥から持ち帰ってきた。(+30,000rrc)",
        "{name}はドラゴンの鱗を溶岩の近くで拾ってきた。(+30,000rrc)",
        "{name}はワイバーンの爪を崖の巣から持ち帰ってきた。(+30,000rrc)",
        "{name}はグリフォンの羽根を山頂で拾ってきた。(+30,000rrc)",
        "{name}は巨大蜘蛛の糸を森の奥で回収してきた。(+30,000rrc)",
        "{name}はフェニックスの羽根を燃え跡から持ち帰ってきた。(+30,000rrc)",
        "{name}はケルベロスの抜けた牙を洞窟で見つけてきた。(+30,000rrc)",
        "{name}はミノタウロスの角の欠片を迷宮で拾ってきた。(+30,000rrc)",
        "{name}はゴーレムの核石を崩れた岩場から取り出してきた。(+30,000rrc)",
        "{name}はスライムの核を地下で回収してきた。(+30,000rrc)",

        "{name}は古代王の金貨袋を遺跡の床下から持ち帰ってきた。(+30,000rrc)",
        "{name}は封印された宝箱を開けて中身を持ち帰ってきた。(+30,000rrc)",
        "{name}は王家の指輪を崩れた神殿で見つけてきた。(+30,000rrc)",
        "{name}は古代の巻物を地下室から持ち帰ってきた。(+30,000rrc)",
        "{name}は金で装飾された短剣を宝物庫で見つけてきた。(+30,000rrc)",
        "{name}は古代のミイラの首飾りを回収してきた。(+30,000rrc)",
        "{name}は銀の装飾盾を遺跡の壁から外してきた。(+30,000rrc)",
        "{name}は王族のティアラを地下の箱から持ち帰ってきた。(+30,000rrc)",
        "{name}は古代硬貨の詰まった壺を掘り出してきた。(+30,000rrc)",
        "{name}は金のインゴットを隠し部屋から持ち帰ってきた。(+30,000rrc)",

        "{name}は月光草の束を夜の森で採取してきた。(+30,000rrc)",
        "{name}は星の砂を砂漠の中心で集めてきた。(+30,000rrc)",
        "{name}は精霊の結晶を泉の底から持ち帰ってきた。(+30,000rrc)",
        "{name}は魔力を帯びたキノコを洞窟で採取してきた。(+30,000rrc)",
        "{name}は虹色の花を高地で摘んできた。(+30,000rrc)",
        "{name}は光る苔を地下で集めてきた。(+30,000rrc)",
        "{name}は精霊樹の枝を森の奥で拾ってきた。(+30,000rrc)",
        "{name}は霧の結晶を湿地帯で回収してきた。(+30,000rrc)",
        "{name}は雷を帯びた石を嵐の後に拾ってきた。(+30,000rrc)",
        "{name}は氷結した花を雪山で持ち帰ってきた。(+30,000rrc)",

        "{name}は禁足の地の奥で黒曜石の塊を持ち帰ってきた。(+30,000rrc)",
        "{name}は安息の地の地下で青い結晶を見つけてきた。(+30,000rrc)",
        "{name}はフリルの裏通路で宝石箱を見つけてきた。(+30,000rrc)",
        "{name}は広場の地下通路で金貨を掘り出してきた。(+30,000rrc)",
        "{name}は教会の地下で古い聖杯を持ち帰ってきた。(+30,000rrc)",
        "{name}は高級ホテルの隠し部屋で宝石を見つけてきた。(+30,000rrc)",
        "{name}は牢獄の奥で鎖に繋がれた宝箱を回収してきた。(+30,000rrc)",
        "{name}は砂漠の遺跡で黄金の仮面を持ち帰ってきた。(+30,000rrc)",
        "{name}はビンゴ倉庫の奥で景品の山を見つけてきた。(+30,000rrc)",
        "{name}はOasis Liveの舞台裏で宝石を回収してきた。(+30,000rrc)",

        "{name}は海底で真珠の塊を見つけてきた。(+30,000rrc)",
        "{name}は沈没船から金貨の袋を持ち帰ってきた。(+30,000rrc)",
        "{name}は海中洞窟で珊瑚の装飾を回収してきた。(+30,000rrc)",
        "{name}は砂浜で大きな貝の中から真珠を見つけてきた。(+30,000rrc)",
        "{name}は水晶洞窟で巨大な結晶を持ち帰ってきた。(+30,000rrc)",
        "{name}は火山のふもとで黒い宝石を拾ってきた。(+30,000rrc)",
        "{name}は雷が落ちた場所で光る石を回収してきた。(+30,000rrc)",
        "{name}は氷の洞窟で青白い結晶を持ち帰ってきた。(+30,000rrc)",
        "{name}は深い森で琥珀の塊を見つけてきた。(+30,000rrc)",
        "{name}は谷底で金の鉱石を掘り出してきた。(+30,000rrc)",
    ],
    
    10000: [
        "{name}は小さなエメラルドの欠片を持ち帰ってきた。(+10,000rrc)",
        "{name}はルビーの粒を岩の隙間から見つけてきた。(+10,000rrc)",
        "{name}はサファイアの欠片を地下水路で拾ってきた。(+10,000rrc)",
        "{name}はアメジストの結晶をひとつ持ち帰ってきた。(+10,000rrc)",
        "{name}はトパーズの破片を岩場から回収してきた。(+10,000rrc)",
        "{name}はオパールの小片を地面から見つけてきた。(+10,000rrc)",
        "{name}はガーネットの粒を崖で拾ってきた。(+10,000rrc)",
        "{name}はアクアマリンの欠片を水辺で見つけてきた。(+10,000rrc)",
        "{name}はラピスラズリの破片を遺跡で拾ってきた。(+10,000rrc)",
        "{name}は黒曜石のかけらを洞窟で持ち帰ってきた。(+10,000rrc)",

        "{name}はドラゴンの鱗の欠片を洞窟で拾ってきた。(+10,000rrc)",
        "{name}はワイバーンの羽を1枚持ち帰ってきた。(+10,000rrc)",
        "{name}はグリフォンの羽根の切れ端を拾ってきた。(+10,000rrc)",
        "{name}は巨大蜘蛛の糸の束を回収してきた。(+10,000rrc)",
        "{name}はフェニックスの燃え残りの羽を拾ってきた。(+10,000rrc)",
        "{name}はケルベロスの爪の欠片を見つけてきた。(+10,000rrc)",
        "{name}はミノタウロスの角の破片を迷宮で拾ってきた。(+10,000rrc)",
        "{name}はゴーレムの小さな核石を回収してきた。(+10,000rrc)",
        "{name}はスライムの核の欠片を持ち帰ってきた。(+10,000rrc)",
        "{name}はコウモリの牙の束を洞窟で集めてきた。(+10,000rrc)",

        "{name}は古代硬貨を数枚、床の隙間から取り出してきた。(+10,000rrc)",
        "{name}は装飾された銀の指輪を拾ってきた。(+10,000rrc)",
        "{name}は古びた短剣を箱の中から持ち帰ってきた。(+10,000rrc)",
        "{name}は金の装飾が施されたコップを見つけてきた。(+10,000rrc)",
        "{name}は古代の小さな壺を掘り出してきた。(+10,000rrc)",
        "{name}は宝石の付いたペンダントを拾ってきた。(+10,000rrc)",
        "{name}は細工された銀貨をまとめて持ち帰ってきた。(+10,000rrc)",
        "{name}は古い宝箱の中身を少し回収してきた。(+10,000rrc)",
        "{name}は王家の紋章入りの小物を見つけてきた。(+10,000rrc)",
        "{name}は装飾の施されたブローチを持ち帰ってきた。(+10,000rrc)",

        "{name}は月光草を数本、森の奥で採取してきた。(+10,000rrc)",
        "{name}は光るキノコをまとめて持ち帰ってきた。(+10,000rrc)",
        "{name}は精霊の粉を泉の周りで集めてきた。(+10,000rrc)",
        "{name}は虹色の花びらを拾ってきた。(+10,000rrc)",
       "{name}は光る苔を削り取って持ち帰ってきた。(+10,000rrc)",
        "{name}は精霊樹の葉を数枚持ち帰ってきた。(+10,000rrc)",
        "{name}は霧の結晶を小さく削り出してきた。(+10,000rrc)",
        "{name}は氷の花びらを雪山で回収してきた。(+10,000rrc)",
        "{name}は雷を帯びた砂を集めてきた。(+10,000rrc)",
        "{name}は発光する虫を捕まえてきた。(+10,000rrc)",

        "{name}は禁足の地の入口で黒い石を拾ってきた。(+10,000rrc)",
        "{name}は安息の地の地下で青い石を見つけてきた。(+10,000rrc)",
        "{name}はフリルで装飾品の欠片を拾ってきた。(+10,000rrc)",
        "{name}は広場の隅で小さな宝石を見つけてきた。(+10,000rrc)",
        "{name}は教会の裏で銀の装飾を拾ってきた。(+10,000rrc)",
        "{name}は高級ホテルで忘れられていた指輪を見つけてきた。(+10,000rrc)",
        "{name}は牢獄で隠されていた鍵を持ち帰ってきた。(+10,000rrc)",
        "{name}は砂漠の遺跡で装飾品を回収してきた。(+10,000rrc)",
        "{name}はビンゴ会場で景品の一部を持ち帰ってきた。(+10,000rrc)",
        "{name}はOasis Liveの裏でアクセサリーを拾ってきた。(+10,000rrc)",

        "{name}は海辺で真珠をひとつ見つけてきた。(+10,000rrc)",
        "{name}は沈没船から小さな箱を持ち帰ってきた。(+10,000rrc)",
        "{name}は海中で珊瑚の欠片を回収してきた。(+10,000rrc)",
        "{name}は浜辺で貝の中から宝石を見つけてきた。(+10,000rrc)",
        "{name}は水晶洞窟で結晶の破片を拾ってきた。(+10,000rrc)",
        "{name}は火山の近くで黒い石を拾ってきた。(+10,000rrc)",
        "{name}は雷の跡地で焦げた宝石を見つけてきた。(+10,000rrc)",
        "{name}は氷の洞窟で結晶の欠片を持ち帰ってきた。(+10,000rrc)",
        "{name}は森で琥珀の小片を見つけてきた。(+10,000rrc)",
        "{name}は谷で金の砂を少し集めてきた。(+10,000rrc)",
    ],
    5000: [
        "{name}は洞窟の奥で銀鉱石の塊を持ち帰ってきた。(+5,000rrc)",
        "{name}は地下水路で良質な鉄鉱石を掘り出してきた。(+5,000rrc)",
        "{name}は岩場で石英の結晶をいくつか回収してきた。(+5,000rrc)",
        "{name}は谷底でまとまった金砂を集めてきた。(+5,000rrc)",
        "{name}は火山のふもとで硫黄の大きな塊を持ち帰ってきた。(+5,000rrc)",
        "{name}は雪山の洞穴で氷晶石を見つけてきた。(+5,000rrc)",
        "{name}は崖の裂け目で黒曜石の塊を削り出してきた。(+5,000rrc)",
        "{name}は森の地下で琥珀の塊を持ち帰ってきた。(+5,000rrc)",
        "{name}は乾いた川底で砂金をしっかり集めてきた。(+5,000rrc)",
        "{name}は遺跡の床下で青銅のインゴットを見つけてきた。(+5,000rrc)",

        "{name}はオークの牙を森の奥で回収してきた。(+5,000rrc)",
        "{name}はゴブリンの武器一式を洞窟で持ち帰ってきた。(+5,000rrc)",
        "{name}はコボルトの爪をまとめて回収してきた。(+5,000rrc)",
        "{name}はリザードマンの鱗を束で持ち帰ってきた。(+5,000rrc)",
        "{name}はハーピーの羽を数枚回収してきた。(+5,000rrc)",
        "{name}はバジリスクの抜け殻を洞窟で見つけてきた。(+5,000rrc)",
        "{name}はマンティコアの尾針を荒野で回収してきた。(+5,000rrc)",
        "{name}はスライムの核を複数持ち帰ってきた。(+5,000rrc)",
        "{name}は巨大コウモリの牙を束で回収してきた。(+5,000rrc)",
        "{name}はワーウルフの毛皮を持ち帰ってきた。(+5,000rrc)",

        "{name}は古びた銀の短剣を遺跡で拾ってきた。(+5,000rrc)",
        "{name}は鉄製の胸当てを地下室で回収してきた。(+5,000rrc)",
        "{name}は革の鎧一式を廃屋で見つけてきた。(+5,000rrc)",
        "{name}は鉄の盾を持ち帰ってきた。(+5,000rrc)",
        "{name}は鎖帷子の一部を拾ってきた。(+5,000rrc)",
        "{name}は装飾付きのヘルメットを見つけてきた。(+5,000rrc)",
        "{name}は使い込まれた槍を持ち帰ってきた。(+5,000rrc)",
        "{name}は銀のバックラーを回収してきた。(+5,000rrc)",
        "{name}はしっかりした弓を森で拾ってきた。(+5,000rrc)",
        "{name}は矢筒いっぱいの矢を持ち帰ってきた。(+5,000rrc)",

        "{name}は火球の魔法スクロールを遺跡で見つけてきた。(+5,000rrc)",
        "{name}は回復魔法の巻物を地下室で持ち帰ってきた。(+5,000rrc)",
        "{name}は風の魔法陣が描かれた羊皮紙を拾ってきた。(+5,000rrc)",
        "{name}は氷の呪文書の断片を見つけてきた。(+5,000rrc)",
        "{name}は雷撃のスクロールを回収してきた。(+5,000rrc)",
        "{name}は結界の魔法紙を持ち帰ってきた。(+5,000rrc)",
        "{name}は古代語の書かれた羊皮紙を見つけてきた。(+5,000rrc)",
        "{name}は召喚魔法の断片を回収してきた。(+5,000rrc)",
        "{name}は魔力の込められた巻物を拾ってきた。(+5,000rrc)",
        "{name}は光魔法のスクロールを見つけてきた。(+5,000rrc)",

        "{name}は月光草を森の奥で大量に採取してきた。(+5,000rrc)",
        "{name}は発光キノコを洞窟でまとめて持ち帰ってきた。(+5,000rrc)",
        "{name}は虹色の花を高地で摘んできた。(+5,000rrc)",
        "{name}は精霊草を泉のそばで束にしてきた。(+5,000rrc)",
        "{name}は毒消し草を湿地で集めてきた。(+5,000rrc)",
        "{name}は光る苔を地下で削り取ってきた。(+5,000rrc)",
        "{name}は氷花を雪山で持ち帰ってきた。(+5,000rrc)",
        "{name}は火花草を火山近くで採取してきた。(+5,000rrc)",
        "{name}は風鳴き草を丘で束ねてきた。(+5,000rrc)",
        "{name}は金色の花びらをまとめて持ち帰ってきた。(+5,000rrc)",

        "{name}は妖精の粉を大量に集めてきた。(+5,000rrc)",
        "{name}は小妖精の羽を複数拾ってきた。(+5,000rrc)",
        "{name}は精霊の結晶を泉で見つけてきた。(+5,000rrc)",
        "{name}は風の精霊石を回収してきた。(+5,000rrc)",
        "{name}は炎の精霊石を拾ってきた。(+5,000rrc)",
        "{name}は水の精霊珠を持ち帰ってきた。(+5,000rrc)",
        "{name}は土の精霊核を見つけてきた。(+5,000rrc)",
        "{name}は闇精霊の残滓を回収してきた。(+5,000rrc)",
        "{name}は光精霊の粒子を集めてきた。(+5,000rrc)",
        "{name}は妖精を瓶に閉じ込めて持ち帰ってきた。(+5,000rrc)",

        "{name}はフリルで銀のアクセサリーを拾ってきた。(+5,000rrc)",
        "{name}は安息の地で香木の束を持ち帰ってきた。(+5,000rrc)",
        "{name}は憩いの場で装飾付きの羽飾りを見つけてきた。(+5,000rrc)",
        "{name}は広場で装飾石を拾ってきた。(+5,000rrc)",
        "{name}は教会の地下で聖水の瓶を回収してきた。(+5,000rrc)",
        "{name}は高級ホテルの裏で宝石付きボタンを拾ってきた。(+5,000rrc)",
        "{name}は牢獄で鉄の鍵束を持ち帰ってきた。(+5,000rrc)",
        "{name}は砂漠の遺跡で黄金の装飾片を見つけてきた。(+5,000rrc)",
        "{name}はビンゴ会場で景品をまとめて持ち帰ってきた。(+5,000rrc)",
        "{name}はOasis Liveの裏でステージ用装飾を回収してきた。(+5,000rrc)",
    ],
    2000: [
        "{name}は浅い洞窟で鉄鉱石の塊を持ち帰ってきた。(+2,000rrc)",
        "{name}は川底で錫鉱石をいくつか集めてきた。(+2,000rrc)",
        "{name}は岩場で石英の結晶をひとつ見つけてきた。(+2,000rrc)",
        "{name}は丘の斜面で銅鉱石を掘り出してきた。(+2,000rrc)",
        "{name}は遺跡の床で青銅の欠片を拾ってきた。(+2,000rrc)",
        "{name}は崖の隙間で黒曜石の破片を回収してきた。(+2,000rrc)",
        "{name}は乾いた川底で砂鉄を集めてきた。(+2,000rrc)",
        "{name}は森の地下で琥珀の欠片を見つけてきた。(+2,000rrc)",
        "{name}は火山のふもとで硫黄の塊を持ち帰ってきた。(+2,000rrc)",
        "{name}は洞穴で白い石灰石を拾ってきた。(+2,000rrc)",

        "{name}はゴブリンの短剣を洞窟で拾ってきた。(+2,000rrc)",
        "{name}はコボルトの爪を巣穴で回収してきた。(+2,000rrc)",
        "{name}はオークの折れた牙を森で見つけてきた。(+2,000rrc)",
        "{name}はリザードマンの鱗を沼地で拾ってきた。(+2,000rrc)",
        "{name}は巨大コウモリの牙を洞窟で回収してきた。(+2,000rrc)",
        "{name}はスライムの核を持ち帰ってきた。(+2,000rrc)",
        "{name}はハーピーの羽を崖で拾ってきた。(+2,000rrc)",
        "{name}はウルフの牙を森で見つけてきた。(+2,000rrc)",
        "{name}はスケルトンの骨片を遺跡で拾ってきた。(+2,000rrc)",
        "{name}はゾンビの爪を墓地で回収してきた。(+2,000rrc)",

        "{name}は使い古された鉄の短剣を拾ってきた。(+2,000rrc)",
        "{name}は木製の盾を持ち帰ってきた。(+2,000rrc)",
        "{name}は革の手袋を廃屋で見つけてきた。(+2,000rrc)",
        "{name}は錆びた鎖を回収してきた。(+2,000rrc)",
        "{name}は折れた槍の先を持ち帰ってきた。(+2,000rrc)",
        "{name}は古びた弓を森で拾ってきた。(+2,000rrc)",
        "{name}は矢を数本持ち帰ってきた。(+2,000rrc)",
        "{name}は鉄のバックラーを見つけてきた。(+2,000rrc)",
        "{name}は破れたマントを回収してきた。(+2,000rrc)",
        "{name}は古いヘルメットを持ち帰ってきた。(+2,000rrc)",

        "{name}は火花の魔法が残る紙片を拾ってきた。(+2,000rrc)",
        "{name}は簡易回復のスクロールを見つけてきた。(+2,000rrc)",
        "{name}は風の魔法が刻まれた紙を回収してきた。(+2,000rrc)",
        "{name}は氷の呪文の切れ端を拾ってきた。(+2,000rrc)",
        "{name}は古い魔法のメモを持ち帰ってきた。(+2,000rrc)",
        "{name}は弱い結界の紙片を見つけてきた。(+2,000rrc)",
        "{name}は古びた魔導書の一部を回収してきた。(+2,000rrc)",
        "{name}は光の魔力が残る紙を拾ってきた。(+2,000rrc)",
        "{name}は魔力の残滓がある羊皮紙を持ち帰ってきた。(+2,000rrc)",
        "{name}は呪文の書きかけを見つけてきた。(+2,000rrc)",

        "{name}は月光草を森で摘んできた。(+2,000rrc)",
        "{name}は発光キノコを洞窟で採取してきた。(+2,000rrc)",
        "{name}は小さな虹色の花を持ち帰ってきた。(+2,000rrc)",
        "{name}は精霊草を泉のそばで集めてきた。(+2,000rrc)",
        "{name}は毒消し草を湿地で拾ってきた。(+2,000rrc)",
        "{name}は光る苔を地下で削ってきた。(+2,000rrc)",
        "{name}は氷花を雪山で見つけてきた。(+2,000rrc)",
        "{name}は火花草を火山近くで拾ってきた。(+2,000rrc)",
        "{name}は風鳴き草を丘で摘んできた。(+2,000rrc)",
        "{name}は香りの良い草を持ち帰ってきた。(+2,000rrc)",

        "{name}は小妖精の羽を森で拾ってきた。(+2,000rrc)",
        "{name}は妖精の粉を少し集めてきた。(+2,000rrc)",
        "{name}は精霊の欠片を見つけてきた。(+2,000rrc)",
        "{name}は風精霊の残り香を回収してきた。(+2,000rrc)",
        "{name}は水精霊の粒を持ち帰ってきた。(+2,000rrc)",
        "{name}は火精霊の灰を拾ってきた。(+2,000rrc)",
        "{name}は土精霊の欠片を回収してきた。(+2,000rrc)",
        "{name}は闇精霊の残滓を拾ってきた。(+2,000rrc)",
        "{name}は光精霊の粒を見つけてきた。(+2,000rrc)",
        "{name}は妖精の落とし物を持ち帰ってきた。(+2,000rrc)",

        "{name}はフリルの床で銅の装飾片を拾ってきた。(+2,000rrc)",
        "{name}は安息の地で木の飾りを見つけてきた。(+2,000rrc)",
        "{name}は憩いの場で羽飾りの欠片を拾ってきた。(+2,000rrc)",
        "{name}は広場で石の装飾を見つけてきた。(+2,000rrc)",
        "{name}は教会の裏でろうそくの残りを回収してきた。(+2,000rrc)",
        "{name}は高級ホテルの裏で装飾糸を拾ってきた。(+2,000rrc)",
        "{name}は牢獄で鉄の鍵を見つけてきた。(+2,000rrc)",
        "{name}は砂漠の入口で乾いた皮を拾ってきた。(+2,000rrc)",
        "{name}はビンゴ会場で小さな景品を持ち帰ってきた。(+2,000rrc)",
        "{name}はOasis Liveの裏で部品を回収してきた。(+2,000rrc)",
    ],
    1000: [
        "{name}は道端で銅貨を数枚拾ってきた。(+1,000rrc)",
        "{name}は草むらで小さな石英を見つけてきた。(+1,000rrc)",
        "{name}は川辺で貝殻をいくつか拾ってきた。(+1,000rrc)",
        "{name}は森の入口で羽根を拾ってきた。(+1,000rrc)",
        "{name}は古い道で鉄片を見つけてきた。(+1,000rrc)",
        "{name}は岩場で丸い石を拾ってきた。(+1,000rrc)",
        "{name}は崖下で小さな黒曜石を見つけてきた。(+1,000rrc)",
        "{name}は洞穴で光る石を拾ってきた。(+1,000rrc)",
        "{name}は砂地できれいなガラス片を見つけてきた。(+1,000rrc)",
        "{name}は木の根元で木の実を拾ってきた。(+1,000rrc)",

        "{name}はゴブリンの落とした袋を拾ってきた。(+1,000rrc)",
        "{name}はコボルトの巣から小物を持ち帰ってきた。(+1,000rrc)",
        "{name}はオークの通った跡で道具を拾ってきた。(+1,000rrc)",
        "{name}はスライムの残骸から核の欠片を見つけてきた。(+1,000rrc)",
        "{name}はウルフの寝床で毛を拾ってきた。(+1,000rrc)",
        "{name}はコウモリの巣で羽を集めてきた。(+1,000rrc)",
        "{name}はスケルトンの残骸から指輪を拾ってきた。(+1,000rrc)",
        "{name}はゾンビのポケットからコインを見つけてきた。(+1,000rrc)",
        "{name}はハーピーの巣で羽根を拾ってきた。(+1,000rrc)",
        "{name}はトレントの根元で木片を見つけてきた。(+1,000rrc)",

        "{name}は古い家の棚で小物を見つけてきた。(+1,000rrc)",
        "{name}は廃屋の床でコインを拾ってきた。(+1,000rrc)",
        "{name}は井戸のそばで装飾品を見つけてきた。(+1,000rrc)",
        "{name}は橋の下で小さな袋を拾ってきた。(+1,000rrc)",
        "{name}は倉庫の裏で部品を見つけてきた。(+1,000rrc)",
        "{name}は古い箱から小物を持ち帰ってきた。(+1,000rrc)",
        "{name}は壁の隙間でコインを見つけてきた。(+1,000rrc)",
        "{name}は棚の奥で小さな宝石を拾ってきた。(+1,000rrc)",
        "{name}は床の下で袋を見つけてきた。(+1,000rrc)",
        "{name}は机の引き出しから小物を持ち帰ってきた。(+1,000rrc)",

        "{name}は月光草を少し摘んできた。(+1,000rrc)",
        "{name}は発光キノコをひとつ持ち帰ってきた。(+1,000rrc)",
        "{name}は草原で花を摘んできた。(+1,000rrc)",
        "{name}は湿地で草を集めてきた。(+1,000rrc)",
        "{name}は森で薬草を少し拾ってきた。(+1,000rrc)",
        "{name}は丘で風に揺れる草を持ち帰ってきた。(+1,000rrc)",
        "{name}は川辺で水草を拾ってきた。(+1,000rrc)",
        "{name}は木の上で実を見つけてきた。(+1,000rrc)",
        "{name}は地面で種を拾ってきた。(+1,000rrc)",
        "{name}は林で小さな花を持ち帰ってきた。(+1,000rrc)",

        "{name}は小妖精の羽を拾ってきた。(+1,000rrc)",
        "{name}は妖精の粉を少し持ち帰ってきた。(+1,000rrc)",
        "{name}は精霊の気配を集めてきた。(+1,000rrc)",
        "{name}は風の精霊の欠片を見つけてきた。(+1,000rrc)",
        "{name}は水の精霊の粒を拾ってきた。(+1,000rrc)",
        "{name}は火の精霊の灰を持ち帰ってきた。(+1,000rrc)",
        "{name}は土の精霊の粒を回収してきた。(+1,000rrc)",
        "{name}は闇の残滓を拾ってきた。(+1,000rrc)",
        "{name}は光の粒を見つけてきた。(+1,000rrc)",
        "{name}は妖精の落とし物を拾ってきた。(+1,000rrc)",

        "{name}はフリルでコインを拾ってきた。(+1,000rrc)",
        "{name}は安息の地で小物を見つけてきた。(+1,000rrc)",
        "{name}は憩いの場で羽を拾ってきた。(+1,000rrc)",
        "{name}は広場で落とし物を見つけてきた。(+1,000rrc)",
        "{name}は教会で小さな装飾を拾ってきた。(+1,000rrc)",
        "{name}はホテルの外でコインを見つけてきた。(+1,000rrc)",
        "{name}は牢獄で鍵の欠片を拾ってきた。(+1,000rrc)",
        "{name}は砂漠で乾いた石を持ち帰ってきた。(+1,000rrc)",
        "{name}はビンゴ会場で景品を拾ってきた。(+1,000rrc)",
        "{name}はOasis Liveで落とし物を見つけてきた。(+1,000rrc)",

        "{name}は他のおあしすっちからコインを分けてもらった。(+1,000rrc)",
        "{name}は仲間のおあしすっちから素材をもらった。(+1,000rrc)",
        "{name}は旅のおあしすっちから小物を受け取った。(+1,000rrc)",
        "{name}は交換でコインを手に入れてきた。(+1,000rrc)",
        "{name}は助けたおあしすっちからお礼をもらった。(+1,000rrc)",
        "{name}は他のおあしすっちの案内で拾い物をしてきた。(+1,000rrc)",
        "{name}は情報を教えてもらって回収してきた。(+1,000rrc)",
        "{name}は他のおあしすっちと協力してコインを見つけてきた。(+1,000rrc)",
        "{name}は一緒に探索して分けてもらった。(+1,000rrc)",
        "{name}は友達のおあしすっちからコインを分けてもらった。(+1,000rrc)",
    ],
    500: [
        "{name}は砂漠で綺麗なガラス片をいくつか持ち帰ってきた。(+500rrc)",
        "{name}は風で飛ばされてきた古い手紙と小銭を拾ってきた。(+500rrc)",
        "{name}は壊れた看板の金具を持ち帰ってきた。(+500rrc)",
        "{name}は誰かの落としたスプーンとコインを拾ってきた。(+500rrc)",
        "{name}は穴に落ちていたコルク栓と小物を見つけてきた。(+500rrc)",
        "{name}は水たまりで光るビー玉をいくつか見つけてきた。(+500rrc)",
        "{name}は古いロープの使えそうな部分を持ち帰ってきた。(+500rrc)",
        "{name}は焼け焦げた木片と釘を拾ってきた。(+500rrc)",
        "{name}は紙袋の中から使えそうな物を持ち帰ってきた。(+500rrc)",
        "{name}は曲がったフォークと小銭を拾ってきた。(+500rrc)",

        "{name}は迷子のおあしすっちを送り届けてちょっとした報酬をもらった。(+500rrc)",
        "{name}は転んだおあしすっちを助けて少し多めにお礼をもらった。(+500rrc)",
        "{name}は道案内のついでに小銭を分けてもらった。(+500rrc)",
        "{name}は休憩していたおあしすっちから軽食とコインをもらった。(+500rrc)",
        "{name}は話しかけてきたおあしすっちからお礼の品を受け取った。(+500rrc)",
        "{name}は迷っていたおあしすっちを助けて報酬を得た。(+500rrc)",
        "{name}は雑談の流れで小物をいくつかもらった。(+500rrc)",
        "{name}は落とし物を届けて少し多めのお礼をもらった。(+500rrc)",
        "{name}は荷物を運んであげて報酬を受け取った。(+500rrc)",
        "{name}は探し物を手伝ってコインをもらった。(+500rrc)",

        "{name}は風で転がってきた空き缶とコインを拾ってきた。(+500rrc)",
        "{name}は水たまりで変な形の石と小銭を見つけてきた。(+500rrc)",
        "{name}は日陰で丸まっていた紙と金具を拾ってきた。(+500rrc)",
        "{name}は砂に埋もれていたボタンとコインを掘り出してきた。(+500rrc)",
        "{name}は草の中からタグと小物を見つけてきた。(+500rrc)",
        "{name}は崩れた壁からレンガ片と金具を持ち帰ってきた。(+500rrc)",
        "{name}は捨てられた箱から使えそうな物を回収してきた。(+500rrc)",
        "{name}は割れた皿の中から使える欠片を持ち帰ってきた。(+500rrc)",
        "{name}は干からびた枝と紐を拾ってきた。(+500rrc)",
        "{name}は用途がありそうな金具をいくつか拾ってきた。(+500rrc)",

        "{name}はビンゴ会場の裏で参加賞を持ち帰ってきた。(+500rrc)",
        "{name}はOasis Liveの片付けで小物とコインを拾ってきた。(+500rrc)",
        "{name}は広場で配布物と少しのコインを持ち帰ってきた。(+500rrc)",
        "{name}はフリルで使えそうな装飾片を拾ってきた。(+500rrc)",
        "{name}は教会の外で羽とコインを拾ってきた。(+500rrc)",
        "{name}はホテルの外で落とし物と小銭を見つけてきた。(+500rrc)",
        "{name}は牢獄の前で鍵の欠片とコインを拾ってきた。(+500rrc)",
        "{name}は砂漠で乾いた革と小物を持ち帰ってきた。(+500rrc)",
        "{name}は合コン会場の外で忘れ物とコインを拾ってきた。(+500rrc)",
        "{name}はホスト通りで名刺とチップを拾ってきた。(+500rrc)",

        "{name}は風に乗って飛んできた羽と小銭をつかまえてきた。(+500rrc)",
        "{name}は虫を追いかけていたら小物を見つけてきた。(+500rrc)",
        "{name}は日向ぼっこ中に近くの落とし物を回収してきた。(+500rrc)",
        "{name}は水を飲みに行ったついでにコインを拾ってきた。(+500rrc)",
        "{name}は休憩中に足元の小物を持ち帰ってきた。(+500rrc)",
        "{name}はぼーっとしていたら転がってきた物を拾ってきた。(+500rrc)",
        "{name}は風に流されてきた物をまとめて拾ってきた。(+500rrc)",
        "{name}は道草中にちょっとした収穫をしてきた。(+500rrc)",
        "{name}は立ち止まった場所で小物とコインを見つけてきた。(+500rrc)",
        "{name}は帰り道でついでに拾い物をしてきた。(+500rrc)",

        "{name}は壊れた時計の使える部品を拾ってきた。(+500rrc)",
        "{name}は古い鍵の一部とコインを持ち帰ってきた。(+500rrc)",
        "{name}は欠けたコインを数枚見つけてきた。(+500rrc)",
        "{name}は汚れたガラス玉と小銭を拾ってきた。(+500rrc)",
        "{name}は紙片の中から価値のある物を見つけてきた。(+500rrc)",
        "{name}は使えそうな釘をまとめて拾ってきた。(+500rrc)",
        "{name}は折れたペンとコインを持ち帰ってきた。(+500rrc)",
        "{name}は焦げた紙の中から小銭を見つけてきた。(+500rrc)",
        "{name}は曲がった針金と部品を拾ってきた。(+500rrc)",
        "{name}は古びた革片と小物を持ち帰ってきた。(+500rrc)",
    ],
    100: [
        "{name}は近所でてんとう虫を捕まえてきた。(+100rrc)",
        "{name}は草むらでバッタを捕まえてきた。(+100rrc)",
        "{name}は林で小さなカブトムシを見つけてきた。(+100rrc)",
        "{name}は木の上でセミの抜け殻を拾ってきた。(+100rrc)",
        "{name}は石の下でダンゴムシを見つけてきた。(+100rrc)",
        "{name}は花の近くでミツバチを見つけてきた。(+100rrc)",
        "{name}は水辺でアメンボを見つけてきた。(+100rrc)",
        "{name}は夜道で蛍を見つけてきた。(+100rrc)",
        "{name}は草の中でコオロギを捕まえてきた。(+100rrc)",
        "{name}は木陰でクワガタの子どもを見つけてきた。(+100rrc)",

        "{name}は川辺で小さな貝を拾ってきた。(+100rrc)",
        "{name}は砂地で白い石を見つけてきた。(+100rrc)",
        "{name}は丘で丸い小石を拾ってきた。(+100rrc)",
        "{name}は道端できれいな石を持ち帰ってきた。(+100rrc)",
        "{name}は水辺でつるつるの石を拾ってきた。(+100rrc)",
        "{name}は崖の下で黒い石を見つけてきた。(+100rrc)",
        "{name}は草原で小さな石を拾ってきた。(+100rrc)",
        "{name}は森で模様のある石を見つけてきた。(+100rrc)",
        "{name}は洞穴で光る石を拾ってきた。(+100rrc)",
        "{name}は川底で丸い石を持ち帰ってきた。(+100rrc)",

        "{name}は野原でタンポポを摘んできた。(+100rrc)",
        "{name}は森で小さな花を見つけてきた。(+100rrc)",
        "{name}は丘で四つ葉のクローバーを見つけてきた。(+100rrc)",
        "{name}は水辺で水草を持ち帰ってきた。(+100rrc)",
        "{name}は林で落ち葉を拾ってきた。(+100rrc)",
        "{name}は庭で草花を摘んできた。(+100rrc)",
        "{name}は森で木の実を見つけてきた。(+100rrc)",
        "{name}は道端で小さな花びらを拾ってきた。(+100rrc)",
        "{name}は湿地で苔を持ち帰ってきた。(+100rrc)",
        "{name}は丘で風に揺れる草を摘んできた。(+100rrc)",

        "{name}は池で小さな魚を見つけてきた。(+100rrc)",
        "{name}は水たまりでおたまじゃくしを見つけてきた。(+100rrc)",
        "{name}は川で小さなエビを捕まえてきた。(+100rrc)",
        "{name}は浜辺でヒトデを見つけてきた。(+100rrc)",
        "{name}は浅瀬でカニを捕まえてきた。(+100rrc)",
        "{name}は水辺で小さな魚影を見つけてきた。(+100rrc)",
        "{name}は川で貝を拾ってきた。(+100rrc)",
        "{name}は池で水草の中から小魚を見つけてきた。(+100rrc)",
        "{name}は浜辺で小さなクラゲを見つけてきた。(+100rrc)",
        "{name}は水たまりで小さな生き物を見つけてきた。(+100rrc)",

        "{name}は小妖精の羽をひとつ拾ってきた。(+100rrc)",
        "{name}は妖精の粉を少し見つけてきた。(+100rrc)",
        "{name}は精霊の気配を感じて帰ってきた。(+100rrc)",
        "{name}は風の粒を持ち帰ってきた。(+100rrc)",
        "{name}は水の粒を拾ってきた。(+100rrc)",
        "{name}は火の小さな火種を見つけてきた。(+100rrc)",
        "{name}は土の粒を持ち帰ってきた。(+100rrc)",
        "{name}は光の粒をひとつ拾ってきた。(+100rrc)",
        "{name}は闇のかけらを見つけてきた。(+100rrc)",
        "{name}は小さな精霊の欠片を持ち帰ってきた。(+100rrc)",

        "{name}はフリルの外で羽根を拾ってきた。(+100rrc)",
        "{name}は安息の地で花を見つけてきた。(+100rrc)",
        "{name}は憩いの場で小さな石を拾ってきた。(+100rrc)",
        "{name}は広場で落ちていた花びらを持ち帰ってきた。(+100rrc)",
        "{name}は教会の外で羽を拾ってきた。(+100rrc)",
        "{name}はホテルの外で小さな石を見つけてきた。(+100rrc)",
        "{name}は牢獄の前で砂を拾ってきた。(+100rrc)",
        "{name}は砂漠で乾いた草を見つけてきた。(+100rrc)",
        "{name}はビンゴ会場で紙を拾ってきた。(+100rrc)",
        "{name}はOasis Liveの外で落とし物を見つけてきた。(+100rrc)",

        "{name}は他のおあしすっちと遊んで小物をもらった。(+100rrc)",
        "{name}は仲間のおあしすっちから草を分けてもらった。(+100rrc)",
        "{name}は旅のおあしすっちから羽をもらった。(+100rrc)",
        "{name}は交換で小さな石をもらった。(+100rrc)",
        "{name}は助けたおあしすっちから花をもらった。(+100rrc)",
        "{name}は案内してもらって拾い物をしてきた。(+100rrc)",
        "{name}は一緒に遊んで何かをもらった。(+100rrc)",
        "{name}は話していたら小物をもらった。(+100rrc)",
       "{name}は友達のおあしすっちから分けてもらった。(+100rrc)",
        "{name}は一緒に散歩して拾い物をしてきた。(+100rrc)",
    ],

    0: [
        "{name}は洞窟で見つけた宝箱を開けたが中には石しか入っていなかった。",
        "{name}は遺跡の奥で光る箱を見つけたが中身は空だった。",
        "{name}は地面を掘り当てたがただの硬い岩盤だった。",
        "{name}は崖の上で輝くものを見つけたがただの水滴だった。",
        "{name}は地下通路を進んだが途中で完全に行き止まりだった。",
        "{name}は砂を掘り進めたが何も埋まっていなかった。",
        "{name}は古い井戸を覗いたが底が見えないだけだった。",
        "{name}は壊れた箱を見つけたが中身は既に抜かれていた。",
        "{name}は岩陰で宝らしき影を見つけたがただの影だった。",
        "{name}は壁の裏を調べたがただの厚い壁だった。",
        "{name}はゴブリンの荷袋を見つけたが中は空だった。",
        "{name}はコボルトの巣に入ったが何も残っていなかった。",
        "{name}はオークの拠点に辿り着いたが誰もいなかった。",
        "{name}はスライムを追い詰めたが逃げられてしまった。",
        "{name}はウルフの巣を見つけたが毛しか残っていなかった。",
        "{name}はハーピーの巣を見つけたが既に空だった。",
        "{name}はスケルトンを倒したが骨しか残らなかった。",
        "{name}はゾンビの持ち物を探したが何も持っていなかった。",
        "{name}は巨大コウモリの巣を調べたが何もなかった。",
        "{name}はトレントの根元を探したが土しかなかった。",
        "{name}は古い宝箱を見つけて開けたが完全に空だった。",
        "{name}は引き出しを開けたが中には何も入っていなかった。",
        "{name}は棚をひっくり返したが埃しか出てこなかった。",
        "{name}は箱の底を探ったが何も見つからなかった。",
        "{name}は袋を拾ったが中身はすでに無かった。",
        "{name}は壁の裏を調べたが何も隠されていなかった。",
        "{name}は床板を外したが何も埋まっていなかった。",
        "{name}は天井を見上げたが何も吊られていなかった。",
        "{name}は机の中を探したが空っぽだった。",
        "{name}は古い壺を割ったが中は空だった。",
        "{name}は月光草を探し回ったが見つからなかった。",
        "{name}は光るキノコを探したが枯れていた。",
        "{name}は花畑を探したがまだ咲いていなかった。",
        "{name}は薬草を探したが見分けがつかなかった。",
        "{name}は森の奥まで進んだが収穫はなかった。",
        "{name}は湿地を歩いたが泥だらけになっただけだった。",
        "{name}は丘を登ったが風しかなかった。",
        "{name}は水辺を探したが何も見つからなかった。",
        "{name}は林を調べたが暗くて見えなかった。",
        "{name}は地面を掘ったが石ばかりだった。",
        "{name}は妖精の光を追いかけたが消えてしまった。",
        "{name}は精霊の声を頼りに進んだが途切れてしまった。",
        "{name}は風の精霊を捕まえようとしたが通り抜けられた。",
        "{name}は水の精霊を探したがただの水面だった。",
        "{name}は火の精霊を見つけたがすぐ消えてしまった。",
        "{name}は土の精霊を探したが地面しかなかった。",
        "{name}は光の粒を追ったが見失ってしまった。",
        "{name}は闇の影を追ったがただの影だった。",
        "{name}は妖精の跡を辿ったが消えていた。",
        "{name}はフリルを調べたが何も落ちていなかった。",
        "{name}は安息の地を探したが誰もいなかった。",
        "{name}は憩いの場を見回したが収穫はなかった。",
        "{name}は広場で落とし物を探したが見つからなかった。",
        "{name}は教会の裏を調べたが何もなかった。",
        "{name}はホテルの周辺を探したが収穫はなかった。",
        "{name}は牢獄の外を調べたが何も見つからなかった。",
        "{name}は砂漠で探したが何も埋まっていなかった。",
        "{name}はビンゴ会場で何も当たらなかった。",
        "{name}はOasis Liveを探したが何も残っていなかった。",
        "{name}は走っているおあしすっちを追ったが追いつけなかった。",
        "{name}は休んでいるおあしすっちに近づいたが逃げられた。",
        "{name}は遊んでいるおあしすっちに混ざれなかった。",
        "{name}は何か持っていそうなおあしすっちを見たが何も持っていなかった。",
        "{name}は転んで足をくじいて探索どころではなかった。",
        "{name}は荷物を落として拾うのに時間を使った。",
        "{name}は道を間違えて元の場所に戻ってきた。",
        "{name}は気づいたら同じ場所をぐるぐる回っていた。",
        "{name}は遠くまで行ったが収穫はなかった。",
        "{name}は途中で日が暮れてしまった。",
        "{name}は帰り道が分からなくなって戻ってきた。",
        "{name}は慎重に進みすぎて何も見つからなかった。",
        "{name}は探索範囲を間違えてしまった。",
        "{name}は自動で開くはずの扉の前で3時間待ったがただの押し扉だった。",
        "{name}は光るスイッチを押したが近くの灯りが一瞬チカっとしただけだった。",
        "{name}は秘密の通路らしき場所に入ったがすぐ行き止まりだった。",
        "{name}は床の模様を順番に踏んだが何も起きなかった。",
        "{name}は宝箱のフタをゆっくり開けたが中に空気しか入っていなかった。",
       "{name}は怪しい本を開いたが中身は全部白紙だった。",
        "{name}は壁のレバーを引いたがどこも動かなかった。",
        "{name}は音のする方向に走ったがただの風の音だった。",
        "{name}は足元の違和感を掘ったがただの石だった。",
        "{name}は地図の「×」に到着したが何も無かった。",
        "{name}は転がってきた樽を追いかけたがただの空き樽だった。",
        "{name}は箱の中から音がしたので開けたが中で木が鳴っていただけだった。",
        "{name}は宝石っぽい物を拾ったがガラスだった。",
        "{name}は光るキノコを持ち帰ろうとしたがただの濡れた岩だった。",
        "{name}は古代文字を解読したが「ここではない」と書いてあった。",
        "{name}は床の罠を避けたが何も設置されていなかった。",
        "{name}は砂を掘ったがただの砂の層が続いていた。",
        "{name}は水面の影を追ったが自分の影だった。",
        "{name}は空から何か落ちてきたと思ったが葉っぱだった。",
        "{name}は古びた壺を慎重に割ったが中に空気しかなかった。",
        "{name}は箱の底を叩いたが鈍い音がするだけだった。",
        "{name}は隠しスイッチを探したが見つからなかった。",
        "{name}は壁の模様を押したが何も起きなかった。",
        "{name}は棚の裏を覗いたがただの壁だった。",
        "{name}は袋を開けたが底に穴が空いていた。",
        "{name}は机の下に潜ったが埃だらけだった。",
        "{name}は天井を見たが何も吊られていなかった。",
        "{name}は床を掘ったが固くて進まなかった。",
        "{name}は鍵穴を見つけたが鍵が合わなかった。",
        "{name}は勢いよく穴を掘ったが自分が落ちた。",
        "{name}はモンスターを追いかけたが逆に追われた。",
    ]
}



class ExploreButton(discord.ui.Button):
    def __init__(self, pet_id: int):
        super().__init__(
            label="🌲 探索",
            style=discord.ButtonStyle.success,
            custom_id=f"oasistchi_explore:{pet_id}"
        )
        self.pet_id = pet_id

    async def callback(self, interaction: discord.Interaction):

        print("🌲 explore button clicked", interaction.user.id, self.pet_id)

        try:
            await interaction.response.defer(ephemeral=True)

            db = interaction.client.db
            uid = str(interaction.user.id)
            gid = str(interaction.guild.id)

            now = now_ts()

            print("🌲 explore after defer OK")

            print("A")
            last = await db.get_explore_time(uid)
            print("B")

            if last and now - last < 10800:
                remain = 10800 - (now - last)
                m = remain // 60

                embed = discord.Embed(
                    title="🌲 探索できない",
                    description=f"あと **{m}分** 待つ必要があります",
                    color=discord.Color.red()
                )

                return await interaction.followup.send(embed=embed, ephemeral=True)

            pet = await db.get_oasistchi_pet(self.pet_id)
            print("C")

            if not pet:
                print("EXPLORE PET NOT FOUND", self.pet_id)
                return await interaction.followup.send(
                    "ペット情報取得失敗", ephemeral=True
                )

            # 抽選
            r = random.random()
            total = 0
            reward = 0

            for p, money in EXPLORE_TABLE:
                total += p
                if r < total:
                    reward = money
                    break

            text = random.choice(EXPLORE_FLAVOR[reward]).format(name=pet["name"])

            if reward > 0:
                await db.add_balance(uid, gid, reward)
            print("D")

            await db.set_explore_time(uid, now)
            print("E")

            unit = (await db.get_settings())["currency_unit"]

            rank = EXPLORE_RANK.get(reward, "N")
            color = EXPLORE_COLOR[rank]

            embed = discord.Embed(
                title=f"🌲 探索結果 [{rank}]",
                description=text,
                color=color
            )

            if reward > 0:
                embed.add_field(
                    name="獲得",
                    value=f"+{reward:,}{unit}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="結果",
                    value="何も見つからなかった…",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception:
            import traceback
            traceback.print_exc()

            try:
                await interaction.followup.send(
                    "探索中にエラーが発生しました",
                    ephemeral=True
                )
            except:
                pass













# =========================
# キャンセル3.9
# =========================

class EntryCancelView(discord.ui.View):

    def __init__(self, entries):
        super().__init__(timeout=120)

        for e in entries:

            if e["status"] == "pending":

                self.add_item(
                    EntryCancelButton(e)
                )
# =========================
# キャンセル3.9
# =========================
class EntryCancelButton(discord.ui.Button):

    def __init__(self, entry):
        super().__init__(
            label=f"{entry['pet_name']} をキャンセル",
            style=discord.ButtonStyle.danger
        )

        self.entry = entry

    async def callback(self, interaction: discord.Interaction):

        db = interaction.client.db

        await db.cancel_entry(
            self.entry["pet_id"],
            self.entry["schedule_id"]
        )

        await interaction.response.send_message(
            f"❌ {self.entry['pet_name']} のエントリーをキャンセルしました。",
            ephemeral=True
        )








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

class RankUpConfirmView(discord.ui.View):
    def __init__(self, pet_id: int, new_skill: str, old_skill: str):
        super().__init__(timeout=30)
        self.pet_id = pet_id
        self.new_skill = new_skill
        self.old_skill = old_skill

    @discord.ui.button(label="はい（上書きする）", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db

        await db._execute(
            """
            UPDATE oasistchi_pets
            SET passive_skill = $1,
                growth = 0
            WHERE id = $2
            """,
            self.new_skill,
            self.pet_id
        )

        old_text = get_passive_display(self.old_skill)
        new_text = get_passive_display(self.new_skill)

        await interaction.response.edit_message(
            content=f"✨ ランクアップ成功！\n旧スキル：{old_text}\n新スキル：{new_text}",
            view=None
        )

    @discord.ui.button(label="いいえ（上書きしない）", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db

        await db._execute(
            """
            UPDATE oasistchi_pets
            SET growth = 0
            WHERE id = $1
            """,
            self.pet_id
        )

        await interaction.response.edit_message(
            content="✨ ランクアップを見送りました（ゲージのみリセット）",
            view=None
        )


class RankUpButton(discord.ui.Button):
    def __init__(self, pet_id: int):
        super().__init__(
            label="ランクアップ",
            style=discord.ButtonStyle.success,
            emoji="✨"
        )
        self.pet_id = pet_id

    async def callback(self, interaction: discord.Interaction):
        db = interaction.client.db

        pet = await db.get_oasistchi_pet(self.pet_id)
        if not pet:
            return await interaction.response.send_message(
                "ペットが見つかりません。",
                ephemeral=True
            )

        if pet["stage"] != "adult" or pet.get("growth", 0) < 100:
            return await interaction.response.send_message(
                "ランクアップ条件を満たしていません。",
                ephemeral=True
            )

        # ⭐ ここで即消費
        await db._execute(
            """
            UPDATE oasistchi_pets
            SET growth = 0
            WHERE id = $1
            """,
            self.pet_id
        )

        old_skill = pet.get("passive_skill")
        new_skill = random.choice(list(PASSIVE_SKILLS.keys()))

        # ⭐ パッシブなし → 即付与
        if not old_skill:
            await db._execute(
                """
                UPDATE oasistchi_pets
                SET passive_skill = $1
                WHERE id = $2
                """,
                new_skill,
                self.pet_id
            )

            new_text = get_passive_display(new_skill)

            return await interaction.response.send_message(
                f"✨ ランクアップ成功！\n新スキル：{new_text}",
                ephemeral=True
            )

        # ⭐ パッシブあり → 確認UI
        old_text = get_passive_display(old_skill)
        new_text = get_passive_display(new_skill)

        view = RankUpConfirmView(self.pet_id, new_skill, old_skill)

        await interaction.response.send_message(
            f"⚠️ 既にパッシブスキルを持っています\n"
            f"旧スキル：{old_text}\n"
            f"新候補：{new_text}\n\n"
            f"上書きしますか？",
            view=view,
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
    # ✅ エントリー確定（修正版：ペット単位で制御）
    # -----------------------------------------
    @discord.ui.button(label="✅ エントリー確定", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        # レース未選択防止
        if not self.selected_race:
            return await interaction.response.send_message(
                "❌ レースを選択してください。",
                ephemeral=True
            )

        # ボタン無効化（連打防止）
        button.disabled = True
        await interaction.response.edit_message(view=self)

        db = interaction.client.db
        pet = self.pet
        race = self.selected_race

        schedule_id = int(race["id"])
        race_date = race["race_date"]
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        # ① 同一レースに同一ペットが既にエントリーしていないか
        if await db.has_pet_entry_for_race(schedule_id, int(pet["id"])):
            return await interaction.followup.send(
                "❌ このおあしすっちはすでにこのレースへエントリーしています。",
                ephemeral=True
            )

        # ② 同一ペットが本日すでに出走確定（selected）していないか
        # ※「同じペットは1日1回」ルールを維持するなら必要
        if await db.has_pet_selected_today(int(pet["id"]), race_date):
            return await interaction.followup.send(
                "❌ このおあしすっちは本日すでに出走しています。（別のおあしすっちで参加してください）",
                ephemeral=True
            )

        # ③ エントリー保存（pending）
        await db.insert_race_entry(
            schedule_id=schedule_id,
            guild_id=guild_id,
            user_id=uid,
            pet_id=int(pet["id"]),       # ★ここが「個体ID」になっていることが重要
            race_date=race_date,
            entry_fee=self.entry_fee,    # ★50000固定じゃなく、viewに渡した entry_fee を使うのが安全
            paid=True
        )

        # 参加費処理（ENTRY_FEEが0なら実質ノーダメ）
        if self.entry_fee > 0:
            await db.remove_balance(uid, guild_id, self.entry_fee)

        # ④ 同一おあしすっちの「同日・他レース」エントリーを無効化（pendingだけ潰す）
        # ＝同じペットで別レースに入れようとしたら、後勝ち/前勝ちの仕様をここで作れる
        await db.cancel_other_entries(
            pet_id=int(pet["id"]),
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
























