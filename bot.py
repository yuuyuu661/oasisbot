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
intents.guilds = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

bot.GUILD_IDS = [
    1444580349773348951,
    1420918259187712093
]

bot.db = Database()


@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")
    print("✔ Bot Ready 完了")


# ------------------------------
# Cog ロード
# ------------------------------
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
        "cogs.backup",
        "cogs.slot",
    ]

    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Cog 読み込み成功: {ext}")
        except Exception as e:
            print(f"Cog 読み込み失敗: {ext} - {e}")


# ------------------------------
# Slash 同期（ギルド専用）
# ------------------------------
async def sync_slash_commands():
    print("🧹 Slash Command 同期開始")

    # グローバルは完全削除（亡霊対策）
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()

    for gid in bot.GUILD_IDS:
        guild = discord.Object(id=gid)
        bot.tree.clear_commands(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Slash 同期完了（{len(synced)}個） for {gid}")

    print("✔ Slash Command 完全同期完了")


# ------------------------------
# メイン起動
# ------------------------------
async def main():
    await bot.db.connect()
    print("データベース準備完了")

    await load_cogs()
    print("すべての Cog ロード完了")

    await sync_slash_commands()

    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
