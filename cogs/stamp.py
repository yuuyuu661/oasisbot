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

class StampBufferView(discord.ui.View):

    def __init__(self, bot, emojis, user_id, page=0):
        super().__init__(timeout=120)

        self.bot = bot
        self.emojis = emojis
        self.user_id = user_id
        self.page = page

        if user_id not in self.bot.stamp_buffer:
            self.bot.stamp_buffer[user_id] = []

        self.update_ui()

    def update_ui(self):
        self.clear_items()

        start = self.page * STAMP_PER_PAGE
        end = start + STAMP_PER_PAGE

        current = self.emojis[start:end]

        self.add_item(StampBufferSelect(current, self))
        self.add_item(SendButton())
        self.add_item(ClearButton())

        if self.page > 0:
            self.add_item(BufferPrev())
        if end < len(self.emojis):
            self.add_item(BufferNext())

class StampBufferSelect(discord.ui.Select):

    def __init__(self, emojis, view):
        self.view_ref = view

        options = [
            discord.SelectOption(label=e.name, value=str(e.id), emoji=e)
            for e in emojis
        ]

        super().__init__(placeholder="スタンプ追加", options=options)

    async def callback(self, interaction: discord.Interaction):

        emoji = interaction.client.get_emoji(int(self.values[0]))

        buffer = interaction.client.stamp_buffer[self.view_ref.user_id]
        buffer.append(str(emoji))

        await interaction.response.edit_message(
            content=f"現在: {''.join(buffer)}",
            view=self.view_ref
        )

class SendButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="送信", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        buffer = interaction.client.stamp_buffer.get(interaction.user.id)

        if not buffer:
            return await interaction.response.send_message("空です", ephemeral=True)

        if not interaction.channel.permissions_for(interaction.guild.me).manage_webhooks:
            return await interaction.response.send_message("Webhook権限なし", ephemeral=True)

        webhook = await interaction.channel.create_webhook(name="stamp")

        await webhook.send(
            content="".join(buffer),
            username=interaction.user.display_name,
            avatar_url=interaction.user.display_avatar.url
        )

        await webhook.delete()

        interaction.client.stamp_buffer[interaction.user.id] = []

        await interaction.response.edit_message(
            content="送信しました",
            view=None
        )

class ClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="クリア", style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        interaction.client.stamp_buffer[interaction.user.id] = []

        await interaction.response.edit_message(
            content="クリアしました",
            view=self.view
        )

class BufferPrev(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        self.view.page -= 1
        self.view.update_ui()
        await interaction.response.edit_message(view=self.view)


class BufferNext(discord.ui.Button):
    def __init__(self):
        super().__init__(label="▶", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        self.view.page += 1
        self.view.update_ui()
        await interaction.response.edit_message(view=self.view)


# =========================
# Cog
# =========================
class StampContextCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, "stamp_target"):
            self.bot.stamp_target = {}
        if not hasattr(self.bot, "stamp_buffer"):
            self.bot.stamp_buffer = {}
    

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
    @app_commands.command(name="スタンプ送信")
    async def stamp_send(self, interaction: discord.Interaction):

        emojis = sorted(self.bot.emojis, key=lambda e: e.name)

        view = StampBufferView(self.bot, emojis, interaction.user.id)

        await interaction.response.send_message(
            "スタンプを追加してください",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    cog = StampContextCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
