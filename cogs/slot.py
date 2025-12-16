import discord
import random
import os
from discord.ext import commands
from discord import app_commands

# =========================
# スロット定数
# =========================
RESULT_SMALL = "small"   # 小当たり
RESULT_BIG = "big"       # 大当たり
RESULT_END = "end"       # 終了（全額支払い）

PROB_TABLE = (
    [RESULT_SMALL] * 8 +
    [RESULT_BIG] * 1 +
    [RESULT_END] * 1
)

ASSET_SMALL = "assets/slot/atari.png"
ASSET_BIG   = "assets/slot/daatari.png"
ASSET_END   = "assets/slot/shuryo.png"


# =========================
# スロット管理
# =========================
class SlotGame:
    def __init__(self, host: discord.Member, vc: discord.VoiceChannel, rate: int, fee: int):
        self.host_id = host.id
        self.vc_id = vc.id
        self.rate = rate
        self.fee = fee

        self.players: list[int] = []
        self.turn_index = 0
        self.total_pool = 0  # 小/大当たりで増える総額（終了者が全額支払い）

        self.waiting = True  # 募集フェーズ
        self.active = True   # ゲーム有効

    def current_player_id(self) -> int:
        return self.players[self.turn_index]

    def next_turn(self):
        if not self.players:
            return
        self.turn_index = (self.turn_index + 1) % len(self.players)


