# cogs/jumbo/jumbo.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView
from .jumbo_draw import JumboDrawHandler


ADMIN_ROLES_CACHE = {}  # ギルドごとの管理者ロールキャッシュ


class JumboCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)

    # ------------------------------------------------------
    # 内部：管理者ロール判定
    # ------------------------------------------------------
    async def is_admin(self, interaction: discord.Interaction):

        # Settings は 1 行固定の共通設定
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        # ユーザーが管理者ロールを所持しているか判定
        return any(
            str(role.id) in admin_roles
            for role in interaction.user.roles
        )

        # 設定ロード
        if guild_id not in ADMIN_ROLES_CACHE:
            settings = await self.bot.db.get_settings()
            ADMIN_ROLES_CACHE[guild_id] = settings["admin_roles"] or []

        admin_roles = ADMIN_ROLES_CACHE[guild_id]
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return False
        return True

    # ------------------------------------------------------
    # /年末ジャンボ開催
    # ------------------------------------------------------
    @app_commands.command(
        name="年末ジャンボ開催",
        description="年末ジャンボを開始し、購入パネルを生成します（管理者専用）"
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

        # 管理者チェック
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        # 期限パース
        try:
            deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
            deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
        except:
            return await interaction.response.send_message(
                "❌ 期限形式は `YYYY-MM-DD HH:MM` で入力してください。",
                ephemeral=True
            )

        # 設定保存
        await self.jumbo_db.set_config(guild_id, title, description, deadline_dt)

        # 購入パネル生成
        embed = discord.Embed(
            title=f"🎉 {title}",
            description=(
                f"{description}\n\n"
                f"**購入期限：<t:{int(deadline_dt.timestamp())}:F>**\n"
                f"1口 = 10,000 spt\n1人最大10口まで\n"
            ),
            color=0xF1C40F
        )

        view = JumboBuyView(self.bot, self.jumbo_db, guild_id)

        await interaction.response.send_message(
            f"🎫 **年末ジャンボを開始しました！**",
            ephemeral=True
        )

        await interaction.followup.send(embed=embed, view=view)

    # ------------------------------------------------------
    # /年末ジャンボ当選者発表
    # ------------------------------------------------------
    @app_commands.command(
        name="年末ジャンボ当選者発表",
        description="年末ジャンボの当選抽選を開始します（管理者専用）"
    )
    async def jumbo_draw(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        # 設定があるか確認
        config = await self.jumbo_db.get_config(guild_id)
        if not config or not config["is_open"]:
            return await interaction.response.send_message(
                "❌ 年末ジャンボは開催されていません。",
                ephemeral=True
            )

        handler = JumboDrawHandler(self.bot, self.jumbo_db)

        # 抽選開始
        await handler.start(interaction)

    # ------------------------------------------------------
    # /ジャンボ履歴リセット
    # ------------------------------------------------------
    @app_commands.command(
        name="ジャンボ履歴リセット",
        description="ジャンボの番号・設定・当選履歴をリセットします（管理者専用）"
    )
    async def jumbo_reset(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.jumbo_db.clear_entries(guild_id)
        await self.jumbo_db.clear_winners(guild_id)
        await self.jumbo_db.reset_config(guild_id)

        await interaction.response.send_message(
            "🧹 **ジャンボ履歴をリセットしました！**\n再度開催が可能です。",
            ephemeral=True
        )


# ------------------------------------------------------
# setup
# ------------------------------------------------------
async def setup(bot):
    cog = JumboCog(bot)
    await bot.add_cog(cog)
    
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))

    print("🎫 Jumbo module loaded.")



