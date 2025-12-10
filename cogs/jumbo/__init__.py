import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView
from .jumbo_draw import JumboDrawHandler


ADMIN_ROLES_CACHE = {}


class JumboCog(commands.Cog):
    """年末ジャンボ機能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)

    # ------------------------
    # 管理者チェック
    # ------------------------
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        guild_id = str(interaction.guild.id)

        if guild_id not in ADMIN_ROLES_CACHE:
            settings = await self.bot.db.get_settings()
            ADMIN_ROLES_CACHE[guild_id] = settings["admin_roles"] or []

        admin_ids = {int(r) for r in ADMIN_ROLES_CACHE[guild_id] if r.isdigit()}
        return any(r.id in admin_ids for r in interaction.user.roles)

    # ------------------------
    # /jumbo_start
    # ------------------------
    @app_commands.command(
        name="jumbo_start",
        description="年末ジャンボを開催し、購入パネルを設置します（管理者のみ）"
    )
    @app_commands.describe(
        title="イベントタイトル",
        description="説明文",
        deadline="購入期限（YYYY-MM-DD HH:MM）"
    )
    async def jumbo_start(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        deadline: str
    ):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        try:
            dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return await interaction.response.send_message(
                "❌ 期限形式は YYYY-MM-DD HH:MM です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)
        await self.jumbo_db.set_config(guild_id, title, description, dt)

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=f"{description}\n\n📅 期限：<t:{int(dt.timestamp())}:F>\n💰 1口 = 10,000 spt（最大10口）",
            color=0xF1C40F
        )

        view = JumboBuyView(self.bot, self.jumbo_db, guild_id)

        await interaction.response.send_message("🎫 開催設定完了！", ephemeral=True)
        await interaction.followup.send(embed=embed, view=view)

    # ------------------------
    # /jumbo_draw
    # ------------------------
    @app_commands.command(
        name="jumbo_draw",
        description="年末ジャンボの抽選を開始（管理者のみ）"
    )
    async def jumbo_draw(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用です。", ephemeral=True)

        config = await self.jumbo_db.get_config(str(interaction.guild.id))
        if not config:
            return await interaction.response.send_message("❌ 開催されていません。", ephemeral=True)

        handler = JumboDrawHandler(self.bot, self.jumbo_db)
        await handler.start(interaction)

    # ------------------------
    # /jumbo_reset
    # ------------------------
    @app_commands.command(
        name="jumbo_reset",
        description="年末ジャンボの履歴を全リセット（管理者のみ）"
    )
    async def jumbo_reset(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.jumbo_db.clear_entries(guild_id)
        await self.jumbo_db.clear_winners(guild_id)
        await self.jumbo_db.reset_config(guild_id)

        await interaction.response.send_message("🧹 ジャンボデータをリセットしました！", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(JumboCog(bot))
    print("🎫 Jumbo module loaded.")
