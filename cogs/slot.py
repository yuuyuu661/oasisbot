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
        reel = (
            [random.choice(kinds) for _ in range(3)]
            if i < frames - 4
            else [kind] * 3
        )

        for col in range(3):
            frame.paste(
                imgs[reel[col]],
                (col * 300, 0),
                imgs[reel[col]]
            )

        draw = ImageDraw.Draw(frame)
        draw.rectangle(
            [0, 0, width - 1, height - 1],
            outline=(255, 215, 0, 255),
            width=6
        )
        gif_frames.append(frame)

    imageio.mimsave(
        cache_path,
        gif_frames,
        format="GIF",
        fps=fps
    )
    return cache_path


# =====================================================
# Embed
# =====================================================
def build_slot_embed(rate: int, fee: int, players: dict) -> discord.Embed:
    player_text = (
        "\n".join([f"・<@{uid}>" for uid in players])
        or "・（まだいません）"
    )

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
    embed.add_field(
        name="👥 参加者",
        value=player_text,
        inline=False
    )
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
        options=[
            discord.SelectOption(label=str(r), value=str(r))
            for r in RATE_OPTIONS
        ]
    )
    async def select_rate(self, interaction: discord.Interaction, select):
        rate = int(select.values[0])
        fee = rate * 2

        await interaction.response.edit_message(
            content="🎰 スロットを作成しました！",
            view=None
        )
        await self.cog.create_slot_session(
            interaction,
            rate,
            fee
        )


class JoinView(discord.ui.View):
    def __init__(self, cog, cid):
        super().__init__(timeout=None)
        self.cog = cog
        self.cid = cid

    @discord.ui.button(
        label="参加",
        style=discord.ButtonStyle.success
    )
    async def join(self, interaction, _):
        await self.cog.handle_join(
            interaction,
            self.cid
        )

    @discord.ui.button(
        label="開始",
        style=discord.ButtonStyle.danger
    )
    async def start(self, interaction, _):
        await self.cog.handle_start(
            interaction,
            self.cid
        )


class SpinView(discord.ui.View):
    def __init__(self, cog, cid):
        super().__init__(timeout=None)
        self.cog = cog
        self.cid = cid

    @discord.ui.button(
        label="🎰 スピン",
        style=discord.ButtonStyle.primary
    )
    async def spin(self, interaction, _):
        await interaction.response.defer()
        await self.cog.handle_spin(
            interaction,
            self.cid
        )


# =====================================================
# Cog
# =====================================================
class SlotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        prepare_slot_images()

    # ---------------------------------------------
    # ★ パネル存在確認（リセット型保険）
    # ---------------------------------------------
    async def _ensure_panel_exists(
        self,
        channel: discord.TextChannel,
        cid: int
    ) -> bool:
        s = SLOT_SESSIONS.get(cid)
        if not s:
            return False

        panel_id = s.get("panel_message_id")
        if not panel_id:
            SLOT_SESSIONS.pop(cid, None)
            return False

        try:
            await channel.fetch_message(panel_id)
            return True

        except (discord.NotFound, discord.Forbidden):
            SLOT_SESSIONS.pop(cid, None)
            return False

        except discord.HTTPException:
            return True

    # ---------------------------------------------
    # /スロット
    # ---------------------------------------------
    @app_commands.command(
        name="スロット",
        description="VC参加型スロットを開始します"
    )
    async def slot(self, interaction: discord.Interaction):
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
            return

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
        msg = await interaction.channel.send(
            embed=embed,
            view=JoinView(self, cid)
        )
        SLOT_SESSIONS[cid]["panel_message_id"] = msg.id

    async def handle_join(self, interaction, cid):
        if not await self._ensure_panel_exists(interaction.channel, cid):
            return await interaction.response.send_message(
                "⚠️ パネルが削除されていたため、スロットをリセットしました。\n"
                "もう一度 **/スロット** から作成してください。",
                ephemeral=True
            )

        s = SLOT_SESSIONS[cid]
        user = interaction.user

        if not user.voice or user.voice.channel.id != s["vc_id"]:
            return await interaction.response.send_message(
                "❌ 指定VCに参加していません。",
                ephemeral=True
            )

        if user.id in s["players"]:
            return await interaction.response.send_message(
                "⚠️ すでに参加しています。",
                ephemeral=True
            )

        row = await self.bot.db.get_user(
            str(user.id),
            str(interaction.guild.id)
        )

        if row["balance"] < s["rate"] * 100:
            return await interaction.response.send_message(
                f"❌ 残高 {s['rate'] * 100}rrc 以上必要です。",
                ephemeral=True
            )

        await self.bot.db.remove_balance(
            str(user.id),
            str(interaction.guild.id),
            s["fee"]
        )

        s["players"][user.id] = {"pool": 0}

        try:
            msg = await interaction.channel.fetch_message(
                s["panel_message_id"]
            )
            await msg.edit(
                embed=build_slot_embed(
                    s["rate"],
                    s["fee"],
                    s["players"]
                )
            )
        except Exception:
            pass

        await interaction.response.send_message(
            "✅ 参加しました！",
            ephemeral=True
        )

    # -------------------------------------------------
    # /スロット参加解除
    # -------------------------------------------------
    @app_commands.command(
        name="スロット参加解除",
        description="スロット参加を解除します（自分 or 管理者指定）"
    )
    @app_commands.describe(
        user="解除するユーザー（省略時は自分）"
    )
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

        if not await self._ensure_panel_exists(interaction.channel, cid):
            return await interaction.response.send_message(
                "⚠️ パネルが削除されていたため、スロットは既にリセットされています。",
                ephemeral=True
            )

        s = SLOT_SESSIONS[cid]
        target = user or interaction.user

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

        await interaction.response.send_message(
            "✅ スロットを終了しました。",
            ephemeral=True
        )


# =====================================================
# setup
# =====================================================
async def setup(bot):
    cog = SlotCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(
                cmd,
                guild=discord.Object(id=gid)
            )
