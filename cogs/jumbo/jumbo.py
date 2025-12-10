import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView
from .jumbo_draw import JumboDrawHandler


ADMIN_ROLES_CACHE = {}


class JumboCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)

    # --------------------------
    # 管理者チェック
    # --------------------------
    async def is_admin(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if guild_id not in ADMIN_ROLES_CACHE:
            settings = await self.bot.db.get_settings()
            ADMIN_ROLES_CACHE[guild_id] = settings["admin_roles"] or []

        admin_roles = ADMIN_ROLES_CACHE[guild_id]
        admin_role_ids = {int(r) for r in admin_roles if r.isdigit()}

        return any(r.id in admin_role_ids for r in interaction.user.roles)

    # ==========================================================
    # /年末ジャンボ開催
    # ==========================================================
    @app_commands.command(
        name="年末ジャンボ開催",
        description="年末ジャンボを開始し、購入パネルを設置します（管理者のみ）"
    )
    @app_commands.describe(
        title="イベントタイトル",
        description="説明文",
        deadline="購入期限（例：2025-12-31 23:59）"
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

        guild_id = str(interaction.guild.id)

        try:
            dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
        except:
            return await interaction.response.send_message(
                "❌ 期限形式は YYYY-MM-DD HH:MM で入力してください。",
                ephemeral=True
            )

        await self.jumbo_db.set_config(guild_id, title, description, dt)

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=(
                f"{description}\n\n"
                f"**購入期限：<t:{int(dt.timestamp())}:F>**\n\n"
                f"1口＝10,000 spt\n最大10口まで購入可能"
            ),
            color=0xF1C40F
        )

        view = JumboBuyView(self.bot, self.jumbo_db, guild_id)

        await interaction.response.send_message("🎫 **年末ジャンボ開始！**", ephemeral=True)
        await interaction.followup.send(embed=embed, view=view)

    # ==========================================================
    # /年末ジャンボ当選者発表
    # ==========================================================
    @app_commands.command(
        name="年末ジャンボ当選者発表",
        description="抽選を開始します（管理者のみ）"
    )
    async def jumbo_draw(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用です。", ephemeral=True)

        config = await self.jumbo_db.get_config(str(interaction.guild.id))
        if not config:
            return await interaction.response.send_message("❌ 開催されていません。", ephemeral=True)

        handler = JumboDrawHandler(self.bot, self.jumbo_db)
        await handler.start(interaction)

    # ==========================================================
    # /ジャンボ履歴リセット
    # ==========================================================
    @app_commands.command(
        name="ジャンボ履歴リセット",
        description="ジャンボの番号・設定・当選履歴を全リセット（管理者のみ）"
    )
    async def jumbo_reset(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.jumbo_db.clear_entries(guild_id)
        await self.jumbo_db.clear_winners(guild_id)
        await self.jumbo_db.reset_config(guild_id)

        await interaction.response.send_message(
            "🧹 ジャンボデータを初期化しました。",
            ephemeral=True
        )


async def setup(bot):
    cog = JumboCog(bot)
    await bot.add_cog(cog)

    print("=== JumboCog attributes ===")
    for attr in dir(cog):
        if not attr.startswith("_"):
            print(attr)

    print("🎫 Jumbo module loaded.")

