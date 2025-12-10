# cogs/jumbo/jumbo_draw.py

import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime, timezone

from .jumbo_db import JumboDB


# ======================================================
# 絵文字数字
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
        6: all_numbers[:5],       # 6等は 5 名
        5: all_numbers[5],
        4: all_numbers[6],
        3: all_numbers[7],
        2: all_numbers[8],
        1: all_numbers[9]
    }
    return winners


# ======================================================
# 次へボタン（押したあとにパネル削除）
# ======================================================
class JumboNextButton(discord.ui.Button):
    def __init__(self, handler, current_rank):
        super().__init__(label="➡️ 次へ", style=discord.ButtonStyle.primary)
        self.handler = handler
        self.current_rank = current_rank

    async def callback(self, interaction: discord.Interaction):
        # ① まず押したことを返す
        await interaction.response.defer()

        # ② 次の抽選処理へ進む
        await self.handler.start_next_rank(interaction, self.current_rank)

        # ③ 次の抽選処理が開始したあとに、元メッセージ削除
        try:
            await interaction.message.delete()
        except:
            pass


class JumboNextView(discord.ui.View):
    def __init__(self, handler, current_rank):
        super().__init__(timeout=None)
        self.add_item(JumboNextButton(handler, current_rank))


# ======================================================
# メイン抽選 Handler
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
            return await interaction.response.send_message("❌ 参加人数が不足しています。", ephemeral=True)

        await interaction.response.send_message("🎉 年末ジャンボ抽選開始！")
        await self.start_rank(interaction, 6)

    async def start_rank(self, interaction, rank):
        if rank == 6:
            await self.draw_rank_multi(interaction, rank, self.winners[rank])
        else:
            await self.draw_rank_single(interaction, rank, self.winners[rank])

    async def start_next_rank(self, interaction, current_rank):
        idx = self.rank_order.index(current_rank)
        if idx == len(self.rank_order) - 1:
            await self.send_final_result(interaction)
            return

        next_rank = self.rank_order[idx + 1]
        await self.start_rank(interaction, next_rank)

    # ======================================================
    # ６等：5名同時抽選（全桁高速回転）
    # ======================================================
    async def draw_rank_multi(self, interaction, rank, numbers):

        msg = await interaction.followup.send(
            embed=discord.Embed(
                title=f"🎰 第{rank}等 抽選中（5名）",
                description="開始します…",
                color=0x3498DB
            )
        )

        final_digits = [[int(d) for d in num] for num in numbers]
        rolling = [[0] * 6 for _ in range(5)]

        # 6桁ぶん繰り返す
        for col in range(6):

            # 全桁高速ルーレット
            for _ in range(18):
                for row in range(5):
                    for i in range(6):
                        if i < col:
                            rolling[row][i] = final_digits[row][i]  # 確定桁
                        else:
                            rolling[row][i] = random.randint(0, 9)

                desc = "\n".join(
                    "".join(DIGIT_EMOJIS[d] for d in rolling[row])
                    for row in range(5)
                )

                await msg.edit(embed=discord.Embed(
                    title=f"🎰 第{rank}等 抽選中（5名）",
                    description=desc,
                    color=0x3498DB
                ))
                await asyncio.sleep(0.04)

            # 一桁確定
            for row in range(5):
                rolling[row][col] = final_digits[row][col]

            desc = "\n".join(
                "".join(DIGIT_EMOJIS[d] for d in rolling[row])
                for row in range(5)
            )

            await msg.edit(embed=discord.Embed(
                title=f"🎉 第{rank}等 確定！（{col+1} 桁目）",
                description=desc,
                color=0x2ecc71
            ))
            await asyncio.sleep(0.35)

        # DB登録
        guild_id = str(interaction.guild.id)
        all_entries = await self.jumbo_db.get_all_numbers(guild_id)

        for num in numbers:
            user_id = next((r["user_id"] for r in all_entries if r["number"] == num), None)
            await self.jumbo_db.set_winner(guild_id, rank, num, user_id)

        # 消して次へ
        try:
            await msg.delete()
        except:
            pass

        await interaction.followup.send(
            f"🎉 第{rank}等の発表が完了しました！",
            view=JumboNextView(self, rank)
        )


    # ======================================================
    # 1〜5等：1名抽選（全桁高速回転）
    # ======================================================
    async def draw_rank_single(self, interaction, rank, number):

        msg = await interaction.followup.send(
            embed=discord.Embed(
                title=f"🎰 第{rank}等 抽選中…",
                description="開始します…",
                color=0xE67E22
            )
        )

        final = [int(n) for n in number]
        rolling = [0] * 6

        for col in range(6):

            # 全桁高速ルーレット
            for _ in range(18):
                for i in range(6):
                    if i < col:
                        rolling[i] = final[i]
                    else:
                        rolling[i] = random.randint(0, 9)

                desc = "".join(DIGIT_EMOJIS[d] for d in rolling)

                await msg.edit(embed=discord.Embed(
                    title=f"🎰 第{rank}等 抽選中…",
                    description=desc,
                    color=0xE67E22
                ))
                await asyncio.sleep(0.04)

            # 一桁確定
            rolling[col] = final[col]

            desc = "".join(DIGIT_EMOJIS[d] for d in rolling)
            await msg.edit(embed=discord.Embed(
                title=f"🎉 第{rank}等 確定！（{col+1} 桁目）",
                description=desc,
                color=0x2ecc71
            ))
            await asyncio.sleep(0.35)

        # 当選登録
        guild_id = str(interaction.guild.id)
        entries = await self.jumbo_db.get_all_numbers(guild_id)
        user_id = next((r["user_id"] for r in entries if r["number"] == number), None)
        await self.jumbo_db.set_winner(guild_id, rank, number, user_id)

        # 消して次へ
        try:
            await msg.delete()
        except:
            pass

        await interaction.followup.send(
            f"🎉 第{rank}等の発表が完了しました！",
            view=JumboNextView(self, rank)
        )


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

        rank_label = {
            1: "1等",
            2: "2等",
            3: "3等",
            4: "4等",
            5: "5等",
            6: "6等（5名）"
        }

        desc = ""

        for rank in [1,2,3,4,5,6]:
            rows = [r for r in winners if r["rank"] == rank]
            if not rows:
                continue

            desc += f"\n**【{rank_label[rank]}】**\n"
            for r in rows:
                user = f"<@{r['user_id']}>" if r["user_id"] else "不明"
                desc += f"- {r['number']} → {user}\n"

        embed.description = desc
        await interaction.followup.send(embed=embed)
