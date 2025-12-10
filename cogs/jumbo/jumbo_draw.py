# cogs/jumbo/jumbo_draw.py

import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime, timezone

from .jumbo_db import JumboDB


# ======================================================
# 絵文字
# ======================================================
DIGIT_EMOJIS = [
    ":zero:", ":one:", ":two:", ":three:", ":four:",
    ":five:", ":six:", ":seven:", ":eight:", ":nine:"
]


# ======================================================
# 当選番号事前生成
# ======================================================

async def choose_winners(jumbo_db: JumboDB, guild_id: str):
    entries = await jumbo_db.get_all_numbers(guild_id)
    all_numbers = [row["number"] for row in entries]
    random.shuffle(all_numbers)

    if len(all_numbers) < 10:
        return None

    winners = {
        6: [],
        5: None,
        4: None,
        3: None,
        2: None,
        1: None
    }

    winners[6] = all_numbers[:5]  # 6等5名

    rest = all_numbers[5:]
    winners[5] = rest[0]
    winners[4] = rest[1]
    winners[3] = rest[2]
    winners[2] = rest[3]
    winners[1] = rest[4]

    return winners


# ======================================================
# 次へボタン（前メッセージ削除）
# ======================================================

class JumboNextButton(discord.ui.Button):
    def __init__(self, handler, current_rank):
        super().__init__(label="➡️ 次へ", style=discord.ButtonStyle.primary)
        self.handler = handler
        self.current_rank = current_rank

    async def callback(self, interaction: discord.Interaction):

        # 押されたボタンのメッセージを削除してログをスッキリ
        try:
            await interaction.message.delete()
        except:
            pass

        await interaction.response.defer()
        await self.handler.start_next_rank(interaction, self.current_rank)


class JumboNextView(discord.ui.View):
    def __init__(self, handler, current_rank):
        super().__init__(timeout=None)
        self.add_item(JumboNextButton(handler, current_rank))


# ======================================================
# メイン抽選クラス
# ======================================================

class JumboDrawHandler:
    def __init__(self, bot, jumbo_db):
        self.bot = bot
        self.jumbo_db = jumbo_db
        self.rank_order = [6, 5, 4, 3, 2, 1]
        self.winners = {}

    async def start(self, interaction: discord.Interaction):

        guild_id = str(interaction.guild.id)
        await self.jumbo_db.close_config(guild_id)

        self.winners = await choose_winners(self.jumbo_db, guild_id)
        if not self.winners:
            return await interaction.response.send_message("❌ 参加口数が不足しています。", ephemeral=True)

        await interaction.response.send_message("🎉 年末ジャンボ抽選開始！")
        await self.start_rank(interaction, 6)

    async def start_rank(self, interaction, rank):

        if rank == 6:
            numbers = self.winners[6]
            await self.draw_rank_multi(interaction, rank, numbers)
        else:
            number = self.winners[rank]
            await self.draw_rank_single(interaction, rank, number)

    async def start_next_rank(self, interaction, current_rank):

        idx = self.rank_order.index(current_rank)
        if idx == len(self.rank_order) - 1:
            await self.send_final_result(interaction)
            return

        next_rank = self.rank_order[idx + 1]
        await self.start_rank(interaction, next_rank)

    # ======================================================
    # ６等：5名同時 絵文字高速ルーレット
    # ======================================================
    async def draw_rank_multi(self, interaction, rank, numbers):

        # メッセージ送信
        msg = await interaction.followup.send(
            embed=discord.Embed(
                title=f"🎰 第{rank}等 抽選中（5名）",
                description="開始します…",
                color=0x3498DB
            )
        )

        # 最終数字
        final_digits = [[int(d) for d in num] for num in numbers]

        # rolling だけを先に初期化（5行 × 6桁）
        rolling = [[0] * 6 for _ in range(5)]

        # 桁ごとにルーレット
        for col in range(6):

            # 高速回転
            for _ in range(12):
                for row in range(5):
                    rolling[row][col] = random.randint(0, 9)

                # 表示形式
                desc = "\n".join(
                    "".join(DIGIT_EMOJIS[d] for d in rolling[row])
                    for row in range(5)
                )

                embed = discord.Embed(
                    title=f"🎰 第{rank}等 抽選中（5名）",
                    description=desc,
                    color=0x3498DB
                )
                await msg.edit(embed=embed)
                await asyncio.sleep(0.08)

            # 一桁確定
            for row in range(5):
                rolling[row][col] = final_digits[row][col]

            desc = "\n".join(
                "".join(DIGIT_EMOJIS[d] for d in rolling[row])
                for row in range(5)
            )
            embed = discord.Embed(
                title=f"🎉 第{rank}等 確定！（5名）",
                description=desc,
                color=0x2ecc71
            )
            await msg.edit(embed=embed)
            await asyncio.sleep(0.5)

        # DB登録
        guild_id = str(interaction.guild.id)
        all_entries = await self.jumbo_db.get_all_numbers(guild_id)

        for num in numbers:
            user_id = None
            for row in all_entries:
                if row["number"] == num:
                    user_id = row["user_id"]
                    break
            await self.jumbo_db.set_winner(guild_id, rank, num, user_id)

        # メッセージ削除して次へ
        await msg.delete()

        view = JumboNextView(self, rank)
        await interaction.followup.send(f"🎫 第{rank}等の発表が完了しました！", view=view)

    # ======================================================
    # １〜５等：1名 絵文字高速ルーレット
    # ======================================================
    async def draw_rank_single(self, interaction, rank, number):

        msg = await interaction.followup.send(
            embed=discord.Embed(
                title=f"🎰 第{rank}等 抽選中…",
                description="準備中…",
                color=0xE67E22
            )
        )

        final_digits = [int(n) for n in number]
        rolling = [0] * 6

        for col in range(6):

            # 高速回転
            for _ in range(12):
                rolling[col] = random.randint(0, 9)

                desc = "".join(DIGIT_EMOJIS[d] for d in rolling)

                embed = discord.Embed(
                    title=f"🎰 第{rank}等 抽選中…",
                    description=desc,
                    color=0xE67E22
                )
                await msg.edit(embed=embed)
                await asyncio.sleep(0.08)

            # 確定
            rolling[col] = final_digits[col]

            desc = "".join(DIGIT_EMOJIS[d] for d in rolling)
            embed = discord.Embed(
                title=f"🎉 第{rank}等 確定！",
                description=desc,
                color=0x2ecc71
            )
            await msg.edit(embed=embed)
            await asyncio.sleep(0.5)

        # 当選登録
        guild_id = str(interaction.guild.id)
        entries = await self.jumbo_db.get_all_numbers(guild_id)
        user_id = None
        for row in entries:
            if row["number"] == number:
                user_id = row["user_id"]
                break
        await self.jumbo_db.set_winner(guild_id, rank, number, user_id)

        # メッセージ削除して次へ
        await msg.delete()

        view = JumboNextView(self, rank)
        await interaction.followup.send(f"🎉 第{rank}等の発表が完了しました！", view=view)

    # ======================================================
    # 最終結果
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
