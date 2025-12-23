# bot.py
import os
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


class OasisBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()
        self.GUILD_IDS = [
            1444580349773348951,
            1420918259187712093
        ]

    async def setup_hook(self):
        # DB
        await self.db.connect()
        print("データベース準備完了")

        # Cogs
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
                await self.load_extension(ext)
                print(f"Cog 読み込み成功: {ext}")
            except Exception as e:
                print(f"Cog 読み込み失敗: {ext} - {e}")

        print("すべての Cog ロード完了")

        # Slash 同期（ここが正解の場所）
        print("🧹 Slash Command 同期開始")

        self.tree.clear_commands(guild=None)
        await self.tree.sync()

        for gid in self.GUILD_IDS:
            guild = discord.Object(id=gid)
            self.tree.clear_commands(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Slash 同期完了（{len(synced)}個） for {gid}")

        print("✔ Slash Command 完全同期完了")


bot = OasisBot()


@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")
    print("✔ Bot Ready 完了")


if __name__ == "__main__":
    bot.run(TOKEN)
