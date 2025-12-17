import discord
import random
import os
from discord.ext import commands
from discord import app_commands


# =========================
# スロット定数
# =========================
RESULT_SMALL = "small"
RESULT_BIG = "big"
RESULT_END = "end"

PROB_TABLE = (
    [RESULT_SMALL] * 8 +
    [RESULT_BIG] +
    [RESULT_END]
)

ASSET_SMALL = "assets/slot/atari.png"
ASSET_BIG   = "assets/slot/daatari.png"
ASSET_END   = "assets/slot/shuryo.png"


# =========================
# スロット管理クラス（キャッシュ）
# =========================
class SlotGame:
    def __init__(
        self,
        host: discord.Member,
        vc: discord.VoiceChannel,
        rate: int,
        fee: int,
        session_id: str
    ):
        self.session_id = session_id
        self.host_id = host.id
        self.vc_id = vc.id
        self.rate = rate
        self.fee = fee

        self.players: list[int] = []
        self.turn_index = 0
        self.total_pool = 0
        self.active = True

    def current_player_id(self) -> int:
        return self.players[self.turn_index]

    def next_turn(self):
        self.turn_index = (self.turn_index + 1) % len(self.players)


# =========================
# Cog 本体
# =========================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[int, SlotGame] = {}

    # -------------------------
    # /スロット
    # -------------------------
    @app_commands.command(
        name="スロット",
        description="ボイスチャット参加者限定のパチンコスロット"
    )
    async def slot(
        self,
        interaction: discord.Interaction,
        rate: int,
        fee: int
    ):
        member = interaction.user

        if not member.voice or not member.voice.channel:
            return await interaction.response.send_message(
                "❌ ボイスチャット参加中のみ使用できます。",
                ephemeral=True
            )

        vc = member.voice.channel
        session_id = str(interaction.id)

        # DBにセッション作成（正本）
        await self.bot.db.create_slot_session(
            session_id=session_id,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            host_id=member.id,
            rate=rate,
            fee=fee
        )

        embed = self._build_recruit_embed(rate, fee, [])

        view = SlotJoinView(
            cog=self,
            host=member,
            vc=vc,
            rate=rate,
            fee=fee,
            session_id=session_id
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )

    # -------------------------
    # 募集用 Embed
    # -------------------------
    def _build_recruit_embed(
        self,
        rate: int,
        fee: int,
        players: list[int]
    ) -> discord.Embed:
        plist = (
            "\n".join(f"・<@{uid}>" for uid in players)
            if players
            else "（まだ参加者はいません）"
        )

        return discord.Embed(
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

    # -------------------------
    # スピン処理
    # -------------------------
    async def spin(
        self,
        interaction: discord.Interaction,
        game: SlotGame
    ):
        user = interaction.user

        if not game.active:
            return await interaction.response.send_message(
                "❌ このゲームは終了しています。",
                ephemeral=True
            )

        if user.id != game.current_player_id():
            return await interaction.response.send_message(
                "❌ あなたの番ではありません。",
                ephemeral=True
            )

        result = random.choice(PROB_TABLE)
        file = self._static_result_file(result)

        if result == RESULT_SMALL:
            game.total_pool += game.rate
            game.next_turn()

        elif result == RESULT_BIG:
            game.total_pool += game.rate * 10
            game.next_turn()

        else:
            await self.finish_game(interaction, game, user, file)
            return

        # DBへ反映（正本更新）
        await self.bot.db.update_slot_turn(
            game.session_id,
            game.turn_index,
            game.total_pool
        )

        await interaction.response.edit_message(
            content=(
                f"{'🟡 小当たり' if result == RESULT_SMALL else '🔵 大当たり'}！\n"
                f"次は <@{game.current_player_id()}> の番！"
            ),
            attachments=[file] if file else None,
            view=SlotNextView(self, game)
        )

    # -------------------------
    # 終了処理
    # -------------------------
    async def finish_game(
        self,
        interaction: discord.Interaction,
        game: SlotGame,
        loser: discord.Member,
        attachment: discord.File | None
    ):
        game.active = False
        guild_id = interaction.guild.id

        total = game.total_pool
        players = game.players[:]

        receivers = [uid for uid in players if uid != loser.id]
        share = total // len(receivers)

        await self.bot.db.add_balance(loser.id, guild_id, -total)

        for uid in receivers:
            await self.bot.db.add_balance(uid, guild_id, share)

        await self.bot.db.finish_slot_session(game.session_id)

        embed = discord.Embed(
            title="📊 リザルト",
            description=(
                f"総額：{total} rrc\n\n"
                f"全額支払い者：{loser.mention}\n\n"
                "配給：\n"
                + "\n".join(f"<@{uid}>：{share} rrc" for uid in receivers)
            ),
            color=0xFF0000
        )

        await interaction.response.edit_message(
            embed=embed,
            attachments=[attachment] if attachment else None,
            view=SlotContinueView(self, game)
        )

    # -------------------------
    # 静的結果画像
    # -------------------------
    def _static_result_file(self, result: str) -> discord.File | None:
        path = {
            RESULT_SMALL: ASSET_SMALL,
            RESULT_BIG: ASSET_BIG,
            RESULT_END: ASSET_END
        }.get(result)

        if path and os.path.exists(path):
            return discord.File(path, filename=os.path.basename(path))
        return None


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
        fee: int,
        session_id: str
    ):
        super().__init__(timeout=None)
        self.cog = cog
        self.host = host
        self.vc = vc
        self.rate = rate
        self.fee = fee
        self.session_id = session_id
        self.players: list[int] = []

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild_id = interaction.guild.id
        user = interaction.user

        if not user.voice or user.voice.channel.id != self.vc.id:
            return await interaction.response.send_message(
                "❌ 同じボイスチャットに居る必要があります。",
                ephemeral=True
            )

        if user.id in self.players:
            return await interaction.response.send_message(
                "❌ すでに参加しています。",
                ephemeral=True
            )

        bal = (await self.cog.bot.db.get_user(user.id, guild_id))["balance"]
        if bal < self.fee:
            return await interaction.response.send_message(
                "❌ rrcが不足しています。",
                ephemeral=True
            )

        await self.cog.bot.db.add_balance(user.id, guild_id, -self.fee)

        # DB正本に追加
        await self.cog.bot.db.add_slot_player(
            self.session_id,
            user.id,
            len(self.players)
        )

        self.players.append(user.id)

        embed = self.cog._build_recruit_embed(
            self.rate,
            self.fee,
            self.players
        )

        await interaction.response.edit_message(embed=embed)

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
            self.fee,
            self.session_id
        )

        rows = await self.cog.bot.db.get_slot_players(self.session_id)
        game.players = [int(r["user_id"]) for r in rows]

        random.shuffle(game.players)

        self.cog.games[interaction.message.id] = game

        await interaction.response.edit_message(
            content=(
                "☠️ **DEAD OR ALIVE！**\n"
                "気合を入れてレバーを叩け！\n\n"
                f"最初は <@{game.current_player_id()}> の番！"
            ),
            view=SlotSpinView(self.cog, game),
            embed=None
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
        await interaction.response.edit_message(
            content=(
                "☠️ **DEAD OR ALIVE！**\n"
                f"次は <@{self.game.current_player_id()}> の番！"
            ),
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
        self.votes.add(interaction.user.id)

        if set(self.game.players) == self.votes:
            self.game.total_pool = 0
            self.game.turn_index = 0
            random.shuffle(self.game.players)
            self.game.active = True

            await interaction.message.edit(
                content=f"🔁 継続！最初は <@{self.game.current_player_id()}> の番！",
                view=SlotSpinView(self.cog, self.game)
            )

    @discord.ui.button(label="終了", style=discord.ButtonStyle.danger)
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.games.pop(interaction.message.id, None)
        await interaction.response.edit_message(
            content="🛑 ゲーム終了",
            view=None
        )


# =========================
# ギルド同期 setup
# =========================
async def setup(bot: commands.Bot):
    cog = SlotCog(bot)
    await bot.add_cog(cog)

    for gid in bot.GUILD_IDS:
        bot.tree.copy_global_to(guild=discord.Object(id=gid))

    await bot.tree.sync()

