import discord
from .hotel_cog import HotelCog


async def setup(bot):
    """
    ホテル機能を bot に登録するエントリーポイント。
    """
    cog = HotelCog(bot)
    await bot.add_cog(cog)

    print("🏨 Hotel module loaded.")


