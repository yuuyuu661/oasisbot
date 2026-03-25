import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from PIL import Image
import io
import traceback

JST = timezone(timedelta(hours=9))



ROLE_IDS = [1445403813853925418,1445403608035364874]
GUILD_ID = 1420918259187712093

BG_PATHS = [
    "cogs/assets/stamp/bg1.png",
    "cogs/assets/stamp/bg2.png",
    "cogs/assets/stamp/bg3.png",
    "cogs/assets/stamp/bg4.png",
    "cogs/assets/stamp/bg5.png",
    "cogs/assets/stamp/bg6.png",
    "cogs/assets/stamp/bg7.png",
    "cogs/assets/stamp/bg8.png",
    "cogs/assets/stamp/bg9.png",
    "cogs/assets/stamp/bg10.png",
]
EMPTY_PATH = "cogs/assets/stamp/empty.png"
STAMP_PATH = "cogs/assets/stamp/stamp.png"


class StampCard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ StampCard cog init")

    # =========================
    # GLOBAL ERROR
    # =========================
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        print("🔥 APP COMMAND ERROR")
        traceback.print_exception(type(error), error, error.__traceback__)

    # =========================
    # DB取得
    # =========================
    async def get_data(self, guild_id, user_id):
        print(f"DB get_data start {guild_id} {user_id}")
        try:
            row = await self.bot.db._fetchrow(
                "SELECT * FROM stamp_cards WHERE guild_id=$1 AND user_id=$2",
                guild_id, user_id
            )
            print("DB get_data result:", row)
            return row
        except Exception as e:
            print("🔥 DB get_data error")
            traceback.print_exc()
            raise

    # =========================
    # スタンプ追加
    # =========================
    async def add_stamp(self, guild_id, user_id):

        today = datetime.now(JST).date()
        row = await self.get_data(guild_id, user_id)

        if row:
            stamps = row["stamps"] + 1
            page = row["page"]

            if stamps >= 10:
                page += 1
                stamps = 0

                await self.bot.db._execute(
                    "UPDATE stamp_cards SET stamps=$1, page=$2, last_stamp_date=$3 WHERE guild_id=$4 AND user_id=$5",
                    stamps, page, today, guild_id, user_id
                )
                return "complete"

            await self.bot.db._execute(
                "UPDATE stamp_cards SET stamps=$1, last_stamp_date=$2 WHERE guild_id=$3 AND user_id=$4",
                stamps, today, guild_id, user_id
            )

            return stamps

        else:
            await self.bot.db._execute(
                "INSERT INTO stamp_cards (guild_id, user_id, stamps, page, last_stamp_date) VALUES($1,$2,$3,$4,$5)",
                guild_id, user_id, 1, 1, today
            )
            return 1

    # =========================
    # 画像生成
    # =========================
    def generate_image(self, stamps, page):

        bg_path = BG_PATHS[(page-1) % len(BG_PATHS)]
        bg = Image.open(bg_path).convert("RGBA")

        empty = Image.open(EMPTY_PATH).convert("RGBA").resize((400, 400))
        stamp = Image.open(STAMP_PATH).convert("RGBA").resize((400, 400))

        start_x = 290
        start_y = 400
        gap_x = 440
        gap_y = 440

        index = 0

        for r in range(2):
            for c in range(5):
                x = start_x + c * gap_x
                y = start_y + r * gap_y

                if index < stamps:
                    bg.paste(stamp, (x, y), stamp)
                else:
                    bg.paste(empty, (x, y), empty)

                index += 1

        buf = io.BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)

        return buf



    # =========================
    # 確認
    # =========================
    @app_commands.command(name="スタンプカード確認")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def check(self, interaction: discord.Interaction, user: discord.Member = None):

        await interaction.response.defer()

        target = user or interaction.user

        # ⭐ 他人確認は管理ロール必須
        if user:
            if not any(r.id in ROLE_IDS for r in interaction.user.roles):
                return await interaction.followup.send("権限がありません", ephemeral=True)

        row = await self.get_data(interaction.guild_id, target.id)

        stamps = row["stamps"] if row else 0
        page = row["page"] if row else 1

        img = self.generate_image(stamps, page)

        await interaction.followup.send(
            content=f"{target.display_name} のスタンプカード（{page}枚目）",
            file=discord.File(img, "card.png")
        )

    # =========================
    # 押す
    # =========================
    @app_commands.command(name="祝福を捧げる")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def push(self, interaction: discord.Interaction, user: discord.Member):

        print("push command called")

        try:
            if not any(r.id in ROLE_IDS for r in interaction.user.roles):
                print("no permission")
                return await interaction.response.send_message("権限がありません", ephemeral=True)

            result = await self.add_stamp(interaction.guild_id, user.id)
            print("add_stamp result:", result)

            if result == "already":
                return await interaction.response.send_message("今日はもう押しています")

            if result == "complete":
                return await interaction.response.send_message(
                    f"{user.mention}\n今回でスタンプ10個目！教会の人に伝えて特典をもらおう！"
                )

            await interaction.response.send_message(
                f"{user.mention} にスタンプを押しました！（{result}/10）"
            )

            print("push success")

        except Exception:
            print("🔥 push error")
            traceback.print_exc()


    # =========================
    # ロール付与パネル
    # =========================
    @app_commands.command(name="ロール付与パネル")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(
        title="パネルタイトル",
        body="パネル本文",
        emoji1="絵文字1",
        role1="ロール1",
        emoji2="絵文字2",
        role2="ロール2",
        emoji3="絵文字3",
        role3="ロール3",
        emoji4="絵文字4",
        role4="ロール4",
        emoji5="絵文字5",
        role5="ロール5"
    )
    async def role_panel(
        self,
        interaction: discord.Interaction,
        title: str,
        body: str,
        emoji1: str,
        role1: discord.Role,
        emoji2: str = None,
        role2: discord.Role = None,
        emoji3: str = None,
        role3: discord.Role = None,
        emoji4: str = None,
        role4: discord.Role = None,
        emoji5: str = None,
        role5: discord.Role = None,
    ):

        if not any(r.id in ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        pairs = [(emoji1, role1)]

        optional = [
            (emoji2, role2),
            (emoji3, role3),
            (emoji4, role4),
            (emoji5, role5)
        ]

        for e, r in optional:
            if e and r:
                pairs.append((e, r))

        embed = discord.Embed(
            title=title,
            description=body,
            color=0x2b2d31
        )

        msg = await interaction.channel.send(embed=embed)

        # mapping保存
        if not hasattr(self.bot, "reaction_role_map"):
            self.bot.reaction_role_map = {}

        self.bot.reaction_role_map[msg.id] = {}

        for emoji, role in pairs:
            await msg.add_reaction(emoji)
            self.bot.reaction_role_map[msg.id][str(emoji)] = role.id

        await interaction.response.send_message("パネル生成しました", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        if payload.user_id == self.bot.user.id:
            return

        if not hasattr(self.bot, "reaction_role_map"):
            return

        if payload.message_id not in self.bot.reaction_role_map:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member is None:
            member = await guild.fetch_member(payload.user_id)

        emoji = str(payload.emoji)
        role_id = self.bot.reaction_role_map[payload.message_id].get(emoji)

        if role_id:
            role = guild.get_role(role_id)
            if role:
                await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):

        if not hasattr(self.bot, "reaction_role_map"):
            return

        if payload.message_id not in self.bot.reaction_role_map:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member is None:
            member = await guild.fetch_member(payload.user_id)

        emoji = str(payload.emoji)
        role_id = self.bot.reaction_role_map[payload.message_id].get(emoji)

        if role_id:
            role = guild.get_role(role_id)
            if role:
                await member.remove_roles(role)


async def setup(bot):
    await bot.add_cog(StampCard(bot))
