import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio


# ============================================
# 🔥 時間切れになったらギャンブルを自動削除
# ============================================
async def delete_when_expired(bot, guild_id, expire_dt):
    """締め切り時間まで待って、自動でギャンブルを削除する"""

    now = datetime.now()
    wait_sec = (expire_dt - now).total_seconds()

    # すでに過ぎている場合は即実行
    if wait_sec <= 0:
        await bot.db.conn.execute("DELETE FROM gamble_current WHERE guild_id=$1", guild_id)
        await bot.db.conn.execute("DELETE FROM gamble_bets WHERE guild_id=$1", guild_id)
        return

    await asyncio.sleep(wait_sec)

    # まだギャンブルが残っていれば削除
    exist = await bot.db.conn.fetchrow(
        "SELECT * FROM gamble_current WHERE guild_id=$1",
        guild_id
    )

    if exist:
        await bot.db.conn.execute("DELETE FROM gamble_current WHERE guild_id=$1", guild_id)
        await bot.db.conn.execute("DELETE FROM gamble_bets WHERE guild_id=$1", guild_id)
        # ここで通知送るなら追加できる（任意）
        # guild = bot.get_guild(int(guild_id))
        # channel = guild.system_channel
        # if channel:
        #     await channel.send("🕒 ギャンブルは締め切りのため自動キャンセルされました。")


class GambleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # DB取得
    async def get_current_gamble(self, guild_id):
        return await self.bot.db.conn.fetchrow(
            "SELECT * FROM gamble_current WHERE guild_id=$1",
            guild_id
        )

    async def clear_gamble(self, guild_id):
        await self.bot.db.conn.execute("DELETE FROM gamble_current WHERE guild_id=$1", guild_id)
        await self.bot.db.conn.execute("DELETE FROM gamble_bets WHERE guild_id=$1", guild_id)

    # ============================================
    # /ギャンブル開始
    # ============================================
    @app_commands.command(
        name="ギャンブル開始",
        description="ギャンブル対戦を開始します。"
    )
    async def start_gamble(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        title: str,
        content: str,
        month: int,
        day: int,
        hour: int,
        minute: int
    ):

        guild = interaction.guild
        guild_id = str(guild.id)
        starter = interaction.user

        # 同時進行不可
        exist = await self.get_current_gamble(guild_id)
        if exist:
            return await interaction.response.send_message(
                "⚠ 現在すでに進行中のギャンブルがあります。",
                ephemeral=True
            )

        # 締め切り日時
        year = datetime.now().year
        expire_dt = datetime(year, month, day, hour, minute)

        # DB登録
        await self.bot.db.conn.execute("""
            INSERT INTO gamble_current (
                guild_id, starter_id, opponent_id,
                title, content, expire_at,
                status, winner
            ) VALUES ($1,$2,$3,$4,$5,$6,'waiting',NULL)
        """, guild_id, str(starter.id), str(opponent.id), title, content, expire_dt)

        # パネル
        embed = discord.Embed(
            title=f"🎮 **{title}**",
            description=f"{content}\n\n🕒 **締め切り：{expire_dt.strftime('%Y/%m/%d %H:%M')}**",
            color=0x3498db
        )

        view = AcceptView(self.bot, guild_id, str(starter.id), str(opponent.id))

        await interaction.response.send_message(embed=embed, view=view)

        # 🔥 時間切れ監視を非同期で起動
        asyncio.create_task(delete_when_expired(self.bot, guild_id, expire_dt))

    # ============================================
    # /ギャンブル終了
    # ============================================
    @app_commands.command(
        name="ギャンブル終了",
        description="進行中ギャンブルを終了し勝敗を決めます。"
    )
    async def end_gamble(self, interaction: discord.Interaction):

        guild_id = str(interaction.guild.id)
        data = await self.get_current_gamble(guild_id)

        if not data:
            return await interaction.response.send_message(
                "⚠ 進行中のギャンブルがありません。",
                ephemeral=True
            )

        if data["status"] not in ["betting", "closed"]:
            return await interaction.response.send_message(
                "⚠ まだ承諾がされていません。",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"🎮 {data['title']}",
            description=data["content"],
            color=0xe67e22
        )

        view = JudgeView(
            self.bot,
            guild_id,
            data["starter_id"],
            data["opponent_id"]
        )

        await interaction.response.send_message(embed=embed, view=view)


