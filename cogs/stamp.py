import discord
from discord.ext import commands

def find_emoji(bot, name_or_id: str):
    # ID指定
    if name_or_id.isdigit():
        return bot.get_emoji(int(name_or_id))

    # 名前指定
    for e in bot.emojis:
        if e.name == name_or_id:
            return e
    return None


class StampCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stamp")
    async def stamp(self, ctx, message_link: str, emoji: str):
        """
        !stamp メッセージリンク 絵文字名 or 絵文字ID
        """

        try:
            parts = message_link.split("/")
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
        except:
            return await ctx.send("❌ メッセージリンクが不正")

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return await ctx.send("❌ チャンネル取得失敗")

        try:
            msg = await channel.fetch_message(message_id)
        except:
            return await ctx.send("❌ メッセージ取得失敗")

        emoji_obj = find_emoji(self.bot, emoji)
        if not emoji_obj:
            return await ctx.send("❌ 絵文字が見つかりません")

        try:
            await msg.add_reaction(emoji_obj)
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.send(f"❌ リアクション失敗: {e}")


async def setup(bot):
    await bot.add_cog(StampCog(bot))