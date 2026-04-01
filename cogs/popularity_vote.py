import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1420918259187712093   # テスト
PAGE_SIZE = 25

ADULT_CATALOG = [
    {"key": "cyan","name": "ちゃん"},
    {"key": "inpure","name": "いんぷれ"},
    {"key": "kiza","name": "きっざにあ"},
    {"key": "konkuri","name": "こんくり"},
    {"key": "kurisu","name": "クリス"},
    {"key": "nino","name": "にの"},
    {"key": "numaru","name": "ぬまるん"},
    {"key": "yuina","name": "ゆいな"},
    {"key": "zenten","name": "ぜんてん"},
    {"key": "eng","name": "えんじぇる"},
    {"key": "yama","name": "やまだ"},
    {"key": "kono","name": "この"},
    {"key": "hiro","name": "ヒロ"},
    {"key": "mio","name": "mio"},
    {"key": "bul","name": "おいら"},
    {"key": "hana","name": "はなこ"},
    {"key": "inu","name": "いぬ"},
    {"key": "ouki","name": "おうき"},
    {"key": "aka","name": "あかり"},
    {"key": "shiba","name": "しば"},
    {"key": "ero","name": "えろこ"},
    {"key": "gero","name": "ゲロ"},
    {"key": "san","name": "サンダー"},
    {"key": "jinsei","name": "loser"},
    {"key": "tonbo","name": "トンボ"},
    {"key": "yuyu","name": "ゅゅ"},
    {"key": "naruse","name": "なるせ"},
    {"key": "rei","name": "れい"},
    {"key": "tumu","name": "つむ"},
    {"key": "urufu","name": "うるふ"},
    {"key": "cyoumi","name": "ちょうみりょう"},
    {"key": "erechima","name": "ういえれ"},
    {"key": "shigu","name": "シグ"},
    {"key": "liu","name": "リウたん"},
    {"key": "minmin","name": "みんみん"},
    {"key": "puchia","name": "ぷちあ"},
    {"key": "pyon","name": "ぴょん"},
    {"key": "dyun","name": "でゅんでゅん"},
    {"key": "ichigo","name": "いちご"},
    {"key": "suu","name": "すーちゃん"},
    {"key": "take","name": "たけのこ"},
    {"key": "tokimi","name": "トキミノ"},
    {"key": "cyama","name": "ちゃま"},
    {"key": "ika","name": "いか"},
    {"key": "kare","name": "カレー"},
    {"key": "lv","name": "lv"},
    {"key": "mata","name": "まったり"},
    {"key": "noa","name": "のあ"},
    {"key": "raise","name": "きみのよめ"},
    {"key": "syuu","name": "しゅうや"},
    {"key": "takana","name": "たかな"},
    {"key": "yomo","name": "よもチ"},
    {"key": "bachio","name": "ばっちお"},
    {"key": "cry","name": "cry"},
    {"key": "hyou","name": "メビウス"},
    {"key": "jyaku","name": "弱"},
    {"key": "kuko","name": "くこ"},
    {"key": "nyao","name": "にゃおっす"},
    {"key": "rana","name": "らな"},
    {"key": "sana","name": "sana"},
    {"key": "taida","name": "怠惰"},
    {"key": "uruha","name": "うるは"},
    {"key": "syoa","name": "しょあ"},
    {"key": "dorei","name": "どれい"},
    {"key": "ivu","name": "いゔ"},
]

CATALOG_NAMES = [x["name"] for x in ADULT_CATALOG]


# =========================
# ページ移動ボタン
# =========================
class VotePageButton(discord.ui.Button):
    def __init__(self, direction: int):
        label = "⬅ 前へ" if direction == -1 else "次へ ➡"
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: VoteSelectView = self.view
        max_page = (len(CATALOG_NAMES) - 1) // PAGE_SIZE

        view.page += self.direction
        view.page = max(0, min(max_page, view.page))
        view.refresh_items()

        await interaction.response.edit_message(
            content=f"🏆 {view.rank}位を選んでください",
            view=view
        )


