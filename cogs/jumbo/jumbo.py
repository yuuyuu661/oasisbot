# cogs/jumbo/jumbo.py
from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView


# =====================================================
# 判定ロジック（連続一致）
# =====================================================
def count_continuous_match(winning: str, target: str) -> int:
    count = 0
    for w, t in zip(winning, target):
        if w == t:
            count += 1
        else:
            break
    return count


def match_to_rank(match: int) -> int | None:
    return {
        6: 1,
        5: 2,
        4: 3,
        3: 4,
        2: 5,
    }.get(match)


def get_prize(config, rank: int) -> int:
    return config[f"prize_{rank}"]


# =====================================================
# 所持番号一覧 View
# =====================================================
class NumberListView(discord.ui.View):
    def __init__(self, user: discord.User, numbers: list[str]):
        super().__init__(timeout=180)
        self.user = user
        self.numbers = numbers
        self.page = 0
        self.per_page = 20

    def make_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_numbers = self.numbers[start:end]

        embed = discord.Embed(
            title="🎟 所持宝くじ番号一覧",
            color=0x3498DB
        )
        embed.description = "\n".join(f"`{n}`" for n in page_numbers) or "該当なし"
        total_pages = (len(self.numbers) - 1) // self.per_page + 1
        embed.set_footer(text=f"{self.page + 1} / {total_pages} ページ")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @discord.ui.button(label="⬅ 前へ")
    async def prev(self, interaction: discord.Interaction, _):
        self.page = max(0, self.page - 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="次へ ➡")
    async def next(self, interaction: discord.Interaction, _):
        max_page = (len(self.numbers) - 1) // self.per_page
        self.page = min(max_page, self.page + 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


# =====================================================
# Jumbo Cog
# =====================================================
class JumboCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)


    # -------------------------------------------------
    # 管理者判定
    # -------------------------------------------------
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        return any(str(r.id) in admin_roles for r in interaction.user.roles)

    # -------------------------------------------------
    # /年末ジャンボ開催
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ開催")
    async def jumbo_start(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        deadline: str,  # MM-DD
    ):
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用", ephemeral=True)

        try:
            month, day = map(int, deadline.split("-"))
            year = datetime.now().year
            deadline_dt = datetime(year, month, day, 23, 59)
        except Exception:
            return await interaction.response.send_message(
                "❌ 期限は MM-DD（例: 12-31）", ephemeral=True
            )

        guild_id = str(interaction.guild.id)
        await self.jumbo_db.set_config(guild_id, title, description, deadline_dt)

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=(
                f"{description}\n\n"
                f"締切：{deadline_dt.strftime('%Y/%m/%d 23:59')}\n"
                f"1口 = 1,000 rrc"
            ),
            color=0xF1C40F
        )

        view = JumboBuyView(self.bot, self.jumbo_db, guild_id)

        await interaction.response.send_message("🎫 ジャンボを開始しました", ephemeral=True)
        await interaction.followup.send(embed=embed, view=view)

    # -------------------------------------------------
    # /年末ジャンボ設定
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ設定")
    async def jumbo_set_prize(self, interaction: discord.Interaction, winning_number: str):

        await interaction.response.defer(ephemeral=True)

        try:
            if not await self.is_admin(interaction):
                return await interaction.followup.send("❌ 管理者専用")

            if not winning_number.isdigit() or len(winning_number) != 6:
                return await interaction.followup.send("❌ 当選番号は6桁です")

            await self.jumbo_db.set_winning_number(
                str(interaction.guild.id),
                winning_number
            )

            await interaction.followup.send("🎯 当選番号を設定しました！")

        except Exception as e:
            print("jumbo_set_prize error:", repr(e))
            await interaction.followup.send(
                "❌ 内部エラーが発生しました（DB）",
                ephemeral=True
            )

    # -------------------------------------------------
    # /年末ジャンボ当選者発表
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ当選者発表")
    async def jumbo_announce(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if not await self.is_admin(interaction):
            return await interaction.followup.send("❌ 管理者専用")

        guild_id = str(interaction.guild.id)
        config = await self.jumbo_db.get_config(guild_id)

        if not config or not config["winning_number"]:
            return await interaction.followup.send("❌ 当選番号が未設定です")

        entries = await self.jumbo_db.get_all_entries(guild_id)
        if not entries:
            return await interaction.followup.send("⚠ 購入者がいません")

        # ★ 固定賞金テーブル
        PRIZES = {
            1: 10_000_000,
            2: 5_000_000,
            3: 1_000_000,
            4: 500_000,
            5: 100_000,
        }

        await self.jumbo_db.clear_winners(guild_id)

        results = {i: [] for i in range(1, 6)}

        for e in entries:
            match = count_continuous_match(config["winning_number"], e["number"])
            rank = match_to_rank(match)
            if not rank:
                continue

            prize = PRIZES[rank]

            await self.jumbo_db.set_winner(
                guild_id,
                rank,
                e["number"],
                e["user_id"],
                match,
                prize
            )
            results[rank].append(e)

        embed = discord.Embed(title="🎉 年末ジャンボ 当選者発表", color=0xF1C40F)
        embed.add_field(
            name="🎯 当選番号",
            value=f"**{config['winning_number']}**",
            inline=False
        )

        for rank in range(1, 6):
            prize = PRIZES[rank]
            winners = results[rank]

            text = "いませんでした。" if not winners else "\n".join(
                f"<@{w['user_id']}> `{w['number']}`"
                for w in winners
            )

            embed.add_field(
                name=f"第{rank}等（{prize:,} rrc）",
                value=text,
                inline=False
            )

        await interaction.followup.send(embed=embed)


    # -------------------------------------------------
    # /年末ジャンボ当選者賞金付与
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ当選者賞金付与")
    async def jumbo_pay_prizes(self, interaction: discord.Interaction):
        # ★ 超重要
        await interaction.response.defer(ephemeral=True)

        if not await self.is_admin(interaction):
            return await interaction.followup.send("❌ 管理者専用", ephemeral=True)

        guild_id = str(interaction.guild.id)
        config = await self.jumbo_db.get_config(guild_id)

        if config["prize_paid"]:
            return await interaction.followup.send("⚠️ すでに付与済み", ephemeral=True)

        winners = await self.jumbo_db.get_all_winners(guild_id)
        if not winners:
            return await interaction.followup.send("⚠️ 当選者なし", ephemeral=True)

        payout: dict[str, int] = {}
        for w in winners:
            payout[w["user_id"]] = payout.get(w["user_id"], 0) + w["prize"]

        for uid, total in payout.items():
            await self.bot.db.add_balance(uid, guild_id, total)

        await self.jumbo_db.mark_prize_paid(guild_id)

        embed = discord.Embed(title="💰 賞金付与完了", color=0x2ECC71)
        for uid, total in payout.items():
            embed.add_field(
                name=f"<@{uid}>",
                value=f"{total:,} rrc",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


    # -------------------------------------------------
    # /所持宝くじ番号確認
    # -------------------------------------------------
    @app_commands.command(name="所持宝くじ番号確認")
    async def jumbo_my_numbers(
        self,
        interaction: discord.Interaction,
        search: str | None = None,
    ):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        rows = await self.jumbo_db.get_user_numbers(guild_id, user_id)
        numbers = [r["number"] for r in rows]

        if search:
            numbers = [n for n in numbers if n.startswith(search) or n.endswith(search)]

        if not numbers:
            return await interaction.response.send_message("該当なし", ephemeral=True)

        view = NumberListView(interaction.user, numbers)
        await interaction.response.send_message(
            embed=view.make_embed(),
            view=view,
            ephemeral=True
        )

    # -------------------------------------------------
    # /ジャンボ履歴リセット
    # -------------------------------------------------
    @app_commands.command(name="ジャンボ履歴リセット")
    async def jumbo_reset(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用", ephemeral=True)

        guild_id = str(interaction.guild.id)
        await self.jumbo_db.clear_entries(guild_id)
        await self.jumbo_db.clear_winners(guild_id)
        await self.jumbo_db.reset_config(guild_id)

        await interaction.response.send_message("🧹 リセット完了", ephemeral=True)


# =====================================================
# setup（bal と完全一致）
# =====================================================
async def setup(bot: commands.Bot):
    await bot.add_cog(JumboCog(bot))









