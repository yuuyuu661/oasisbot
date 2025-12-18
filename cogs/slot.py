import random
import asyncio
import os
from io import BytesIO

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
ASSET_DIR = os.path.join(BASE_DIR, "assets", "slot")
CACHE_DIR = os.path.join(ASSET_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# =====================================================
# スロット素材
# =====================================================
SLOT_IMAGES = {
    "SMALL": "atari.png",
    "BIG": "daatari.png",
    "END": "shuryo.png",
}

# =====================================================
# 素材キャッシュ
# =====================================================
SLOT_IMAGE_CACHE: dict[str, Image.Image] = {}

def prepare_slot_images():
    for kind, fname in SLOT_IMAGES.items():
        path = os.path.join(ASSET_DIR, fname)
        img = Image.open(path).convert("RGBA")
        SLOT_IMAGE_CACHE[kind] = img.resize((300, 300), Image.LANCZOS)

# =====================================================
# GIF生成（ジャンボ方式・高速）
# =====================================================
async def generate_slot_gif(kind: str, duration: float = 4.0) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{kind.lower()}.gif")
    if os.path.exists(cache_path):
        return cache_path

    width, height = 900, 300
    fps = 12
    frames = int(duration * fps)

    imgs = SLOT_IMAGE_CACHE
    kinds = list(imgs.keys())

    gif_frames = []

    for i in range(frames):
        frame = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        if i < frames - 4:
            reel = [random.choice(kinds) for _ in range(3)]
        else:
            reel = [kind, kind, kind]

        for col in range(3):
            frame.paste(imgs[reel[col]], (col * 300, 0), imgs[reel[col]])

        draw = ImageDraw.Draw(frame)
        draw.rectangle(
            [0, 0, width - 1, height - 1],
            outline=(255, 215, 0, 255),
            width=6
        )

        gif_frames.append(frame)

    imageio.mimsave(cache_path, gif_frames, format="GIF", fps=fps)
    return cache_path

# =====================================================
# 開始パネル Embed 生成
# =====================================================
def build_slot_embed(rate: int, fee: int, players: dict) -> discord.Embed:
    if players:
        player_text = "\n".join([f"・<@{uid}>" for uid in players.keys()])
    else:
        player_text = "・（まだいません）"

    embed = discord.Embed(
        title="🎰 スロット開始！",
        description=(
            f"レート：{rate} rrc\n"
            f"参加費：{fee} rrc\n\n"
            "📜 **ルール・確率**\n"
            f"1/10 大当たり：+{rate * 10} rrc\n"
            f"8/10 当たり　：+{rate} rrc\n"
            "1/10 終了　　：全額支払い\n\n"
            "👥 **参加者**\n"
            f"{player_text}\n\n"
            "👇 **下記の参加ボタンから参加してください**"
        ),
        color=0xF1C40F
    )
    return embed

# =====================================================
# View
# =====================================================
class JoinView(discord.ui.View):
    def __init__(self, cog, cid):
        super().__init__(timeout=None)
        self.cog = cog
        self.cid = cid

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, _):
        await self.cog.handle_join(interaction, self.cid)

    @discord.ui.button(label="開始", style=discord.ButtonStyle.danger)
    async def start(self, interaction: discord.Interaction, _):
        await self.cog.handle_start(interaction, self.cid)