# =========================
# Select
# =========================
class VoteNameSelect(discord.ui.Select):
    def __init__(self, names):
        options = [
            discord.SelectOption(label=name, value=name)
            for name in names
        ]

        super().__init__(
            placeholder="おあしすっちを選択",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view: VoteSelectView = self.view
        picked = self.values[0]

        if picked in view.selected:
            return await interaction.response.send_message(
                "⚠ 同じおあしすっちは選べません",
                ephemeral=True
            )

        view.selected.append(picked)

        if len(view.selected) >= 5:
            await interaction.client.db._execute("""
                INSERT INTO oasistchi_popularity_votes
                (guild_id, user_id, rank_1, rank_2, rank_3, rank_4, rank_5)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """,
                str(interaction.guild.id),
                str(interaction.user.id),
                *view.selected
            )

            return await interaction.response.edit_message(
                content=(
                    "🏆 投票完了！\n\n"
                    f"1位: {view.selected[0]}\n"
                    f"2位: {view.selected[1]}\n"
                    f"3位: {view.selected[2]}\n"
                    f"4位: {view.selected[3]}\n"
                    f"5位: {view.selected[4]}"
                ),
                view=None
            )

        view.rank += 1
        view.page = 0
        view.refresh_items()

        await interaction.response.edit_message(
            content=f"🏆 {view.rank}位を選んでください",
            view=view
        )


# =========================
# 投票選択View
# =========================
class VoteSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.page = 0
        self.rank = 1
        self.selected = []
        self.refresh_items()

    def refresh_items(self):
        self.clear_items()

        start = self.page * PAGE_SIZE
        end = start + PAGE_SIZE
        names = [
            x for x in CATALOG_NAMES[start:end]
            if x not in self.selected
        ]

        self.add_item(VoteNameSelect(names))

        max_page = (len(CATALOG_NAMES) - 1) // PAGE_SIZE
        if self.page > 0:
            self.add_item(VotePageButton(-1))
        if self.page < max_page:
            self.add_item(VotePageButton(1))


# =========================
# 開始ボタン
# =========================
class PopularityVoteStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="投票",
        style=discord.ButtonStyle.green,
        custom_id="oasistchi_popularity_vote"
    )
    async def vote_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        already = await interaction.client.db._fetchrow("""
            SELECT 1
            FROM oasistchi_popularity_votes
            WHERE guild_id=$1 AND user_id=$2
        """, str(interaction.guild.id), str(interaction.user.id))

        if already:
            return await interaction.response.send_message(
                "✅ すでに投票済みです",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🏆 1位を選んでください",
            view=VoteSelectView(),
            ephemeral=True
        )


# =========================
# Cog
# =========================
class PopularityVoteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(PopularityVoteStartView())

    @app_commands.command(name="おあしすっち人気投票")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def start_vote(
        self,
        interaction: discord.Interaction,
        title: str,
        body: str
    ):
        embed = discord.Embed(
            title=title,
            description=body,
            color=discord.Color.gold()
        )

        await interaction.response.send_message(
            embed=embed,
            view=PopularityVoteStartView()
        )

    @app_commands.command(name="人気投票結果発表")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def show_result(self, interaction: discord.Interaction):

        rows = await self.bot.db._fetch("""
            SELECT rank_1, rank_2, rank_3, rank_4, rank_5
            FROM oasistchi_popularity_votes
            WHERE guild_id=$1
        """, str(interaction.guild.id))

        scores = {}

        for row in rows:
            ranks = [
                row["rank_1"],
                row["rank_2"],
                row["rank_3"],
                row["rank_4"],
                row["rank_5"]
            ]

            for i, name in enumerate(ranks):
                scores[name] = scores.get(name, 0) + (5 - i)

        top10 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]

        lines = []
        for i, (name, score) in enumerate(top10, 1):
            lines.append(f"**{i}位** {name}　`{score}票`")

        embed = discord.Embed(
            title="🏆 人気投票結果",
            description="\n".join(lines) if lines else "まだ投票がありません",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(PopularityVoteCog(bot))
