# cogs/init.py
import discord
from discord.ext import commands
from discord import app_commands

SUPER_ADMIN = 716667546241335328  # ゆう専用ユーザーID


class InitCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="初期設定",
        description="通貨Botの初期設定を行います（特定ユーザーのみ）"
    )
    @app_commands.describe(
        admin_role="管理者ロールを追加",
        currency_unit="通貨単位（例：Spt）",
        log_pay="通貨ログを送信するチャンネル",
        log_manage="管理ログを送信するチャンネル",
        log_salary="給料ログを送信するチャンネル"
    )
    async def init_settings(
        self,
        interaction: discord.Interaction,
        admin_role: discord.Role = None,
        currency_unit: str = None,
        log_pay: discord.TextChannel = None,
        log_manage: discord.TextChannel = None,
        log_salary: discord.TextChannel = None
    ):
        # --- 権限チェック ---
        if interaction.user.id != SUPER_ADMIN:
            return await interaction.response.send_message(
                "❌ このコマンドを実行できるのは bot 管理者のみです。",
                ephemeral=True
            )

        settings = await self.bot.db.get_settings()

        update_data = {}

        # 管理者ロール追加
        if admin_role:
            current = settings["admin_roles"] or []
            if str(admin_role.id) not in current:
                current.append(str(admin_role.id))
            update_data["admin_roles"] = current

        # 通貨単位
        if currency_unit:
            update_data["currency_unit"] = currency_unit

        # ログチャンネル設定
        if log_pay:
            update_data["log_pay"] = str(log_pay.id)

        if log_manage:
            update_data["log_manage"] = str(log_manage.id)

        if log_salary:
            update_data["log_salary"] = str(log_salary.id)

        # DB反映
        if update_data:
            await self.bot.db.update_settings(**update_data)

        # --- 完了メッセージ ---
        msg = "🛠 **初期設定を更新しました！**\n\n"

        if admin_role:
            msg += f"- 管理者ロール: <@&{admin_role.id}>\n"
        if currency_unit:
            msg += f"- 通貨単位: {currency_unit}\n"
        if log_pay:
            msg += f"- 通貨ログ: {log_pay.mention}\n"
        if log_manage:
            msg += f"- 管理ログ: {log_manage.mention}\n"
        if log_salary:
            msg += f"- 給料ログ: {log_salary.mention}\n"

        if update_data == {}:
            msg = "⚠️ 更新された項目がありませんでした。"

        await interaction.response.send_message(msg)


async def setup(bot):
    cog = InitCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))