class SpinView(discord.ui.View):
    def __init__(self, cog, cid):
        super().__init__(timeout=None)
        self.cog = cog
        self.cid = cid

    @discord.ui.button(label="🎰 スピン", style=discord.ButtonStyle.primary)
    async def spin(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        await self.cog.handle_spin(interaction, self.cid)

# =====================================================
# Cog 本体
# =====================================================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        prepare_slot_images()

    # -------------------------------------------------
    # /スロット
    # -------------------------------------------------
    @app_commands.command(name="スロット", description="VC参加型スロットを開始します")
    @app_commands.describe(rate="当たりレート", fee="参加費")
    async def slot(self, interaction: discord.Interaction, rate: int, fee: int):

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
            "players": {},
            "order": [],
            "turn": 0,
            "state": "JOIN",
        }

        embed = build_slot_embed(rate, fee, {})

        await interaction.response.send_message(
            embed=embed,
            view=JoinView(self, cid)
        )

        msg = await interaction.original_response()
        SLOT_SESSIONS[cid]["panel_message_id"] = msg.id

    # -------------------------------------------------
    # 参加
    # -------------------------------------------------
    async def handle_join(self, interaction, cid):
        s = SLOT_SESSIONS[cid]
        user = interaction.user

        if user.id in s["players"]:
            return await interaction.response.send_message("⚠️ すでに参加しています。", ephemeral=True)

        row = await self.bot.db.get_user(str(user.id), str(interaction.guild.id))
        if row["balance"] < s["fee"]:
            return await interaction.response.send_message("❌ 残高不足です。", ephemeral=True)

        await self.bot.db.remove_balance(str(user.id), str(interaction.guild.id), s["fee"])
        s["players"][user.id] = {"pool": 0}

        # ★ 参加者リスト更新
        try:
            msg = await interaction.channel.fetch_message(s["panel_message_id"])
            await msg.edit(embed=build_slot_embed(s["rate"], s["fee"], s["players"]))
        except Exception:
            pass

        await interaction.response.send_message("✅ 参加しました！", ephemeral=True)

    # -------------------------------------------------
    # 開始
    # -------------------------------------------------
    async def handle_start(self, interaction, cid):
        s = SLOT_SESSIONS[cid]

        if interaction.user.id != s["host"]:
            return await interaction.response.send_message("❌ 代表者のみ開始できます。", ephemeral=True)

        if len(s["players"]) < 2:
            return await interaction.response.send_message("⚠️ 2人以上必要です。", ephemeral=True)

        s["order"] = list(s["players"].keys())
        random.shuffle(s["order"])
        s["turn"] = 0
        s["state"] = "PLAY"

        await interaction.message.edit(view=None)
        await self.send_turn_panel(interaction.channel, cid)

    # -------------------------------------------------
    # スピン（以降は据え置き）
    # -------------------------------------------------
    async def handle_spin(self, interaction, cid):
        s = SLOT_SESSIONS[cid]
        uid = s["order"][s["turn"]]

        if interaction.user.id != uid:
            return await interaction.response.send_message("⛔ あなたの番ではありません。", ephemeral=True)

        roll = random.randint(1, 10)
        result = "END" if roll == 1 else "BIG" if roll == 2 else "SMALL"

        gif_path = await generate_slot_gif(result)
        file = discord.File(gif_path, filename="slot.gif")

        embed = discord.Embed(title="🎰 スロット回転中…")
        embed.set_image(url="attachment://slot.gif")

        await interaction.followup.send(file=file, embed=embed)

        await asyncio.sleep(8)

        rate = s["rate"]
        player = s["players"][uid]

        if result == "END":
            await self.handle_end(interaction.channel, cid, uid)
            return

        gain = rate * 10 if result == "BIG" else rate
        player["pool"] += gain

        total_pool = sum(p["pool"] for p in s["players"].values())

        await interaction.followup.send(
            f"🎉 **{interaction.user.display_name} "
            f"{'大当たり' if result == 'BIG' else '小当たり'}！！ +{gain}rrc**\n"
            f"💰 現在総額：{total_pool}rrc（参加費除外）",
        )

        s["turn"] = (s["turn"] + 1) % len(s["order"])
        await self.send_turn_panel(interaction.channel, cid)
# -------------------------------------------------
# 終了処理（残高不足チェック付き・安全版）
# -------------------------------------------------
async def handle_end(self, channel, cid, loser_id):
    s = SLOT_SESSIONS[cid]
    guild = channel.guild

    # ----------------------------
    # 分配額計算
    # ----------------------------
    entry_pool = s["fee"] * len(s["players"])
    win_pool = sum(p["pool"] for p in s["players"].values())
    total = entry_pool + win_pool

    survivors = [uid for uid in s["players"] if uid != loser_id]

    # 念のため
    if not survivors:
        await channel.send("💥 終了！分配対象がいないため清算なし。")
        del SLOT_SESSIONS[cid]
        return

    share = total // len(survivors)

    # ----------------------------
    # ★ 残高不足チェック（ここが重要）
    # ----------------------------
    shortage_users = []

    for uid in survivors:
        row = await self.bot.db.get_user(str(uid), str(guild.id))
        if row["balance"] < 0:
            shortage_users.append(uid)

    # 1人でも不足していたら清算中止
    if shortage_users:
        names = ", ".join(f"<@{u}>" for u in shortage_users)
        await channel.send(
            "💥 **終了！**\n"
            "⚠ **清算失敗**\n"
            f"{names} の残高が不足しています。\n"
            "今回は通貨の増減は行われませんでした。"
        )
        del SLOT_SESSIONS[cid]
        return

    # ----------------------------
    # ★ 通常清算
    # ----------------------------
    for uid in survivors:
        await self.bot.db.add_balance(
            str(uid),
            str(guild.id),
            share
        )

    loser = guild.get_member(loser_id)

    await channel.send(
        f"💥 **終了！**\n"
        f"破産者：{loser.mention}\n"
        f"🎁 総分配額：{total}rrc\n"
        f"👥 1人あたり：{share}rrc"
    )

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
            except Exception:
                pass
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))


