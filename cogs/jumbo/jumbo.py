import discord
from discord.ext import commands
from discord import app_commands

from .jumbo_db import JumboDB


class JumboCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)

    # ================================
    # /年末ジャンボ設定
    # ================================
    @app_commands.command(
        name="年末ジャンボ設定",
        description="当選番号と各等賞の賞金を設定します（管理者専用）"
    )
    @app_commands.describe(
        winning_number="当選番号（6桁）",
        prize_1="1等の賞金",
        prize_2="2等の賞金",
        prize_3="3等の賞金",
        prize_4="4等の賞金",
        prize_5="5等の賞金",
    )
    async def jumbo_set_prize(
        self,
        interaction: discord.Interaction,
        winning_number: str,
        prize_1: int,
        prize_2: int,
        prize_3: int,
        prize_4: int,
        prize_5: int,
    ):
        await interaction.response.send_message(
            "🎯 Slash 登録テスト成功！",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(JumboCog(bot))
