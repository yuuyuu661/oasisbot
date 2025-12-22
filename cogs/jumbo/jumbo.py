# cogs/jumbo/jumbo.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView

class JumboCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)
        bot.loop.create_task(self.jumbo_db.init_tables())

    # ------------------------------------------------------
    # 内部：管理者ロール判定（AdminCog と統一）
    # ------------------------------------------------------
    async def is_admin(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        return any(
            str(role.id) in admin_roles
            for role in interaction.user.roles
        )

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
        deadline="締切日（例：12-31 のみ）"
    )
    async def jumbo_start(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        deadline: str  # ← 例： "12-31"
    ):

        # 管理者チェック
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        # 今年の年を自動取得
        current_year = datetime.now().year

        # 期限パース（月-日 のみ）
        try:
            # "12-31" → datetime(current_year, 12, 31, 23, 59)
            month, day = map(int, deadline.split("-"))
            deadline_dt = datetime(current_year, month, day, 23, 59)
        except Exception:
            return await interaction.response.send_message(
                "❌ 期限形式は `MM-DD`（例：12-31）で入力してください。",
                ephemeral=True
            )

        # DBには naive datetime のまま保存
        await self.jumbo_db.set_config(guild_id, title, description, deadline_dt)

        # Discord表示用にUTCタイムスタンプへ変換
        ts = int(deadline_dt.replace(tzinfo=timezone.utc).timestamp())

        # 日本語曜日
        week = ["月", "火", "水", "木", "金", "土", "日"]
        w = week[deadline_dt.weekday()]

        deadline_str = (
            f"{deadline_dt.year}年"
            f"{deadline_dt.month}月"
            f"{deadline_dt.day}日"
            f"（{w}）23:59 締切"
        )

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=(
                f"{description}\n\n"
                f"**購入期限：{deadline_str}**\n"
                f"1口 = 1,000 rrc\n"
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
    # /年末ジャンボ設定
    # ------------------------------------------------------
    @app_commands.command(
        name="年末ジャンボ設定",
        description="当選番号と各等賞の賞金を設定します（管理者専用）"
    )
    @app_commands.describe(
        winning_number="当選番号（6桁）",
        prize_1="1等の賞金",
        prize_2="2等の賞金",
        prize_3="3等の賞金",
        prize_4="4等の賞金",
        prize_5="5等の賞金",
    )
    async def jumbo_set_prize(
        self,
        interaction: discord.Interaction,
        winning_number: str,
        prize_1: int,
        prize_2: int,
        prize_3: int,
        prize_4: int,
        prize_5: int,
    ):
        # 管理者チェック
        if not await self.is_admin(interaction):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)

        # 開催チェック
        config = await self.jumbo_db.get_config(guild_id)
        if not config:
            return await interaction.response.send_message(
                "❌ 年末ジャンボが開催されていません。",
                ephemeral=True
            )

        # 当選番号チェック
        if not (winning_number.isdigit() and len(winning_number) == 6):
            return await interaction.response.send_message(
                "❌ 当選番号は6桁の数字で入力してください。",
                ephemeral=True
            )

        # 保存
        await self.jumbo_db.set_prize_config(
            guild_id,
            winning_number,
            prize_1,
            prize_2,
            prize_3,
            prize_4,
            prize_5
        )

        # 確認用Embed
        embed = discord.Embed(
            title="🎯 年末ジャンボ 当選番号・賞金設定完了",
            color=0xF1C40F
        )
        embed.add_field(name="当選番号", value=f"**{winning_number}**", inline=False)
        embed.add_field(name="第1等", value=f"{prize_1:,} rrc")
        embed.add_field(name="第2等", value=f"{prize_2:,} rrc")
        embed.add_field(name="第3等", value=f"{prize_3:,} rrc")
        embed.add_field(name="第4等", value=f"{prize_4:,} rrc")
        embed.add_field(name="第5等", value=f"{prize_5:,} rrc")

        await interaction.response.send_message(embed=embed)

# ======================================================
# setup
# ======================================================

async def setup(bot):
    cog = JumboCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))









