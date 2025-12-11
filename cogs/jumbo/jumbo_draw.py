# jumbo_draw.py
# ---------------------------------------------------------
# 🎉 Oasis 年末ジャンボ 抽選モジュール
# ---------------------------------------------------------
# 仕様：
#  - 抽選順は 6等 → 5等 → 4等 → 3等 → 2等 → 1等
#  - GIF は 6桁 / 1200px 幅で見切れゼロ
#  - 6等のみ 5名同時抽選（1200×1000）
#  - GIF ルーレットは 4秒
#  - 次へボタンで手動進行
#  - 最終結果は 1つのEmbedにまとめる
# ---------------------------------------------------------

import discord
from discord.ext import commands
import asyncio
import random
import imageio
from PIL import Image
from io import BytesIO
import os


# ---------------------------------------------------------
# デジット画像キャッシュ
# ---------------------------------------------------------
DIGIT_PATH = os.path.join(os.path.dirname(__file__), "digits")
digit_cache = {}


def load_digit(num: int):
    """digit_0.png ～ digit_9.png を読み込む"""
    if num in digit_cache:
        return digit_cache[num]

    path = os.path.join(DIGIT_PATH, f"digit_{num}.png")
    img = Image.open(path).convert("RGBA")

    # GIF で綺麗に使うため統一サイズ 200×200
    img = img.resize((200, 200), Image.LANCZOS)

    digit_cache[num] = img
    return img


