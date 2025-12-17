import discord
from discord.ext import commands

from .hotel_cog import HotelCog


async def setup(bot: commands.Bot):
    await bot.add_cog(HotelCog(bot))
    print("🏨 Hotel module loaded.")
