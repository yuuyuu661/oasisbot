# cogs/admin.py
import discord
from discord.ext import commands
from discord import app_commands

from paginator import Paginator
from logger import log_manage


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -----------------------------------------------------
    # /残高設定
    # -----------------------------------------------------
    @app_commands.command(name="残高設定", description="ユーザーの残高を設定・増加・減少します（管理者専用）")
    @app_commands.describe(
        user="対象ユーザー",
        amount="数値",
        mode="設定 / 増加 / 減少"
    )
    async def set_balance(self, interaction, user: discord.User, amount: int, mode: str):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(r.id in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        user_id = str(user.id)
        amount = int(amount)

        if amount < 0:
            return await interaction.response.send_message("❌ 0以上の数値を指定してください", ephemeral=True)

        # 実行処理
        if mode == "設定":
            await self.bot.db.set_balance(user_id, amount)
        elif mode == "増加":
            await self.bot.db.add_balance(user_id, amount)
        elif mode == "減少":
            await self.bot.db.remove_balance(user_id, amount)
        else:
            return await interaction.response.send_message("❌ mode は 「設定 / 増加 / 減少」 から選んでください")

        new_balance = (await self.bot.db.get_user(user_id))["balance"]

        # ログ送信
        await log_manage(
            bot=self.bot,
            settings=settings,
            admin_id=str(interaction.user.id),
            target_id=user_id,
            action=mode,
            amount=amount,
            new_balance=new_balance
        )

        await interaction.response.send_message(
            f"📝 <@{user_id}> の残高を **{mode}** しました。\n現在残高：**{new_balance}{unit}**"
        )

    # -----------------------------------------------------
    # /残高一覧（ページング）
    # -----------------------------------------------------
    @app_commands.command(name="残高一覧", description="全ユーザーの残高を高い順に表示します（管理者専用）")
    async def list_balances(self, interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(r.id in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        unit = settings["currency_unit"]

        rows = await self.bot.db.get_all_balances()
        if not rows:
            return await interaction.response.send_message("データがありません。", ephemeral=True)

        pages = []
        chunk = 10

        for i in range(0, len(rows), chunk):
            embed = discord.Embed(
                title="💰 残高一覧（上位順）",
                color=0x00FF88
            )
            for row in rows[i:i+chunk]:
                uid = row["user_id"]
                bal = row["balance"]
                embed.add_field(
                    name=f"<@{uid}>",
                    value=f"{bal}{unit}",
                    inline=False
                )
            pages.append(embed)

        paginator = Paginator(pages)
        await interaction.response.send_message(embed=pages[0], view=paginator)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
