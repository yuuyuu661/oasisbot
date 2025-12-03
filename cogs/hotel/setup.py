# cogs/hotel/setup.py

from .checkin import HotelCheckinCog
from .ticket_buttons import TicketButtonsCog
from .room_buttons import RoomButtonsCog

async def setup(bot):
    # 3つの Cog を登録（ホテル機能を分割して管理）
    await bot.add_cog(HotelCheckinCog(bot))
    await bot.add_cog(TicketButtonsCog(bot))
    await bot.add_cog(RoomButtonsCog(bot))

    # guild 固定同期
    for gid in bot.GUILD_IDS:
        await bot.tree.sync(guild_id=gid)

    print("🏨 Hotel module loaded successfully!")
