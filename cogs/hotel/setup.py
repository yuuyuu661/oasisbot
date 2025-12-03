# cogs/hotel/setup.py

from .hotel_cog import HotelCog   # ← これだけでよい

async def setup(bot):
    await bot.add_cog(HotelCog(bot))

    # guild 固定同期
    if hasattr(bot, "GUILD_IDS"):
        for gid in bot.GUILD_IDS:
            guild = bot.get_guild(gid)
            if guild:
                try:
                    synced = await bot.tree.sync(guild=guild)
                    print(f"Hotel module synced {len(synced)} cmds → guild {gid}")
                except Exception as e:
                    print(f"Hotel sync failed for {gid}: {e}")

    print("🏨 Hotel module loaded successfully!")
