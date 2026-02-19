import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import uvicorn

from db import Database
from web_api import app

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WEB_SECRET = os.getenv("WEB_SECRET")

if not WEB_SECRET:
    raise ValueError("WEB_SECRET が設定されていません")

print("🔐 WEB_SECRET loaded (BOT)")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()

        self.GUILD_IDS = [
            1444580349773348951,
            1420918259187712093
        ]

    async def setup_hook(self):
        print("🔌 DB 初期化開始")
        await self.db.init_db()
        print("✅ DB 初期化完了")

        await self.load_cogs()
        print("📦 Cog ロード完了")

        # ---- Guild コマンド同期 ----
        for gid in self.GUILD_IDS:
            guild_obj = discord.Object(id=gid)
            synced = await self.tree.sync(guild=guild_obj)
            print(f"Slash Command 同期完了（{len(synced)}個） for {gid}")

    async def load_cogs(self):
        extensions = [
            "cogs.balance",
            "cogs.salary",
            "cogs.admin",
            "cogs.init",
            "cogs.interview",
            "cogs.subscription",
            "cogs.hotel.setup",
            "cogs.gamble",
            "cogs.backup",
            "cogs.slot",
            "cogs.janken_card",
            "cogs.oasistchi",
            "cogs.race_debug",
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"Cog 読み込み成功: {ext}")
            except Exception as e:
                print(f"❌ Cog 読み込み失敗: {ext} - {e}")
                
bot = MyBot()
@bot.event
async def on_ready():
    print(f"🚀 ログイン完了：{bot.user}")


async def start_bot():
    await bot.start(TOKEN)


async def start_api():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_api())
    loop.create_task(start_bot())
    loop.run_forever()













