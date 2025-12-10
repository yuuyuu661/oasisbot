# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from db import Database

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# intents（ホテル機能対応版）
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True

# Bot インスタンス作成
bot = commands.Bot(command_prefix="!", intents=intents)

# GUILD_IDS
bot.GUILD_IDS = [
    1444580349773348951,
    1420918259187712093
]

# DB
bot.db = Database()


@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")

    await bot.db.init_db()
    print("データベース準備完了")

    await load_cogs()

    for gid in bot.GUILD_IDS:
        guild_obj = discord.Object(id=gid)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"Slash Command 同期完了（{len(synced)}個） for {gid}")


async def load_cogs():
    extensions = [
        "cogs.balance",
        "cogs.salary",
        "cogs.admin",
        "cogs.init",
        "cogs.interview",
        "cogs.subscription",
        "cogs.hotel.setup",
        "cogs.gamble", 
        "cogs.jumbo.jumbo", 
    ]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Cog 読み込み成功: {ext}")
        except Exception as e:
            print(f"Cog 読み込み失敗: {ext} - {e}")


if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))








