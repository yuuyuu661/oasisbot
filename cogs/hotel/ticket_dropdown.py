# cogs/hotel/ticket_buttons.py

import discord
from discord.ext import commands
from datetime import datetime


# ======================================================
# チケット購入用 モーダル（確認）
# ======================================================
class TicketBuyConfirmModal(discord.ui.Modal):
    """購入確認モーダル"""

    def __init__(self, label, amount, price, config):
        super().__init__(title=f"{label}を購入しますか？")
        self.amount = amount
        self.price = price
        self.config = config

        self.confirm = discord.ui.TextInput(
            label=f"購入を実行するには「はい」と入力してください",
            placeholder="はい",
            required=True
        )
        self.add_item(self.confirm)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(user.id)

        # 残高チェック
        balance = (await interaction.client.db.get_user(user_id, guild_id))["balance"]
        if balance < self.price:
            return await interaction.response.send_message(
                f"❌ 残高不足です。必要：{self.price} / 所持：{balance}",
                ephemeral=True
            )

        # 残高減算
        await interaction.client.db.remove_balance(user_id, guild_id, self.price)

        # チケット付与
        new_tickets = await interaction.client.db.add_tickets(
            user_id, guild_id, self.amount
        )

        await interaction.response.send_message(
            f"🎫 購入完了！{self.amount}枚追加（現在：{new_tickets}枚）",
            ephemeral=True
        )

        # -------------------------------------------------
        # 購入ログを送信（embed）
        # -------------------------------------------------
        log_channel = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_channel:
            embed = discord.Embed(
                title="🎫 チケット購入",
                color=0xF4D03F
            )
            embed.add_field(name="ユーザー", value=user.mention, inline=False)
            embed.add_field(name="購入内容", value=f"{self.amount}枚", inline=True)
            embed.add_field(name="消費通貨", value=f"{self.price}", inline=True)
            embed.add_field(name="残高", value=f"{balance - self.price}", inline=True)
            embed.add_field(name="所持チケット", value=f"{new_tickets}枚")

            await log_channel.send(embed=embed)


# ======================================================
# チケット購入 1枚
# ======================================================
class TicketBuyButton1(discord.ui.Button):
    def __init__(self, config):
        super().__init__(
            label="🎫 1枚購入",
            style=discord.ButtonStyle.blurple
        )
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        price = self.config["ticket_price_1"]
        modal = TicketBuyConfirmModal("1枚", 1, price, self.config)
        await interaction.response.send_modal(modal)


# ======================================================
# チケット購入 10枚
# ======================================================
class TicketBuyButton10(discord.ui.Button):
    def __init__(self, config):
        super().__init__(
            label="🎫 10枚購入",
            style=discord.ButtonStyle.blurple
        )
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        price = self.config["ticket_price_10"]
        modal = TicketBuyConfirmModal("10枚", 10, price, self.config)
        await interaction.response.send_modal(modal)


# ======================================================
# チケット購入 30枚
# ======================================================
class TicketBuyButton30(discord.ui.Button):
    def __init__(self, config):
        super().__init__(
            label="🎫 30枚購入",
            style=discord.ButtonStyle.blurple
        )
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        price = self.config["ticket_price_30"]
        modal = TicketBuyConfirmModal("30枚", 30, price, self.config)
        await interaction.response.send_modal(modal)


# ======================================================
# Cog（ホテル操作パネルに組み込む用）
# ======================================================
class TicketButtonsCog(commands.Cog):
    """ホテルのチケット購入ボタン関連"""

    def __init__(self, bot):
        self.bot = bot

