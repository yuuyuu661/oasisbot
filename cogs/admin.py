# cogs/admin.py
import discord
from discord.ext import commands
from discord import app_commands

from paginator import Paginator
from logger import log_manage


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------
    # /残高設定
    # --------------------------
    @app_commands.command(name="残高設定", description="ユーザーの残高を設定・増加・減少（管理者）")
    async def set_balance(self, interaction: discord.Interaction, user: discord.User, amount: int, mode: str):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        uid = str(user.id)

        if mode == "設定":
            await self.bot.db.set_balance(uid, amount)
        elif mode == "増加":
            await self.bot.db.add_balance(uid, amount)
        elif mode == "減少":
            await self.bot.db.remove_balance(uid, amount)
        else:
            return await interaction.response.send_message("モードは 設定 / 増加 / 減少 から選んでください")

        new_bal = (await self.bot.db.get_user(uid))["balance"]

        await log_manage(self.bot, settings, str(interaction.user.id), uid, mode, amount, new_bal)

        await interaction.response.send_message(
            f"📝 <@{uid}> の残高を **{mode}** しました。\n現在：**{new_bal}{unit}**"
        )

    # --------------------------
    # /残高一覧
    # --------------------------
    @app_commands.command(name="残高一覧", description="全ユーザーの残高ランキング（管理者）")
    async def list_balances(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        rows = await self.bot.db.get_all_balances()
        if not rows:
            return await interaction.response.send_message("データがありません。")

        pages = []
        for i in range(0, len(rows), 10):
            embed = discord.Embed(title="💰 残高一覧（上位順）", color=0x00FF88)

            for row in rows[i:i+10]:
                embed.add_field(
                    name=f"<@{row['user_id']}>",
                    value=f"{row['balance']}{unit}",
                    inline=False
                )

            pages.append(embed)

        paginator = Paginator(pages)
        await interaction.response.send_message(embed=pages[0], view=paginator)


async def setup(bot):
    cog = AdminCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))


