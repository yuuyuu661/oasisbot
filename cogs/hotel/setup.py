import discord
from .hotel_cog import HotelCog


async def setup(bot: commands.Bot):
    await bot.add_cog(HotelSetupCog(bot))

    print("🏨 Hotel module loaded.")



