# cogs/salary.py
import discord
from discord import app_commands
from discord.ext import commands

from paginator import Paginator
from logger import log_salary


class SalaryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------------------------------------------
    # /給料設定
    # -------------------------------------------------------
    @app_commands.command(name="給料設定", description="指定ロールの給料額を設定します（管理者専用）")
    @app_commands.describe(role="給料を設定するロール", amount="給料額（整数）")
    async def set_salary(self, interaction: discord.Interaction, role: discord.Role, amount: int):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(r.id in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        if amount < 0:
            return await interaction.response.send_message("❌ 0以上で入力してください。", ephemeral=True)

        await self.bot.db.set_salary(str(role.id), amount)

        await interaction.response.send_message(
            f"📝 ロール **{role.name}** の給料を **{amount}{settings['currency_unit']}** に設定しました。",
            ephemeral=False
        )

    # -------------------------------------------------------
    # /給料一覧
    # -------------------------------------------------------
    @app_commands.command(name="給料一覧", description="給料設定されているロール一覧を表示します（管理者専用）")
    async def list_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(r.id in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        rows = await self.bot.db.get_salaries()

        if not rows:
            return await interaction.response.send_message("⚠️ まだ給料設定はありません。", ephemeral=True)

        pages = []
        chunk = 10
        for i in range(0, len(rows), chunk):
            embed = discord.Embed(title="💼 給料一覧", color=0x00AAFF)

            for row in rows[i:i+chunk]:
                role_id = row["role_id"]
                salary = row["salary"]
                embed.add_field(
                    name=f"<@&{role_id}>",
                    value=f"{salary} {unit}",
                    inline=False
                )

            pages.append(embed)

        paginator = Paginator(pages)
        await interaction.response.send_message(embed=pages[0], view=paginator)

    # -------------------------------------------------------
    # /給料確認（自分が貰える給料の合計）
    # -------------------------------------------------------
    @app_commands.command(name="給料確認", description="自分のロールに基づく給料の合計を表示します")
    async def check_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        unit = settings["currency_unit"]
        salaries = await self.bot.db.get_salaries()

        role_salary_map = {row["role_id"]: row["salary"] for row in salaries}

        total = 0
        detail = ""

        for role in interaction.user.roles:
            if str(role.id) in role_salary_map:
                salary = role_salary_map[str(role.id)]
                detail += f"- {role.name}: {salary}{unit}\n"
                total += salary

        if total == 0:
            return await interaction.response.send_message("あなたのロールには給料設定がありません。")

        embed = discord.Embed(
            title="💰 給料確認",
            description=detail + f"\n**合計: {total}{unit}**",
            color=0xFFD700
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------
    # /給料配布（全メンバーへ）
    # -------------------------------------------------------
    @app_commands.command(name="給料配布", description="給料を全メンバーに配布します（管理者専用）")
    async def give_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(r.id in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        salaries = await self.bot.db.get_salaries()
        salary_map = {row["role_id"]: row["salary"] for row in salaries}

        if not salary_map:
            return await interaction.response.send_message("⚠️ 給料設定がありません。", ephemeral=True)

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

        await log_salary(
            bot=self.bot,
            settings=settings,
            executor_id=str(interaction.user.id),
            total_users=total_users,
            total_amount=total_amount
        )

        await interaction.response.send_message(
            f"🎉 給料を **{total_users}人** に合計 **{total_amount}{unit}** 配布しました！"
        )


async def setup(bot):
    cog = SalaryCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        bot.tree.add_command(cmd, guild=discord.Object(id=1420918259187712093))



