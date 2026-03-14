import discord
from discord.ext import commands
import time

# ⭐ 監視VCカテゴリー
WATCH_CATEGORIES = {
    1420918260328566866,
    1420918260328566867,
}

# ⭐ 自己紹介チャンネル対応
INTRO_CHANNEL_MAP = {
    ("仮", "男"): 1482197753537888296,
    ("仮", "女"): 1482197779496566936,
    ("本", "男"): 1482197806922989659,
    ("本", "女"): 1482197840896987166,
}

# ⭐ 判定ロール
ROLE_MAP = {
    "仮": 1482197926754127963,
    "本": 1482197992470614026,
    "男": 1482198063010418718,
    "女": 1482198021071573043,
}

CACHE_TTL = 3600  # キャッシュ1時間

class IntroCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.vc_cooldown = {}

    def resolve_intro_channel(self, member):
        roles = {r.id for r in member.roles}

        status = None
        gender = None

        if ROLE_MAP["仮"] in roles:
            status = "仮"
        elif ROLE_MAP["本"] in roles:
            status = "本"

        if ROLE_MAP["男"] in roles:
            gender = "男"
        elif ROLE_MAP["女"] in roles:
            gender = "女"

        if not status or not gender:
            return None

        return INTRO_CHANNEL_MAP.get((status, gender))

    async def find_intro_url(self, guild, member, channel_id):
        now = time.time()

        if member.id in self.cache:
            url, ts = self.cache[member.id]
            if now - ts < CACHE_TTL:
                return url

        channel = guild.get_channel(channel_id)
        if not channel:
            return None

        async for msg in channel.history(limit=40):
            if msg.author.id == member.id:
                url = msg.jump_url
                self.cache[member.id] = (url, now)
                return url

        return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):

        if member.bot:
            return

        # 入室のみ
        if before.channel == after.channel:
            return

        if after.channel is None:
            return

        vc = after.channel

        # ⭐ 監視カテゴリー判定
        if not vc.category or vc.category.id not in WATCH_CATEGORIES:
            return

        now = time.time()

        # ⭐ 連投防止
        if member.id in self.vc_cooldown:
            if now - self.vc_cooldown[member.id] < 30:
                return

        channel_id = self.resolve_intro_channel(member)
        if not channel_id:
            return

        url = await self.find_intro_url(member.guild, member, channel_id)
        if not url:
            return

        try:
            await vc.send(
                f"📢 {member.mention} の自己紹介はこちら\n{url}"
            )
            self.vc_cooldown[member.id] = now
        except:
            pass


async def setup(bot):
    await bot.add_cog(IntroCog(bot))
