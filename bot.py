# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from db import Database

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True

# Bot インスタンス作成
bot = commands.Bot(command_prefix="!", intents=intents)

# ★★★ ここで GUILD_IDS を登録（正しい場所） ★★★
bot.GUILD_IDS = [
    1444580349773348951,   # 新しい方
    1420918259187712093    # もともとの方
]

# DB
bot.db = Database()

# --------------------------------
# Bot 起動時
# --------------------------------
@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")

    # DB初期化
    await bot.db.init_db()
    print("データベース準備完了")

    # Cog 読み込み
    await load_cogs()

    # スラッシュコマンド同期（複数ギルド）
    for gid in bot.GUILD_IDS:
        guild_obj = discord.Object(id=gid)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"Slash Command 同期完了（{len(synced)}個） for {gid}")


# --------------------------------
# Cog 読み込み
# --------------------------------
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


# --------------------------------
# 実行
# --------------------------------
if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
