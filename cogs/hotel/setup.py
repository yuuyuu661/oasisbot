import discord
from .hotel_cog import HotelCog

@bot.event
async def on_guild_channel_delete(channel):
    # Hotel room cleanup
    if isinstance(channel, discord.VoiceChannel):
        room = await bot.db.get_room(str(channel.id))
        if room:
            await bot.db.delete_room(str(channel.id))
            print(f"[Hotel] Room deleted → cleanup DB (Channel {channel.id})")


async def setup(bot):
    """
    ホテル機能を bot に登録するエントリーポイント。
    """
    cog = HotelCog(bot)
    await bot.add_cog(cog)

    # 指定ギルドにスラッシュコマンドを同期
    if hasattr(bot, "GUILD_IDS"):
        for cmd in cog.get_app_commands():
            for gid in bot.GUILD_IDS:
                bot.tree.add_command(cmd, guild=discord.Object(id=gid))

    print("🏨 Hotel module loaded.")

