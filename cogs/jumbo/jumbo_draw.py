# jumbo_draw.py

import discord
from discord.ext import commands
import asyncio
import random
import imageio
from PIL import Image
import os
from io import BytesIO


# =========================================
# 画像パス
# =========================================
DIGIT_PATH = os.path.join(os.path.dirname(__file__), "digits")


# =========================================
# 画像キャッシュ読み込み
# =========================================
digit_cache = {}

def load_digit(num: int):
    """ digit_0.png ~ digit_9.png を読み込む（キャッシュ対応） """
    if num in digit_cache:
        return digit_cache[num]

    path = os.path.join(DIGIT_PATH, f"digit_{num}.png")
    img = Image.open(path).convert("RGBA")
    img = img.resize((200, 200), Image.LANCZOS)

    digit_cache[num] = img
    return img


# =========================================
# GIF（1列用）
# =========================================
async def generate_gif(width, height, columns, result_digits, duration=4.0):
    """
    width, height : GIF全体のサイズ
    columns      : 桁数（通常6）
    result_digits: 確定数字 [0,1,2,3,4,5]
    duration     : 秒数（4秒）
    """

    fps = 18
    frames = int(duration * fps)

    gif_frames = []

    # 数字の幅（隙間あり）
    cell_width = width // columns

    for frame_index in range(frames):

        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        for col in range(columns):

            # 最後の5フレームで着地
            if frame_index < frames - 5:
                digit = random.randint(0, 9)
            else:
                digit = result_digits[col]

            dimg = load_digit(digit)

            # 隙間ありギチギチ配置
            x = col * cell_width + 10
            y = (height // 2) - 100

            img.paste(dimg, (x, y), dimg)

        gif_frames.append(img)

    buffer = BytesIO()
    imageio.mimsave(buffer, gif_frames, format="GIF", fps=fps)
    buffer.seek(0)
    return buffer


# =========================================
# GIF（5列 × 6桁 = 5名同時抽選）
# =========================================
async def generate_gif_multiple(result_list, duration=4.0):
    """
    result_list = [ [6桁], [6桁], [6桁], [6桁], [6桁] ]
    """

    width = 600
    height = 1000  # 高さ余裕
    columns = 6

    fps = 18
    frames = int(duration * fps)

    gif_frames = []

    cell_width = width // columns
    row_height = 180  # 数字の高さ＋余白

    for frame_index in range(frames):

        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        for row, digits in enumerate(result_list):

            for col in range(columns):

                if frame_index < frames - 5:
                    digit = random.randint(0, 9)
                else:
                    digit = digits[col]

                dimg = load_digit(digit)

                x = col * cell_width + 10
                y = row * row_height + 20

                img.paste(dimg, (x, y), dimg)

        gif_frames.append(img)

    buffer = BytesIO()
    imageio.mimsave(buffer, gif_frames, format="GIF", fps=fps)
    buffer.seek(0)
    return buffer


# =========================================
# 次へボタン
# =========================================
class NextView(discord.ui.View):

    def __init__(self, message_to_delete: discord.Message):
        super().__init__(timeout=None)
        self.message_to_delete = message_to_delete
        self.pressed = False

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.primary)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):

        # 押されたことを記録 → メインロジックを進める
        self.pressed = True

        # GIFメッセージ削除
        try:
            await self.message_to_delete.delete()
        except:
            pass

        await interaction.response.send_message("次へ進みます…", ephemeral=True)
        self.stop()


# =========================================
# メイン抽選クラス
# =========================================
class JumboDrawHandler:

    def __init__(self, bot, jumbo_db):
        self.bot = bot
        self.db = jumbo_db


    async def start(self, interaction):

        await interaction.response.send_message("🎉 年末ジャンボ抽選開始！")
        await asyncio.sleep(1)

        guild_id = str(interaction.guild.id)
        entries = await self.db.get_all_entries(guild_id)

        if not entries:
            return await interaction.followup.send("⚠ 購入者がいません。")

        # 1〜5等
        for rank in range(1, 6):
            await self.draw_rank(interaction, guild_id, entries, rank)

        # 6等（5名同時）
        await self.draw_rank_6(interaction, guild_id, entries)

        await interaction.followup.send("🎉 **年末ジャンボ全抽選が完了しました！**")


    # --------------------------------------------------
    # 1〜5等（1名）
    # --------------------------------------------------
    async def draw_rank(self, interaction, guild_id, entries, rank: int):

        await interaction.followup.send(f"🎰 第{rank}等 抽選中…")

        winner = random.choice(entries)
        number = winner["number"]
        user_id = winner["user_id"]

        digits = [int(c) for c in number]

        # GIF生成
        gif = await generate_gif(600, 240, 6, digits, duration=4.0)

        file = discord.File(gif, filename="draw.gif")

        # ネタバレ防止 → まずGIFだけ表示
        msg = await interaction.followup.send(
            f"🎉 **第{rank}等 当選番号 発表！**\n（数字はアニメーション後に表示されます）",
            file=file
        )

        # 次へボタンを置く
        view = NextView(msg)
        await msg.edit(view=view)

        # ボタンが押されるまで待つ
        timeout = await view.wait()

        # ボタン押されたら当選情報を表示
        await interaction.followup.send(
            f"✨ **第{rank}等 確定！**\n番号：`{number}`\n当選者：<@{user_id}>"
        )


    # --------------------------------------------------
    # 6等（5名同時抽選）
    # --------------------------------------------------
    async def draw_rank_6(self, interaction, guild_id, entries):

        await interaction.followup.send("🎰 第6等 抽選中…（5名）")

        winners = random.sample(entries, 5)
        numbers = [w["number"] for w in winners]
        digits_list = [[int(c) for c in num] for num in numbers]

        gif = await generate_gif_multiple(digits_list, duration=4.0)
        file = discord.File(gif, filename="draw6.gif")

        msg = await interaction.followup.send(
            "🎉 **第6等 当選番号 5名 発表！**\n（数字はアニメーション後に表示されます）",
            file=file
        )

        view = NextView(msg)
        await msg.edit(view=view)

        timeout = await view.wait()

        # 結果表示
        result_text = "✨ **第6等 確定！**\n\n"
        for num, w in zip(numbers, winners):
            result_text += f"番号 `{num}` → <@{w['user_id']}>\n"

        await interaction.followup.send(result_text)
