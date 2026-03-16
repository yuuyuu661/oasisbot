import discord
from discord.ext import commands
from discord import app_commands

STAMP_PER_PAGE = 20


class StampSelect(discord.ui.Select):
    def __init__(self, emojis, page):

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

        target = interaction.client.stamp_target.get(interaction.user.id)

        if not target:
            return await interaction.response.send_message(
                "対象メッセージが見つかりません",
                ephemeral=True
            )

        try:
            await target.add_reaction(emoji)
            await interaction.response.send_message(
                f"{emoji} スタンプ付与",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"失敗: {e}",
                ephemeral=True
            )


class StampView(discord.ui.View):
    def __init__(self, bot, emojis, page=0):
        super().__init__(timeout=60)

        self.bot = bot
        self.emojis = emojis
        self.page = page

        self.update_ui()

    def update_ui(self):
        self.clear_items()

        start = self.page * STAMP_PER_PAGE
        end = start + STAMP_PER_PAGE

        current = self.emojis[start:end]

        self.add_item(StampSelect(current, self.page))

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


class StampContextCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.stamp_target = {}

        self.ctx_menu = app_commands.ContextMenu(
            name="スタンプ",
            callback=self.stamp_menu
        )
        bot.tree.add_command(self.ctx_menu)

    async def stamp_menu(self, interaction: discord.Interaction, message: discord.Message):

        emojis = sorted(self.bot.emojis, key=lambda e: e.name)

        if not emojis:
            return await interaction.response.send_message(
                "絵文字がありません",
                ephemeral=True
            )

        self.bot.stamp_target[interaction.user.id] = message

        view = StampView(self.bot, emojis)

        await interaction.response.send_message(
            "スタンプを選択",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(StampContextCog(bot))
