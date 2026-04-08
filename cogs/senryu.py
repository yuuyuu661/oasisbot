import re
import discord
from discord.ext import commands
from discord import app_commands
from pykakasi import kakasi


GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418

# 小文字は前文字と結合して1音
SMALL = set("ゃゅょぁぃぅぇぉャュョァィゥェォ")


class SenryuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channels: set[int] = set()

        kks = kakasi()
        self.converter = kks.getConverter()

    # =========================
    # 管理者設定
    # =========================
    @app_commands.command(name="川柳検出")
    async def setup_senryu(
        self,
        interaction: discord.Interaction,
        channel1: discord.TextChannel,
        channel2: discord.TextChannel | None = None,
        channel3: discord.TextChannel | None = None,
    ):
        if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        channels = [channel1, channel2, channel3]
        self.target_channels = {c.id for c in channels if c}

        await interaction.response.send_message(
            "🌸 川柳検出ON",
            ephemeral=True
        )

    # =========================
    # モーラ分解
    # =========================
    def split_mora(self, text: str):
        mora = []
        for ch in text:
            if ch in SMALL and mora:
                mora[-1] += ch
            else:
                mora.append(ch)
        return mora

    # =========================
    # 川柳検出
    # =========================
    def detect_senryu(self, original_text: str):
        # 漢字をひらがな化
        hira = self.converter.do(original_text)

        cleaned = re.sub(r"\s+", "", hira)
        cleaned = re.sub(r"[。、！!？?・…ｗwW]", "", cleaned)

        mora = self.split_mora(cleaned)

        for start in range(len(mora)):
            if start + 17 > len(mora):
                break

            chunk = mora[start:start + 17]

            return (
                "".join(chunk[:5]),
                "".join(chunk[5:12]),
                "".join(chunk[12:17]),
            )

        return None

    # =========================
    # 監視
    # =========================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id not in self.target_channels:
            return

        result = self.detect_senryu(message.content)
        if not result:
            return

        first, second, third = result

        await message.channel.send(
            "🌸 **川柳を検出しました！！**\n\n"
            f"「{first}\n"
            f"　{second}\n"
            f"　　{third}」"
        )




async def setup(bot):
    cog = SenryuCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            try:
                bot.tree.add_command(cmd, guild=discord.Object(id=gid))
            except Exception:
                pass
