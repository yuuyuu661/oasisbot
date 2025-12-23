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

        # ★ 追加：DBマイグレーションを自動実行
        bot.loop.create_task(self.jumbo_db.init_tables())


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
        print("[JUMBO] announce start")

        await interaction.response.defer()
        print("[JUMBO] defer OK")

        if not await self.is_admin(interaction):
            print("[JUMBO] admin check NG")
            return await interaction.followup.send("❌ 管理者専用")

        print("[JUMBO] admin check OK")

        guild_id = str(interaction.guild.id)
        print("[JUMBO] guild_id =", guild_id)

        config = await self.jumbo_db.get_config(guild_id)
        print("[JUMBO] config fetched:", dict(config) if config else None)

        if not config or not config["winning_number"]:
            print("[JUMBO] winning_number missing")
            return await interaction.followup.send("❌ 当選番号が未設定です")

        print("[JUMBO] winning_number =", config["winning_number"])

        entries = await self.jumbo_db.get_all_entries(guild_id)
        print("[JUMBO] entries count =", len(entries))

        if not entries:
            print("[JUMBO] no entries")
            return await interaction.followup.send("⚠ 購入者がいません")

        await self.jumbo_db.clear_winners(guild_id)
        print("[JUMBO] winners cleared")

        PRIZES = {
            1: 10_000_000,
            2: 5_000_000,
            3: 1_000_000,
            4: 500_000,
            5: 100_000,
        }

        results = {i: [] for i in range(1, 6)}

        for e in entries:
            try:
                print("[JUMBO] check number:", e["number"])

                match = count_continuous_match(
                    str(config["winning_number"]),
                    str(e["number"])
                )
                print("[JUMBO] match count =", match)

                rank = match_to_rank(match)
                print("[JUMBO] rank =", rank)

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

                print("[JUMBO] winner saved:", e["number"], "rank", rank)
                results[rank].append(e)

            except Exception as ex:
                print("[JUMBO] ERROR in loop:", repr(ex), "data:", dict(e))

    # -------------------------------------------------
    # /所持宝くじ番号確認
    # -------------------------------------------------
    @app_commands.command(name="所持宝くじ番号を確認")
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

















