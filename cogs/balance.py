# cogs/balance.py
import discord
from discord.ext import commands
from discord import app_commands

from logger import log_pay


class BalanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------
    # /bal
    # --------------------------
    @app_commands.command(name="bal", description="自分または指定ユーザーの残高を表示します")
    @app_commands.describe(user="残高を確認したいユーザー（省略可）")
    async def bal(self, interaction: discord.Interaction, user: discord.User = None):

        if user is None:
            user = interaction.user
            target_is_self = True
        else:
            target_is_self = False

        # 管理者チェック（他人を見る時）
        if not target_is_self:
            settings = await self.bot.db.get_settings()
            admin_roles = settings["admin_roles"] or []

            if not any(str(role.id) in admin_roles for role in interaction.user.roles):
                return await interaction.response.send_message(
                    "❌ 他人の残高を見るには管理者ロールが必要です。",
                    ephemeral=True
                )

        guild_id = str(interaction.guild.id)
        data = await self.bot.db.get_user(str(user.id), guild_id)
        unit = (await self.bot.db.get_settings())["currency_unit"]

        await interaction.response.send_message(
            f"💰 **{user.display_name}** の残高： **{data['balance']} {unit}**"
        )

    # --------------------------
    # /pay
    # --------------------------
    @app_commands.command(name="pay", description="指定ユーザーに通貨を送金します")
    @app_commands.describe(user="相手ユーザー", amount="送金額（1以上）")
    async def pay(self, interaction: discord.Interaction, user: discord.User, amount: int):

        if amount < 1:
            return await interaction.response.send_message("❌ 1以上の金額を指定してください。", ephemeral=True)

        sender_id = str(interaction.user.id)
        receiver_id = str(user.id)

        if sender_id == receiver_id:
            return await interaction.response.send_message("❌ 自分には送金できません。", ephemeral=True)

        sender = await self.bot.db.get_user(sender_id)
        if sender["balance"] < amount:
            return await interaction.response.send_message("❌ 残高不足です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.bot.db.remove_balance(sender_id, guild_id, amount)
        await self.bot.db.add_balance(receiver_id, guild_id, amount)

        settings = await self.bot.db.get_settings()

        await log_pay(
            bot=self.bot,
            settings=settings,
            from_id=sender_id,
            to_id=receiver_id,
            amount=amount
        )

        await interaction.response.send_message(
            f"💸 <@{receiver_id}> に **{amount}{settings['currency_unit']}** を送金しました！"
        )


async def setup(bot):
    cog = BalanceCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))



