import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta, date

JST = timezone(timedelta(hours=9))

def today_jst_date():
    return datetime.now(JST).date()

class RaceDebug(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(
        name="レース即抽選",
        description="【デバッグ】pending中のエントリーから即抽選して出走決定パネルを表示"
    )
    async def debug_race_lottery(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        today = today_jst_date()
        guild_id = str(interaction.guild.id)

        races = await self.db.get_today_race_schedules(today, guild_id)
        if not races:
            return await interaction.followup.send("❌ 本日のレースがありません", ephemeral=True)

        target_race = None
        pending_count = 0

        for race in races:
            pending = await self.db.get_race_entries_pending(
                guild_id,
                today,
                race["id"]
            )

            if len(pending) >= 2:
                target_race = race
                pending_count = len(pending)
                break

        if not target_race:
            return await interaction.followup.send(
                "❌ 抽選可能なレースがありません（pending が2体以上なし）",
                ephemeral=True
            )

        race_cog = self.bot.get_cog("OasistchiCog")
        if not race_cog:
            return await interaction.followup.send("❌ レース処理Cogが見つかりません", ephemeral=True)

        await race_cog.run_race_lottery(target_race)

        await interaction.followup.send(
            (
                "✅ **デバッグ抽選完了！**\n"
                f"🆔 race_id: `{target_race['id']}`\n"
                f"🕘 第{target_race['race_no']}レース（{target_race['race_time']}）\n"
                f"👥 pending: {pending_count}体"
            ),
            ephemeral=True
        )


    @app_commands.command(
        name="race_entries_debug",
        description="【デバッグ】本日のレースエントリー状況（race_id表示）"
    )
    async def race_entries_debug(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        race_date = datetime.now(JST).date()
        races = await self.db.get_today_race_schedules(race_date)

        if not races:
            return await interaction.followup.send(
                "❌ 本日のレースが存在しません。",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🧪 本日のレースエントリー状況",
            description=f"📅 {race_date}",
            color=discord.Color.blue()
        )

        for race in races:
            entries = await self.db.conn.fetch("""
                SELECT *
                FROM race_entries
                WHERE race_date = $1
                  AND schedule_id = $2
            """, race_date, race["id"])

            pending = [e for e in entries if e["status"] == "pending"]
            selected = [e for e in entries if e["status"] == "selected"]
            cancelled = [e for e in entries if e["status"] == "cancelled"]

            value = (
                f"🆔 race_id: `{race['id']}`\n"
                f"📝 pending: {len(pending)}\n"
                f"✅ selected: {len(selected)}\n"
                f"❌ cancelled: {len(cancelled)}"
            )

            if pending:
                lines = []
                for e in pending:
                    lines.append(f"・pet_id `{e['pet_id']}` / <@{e['user_id']}>")
                value += "\n" + "\n".join(lines)

            embed.add_field(
                name=f"第{race['race_no']}レース｜🕘 {race['race_time']}",
                value=value,
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="race_entries_reset",
        description="【デバッグ】本日のレースエントリーを全リセット"
    )
    async def race_entries_reset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        race_date = today_jst_date()

        # race_entries 全削除
        await self.db.conn.execute("""
            DELETE FROM race_entries
            WHERE race_date = $1
        """, race_date)

        # race_schedules 状態リセット
        await self.db.conn.execute("""
            UPDATE race_schedules
            SET
                lottery_done = FALSE,
                race_finished = FALSE
            WHERE race_date = $1
        """, race_date)

        await interaction.followup.send(
            f"🧹 **本日のレースエントリーをリセットしました**\n"
            f"📅 {race_date}\n"
            f"・エントリー全削除\n"
            f"・抽選／完了フラグ初期化",
            ephemeral=True
        )


async def setup(bot):
    cog = RaceDebug(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))




