# =========================
# Cog
# =========================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[int, SlotGame] = {}  # message_id -> SlotGame

    # =========================
    # /スロット
    # =========================
    @app_commands.command(
        name="スロット",
        description="ボイスチャット参加者限定のパチンコスロット"
    )
    async def slot(self, interaction: discord.Interaction, rate: int, fee: int):
        member = interaction.user

        # VCチェック
        if not member.voice or not member.voice.channel:
            return await interaction.response.send_message(
                "❌ ボイスチャット参加中のみ使用できます。",
                ephemeral=True
            )

        vc = member.voice.channel

        embed = self._build_recruit_embed(rate, fee, players=[])

        view = SlotJoinView(cog=self, host=member, vc=vc, rate=rate, fee=fee)
        await interaction.response.send_message(embed=embed, view=view)

    # =========================
    # 内部：募集Embed生成
    # =========================
    def _build_recruit_embed(self, rate: int, fee: int, players: list[int]) -> discord.Embed:
        if players:
            plist = "\n".join([f"・<@{uid}>" for uid in players])
        else:
            plist = "（まだ参加者はいません）"

        embed = discord.Embed(
            title="🎰 **パチンコ**",
            description=(
                f"小当たり：+{rate} rrc\n"
                f"大当たり：+{rate * 10} rrc\n"
                f"終了：全額支払い\n\n"
                f"参加費：{fee} rrc\n\n"
                f"参加者：\n{plist}"
            ),
            color=0xFFD700
        )
        return embed

    # =========================
    # スピン処理
    # =========================
    async def spin(self, interaction: discord.Interaction, game: SlotGame):
        user = interaction.user

        if not game.active:
            return await interaction.response.send_message("❌ このゲームは終了しています。", ephemeral=True)

        # ターン制限
        if user.id != game.current_player_id():
            return await interaction.response.send_message("❌ あなたの番ではありません。", ephemeral=True)

        # 結果抽選（3レーン同一）
        result = random.choice(PROB_TABLE)

        # ここで本物の回転GIFを生成したい場合は、後でこの関数を実装して差し替えOK
        # file = await self._generate_spin_gif(result)
        file = self._static_result_file(result)

        # 勝ち分加算 or 終了処理
        if result == RESULT_SMALL:
            game.total_pool += game.rate
            text = f"🟡 小当たり！ +{game.rate} rrc\n次は <@{game.current_player_id()}> の後…"
            game.next_turn()
            next_text = f"次は <@{game.current_player_id()}> の番！"

            await interaction.response.edit_message(
                content=f"🟡 小当たり！ +{game.rate} rrc\n{next_text}",
                attachments=[file] if file else None,
                view=SlotNextView(self, game)
            )
            return

        if result == RESULT_BIG:
            game.total_pool += game.rate * 10
            next_text = ""
            game.next_turn()
            next_text = f"次は <@{game.current_player_id()}> の番！"

            await interaction.response.edit_message(
                content=f"🔵 大当たり！！ +{game.rate * 10} rrc\n{next_text}",
                attachments=[file] if file else None,
                view=SlotNextView(self, game)
            )
            return

        # RESULT_END
        await self.finish_game(interaction, game, loser=user, attachment=file)

    # =========================
    # 終了処理（全額支払い＋配給）
    # =========================
    async def finish_game(self, interaction: discord.Interaction, game: SlotGame, loser: discord.Member, attachment: discord.File | None = None):
        total = game.total_pool
        players = game.players[:]  # copy

        game.active = False

        # 念のため（参加者2人未満は成立しない）
        if len(players) < 2:
            embed = discord.Embed(
                title="📊 リザルト",
                description="❌ 参加者が不足していたためゲームを終了しました。",
                color=0xFF0000
            )
            return await interaction.response.edit_message(content=None, embed=embed, view=None)

        # 配給額（終了者以外で割る）
        receivers = [uid for uid in players if uid != loser.id]
        share = total // len(receivers) if receivers else 0

        # 残高処理（DB関数名はあなたの環境に合わせてOK）
        # loser が全額支払い
        await self.bot.db.add_balance(loser.id, -total)
        # 他メンバーへ配給
        for uid in receivers:
            await self.bot.db.add_balance(uid, share)

        embed = discord.Embed(
            title="📊 リザルト",
            description=(
                f"総額：{total} rrc\n\n"
                f"全額支払い者：{loser.mention}\n\n"
                "配給：\n" +
                ("\n".join([f"<@{uid}>：{share} rrc" for uid in receivers]) if receivers else "（配給対象なし）")
            ),
            color=0xFF0000
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            attachments=[attachment] if attachment else None,
            view=SlotContinueView(self, game)
        )

    # =========================
    # 静的画像（今はこれでOK：後でGIFに置き換え）
    # =========================
    def _static_result_file(self, result: str) -> discord.File | None:
        path = None
        if result == RESULT_SMALL:
            path = ASSET_SMALL
        elif result == RESULT_BIG:
            path = ASSET_BIG
        elif result == RESULT_END:
            path = ASSET_END

        if path and os.path.exists(path):
            return discord.File(path, filename=os.path.basename(path))
        return None

    # =========================
    # /スロットリセット
    # =========================
    @app_commands.command(
        name="スロットリセット",
        description="指定ユーザーのスロット参加キューを解除"
    )
    async def slot_reset(self, interaction: discord.Interaction, user: discord.User):
        # 参加中のゲームから外す
        for mid, game in list(self.games.items()):
            if user.id in game.players:
                game.players.remove(user.id)

                # ターン調整（抜けた人が現在ターン以前なら index ずれる）
                if game.turn_index >= len(game.players):
                    game.turn_index = 0

                await interaction.response.send_message(
                    f"✅ {user.mention} を参加キューから解除しました。",
                    ephemeral=True
                )
                return

        await interaction.response.send_message("❌ 該当する参加キューがありません。", ephemeral=True)


