import discord
from discord.ext import commands

FORUM_ID = 1482927126238728294

PASS_EMOJI = "a_12"
FAIL_EMOJI = "a_13"

THRESHOLD = 4


class ForumJudgeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.judged_messages = set()  # 二重判定防止

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):

        if payload.guild_id is None:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if not isinstance(channel, discord.Thread):
            return

        if channel.parent_id != FORUM_ID:
            return

        # フォーラム投稿の最初のメッセージのみ判定
        if payload.message_id != channel.id:
            return

        if payload.message_id in self.judged_messages:
            return

        msg = await channel.fetch_message(payload.message_id)

        pass_count = 0
        fail_count = 0

        for reaction in msg.reactions:

            emoji_name = None

            if isinstance(reaction.emoji, discord.Emoji):
                emoji_name = reaction.emoji.name

            if emoji_name == PASS_EMOJI:
                pass_count = reaction.count

            if emoji_name == FAIL_EMOJI:
                fail_count = reaction.count

        if pass_count >= THRESHOLD:
            self.judged_messages.add(payload.message_id)
            await channel.send("✅ 合格です")

        elif fail_count >= THRESHOLD:
            self.judged_messages.add(payload.message_id)
            await channel.send("❌ 残念でした")


async def setup(bot):
    await bot.add_cog(ForumJudgeCog(bot))