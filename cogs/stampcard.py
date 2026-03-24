import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from PIL import Image
import io

JST = timezone(timedelta(hours=9))

ROLE_ID = 716667546241335328
GUILD_ID = 1420918259187712093

BG_PATH = "cogs/assets/stamp/bg.png"
EMPTY_PATH = "cogs/assets/stamp/empty.png"
STAMP_PATH = "cogs/assets/stamp/stamp.png"


class StampCard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_data(self, guild_id, user_id):
        return await self.bot.db.fetchrow(
            "SELECT * FROM stamp_cards WHERE guild_id=$1 AND user_id=$2",
            guild_id, user_id
        )

    async def add_stamp(self, guild_id, user_id):
        today = datetime.now(JST).date()

        row = await self.get_data(guild_id, user_id)

        if row:
            if row["last_stamp_date"] == today:
                return "already"

            stamps = row["stamps"] + 1

            # ⭐ 10達成
            if stamps >= 10:
                await self.bot.db.execute(
                    "UPDATE stamp_cards SET stamps=0, last_stamp_date=$1 WHERE guild_id=$2 AND user_id=$3",
                    today, guild_id, user_id
                )
                return "complete"

            await self.bot.db.execute(
                "UPDATE stamp_cards SET stamps=$1, last_stamp_date=$2 WHERE guild_id=$3 AND user_id=$4",
                stamps, today, guild_id, user_id
            )

        else:
            stamps = 1
            await self.bot.db.execute(
                "INSERT INTO stamp_cards VALUES($1,$2,$3,$4)",
                guild_id, user_id, stamps, today
            )

        return stamps

    def generate_image(self, stamps):
        bg = Image.open(BG_PATH).convert("RGBA")
        empty = Image.open(EMPTY_PATH).convert("RGBA")
        stamp = Image.open(STAMP_PATH).convert("RGBA")

        start_x = 120
        start_y = 200
        gap_x = 200

        index = 0

        for row in range(2):
            for col in range(5):

                x = start_x + col * gap_x
                y = start_y + row * 180

                if index < stamps:
                    bg.paste(stamp, (x, y), stamp)
                else:
                    bg.paste(empty, (x, y), empty)

                index += 1

        buf = io.BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)

        return buf

    @app_commands.command(name="スタンプカード確認")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def check(self, interaction: discord.Interaction):

        await interaction.response.defer()

        row = await self.get_data(interaction.guild_id, interaction.user.id)
        stamps = row["stamps"] if row else 0

        img = self.generate_image(stamps)

        await interaction.followup.send(
            file=discord.File(img, "card.png")
        )

    @app_commands.command(name="スタンプカードを押す")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def push(self, interaction: discord.Interaction, user: discord.Member):

        if ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        result = await self.add_stamp(interaction.guild_id, user.id)

        if result == "already":
            return await interaction.response.send_message("今日はもう押しています")

        if result == "complete":
            return await interaction.response.send_message(
                f"{user.mention}\n今回でスタンプ10個目！協会の人に伝えて特典をもらおう！"
            )

        await interaction.response.send_message(
            f"{user.mention} にスタンプを押しました！（{result}/10）"
        )


async def setup(bot):
    await bot.add_cog(StampCard(bot))
