import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, date
import calendar

TARGET_GUILD_ID = 1420918259187712093

JST = timedelta(hours=9)

EMOJI_GUILD_ID = 1420918259187712093

WEEK_EMOJI = {
    "日": "<:nichi:1498244995486973953>",
    "月": "<:getu:1498244813521162340>",
    "火": "<:ka:1498244842822697011>",
    "水": "<:sui:1498244868630384640>",
    "木": "<:moku:1498244884803620955>",
    "金": "<:kin:1498244926192746516>",
    "土": "<:do:1498244971445227693>",
}

DAY_EMOJI = {
    1: "<:1_:1498506972763521084>",
    2: "<:2_:1498506994603135016>",
    3: "<:3_:1498507096327721103>",
    4: "<:4_:1498507114862084337>",
    5: "<:5_:1498507133040197692>",
    6: "<:6_:1498507150098436267>",
    7: "<:7_:1498507168389791915>",
    8: "<:8_:1498507189294202890>",
    9: "<:9_:1498507207346622555>",
    10: "<:10_:1498507233778995302>",
    11: "<:11_:1498507253278310572>",
    12: "<:12_:1498507274128195634>",
    13: "<:13_:1498507302297141268>",
    14: "<:14_:1498507322488782978>",
    15: "<:15_:1498507343124758598>",
    16: "<:16_:1498507370903638077>",
    17: "<:17_:1498507390289580033>",
    18: "<:18_:1498507410711642142>",
    19: "<:19_:1498507434074046534>",
    20: "<:20_:1498507452948414596>",
    21: "<:21_:1498507481469419530>",
    22: "<:22_:1498507502483144794>",
    23: "<:23_:1498507520057151561>",
    24: "<:24_:1498507540865093652>",
    25: "<:25_:1498507561706455181>",
    26: "<:26_:1498507584175607912>",
    27: "<:27_:1498507604979220631>",
    28: "<:28_:1498507623434027038>",
    29: "<:29_:1498507644196093972>",
    30: "<:30_:1498507665532522536>",
    31: "<:31_:1498507687279853608>"
}

FREE = "<:free:1498494655279403008>"

LINES = [
    "<:line1:1498506208439435386>",
    "<:line2:1498506232909008928>",
    "<:line3:1498506263305261076>",
    "<:line4:1498506285333610557>",
    "<:line5:1498506307085275146>",
    "<:line6:1498506329839370381>",
    "<:line7:1498506349426774126>",
    "<:line8:1498506369454571632>",
    "<:line9:1498506389557874738>",
    "<:line10:1498506409057189938>",
]

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

        text += "\n"

    return text




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

        # イベント一覧
        event_list = ""
        symbols = ["■", "□", "◆", "◇", "●", "○"]

        for i, e in enumerate(events_this + events_next):
            symbol = symbols[i % len(symbols)]
            event_list += f"{symbol} {e['start_date']}〜{e['end_date']}：{e['event_name']}\n"

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
