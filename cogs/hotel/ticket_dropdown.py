import discord
from discord.ext import commands


# ======================================================
# 購入確認モーダル
# ======================================================
class TicketBuyConfirmModal(discord.ui.Modal):
    """購入確認モーダル"""

    def __init__(self, label, amount, price, config):
        super().__init__(title=f"{label}を購入しますか？")
        self.amount = amount
        self.price = price
        self.config = config

        self.confirm = discord.ui.TextInput(
            label="購入を確定するには「はい」と入力してください",
            placeholder="はい",
            required=True
        )
        self.add_item(self.confirm)

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value != "はい":
            return await interaction.response.send_message(
                "❌ キャンセルされました。",
                ephemeral=True
            )

        user = interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(user.id)

        # 残高チェック
        balance = (await interaction.client.db.get_user(user_id, guild_id))["balance"]
        if balance < self.price:
            return await interaction.response.send_message(
                f"❌ 残高不足です。\n必要：{self.price} / 所持：{balance}",
                ephemeral=True
            )

        # 通貨減算
        await interaction.client.db.remove_balance(user_id, guild_id, self.price)

        # チケット付与
        new_tickets = await interaction.client.db.add_tickets(
            user_id, guild_id, self.amount
        )

        await interaction.response.send_message(
            f"🎫 **購入完了！**\n"
            f"{self.amount}枚追加 → 所持：{new_tickets}枚",
            ephemeral=True
        )

        # -------------------------------------------------
        # ログを送信（embed）
        # -------------------------------------------------
        log_channel = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_channel:
            embed = discord.Embed(
                title="🎫 チケット購入ログ",
                color=0xF4D03F
            )
            embed.add_field(name="ユーザー", value=user.mention, inline=False)
            embed.add_field(name="購入枚数", value=f"{self.amount}枚", inline=True)
            embed.add_field(name="消費通貨", value=f"{self.price}", inline=True)
            embed.add_field(name="残高（購入後）", value=f"{balance - self.price}", inline=True)
            embed.add_field(name="現在のチケット数", value=f"{new_tickets}枚", inline=False)

            await log_channel.send(embed=embed)


# ======================================================
# チケット購入ボタン：1枚
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
# チケット購入ボタン：10枚
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
# チケット購入ボタン：30枚
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
# Cog（登録用）
# ======================================================
class TicketButtonsCog(commands.Cog):
    """ホテルのチケット購入ボタン関連"""

    def __init__(self, bot):
        self.bot = bot

# ======================================================
# setup（Bot がこの Cog を読み込むために必要）
# ======================================================

async def setup(bot):
    await bot.add_cog(TicketButtonsCog(bot))
