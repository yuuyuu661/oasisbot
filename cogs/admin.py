# cogs/admin.py
import discord
from discord.ext import commands
from discord import app_commands

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -----------------------------------
    # 🚨 管理者チェック（共通）
    # -----------------------------------
    async def is_admin(self, interaction):
        guild_id = str(interaction.guild.id)
        settings = await self.bot.db.get_settings(guild_id)
        admin_roles = settings["admin_roles"]

        if not admin_roles:
            return False

        # ロールチェック
        user_role_ids = [str(r.id) for r in interaction.user.roles]
        return any(r in admin_roles for r in user_role_ids)

    # -----------------------------------
    # 💰 残高一覧（/残高一覧）
    # -----------------------------------
    @app_commands.command(name="残高一覧", description="全メンバーの残高を上位順で表示")
    async def balance_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        settings = await self.bot.db.get_settings(guild_id)
        unit = settings["currency_unit"]

        rows = await self.bot.db.get_all_balances(guild_id)

        embed = discord.Embed(title="💰 残高一覧（上位順）", color=0xf1c40f)
        desc = ""

        for r in rows:
            desc += f"<@{r['user_id']}>\n{r['balance']} {unit}\n\n"

        embed.description = desc or "データなし"
        await interaction.response.send_message(embed=embed)

    # -----------------------------------
    # 🛠 残高設定（/残高設定）
    # -----------------------------------
    @app_commands.command(
        name="残高設定",
        description="特定ユーザーの残高を設定・増加・減少させます（管理者専用）"
    )
    @app_commands.describe(
        user="対象ユーザー",
        amount="数値",
        mode="設定・増加・減少から選択"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="設定", value="set"),
        app_commands.Choice(name="増加", value="add"),
        app_commands.Choice(name="減少", value="remove"),
    ])
    async def balance_edit(self, interaction: discord.Interaction, user: discord.User, amount: int, mode: app_commands.Choice[str]):
        guild_id = str(interaction.guild.id)

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です", ephemeral=True)

        settings = await self.bot.db.get_settings(guild_id)
        unit = settings["currency_unit"]

        user_id = str(user.id)

        if mode.value == "set":
            await self.bot.db.set_balance(user_id, guild_id, amount)
            text = f"🛠 **{user.mention} の残高を {amount}{unit} に設定しました。**"

        elif mode.value == "add":
            await self.bot.db.add_balance(user_id, guild_id, amount)
            text = f"➕ **{user.mention} に {amount}{unit} を追加しました。**"

        elif mode.value == "remove":
            await self.bot.db.remove_balance(user_id, guild_id, amount)
            text = f"➖ **{user.mention} から {amount}{unit} を減少しました。**"

        # ログ送信
        if settings["log_manage"]:
            log_ch = interaction.guild.get_channel(int(settings["log_manage"]))
            if log_ch:
                await log_ch.send(text)

        await interaction.response.send_message(text)

    # -----------------------------------
    # 📦 給料配布（/給料配布）
    # -----------------------------------
    @app_commands.command(name="給料配布", description="全メンバーに給料を配布（管理者専用）")
    async def give_salary(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です", ephemeral=True)

        settings = await self.bot.db.get_settings(guild_id)
        unit = settings["currency_unit"]
        salaries = await self.bot.db.get_salaries(guild_id)

        total_given = 0
        roles_with_salary = {s["role_id"]: s["salary"] for s in salaries}

        # メンバー全員に給料付与
        for member in interaction.guild.members:
            if member.bot:
                continue

            give = 0
            for role in member.roles:
                if str(role.id) in roles_with_salary:
                    give += roles_with_salary[str(role.id)]

            if give > 0:
                await self.bot.db.add_balance(str(member.id), guild_id, give)
                total_given += give

        # 給料ログ
        if settings["log_salary"]:
            log_ch = interaction.guild.get_channel(int(settings["log_salary"]))
            if log_ch:
                await log_ch.send(f"📦 給料配布完了！ 合計 `{total_given}{unit}` を配布しました。")

        await interaction.response.send_message(
            f"📦 給料配布完了！合計 **{total_given}{unit}** を配布しました。"
        )


# -----------------------------------
# setup（ギルド同期）
# -----------------------------------
async def setup(bot):
    cog = AdminCog(bot)
    await bot.add_cog(cog)

    # ⭐ この Cog が持つコマンドだけを登録する
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
