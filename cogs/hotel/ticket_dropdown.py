import discord
from discord.ext import commands


# ======================================================
# 購入確認モーダル
# ======================================================
class TicketBuyConfirmModal(discord.ui.Modal):
    """確認モーダル（はい と入力したら購入）"""

    def __init__(self, amount, price, config):
        super().__init__(title="チケット購入確認")
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

        # 残高確認
        balance = (await interaction.client.db.get_user(user_id, guild_id))["balance"]
        if balance < self.price:
            return await interaction.response.send_message(
                f"❌ 残高不足です。\n必要：{self.price} / 所持：{balance}",
                ephemeral=True
            )

        # 残高減算
        await interaction.client.db.remove_balance(user_id, guild_id, self.price)

        # チケット追加
        new_tickets = await interaction.client.db.add_tickets(
            user_id, guild_id, self.amount
        )

        await interaction.response.send_message(
            f"🎫 **購入完了！**\n"
            f"{self.amount}枚追加 → 所持：{new_tickets}枚",
            ephemeral=True
        )


# ======================================================
# チケット購入ボタン（プルダウン選択後に表示）
# ======================================================
class TicketBuyExecuteButton(discord.ui.Button):
    def __init__(self, amount, price, config):
        super().__init__(label=f"購入を進める（{amount}枚）", style=discord.ButtonStyle.success)
        self.amount = amount
        self.price = price
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        modal = TicketBuyConfirmModal(self.amount, self.price, self.config)
        await interaction.response.send_modal(modal)


# ======================================================
# プルダウン
# ======================================================
class TicketBuyDropdown(discord.ui.Select):
    def __init__(self, config):
        self.config = config

        options = [
            discord.SelectOption(
                label=f"1枚 ({config['ticket_price_1']}pt)",
                value="1"
            ),
            discord.SelectOption(
                label=f"10枚 ({config['ticket_price_10']}pt)",
                value="10"
            ),
            discord.SelectOption(
                label=f"30枚 ({config['ticket_price_30']}pt)",
                value="30"
            ),
        ]

        super().__init__(
            placeholder="チケット購入を選択...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        amount = int(self.values[0])

        # 価格算出
        price_map = {
            1: self.config["ticket_price_1"],
            10: self.config["ticket_price_10"],
            30: self.config["ticket_price_30"],
        }
        price = price_map[amount]

        # ==============================
        # ボタン付きの確認パネルを表示
        # ==============================
        view = discord.ui.View(timeout=30)
        view.add_item(TicketBuyExecuteButton(amount, price, self.config))

        await interaction.response.send_message(
            f"🎫 **{amount}枚の購入を選択しました。**\n購入を進める場合は下のボタンを押してください。",
            view=view,
            ephemeral=True
        )


# ======================================================
# Cog 登録
# ======================================================
class TicketButtonsCog(commands.Cog):
    pass
