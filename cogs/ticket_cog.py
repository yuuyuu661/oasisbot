import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
import asyncio
import re
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List

JST = timezone(timedelta(hours=9))

TICKET_LABELS_FILE = "data/ticket_labels.json"

# =========================
# util
# =========================

def load_labels():
    if not os.path.exists(TICKET_LABELS_FILE):
        return ["問い合わせ"]
    with open(TICKET_LABELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_labels(labels):
    with open(TICKET_LABELS_FILE, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)

def slugify(label: str):
    label = re.sub(r"\s+", "-", label.lower())
    label = re.sub(r"[^a-z0-9\-ぁ-んァ-ヴー一-龯]", "", label)
    return label or "ticket"

# =========================
# close button
# =========================

class CloseTicketView(View):

    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="問い合わせ終了", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):

        channel = interaction.channel
        await interaction.response.send_message("5秒後に削除します", ephemeral=True)

        await asyncio.sleep(5)
        await channel.delete()

# =========================
# ticket create view
# =========================

class TicketView(View):

    def __init__(self, label, support_role_id):
        super().__init__(timeout=None)
        self.label = label
        self.slug = slugify(label)
        self.support_role_id = support_role_id

        btn = Button(
            label=f"{label}チケット作成",
            style=discord.ButtonStyle.green,
            custom_id=f"ticket_create::{self.slug}"
        )

        async def callback(interaction: discord.Interaction):
            await self.create_ticket(interaction)

        btn.callback = callback
        self.add_item(btn)

    async def create_ticket(self, interaction):

        guild = interaction.guild
        category = interaction.channel.category

        if not category:
            await interaction.response.send_message("カテゴリ内で実行してください", ephemeral=True)
            return

        support_role = guild.get_role(self.support_role_id)

        name = f"{self.slug}-{interaction.user.name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            support_role: discord.PermissionOverwrite(view_channel=True)
        }

        ch = await guild.create_text_channel(
            name=name,
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"作成しました {ch.mention}", ephemeral=True)

        await ch.send(
            f"{interaction.user.mention} 内容を書いてください",
            view=CloseTicketView(interaction.user.id)
        )

# =========================
# cog
# =========================

class TicketCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):

        settings = await self.bot.db.get_settings_global()

        support_role = int(settings["ticket_support_role"])

        for lb in load_labels():
            self.bot.add_view(TicketView(lb, support_role))

    @app_commands.command(name="ticket")
    async def ticket_panel(self, interaction: discord.Interaction, label: Optional[str] = "問い合わせ"):

        SUPPORT_ROLE_ID = 1445403608035364874

        labels = load_labels()
        if label not in labels:
            labels.append(label)
            save_labels(labels)

        view = TicketView(label, support_role)

        await interaction.response.send_message(
            f"{label}チケットを作成できます",
            view=view
        )

async def setup(bot):

    await bot.add_cog(TicketCog(bot))
