import discord
from .hotel_cog import HotelCog

async def setup(bot):
    """
    ホテル機能を bot に登録するエントリーポイント。
    """
    cog = HotelCog(bot)
    await bot.add_cog(cog)

    # ★ ホテルから add_command を行わない（衝突するため）
    #   bot.tree.sync() は bot.py 側に任せる。
    print("🏨 Hotel module loaded.")
