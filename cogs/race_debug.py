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

        # ❌ async with self.db._lock: ← これは消す！

        today = datetime.now(JST).date()
        guild_id = str(interaction.guild.id)

        races = await self.db.get_today_race_schedules(today)
        if not races:
            return await interaction.followup.send(
                "❌ 本日のレースがありません",
                ephemeral=True
            )

            # =========================
            # ★ pending 2体以上のレースを探す
            # =========================
            target_race = None
            pending_count = 0

            for race in races:
                count = await self.db.conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM race_entries
                    WHERE race_date = $1
                      AND schedule_id = $2
                      AND status = 'pending'
                    """,
                    today,
                    race["id"]
                )

                if count >= 2:
                    target_race = race
                    pending_count = count
                    break

            if not target_race:
                return await interaction.followup.send(
                    "❌ 抽選可能なレースがありません（pending が2体以上なし）",
                    ephemeral=True
                )

            # =========================
            # ★ 本番と同じ処理を呼ぶ
            # =========================
            race_cog = self.bot.get_cog("OasistchiCog")
            if not race_cog:
                return await interaction.followup.send(
                    "❌ レース処理Cogが見つかりません",
                    ephemeral=True
                )

            await race_cog.run_race_lottery(target_race)
            await self.db.mark_race_lottery_done(target_race["id"])

            await interaction.followup.send(
                (
                    "✅ **デバッグ抽選完了！**\n"
                    f"🆔 race_id: `{target_race['id']}`\n"
                    f"🕘 第{target_race['race_no']}レース（{target_race['race_time']}）\n"
                    f"👥 pending: {pending_count}体"
                ),
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
















