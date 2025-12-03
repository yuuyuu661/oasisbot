# cogs/hotel/setup.py

from .hotel_cog import HotelCog   # ← これが必要！！
from .checkin import HotelCheckinCog
from .ticket_buttons import TicketButtonsCog
from .room_buttons import RoomButtonsCog


async def setup(bot):
    # Cog 登録（順番はどれでもOK）
    await bot.add_cog(HotelCog(bot))          # ← コマンド持ってる本体
    await bot.add_cog(HotelCheckinCog(bot))
    await bot.add_cog(TicketButtonsCog(bot))
    await bot.add_cog(RoomButtonsCog(bot))

    # --- ★ guild 固定同期（スラッシュ反映の核心） ---
    for gid in bot.GUILD_IDS:
        guild = bot.get_guild(gid)
        try:
            synced = await bot.tree.sync(guild=guild)
            print(f"Hotel module synced {len(synced)} cmds → guild {gid}")
        except Exception as e:
            print(f"Hotel sync failed for {gid}: {e}")

    print("🏨 Hotel module loaded successfully!")
