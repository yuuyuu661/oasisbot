import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image
import os
import tempfile

# ==================================================
# セッション管理
# ==================================================
# channel_id -> session
SLOT_SESSIONS: dict[int, dict] = {}

# ==================================================
# スロット素材
# ==================================================
SLOT_IMAGES = {
    "SMALL": "cogs/assets/slot/atari.png",
    "BIG":   "cogs/assets/slot/daatari.png",
    "END":   "cogs/assets/slot/shuryo.png",
}
SPIN_KEYS = ["SMALL", "BIG", "END"]


# ==================================================
# 3レーン画像合成
# ==================================================
def make_3reel_image(left: str, center: str, right: str) -> str:
    img_l = Image.open(left)
    img_c = Image.open(center)
    img_r = Image.open(right)

    w, h = img_l.size
    canvas = Image.new("RGBA", (w * 3, h))
    canvas.paste(img_l, (0, 0))
    canvas.paste(img_c, (w, 0))
    canvas.paste(img_r, (w * 2, 0))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    canvas.save(tmp.name)
    return tmp.name


# ==================================================
# View
# ==================================================
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


# ==================================================
# Cog
# ==================================================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ----------------------------------------------
    # /スロット
    # ----------------------------------------------
    @app_commands.command(name="スロット", description="VC参加型スロットを開始します")
    @app_commands.describe(rate="当たりレート", fee="参加費")
    async def slot(self, interaction: discord.Interaction, rate: int, fee: int):
        if interaction.guild is None:
            return await interaction.response.send_message("サーバー内専用です。", ephemeral=True)

        if not interaction.user.voice:
            return await interaction.response.send_message("❌ VCに参加してください。", ephemeral=True)

        cid = interaction.channel.id
        if cid in SLOT_SESSIONS:
            return await interaction.response.send_message("⚠️ すでに進行中です。", ephemeral=True)

        SLOT_SESSIONS[cid] = {
            "vc_id": interaction.user.voice.channel.id,
            "host": interaction.user.id,
            "rate": rate,
            "fee": fee,
            "players": {},   # uid -> pool
            "order": [],
            "turn": 0,
            "state": "JOIN",
        }

        embed = discord.Embed(
            title="🎰 スロット開始！",
            description=f"レート：{rate}\n参加費：{fee}\n\n👇 参加してください",
            color=0xF1C40F
        )

        await interaction.response.send_message(embed=embed, view=JoinView(self, cid))

    # ----------------------------------------------
    # 参加
    # ----------------------------------------------
    async def handle_join(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS.get(channel_id)
        if not session:
            return await interaction.response.send_message("❌ セッションなし", ephemeral=True)

        user = interaction.user
        guild = interaction.guild

        if not user.voice or user.voice.channel.id != session["vc_id"]:
            return await interaction.response.send_message("❌ 指定VCにいません", ephemeral=True)

        if user.id in session["players"]:
            return await interaction.response.send_message("⚠️ 参加済み", ephemeral=True)

        row = await self.bot.db.get_user(str(user.id), str(guild.id))
        if row["balance"] < session["fee"]:
            return await interaction.response.send_message("❌ 残高不足", ephemeral=True)

        await self.bot.db.remove_balance(str(user.id), str(guild.id), session["fee"])
        session["players"][user.id] = 0

        await interaction.response.send_message("✅ 参加完了！", ephemeral=True)

    # ----------------------------------------------
    # 開始
    # ----------------------------------------------
    async def handle_start(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS[channel_id]

        if interaction.user.id != session["host"]:
            return await interaction.response.send_message("❌ 代表者のみ", ephemeral=True)

        if len(session["players"]) < 2:
            return await interaction.response.send_message("⚠️ 2人以上必要", ephemeral=True)

        order = list(session["players"].keys())
        random.shuffle(order)

        session["order"] = order
        session["turn"] = 0
        session["state"] = "PLAY"

        await interaction.message.edit(view=None)
        await self.send_turn(interaction.channel, channel_id)

    # ----------------------------------------------
    # スピン（3レーン演出）
    # ----------------------------------------------
    async def handle_spin(self, interaction: discord.Interaction, channel_id: int):
        session = SLOT_SESSIONS[channel_id]
        uid = session["order"][session["turn"]]

        if interaction.user.id != uid:
            return await interaction.response.send_message("⛔ あなたの番ではありません", ephemeral=True)

        await interaction.response.defer()

        msg = await interaction.followup.send("🎰 回転中…")

        # --- 演出 ---
        for _ in range(5):
            k1, k2, k3 = random.choices(SPIN_KEYS, k=3)
            img = make_3reel_image(
                SLOT_IMAGES[k1],
                SLOT_IMAGES[k2],
                SLOT_IMAGES[k3]
            )
            file = discord.File(img, filename="slot.png")
            embed = discord.Embed()
            embed.set_image(url="attachment://slot.png")
            await msg.edit(embed=embed, attachments=[file])
            os.unlink(img)
            await asyncio.sleep(0.35)

        # --- 抽選 ---
        roll = random.randint(1, 10)
        if roll == 1:
            result = "END"
        elif roll == 2:
            result = "BIG"
        else:
            result = "SMALL"

        final_img = make_3reel_image(
            SLOT_IMAGES[result],
            SLOT_IMAGES[result],
            SLOT_IMAGES[result]
        )
        final_file = discord.File(final_img, filename="slot.png")
        final_embed = discord.Embed(title="🎰 結果！")
        final_embed.set_image(url="attachment://slot.png")

        await msg.edit(embed=final_embed, attachments=[final_file])
        os.unlink(final_img)

        rate = session["rate"]

        if result == "END":
            await self.handle_end(interaction.channel, channel_id, uid)
            return

        gain = rate * 10 if result == "BIG" else rate
        session["players"][uid] += gain

        session["turn"] = (session["turn"] + 1) % len(session["order"])

        await interaction.followup.send(
            f"{interaction.user.mention}\n"
            f"{'🎉 大当たり' if result=='BIG' else '✨ 小当たり'} +{gain}",
            view=SpinView(self, channel_id)
        )

        await self.send_turn(interaction.channel, channel_id)

    # ----------------------------------------------
    # 終了処理
    # ----------------------------------------------
    async def handle_end(self, channel: discord.TextChannel, channel_id: int, loser_id: int):
        session = SLOT_SESSIONS[channel_id]
        guild = channel.guild

        total = session["fee"] + session["players"][loser_id]
        survivors = [u for u in session["players"] if u != loser_id]

        if survivors:
            share = total // len(survivors)
            for uid in survivors:
                await self.bot.db.add_balance(str(uid), str(guild.id), share)

        loser = guild.get_member(loser_id)
        await channel.send(
            f"💥 **終了！**\n"
            f"破産者：{loser.mention}\n"
            f"失った額：{total}"
        )

        del SLOT_SESSIONS[channel_id]

    # ----------------------------------------------
    # ターン表示
    # ----------------------------------------------
    async def send_turn(self, channel: discord.TextChannel, channel_id: int):
        session = SLOT_SESSIONS[channel_id]
        uid = session["order"][session["turn"]]
        member = channel.guild.get_member(uid)

        await channel.send(
            f"👉 **{member.display_name} の番です！**",
            view=SpinView(self, channel_id)
        )


# ==================================================
# setup（ギルド紐付け方式）
# ==================================================
async def setup(bot: commands.Bot):
    cog = SlotCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            try:
                bot.tree.remove_command(cmd.name, guild=discord.Object(id=gid))
            except Exception:
                pass
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
