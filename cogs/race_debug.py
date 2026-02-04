import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

class RaceDebug(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(
        name="レース即抽選",
        description="【デバッグ】現在のエントリーから即抽選して出走決定パネルを表示"
    )
    async def debug_race_lottery(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        today = datetime.now(JST).date()

        races = await self.db.get_today_race_schedules(today)
        if not races:
            return await interaction.followup.send(
                "❌ 本日のレースがありません",
                ephemeral=True
            )

        race = races[0]

        entries = await self.db.get_race_entries_by_schedule(
            race_date=today,
            schedule_id=race["id"]
        )

        if len(entries) <= 1:
            return await interaction.followup.send(
                "❌ エントリーが2体未満です",
                ephemeral=True
            )

        selected = random.sample(entries, k=min(8, len(entries)))

        # 表示だけ（DBは一切更新しない）
        await self.send_race_entry_panel(race, selected)

        await interaction.followup.send(
            f"✅ デバッグ抽選完了（{len(selected)}体）",
            ephemeral=True
        )

    # =========================
    # 出走決定パネル（仮）
    # =========================
    async def send_race_entry_panel(self, race: dict, entries: list[dict]):
        channel = self.bot.get_channel(1466693608366276793)
        if not channel:
            return

        embed = discord.Embed(
            title=f"🏁 第{race['race_no']}レース 出走決定（デバッグ）",
            description=f"{race['race_time']}｜{race['distance']}｜{race['surface']}｜{race['condition']}",
            color=discord.Color.orange()
        )

        for i, e in enumerate(entries, start=1):
            pet = await self.db.get_oasistchi_pet(e["pet_id"])
            embed.add_field(
                name=f"枠 {i}",
                value=f"<@{e['user_id']}>\n🐣 {pet['name']}",
                inline=False
            )

        await channel.send(embed=embed)


async def setup(bot):
    cog = RaceDebug(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))


