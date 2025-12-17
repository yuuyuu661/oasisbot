# cogs/slot.py
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# ==========================
# セッション管理（Cog内で使用）
# ==========================
# channel_id -> session
SLOT_SESSIONS: dict[int, dict] = {}


# ==========================
# View（UI専用・ロジックなし）
# ==========================
class JoinView(discord.ui.View):
    def __init__(self, cog: "SlotCog", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_join(interaction, self.channel_id)

    @discord.ui.button(label="開始", style=discord.ButtonStyle.danger)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_start(interaction, self.channel_id)


class SpinView(discord.ui.View):
    def __init__(self, cog: "SlotCog", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="🎰 スピン", style=discord.ButtonStyle.primary)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_spin(interaction, self.channel_id)


# ==========================
# Cog 本体
# ==========================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------------------
    # /スロット
    # --------------------------
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
            return await interaction.response.send_message(
                "❌ VCに参加してください。",
                ephemeral=True
            )

        channel_id = interaction.channel.id
        if channel_id in SLOT_SESSIONS:
            return await interaction.response.send_message(
                "⚠️ このチャンネルではすでにスロットが進行中です。",
                ephemeral=True
            )

        SLOT_SESSIONS[channel_id] = {
            "vc_id": interaction.user.voice.channel.id,
            "host": interaction.user.id,
            "rate": rate,
            "fee": fee,
            "players": {},   # user_id -> pool
            "order": [],
            "turn": 0,
            "state": "JOIN",
        }

        embed = discord.Embed(
            title="🎰 スロット開始！",
            description=(
                f"レート：{rate}\n"
                f"参加費：{fee}\n\n"
                "👇 参加ボタンを押してください"
            ),
            color=0xF1C40F
        )

        await interaction.response.send_message(
            embed=embed,
            view=JoinView(self, channel_id)
        )

    # ==========================
    # 参加処理
    # ==========================
    async def handle_join(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS.get(channel_id)
        if not session:
            return await interaction.response.send_message("❌ セッションがありません。", ephemeral=True)

        user = interaction.user

        if not user.voice or user.voice.channel.id != session["vc_id"]:
            return await interaction.response.send_message("❌ 指定VCに参加していません。", ephemeral=True)

        if user.id in session["players"]:
            return await interaction.response.send_message("⚠️ すでに参加しています。", ephemeral=True)

        row = await self.bot.db.get_user(str(user.id), str(interaction.guild.id))
        if row["balance"] < session["fee"]:
            return await interaction.response.send_message("❌ 残高不足です。", ephemeral=True)

        await self.bot.db.remove_balance(str(user.id), str(interaction.guild.id), session["fee"])
        session["players"][user.id] = 0

        await interaction.response.send_message("✅ 参加しました！", ephemeral=True)

    # ==========================
    # 開始処理
    # ==========================
    async def handle_start(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS.get(channel_id)
        if not session:
            return

        if interaction.user.id != session["host"]:
            return await interaction.response.send_message("❌ 代表者のみ開始できます。", ephemeral=True)

        if len(session["players"]) < 2:
            return await interaction.response.send_message("⚠️ 2人以上必要です。", ephemeral=True)

        order = list(session["players"].keys())
        random.shuffle(order)

        session["order"] = order
        session["turn"] = 0
        session["state"] = "PLAY"

        await interaction.message.edit(view=None)
        await self.send_turn_panel(interaction.channel, channel_id)

    # ==========================
    # スピン処理
    # ==========================
    async def handle_spin(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS.get(channel_id)
        if not session or session["state"] != "PLAY":
            return

        current_id = session["order"][session["turn"]]
        if interaction.user.id != current_id:
            return await interaction.response.send_message("⛔ あなたの番ではありません。", ephemeral=True)

        await interaction.response.defer()

        await interaction.followup.send("🎰 スロット回転中…")
        await asyncio.sleep(2)

        roll = random.randint(1, 10)
        rate = session["rate"]

        if roll == 1:
            await self.handle_end(interaction.channel, channel_id, current_id)
            return
        elif roll == 2:
            session["players"][current_id] += rate * 10
            text = f"🎉 **大当たり！ +{rate*10}**"
        else:
            session["players"][current_id] += rate
            text = f"✨ **小当たり +{rate}**"

        session["turn"] = (session["turn"] + 1) % len(session["order"])

        await interaction.followup.send(
            f"{interaction.user.mention}\n{text}",
            view=SpinView(self, channel_id)
        )

        await self.send_turn_panel(interaction.channel, channel_id)

    # ==========================
    # 終了処理
    # ==========================
    async def handle_end(self, channel: discord.TextChannel, channel_id: int, loser_id: int):
        session = SLOT_SESSIONS[channel_id]
        guild = channel.guild

        loser_pool = session["players"][loser_id]
        total_loss = session["fee"] + loser_pool
        survivors = [uid for uid in session["players"] if uid != loser_id]
        share = total_loss // len(survivors)

        for uid in survivors:
            await self.bot.db.add_balance(str(uid), str(guild.id), share)

        loser = guild.get_member(loser_id)

        await channel.send(
            f"💥 **終了！**\n"
            f"破産者：{loser.mention}\n"
            f"失った額：{total_loss}\n"
            f"各自獲得：{share}"
        )

        del SLOT_SESSIONS[channel_id]

    # ==========================
    # ターン表示
    # ==========================
    async def send_turn_panel(self, channel: discord.TextChannel, channel_id: int):
        session = SLOT_SESSIONS[channel_id]
        uid = session["order"][session["turn"]]
        member = channel.guild.get_member(uid)

        await channel.send(
            f"👉 **{member.display_name} の番です！**",
            view=SpinView(self, channel_id)
        )


# ==========================
# setup（/bal と同じ構成）
# ==========================
async def setup(bot: commands.Bot):
    await bot.add_cog(SlotCog(bot))