# ---------------------------------------------------------
# ★ 単体レーン GIF（1〜5等用）
# ---------------------------------------------------------
async def generate_gif_single(result_digits, duration=4.0):
    """
    result_digits : 確定6桁 [d1,d2,...]
    GIF 出力：1200×250
    """

    width = 1200
    height = 250
    columns = 6

    fps = 18
    frames = int(duration * fps)

    gif_frames = []

    for frame_index in range(frames):
        frame = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        for col in range(columns):

            # 最後の5フレームで確定へ寄せる
            if frame_index < frames - 5:
                digit = random.randint(0, 9)
            else:
                digit = result_digits[col]

            dimg = load_digit(digit)

            # 横 200px × 6 = 1200px
            x = col * 200
            y = (height // 2) - 100  # 中央寄せ

            frame.paste(dimg, (x, y), dimg)

        gif_frames.append(frame)

    buffer = BytesIO()
    imageio.mimsave(buffer, gif_frames, format="GIF", fps=fps)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------
# ★ 6等（5レーン同時抽選）
# ---------------------------------------------------------
async def generate_gif_multi(result_lists, duration=4.0):
    """
    result_lists : [[6桁], [6桁], [6桁], [6桁], [6桁]]
    5名分まとめて抽選
    """

    width = 1200
    height = 1000  # 200px × 5行
    rows = 5
    columns = 6

    fps = 18
    frames = int(duration * fps)

    gif_frames = []

    for frame_index in range(frames):

        frame = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        for row in range(rows):
            digits = result_lists[row]

            for col in range(columns):

                if frame_index < frames - 5:
                    digit = random.randint(0, 9)
                else:
                    digit = digits[col]

                dimg = load_digit(digit)

                x = col * 200
                y = row * 200

                frame.paste(dimg, (x, y), dimg)

        gif_frames.append(frame)

    buffer = BytesIO()
    imageio.mimsave(buffer, gif_frames, format="GIF", fps=fps)
    buffer.seek(0)
    return buffer
# ---------------------------------------------------------
# ★ 次へボタン（手動で抽選を進行）
# ---------------------------------------------------------
class NextButtonView(discord.ui.View):
    def __init__(self, msg_to_delete: discord.Message):
        super().__init__(timeout=None)
        self.msg_to_delete = msg_to_delete

    @discord.ui.button(label="次へ ➜", style=discord.ButtonStyle.primary)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        # GIFメッセージを削除
        try:
            await self.msg_to_delete.delete()
        except:
            pass

        await interaction.response.send_message("次へ進みます…", ephemeral=True)
        self.stop()


# ---------------------------------------------------------
# ★ 抽選メインクラス
# ---------------------------------------------------------
class JumboDrawHandler:
    def __init__(self, bot, jumbo_db):
        self.bot = bot
        self.db = jumbo_db
        self.results = {}  # rank -> [(number, user_id), ...]

    # -----------------------------------------------------
    # ★ 抽選開始（6 → 1等）
    # -----------------------------------------------------
    async def start(self, interaction: discord.Interaction):

        await interaction.response.send_message("🎉 年末ジャンボ抽選開始！", ephemeral=False)
        await asyncio.sleep(1)

        guild_id = str(interaction.guild.id)

        # 購入番号取得
        entries = await self.db.get_all_numbers(guild_id)
        if not entries:
            return await interaction.followup.send("⚠ 購入者がいません。")

        # 6等 → 1等
        await self.draw_rank_6(interaction, entries)       # 6等（5名）
        await self.draw_rank_single(interaction, entries, 5)
        await self.draw_rank_single(interaction, entries, 4)
        await self.draw_rank_single(interaction, entries, 3)
        await self.draw_rank_single(interaction, entries, 2)
        await self.draw_rank_single(interaction, entries, 1)

        # 最後に総まとめ
        await self.send_summary(interaction)

    # -----------------------------------------------------
    # ★ 単体抽選（5〜1等）
    # -----------------------------------------------------
    async def draw_rank_single(self, interaction, entries, rank: int):
        await interaction.followup.send(f"🎰 第{rank}等 抽選中…")

        # ランダム1名
        winner = random.choice(entries)
        number = winner["number"]
        user_id = winner["user_id"]

        digits = [int(c) for c in number]

        # GIF生成
        gif = await generate_gif_single(digits, duration=4.0)
        file = discord.File(gif, filename=f"rank{rank}.gif")

        # GIF表示（ネタバレ防止、番号を表示しない）
        msg = await interaction.followup.send(
            f"🎬 **第{rank}等 抽選結果…！（ネタバレ防止中）**",
            file=file
        )

        # ボタン
        view = NextButtonView(msg)
        await msg.edit(view=view)
        await view.wait()

        # 結果を記録（後でまとめて発表）
        if rank not in self.results:
            self.results[rank] = []
        self.results[rank].append((number, user_id))

    # -----------------------------------------------------
    # ★ 6等（5名同時 抽選）
    # -----------------------------------------------------
    async def draw_rank_6(self, interaction, entries):
        await interaction.followup.send("🎰 第6等（5名） 抽選中…")

        winners = random.sample(entries, 5)
        numbers = [w["number"] for w in winners]
        digits_list = [[int(c) for c in num] for num in numbers]

        gif = await generate_gif_multi(digits_list, duration=4.0)
        file = discord.File(gif, filename="rank6.gif")

        msg = await interaction.followup.send(
            "🎬 **第6等（5名）抽選結果…！（ネタバレ防止中）**",
            file=file
        )

        view = NextButtonView(msg)
        await msg.edit(view=view)
        await view.wait()

        # 結果を記録
        self.results[6] = []
        for num, w in zip(numbers, winners):
            self.results[6].append((num, w["user_id"]))
# ---------------------------------------------------------
# ★ 総まとめ結果 Embed
# ---------------------------------------------------------
    async def send_summary(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🎉 年末ジャンボ 当選結果",
            description="おめでとうございます！\n\n※番号は「番号 → ユーザー名」で表示",
            color=0xF1C40F
        )

        # 6等 → 1等 の順で表示
        for rank in [6, 5, 4, 3, 2, 1]:

            if rank not in self.results:
                continue

            lines = []
            for number, user_id in self.results[rank]:
                lines.append(f"・`{number}` → <@{user_id}>")

            embed.add_field(
                name=f"【第{rank}等】",
                value="\n".join(lines),
                inline=False
            )

        embed.set_footer(text="Oasis 年末ジャンボ 2025")

        await interaction.followup.send(embed=embed)
