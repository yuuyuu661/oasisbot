import discord


class TicketBuyDropdown(discord.ui.Select):
    def __init__(self, config):
        self.config = config

        options = [
            discord.SelectOption(
                label=f"1枚購入 ({config['ticket_price_1']}pt)",
                value="1"
            ),
            discord.SelectOption(
                label=f"10枚購入 ({config['ticket_price_10']}pt)",
                value="10"
            ),
            discord.SelectOption(
                label=f"30枚購入 ({config['ticket_price_30']}pt)",
                value="30"
            ),
        ]

        super().__init__(
            placeholder="チケット購入...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        amount = int(self.values[0])
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # 価格
        price_map = {
            1: self.config["ticket_price_1"],
            10: self.config["ticket_price_10"],
            30: self.config["ticket_price_30"],
        }
        price = price_map[amount]

        # 残高確認
        balance = (await interaction.client.db.get_user(user_id, guild_id))["balance"]
        if balance < price:
            return await interaction.response.send_message(
                "❌ 残高が不足しています。",
                ephemeral=True
            )

        # pt消費
        await interaction.client.db.remove_balance(user_id, guild_id, price)

        # チケット追加
        await interaction.client.db.add_tickets(user_id, guild_id, amount)

        await interaction.response.send_message(
            f"🎫 チケット **{amount}枚** を購入しました！（{price}pt消費）",
            ephemeral=True
        )
