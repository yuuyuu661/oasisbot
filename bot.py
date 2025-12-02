# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from db import Database

# -----------------------
#        設定
# -----------------------

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
bot.GUILD_IDS = [1444580349773348951, 1420918259187712093]
GUILD = discord.Object(id=GUILD_ID)

# intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.db = Database()

# ★★ ここ追加！！ ★★
# Cog 全体で参照するギルドIDリスト
bot.GUILD_IDS = [GUILD_ID]


# -----------------------
#   Bot 起動時イベント
# -----------------------

@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")

    # DB初期化
    await bot.db.init_db()
    print("データベース準備完了")

    # Cog 読み込み
    await load_cogs()

    # ★ 同期対象を bot.GUILD_IDS に変更
    for gid in bot.GUILD_IDS:
        synced = await bot.tree.sync(guild=discord.Object(id=gid))
        print(f"Slash Command 同期完了（{len(synced)}個） in {gid}")


# -----------------------
#     Cog の読み込み
# -----------------------

async def load_cogs():
    extensions = [
        "cogs.balance",
        "cogs.salary",
        "cogs.admin",
        "cogs.init",
    ]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Cog 読み込み成功: {ext}")
        except Exception as e:
            print(f"Cog 読み込み失敗: {ext} - {e}")


# -----------------------
#     Bot 実行
# -----------------------

if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
