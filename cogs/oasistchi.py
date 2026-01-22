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

DATA_PATH = "data/oasistchi.json"

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

def load_data():
    if not os.path.exists(DATA_PATH):
        return {"users": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_user(data: dict, uid: str) -> dict:
    return data["users"].setdefault(uid, {"slots": 1, "pets": []})

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
    if stage == "child":
        return 100.0 / 36.0     # 36時間
    return 0.0

def try_evolve(pet: dict):
    if pet["stage"] == "egg" and pet["growth"] >= 100.0:
        pet["stage"] = "child"
        pet["growth"] = 0.0
        pet["poop"] = False

    elif pet["stage"] == "child" and pet["growth"] >= 100.0:
        pet["stage"] = "adult"
        pet["growth"] = 0.0
        pet["poop"] = False

def get_pet_file(pet: dict, state: str) -> discord.File:
    """
    state: "idle" | "pet" | "clean" | "poop"
    """
    egg = pet.get("egg_type", "red")
    path = os.path.join(ASSET_BASE, "egg", egg, f"{state}.gif")
    return discord.File(path, filename="pet.gif")

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
# Cog
# =========================
class OasistchiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.poop_check.start()

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

        view = EggSelectView(
            egg_price=egg_price,
            slot_price=slot_price,
            panel_title=title,
            panel_body=body
        )

        embed, file = view.build_panel_embed()

        await interaction.response.send_message(
            embed=embed,
            view=view,
            files=[file]
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
        data = load_data()
        uid = str(interaction.user.id)

        if uid not in data["users"]:
            return await interaction.response.send_message(
                "まだおあしすっちを持っていません。",
                ephemeral=True
            )

        pet_index = (index - 1) if index else 0
        pets = data["users"][uid]["pets"]

        if pet_index >= len(pets):
            return await interaction.response.send_message(
                "その番号のおあしすっちは存在しません。",
                ephemeral=True
            )

        pet = pets[pet_index]
        embed = self.make_status_embed(pet)

        pet_file = self.get_pet_image(pet)
        gauge_file = build_growth_gauge_file(pet["growth"])
        view = CareView(uid, pet_index)
        await interaction.followup.send(
           embed=embed,
            view=view,
            files=[pet_file, gauge_file]
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
            value=gauge_emoji(pet["happiness"], emoji="😊"),
            inline=False
        )

        # ✅ メイン画像：おあしすっち
        embed.set_image(url="attachment://pet.gif")

        # ✅ サムネイル：進化ゲージ
        embed.set_thumbnail(url="attachment://growth.png")

        return embed

    def get_pet_image(self, pet: dict):
        egg = pet.get("egg_type", "red")
        state = "poop" if pet.get("poop") else "idle"
        path = os.path.join(ASSET_BASE, "egg", egg, f"{state}.gif")
        return discord.File(path, filename="pet.gif")

    # -----------------------------
    # うんち抽選（60分）
    # -----------------------------
    @tasks.loop(minutes=60)
    async def poop_check(self):
        data = load_data()
        now = now_ts()

        for user in data["users"].values():
            for pet in user["pets"]:

                # -----------------
                # うんち抽選
                # -----------------
                if pet["stage"] in ("egg", "child") and not pet["poop"]:
                    if random.random() < 0.3:
                        pet["poop"] = True

                # -----------------
                # 成長処理（時間経過）
                # -----------------
                rate = growth_rate_per_hour(pet["stage"])
                if rate > 0:
                    mult = 0.5 if pet.get("poop") else 1.0
                    pet["growth"] = min(100.0, pet["growth"] + rate * mult)

                # -----------------
                # 進化判定
                # -----------------
                try_evolve(pet)

                # -----------------
                # 放置ペナルティ（10時間）
                # -----------------
                last_interaction = pet.get("last_interaction", pet.get("last_tick", now))
                if now - last_interaction > 36000:
                    pet["happiness"] = max(0, pet["happiness"] - 10)

                # -----------------
                # 内部更新時刻
                # -----------------
                pet["last_tick"] = now

        save_data(data)

# =========================
# 購入パネル View
# =========================
class EggSelectView(discord.ui.View):
    """
    ⬅➡ でたまご切替
    購入で 1匹登録
    課金で 育成枠増築（確認付き）
    """
    def __init__(
            self,
            egg_price: int,
            slot_price: int,
            panel_title: str,
            panel_body: str
        ):
            super().__init__(timeout=None)
            self.egg_price = int(egg_price)
            self.slot_price = int(slot_price)
            self.panel_title = panel_title
            self.panel_body = panel_body
            self.index = 0

    def current(self) -> dict:
        return EGG_CATALOG[self.index]

    def build_panel_embed(self) -> tuple[discord.Embed, discord.File]:
        egg = self.current()

        embed = discord.Embed(
            title=self.panel_title,
            description=(
                f"{self.panel_body}\n\n"
                f"**選択中：{egg['name']}**\n"
                f"🐣 たまご価格：**{self.egg_price} rrc**\n"
                f"🧩 育成枠増築：**{self.slot_price} rrc**\n\n"
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

    @discord.ui.button(label="課金", style=discord.ButtonStyle.primary)
    async def charge(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 増築確認（ephemeral）
        view = ConfirmPurchaseView(
            kind="slot",
            label="育成枠を増築",
            price=self.slot_price,
            egg_key=None,
            slot_price=self.slot_price
        )
        await interaction.response.send_message(
            f"育成枠を **{self.slot_price}** で増築しますか？\n"
            "（仮：通貨処理は後で連携）",
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

        if guild is None:
            return await interaction.response.edit_message(
                content="❌ サーバー内でのみ購入できます。",
                view=None
            )

        db = bot.db
        data = load_data()
        uid = str(user.id)
        gid = str(guild.id)

        # -------------------------
        # 残高チェック
        # -------------------------
        try:
            settings = await db.get_settings()
            unit = settings["currency_unit"]

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
        user_data = ensure_user(data, uid)

        if self.kind == "egg":
            if len(user_data["pets"]) >= user_data["slots"]:
                # 差し戻し（返金）
                await db.add_balance(uid, gid, self.price)
                return await interaction.response.edit_message(
                    content="❌ 育成枠が足りません。（返金しました）",
                    view=None
                )

            user_data["pets"].append({
                "stage": "egg",
                "egg_type": self.egg_key or "red",
                "growth": 0.0,
                "happiness": 50,
                "hunger": 100,
                "poop": False,

                # 時刻管理を分離
                "last_pet": 0,
                "last_interaction": time.time(),  # ユーザー操作用
                "last_tick": time.time()          # Bot定期処理用
            })

            save_data(data)

            return await interaction.response.edit_message(
                content=(
                    f"✅ **たまごを購入しました！**\n"
                   f"残高: **{balance - self.price:,} {unit}**\n"
                    f"`/おあしすっち` で確認できます 🥚"
                ),
                view=None
            )

        if self.kind == "slot":
            user_data["slots"] += 1
            save_data(data)

            return await interaction.response.edit_message(
                content=(
                    f"✅ **育成枠を1つ増築しました！**\n"
                    f"現在の育成枠: **{user_data['slots']}**\n"
                    f"残高: **{balance - self.price:,} {unit}**"
                ),
                view=None
            )

        return await interaction.response.edit_message(
            content="❌ 不明な購入種別です。",
            view=None
        )

# =========================
# お世話ボタン（既存そのまま）
# =========================
class CareView(discord.ui.View):
    def __init__(self, uid: str, index: int):
        super().__init__(timeout=None)
        self.uid = uid
        self.index = index

    @discord.ui.button(label="なでなで", style=discord.ButtonStyle.primary)
    async def pet(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        pet = data["users"][self.uid]["pets"][self.index]

        now = now_ts()
        if now - pet["last_pet"] < 10800:
            return await interaction.response.send_message(
                "まだなでなでできません。（3時間クールタイム）",
                ephemeral=True
            )

        # -------------------------
        # ステータス更新
        # -------------------------
        pet["happiness"] = min(100, pet["happiness"] + 10)
        pet["growth"] = min(100.0, pet["growth"] + 5.0)
        pet["last_pet"] = now
        pet["last_interaction"] = now
        save_data(data)

        cog = interaction.client.get_cog("OasistchiCog")
        egg = pet.get("egg_type", "red")

        # -------------------------
        # ① pet.gif を表示
        # -------------------------
        embed = cog.make_status_embed(pet)
        pet_file = get_pet_file(pet, "pet")
        gauge_file = build_growth_gauge_file(pet["growth"])

        await interaction.response.edit_message(
            embed=embed,
            attachments=[pet_file, gauge_file],
            view=self
        )

        # -------------------------
        # ② GIFの長さだけ待つ（ここが可変）
        # -------------------------
        pet_gif_path = os.path.join(ASSET_BASE, "egg", egg, "pet.gif")
        wait_seconds = get_gif_duration_seconds(pet_gif_path, fallback=2.0)
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

    @discord.ui.button(label="お世話", style=discord.ButtonStyle.success)
    async def care(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        pet = data["users"][self.uid]["pets"][self.index]
        now = now_ts()

        if not pet.get("poop"):
            return await interaction.response.send_message(
                "今はお世話しなくて大丈夫！",
                ephemeral=True
            )

        # -------------------------
        # うんち処理
        # -------------------------
        pet["poop"] = False
        pet["happiness"] = min(100, pet["happiness"] + 5)
        pet["last_interaction"] = now
        save_data(data)

        cog = interaction.client.get_cog("OasistchiCog")
        egg = pet.get("egg_type", "red")

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

async def setup(bot):
    cog = OasistchiCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))









