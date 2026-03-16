import discord
from discord.ext import commands
from discord import app_commands

STAMP_PER_PAGE = 20


# =========================
# Select
# =========================
class StampSelect(discord.ui.Select):
    def __init__(self, emojis, page, mode):
        self.mode = mode

        options = [
            discord.SelectOption(
                label=e.name,
                value=str(e.id),
                emoji=e
            )
            for e in emojis
        ]

        super().__init__(
            placeholder=f"スタンプ選択 (Page {page+1})",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        emoji_id = int(self.values[0])
        emoji = interaction.client.get_emoji(emoji_id)

        # =========================
        # リアクションモード
        # =========================
        if self.mode == "react":
            target = interaction.client.stamp_target.get(interaction.user.id)

            if not target:
                return await interaction.response.send_message(
                    "対象メッセージが見つかりません",
                    ephemeral=True
                )

            await target.add_reaction(emoji)
            return await interaction.response.send_message(
                f"{emoji} リアクション付与",
                ephemeral=True
            )

        # =========================
        # 送信モード
        # =========================
        elif self.mode == "send":

            webhook = await interaction.channel.create_webhook(name="stamp")

            await webhook.send(
                content=str(emoji),
                username=interaction.user.display_name,
                avatar_url=interaction.user.display_avatar.url
            )

            await webhook.delete()

            return await interaction.response.defer()


# =========================
# View
# =========================
class StampView(discord.ui.View):
    def __init__(self, bot, emojis, mode, page=0):
        super().__init__(timeout=60)

        self.bot = bot
        self.emojis = emojis
        self.page = page
        self.mode = mode

        self.update_ui()

    def update_ui(self):
        self.clear_items()

        start = self.page * STAMP_PER_PAGE
        end = start + STAMP_PER_PAGE

        current = self.emojis[start:end]

        self.add_item(StampSelect(current, self.page, self.mode))

        if self.page > 0:
            self.add_item(PrevButton())

        if end < len(self.emojis):
            self.add_item(NextButton())


class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: StampView = self.view
        view.page -= 1
        view.update_ui()
        await interaction.response.edit_message(view=view)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="▶", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: StampView = self.view
        view.page += 1
        view.update_ui()
        await interaction.response.edit_message(view=view)


# =========================
# Cog
# =========================
class StampContextCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, "stamp_target"):
            self.bot.stamp_target = {}

    async def cog_load(self):

        self.ctx_menu = app_commands.ContextMenu(
            name="スタンプ",
            callback=self.stamp_menu
        )

        for gid in self.bot.GUILD_IDS:
            self.bot.tree.add_command(
                self.ctx_menu,
                guild=discord.Object(id=gid)
            )

    # =========================
    # ContextMenu（リアクション）
    # =========================
    async def stamp_menu(self, interaction: discord.Interaction, message: discord.Message):

        emojis = sorted(self.bot.emojis, key=lambda e: e.name)

        self.bot.stamp_target[interaction.user.id] = message

        view = StampView(self.bot, emojis, mode="react")

        await interaction.response.send_message(
            "スタンプを選択",
            view=view,
            ephemeral=True
        )

    # =========================
    # Slash（送信）
    # =========================
    @app_commands.command(name="スタンプ送信", description="スタンプを送信します")
    async def stamp_send(self, interaction: discord.Interaction):

        emojis = sorted(self.bot.emojis, key=lambda e: e.name)

        view = StampView(self.bot, emojis, mode="send")

        await interaction.response.send_message(
            "送信するスタンプを選択",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    cog = StampContextCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
