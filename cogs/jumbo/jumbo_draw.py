# jumbo_draw.py
# ---------------------------------------------------------
# Oasis 年末ジャンボ 抽選モジュール
# ---------------------------------------------------------
#   - 抽選順：6等 → 5等 → 4等 → 3等 → 2等 → １等
#   - GIFは1200px幅（数字6桁 × 200px）で見切れゼロ
#   - 6等は5レーン同時抽選（1200×1000）
#   - 枠は金色（outline）
#   - ルーレットは4秒・高速
#   - ネタバレ防止：抽選中は番号表示なし
#   - Nextボタンで進行、押した瞬間に当選番号書き換え
#   - 最後は等級ごとにEmbedを色分けして豪華発表
# ---------------------------------------------------------

import discord
from discord.ext import commands
import asyncio
import random
import imageio
from PIL import Image, ImageDraw
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

    # GIFで綺麗に使うため統一サイズ 200×200
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

            x = col * 200   # 200px × 6 = 1200px
            y = (height // 2) - 100

            frame.paste(dimg, (x, y), dimg)

        # ★ 金枠（豪華仕様）
        draw = ImageDraw.Draw(frame)
        draw.rectangle(
            [0, 0, width - 1, height - 1],
            outline=(255, 215, 0, 255),  # gold
            width=8
        )

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
    height = 1000  # 200×5
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

        # ★ 金枠
        draw = ImageDraw.Draw(frame)
        draw.rectangle(
            [0, 0, width - 1, height - 1],
            outline=(255, 215, 0, 255),
            width=8
        )

        gif_frames.append(frame)

    buffer = BytesIO()
    imageio.mimsave(buffer, gif_frames, format="GIF", fps=fps)
    buffer.seek(0)
    return buffer
# ---------------------------------------------------------
# ★ 次へボタン（手動で抽選を進行）
# ---------------------------------------------------------
class NextButtonView(discord.ui.View):
    def __init__(self, msg_gif: discord.Message, msg_status: discord.Message,
                 rank: int, number: str, user_id: str):
        """
        msg_gif     : GIF のメッセージ
        msg_status  : 「第◯等 抽選中…」のメッセージ
        rank        : 等級
        number      : 当選番号
        user_id     : 当選者ID
        """
        super().__init__(timeout=None)
        self.msg_gif = msg_gif
        self.msg_status = msg_status
        self.rank = rank
        self.number = number
        self.user_id = user_id

    @discord.ui.button(label="次へ ➜", style=discord.ButtonStyle.primary)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):

        # GIF を削除
        try:
            await self.msg_gif.delete()
        except:
            pass

        # 抽選中メッセージを書き換え
        try:
            await self.msg_status.edit(
                content=(
                    f"🎉 **第{self.rank}等 当選番号 発表！**\n"
                    f"番号：`{self.number}`\n"
                    f"当選者：<@{self.user_id}>"
                )
            )
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

        # 結果保存用：rank → [(number, user_id), ...]
        self.results = {}

    # -----------------------------------------------------
    # ★ 抽選開始（6 → 1等）
    # -----------------------------------------------------
    async def start(self, interaction: discord.Interaction):

        await interaction.response.send_message("🎉 年末ジャンボ抽選開始！", ephemeral=False)
        await asyncio.sleep(1)

        guild_id = str(interaction.guild.id)

        # 番号一覧取得
        entries = await self.db.get_all_numbers(guild_id)
        if not entries:
            return await interaction.followup.send("⚠ 購入者がいません。")

        # 6 → 1等の順に抽選
        await self.draw_rank_6(interaction, entries)
        await self.draw_rank_single(interaction, entries, 5)
        await self.draw_rank_single(interaction, entries, 4)
        await self.draw_rank_single(interaction, entries, 3)
        await self.draw_rank_single(interaction, entries, 2)
        await self.draw_rank_single(interaction, entries, 1)

        # 全て終わったらまとめ発表
        await self.send_summary(interaction)

    # -----------------------------------------------------
    # ★ 単体抽選（5〜1等）
    # -----------------------------------------------------
    async def draw_rank_single(self, interaction, entries, rank: int):

        # 「第◯等 抽選中…」メッセージを保持
        msg_status = await interaction.followup.send(f" 第{rank}等 抽選中…")

        # ランダムに1名選出
        winner = random.choice(entries)
        number = winner["number"]
        user_id = winner["user_id"]
        digits = [int(c) for c in number]

        # GIF生成
        gif = await generate_gif_single(digits, duration=4.0)
        file = discord.File(gif, filename=f"rank{rank}.gif")

        # GIF表示
        msg_gif = await interaction.followup.send(
            f"**第{rank}等 抽選結果…**",
            file=file
        )

        # Nextボタン配置（押したら書き換え）
        view = NextButtonView(
            msg_gif=msg_gif,
            msg_status=msg_status,
            rank=rank,
            number=number,
            user_id=user_id
        )
        await msg_gif.edit(view=view)
        await view.wait()

        # 結果保存
        if rank not in self.results:
            self.results[rank] = []
        self.results[rank].append((number, user_id))

    # -----------------------------------------------------
    # ★ 6等（5名同時抽選）
    # -----------------------------------------------------
    async def draw_rank_6(self, interaction, entries):

        # ステータスメッセージ
        msg_status = await interaction.followup.send(" 第6等（5名） 抽選中…")

        # 5名選出
        winners = random.sample(entries, 5)
        numbers = [w["number"] for w in winners]
        digits_list = [[int(c) for c in num] for num in numbers]

        # GIF生成
        gif = await generate_gif_multi(digits_list, duration=4.0)
        file = discord.File(gif, filename="rank6.gif")

        msg_gif = await interaction.followup.send(
            " **第6等 抽選結果…**",
            file=file
        )

        # 6等は5人分を保持して後でまとめて表示
        # Nextボタン押されたら番号を1人ずつ表示するのではなく、まとめて表示
        # → msg_status を「6等結果まとめ」に書き換え
        result_text = ""
        for num, w in zip(numbers, winners):
            result_text += f"・`{num}` → <@{w['user_id']}>\n"

        view = NextButtonView(
            msg_gif=msg_gif,
            msg_status=msg_status,
            rank=6,
            number="複数",      # 実際は使わない
            user_id="複数"       # 実際は使わない
        )

        # この部分だけ特例：後で書き換える本文を保持
        view.result_text_multi = result_text

        await msg_gif.edit(view=view)
        await view.wait()

        # 6等結果を保存
        self.results[6] = []
        for num, w in zip(numbers, winners):
            self.results[6].append((num, w["user_id"]))
# ---------------------------------------------------------
# ★ 等級別まとめ結果（豪華カラー・Embed分割）
# ---------------------------------------------------------
    async def send_summary(self, interaction: discord.Interaction):

        await interaction.followup.send("🎉 **全ての抽選が終了しました！**\n最終結果を発表します…")

        # 等級ごとに豪華カラー
        rank_colors = {
            6: 0xC0C0C0,   # 銀
            5: 0xCD7F32,   # ブロンズ
            4: 0x4AA3FF,   # 青宝石
            3: 0xC77DFF,   # 紫水晶
            2: 0xE74C3C,   # 赤（強運）
            1: 0xF1C40F,   # 金（最上位）
        }

        # 6 → 1 等の順で豪華に表示
        for rank in [6, 5, 4, 3, 2, 1]:

            if rank not in self.results:
                continue

            embed = discord.Embed(
                title=f"🎉 第{rank}等 当選結果",
                color=rank_colors[rank]
            )

            lines = []
            for number, user_id in self.results[rank]:
                lines.append(f"・`{number}` → <@{user_id}>")

            embed.description = "\n".join(lines)
            embed.set_footer(text="Oasis 年末ジャンボ 2025")

            await interaction.followup.send(embed=embed)

