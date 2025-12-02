# cogs/init.py
import discord
from discord.ext import commands
from discord import app_commands

OWNER_ID = 716667546241335328  # ゆう専用

class InitCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="初期設定", description="初期設定を行います（ゆう専用）")
    async def init(self, interaction: discord.Interaction,
                   通貨ログ: discord.TextChannel,
                   管理ログ: discord.TextChannel,
                   給料ログ: discord.TextChannel,
                   通貨単位: str,
                   管理者ロール: discord.Role):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌権限がありません", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.bot.db.ensure_settings(guild_id)

        await self.bot.db.update_settings(
            guild_id,
            admin_roles=[str(管理者ロール.id)],
            log_pay=str(通貨ログ.id),
            log_manage=str(管理ログ.id),
            log_salary=str(給料ログ.id),
            currency_unit=通貨単位
        )

        await interaction.response.send_message(
            f"🔧 初期設定を更新しました！\n"
            f"・通貨ログ: {通貨ログ.mention}\n"
            f"・管理ログ: {管理ログ.mention}\n"
            f"・給料ログ: {給料ログ.mention}\n"
            f"・管理者ロール: {管理者ロール.mention}"
        )

async def setup(bot):
    cog = THIS_COG_CLASS(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))

