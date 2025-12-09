import discord
from discord.ext import commands


# ======================================================
# 購入確定ボタン（edit_message で安定動作）
# ======================================================
class TicketConfirmButton(discord.ui.Button):
    def __init__(self, amount, price, config):
        super().__init__(label="購入を確定する", style=discord.ButtonStyle.green)
        self.amount = amount
        self.price = price
        self.config = config

    async def callback(self, interaction: discord.Interaction):

        user = interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(user.id)

        # 残高確認
        balance = (await interaction.client.db.get_user(user_id, guild_id))["balance"]
        if balance < self.price:
            return await interaction.response.edit_message(
                content=f"❌ 残高不足です。\n必要：{self.price}pt / 所持：{balance}pt",
                view=None
            )

        # 残高減算
        await interaction.client.db.remove_balance(user_id, guild_id, self.price)

        # チケット付与
        new_tickets = await interaction.client.db.add_tickets(
            user_id, guild_id, self.amount
        )

        # メッセージ更新（成功）
        await interaction.response.edit_message(
            content=f"🎫 **購入完了！**\n{self.amount}枚 → 所持：{new_tickets}枚",
            view=None
        )

        # --- ログ送信 ---
        log_channel = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_channel:
            embed = discord.Embed(
                title="🎫 チケット購入ログ",
                color=0xF4D03F
            )
            embed.add_field(name="ユーザー", value=user.mention)
            embed.add_field(name="購入枚数", value=f"{self.amount}枚", inline=True)
            embed.add_field(name="金額", value=f"{self.price}pt", inline=True)
            embed.add_field(name="残高（購入後）", value=f"{balance - self.price}pt", inline=True)
            embed.add_field(name="所持チケット", value=f"{new_tickets}枚", inline=False)
            await log_channel.send(embed=embed)


# ======================================================
# 購入ボタン（プルダウン選択後）
# ======================================================
class TicketBuyExecuteButton(discord.ui.Button):
    def __init__(self, selector, config):
        super().__init__(label="🎫 購入する", style=discord.ButtonStyle.success)
        self.selector = selector
        self.config = config

    async def callback(self, interaction: discord.Interaction):

        # プルダウンで未選択
        if not self.selector.values:
            return await interaction.response.send_message(
                "⚠ チケット枚数を選択してください。",
                ephemeral=True
            )

        amount = int(self.selector.values[0])

        price = {
            1: self.config["ticket_price_1"],
            10: self.config["ticket_price_10"],
            30: self.config["ticket_price_30"],
        }[amount]

        # 購入確認ボタン付き UI を出す（← ここ重要：edit_message を使う）
        confirm_view = discord.ui.View(timeout=20)
        confirm_view.add_item(TicketConfirmButton(amount, price, self.config))

        await interaction.response.send_message(
            content=f"🎫 **{amount}枚を購入しますか？**\n金額：{price}pt",
            view=confirm_view,
            ephemeral=True
        )


# ======================================================
# プルダウン
# ======================================================
class TicketBuyDropdown(discord.ui.Select):
    def __init__(self, config):
        self.config = config

        options = [
            discord.SelectOption(label=f"1枚（{config['ticket_price_1']}pt）", value="1"),
            discord.SelectOption(label=f"10枚（{config['ticket_price_10']}pt）", value="10"),
            discord.SelectOption(label=f"30枚（{config['ticket_price_30']}pt）", value="30"),
        ]

        super().__init__(
            placeholder="チケット枚数を選択…",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # 選択しただけでボタンが動けばいいので応答は軽くてOK
        await interaction.response.defer()  # ← これだけでエラーが消える



# ======================================================
# View（パネル構成）
# ======================================================
class TicketDropdownView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)
        selector = TicketBuyDropdown(config)
        self.add_item(selector)
        self.add_item(TicketBuyExecuteButton(selector, config))


# Cog
class TicketButtonsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

