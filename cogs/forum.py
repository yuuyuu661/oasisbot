import discord
from discord.ext import commands

FORUM_ID = 1482927126238728294
LOG_CHANNEL_ID = 1445402811352219852

PASS_EMOJI = "a_12"
FAIL_EMOJI = "a_13"

THRESHOLD = 2


class ForumJudgeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.judged_messages = set()

    async def send_log(self, guild, thread, result):

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        embed = discord.Embed(
            title="📋 判定結果",
            color=discord.Color.green() if result == "合格" else discord.Color.red()
        )

        embed.add_field(name="投稿者", value=thread.owner.mention if thread.owner else "不明")
        embed.add_field(name="スレッド", value=thread.mention)
        embed.add_field(name="結果", value=result)

        await log_channel.send(embed=embed)

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

        # 最初のメッセージのみ
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

        guild = self.bot.get_guild(payload.guild_id)

        if pass_count >= THRESHOLD:
            self.judged_messages.add(payload.message_id)

            await channel.send("✅ 合格です")
            await self.send_log(guild, channel, "合格")

        elif fail_count >= THRESHOLD:
            self.judged_messages.add(payload.message_id)

            await channel.send("❌ 残念でした")
            await self.send_log(guild, channel, "不合格")


async def setup(bot):
    await bot.add_cog(ForumJudgeCog(bot))
