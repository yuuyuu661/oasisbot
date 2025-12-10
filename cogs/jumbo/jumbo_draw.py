# cogs/jumbo/jumbo_draw.py

import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime, timezone

from .jumbo_db import JumboDB


# ======================================================
# 当選番号事前生成
# ======================================================

async def choose_winners(jumbo_db: JumboDB, guild_id: str):
    """
    全番号を取得 → そこから当選番号を抽選（重複無し）
    rank:
      6等 → 5名
      5等 → 1名
      4等 → 1名
      3等 → 1名
      2等 → 1名
      1等 → 1名
    """

    entries = await jumbo_db.get_all_numbers(guild_id)
    all_numbers = [row["number"] for row in entries]
    random.shuffle(all_numbers)

    if len(all_numbers) < 10:
        # 最低10件は必要
        return None

    winners = {
        6: [],  # 5名
        5: None,
        4: None,
        3: None,
        2: None,
        1: None
    }

    # 6等 → 最初の5名
    winners[6] = all_numbers[:5]

    # 5〜1等 → 残りからそれぞれ1名ずつ
    rest = all_numbers[5:]
    random.shuffle(rest)

    winners[5] = rest[0]
    winners[4] = rest[1]
    winners[3] = rest[2]
    winners[2] = rest[3]
    winners[1] = rest[4]

    return winners


# ======================================================
# 進行ボタン
# ======================================================

class JumboNextButton(discord.ui.Button):
    def __init__(self, handler, current_rank):
        super().__init__(label="➡️ 次へ", style=discord.ButtonStyle.primary)
        self.handler = handler
        self.current_rank = current_rank

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.handler.start_next_rank(interaction, self.current_rank)


class JumboNextView(discord.ui.View):
    def __init__(self, handler, current_rank):
        super().__init__(timeout=None)
        self.add_item(JumboNextButton(handler, current_rank))


# ======================================================
# メイン抽選クラス（演出）
# ======================================================

class JumboDrawHandler:
    def __init__(self, bot, jumbo_db):
        self.bot = bot
        self.jumbo_db = jumbo_db
        self.rank_order = [6, 5, 4, 3, 2, 1]  # 抽選順
        self.winners = {}                     # {rank: 番号 or [番号…]}

    # ------------------------------------------
    # 抽選開始
    # ------------------------------------------
    async def start(self, interaction: discord.Interaction):

        guild_id = str(interaction.guild.id)

        # まず購入受付を終了
        await self.jumbo_db.close_config(guild_id)

        # 当選番号事前生成
        self.winners = await choose_winners(self.jumbo_db, guild_id)
        if not self.winners:
            return await interaction.response.send_message("❌ 参加口数が不足しています。", ephemeral=True)

        # 6等から開始
        await interaction.response.send_message("🎉 年末ジャンボ抽選開始！", ephemeral=False)
        await self.start_rank(interaction, 6)

    # ------------------------------------------
    # 該当ランクの抽選演出
    # ------------------------------------------
    async def start_rank(self, interaction, rank):

        guild_id = str(interaction.guild.id)

        if rank == 6:
            numbers = self.winners[6]  # 配列（5名）
            await self.draw_rank_multi(interaction, rank, numbers)
        else:
            number = self.winners[rank]
            await self.draw_rank_single(interaction, rank, number)

    # ------------------------------------------
    # 次へ進む
    # ------------------------------------------
    async def start_next_rank(self, interaction, current_rank):

        idx = self.rank_order.index(current_rank)
        if idx == len(self.rank_order) - 1:
            # すべて終了 → リザルト出す
            await self.send_final_result(interaction)
            return

        next_rank = self.rank_order[idx + 1]
        await self.start_rank(interaction, next_rank)

    # ======================================================
    # ６等：5名同時（縦5列）ルーレット
    # ======================================================

    async def draw_rank_multi(self, interaction, rank, numbers):

        # 最初のランダム文字列
        random_rows = [[str(random.randint(0, 9)) for _ in range(6)] for __ in range(5)]

        embed = discord.Embed(
            title=f"🎰 第{rank}等 抽選中（5名）",
            color=0x3498DB
        )

        def format_rows(rows):
            return "\n".join([
                "".join([f"[{c}]" for c in row])
                for row in rows
            ])

        embed.description = format_rows(random_rows)

        msg = await interaction.followup.send(embed=embed)

        # 停止処理（1桁ずつ、5列同時）
        for digit in range(6):

            await asyncio.sleep(1)

            for i in range(5):
                random_rows[i][digit] = numbers[i][digit]

            embed.description = format_rows(random_rows)
            await msg.edit(embed=embed)

        # 当選者を登録
        guild_id = str(interaction.guild.id)
        for num in numbers:
            # number から user を特定
            entries = await self.jumbo_db.get_all_numbers(guild_id)
            user_id = None
            for row in entries:
                if row["number"] == num:
                    user_id = row["user_id"]
                    break

            await self.jumbo_db.set_winner(guild_id, rank, num, user_id)

        # 次へボタン
        view = JumboNextView(self, rank)
        await interaction.followup.send(f"🎫 第{rank}等の発表が完了しました！", view=view)

    # ======================================================
    # １〜５等：1名ルーレット
    # ======================================================

    async def draw_rank_single(self, interaction, rank, number):

        # ランダム文字列（1列6桁）
        random_row = [str(random.randint(0, 9)) for _ in range(6)]

        embed = discord.Embed(
            title=f"🎰 第{rank}等 抽選中…",
            color=0xE67E22
        )

        def fmt(row):
            return "".join([f"[{c}]" for c in row])

        embed.description = fmt(random_row)

        msg = await interaction.followup.send(embed=embed)

        # 1桁ずつストップ
        for digit in range(6):
            await asyncio.sleep(1)
            random_row[digit] = number[digit]
            embed.description = fmt(random_row)
            await msg.edit(embed=embed)

        # 当選者を登録
        guild_id = str(interaction.guild.id)
        entries = await self.jumbo_db.get_all_numbers(guild_id)
        user_id = None
        for row in entries:
            if row["number"] == number:
                user_id = row["user_id"]
                break

        await self.jumbo_db.set_winner(guild_id, rank, number, user_id)

        # 次へ
        view = JumboNextView(self, rank)
        await interaction.followup.send(f"🎉 第{rank}等の発表が完了しました！", view=view)

    # ======================================================
    # 最終リザルト
    # ======================================================

    async def send_final_result(self, interaction):

        guild_id = str(interaction.guild.id)
        winners = await self.jumbo_db.get_all_winners(guild_id)

        embed = discord.Embed(
            title="🎉 年末ジャンボ 最終結果 🎉",
            color=0xF1C40F
        )

        rank_names = {
            1: "1等",
            2: "2等",
            3: "3等",
            4: "4等",
            5: "5等",
            6: "6等（5名）"
        }

        desc = ""

        for rank in [1, 2, 3, 4, 5, 6]:
            rows = [w for w in winners if w["rank"] == rank]
            if not rows:
                continue

            desc += f"\n**【{rank_names[rank]}】**\n"
            for row in rows:
                user = f"<@{row['user_id']}>" if row["user_id"] else "不明"
                desc += f"- {row['number']} → {user}\n"

        embed.description = desc

        await interaction.followup.send(embed=embed)