# =========================
# View：参加・締め切り
# =========================
class SlotJoinView(discord.ui.View):
    def __init__(
        self,
        cog: SlotCog,
        host: discord.Member,
        vc: discord.VoiceChannel,
        rate: int,
        fee: int
    ):
        super().__init__(timeout=None)

        self.cog = cog
        self.host = host
        self.vc = vc
        self.rate = rate
        self.fee = fee

        # ★ 最初は空（主催者も未参加）
        self.players: list[int] = []

    # -------------------------
    # 参加ボタン
    # -------------------------
    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        user = interaction.user
        guild = interaction.guild

        if not guild:
            return await interaction.response.send_message(
                "❌ サーバー内でのみ使用できます。",
                ephemeral=True
            )

        # VCチェック
        if (
            not user.voice
            or not user.voice.channel
            or user.voice.channel.id != self.vc.id
        ):
            return await interaction.response.send_message(
                "❌ 主催者と同じボイスチャットに居る必要があります。",
                ephemeral=True
            )

        # 二重参加防止
        if user.id in self.players:
            return await interaction.response.send_message(
                "❌ すでに参加しています。",
                ephemeral=True
            )

        try:
            guild_id = guild.id

            user_row = await self.cog.bot.db.get_user(
                user.id,
                guild_id
            )
            bal = user_row["balance"]

            if bal < self.fee:
                return await interaction.response.send_message(
                    "❌ rrcが不足しています。",
                    ephemeral=True
                )

            # 参加費支払い
            await self.cog.bot.db.add_balance(
                user.id,
                guild_id,
                -self.fee
            )

        except Exception as e:
            print("Slot join error:", e)
            return await interaction.response.send_message(
                "❌ 内部エラーが発生しました（管理者に連絡してください）",
                ephemeral=True
            )

        # 参加確定
        self.players.append(user.id)

        embed = self.cog._build_recruit_embed(
            self.rate,
            self.fee,
            self.players
        )

        await interaction.response.edit_message(embed=embed)

    # -------------------------
    # 締め切りボタン
    # -------------------------
    @discord.ui.button(label="締め切り", style=discord.ButtonStyle.danger)
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message(
                "❌ 主催者のみ使用できます。",
                ephemeral=True
            )

        if len(self.players) < 2:
            return await interaction.response.send_message(
                "❌ 参加者は2人以上必要です。",
                ephemeral=True
            )

        game = SlotGame(
            self.host,
            self.vc,
            self.rate,
            self.fee
        )
        game.players = self.players.copy()
        random.shuffle(game.players)

        self.cog.games[interaction.message.id] = game

        await interaction.response.edit_message(
            content=(
                "☠️ **DEAD OR ALIVE！**\n"
                "気合を入れてレバーを叩け！\n\n"
                f"最初は <@{game.current_player_id()}> の番！"
            ),
            embed=None,
            view=SlotSpinView(self.cog, game)
        )

# =========================
# View：スピン
# =========================
class SlotSpinView(discord.ui.View):
    def __init__(self, cog: SlotCog, game: SlotGame):
        super().__init__(timeout=None)
        self.cog = cog
        self.game = game

    @discord.ui.button(label="🎰 スピン", style=discord.ButtonStyle.primary)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.spin(interaction, self.game)


# =========================
# View：次へ
# =========================
class SlotNextView(discord.ui.View):
    def __init__(self, cog: SlotCog, game: SlotGame):
        super().__init__(timeout=None)
        self.cog = cog
        self.game = game

    @discord.ui.button(label="次", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.game.active:
            return await interaction.response.send_message("❌ このゲームは終了しています。", ephemeral=True)

        await interaction.response.edit_message(
            content=f"☠️ **DEAD OR ALIVE！**\n気合を入れてレバーを叩け！\n\n次は <@{self.game.current_player_id()}> の番！",
            view=SlotSpinView(self.cog, self.game)
        )


# =========================
# View：継続 or 終了
# =========================
class SlotContinueView(discord.ui.View):
    def __init__(self, cog: SlotCog, game: SlotGame):
        super().__init__(timeout=None)
        self.cog = cog
        self.game = game
        self.votes: set[int] = set()

    @discord.ui.button(label="継続", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.game.players:
            return await interaction.response.send_message("❌ 参加者のみ押せます。", ephemeral=True)

        self.votes.add(uid)

        # 全員同意で継続（※参加費の再徴収は「後で実装」の場所）
        if set(self.game.players) == self.votes:
            # TODO: ここで全員から参加費(self.game.fee)を再徴収したい場合は実装
            self.game.total_pool = 0
            self.game.turn_index = 0
            random.shuffle(self.game.players)
            self.game.active = True

            await interaction.message.edit(
                content=f"🔁 継続！\n最初は <@{self.game.current_player_id()}> の番！",
                embed=None,
                view=SlotSpinView(self.cog, self.game),
                attachments=[]
            )

    @discord.ui.button(label="終了", style=discord.ButtonStyle.danger)
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ゲーム完全終了
        self.cog.games.pop(interaction.message.id, None)
        await interaction.response.edit_message(content="🛑 ゲーム終了", embed=None, view=None, attachments=[])


# =========================
# ギルド同期 setup（あなたの方式）
# =========================
async def setup(bot: commands.Bot):
    cog = SlotCog(bot)
    await bot.add_cog(cog)

    # bot.GUILD_IDS = [ ... ] を持ってる前提
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))



