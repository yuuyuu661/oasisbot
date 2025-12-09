# paginator.py
import discord
from discord.ui import View, Button


class Paginator(View):
    def __init__(self, pages, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.index = 0

        
        self.prev_button = Button(label="⬅️", style=discord.ButtonStyle.primary)
        self.next_button = Button(label="➡️", style=discord.ButtonStyle.primary)

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.pages) - 1

    async def prev_page(self, interaction: discord.Interaction):
        if self.index > 0:
            self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.index < len(self.pages) - 1:
            self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

