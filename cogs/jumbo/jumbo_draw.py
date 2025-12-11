# jumbo_draw.py
import discord
from discord.ext import commands
import asyncio
import random
import imageio
from PIL import Image
import os
from io import BytesIO

DIGIT_PATH = os.path.join(os.path.dirname(__file__), "digits")


# ─────────────────────────────────────────────
# ★ 画像読み込み（キャッシュ）
# ─────────────────────────────────────────────
digit_cache = {}

def load_digit(num: int):
    """digit_0.png 〜 digit_9.png を読み込む"""
    if num in digit_cache:
        return digit_cache[num]

    path = os.path.join(DIGIT_PATH, f"digit_{num}.png")
    img = Image.open(path).convert("RGBA")

    # 念のため 200x200 に揃える
    img = img.resize((200, 200), Image.LANCZOS)

    digit_cache[num] = img
    return img


# ─────────────────────────────────────────────
# ★ GIF生成本体
# ─────────────────────────────────────────────
async def generate_gif(width, height, columns, result_digits, duration=2.0):
    """
    width, height  : GIF全体のサイズ
    columns        : 桁数（通常6桁）
    result_digits  : 最後に確定する数字 [1st,2nd,...]
    duration       : 秒（2秒）
    """

    fps = 18
    frames = int(duration * fps)

    # 1フレームずつ生成
    gif_frames = []

    for frame_index in range(frames):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        for col in range(columns):
            # ランダム数字または確定寄せ
            if frame_index < frames - 3:
                # ランダム高速回転
                digit = random.randint(0, 9)
            else:
                # 最終3フレームで確定数字に寄せる
                digit = result_digits[col]

            dimg = load_digit(digit)

            # ─ ギチギチ配置（隙間ゼロ） ─
            x = col * (width // columns)
            y = (height // 2) - 100  # 数字の高さ200px → 中央配置
            img.paste(dimg, (x, y), dimg)

        gif_frames.append(img)

    # GIF書き出し
    buffer = BytesIO()
    imageio.mimsave(buffer, gif_frames, format="GIF", fps=fps)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# ★ 6等用（5名ぶん同時抽選）
# ─────────────────────────────────────────────
async def generate_gif_multiple(result_list):
    """
    result_list = [ [6桁], [6桁], [6桁], [6桁], [6桁] ]  
    5名ぶんの番号リスト
    """
    width, height = 600, 600
    columns = 6

    fps = 18
    frames = int(2.0 * fps)

    gif_frames = []

    for frame_index in range(frames):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))

        for row, digits in enumerate(result_list):
            for col in range(columns):
                # ランダム or 確定寄せ
                if frame_index < frames - 3:
                    digit = random.randint(0, 9)
                else:
                    digit = digits[col]

                dimg = load_digit(digit)

                x = col * 100  # 600 / 6 = 100
                y = row * 100
                img.paste(dimg, (x, y), dimg)

        gif_frames.append(img)

    buffer = BytesIO()
    imageio.mimsave(buffer, gif_frames, format="GIF", fps=fps)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# ★ 次へボタン
# ─────────────────────────────────────────────
class NextView(discord.ui.View):
    def __init__(self, message_to_delete: discord.Message):
        super().__init__(timeout=None)
        self.message_to_delete = message_to_delete

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.primary)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 押されたら古いGIFメッセージを削除
        try:
            await self.message_to_delete.delete()
        except:
            pass

        await interaction.response.send_message("次の抽選へ進みます…", ephemeral=True)
        self.stop()


# ─────────────────────────────────────────────
# ★ メイン抽選クラス
# ─────────────────────────────────────────────
class JumboDrawHandler:
    def __init__(self, bot, jumbo_db):
        self.bot = bot
        self.db = jumbo_db

    async def start(self, interaction):
        await interaction.response.send_message("🎉 年末ジャンボ抽選開始！", ephemeral=False)
        await asyncio.sleep(1)

        guild_id = str(interaction.guild.id)

        # 全購入番号をDBから取得
        entries = await self.db.get_all_entries(guild_id)
        if not entries:
            return await interaction.followup.send("⚠ 購入者がいません。")

        # ランク別に抽選開始
        await self.draw_rank(interaction, guild_id, entries, 1)
        await self.draw_rank(interaction, guild_id, entries, 2)
        await self.draw_rank(interaction, guild_id, entries, 3)
        await self.draw_rank(interaction, guild_id, entries, 4)
        await self.draw_rank(interaction, guild_id, entries, 5)

        # 6等は5名同時抽選
        await self.draw_rank_6(interaction, guild_id, entries)

        await interaction.followup.send("🎉 **年末ジャンボ全抽選が完了しました！！**")

    # ──────────────────────────
    # ★ 1〜5等の抽選
    # ──────────────────────────
    async def draw_rank(self, interaction, guild_id, entries, rank: int):
        await interaction.followup.send(f"🎰 第{rank}等 抽選中…")

        # ランダムに1つ選ぶ
        winner = random.choice(entries)
        number = winner["number"]
        user_id = winner["user_id"]

        digits = [int(c) for c in number]

        # GIF生成
        gif = await generate_gif(600, 200, 6, digits, duration=2.0)

        # GIF送信
        file = discord.File(gif, filename="draw.gif")
        msg = await interaction.followup.send(
            f"🎉 **第{rank}等 当選番号 発表！**\n番号：`{number}` → <@{user_id}>",
            file=file
        )

        # 次へボタン
        view = NextView(msg)
        await msg.edit(view=view)

    # ──────────────────────────
    # ★ 6等（5名同時抽選）
    # ──────────────────────────
    async def draw_rank_6(self, interaction, guild_id, entries):
        await interaction.followup.send("🎰 第6等 抽選中…（5名）")

        winners = random.sample(entries, 5)
        numbers = [w["number"] for w in winners]

        digits_list = [[int(c) for c in num] for num in numbers]

        # GIF生成（5名同時）
        gif = await generate_gif_multiple(digits_list)

        file = discord.File(gif, filename="draw6.gif")
        msg = await interaction.followup.send(
            "🎉 **第6等 当選番号 5名 発表！**",
            file=file
        )

        # 次へボタン
        view = NextView(msg)
        await msg.edit(view=view)
