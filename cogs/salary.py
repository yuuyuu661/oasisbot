# cogs/salary.py
import discord
from discord.ext import commands
from discord import app_commands

class SalaryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 給料設定
    @app_commands.command(name="給料設定", description="指定ロールの給料額を設定")
    async def set_salary(self, interaction: discord.Interaction, role: discord.Role, amount: int):
        guild_id = str(interaction.guild.id)
        settings = await self.bot.db.get_settings(guild_id)

        if str(interaction.user.top_role.id) not in settings["admin_roles"]:
            return await interaction.response.send_message("❌ 管理者ロールが必要です", ephemeral=True)

        await self.bot.db.set_salary(str(role.id), guild_id, amount)

        await interaction.response.send_message(f"🧾 **{role.name} の給料を {amount} に設定しました！**")

    # 給料一覧
    @app_commands.command(name="給料一覧", description="登録済みの給料一覧を表示")
    async def salary_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        settings = await self.bot.db.get_settings(guild_id)
        salaries = await self.bot.db.get_salaries(guild_id)
        unit = settings["currency_unit"]

        embed = discord.Embed(title="🧾 給料一覧", color=0xe67e22)
        desc = ""

        for s in salaries:
            role = interaction.guild.get_role(int(s["role_id"]))
            name = role.name if role else "(不明ロール)"
            desc += f"**{name}**\n{s['salary']} {unit}\n\n"

        embed.description = desc or "データなし"
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SalaryCog(bot))
    for cmd in bot.tree.get_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
