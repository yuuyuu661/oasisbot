import discord
from discord.ext import commands
from discord import app_commands


PRESET_COLORS = {
    "🔴 赤": "#FF3B30",
    "🟠 オレンジ": "#FF9500",
    "🟡 黄": "#FFCC00",
    "🟢 緑": "#34C759",
    "🔵 青": "#007AFF",
    "🟣 紫": "#AF52DE",
    "⚫ 黒": "#1C1C1E",
    "⚪ 白": "#F2F2F7",
    "🟤 茶": "#8E8E93",
    "🩷 ピンク": "#FF2D55",
    "🟦 水色": "#5AC8FA",
    "🟨 ライム": "#A3E635",
}


# --------------------------------------------------
# 色選択 View
# --------------------------------------------------
class ColorSelectView(discord.ui.View):
    def __init__(self, bot, user, guild_id, price, description):
        super().__init__(timeout=180)
        self.bot = bot
        self.user = user
        self.guild_id = guild_id
        self.price = price
        self.description = description

        self.color1 = None
        self.color2 = None

        self.add_item(ColorSelect(self, 1))
        self.add_item(ColorSelect(self, 2))
        self.add_item(ConfirmButton(self))


class ColorSelect(discord.ui.Select):
    def __init__(self, view, index: int):
        options = [
            discord.SelectOption(
                label=name,
                value=code
            )
            for name, code in PRESET_COLORS.items()
        ]

        super().__init__(
            placeholder=f"色 {index} を選択してください",
            options=options,
            min_values=1,
            max_values=1
        )

        self.view_ref = view
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.user.id:
            await interaction.response.send_message(
                "この操作は購入者本人のみ行えます。",
                ephemeral=True
            )
            return

        if self.index == 1:
            self.view_ref.color1 = self.values[0]
        else:
            self.view_ref.color2 = self.values[0]

        await interaction.response.send_message(
            f"色 {self.index} を設定しました。",
            ephemeral=True
        )


class ConfirmButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(
            label="購入する",
            style=discord.ButtonStyle.success
        )
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.user.id:
            await interaction.response.send_message(
                "この操作は購入者本人のみ行えます。",
                ephemeral=True
            )
            return

        if not self.view_ref.color1 or not self.view_ref.color2:
            await interaction.response.send_message(
                "色を2つ選択してください。",
                ephemeral=True
            )
            return

        db = self.view_ref.bot.db
        user_id = str(self.view_ref.user.id)
        guild_id = str(self.view_ref.guild_id)

        user = await db.get_user(user_id, guild_id)
        if user["balance"] < self.view_ref.price:
            await interaction.response.send_message(
                "残高が足りません。",
                ephemeral=True
            )
            return

        # 支払い
        await db.remove_balance(
            user_id,
            guild_id,
            self.view_ref.price
        )

        # 色保存
        await db.set_gradient_color(
            user_id,
            guild_id,
            self.view_ref.color1,
            self.view_ref.color2
        )
        # プレミアム付与（30日）
        await db.set_premium(
            user_id,
            guild_id,
           days=30
        )

        await interaction.response.send_message(
            "🎉 プレミアム購入が完了しました！\n"
            "次回の /pay から演出が変わります。",
            ephemeral=True
        )

        self.view_ref.stop()


# --------------------------------------------------
# Cog
# --------------------------------------------------
class PremiumShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="プレミアムショップ",
        description="プレミアム演出を購入します"
    )
    @app_commands.describe(
        description="商品説明",
        price="価格"
    )
    async def premium_shop(
        self,
        interaction: discord.Interaction,
        description: str,
        price: int
    ):
        if price <= 0:
            await interaction.response.send_message(
                "価格は1以上を指定してください。",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💎 プレミアムショップ",
            description=description,
            color=0xFFD700
        )
        embed.add_field(
            name="価格",
            value=f"{price:,} Spt",
            inline=False
        )

        view = ColorSelectView(
            bot=self.bot,
            user=interaction.user,
            guild_id=interaction.guild.id,
            price=price,
            description=description
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )


async def setup(bot):
    cog = PremiumShopCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            bot.tree.add_command(
                cmd,
                guild=discord.Object(id=gid)
            )


