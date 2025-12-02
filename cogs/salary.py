# cogs/salary.py
import discord
from discord.ext import commands
from discord import app_commands

from paginator import Paginator
from logger import log_salary


class SalaryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------
    # /給料設定
    # --------------------------
    @app_commands.command(name="給料設定", description="指定ロールの給料額を設定します（管理者）")
    async def set_salary(self, interaction: discord.Interaction, role: discord.Role, amount: int):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        await self.bot.db.set_salary(str(role.id), amount)

        unit = settings["currency_unit"]
        await interaction.response.send_message(
            f"📝 ロール **{role.name}** の給料を **{amount}{unit}** に設定しました。"
        )

    # --------------------------
    # /給料一覧
    # --------------------------
    @app_commands.command(name="給料一覧", description="設定されているロール給料一覧（管理者）")
    async def list_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        rows = await self.bot.db.get_salaries()

        if not rows:
            return await interaction.response.send_message("⚠️ まだ給料設定がありません。", ephemeral=True)

        pages = []
        for i in range(0, len(rows), 10):
            embed = discord.Embed(title="💼 給料一覧", color=0x00AAFF)

            for row in rows[i:i+10]:
                embed.add_field(
                    name=f"<@&{row['role_id']}>",
                    value=f"{row['salary']} {unit}",
                    inline=False
                )

            pages.append(embed)

        paginator = Paginator(pages)
        await interaction.response.send_message(embed=pages[0], view=paginator)

    # --------------------------
    # /給料確認
    # --------------------------
    @app_commands.command(name="給料確認", description="自分のロールに基づく給料合計を表示します")
    async def check_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        unit = settings["currency_unit"]

        rows = await self.bot.db.get_salaries()
        salary_map = {row["role_id"]: row["salary"] for row in rows}

        total = 0
        desc = ""

        for role in interaction.user.roles:
            if str(role.id) in salary_map:
                total += salary_map[str(role.id)]
                desc += f"- {role.name}: {salary_map[str(role.id)]}{unit}\n"

        if total == 0:
            return await interaction.response.send_message("あなたのロールには給料設定がありません。")

        embed = discord.Embed(
            title="💰 給料確認",
            description=desc + f"\n**合計：{total}{unit}**",
            color=0xFFD700
        )
        await interaction.response.send_message(embed=embed)

    # --------------------------
    # /給料配布
    # --------------------------
    @app_commands.command(name="給料配布", description="給料を全メンバーに配布します（管理者）")
    async def give_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        rows = await self.bot.db.get_salaries()
        salary_map = {row["role_id"]: row["salary"] for row in rows}

        guild = interaction.guild
        total_users = 0
        total_amount = 0

        for member in guild.members:
            if member.bot:
                continue

            add_amount = 0

            for role in member.roles:
                if str(role.id) in salary_map:
                    add_amount += salary_map[str(role.id)]

            if add_amount > 0:
                await self.bot.db.add_balance(str(member.id), add_amount)
                total_users += 1
                total_amount += add_amount

        await log_salary(self.bot, settings, str(interaction.user.id), total_users, total_amount)

        await interaction.response.send_message(
            f"🎉 **{total_users}人** に **{total_amount}{unit}** を配布しました！"
        )


async def setup(bot):
    cog = SalaryCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        bot.tree.add_command(cmd, guild=discord.Object(id=1420918259187712093))
