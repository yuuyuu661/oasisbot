import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
import os
import random

DATA_PATH = "data/oasistchi.json"

def load_data():
    if not os.path.exists(DATA_PATH):
        return {"users": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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
        admin_roles = settings["admin_roles"]

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
        embed.set_image(url="attachment://egg.png")

        view = EggSelectView(egg_price, slot_price)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            files=[discord.File("assets/oasistchi/eggs/red_idle.gif", "egg.png")]
        )

    # -----------------------------
    # ユーザー：おあしすっち表示
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

    # -----------------------------
    # ステータス表示
    # -----------------------------
    def make_status_embed(self, pet: dict):
        embed = discord.Embed(title="🐣 おあしすっち", color=discord.Color.green())

        embed.add_field(
            name="成長ゲージ",
            value=f"{round(pet['growth'])}%",
            inline=False
        )

        if pet["stage"] != "egg":
            embed.add_field(name="空腹度", value="--", inline=True)

        embed.add_field(
            name="幸福度",
            value=f"{pet['happiness']}%",
            inline=True
        )

        return embed

    def get_pet_image(self, pet: dict):
        if pet["poop"]:
            path = "assets/oasistchi/eggs/red_poop.gif"
        else:
            path = "assets/oasistchi/eggs/red_idle.gif"

        return discord.File(path, "pet.gif")

    # -----------------------------
    # うんち抽選（60分）
    # -----------------------------
    @tasks.loop(minutes=60)
    async def poop_check(self):
        data = load_data()
        now = time.time()

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

# -----------------------------
# ボタン：たまご選択・購入
# -----------------------------
class EggSelectView(discord.ui.View):
    def __init__(self, egg_price: int, slot_price: int):
        super().__init__(timeout=None)
        self.egg_price = egg_price
        self.slot_price = slot_price
        self.index = 0

    @discord.ui.button(label="⬅", style=discord.ButtonStyle.gray)
    async def left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(label="➡", style=discord.ButtonStyle.gray)
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(label="購入", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        uid = str(interaction.user.id)

        user = data["users"].setdefault(uid, {"slots": 1, "pets": []})

        if len(user["pets"]) >= user["slots"]:
            return await interaction.response.send_message(
                "育成枠が足りません。",
                ephemeral=True
            )

        user["pets"].append({
            "stage": "egg",
            "egg_type": "red",
            "growth": 0,
            "happiness": 50,
            "poop": False,
            "last_pet": 0,
            "last_update": time.time()
        })

        save_data(data)

        await interaction.response.send_message(
            "🥚 おあしすっちを購入しました！",
            ephemeral=True
        )

    @discord.ui.button(label="課金", style=discord.ButtonStyle.gold)
    async def charge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"育成枠を {self.slot_price} で増築しますか？（仮）",
            ephemeral=True
        )

# -----------------------------
# お世話ボタン
# -----------------------------
class CareView(discord.ui.View):
    def __init__(self, uid: str, index: int):
        super().__init__(timeout=None)
        self.uid = uid
        self.index = index

    @discord.ui.button(label="なでなで", style=discord.ButtonStyle.primary)
    async def pet(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        pet = data["users"][self.uid]["pets"][self.index]

        now = time.time()
        if now - pet["last_pet"] < 10800:
            return await interaction.response.send_message(
                "まだなでなでできません。",
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



