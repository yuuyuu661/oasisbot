from .checkin import HotelCheckinCog
from .ticket_dropdown import TicketButtonsCog   # ← ここを変更！
from .room_buttons import RoomButtonsCog


async def setup(bot):
    await bot.add_cog(HotelCheckinCog(bot))
    await bot.add_cog(TicketButtonsCog(bot))
    await bot.add_cog(RoomButtonsCog(bot))

    if hasattr(bot, "GUILD_IDS"):
        for gid in bot.GUILD_IDS:
            try:
                guild = bot.get_guild(gid)
                synced = await bot.tree.sync(guild=guild)
                print(f"Hotel module synced {len(synced)} cmds → guild {gid}")
            except Exception as e:
                print(f"Hotel sync failed for {gid}: {e}")

    print("🏨 Hotel module loaded successfully!")
