import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio


# ============================================
# 🔥 時間切れになったらギャンブルを自動削除
# ============================================
async def delete_when_expired(bot, guild_id: str, expire_dt: datetime):
    """締め切り時間まで待って、自動でギャンブルを削除する"""

    # 期限との差分を計算
    now = datetime.now()
    wait_sec = (expire_dt - now).total_seconds()

    # すでに過ぎている場合は即実行
    if wait_sec <= 0:
        await bot.db.conn.execute(
            "DELETE FROM gamble_current WHERE guild_id=$1",
            guild_id
        )
        await bot.db.conn.execute(
            "DELETE FROM gamble_bets WHERE guild_id=$1",
            guild_id
        )
        return

    # 期限まで待つ
    await asyncio.sleep(wait_sec)

    # まだギャンブルが残っていれば削除
    exist = await bot.db.conn.fetchrow(
        "SELECT * FROM gamble_current WHERE guild_id=$1",
        guild_id
    )

    if exist:
        await bot.db.conn.execute(
            "DELETE FROM gamble_current WHERE guild_id=$1",
            guild_id
        )
        await bot.db.conn.execute(
            "DELETE FROM gamble_bets WHERE guild_id=$1",
            guild_id
        )
        # 必要ならここで通知メッセージを投げてもOK
        # 例）system_channel 等にメッセージ送信など


class GambleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================
    # Cog ロード時：残っているギャンブルに監視タスクを張り直す
    # ============================================
    async def cog_load(self):
        """
        Bot再起動時などに、DBに残っているギャンブルの expire_at を見て
        自動削除タスクを張り直す。
        """
        rows = await self.bot.db.conn.fetch(
            "SELECT guild_id, expire_at FROM gamble_current"
        )

        now = datetime.now()

        for row in rows:
            guild_id = row["guild_id"]
            expire_at = row["expire_at"]  # datetime

            # すでに期限切れなら即削除
            if expire_at <= now:
                await self.clear_gamble(guild_id)
            else:
                # 期限前ならタイマーを張り直し
                asyncio.create_task(
                    delete_when_expired(self.bot, guild_id, expire_at)
                )

    # DB取得
    async def get_current_gamble(self, guild_id: str):
        return await self.bot.db.conn.fetchrow(
            "SELECT * FROM gamble_current WHERE guild_id=$1",
            guild_id
        )

    async def clear_gamble(self, guild_id: str):
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_current WHERE guild_id=$1",
            guild_id
        )
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_bets WHERE guild_id=$1",
            guild_id
        )

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

        # 締め切り日時（同じ年と仮定）
        year = datetime.now().year
        expire_dt = datetime(year, month, day, hour, minute)

        # DB登録
        await self.bot.db.conn.execute(
            """
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

    # ============================================
    # /ギャンブルリセット
    # ============================================
    @app_commands.command(
        name="ギャンブルリセット",
        description="進行中ギャンブルの状態を強制リセットします。（ビューが死んだとき用）"
    )
    async def reset_gamble(self, interaction: discord.Interaction):

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True
            )

        guild_id = str(guild.id)

        # 管理者ロールチェック
        db = self.bot.db
        settings = await db.get_settings()
        admin_roles = settings.get("admin_roles", [])  # ['id', 'id', ...]
        admin_ids = {int(rid) for rid in admin_roles if str(rid).isdigit()}

        has_admin = any(r.id in admin_ids for r in interaction.user.roles)

        if not has_admin:
            return await interaction.response.send_message(
                "❌ ギャンブルをリセットするには管理者ロールが必要です。",
                ephemeral=True
            )

        # 現在の状態確認
        data = await self.get_current_gamble(guild_id)
        if not data:
            return await interaction.response.send_message(
                "✅ 現在このサーバーに進行中のギャンブルはありません。",
                ephemeral=True
            )

        # 状態クリア
        await self.clear_gamble(guild_id)

        await interaction.response.send_message(
            "🧹 このサーバーの進行中ギャンブルをリセットしました。\n"
            "もう一度 `/ギャンブル開始` からやり直せます。",
            ephemeral=True
        )


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

        # ラベルを先に作っておく
        self.label_A = f"{starter_user.display_name} に賭ける"
        self.label_B = f"{opponent_user.display_name} に賭ける"

        # ★ ボタンを取得して書き換える
        self.children[0].label = self.label_A   # bet_starter
        self.children[1].label = self.label_B   # bet_opponent

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.blurple)
    async def bet_starter(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ボタンラベルを更新してからモーダル
        button.label = self.label_A
        await self.open_bet_modal(interaction, "A")

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.grey)
    async def bet_opponent(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = self.label_B
        await self.open_bet_modal(interaction, "B")

    @discord.ui.button(label="締め切り", style=discord.ButtonStyle.red)
    async def close_bet(self, interaction: discord.Interaction, button: discord.ui.Button):

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
    async def open_bet_modal(self, interaction: discord.Interaction, side: str):

        class BetModal(discord.ui.Modal, title="賭け金入力"):
            amount = discord.ui.TextInput(label="賭け金（整数）", required=True)

            async def on_submit(self, modal_interaction: discord.Interaction):

                try:
                    amt = int(self.amount.value)
                    if amt <= 0:
                        raise ValueError
                except Exception:
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

                await interaction.client.db.conn.execute(
                    """
                    INSERT INTO gamble_bets (guild_id, user_id, side, amount)
                    VALUES ($1,$2,$3,$4)
                    """,
                    guild_id,
                    uid,
                    side,
                    amt
                )

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

        # ラベル準備
        self.label_A = f"{starter_user.display_name} の勝利"
        self.label_B = f"{opponent_user.display_name} の勝利"

        # ★ ボタンの初期ラベルを設定
        self.children[0].label = self.label_A   # win_A
        self.children[1].label = self.label_B   # win_B

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.green)
    async def win_A(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = self.label_A
        await self.vote(interaction, "A")

    @discord.ui.button(label="loading...", style=discord.ButtonStyle.green)
    async def win_B(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = self.label_B
        await self.vote(interaction, "B")

    async def vote(self, interaction: discord.Interaction, side: str):

        if str(interaction.user.id) not in [self.starter_id, self.opponent_id]:
            return await interaction.response.send_message(
                "❌ あなたは判定者ではありません。",
                ephemeral=True
            )

        self.votes[str(interaction.user.id)] = side

        # 両者が投票したら確定
        if len(self.votes) == 2:
            vals = list(self.votes.values())
            if vals[0] == vals[1]:
                await self.finish(interaction, vals[0])
                return

        await interaction.response.send_message("投票完了", ephemeral=True)

    async def finish(self, interaction: discord.Interaction, winner_side: str):

        await self.bot.db.conn.execute(
            "UPDATE gamble_current SET winner=$1 WHERE guild_id=$2",
            winner_side,
            self.guild_id
        )

        embed = await self.create_result_embed(interaction)

        await interaction.channel.send(embed=embed)

        # DBクリーンアップ
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_current WHERE guild_id=$1",
            self.guild_id
        )
        await self.bot.db.conn.execute(
            "DELETE FROM gamble_bets WHERE guild_id=$1",
            self.guild_id
        )

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

    # グループ分け
    winner_list = [b for b in bets if b["side"] == winner_side]
    loser_list = [b for b in bets if b["side"] != winner_side]

    pay_dict = {}
    actual_bonus_total = 0

    # -----------------------------
    # 🎯 勝者側：当選配当を計算
    # -----------------------------
    for b in winner_list:
        uid = b["user_id"]
        bet = b["amount"]
        ratio = bet / winner_total if winner_total > 0 else 0
        bonus = min(int(loser_total * ratio), bet)
        payout = bet + bonus

        pay_dict[uid] = {
            "bet": bet,
            "payout": payout,
            "refund": 0,
            "side": "winner"
        }
        actual_bonus_total += bonus

    # -----------------------------
    # 💸 敗者側：払い戻しを計算
    # -----------------------------
    remain = loser_total - actual_bonus_total

    for b in loser_list:
        uid = b["user_id"]
        bet = b["amount"]
        ratio = bet / loser_total if loser_total > 0 else 0
        refund = int(remain * ratio)

        pay_dict[uid] = {
            "bet": bet,
            "payout": 0,
            "refund": refund,
            "side": "loser"
        }

    # DB反映
    for uid, info in pay_dict.items():
        await db.add_balance(uid, guild_id, info["payout"] + info["refund"])

    # -----------------------------
    # 📌 Embed 構築
    # -----------------------------
    embed = discord.Embed(
        title=f"🏆 結果：{data['title']}",
        description=data["content"],
        color=0xf1c40f
    )

    # 勝者
    winner_user = starter_id if winner_side == "A" else opponent_id
    embed.add_field(name="🏆 勝者", value=f"<@{winner_user}>", inline=False)

    # -------- 当選配当（winner） --------
    winner_lines = []
    for uid, info in pay_dict.items():
        if info["side"] == "winner":
            winner_lines.append(
                f"<@{uid}>\n"
                f"　賭け額：{info['bet']} spt\n"
                f"　当選配当：{info['payout']} spt"
            )

    if winner_lines:
        embed.add_field(
            name="💰 当選配当",
            value="\n".join(winner_lines),
            inline=False
        )

    # -------- 払い戻し（loser） --------
    loser_lines = []
    for uid, info in pay_dict.items():
        if info["side"] == "loser" and info["refund"] > 0:
            loser_lines.append(
                f"<@{uid}>\n"
                f"　賭け額：{info['bet']} spt\n"
                f"　払い戻し：{info['refund']} spt"
            )

    if loser_lines:
        embed.add_field(
            name="💸 払い戻し",
            value="\n".join(loser_lines),
            inline=False
        )

    return embed



# ===========================================================
# setup
# ===========================================================
async def setup(bot: commands.Bot):
    cog = GambleCog(bot)
    await bot.add_cog(cog)

    # 既存設計に合わせてギルド別コマンド登録
    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))


