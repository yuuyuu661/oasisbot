# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from db import Database

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False  # ★ 同期が1回しか走らないようにする

bot.GUILD_IDS = [
    1444580349773348951,
    1420918259187712093
]

bot.db = Database()


@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")

    await bot.db.init_db()
    print("データベース準備完了")

    await load_cogs()
    print("すべてのCogロード完了")

    # ★ ここが重要！ syncは一度だけ
    if not bot.synced:
        for gid in bot.GUILD_IDS:
            guild_obj = discord.Object(id=gid)
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"Slash Command 同期完了（{len(synced)}個） for {gid}")

        bot.synced = True
        print("✔ コマンド完全同期済み！")


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
        "cogs.jumbo",      # ★正しくここを読む
    ]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Cog 読み込み成功: {ext}")
        except Exception as e:
            print(f"Cog 読み込み失敗: {ext} - {e}")


if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
