import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import calendar

TARGET_GUILD_ID = 1310885590094450739

JST = timedelta(hours=9)

def now_jst():
    return datetime.utcnow() + JST


def build_calendar(year, month, events):
    cal = calendar.monthcalendar(year, month)
    text = f"📅 {year}年 {month}月\n\n"

    for week in cal:
        for day in week:
            if day == 0:
                text += "   "
            else:
                mark = ""
                for e in events:
                    if e["start_date"].day <= day <= e["end_date"].day:
                        mark = "📌"
                text += f"{day:2}{mark} "
        text += "\n"

    return text


class EventCalendarCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # ✅ テーブル作成（起動時1回）
        await self.bot.db._execute("""
        CREATE TABLE IF NOT EXISTS event_calendar (
            id SERIAL PRIMARY KEY,
            guild_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        if not self.event_notify.is_running():
            self.event_notify.start()

    def cog_unload(self):
        self.event_notify.cancel()

    # =========================
    # 📅 カレンダー確認
    # =========================
    @app_commands.command(name="イベントカレンダー確認")
    async def show_calendar(self, interaction: discord.Interaction):

        # ✅ ギルド制限
        if interaction.guild.id != TARGET_GUILD_ID:
            return await interaction.response.send_message(
                "❌ このコマンドはこのサーバーでは使えません。",
                ephemeral=True
            )

        await interaction.response.defer()

        now = now_jst()
        guild_id = str(interaction.guild.id)

        # 今月
        start_this = datetime(now.year, now.month, 1).date()
        end_this = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1]).date()

        events_this = await self.bot.db.get_events_in_range(
            guild_id, start_this, end_this
        )

        cal_this = build_calendar(now.year, now.month, events_this)

        # 来月
        next_month = now.month + 1
        next_year = now.year
        if next_month == 13:
            next_month = 1
            next_year += 1

        start_next = datetime(next_year, next_month, 1).date()
        end_next = datetime(next_year, next_month, calendar.monthrange(next_year, next_month)[1]).date()

        events_next = await self.bot.db.get_events_in_range(
            guild_id, start_next, end_next
        )

        cal_next = build_calendar(next_year, next_month, events_next)

        event_list = ""
        for e in events_this + events_next:
            event_list += f"📌 {e['start_date']}〜{e['end_date']}：{e['event_name']}\n"

        embed = discord.Embed(
            title="📅 イベントカレンダー",
            description="```" + cal_this + "\n" + cal_next + "```",
            color=discord.Color.blue()
        )

        if event_list:
            embed.add_field(name="📌 イベント一覧", value=event_list, inline=False)

        await interaction.followup.send(embed=embed)

    # =========================
    # 📌 登録
    # =========================
    @app_commands.command(name="イベントカレンダー登録")
    async def add_event(self, interaction: discord.Interaction, period: str, name: str):

        if interaction.guild.id != TARGET_GUILD_ID:
            return await interaction.response.send_message(
                "❌ このコマンドはこのサーバーでは使えません。",
                ephemeral=True
            )

        try:
            start_str, end_str = period.split("~")
            start_date = datetime.strptime(start_str.strip(), "%Y/%m/%d").date()
            end_date = datetime.strptime(end_str.strip(), "%Y/%m/%d").date()
        except:
            return await interaction.response.send_message(
                "❌ 形式は 2026/04/27~2026/04/30",
                ephemeral=True
            )

        await self.bot.db.add_event(
            str(interaction.guild.id),
            name,
            start_date,
            end_date
        )

        await interaction.response.send_message(
            f"✅ 登録\n📌 {start_date}〜{end_date}：{name}"
        )

    # =========================
    # 🔔 通知（このギルドだけ）
    # =========================
    @tasks.loop(minutes=1)
    async def event_notify(self):

        now = now_jst()
        today = now.date()

        guild = self.bot.get_guild(TARGET_GUILD_ID)
        if not guild:
            return

        events = await self.bot.db.get_today_events(str(guild.id), today)

        if not events:
            return

        channel = guild.system_channel
        if not channel:
            return

        for e in events:
            await channel.send(
                f"📅 **本日のイベント！**\n📌 {e['event_name']}"
            )

    @event_notify.before_loop
    async def before_notify(self):
        await self.bot.wait_until_ready()




async def setup(bot):
    cog = EventCalendarCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
