# cogs/jumbo/jumbo.py
from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView

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
    # /年末ジャンボ当選者発表
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ当選者発表")
    async def jumbo_announce(self, interaction: discord.Interaction):
        print("[JUMBO] announce start")
        await interaction.response.defer()
        print("[JUMBO] defer OK")

        if not await self.is_admin(interaction):
            return await interaction.followup.send("❌ 管理者専用")

        guild_id = str(interaction.guild.id)

        config = await self.jumbo_db.get_config(guild_id)
        if not config or not config["winning_number"]:
            return await interaction.followup.send("❌ 当選番号が未設定です")

        winning = config["winning_number"]
        print("[JUMBO] winning_number =", winning)

        entries = await self.jumbo_db.get_all_entries(guild_id)
        print("[JUMBO] entries count =", len(entries))

        if not entries:
            return await interaction.followup.send("⚠ 購入者がいません")

        # 念のため当選結果リセット
        await self.jumbo_db.clear_winners(guild_id)

        # 等級定義
        RANK_RULES = {
            1: 6,
            2: 5,
            3: 4,
            4: 3,
            5: 2,
        }

        PRIZES = {
            1: 10_000_000,
            2: 5_000_000,
            3: 1_000_000,
            4: 500_000,
            5: 100_000,
        }

        results = {r: [] for r in range(1, 6)}
        used_numbers = set()  # 同じ番号の重複当選防止

        for rank, length in RANK_RULES.items():
            patterns = [
                winning[i:i+length]
                for i in range(0, len(winning) - length + 1)
            ]

            print(f"[JUMBO] rank {rank} patterns:", patterns)

            for e in entries:
                number = e["number"]

                if number in used_numbers:
                    continue

                if any(p in number for p in patterns):
                    used_numbers.add(number)

                    await self.jumbo_db.set_winner(
                        guild_id,
                        rank,
                        number,
                        e["user_id"],
                        length,
                        PRIZES[rank]
                    )

                    results[rank].append(e)
                    print("[JUMBO] HIT", number, "rank", rank)

        # ===== パネル生成 =====
        embed = discord.Embed(
            title="🎉 年末ジャンボ 当選者発表",
            color=0xF1C40F
        )

        embed.add_field(
            name="🎯 当選番号",
            value=f"**{winning}**",
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
        print("[JUMBO] announce done")



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



























