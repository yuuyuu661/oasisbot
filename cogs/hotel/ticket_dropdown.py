import discord
from discord.ext import commands


# ======================================================
# 購入実行ボタン（プルダウン選択後に押す）
# ======================================================
class TicketBuyExecuteButton(discord.ui.Button):
    def __init__(self, selector, config):
        super().__init__(label="🎫 購入する", style=discord.ButtonStyle.success)
        self.selector = selector   # ← プルダウンの値を参照
        self.config = config

    async def callback(self, interaction: discord.Interaction):

        # プルダウンで選んだ数を取得
        if not self.selector.values:
            return await interaction.response.send_message(
                "⚠ チケット枚数を選択してください。",
                ephemeral=True
            )

        amount = int(self.selector.values[0])
        price_map = {
            1: self.config["ticket_price_1"],
            10: self.config["ticket_price_10"],
            30: self.config["ticket_price_30"]
        }
        price = price_map[amount]

        # --- 確認ボタンの表示 ---
        view = discord.ui.View(timeout=15)
        view.add_item(TicketConfirmButton(amount, price, self.config))

        await interaction.response.send_message(
            f"🎫 **{amount}枚を購入しますか？**\n\n金額：{price}pt",
            view=view,
            ephemeral=True
        )


# ======================================================
# 購入実行（ボタン押したら即購入）
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

        # 残高チェック
        balance = (await interaction.client.db.get_user(user_id, guild_id))["balance"]
        if balance < self.price:
            return await interaction.response.send_message(
                f"❌ 残高不足です。\n必要：{self.price}pt / 所持：{balance}pt",
                ephemeral=True
            )

        # 減算
        await interaction.client.db.remove_balance(user_id, guild_id, self.price)

        # チケット加算
        new_tickets = await interaction.client.db.add_tickets(user_id, guild_id, self.amount)

        await interaction.response.send_message(
            f"🎫 **購入完了！**\n{self.amount}枚 → 所持：{new_tickets}枚",
            ephemeral=True
        )

        # --- ログ出力（embed） ---
        log_channel = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_channel:
            embed = discord.Embed(
                title="🎫 チケット購入ログ",
                color=0xF4D03F
            )
            embed.add_field(name="ユーザー", value=user.mention, inline=False)
            embed.add_field(name="購入枚数", value=f"{self.amount}枚", inline=True)
            embed.add_field(name="金額", value=f"{self.price}pt", inline=True)
            embed.add_field(name="残高（購入後）", value=f"{balance - self.price}pt", inline=True)
            embed.add_field(name="所持チケット", value=f"{new_tickets}枚", inline=False)
            await log_channel.send(embed=embed)


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


# ======================================================
# View（チケット購入UI）
# ======================================================
class TicketDropdownView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)
        selector = TicketBuyDropdown(config)
        self.add_item(selector)
        self.add_item(TicketBuyExecuteButton(selector, config))



# Cog（登録用）
class TicketButtonsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
