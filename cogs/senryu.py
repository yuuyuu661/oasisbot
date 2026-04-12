import re
import discord
from discord.ext import commands
from discord import app_commands
from pykakasi import kakasi


GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418



# 小文字は前文字と結合して1音
SMALL = set("ゃゅょぁぃぅぇぉャュョァィゥェォ")

# 句切れとして強い
CUT_HINTS_STRONG = {"。", "、", "！", "？", "…", " ", "　"}

# 句切れとして弱い
CUT_HINTS_WEAK = {"は", "が", "を", "に", "で", "と", "も", "の", "へ", "や", "か"}

# 句の終わりに来やすい
GOOD_ENDINGS = {
    "だ", "です", "ます", "かな", "けり", "なり",
    "よ", "ね", "ぞ", "や", "か", "な", "わ",
    "た", "て", "る", "たい", "ない"
}

# 句の終わりに来るとかなり不自然になりやすい
BAD_ENDINGS = {
    "を", "に", "で", "と", "が", "は", "の", "へ"
}

# 句の頭に来ると不自然になりやすい
BAD_STARTS = {
    "を", "に", "で", "と", "が", "は", "の", "も", "へ"
}


class SenryuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channels: set[int] = set()

        kks = kakasi()
        self.converter = kks.getConverter()
        self.senryu_icon_path = "cogs/assets/senryu/master.png"

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
        cleaned_orig = re.sub(r"[。!！?？・,…，ｗwW]+", "", cleaned_orig)

        if not cleaned_orig:
            return None

        # 短すぎ・長すぎは除外
        if len(cleaned_orig) < 5:
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

            first = cleaned_orig[raw_start:raw_first_end].strip()
            second = cleaned_orig[raw_first_end:raw_second_end].strip()
            third = cleaned_orig[raw_second_end:raw_end].strip()

            first_m = "".join(mora[start:first_end])
            second_m = "".join(mora[first_end:second_end])
            third_m = "".join(mora[second_end:end])

            print(
                "[SENRYU CUT]",
                f"start={start}",
                f"first={first}",
                f"second={second}",
                f"third={third}"
            )

            score = self.candidate_score(first, second, third, first_m, second_m)

            print(
                "[SENRYU SCORE]",
                f"score={score}",
                f"first={first}",
                f"second={second}",
                f"third={third}"
            )

            if self.is_good_candidate(first, second, third, score):
                candidates.append((score, first, second, third))

        if not candidates:
            print("[SENRYU] no good candidates")
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0]

        print("[SENRYU BEST]", best)

        _, first, second, third = best
        return first, second, third


    def is_strong_break(self, text: str) -> bool:
        return bool(text) and any(text.endswith(x) for x in CUT_HINTS_STRONG)

    def is_weak_break(self, text: str) -> bool:
        return bool(text) and any(text.endswith(x) for x in CUT_HINTS_WEAK)

    def has_bad_repetition(self, text: str) -> bool:
        # 同じ文字3連続以上
        return re.search(r"(.)\1\1", text) is not None

    def is_mostly_hiragana(self, text: str) -> bool:
        hira = re.findall(r"[ぁ-んー]", text)
        if not text:
            return False
        return len(hira) / max(1, len(text)) >= 0.8

    def phrase_quality_score(self, phrase: str, is_last: bool = False) -> int:
        score = 0
        phrase = phrase.strip()

        if not phrase:
            return -100

        if len(phrase) >= 2:
            score += 1
        else:
            score -= 2

        if self.has_bad_repetition(phrase):
            score -= 4

        if any(phrase.startswith(x) for x in BAD_STARTS):
            score -= 4

        if any(phrase.endswith(x) for x in BAD_ENDINGS):
            score -= 4

        if any(phrase.endswith(x) for x in GOOD_ENDINGS):
            score += 2

        if is_last:
            if any(phrase.endswith(x) for x in BAD_ENDINGS):
                score -= 2
            if re.search(r"[ぁ-んァ-ン一-龥]$", phrase):
                score += 1

        if self.is_mostly_hiragana(phrase) and len(phrase) >= 4:
            score -= 1

        return score

    def candidate_score(self, first: str, second: str, third: str, first_m: str, second_m: str) -> int:
        score = 0

        # 句切れ
        if self.is_strong_break(first):
            score += 5
        elif self.is_weak_break(first_m):
            score += 2

        if self.is_strong_break(second):
            score += 5
        elif self.is_weak_break(second_m):
            score += 2

        # 各句の自然さ
        score += self.phrase_quality_score(first)
        score += self.phrase_quality_score(second)
        score += self.phrase_quality_score(third, is_last=True)

        # 極端に短い・変な句を減点
        if len(first.strip()) <= 1:
            score -= 3
        if len(second.strip()) <= 1:
            score -= 3
        if len(third.strip()) <= 1:
            score -= 3

        # 全部ほぼひらがなだけで構成されるとノイズ率高め
        joined = first + second + third
        if self.is_mostly_hiragana(joined) and len(joined) >= 10:
            score -= 2

        return score

    def is_good_candidate(self, first: str, second: str, third: str, score: int) -> bool:
        if score < 3:
            return False

        if any(first.startswith(x) for x in BAD_STARTS):
            return False
        if any(second.startswith(x) for x in BAD_STARTS):
            return False
        if any(third.startswith(x) for x in BAD_STARTS):
            return False

        bad_end_count = 0
        for p in (first, second, third):
            if any(p.endswith(x) for x in BAD_ENDINGS):
                bad_end_count += 1
        if bad_end_count >= 2:
            return False

        return True

    # =========================
    # 監視
    # =========================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id not in self.target_channels:
            return

        text = message.content.strip()

        # 短文すぎる・URLだけ・メンションだけを弾く
        if len(text) < 8:
            return
        if re.fullmatch(r"https?://\S+", text):
            return
        if re.fullmatch(r"<@!?[0-9]+>", text):
            return

        result = self.detect_senryu(text)
        if not result:
            return

        first, second, third = result

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
                "**ここで一句！**\n\n"
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
