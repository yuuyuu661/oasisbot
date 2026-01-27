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
from datetime import datetime, timezone, timedelta

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
]

TRAIN_RESULTS = [
    (1, "今回はダメかも..."),
    (2, "今回はまあまあ..."),
    (3, "今回はかなりいい！"),
    (4, "今回はすばらしい！"),
    (5, "今回は大成功だ！！！"),
]
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

def do_training(current_total: int):
    if current_total >= 100:
        return 0, "これ以上成長できない…"

    gain, text = random.choice(TRAIN_RESULTS)
    if current_total + gain > 100:
        gain = 100 - current_total

    return gain, text

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


# =========================
# Cog
# =========================
class OasistchiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.poop_check.start()
        self.race_daily_reset.start()

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

        # ✅ 共有パネルは「固定のEmbed + 入口ボタンのみ」
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
    # ユーザー：おあしすっち表示（既存）
    # -----------------------------
    @app_commands.command(name="おあしすっち")
    async def oasistchi(
        self,
        interaction: discord.Interaction,
        index: int | None = None
    ):
        await interaction.response.defer()
        db = interaction.client.db
        uid = str(interaction.user.id)

        pets = await db.get_oasistchi_pets(uid)
        if not pets:
            return await interaction.followup.send(
                "まだおあしすっちを持っていません。",
                ephemeral=True
            )

        pet_index = (index - 1) if index else 0
        if pet_index < 0 or pet_index >= len(pets):
            return await interaction.followup.send(
                "その番号のおあしすっちは存在しません。",
                ephemeral=True
            )

        pet = dict(pets[pet_index])

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
        embed = discord.Embed(
            title="🐣 おあしすっち",
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

        # 🧬 成体のみステータス表示
        if pet["stage"] == "adult":
            stats_text = "\n".join([
                format_status(pet["base_speed"], pet["train_speed"], "🏃", "スピード"),
                format_status(pet["base_stamina"], pet["train_stamina"], "🫀", "スタミナ"),
                format_status(pet["base_power"], pet["train_power"], "💥", "パワー"),
            ])

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
            embed.add_field(
                name="🏋️ 特訓回数",
                value=f"{pet['training_count']} / 30",
                inline=False
            )

        embed.set_image(url="attachment://pet.gif")
        embed.set_thumbnail(url="attachment://growth.png")

        return embed

    def get_pet_image(self, pet: dict):
        if pet["stage"] == "adult":
            key = pet["adult_key"]
            path = os.path.join(ASSET_BASE, "adult", key, "idle.gif")
        else:
            egg = pet.get("egg_type", "red")
            state = "poop" if pet.get("poop") else "idle"
            path = os.path.join(ASSET_BASE, "egg", egg, f"{state}.gif")

        return discord.File(path, filename="pet.gif")

    # -----------------------------
    # うんち抽選（60分）
    # -----------------------------
    @tasks.loop(minutes=60)
    async def poop_check(self):
        if not self.bot.is_ready():
            return
        db = self.bot.db 
        pets = await self.bot.db.get_all_oasistchi_pets()

        now = time.time()

        for pet in pets:
            updates = {}

            # うんち抽選
            if pet["stage"] == "egg" and not pet["poop"]:
                if random.random() < 0.3:
                    updates["poop"] = True

            # 成体の空腹度
            if pet["stage"] == "adult":
                if now - pet["last_hunger_tick"] >= 7200:
                    updates["hunger"] = max(0, pet["hunger"] - 10)
                    updates["last_hunger_tick"] = now

            # 通知（後述）
            if pet["hunger"] <= 50 and pet.get("notify", {}).get("food"):
                try:
                    uid = pet["user_id"]
                    user_obj = await self.bot.fetch_user(int(uid))
                    await user_obj.send("🍖 おあしすっちがおなかすいてるみたい…")
                except:
                    pass

            # 幸福度
            if pet["hunger"] <= 50:
                if now - pet["last_unhappy_tick"] >= 3600:
                    updates["happiness"] = max(0, pet["happiness"] - 10)
                    updates["last_unhappy_tick"] = now

            # 成長
            if pet["stage"] == "egg":
                rate = 100 / 12
                mult = 0.5 if pet["poop"] else 1.0
                updates["growth"] = min(100, pet["growth"] + rate * mult)

            if updates:
                await db.update_oasistchi_pet(pet["id"], **updates)

                # -----------------
                # 孵化通知（成長100%到達時）
                # -----------------
                if (
                    pet["stage"] == "egg"
                    and pet.get("growth", 0) < 100
                    and updates.get("growth", 0) >= 100
                    and not pet.get("notified_hatch", False)
                ):
                    uid = str(pet["user_id"])  # ← DB列名に合わせる

                    try:
                        uid = pet["user_id"]
                        user_obj = await self.bot.fetch_user(int(uid))
                        await user_obj.send(
                            "🥚 おあしすっちが孵化しそう！\n`/おあしすっち` で確認してね！"
                        )
                    except:
                        pass

                    await db.update_oasistchi_pet(
                        pet["id"],
                        notified_hatch=True
                    )

                # -----------------
                # 放置ペナルティ（10時間）
                # -----------------
                last_interaction = pet.get("last_interaction", now)
                if now - last_interaction > 36000:
                    await self.bot.db.update_oasistchi_pet(
                        pet["id"],
                        happiness=max(0, pet["happiness"] - 10)
                    )

    # -----------------------------
    # レース日付
    # -----------------------------
    @tasks.loop(minutes=60)
    async def race_daily_reset(self):
        if not self.bot.is_ready():
            return
        db = self.bot.db

        settings = await db.get_settings()
        today = today_jst_str()
        last = settings.get("oasistchi_race_reset_date")

        # すでに今日リセット済み
        if last == today:
            return

        print("🏁 おあしすっち レース日付リセット実行")

        # raced_today を全リセット
        await db.conn.execute("""
            UPDATE oasistchi_pets
            SET raced_today = FALSE;
        """)

        # 日付保存
        await db.update_settings(
            oasistchi_race_reset_date=today
        )
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

    @discord.ui.button(label="🥚 たまご購入", style=discord.ButtonStyle.green)
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

    @discord.ui.button(label="💳 課金", style=discord.ButtonStyle.primary)
    async def open_charge(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChargeSelectView(slot_price=self.slot_price)

        await interaction.response.send_message(
            "課金メニューを選択してください。",
            view=view,
            ephemeral=True
        )



    @discord.ui.button(label="🔔 通知設定", style=discord.ButtonStyle.secondary)
    async def open_notify(self, interaction, button):
        view = NotifySelectView()
        await interaction.response.send_message(
            "通知設定を選んでください。",
           view=view,
            ephemeral=True
        )

    @discord.ui.button(label="🏁 レース予定", style=discord.ButtonStyle.primary)
    async def open_race_schedule(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db

        schedules = await db.get_race_schedules()
        if not schedules:
            return await interaction.followup.send(
                "本日のレース予定はありません。",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🏁 本日のレース予定",
            description="参加費：**50,000 rrc**\n同一ペットは1日1回まで",
            color=discord.Color.gold()
        )

        for s in schedules:
            embed.add_field(
            name=    f"第{s['race_no']}レース",
                value=f"🕒 {s['race_time'].strftime('%H:%M')}",
                inline=False
            )

        embed.set_footer(text="⏱ レース30分前からエントリー可能")

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
                label="育成枠を1つ増築",
                description=f"{slot_price} rrc",
                value="slot"
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

        if value == "slot":
            view = ConfirmPurchaseView(
                kind="slot",
                label="育成枠を増築",
                price=self.slot_price,
                egg_key=None,
                slot_price=self.slot_price
            )
            await interaction.response.send_message(
                f"育成枠を **{self.slot_price}** で増築しますか？",
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

    @discord.ui.button(label="購入する", style=discord.ButtonStyle.green)
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = interaction.client
        guild = interaction.guild
        user = interaction.user
        uid = str(user.id) 

        if guild is None:
            return await interaction.response.edit_message(
                content="❌ サーバー内でのみ購入できます。",
                view=None
            )

        db = bot.db
        gid = str(guild.id)

        # -------------------------
        # 残高チェック
        # -------------------------
        settings = await db.get_settings()
        unit = settings["currency_unit"]

        uid = str(interaction.user.id)
        row = await db.get_user(uid, gid)
        balance = row["balance"]

        if balance < self.price:
            return await interaction.response.edit_message(
                content=(
                    f"❌ 残高が足りません。\n"
                    f"現在: **{balance:,} {unit}** / 必要: **{self.price:,} {unit}**"
                ),
                view=None
            )

        # 残高減算
        try:
            settings = await db.get_settings()
            unit = settings["currency_unit"]

            row = await db.get_user(uid, gid)
            balance = row["balance"]

            if balance < self.price:
                return await interaction.response.edit_message(...)

            await db.remove_balance(uid, gid, self.price)

        except Exception as e:
            print("purchase error:", repr(e))
            return await interaction.response.edit_message(
                content="❌ 通貨処理中にエラーが発生しました。",
                view=None
            )

        # -------------------------
        # 購入内容の反映
        # -------------------------

        if self.kind == "egg":
            uid = str(interaction.user.id)

            # 育成枠チェック
            pets = await db.get_oasistchi_pets(uid)
            user_row = await db.get_oasistchi_user(uid)

            if len(pets) >= user_row["slots"]:
                return await interaction.response.edit_message(
                    content=(
                        "❌ 育成枠がいっぱいです。\n"
                        "「お別れ」するか、課金で枠を拡張してください。"
                    ),
                    view=None
                )

            await db.add_oasistchi_egg(
                uid,
                self.egg_key or "red"
            )

            return await interaction.response.edit_message(
                content=(
                    f"✅ **たまごを購入しました！**\n"
                    f"残高: **{balance - self.price:,} {unit}**\n"
                    f"`/おあしすっち` で確認できます"
                ),
                view=None
            )

        if self.kind == "slot":
            user_row = await db.get_oasistchi_user(uid)

            if user_row["slots"] >= 5:
                return await interaction.response.edit_message(
                    content="❌ 育成枠は最大 **5枠** までです。",
                    view=None
                )

            await db.add_oasistchi_slot(uid, 1)

            return await interaction.response.edit_message(
                content=(
                    f"✅ **育成枠を1つ増築しました！**\n"
                    f"現在の育成枠: **{user_row['slots']}**\n"
                    f"残高: **{balance - self.price:,} {unit}**"
                ),
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
            last_interaction=now,
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

        # ⑧ idle に戻す（また元メッセージ編集）
        embed = cog.make_status_embed(pet)
        pet_file = get_pet_file(pet, "idle")
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
            last_interaction=now,
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

        # -------------------------
        # ③ idle に戻す
        # -------------------------
        embed = cog.make_status_embed(pet)
        pet_file = get_pet_file(pet, "idle")
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
        
        # 成体のみ
        if pet["stage"] != "adult":
            return await interaction.response.send_message(
                "まだごはんは食べられません。",
                ephemeral=True
            )

        # おなかいっぱい判定
        if pet.get("hunger", 100) >= 100:
            return await interaction.response.send_message(
                "🍖 いまはおなかいっぱいみたい。",
                ephemeral=True
            )

        await interaction.response.defer()

        # ステータス更新
        await db.update_oasistchi_pet(
            self.pet_id,
            hunger=100,
            last_interaction=now_ts(),
        )

        cog = interaction.client.get_cog("OasistchiCog")

        # eat.gif 表示
        embed = cog.make_status_embed(pet)
        pet_file = get_pet_file(pet, "eat")
        gauge_file = build_growth_gauge_file(pet["growth"])

        await interaction.edit_original_response(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

        # GIF再生時間待ち
        eat_path = os.path.join(
            ASSET_BASE, "adult", pet["adult_key"], "eat.gif"
        )
        await asyncio.sleep(get_gif_duration_seconds(eat_path, 2.0))

        # idle に戻す
        embed = cog.make_status_embed(pet)
        pet_file = get_pet_file(pet, "idle")

        await interaction.edit_original_response(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

        # 🔔 通知（任意）
        if pet.get("notify", {}).get("food"):
            try:
                await interaction.user.send("🍖 ごはんを食べて元気いっぱい！")
            except:
                pass
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

        view = TrainingSelectView(self.pet_id)
        await interaction.response.send_message(
            "どのステータスを特訓しますか？",
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
        pet_file = get_pet_file(pet, "idle")
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
        pet_file = get_pet_file(pet, "idle")
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
        if not self.is_owner(interaction):
            return await interaction.response.send_message(
                "❌ このおあしすっちはあなたのものではありません。",
                ephemeral=True
            )

        return await interaction.response.send_message(
            "🚧 現在開発中です。\nアップデートをお待ちください！",
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

        if pet["training_count"] >= 30:
            return await interaction.response.send_message(
                "🏋️ このおあしすっちはもう十分に特訓したようだ…\n"
                ephemeral=True
            )
        

        stat = self.values[0]

        # 現在の特訓合計
        current = pet[f"train_{stat}"]

        gain, text = do_training(current)

        if gain <= 0:
            return await interaction.response.send_message(
                "❌ これ以上このステータスは成長できません。",
                ephemeral=True
            )

        # DB反映
        await db.update_oasistchi_pet(
            self.pet_id,
            **{f"train_{stat}": current + gain},
            training_count=pet["training_count"] + 1,
            last_interaction=now_ts()
        )

        await interaction.response.send_message(
            f"{text}\n**{stat.upper()} +{gain}**",
            ephemeral=True
        )

async def setup(bot):
    cog = OasistchiCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))





































