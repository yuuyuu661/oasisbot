import random
import asyncio
import os

import discord
from discord.ext import commands
from discord import app_commands

import imageio
from PIL import Image, ImageDraw

# =====================================================
# セッション管理
# =====================================================
SLOT_SESSIONS: dict[int, dict] = {}

# =====================================================
# パス設定
# =====================================================
BASE_DIR = os.path.dirname(__file__)
SLOT_ASSET_DIR = os.path.join(BASE_DIR, "assets", "slot")
CACHE_DIR = os.path.join(SLOT_ASSET_DIR, "cache")

SLOT_IMAGES = {
    "SMALL": "atari.png",
    "BIG": "daatari.png",
    "END": "shuryo.png",
}

# =====================================================
# 画像ロード
# =====================================================
def load_slot_image(kind: str) -> Image.Image:
    path = os.path.join(SLOT_ASSET_DIR, SLOT_IMAGES[kind])
    img = Image.open(path).convert("RGBA")
    return img.resize((300, 300), Image.LANCZOS)

# =====================================================
# ★ 3レーンGIF生成（事前生成）
# =====================================================
def generate_slot_gif_cached(result_kind: str, duration: float = 4.0):
    os.makedirs(CACHE_DIR, exist_ok=True)
    out_path = os.path.join(CACHE_DIR, f"{result_kind.lower()}.gif")

    if os.path.exists(out_path):
        return  # 既にあれば作らない

    width, height = 900, 300
    columns = 3
    fps = 15
    frames = int(duration * fps)

    gif_frames = []

    for frame_index in range(frames):
        frame = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        for col in range(columns):
            if frame_index < frames - 5:
                kind = random.choice(list(SLOT_IMAGES.keys()))
            else:
                kind = result_kind

            img = load_slot_image(kind)
            frame.paste(img, (col * 300, 0), img)

        # 金枠
        draw = ImageDraw.Draw(frame)
        draw.rectangle(
            [0, 0, width - 1, height - 1],
            outline=(255, 215, 0, 255),
            width=6
        )

        gif_frames.append(frame)

    imageio.mimsave(out_path, gif_frames, format="GIF", fps=fps)

# =====================================================
# View
# =====================================================
class JoinView(discord.ui.View):
    def __init__(self, cog, channel_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, interaction, _):
        await self.cog.handle_join(interaction, self.channel_id)

    @discord.ui.button(label="開始", style=discord.ButtonStyle.danger)
    async def start(self, interaction, _):
        await self.cog.handle_start(interaction, self.channel_id)


class SpinView(discord.ui.View):
    def __init__(self, cog, channel_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="🎰 スピン", style=discord.ButtonStyle.primary)
    async def spin(self, interaction, _):
        await self.cog.handle_spin(interaction, self.channel_id)

# =====================================================
# Cog 本体
# =====================================================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.prepare_gifs()

    # -------------------------------------------------
    # 起動時にGIF事前生成
    # -------------------------------------------------
    def prepare_gifs(self):
        for kind in SLOT_IMAGES.keys():
            generate_slot_gif_cached(kind)

    # -------------------------------------------------
    @app_commands.command(name="スロット", description="VC参加型スロットを開始します")
    @app_commands.describe(rate="当たりレート", fee="参加費")
    async def slot(self, interaction: discord.Interaction, rate: int, fee: int):

        if not interaction.user.voice:
            return await interaction.response.send_message(
                "❌ VCに参加してください。",
                ephemeral=True
            )

        cid = interaction.channel.id
        if cid in SLOT_SESSIONS:
            return await interaction.response.send_message(
                "⚠️ すでに進行中です。",
                ephemeral=True
            )

        SLOT_SESSIONS[cid] = {
            "vc_id": interaction.user.voice.channel.id,
            "host": interaction.user.id,
            "rate": rate,
            "fee": fee,
            "players": {},
            "order": [],
            "turn": 0,
            "state": "JOIN",
        }

        embed = discord.Embed(
            title="🎰 スロット開始！",
            description=f"レート：{rate}\n参加費：{fee}",
            color=0xF1C40F
        )

        await interaction.response.send_message(
            embed=embed,
            view=JoinView(self, cid)
        )

    # -------------------------------------------------
    async def handle_join(self, interaction, cid):
        s = SLOT_SESSIONS[cid]

        if interaction.user.id in s["players"]:
            return await interaction.response.send_message(
                "⚠️ すでに参加しています。",
                ephemeral=True
            )

        row = await self.bot.db.get_user(
            str(interaction.user.id),
            str(interaction.guild.id)
        )

        if row["balance"] < s["fee"]:
            return await interaction.response.send_message(
                "❌ 残高不足です。",
                ephemeral=True
            )

        await self.bot.db.remove_balance(
            str(interaction.user.id),
            str(interaction.guild.id),
            s["fee"]
        )

        s["players"][interaction.user.id] = 0
        await interaction.response.send_message("✅ 参加しました！", ephemeral=True)

    # -------------------------------------------------
    async def handle_start(self, interaction, cid):
        s = SLOT_SESSIONS[cid]

        if interaction.user.id != s["host"]:
            return

        if len(s["players"]) < 2:
            return await interaction.response.send_message(
                "⚠️ 2人以上必要です。",
                ephemeral=True
            )

        s["order"] = list(s["players"].keys())
        random.shuffle(s["order"])
        s["turn"] = 0
        s["state"] = "PLAY"

        await interaction.message.edit(view=None)
        await self.send_turn_panel(interaction.channel, cid)

    # -------------------------------------------------
    async def handle_spin(self, interaction, cid):
        s = SLOT_SESSIONS[cid]
        uid = s["order"][s["turn"]]

        if interaction.user.id != uid:
            return await interaction.response.send_message(
                "⛔ あなたの番ではありません。",
                ephemeral=True
            )

        await interaction.response.defer()

        roll = random.randint(1, 10)
        result = "END" if roll == 1 else "BIG" if roll == 2 else "SMALL"

        gif_path = os.path.join(CACHE_DIR, f"{result.lower()}.gif")
        file = discord.File(gif_path, filename="slot.gif")

        embed = discord.Embed(title="🎰 スロット結果！")
        embed.set_image(url="attachment://slot.gif")

        await interaction.followup.send(file=file, embed=embed)

        if result == "END":
            await self.handle_end(interaction.channel, cid, uid)
            return

        s["players"][uid] += s["rate"] * (10 if result == "BIG" else 1)
        s["turn"] = (s["turn"] + 1) % len(s["order"])

        await self.send_turn_panel(interaction.channel, cid)

    # -------------------------------------------------
    async def handle_end(self, channel, cid, loser_id):
        s = SLOT_SESSIONS[cid]
        guild = channel.guild

        total = s["fee"] + s["players"][loser_id]
        survivors = [u for u in s["players"] if u != loser_id]

        share = total // len(survivors)
        for u in survivors:
            await self.bot.db.add_balance(str(u), str(guild.id), share)

        await channel.send("💥 **終了！ 清算完了！**")
        del SLOT_SESSIONS[cid]

    # -------------------------------------------------
    async def send_turn_panel(self, channel, cid):
        s = SLOT_SESSIONS[cid]
        uid = s["order"][s["turn"]]
        member = channel.guild.get_member(uid)

        await channel.send(
            f"👉 **{member.display_name} の番です！**",
            view=SpinView(self, cid)
        )

# =====================================================
# setup
# =====================================================
async def setup(bot: commands.Bot):
    cog = SlotCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            try:
                bot.tree.remove_command(cmd.name, guild=discord.Object(id=gid))
            except:
                pass
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
