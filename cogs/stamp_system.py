import discord
from discord.ext import commands
from discord import app_commands
import os
import math

STAMP_DIR = "stamps"
PER_PAGE = 25


# ==============================
# スタンプボタン
# ==============================

class StampButton(discord.ui.Button):

    def __init__(self, filename):

        name = os.path.splitext(filename)[0]

        super().__init__(
            label=name[:20],
            style=discord.ButtonStyle.secondary,
            row=None
        )

        self.filename = filename

    async def callback(self, interaction: discord.Interaction):

        path = f"{STAMP_DIR}/{self.filename}"

        file = discord.File(path)

        await interaction.response.send_message(
            file=file
        )


# ==============================
# ページナビゲーション
# ==============================

class PageButton(discord.ui.Button):

    def __init__(self, direction):

        label = "◀" if direction == -1 else "▶"

        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary
        )

        self.direction = direction

    async def callback(self, interaction: discord.Interaction):

        view: StampView = self.view

        view.page += self.direction

        view.page = max(0, min(view.page, view.max_page))

        await view.update(interaction)


# ==============================
# 検索モーダル
# ==============================

class SearchModal(discord.ui.Modal, title="スタンプ検索"):

    query = discord.ui.TextInput(
        label="検索ワード",
        placeholder="スタンプ名を入力",
        required=True
    )

    def __init__(self, view):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):

        view = self.view_ref

        q = self.query.value.lower()

        view.filtered = [
            f for f in view.all_files
            if q in f.lower()
        ]

        view.page = 0
        view.update_pages()

        await view.update(interaction)


class SearchButton(discord.ui.Button):

    def __init__(self):
        super().__init__(
            label="🔎 検索",
            style=discord.ButtonStyle.success
        )

    async def callback(self, interaction: discord.Interaction):

        view: StampView = self.view

        await interaction.response.send_modal(
            SearchModal(view)
        )


# ==============================
# メインView
# ==============================

class StampView(discord.ui.View):

    def __init__(self, files):

        super().__init__(timeout=300)

        self.all_files = files
        self.filtered = files

        self.page = 0

        self.update_pages()

        self.build()

    # --------------------------

    def update_pages(self):

        self.max_page = max(
            0,
            math.ceil(len(self.filtered) / PER_PAGE) - 1
        )

    # --------------------------

    def build(self):

        self.clear_items()

        start = self.page * PER_PAGE
        end = start + PER_PAGE

        page_files = self.filtered[start:end]

        for f in page_files:

            self.add_item(StampButton(f))

        self.add_item(PageButton(-1))
        self.add_item(PageButton(1))
        self.add_item(SearchButton())

    # --------------------------

    async def update(self, interaction):

        self.build()

        embed = self.make_embed()

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    # --------------------------

    def make_embed(self):

        embed = discord.Embed(
            title="🖼 スタンプ一覧",
            description=f"{len(self.filtered)} 件",
            color=0x2b2d31
        )

        start = self.page * PER_PAGE
        end = start + PER_PAGE

        page_files = self.filtered[start:end]

        text = ""

        for f in page_files:

            name = os.path.splitext(f)[0]

            text += f"`{name}` "

        embed.add_field(
            name=f"ページ {self.page+1}/{self.max_page+1}",
            value=text if text else "なし",
            inline=False
        )

        return embed


# ==============================
# コグ
# ==============================

class StampSystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="スタンプ",
        description="スタンプを送信"
    )
    async def stamp(self, interaction: discord.Interaction):

        if not os.path.exists(STAMP_DIR):

            await interaction.response.send_message(
                "スタンプフォルダがありません",
                ephemeral=True
            )
            return

        files = [
            f for f in os.listdir(STAMP_DIR)
            if f.lower().endswith(
                (".png", ".gif", ".jpg", ".webp")
            )
        ]

        if not files:

            await interaction.response.send_message(
                "スタンプがありません",
                ephemeral=True
            )
            return

        view = StampView(files)

        embed = view.make_embed()

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )


async def setup(bot):

    await bot.add_cog(StampSystem(bot))