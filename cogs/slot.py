import discord
import random
import asyncio
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
    [RESULT_BIG] * 1 +
    [RESULT_END] * 1
)

# =========================
# スロット管理
# =========================
class SlotGame:
    def __init__(self, host, vc, rate, fee):
        self.host = host
        self.vc_id = vc.id
        self.rate = rate
        self.fee = fee

        self.players: list[int] = []
        self.turn_index = 0
        self.total_pool = 0

        self.active = True
        self.waiting = True

    def current_player(self):
        return self.players[self.turn_index]

    def next_turn(self):
        self.turn_index = (self.turn_index + 1) % len(self.players)


# =========================
# Cog
# =========================
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[int, SlotGame] = {}  # message_id: SlotGame

    # =========================
    # /スロット
    # =========================
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

        # VCチェック
        if not member.voice or not member.voice.channel:
            return await interaction.response.send_message(
                "❌ ボイスチャット参加中のみ使用できます。",
                ephemeral=True
            )

        vc = member.voice.channel

        embed = discord.Embed(
            title="🎰 **パチンコ**",
            description=(
                f"小当たり：+{rate} rrc\n"
                f"大当たり：+{rate * 10} rrc\n"
                f"終了：全額支払い\n\n"
                f"参加費：{fee} rrc\n\n"
                f"参加者：\n・{member.mention}"
            ),
            color=0xFFD700
        )

        view = SlotJoinView(self, member, vc, rate, fee)
        await interaction.response.send_message(embed=embed, view=view)

    # =========================
    # スピン処理
    # =========================
    async def spin(self, interaction: discord.Interaction, game: SlotGame):
        user = interaction.user

        if user.id != game.current_player():
            return await interaction.response.send_message(
                "❌ あなたの番ではありません。",
                ephemeral=True
            )

        result = random.choice(PROB_TABLE)

        # GIF表示（今回は静的画像想定）
        if result == RESULT_SMALL:
            game.total_pool += game.rate
            text = f"🟡 小当たり！ +{game.rate} rrc"
            game.next_turn()

        elif result == RESULT_BIG:
            game.total_pool += game.rate * 10
            text = f"🔵 大当たり！！ +{game.rate * 10} rrc"
            game.next_turn()

        else:
            # 終了
            await self.finish_game(interaction, game, user)
            return

        await interaction.response.edit_message(
            content=text,
            view=SlotNextView(self, game)
        )

    # =========================
    # 終了処理
    # =========================
    async def finish_game(self, interaction, game: SlotGame, loser: discord.Member):
        total = game.total_pool
        players = game.players

        share = total // (len(players) - 1)

        # 支払い
        await self.bot.db.add_balance(loser.id, -total)
        for uid in players:
            if uid != loser.id:
                await self.bot.db.add_balance(uid, share)

        embed = discord.Embed(
            title="📊 リザルト",
            description=(
                f"総額：{total} rrc\n\n"
                f"全額支払い者：{loser.mention}\n\n"
                "配給：\n" +
                "\n".join(
                    f"<@{uid}>：{share} rrc"
                    for uid in players if uid != loser.id
                )
            ),
            color=0xFF0000
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=SlotContinueView(self, game)
        )

    # =========================
    # /スロットリセット
    # =========================
    @app_commands.command(
        name="スロットリセット",
        description="スロット参加キューをリセット"
    )
    async def slot_reset(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ):
        for game in self.games.values():
            if user.id in game.players:
                game.players.remove(user.id)
                await interaction.response.send_message(
                    f"✅ {user.mention} をキューから解除しました。",
                    ephemeral=True
                )
                return

        await interaction.response.send_message(
            "❌ 該当するゲームがありません。",
            ephemeral=True
        )


# =========================
# View：参加・締め切り
# =========================
class SlotJoinView(discord.ui.View):
    def __init__(self, cog, host, vc, rate, fee):
        super().__init__(timeout=None)
        self.cog = cog
        self.host = host
        self.vc = vc
        self.rate = rate
        self.fee = fee
        self.players = [host.id]

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        self.players.append(user.id)

        embed = interaction.message.embeds[0]
        embed.description += f"\n・{user.mention}"
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="締め切り", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message(
                "❌ 主催者のみ使用できます。",
                ephemeral=True
            )

        game = SlotGame(self.host, self.vc, self.rate, self.fee)
        game.players = self.players.copy()
        random.shuffle(game.players)

        self.cog.games[interaction.message.id] = game

        await interaction.response.edit_message(
            content="☠️ **DEAD OR ALIVE！**\n気合を入れてレバーを叩け！",
            view=SlotSpinView(self.cog, game)
        )


# =========================
# View：スピン
# =========================
class SlotSpinView(discord.ui.View):
    def __init__(self, cog, game):
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
    def __init__(self, cog, game):
        super().__init__(timeout=None)
        self.cog = cog
        self.game = game

    @discord.ui.button(label="次", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=f"次は <@{self.game.current_player()}> の番！",
            view=SlotSpinView(self.cog, self.game)
        )


# =========================
# View：継続 or 終了
# =========================
class SlotContinueView(discord.ui.View):
    def __init__(self, cog, game):
        super().__init__(timeout=None)
        self.cog = cog
        self.game = game
        self.votes = set()

    @discord.ui.button(label="継続", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.votes.add(interaction.user.id)
        if set(self.game.players) == self.votes:
            self.game.total_pool = 0
            self.game.turn_index = 0
            random.shuffle(self.game.players)

            await interaction.message.edit(
                content="🔁 継続！再スタート！",
                view=SlotSpinView(self.cog, self.game)
            )

    @discord.ui.button(label="終了", style=discord.ButtonStyle.danger)
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.games.pop(interaction.message.id, None)
        await interaction.response.edit_message(
            content="🛑 ゲーム終了",
            view=None
        )


async def setup(bot):
    await bot.add_cog(SlotCog(bot))
