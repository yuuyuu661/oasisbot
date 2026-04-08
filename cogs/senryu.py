import re
import discord
from discord.ext import commands
from discord import app_commands
from pykakasi import kakasi


GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418

# 小文字は前文字と結合して1音
SMALL = set("ゃゅょぁぃぅぇぉャュョァィゥェォ")

CUT_HINTS = {"は", "が", "を", "に", "で", "と", "も", "の"}


class SenryuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channels: set[int] = set()

        kks = kakasi()
        self.converter = kks.getConverter()

    async def cog_load(self):
        for guild in self.bot.guilds:
            rows = await self.bot.db.get_senryu_channels(str(guild.id))
            for r in rows:
                self.target_channels.add(int(r["channel_id"]))

        print("🌸 川柳チャンネル復元完了", self.target_channels)

    # =========================
    # 管理者設定（トグル式）
    # =========================
    @app_commands.command(name="川柳検出")
    async def setup_senryu(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)
        channel_id = str(channel.id)

        enabled = await self.bot.db.toggle_senryu_channel(
            guild_id,
            channel_id
        )

        if enabled:
            self.target_channels.add(channel.id)
            msg = f"🌸 {channel.mention} の川柳検出をONにしました"
        else:
            self.target_channels.discard(channel.id)
            msg = f"🧹 {channel.mention} の川柳検出を解除しました"

        await interaction.response.send_message(
            msg,
            ephemeral=True
        )

    # =========================
    # モーラ分解
    # =========================
    def split_mora_with_map(self, hira: str, mapping: list[int]):
        mora = []
        mora_map = []

        for i, ch in enumerate(hira):
            if ch in SMALL and mora:
                mora[-1] += ch
            else:
                mora.append(ch)
                mora_map.append(mapping[i])

        return mora, mora_map

    def is_natural_break(self, text: str) -> bool:
        return text[-1] in CUT_HINTS if text else False


    def build_kana_map(self, text: str):
        hira = ""
        mapping = []

        result = self.converter.convert(text)

        raw_index = 0

        for item in result:
            orig = item["orig"]
            kana = item["hira"]

            hira += kana

            orig_len = len(orig)
            kana_len = len(kana)

            for i in range(kana_len):
                mapped = raw_index + min(
                    orig_len - 1,
                    i * orig_len // kana_len
                )
                mapping.append(mapped)

            raw_index += orig_len

        return hira, mapping

    # =========================
    # 川柳検出
    # =========================
    def detect_senryu(self, original_text: str):
        cleaned_orig = re.sub(r"\s+", "", original_text)
        cleaned_orig = re.sub(r"[。、！!？?・…ｗwW,，]", "", cleaned_orig)

        if not cleaned_orig:
            return None

        print("[SENRYU RAW]", cleaned_orig)

        hira, mapping = self.build_kana_map(cleaned_orig)
        print("[SENRYU HIRA]", hira)
        print("[SENRYU MAP]", mapping)

        mora, mora_map = self.split_mora_with_map(hira, mapping)
        print("[SENRYU MORA]", mora)
        print("[SENRYU MORA_MAP]", mora_map)

        candidates = []

        for start in range(len(mora)):
            end = start + 17
            if end > len(mora):
                break

            first_end = start + 5
            second_end = start + 12

            raw_start = mora_map[start]
            raw_first_end = mora_map[first_end - 1] + 1
            raw_second_end = mora_map[second_end - 1] + 1
            raw_end = mora_map[end - 1] + 1

            first = cleaned_orig[raw_start:raw_first_end]
            second = cleaned_orig[raw_first_end:raw_second_end]
            third = cleaned_orig[raw_second_end:raw_end]

            print(
                "[SENRYU CUT]",
                f"start={start}",
                f"first={first}",
                f"second={second}",
                f"third={third}"
            )

            first_m = "".join(mora[start:first_end])
            second_m = "".join(mora[first_end:second_end])

            score = 0
            if self.is_natural_break(first_m):
                score += 2
            if self.is_natural_break(second_m):
                score += 2

            candidates.append((score, first, second, third))

        if not candidates:
            print("[SENRYU] no candidates")
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        print("[SENRYU BEST]", candidates[0])

        _, first, second, third = candidates[0]
        return first, second, third

    # =========================
    # 監視
    # =========================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id not in self.target_channels:
            return

        result = self.detect_senryu(message.content)
        if not result:
            return

        first, second, third = result

        # =========================
        # 川柳名人 webhook送信
        # =========================
        webhooks = await message.channel.webhooks()
        webhook = discord.utils.get(webhooks, name="川柳名人")

        if webhook is None:
            with open(self.senryu_icon_path, "rb") as f:
                avatar_bytes = f.read()

            webhook = await message.channel.create_webhook(
                name="川柳名人",
                avatar=avatar_bytes
            )

        await webhook.send(
            content=(
                "🌸 **川柳を検出しました！！**\n\n"
                f"「{first}\n"
                f"　{second}\n"
                f"　　{third}」"
            ),
            username="川柳名人"
        )




async def setup(bot):
    cog = SenryuCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            try:
                bot.tree.add_command(cmd, guild=discord.Object(id=gid))
            except Exception:
                pass
