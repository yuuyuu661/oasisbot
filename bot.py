import discord
from discord.ext import commands
import asyncio
import os
from db import Database

# ----------------------------------
# 複数ギルド設定
# ----------------------------------
GUILD_IDS = [
    1420918259187712093,
    1444580349773348951
]

# Botインスタンス作成
bot = commands.Bot(
    command_prefix="!",
    intents=discord.Intents.all()
)

# ★ ここにセットするのが正解！
bot.GUILD_IDS = GUILD_IDS


# ----------------------------------
# 起動時
# ----------------------------------
@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")

    # DB準備
    await bot.db.init()
    print(" データベース準備完了")

    # Cog 読み込み
    for ext in [
        "cogs.balance",
        "cogs.salary",
        "cogs.admin",
        "cogs.init",
    ]:
        try:
            await bot.load_extension(ext)
            print(f" Cog 読み込み成功: {ext}")
        except Exception as e:
            print(f" Cog 読み込み失敗: {ext} - {e}")

    # Slash Command 同期（複数ギルド）
    for gid in bot.GUILD_IDS:
        await bot.tree.sync(guild=discord.Object(id=gid))

    print(" Slash Command 同期完了")


# ----------------------------------
# 実行
# ----------------------------------
from dotenv import load_dotenv
load_dotenv()

bot.db = Database(os.getenv("DATABASE_URL"))
bot.run(os.getenv("DISCORD_TOKEN"))