# ===========================================================
# 承諾ボタン
# ===========================================================

class AcceptView(discord.ui.View):
    def __init__(self, bot, guild_id, starter_id, opponent_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.starter_id = starter_id
        self.opponent_id = opponent_id

    @discord.ui.button(label="承諾する", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        # 対戦相手限定
        if str(interaction.user.id) != self.opponent_id:
            return await interaction.response.send_message(
                "❌ あなたは対戦相手ではありません。",
                ephemeral=True
            )

        # 承諾
        await self.bot.db.conn.execute(
            "UPDATE gamble_current SET status='betting' WHERE guild_id=$1",
            self.guild_id
        )

        data = await self.bot.db.conn.fetchrow(
            "SELECT * FROM gamble_current WHERE guild_id=$1",
            self.guild_id
        )

        embed = discord.Embed(
            title=f"🎲 **{data['title']}**",
            description=f"{data['content']}\n\n📝 賭けフェーズ開始！",
            color=0x2ecc71
        )

        view = BetView(self.bot, self.guild_id, self.starter_id, self.opponent_id)

        await interaction.response.edit_message(embed=embed, view=view)


# ===========================================================
# 賭けフェーズ
# ===========================================================

class BetView(discord.ui.View):
    def __init__(self, bot, guild_id, starter_id, opponent_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.starter_id = starter_id
        self.opponent_id = opponent_id

        guild = bot.get_guild(int(guild_id))
        starter_user = guild.get_member(int(starter_id))
        opponent_user = guild.get_member(int(opponent_id))

        self.label_A = f"{starter_user.display_name} に賭ける"
        self.label_B = f"{opponent_user.display_name} に賭ける"

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.blurple)
    async def bet_starter(self, interaction, button):
        button.label = self.label_A
        await self.open_bet_modal(interaction, "A")

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.grey)
    async def bet_opponent(self, interaction, button):
        button.label = self.label_B
        await self.open_bet_modal(interaction, "B")

    @discord.ui.button(label="締め切り", style=discord.ButtonStyle.red)
    async def close_bet(self, interaction, button):

        if str(interaction.user.id) != self.starter_id:
            return await interaction.response.send_message(
                "❌ 締め切り操作は開始者のみです。",
                ephemeral=True
            )

        await self.bot.db.conn.execute(
            "UPDATE gamble_current SET status='closed' WHERE guild_id=$1",
            self.guild_id
        )

        for c in self.children:
            c.disabled = True

        embed = discord.Embed(
            title="🔒 賭け締め切り",
            description="これ以上賭けることはできません。",
            color=0xc0392b
        )

        await interaction.response.edit_message(embed=embed, view=self)

    # モーダル
    async def open_bet_modal(self, interaction, side):

        class BetModal(discord.ui.Modal, title="賭け金入力"):
            amount = discord.ui.TextInput(label="賭け金（整数）", required=True)

            async def on_submit(self, modal_interaction):

                try:
                    amt = int(self.amount.value)
                    if amt <= 0:
                        raise ValueError
                except:
                    return await modal_interaction.response.send_message(
                        "❌ 正の整数を入力してください。",
                        ephemeral=True
                    )

                uid = str(modal_interaction.user.id)
                guild_id = str(modal_interaction.guild.id)

                # 残高
                balance = (await interaction.client.db.get_user(uid, guild_id))["balance"]
                if balance < amt:
                    return await modal_interaction.response.send_message(
                        "❌ 残高不足です。",
                        ephemeral=True
                    )

                await interaction.client.db.remove_balance(uid, guild_id, amt)

                await interaction.client.db.conn.execute("""
                    INSERT INTO gamble_bets (guild_id, user_id, side, amount)
                    VALUES ($1,$2,$3,$4)
                """, guild_id, uid, side, amt)

                return await modal_interaction.response.send_message(
                    f"🎫 {amt} を賭けました！",
                    ephemeral=True
                )

        await interaction.response.send_modal(BetModal())


# ===========================================================
# 勝敗判定フェーズ
# ===========================================================

class JudgeView(discord.ui.View):
    def __init__(self, bot, guild_id, starter_id, opponent_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.starter_id = starter_id
        self.opponent_id = opponent_id
        self.votes = {}

        guild = bot.get_guild(int(guild_id))
        starter_user = guild.get_member(int(starter_id))
        opponent_user = guild.get_member(int(opponent_id))

        self.label_A = f"{starter_user.display_name} の勝利"
        self.label_B = f"{opponent_user.display_name} の勝利"

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.green)
    async def win_A(self, interaction, button):
        button.label = self.label_A
        await self.vote(interaction, "A")

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.green)
    async def win_B(self, interaction, button):
        button.label = self.label_B
        await self.vote(interaction, "B")

    async def vote(self, interaction, side):

        if str(interaction.user.id) not in [self.starter_id, self.opponent_id]:
            return await interaction.response.send_message(
                "❌ あなたは判定者ではありません。",
                ephemeral=True
            )

        self.votes[str(interaction.user.id)] = side

        if len(self.votes) == 2:
            vals = list(self.votes.values())
            if vals[0] == vals[1]:
                await self.finish(interaction, vals[0])
                return

        await interaction.response.send_message("投票完了", ephemeral=True)

    async def finish(self, interaction, winner_side):

        await self.bot.db.conn.execute(
            "UPDATE gamble_current SET winner=$1 WHERE guild_id=$2",
            winner_side, self.guild_id
        )

        embed = await self.create_result_embed(interaction)

        await interaction.channel.send(embed=embed)

        await self.bot.db.conn.execute("DELETE FROM gamble_current WHERE guild_id=$1", self.guild_id)
        await self.bot.db.conn.execute("DELETE FROM gamble_bets WHERE guild_id=$1", self.guild_id)

        await interaction.response.send_message("勝負確定！", ephemeral=True)

    async def create_result_embed(self, interaction):

        guild_id = self.guild_id
        db = self.bot.db

        data = await db.conn.fetchrow(
            "SELECT * FROM gamble_current WHERE guild_id=$1",
            guild_id
        )
        bets = await db.conn.fetch(
            "SELECT * FROM gamble_bets WHERE guild_id=$1",
            guild_id
        )

        winner_side = data["winner"]
        starter_id = data["starter_id"]
        opponent_id = data["opponent_id"]

        # 合計
        A_total = sum(b["amount"] for b in bets if b["side"] == "A")
        B_total = sum(b["amount"] for b in bets if b["side"] == "B")

        winner_total = A_total if winner_side == "A" else B_total
        loser_total = B_total if winner_side == "A" else A_total

        # 勝者側
        winner_list = [b for b in bets if b["side"] == winner_side]
        loser_list = [b for b in bets if b["side"] != winner_side]

        pay_dict = {}
        actual_bonus_total = 0

        for b in winner_list:
            uid = b["user_id"]
            bet = b["amount"]
            ratio = bet / winner_total if winner_total > 0 else 0
            bonus = min(int(loser_total * ratio), bet)
            payout = bet + bonus
            pay_dict[uid] = payout
            actual_bonus_total += bonus

        # 敗者側残りを比率返金
        remain = loser_total - actual_bonus_total

        for b in loser_list:
            uid = b["user_id"]
            bet = b["amount"]
            ratio = bet / loser_total if loser_total > 0 else 0
            refund = int(remain * ratio)
            pay_dict[uid] = pay_dict.get(uid, 0) + refund

        # DB反映
        for uid, amount in pay_dict.items():
            await db.add_balance(uid, guild_id, amount)

        # embed
        embed = discord.Embed(
            title=f"🏆 結果：{data['title']}",
            description=data["content"],
            color=0xf1c40f
        )

        winner_user = starter_id if winner_side == "A" else opponent_id
        embed.add_field(name="勝者", value=f"<@{winner_user}>", inline=False)

        lines = [f"<@{uid}>：{amount} spt" for uid, amount in pay_dict.items()]
        embed.add_field(name="最終配当", value="\n".join(lines), inline=False)

        return embed


# ===========================================================
# setup
# ===========================================================
async def setup(bot):
    cog = GambleCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
