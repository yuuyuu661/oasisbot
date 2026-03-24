import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from PIL import Image
import io
import traceback

JST = timezone(timedelta(hours=9))

ROLE_ID = 1445403813853925418
GUILD_ID = 1420918259187712093

BG_PATH = "cogs/assets/stamp/bg.png"
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
        print("add_stamp start")

        try:
            today = datetime.now(JST).date()
            print("today:", today)

            row = await self.get_data(guild_id, user_id)

            if row:
                print("row exists")




                stamps = row["stamps"] + 1
                print("new stamps:", stamps)

                if stamps >= 10:
                    print("stamp complete")
                    await self.bot.db._execute(
                        "UPDATE stamp_cards SET stamps=0, last_stamp_date=$1 WHERE guild_id=$2 AND user_id=$3",
                        today, guild_id, user_id
                    )
                    return "complete"

                await self.bot.db._execute(
                    "UPDATE stamp_cards SET stamps=$1, last_stamp_date=$2 WHERE guild_id=$3 AND user_id=$4",
                    stamps, today, guild_id, user_id
                )

            else:
                print("row not exists -> insert")
                stamps = 1
                await self.bot.db._execute(
                    "INSERT INTO stamp_cards VALUES($1,$2,$3,$4)",
                    guild_id, user_id, stamps, today
                )

            return stamps

        except Exception as e:
            print("🔥 add_stamp error")
            traceback.print_exc()
            raise

    # =========================
    # 画像生成
    # =========================
    def generate_image(self, stamps):
        print("generate_image start", stamps)
        try:
            bg = Image.open(BG_PATH).convert("RGBA")
            empty = Image.open(EMPTY_PATH).convert("RGBA")
            stamp = Image.open(STAMP_PATH).convert("RGBA")

            # ⭐ サイズ統一（ここ超重要）
            empty = empty.resize((400, 400))
            stamp = stamp.resize((400, 400))

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

            print("generate_image success")
            return buf

        except Exception as e:
            print("🔥 generate_image error")
            traceback.print_exc()
            raise

    # =========================
    # 確認
    # =========================
    @app_commands.command(name="スタンプカード確認")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def check(self, interaction: discord.Interaction):

        print("check command called")

        try:
            await interaction.response.defer()
            print("defer success")

            row = await self.get_data(interaction.guild_id, interaction.user.id)
            stamps = row["stamps"] if row else 0
            print("stamps:", stamps)

            img = self.generate_image(stamps)

            await interaction.followup.send(
                file=discord.File(img, "card.png")
            )

            print("check success")

        except Exception:
            print("🔥 check error")
            traceback.print_exc()

    # =========================
    # 押す
    # =========================
    @app_commands.command(name="祝福を捧げる")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def push(self, interaction: discord.Interaction, user: discord.Member):

        print("push command called")

        try:
            if ROLE_ID not in [r.id for r in interaction.user.roles]:
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


async def setup(bot):
    await bot.add_cog(StampCard(bot))
