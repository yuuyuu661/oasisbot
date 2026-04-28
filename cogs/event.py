import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, date
import calendar
from io import BytesIO

TARGET_GUILD_ID = 1420918259187712093

JST = timedelta(hours=9)

EMOJI_GUILD_ID = 1420918259187712093

from PIL import Image

def load_img(path):
    return Image.open(path).convert("RGBA")

def now_jst():
    return datetime.utcnow() + JST


def build_calendar(year, month, events):
    cal = calendar.monthcalendar(year, month)

    text = f"📅 {year}年 {month}月\n\n"

    # 曜日
    week_header = ["日", "月", "火", "水", "木", "金", "土"]
    text += "".join(WEEK_EMOJI[d] for d in week_header) + "\n"

    for week in cal:
        # 日付
        line_days = ""
        for day in week:
            if day == 0:
                line_days += FREE
            else:
                line_days += DAY_EMOJI[day]

        text += line_days + "\n"

        # イベント
        for i, e in enumerate(events):
            line = ""
            has = False
            symbol = LINES[i % len(LINES)]

            for day in week:
                if day == 0:
                    line += FREE
                    continue

                current_date = date(year, month, day)

                if e["start_date"] <= current_date <= e["end_date"]:
                    line += symbol
                    has = True
                else:
                    line += FREE

            if has:
                text += line + "\n"


    return text



def build_calendar_image(year, month, events):
    cal = calendar.monthcalendar(year, month)

    CELL = 80  # ←ここでサイズ調整

    img = Image.new("RGBA", (CELL*7, CELL*8), (255,255,255,255))

    # 曜日
    week_names = ["nichi","getu","ka","sui","moku","kin","do"]
    for i, w in enumerate(week_names):
        icon = load_img(f"assets/week/{w}.png").resize((CELL, CELL))
        img.paste(icon, (i*CELL, 0), icon)

    # 日付
    for y, week in enumerate(cal):
        for x, day in enumerate(week):
            if day == 0:
                icon = load_img("assets/free.png")
            else:
                icon = load_img(f"assets/day/{day}.png")

            icon = icon.resize((CELL, CELL))
            img.paste(icon, (x*CELL, (y+1)*CELL), icon)

    return img


class EventCalendarCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def event_autocomplete(self, interaction: discord.Interaction, current: str):

        guild_id = str(interaction.guild.id)

        rows = await self.bot.db._fetch("""
            SELECT id, event_name, start_date, end_date
            FROM event_calendar
            WHERE guild_id = $1
              AND event_name ILIKE $2
            ORDER BY start_date
            LIMIT 25
        """, guild_id, f"%{current}%")

        return [
            app_commands.Choice(
                name=f"{r['event_name']} ({r['start_date']}~{r['end_date']})",
                value=str(r["id"])
            )
            for r in rows
        ]

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



    # =========================
    # 📅 カレンダー確認
    # =========================
    @app_commands.command(name="イベントカレンダー確認")
    async def show_calendar(self, interaction: discord.Interaction):

        if interaction.guild.id != TARGET_GUILD_ID:
            return await interaction.response.send_message(
                "❌ このサーバーでは使えません",
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


        # イベント一覧
        event_list = ""

        for i, e in enumerate(events_this + events_next):
            symbol = LINES[i % len(LINES)]
            event_list += f"{symbol} {e['start_date']}〜{e['end_date']}：{e['event_name']}\n"

        buf1 = BytesIO()
        img1 = build_calendar_image(now.year, now.month, events_this)
        img1.save(buf1, format="PNG")
        buf1.seek(0)
        file1 = discord.File(buf1, filename="calendar_this.png")

        # 来月画像
        buf2 = BytesIO()
        img2 = build_calendar_image(next_year, next_month, events_next)
        img2.save(buf2, format="PNG")
        buf2.seek(0)
        file2 = discord.File(buf2, filename="calendar_next.png")



        # Embed作成
        embed = discord.Embed(
            title="📅 イベントカレンダー",
            description="📌イベント一覧\n" + (event_list if event_list else "なし"),
            color=discord.Color.blue()
        )

        # 送信
        await interaction.followup.send(
            embed=embed,
            files=[file1, file2]
        )

    # =========================
    # 📌 登録
    # =========================
    @app_commands.command(name="イベントカレンダー登録")
    async def add_event(
        self,
        interaction: discord.Interaction,
        start: str,
        end: str,
        name: str
    ):

        if interaction.guild.id != TARGET_GUILD_ID:
            return await interaction.response.send_message(
                "❌ このコマンドはこのサーバーでは使えません。",
                ephemeral=True
            )

        try:
            start_date = datetime.strptime(start.strip(), "%Y/%m/%d").date()
            end_date = datetime.strptime(end.strip(), "%Y/%m/%d").date()
        except:
            return await interaction.response.send_message(
                "❌ 形式は 2026/04/27",
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


    @app_commands.command(name="イベント予定削除")
    @app_commands.describe(event="削除するイベントを選択")
    @app_commands.autocomplete(event=event_autocomplete)
    async def delete_event(self, interaction: discord.Interaction, event: str):

        if interaction.guild.id != TARGET_GUILD_ID:
            return await interaction.response.send_message(
               "❌ このコマンドはこのサーバーでは使えません。",
                ephemeral=True
            )

        event_id = int(event)

        # 一応取得（表示用）
        row = await self.bot.db._fetchrow("""
            SELECT event_name, start_date, end_date
            FROM event_calendar
            WHERE id = $1
        """, event_id)

        if not row:
            return await interaction.response.send_message(
                "❌ イベントが見つかりません",
                ephemeral=True
            )

        await self.bot.db.delete_event_by_id(event_id)

        await interaction.response.send_message(
           f"🗑️ 削除しました\n📌 {row['start_date']}〜{row['end_date']}：{row['event_name']}"
        )






async def setup(bot):
    cog = EventCalendarCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
