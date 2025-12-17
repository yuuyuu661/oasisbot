# cogs/slot.py
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# ==========================
# セッション管理
# ==========================
SLOT_SESSIONS: dict[int, dict] = {}

# ==========================
# View（ボタンUI）
# ==========================
class JoinView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.channel_id = channel_id

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = SLOT_SESSIONS.get(self.channel_id)
        if not session:
            return await interaction.response.send_message("❌ セッションが存在しません。", ephemeral=True)

        user = interaction.user

        # VCチェック
        if not interaction.user.voice or interaction.user.voice.channel.id != session["vc_id"]:
            return await interaction.response.send_message("❌ 指定VCに参加していません。", ephemeral=True)

        if user.id in session["players"]:
            return await interaction.response.send_message("⚠️ すでに参加しています。", ephemeral=True)

        # 残高チェック
        row = await self.bot.db.get_user(str(user.id), str(interaction.guild.id))
        if row["balance"] < session["fee"]:
            return await interaction.response.send_message("❌ 残高不足です。", ephemeral=True)

        # 参加費徴収
        await self.bot.db.remove_balance(str(user.id), str(interaction.guild.id), session["fee"])

        session["players"][user.id] = {
            "pool": 0
        }

        await interaction.response.send_message("✅ 参加しました！", ephemeral=True)

    @discord.ui.button(label="開始", style=discord.ButtonStyle.danger)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = SLOT_SESSIONS.get(self.channel_id)
        if not session:
            return

        if interaction.user.id != session["host"]:
            return await interaction.response.send_message("❌ 代表者のみ開始できます。", ephemeral=True)

        if len(session["players"]) < 2:
            return await interaction.response.send_message("⚠️ 2人以上必要です。", ephemeral=True)

        # 順番シャッフル
        order = list(session["players"].keys())
        random.shuffle(order)

        session["order"] = order
        session["turn"] = 0
        session["state"] = "PLAYING"

        await interaction.message.edit(view=None)

        await send_turn_panel(self.bot, interaction.channel, session)


class SpinView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.channel_id = channel_id

    @discord.ui.button(label="🎰 スピン", style=discord.ButtonStyle.primary)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = SLOT_SESSIONS.get(self.channel_id)
        if not session or session["state"] != "PLAYING":
            return

        current = session["order"][session["turn"]]

        if interaction.user.id != current:
            return await interaction.response.send_message("⛔ あなたの番ではありません。", ephemeral=True)

        await interaction.response.defer()

        # --- 演出（仮） ---
        await interaction.followup.send("🎰 スロット回転中…")
        await asyncio.sleep(2)

        roll = random.randint(1, 10)

        if roll == 1:
            result = "END"
        elif roll == 2:
            result = "BIG"
        else:
            result = "SMALL"

        rate = session["rate"]
        player = session["players"][current]

        if result == "SMALL":
            player["pool"] += rate
            text = f"✨ 小当たり！ +{rate}"
            next_turn(session)

        elif result == "BIG":
            player["pool"] += rate * 10
            text = f"🎉 大当たり！！ +{rate*10}"
            next_turn(session)

        else:
            await handle_end(self.bot, interaction.channel, session, current)
            return

        await interaction.followup.send(
            f"{interaction.user.mention}\n{text}",
            view=SpinView(self.bot, self.channel_id)
        )


# ==========================
# 補助関数
# ==========================
async def send_turn_panel(bot, channel, session):
    uid = session["order"][session["turn"]]
    member = channel.guild.get_member(uid)

    await channel.send(
        f"👉 **{member.display_name} の番です！**",
        view=SpinView(bot, channel.id)
    )


def next_turn(session):
    session["turn"] = (session["turn"] + 1) % len(session["order"])


async def handle_end(bot, channel, session, loser_id):
    guild = channel.guild
    loser = guild.get_member(loser_id)

    total_loss = session["fee"] + session["players"][loser_id]["pool"]
    survivors = [uid for uid in session["players"] if uid != loser_id]

    share = total_loss // len(survivors)

    # 精算
    for uid in survivors:
        await bot.db.add_balance(str(uid), str(guild.id), share)

    await channel.send(
        f"💥 **終了！**\n"
        f"破産者：{loser.mention}\n"
        f"失った額：{total_loss}\n"
        f"各自獲得：{share}"
    )

    del SLOT_SESSIONS[channel.id]


# ==========================
# Cog
# ==========================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="スロット",
        description="VC参加型スロットを開始します"
    )
    @app_commands.describe(
        rate="当たりレート",
        fee="参加費"
    )
    async def slot(self, interaction: discord.Interaction, rate: int, fee: int):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ VCに参加してください。", ephemeral=True)

        channel_id = interaction.channel.id

        if channel_id in SLOT_SESSIONS:
            return await interaction.response.send_message("⚠️ すでにスロットが進行中です。", ephemeral=True)

        SLOT_SESSIONS[channel_id] = {
            "vc_id": interaction.user.voice.channel.id,
            "host": interaction.user.id,
            "rate": rate,
            "fee": fee,
            "players": {},
            "order": [],
            "turn": 0,
            "state": "JOINING",
        }

        embed = discord.Embed(
            title="🎰 スロット開始！",
            description=(
                f"レート：{rate}\n"
                f"参加費：{fee}\n\n"
                f"👇 参加ボタンを押してください"
            ),
            color=0xF1C40F
        )

        await interaction.response.send_message(
            embed=embed,
            view=JoinView(self.bot, channel_id)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SlotCog(bot))
