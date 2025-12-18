import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# ==========================
# セッション管理
# channel_id -> session
# ==========================
SLOT_SESSIONS: dict[int, dict] = {}

ASSET_DIR = "cogs/assets/slot"
GIF_REEL = f"{ASSET_DIR}/reel.gif"
GIF_SMALL = f"{ASSET_DIR}/small.gif"
GIF_BIG = f"{ASSET_DIR}/big.gif"
GIF_END = f"{ASSET_DIR}/end.gif"


# ==========================
# View
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

    # --------------------------------------------------
    # /スロット
    # --------------------------------------------------
    @app_commands.command(
        name="スロット",
        description="VC不要の参加型スロットを開始します"
    )
    @app_commands.describe(
        rate="当たりレート",
        fee="参加費"
    )
    async def slot(self, interaction: discord.Interaction, rate: int, fee: int):
        if interaction.guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True
            )

        channel_id = interaction.channel.id
        if channel_id in SLOT_SESSIONS:
            return await interaction.response.send_message(
                "⚠️ このチャンネルではすでにスロットが進行中です。",
                ephemeral=True
            )

        SLOT_SESSIONS[channel_id] = {
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
                f"**レート**：{rate}\n"
                f"**参加費**：{fee}\n\n"
                "👇 参加ボタンを押してください"
            ),
            color=0xF1C40F
        )

        await interaction.response.send_message(
            embed=embed,
            view=JoinView(self, channel_id)
        )

    # --------------------------------------------------
    # 参加処理
    # --------------------------------------------------
    async def handle_join(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS.get(channel_id)
        if not session:
            return await interaction.response.send_message(
                "❌ セッションが存在しません。",
                ephemeral=True
            )

        if interaction.guild is None:
            return

        user = interaction.user

        if user.id in session["players"]:
            return await interaction.response.send_message(
                "⚠️ すでに参加しています。",
                ephemeral=True
            )

        row = await self.bot.db.get_user(str(user.id), str(interaction.guild.id))
        if row["balance"] < session["fee"]:
            return await interaction.response.send_message(
                "❌ 残高不足です。",
                ephemeral=True
            )

        await self.bot.db.remove_balance(
            str(user.id),
            str(interaction.guild.id),
            session["fee"]
        )

        session["players"][user.id] = 0

        await interaction.response.send_message(
            "✅ 参加しました！",
            ephemeral=True
        )

    # --------------------------------------------------
    # 開始処理
    # --------------------------------------------------
    async def handle_start(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS.get(channel_id)
        if not session:
            return

        if interaction.user.id != session["host"]:
            return await interaction.response.send_message(
                "❌ 代表者のみ開始できます。",
                ephemeral=True
            )

        if len(session["players"]) < 2:
            return await interaction.response.send_message(
                "⚠️ 2人以上必要です。",
                ephemeral=True
            )

        order = list(session["players"].keys())
        random.shuffle(order)

        session["order"] = order
        session["turn"] = 0
        session["state"] = "PLAY"

        await interaction.message.edit(view=None)
        await self.send_turn_panel(interaction.channel, channel_id)

    # --------------------------------------------------
    # スピン処理（GIF演出あり）
    # --------------------------------------------------
    async def handle_spin(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS.get(channel_id)
        if not session or session["state"] != "PLAY":
            return

        current_id = session["order"][session["turn"]]
        if interaction.user.id != current_id:
            return await interaction.response.send_message(
                "⛔ あなたの番ではありません。",
                ephemeral=True
            )

        await interaction.response.defer()

        # ===== 結果を先に確定 =====
        roll = random.randint(1, 10)
        if roll == 1:
            result = "END"
        elif roll == 2:
            result = "BIG"
        else:
            result = "SMALL"

        # ===== 回転演出 =====
        await interaction.followup.send(
            content="🎰 スロット回転中…",
            file=discord.File(GIF_REEL)
        )
        await asyncio.sleep(2)

        rate = session["rate"]

        # ===== 結果処理 =====
        if result == "SMALL":
            session["players"][current_id] += rate
            text = f"✨ **小当たり！ +{rate}**"
            gif = GIF_SMALL

        elif result == "BIG":
            session["players"][current_id] += rate * 10
            text = f"🎉 **大当たり！！ +{rate * 10}**"
            gif = GIF_BIG

        else:
            await interaction.followup.send(
                file=discord.File(GIF_END)
            )
            await self.handle_end(interaction.channel, channel_id, current_id)
            return

        # 次ターン
        session["turn"] = (session["turn"] + 1) % len(session["order"])

        await interaction.followup.send(
            content=f"{interaction.user.mention}\n{text}",
            file=discord.File(gif),
            view=SpinView(self, channel_id)
        )

        await self.send_turn_panel(interaction.channel, channel_id)

    # --------------------------------------------------
    # 終了処理
    # --------------------------------------------------
    async def handle_end(self, channel: discord.TextChannel, channel_id: int, loser_id: int):
        session = SLOT_SESSIONS[channel_id]
        guild = channel.guild

        loser_pool = session["players"][loser_id]
        total_loss = session["fee"] + loser_pool

        survivors = [uid for uid in session["players"] if uid != loser_id]
        if not survivors:
            await channel.send("💥 終了！（参加者が1人のため清算なし）")
            del SLOT_SESSIONS[channel_id]
            return

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

    # --------------------------------------------------
    # ターン表示
    # --------------------------------------------------
    async def send_turn_panel(self, channel: discord.TextChannel, channel_id: int):
        session = SLOT_SESSIONS[channel_id]
        uid = session["order"][session["turn"]]
        member = channel.guild.get_member(uid)

        await channel.send(
            f"👉 **{member.display_name} の番です！**",
            view=SpinView(self, channel_id)
        )


# ==========================
# setup（安定構成）
# ==========================
async def setup(bot: commands.Bot):
    cog = SlotCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            try:
                bot.tree.remove_command(cmd.name, guild=discord.Object(id=gid))
            except Exception:
                pass

            bot.tree.add_command(
                cmd,
                guild=discord.Object(id=gid)
            )
