import re
import discord
from discord.ext import commands
from discord import app_commands
from pykakasi import kakasi


GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418

# 小文字は前文字と結合して1音
SMALL = set("ゃゅょぁぃぅぇぉャュョァィゥェォ")

CUT_HINTS = {"は", "が", "を", "に", "で", "と", "も", "の"}


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

    def is_natural_break(self, text: str) -> bool:
        return text[-1] in CUT_HINTS if text else False

    def build_kana_map(self, text: str):
        """
        元文 → かな変換 + 元文字位置マップ
        """
        hira = ""
        mapping = []

        for i, ch in enumerate(text):
            kana = self.converter.do(ch)
            hira += kana
            mapping.extend([i] * len(kana))

        return hira, mapping

    # =========================
    # 川柳検出
    # =========================
    def detect_senryu(self, original_text: str):
        cleaned_orig = re.sub(r"\s+", "", original_text)
        cleaned_orig = re.sub(r"[。、！!？?・…ｗwW,，]", "", cleaned_orig)

        if not cleaned_orig:
            return None

        hira, mapping = self.build_kana_map(cleaned_orig)

        mora = self.split_mora(hira)

        candidates = []

        for start in range(len(mora)):
            end = start + 17
            if end > len(mora):
                break

            chunk = mora[start:end]

            first_m = "".join(chunk[:5])
            second_m = "".join(chunk[5:12])
            third_m = "".join(chunk[12:17])

            # 元文の位置へ逆変換
            raw_start = mapping[start]
            raw_end = mapping[end - 1] + 1

            raw_chunk = cleaned_orig[raw_start:raw_end]

            score = 0
            if self.is_natural_break(first_m):
                score += 2
            if self.is_natural_break(second_m):
                score += 2

            candidates.append((score, raw_chunk))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, raw_chunk = candidates[0]

        # 表示は元文ベースで自然に3分割
        first = raw_chunk[:len(raw_chunk)//3]
        second = raw_chunk[len(raw_chunk)//3:len(raw_chunk)*2//3]
        third = raw_chunk[len(raw_chunk)*2//3:]

        return first, second, third

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
