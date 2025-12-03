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
    @app_commands.command(name="残高一覧", description="全ユーザーの残高を上位順に表示します（管理者限定）")
    async def balance_list(self, interaction: discord.Interaction):

        # 管理者チェック
        if not await self.is_admin(interaction.user):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)
        balances = await self.bot.db.get_all_balances(guild_id)
        settings = await self.bot.db.get_settings()
        currency_unit = settings["currency_unit"]

        embed = discord.Embed(
            title="💰 残高一覧（上位順）",
            color=0xf1c40f
        )

        lines = []
        for user in balances:
            user_id = str(user["user_id"])
            balance = user["balance"]

            mention = f"<@{user_id}>"
            lines.append(f"{mention}\n{balance}{currency_unit}\n")

        embed.description = "".join(lines)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    cog = AdminCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))





