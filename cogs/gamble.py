# cogs/gamble.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta


class GambleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # ================ 内部ヘルパー ================

    async def get_current_gamble(self, guild_id):
        """進行中ギャンブルを取得"""
        return await self.bot.db.conn.fetchrow(
            "SELECT * FROM gamble_current WHERE guild_id=$1",
            guild_id
        )

    async def clear_gamble(self, guild_id):
        """ギャンブル終了後にリセット"""
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_current WHERE guild_id=$1",
            guild_id
        )
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_bets WHERE guild_id=$1",
            guild_id
        )

    # ================ ギャンブル開始 ================
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

        # ギャンブル登録
        await self.bot.db.conn.execute("""
            INSERT INTO gamble_current (
                guild_id, starter_id, opponent_id,
                title, content, expire_at,
                status, winner
            ) VALUES ($1,$2,$3,$4,$5,$6,'waiting',NULL)
        """,
        guild_id,
        str(starter.id),
        str(opponent.id),
        title,
        content,
        expire_dt
        )

        # 承諾パネル
        embed = discord.Embed(
            title=f"🎮 **{title}**",
            description=f"{content}\n\n🕒 **締め切り：{expire_dt.strftime('%Y/%m/%d %H:%M')}**",
            color=0x3498db
        )

        view = AcceptView(
            bot=self.bot,
            guild_id=guild_id,
            starter_id=str(starter.id),
            opponent_id=str(opponent.id)
        )

        await interaction.response.send_message(embed=embed, view=view)


    # ================ ギャンブル終了 ================
    @app_commands.command(
        name="ギャンブル終了",
        description="進行中ギャンブルを終了し勝敗を決めます。"
    )
    async def end_gamble(self, interaction: discord.Interaction):

        guild = interaction.guild
        guild_id = str(guild.id)

        data = await self.get_current_gamble(guild_id)
        if not data:
            return await interaction.response.send_message(
                "⚠ 進行中のギャンブルがありません。",
                ephemeral=True
            )

        if data["status"] != "betting" and data["status"] != "closed":
            return await interaction.response.send_message(
                "⚠ まだ承諾が行われていません。",
                ephemeral=True
            )

        # 勝敗パネル表示
        embed = discord.Embed(
            title=f"🎮 {data['title']}",
            description=data["content"],
            color=0xe67e22
        )

        view = JudgeView(
            bot=self.bot,
            guild_id=guild_id,
            starter_id=data["starter_id"],
            opponent_id=data["opponent_id"]
        )

        await interaction.response.send_message(embed=embed, view=view)


# ===========================================================
# -------------------- 承諾ボタン ---------------------------
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

        # 対戦相手だけ押せる
        if str(interaction.user.id) != self.opponent_id:
            return await interaction.response.send_message(
                "❌ あなたは対戦相手ではありません。",
                ephemeral=True
            )

        # 状態遷移
        await self.bot.db.conn.execute(
            "UPDATE gamble_current SET status='betting' WHERE guild_id=$1",
            self.guild_id
        )

        # 賭けフェーズUIを表示
        data = await self.bot.db.conn.fetchrow(
            "SELECT * FROM gamble_current WHERE guild_id=$1",
            self.guild_id
        )

        embed = discord.Embed(
            title=f"🎲 **{data['title']}**",
            description=f"{data['content']}\n\n📝 賭けフェーズ開始！",
            color=0x2ecc71
        )

        view = BetView(
            bot=self.bot,
            guild_id=self.guild_id,
            starter_id=self.starter_id,
            opponent_id=self.opponent_id
        )

        await interaction.response.edit_message(embed=embed, view=view)


# ===========================================================
# --------------------- 賭けフェーズ -------------------------
# ===========================================================

class BetView(discord.ui.View):
    def __init__(self, bot, guild_id, starter_id, opponent_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.starter_id = starter_id
        self.opponent_id = opponent_id

    @discord.ui.button(label="開始者に賭ける", style=discord.ButtonStyle.blurple)
    async def bet_starter(self, interaction: discord.Interaction, button):
        await self.open_bet_modal(interaction, side="A")

    @discord.ui.button(label="対戦者に賭ける", style=discord.ButtonStyle.grey)
    async def bet_opponent(self, interaction: discord.Interaction, button):
        await self.open_bet_modal(interaction, side="B")

    @discord.ui.button(label="締め切り", style=discord.ButtonStyle.red)
    async def close_bet(self, interaction: discord.Interaction, button):

        # 開始者だけ押せる
        if str(interaction.user.id) != self.starter_id:
            return await interaction.response.send_message(
                "❌ 締め切りを行えるのは開始者のみです。",
                ephemeral=True
            )

        # 締め切り
        await self.bot.db.conn.execute(
            "UPDATE gamble_current SET status='closed' WHERE guild_id=$1",
            self.guild_id
        )

        # UI無効化
        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="🔒 賭け締め切り",
            description="これ以上賭けることはできません。",
            color=0xc0392b
        )

        await interaction.response.edit_message(embed=embed, view=self)

    # ---------------- 賭け金モーダル ----------------
    async def open_bet_modal(self, interaction, side):

        class BetModal(discord.ui.Modal, title="賭け金入力"):
            amount = discord.ui.TextInput(label="賭け金（整数）", placeholder="1000", required=True)

            async def on_submit(self, modal_interaction):

                # 金額チェック
                try:
                    amt = int(self.amount.value)
                    if amt <= 0:
                        raise ValueError
                except:
                    return await modal_interaction.response.send_message(
                        "❌ 0以上の整数を入力してください。",
                        ephemeral=True
                    )

                uid = str(modal_interaction.user.id)
                guild_id = str(modal_interaction.guild.id)

                # 残高確認
                balance = (await interaction.client.db.get_user(uid, guild_id))["balance"]
                if balance < amt:
                    return await modal_interaction.response.send_message(
                        "❌ 残高不足です。",
                        ephemeral=True
                    )

                # 減算
                await interaction.client.db.remove_balance(uid, guild_id, amt)

                # DB登録
                await interaction.client.db.conn.execute("""
                    INSERT INTO gamble_bets (guild_id, user_id, side, amount)
                    VALUES ($1,$2,$3,$4)
                """,
                guild_id, uid, side, amt
                )

                await modal_interaction.response.send_message(
                    f"🎫 {amt} を賭けました！",
                    ephemeral=True
                )

        await interaction.response.send_modal(BetModal())


