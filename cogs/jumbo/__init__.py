import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView
from .jumbo_draw import JumboDrawHandler


ADMIN_ROLES_CACHE = {}


class JumboCog(commands.Cog):
    """Jumbo Lottery"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        guild_id = str(interaction.guild.id)
        if guild_id not in ADMIN_ROLES_CACHE:
            settings = await self.bot.db.get_settings()
            ADMIN_ROLES_CACHE[guild_id] = settings["admin_roles"] or []
        admin_ids = {int(r) for r in ADMIN_ROLES_CACHE[guild_id] if r.isdigit()}
        return any(r.id in admin_ids for r in interaction.user.roles)

    @app_commands.command(name="jumbo_start", description="Start jumbo lottery")
    @app_commands.describe(
        title="Title",
        description="Description",
        deadline="Deadline (YYYY-MM-DD HH:MM)"
    )
    async def jumbo_start(self, interaction: discord.Interaction, title: str, description: str, deadline: str):
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("Admin only", ephemeral=True)

        try:
            dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
        except:
            return await interaction.response.send_message("Invalid deadline", ephemeral=True)

        guild_id = str(interaction.guild.id)
        await self.jumbo_db.set_config(guild_id, title, description, dt)

        embed = discord.Embed(
            title=title,
            description=description,
            color=0xF1C40F
        )
        view = JumboBuyView(self.bot, self.jumbo_db, guild_id)

        await interaction.response.send_message("Started!", ephemeral=True)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="jumbo_draw", description="Draw winners")
    async def jumbo_draw(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("Admin only", ephemeral=True)

        config = await self.jumbo_db.get_config(str(interaction.guild.id))
        if not config:
            return await interaction.response.send_message("Not started", ephemeral=True)

        handler = JumboDrawHandler(self.bot, self.jumbo_db)
        await handler.start(interaction)

    @app_commands.command(name="jumbo_reset", description="Reset jumbo data")
    async def jumbo_reset(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("Admin only", ephemeral=True)

        guild_id = str(interaction.guild.id)
        await self.jumbo_db.clear_entries(guild_id)
        await self.jumbo_db.clear_winners(guild_id)
        await self.jumbo_db.reset_config(guild_id)

        await interaction.response.send_message("Reset complete", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(JumboCog(bot))
    print("🎫 Jumbo module loaded.")
