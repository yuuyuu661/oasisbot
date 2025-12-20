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

RATE_OPTIONS = [500, 1000, 3000, 5000, 10000]

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

SLOT_IMAGE_CACHE: dict[str, Image.Image] = {}

def prepare_slot_images():
    for kind, fname in SLOT_IMAGES.items():
        path = os.path.join(ASSET_DIR, fname)
        img = Image.open(path).convert("RGBA")
        SLOT_IMAGE_CACHE[kind] = img.resize((300, 300), Image.LANCZOS)

# =====================================================
# GIF生成
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
        reel = [random.choice(kinds) for _ in range(3)] if i < frames - 4 else [kind] * 3

        for col in range(3):
            frame.paste(imgs[reel[col]], (col * 300, 0), imgs[reel[col]])

        draw = ImageDraw.Draw(frame)
        draw.rectangle([0, 0, width - 1, height - 1], outline=(255, 215, 0, 255), width=6)
        gif_frames.append(frame)

    imageio.mimsave(cache_path, gif_frames, format="GIF", fps=fps)
    return cache_path

# =====================================================
# Embed
# =====================================================
def build_slot_embed(rate: int, fee: int, players: dict) -> discord.Embed:
    player_text = "\n".join([f"・<@{uid}>" for uid in players]) or "・（まだいません）"

    embed = discord.Embed(
        title="🎰 スロット開始！",
        description=(
            f"レート：{rate} rrc\n"
            f"参加費：{fee} rrc\n"
            f"参加条件：残高 **{rate * 100} rrc 以上**\n\n"
            "📜 **ルール**\n"
            f"1/10 大当たり：+{rate * 10} rrc\n"
            f"8/10 当たり　：+{rate} rrc\n"
            "1/10 終了　　：全額支払い"
        ),
        color=0xF1C40F
    )
    embed.add_field(name="👥 参加者", value=player_text, inline=False)
    return embed

# =====================================================
# View
# =====================================================
class RateSelectView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog

    @discord.ui.select(
        placeholder="レートを選択してください",
        options=[discord.SelectOption(label=str(r), value=str(r)) for r in RATE_OPTIONS]
    )
    async def select_rate(self, interaction: discord.Interaction, select):
        rate = int(select.values[0])
        fee = rate * 2
        await interaction.response.edit_message(content="🎰 スロットを作成しました！", view=None)
        await self.cog.create_slot_session(interaction, rate, fee)

class JoinView(discord.ui.View):
    def __init__(self, cog, cid):
        super().__init__(timeout=None)
        self.cog = cog
        self.cid = cid

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, interaction, _):
        await self.cog.handle_join(interaction, self.cid)

    @discord.ui.button(label="開始", style=discord.ButtonStyle.danger)
    async def start(self, interaction, _):
        await self.cog.handle_start(interaction, self.cid)

class SpinView(discord.ui.View):
    def __init__(self, cog, cid):
        super().__init__(timeout=None)
        self.cog = cog
        self.cid = cid

    @discord.ui.button(label="🎰 スピン", style=discord.ButtonStyle.primary)
    async def spin(self, interaction, _):
        await interaction.response.defer()
        await self.cog.handle_spin(interaction, self.cid)

