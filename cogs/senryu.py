import re
import discord
from discord.ext import commands
from discord import app_commands


GUILD_ID = 1310885590094450739
ADMIN_ROLE_ID = 1310906528517062770

# 小文字は前文字と結合して1音
SMALL = set("ゃゅょぁぃぅぇぉャュョァィゥェォ")


class SenryuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.target_channels: set[int] = set()

    # =========================
    # 管理者：監視チャンネル設定
    # =========================
    @app_commands.command(name="川柳検出")
    @app_commands.describe(
        channel1="監視対象1",
        channel2="監視対象2",
        channel3="監視対象3",
        channel4="監視対象4",
        channel5="監視対象5",
    )
    async def setup_senryu(
        self,
        interaction: discord.Interaction,
        channel1: discord.TextChannel,
        channel2: discord.TextChannel | None = None,
        channel3: discord.TextChannel | None = None,
        channel4: discord.TextChannel | None = None,
        channel5: discord.TextChannel | None = None,
    ):
        # 管理者ロールチェック
        if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        channels = [channel1, channel2, channel3, channel4, channel5]
        self.target_channels = {c.id for c in channels if c is not None}

        mentions = "\n".join(c.mention for c in channels if c)

        await interaction.response.send_message(
            "🌸 **川柳検出を有効化しました！**\n\n"
            f"{mentions}",
            ephemeral=True
        )

    # =========================
    # モーラ分解
    # =========================
    def split_mora(self, text: str) -> list[str]:
        mora = []

        for ch in text:
            if ch in SMALL and mora:
                mora[-1] += ch
            else:
                mora.append(ch)

        return mora

    # =========================
    # 川柳検出（全文スキャン）
    # =========================
    def detect_senryu(self, text: str):
        # 空白・句読点・草を軽く除去
        cleaned = re.sub(r"\s+", "", text)
        cleaned = re.sub(r"[。、！!？?・…ｗwW]", "", cleaned)

        if not cleaned:
            return None

        mora = self.split_mora(cleaned)

        # 全文を最初から順にスキャン
        for start in range(len(mora)):
            if start + 17 > len(mora):
                break

            chunk = mora[start:start + 17]

            first = "".join(chunk[:5])
            second = "".join(chunk[5:12])
            third = "".join(chunk[12:17])

            # 最初に見つかった一句だけ返す
            return first, second, third

        return None

    # =========================
    # メッセージ監視
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
    await bot.add_cog(SenryuCog(bot))