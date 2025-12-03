# cogs/hotel/setup.py

from .hotel_cog import HotelCog

async def setup(bot):
    await bot.add_cog(HotelCog(bot))

    # Slash Command をギルドごとに同期
    if hasattr(bot, "GUILD_IDS"):
        for gid in bot.GUILD_IDS:
            try:
                guild = bot.get_guild(gid)
                synced = await bot.tree.sync(guild=guild)
                print(f"Hotel module synced {len(synced)} cmds → guild {gid}")
            except Exception as e:
                print(f"Hotel sync failed for {gid}: {e}")

    print("🏨 Hotel module loaded successfully!")