# ===========================================================
# ----------------------- 勝敗判定 ---------------------------
# ===========================================================

class JudgeView(discord.ui.View):
    def __init__(self, bot, guild_id, starter_id, opponent_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.starter_id = starter_id
        self.opponent_id = opponent_id
        self.votes = {}  # {user_id: 'A' or 'B'}

    @discord.ui.button(label="開始者の勝利", style=discord.ButtonStyle.green)
    async def win_A(self, interaction, button):
        await self.vote(interaction, "A")

    @discord.ui.button(label="対戦者の勝利", style=discord.ButtonStyle.green)
    async def win_B(self, interaction, button):
        await self.vote(interaction, "B")

    async def vote(self, interaction, side):

        # 2人だけ押せる
        if str(interaction.user.id) not in [self.starter_id, self.opponent_id]:
            return await interaction.response.send_message(
                "❌ あなたは判定者ではありません。",
                ephemeral=True
            )

        self.votes[str(interaction.user.id)] = side

        # 両者一致チェック
        if len(self.votes) == 2:
            vals = list(self.votes.values())
            if vals[0] == vals[1]:
                # 勝者決定
                await self.finish(interaction, vals[0])
                return

        await interaction.response.send_message("投票を受け付けました。", ephemeral=True)

    # ---------------- 完了処理 ----------------
    async def finish(self, interaction, winner):

        # 勝者登録
        await self.bot.db.conn.execute(
            "UPDATE gamble_current SET winner=$1 WHERE guild_id=$2",
            winner,
            self.guild_id
        )

        # リザルト生成
        embed, view = await self.create_result_embed(interaction)

        # リザルト送信
        await interaction.channel.send(embed=embed)

        # クリア
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_current WHERE guild_id=$1",
            self.guild_id
        )
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_bets WHERE guild_id=$1",
            self.guild_id
        )

        await interaction.response.send_message("勝負が確定しました！", ephemeral=True)

    # ---------------- リザルト生成 ----------------
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

        # A: 開始者 / B: 対戦者
        starter_id = data["starter_id"]
        opponent_id = data["opponent_id"]

        # 集計
        A_total = sum(b["amount"] for b in bets if b["side"] == "A")
        B_total = sum(b["amount"] for b in bets if b["side"] == "B")

        winner_total = A_total if winner_side == "A" else B_total
        loser_total  = B_total if winner_side == "A" else A_total

        # 勝者側配当（上限はbet）
        winner_list = [b for b in bets if b["side"] == winner_side]
        loser_list  = [b for b in bets if b["side"] != winner_side]

        # 勝者側配当
        pay_dict = {}  # {user_id: payout}
        actual_bonus_total = 0

        for b in winner_list:
            uid = b["user_id"]
            bet = b["amount"]

            # 割合計算
            ratio = bet / winner_total if winner_total > 0 else 0
            bonus = int(loser_total * ratio)

            # 上限は bet
            bonus = min(bonus, bet)
            payout = bet + bonus

            pay_dict[uid] = payout
            actual_bonus_total += bonus

        # 残額
        remain = loser_total - actual_bonus_total

        # 敗者側配当
        for b in loser_list:
            uid = b["user_id"]
            bet = b["amount"]

            ratio = bet / loser_total if loser_total > 0 else 0
            refund = int(remain * ratio)

            if uid in pay_dict:
                pay_dict[uid] += refund
            else:
                pay_dict[uid] = refund

        # 残高反映
        for uid, amount in pay_dict.items():
            await db.add_balance(uid, guild_id, amount)

        # リザルトembed
        embed = discord.Embed(
            title=f"🏆 結果：{data['title']}",
            description=data["content"],
            color=0xf1c40f
        )

        # 勝者表示
        winner_user = starter_id if winner_side == "A" else opponent_id
        embed.add_field(
            name="勝者",
            value=f"<@{winner_user}>",
            inline=False
        )

        # 賭け一覧
        lines = []
        for uid, amount in pay_dict.items():
            lines.append(f"<@{uid}>： {amount} spt")

        embed.add_field(
            name="最終配当",
            value="\n".join(lines),
            inline=False
        )

        return embed, None


# ===========================================================
# setup
# ===========================================================

async def setup(bot):
    await bot.add_cog(GambleCog(bot))
