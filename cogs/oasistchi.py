import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
import os
import random

DATA_PATH = "data/oasistchi.json"

# =========================
# ここだけ環境に合わせて
# =========================
ASSET_BASE = "assets/oasistchi"  # oasisbot/assets/oasistchi を想定

EGG_CATALOG = [
    {
        "key": "red",
        "name": "🔴 レッドたまご",
        "icon": f"{ASSET_BASE}/egg/red/icon.png",
    },
    # 追加する時はここに増やす
    # {"key":"blue","name":"🔵 ブルーたまご","icon": f"{ASSET_BASE}/egg/blue/icon.png"},
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

        view = EggSelectView(egg_price=egg_price, slot_price=slot_price)

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
        file = self.get_pet_image(pet)
        view = CareView(uid, pet_index)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            files=[file]
        )

    def make_status_embed(self, pet: dict):
        embed = discord.Embed(title="🐣 おあしすっち", color=discord.Color.green())
        embed.add_field(name="成長ゲージ", value=f"{round(pet['growth'])}%", inline=False)

        if pet["stage"] != "egg":
            embed.add_field(name="空腹度", value="--", inline=True)

        embed.add_field(name="幸福度", value=f"{pet['happiness']}%", inline=True)
        embed.set_image(url="attachment://pet.gif")
        return embed

    def get_pet_image(self, pet: dict):
        # 今はredのみ
        if pet.get("poop"):
            path = f"{ASSET_BASE}/egg/red/poop.gif"
        else:
            path = f"{ASSET_BASE}/egg/red/idle.gif"
        return discord.File(path, "pet.gif")

    # -----------------------------
    # うんち抽選（60分）
    # -----------------------------
    @tasks.loop(minutes=60)
    async def poop_check(self):
        data = load_data()
        now = now_ts()

        for user in data["users"].values():
            for pet in user["pets"]:
                if pet["stage"] == "egg" and not pet["poop"]:
                    if random.random() < 0.3:
                        pet["poop"] = True

                # 10時間放置で幸福度減少
                if now - pet["last_update"] > 36000:
                    pet["happiness"] = max(0, pet["happiness"] - 10)

                pet["last_update"] = now

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
    def __init__(self, egg_price: int, slot_price: int):
        super().__init__(timeout=None)
        self.egg_price = int(egg_price)
        self.slot_price = int(slot_price)
        self.index = 0  # EGG_CATALOG の index

    def current(self) -> dict:
        return EGG_CATALOG[self.index]

    def build_panel_embed(self) -> tuple[discord.Embed, discord.File]:
        egg = self.current()
        embed = discord.Embed(
            title="🥚 おあしすっち たまごショップ",
            description=(
                f"**選択中：{egg['name']}**\n"
                f"🥚 たまご価格：**{self.egg_price}**\n"
                f"🧩 育成枠増築：**{self.slot_price}**\n\n"
                "⬅➡でたまごを切り替え、購入してください。"
            ),
            color=discord.Color.orange()
        )
        # 画像は添付ファイル参照
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

    @discord.ui.button(label="課金", style=discord.ButtonStyle.gold)
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
        data = load_data()
        uid = str(interaction.user.id)
        user = ensure_user(data, uid)

        # ---- TODO: 通貨チェック（Spt減算）ここに差し込む ----
        # 例: if await get_balance(uid) < self.price: ...
        # ---------------------------------------------------

        if self.kind == "egg":
            # 育成枠チェック
            if len(user["pets"]) >= user["slots"]:
                return await interaction.response.edit_message(
                    content="❌ 育成枠が足りません。課金で増築してください。",
                    view=None
                )

            # たまご登録（今はeggのみ）
            user["pets"].append({
                "stage": "egg",
                "egg_type": self.egg_key or "red",
                "growth": 0.0,
                "happiness": 50,
                "poop": False,
                "last_pet": 0,
                "last_update": now_ts()
            })
            save_data(data)

            return await interaction.response.edit_message(
                content="✅ たまごを購入しました！ `/おあしすっち` で確認できます。",
                view=None
            )

        if self.kind == "slot":
            user["slots"] = int(user.get("slots", 1)) + 1
            save_data(data)
            return await interaction.response.edit_message(
                content=f"✅ 育成枠を増築しました！ 現在の育成枠：**{user['slots']}**",
                view=None
            )

        await interaction.response.edit_message(content="❌ 不明な購入種別です。", view=None)

    @discord.ui.button(label="やめる", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="キャンセルしました。", view=None)

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

        pet["happiness"] = min(100, pet["happiness"] + 10)
        pet["last_pet"] = now
        save_data(data)

        await interaction.response.send_message("😊 なでなでした！", ephemeral=True)

    @discord.ui.button(label="お世話", style=discord.ButtonStyle.success)
    async def care(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        pet = data["users"][self.uid]["pets"][self.index]

        if pet["poop"]:
            pet["poop"] = False
            pet["happiness"] = min(100, pet["happiness"] + 5)
            save_data(data)
            await interaction.response.send_message("🧹 きれいにしました！", ephemeral=True)
        else:
            await interaction.response.send_message("今はお世話不要です。", ephemeral=True)

async def setup(bot):
    cog = OasistchiCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
