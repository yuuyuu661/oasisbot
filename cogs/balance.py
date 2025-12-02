# cogs/balance.py
import discord
from discord.ext import commands
from discord import app_commands

class BalanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------
    # /bal
    # --------------------
    @app_commands.command(name="bal", description="自分または指定ユーザーの残高を表示します")
    async def bal(self, interaction: discord.Interaction, user: discord.User = None):
        guild_id = str(interaction.guild.id)
        target = user or interaction.user

        data = await self.bot.db.get_user(str(target.id), guild_id)
        settings = await self.bot.db.get_settings(guild_id)
        unit = settings["currency_unit"]

        embed = discord.Embed(
            title=f"💰 残高 - {target.display_name}",
            description=f"{data['balance']} {unit}",
            color=0x00ff99
        )
        await interaction.response.send_message(embed=embed)

    # --------------------
    # /pay
    # --------------------
    @app_commands.command(name="pay", description="指定ユーザーに通貨を送金します")
    async def pay(self, interaction: discord.Interaction, user: discord.User, amount: int):
        guild_id = str(interaction.guild.id)
        settings = await self.bot.db.get_settings(guild_id)
        unit = settings["currency_unit"]

        if amount <= 0:
            return await interaction.response.send_message("送金額は1以上にしてください。", ephemeral=True)

        sender_id = str(interaction.user.id)
        receiver_id = str(user.id)

        sender = await self.bot.db.get_user(sender_id, guild_id)

        if sender["balance"] < amount:
            return await interaction.response.send_message("残高が不足しています。", ephemeral=True)

        await self.bot.db.remove_balance(sender_id, guild_id, amount)
        await self.bot.db.add_balance(receiver_id, guild_id, amount)

        # ログ
        if settings["log_pay"]:
            log_ch = interaction.guild.get_channel(int(settings["log_pay"]))
            if log_ch:
                await log_ch.send(f"💸 **{interaction.user.mention} → {user.mention} : {amount}{unit} 送金**")

        await interaction.response.send_message(
            f"💸 {user.mention} に **{amount}{unit}** を送金しました！"
        )

    # setup
async def setup(bot):
    await bot.add_cog(BalanceCog(bot))
    for cmd in bot.tree.get_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