# =====================================================
# Cog
# =====================================================
class SlotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        prepare_slot_images()

    @app_commands.command(name="スロット", description="VC参加型スロットを開始します")
    async def slot(self, interaction: discord.Interaction):
        # ★ 先に defer（超重要）
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.voice:
            return await interaction.followup.send(
                "❌ VCに参加してください。",
                ephemeral=True
            )

        await interaction.followup.send(
            "🎰 レートを選択してください",
            view=RateSelectView(self),
            ephemeral=True
        )

    async def create_slot_session(self, interaction, rate, fee):
        cid = interaction.channel.id
        if cid in SLOT_SESSIONS:
            SLOT_SESSIONS.pop(cid, None)

        SLOT_SESSIONS[cid] = {
            "vc_id": interaction.user.voice.channel.id,
            "host": interaction.user.id,
            "rate": rate,
            "fee": fee,
            "players": {},
            "order": [],
            "turn": 0,
            "state": "JOIN",
            "spinning": False,
        }

        embed = build_slot_embed(rate, fee, {})
        msg = await interaction.channel.send(embed=embed, view=JoinView(self, cid))
        SLOT_SESSIONS[cid]["panel_message_id"] = msg.id

    async def handle_join(self, interaction, cid):
        s = SLOT_SESSIONS[cid]
        user = interaction.user

        if not user.voice or user.voice.channel.id != s["vc_id"]:
            return await interaction.response.send_message("❌ 指定VCに参加していません。", ephemeral=True)

        if user.id in s["players"]:
            return await interaction.response.send_message("⚠️ すでに参加しています。", ephemeral=True)

        row = await self.bot.db.get_user(str(user.id), str(interaction.guild.id))

        if row["balance"] < s["rate"] * 100:
            return await interaction.response.send_message(
                f"❌ 残高 {s['rate'] * 100}rrc 以上必要です。",
                ephemeral=True
            )

        await self.bot.db.remove_balance(str(user.id), str(interaction.guild.id), s["fee"])
        s["players"][user.id] = {"pool": 0}

        try:
            msg = await interaction.channel.fetch_message(s["panel_message_id"])
            await msg.edit(embed=build_slot_embed(s["rate"], s["fee"], s["players"]))
        except Exception:
            pass

        await interaction.response.send_message("✅ 参加しました！", ephemeral=True)

    async def handle_start(self, interaction, cid):
        s = SLOT_SESSIONS[cid]

        if interaction.user.id != s["host"]:
            return await interaction.response.send_message("❌ 代表者のみ開始できます。", ephemeral=True)

        if len(s["players"]) < 2:
            return await interaction.response.send_message("⚠️ 2人以上必要です。", ephemeral=True)

        s["order"] = list(s["players"])
        random.shuffle(s["order"])
        s["turn"] = 0
        s["state"] = "PLAY"

        await interaction.message.edit(view=None)
        await self.send_turn_panel(interaction.channel, cid)

    async def handle_spin(self, interaction, cid):
        s = SLOT_SESSIONS[cid]
        uid = s["order"][s["turn"]]

        if interaction.user.id != uid:
            return

        if s["spinning"]:
            return

            # ★ ここでボタンを消す
        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass

        s["spinning"] = True
        try:
            roll = random.randint(1, 10)
            result = "END" if roll == 1 else "BIG" if roll == 2 else "SMALL"

            gif = await generate_slot_gif(result)
            file = discord.File(gif, filename="slot.gif")
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
                f"💰 現在総額：{total_pool}rrc（参加費除外）"
            )

            s["turn"] = (s["turn"] + 1) % len(s["order"])
            await self.send_turn_panel(interaction.channel, cid)

        finally:
            s["spinning"] = False

    async def handle_end(self, channel, cid, loser_id):
        s = SLOT_SESSIONS[cid]
        guild = channel.guild

        entry_pool = s["fee"] * len(s["players"])
        win_pool = sum(p["pool"] for p in s["players"].values())
        total = entry_pool + win_pool

        survivors = [uid for uid in s["players"] if uid != loser_id]
        share = total // len(survivors)

        for uid in survivors:
            await self.bot.db.add_balance(str(uid), str(guild.id), share)

        loser = guild.get_member(loser_id)
        await channel.send(
            f"💥 **終了！**\n"
            f"破産者：{loser.mention}\n"
            f"🎁 総分配額：{total}rrc\n"
            f"👥 1人あたり：{share}rrc"
        )

        SLOT_SESSIONS.pop(cid, None)

    async def send_turn_panel(self, channel, cid):
        s = SLOT_SESSIONS[cid]
        uid = s["order"][s["turn"]]
        member = channel.guild.get_member(uid)
        await channel.send(f"👉 **{member.display_name} の番です！**", view=SpinView(self, cid))

# -------------------------------------------------
# /スロット参加解除
# -------------------------------------------------
    @app_commands.command(
        name="スロット参加解除",
        description="スロット参加を解除します（自分 or 管理者指定）"
    )
    @app_commands.describe(user="解除するユーザー（省略時は自分）")
    async def slot_leave(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None
    ):
        cid = interaction.channel.id

        if cid not in SLOT_SESSIONS:
            return await interaction.response.send_message(
                "❌ このチャンネルで進行中のスロットはありません。",
                ephemeral=True
            )

        s = SLOT_SESSIONS[cid]

        target = user or interaction.user

        # 管理者権限チェック（他人指定時）
        if user and user.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "❌ 他ユーザーを解除するには管理者権限が必要です。",
                    ephemeral=True
                )

        if target.id not in s["players"]:
            return await interaction.response.send_message(
                "⚠️ そのユーザーは参加していません。",
               ephemeral=True
            )

        # スピン中の本人は解除不可（事故防止）
        if s.get("spinning") and s["order"] and s["order"][s["turn"]] == target.id:
            return await interaction.response.send_message(
                "⏳ 現在スピン処理中のため解除できません。",
                ephemeral=True
            )

        # =====================================
        # ★ ここからが「修正2」の本体 ★
        # 参加中 → 全員返金してゲーム終了
        # =====================================
        refund = s["fee"]

        for uid in s["players"]:
            await self.bot.db.add_balance(
                str(uid),
                str(interaction.guild.id),
                refund
            )

        await interaction.channel.send(
            "🛑 **スロットがキャンセルされました。**\n"
            "💸 参加費は全員に返還されました。"
        )

        SLOT_SESSIONS.pop(cid, None)

        return await interaction.response.send_message(
            "✅ スロットを終了しました。",
            ephemeral=True
        )

        # --- players から削除 ---
        del s["players"][target.id]

        # --- order（ターン順）から削除 ---
        if target.id in s["order"]:
            idx = s["order"].index(target.id)
            s["order"].remove(target.id)

            # ターン補正
            if idx < s["turn"]:
                s["turn"] -= 1
            if s["turn"] >= len(s["order"]):
                s["turn"] = 0

        # --- パネル更新 ---
        try:
            msg = await interaction.channel.fetch_message(s["panel_message_id"])
            await msg.edit(
                embed=build_slot_embed(s["rate"], s["fee"], s["players"])
            )
        except Exception:
            pass

        await interaction.response.send_message(
            f"✅ **{target.display_name}** をスロット参加から解除しました。",
            ephemeral=True
        )


# ======================================================
# setup
# ======================================================

async def setup(bot):
    cog = SlotCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))


