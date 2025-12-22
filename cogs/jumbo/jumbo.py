# cogs/jumbo/jumbo.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView


class NumberListView(discord.ui.View):
    def __init__(self, user: discord.User, numbers: list[str], per_page: int = 20):
        super().__init__(timeout=180)
        self.user = user
        self.numbers = numbers
        self.per_page = per_page
        self.page = 0

    def get_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_numbers = self.numbers[start:end]

        embed = discord.Embed(
            title="🎟 所持宝くじ番号一覧",
            color=0x3498DB
        )

        if page_numbers:
            embed.description = "\n".join(f"`{n}`" for n in page_numbers)
        else:
            embed.description = "該当する番号はありません。"

        total_pages = (len(self.numbers) - 1) // self.per_page + 1
        embed.set_footer(text=f"{self.page + 1} / {total_pages} ページ")

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ この操作はコマンド実行者のみ可能です。",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="⬅ 前へ", style=discord.ButtonStyle.gray)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="次へ ➡", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_page = (len(self.numbers) - 1) // self.per_page
        if self.page < max_page:
            self.page += 1
        await interaction.response.edit_message(embed=self.get_embed(), view=self)



def count_match_digits(winning: str, target: str) -> int:
    return sum(1 for w, t in zip(winning, target) if w == t)


def match_to_rank(match_count: int) -> int | None:
    if match_count == 6:
        return 1
    if match_count == 5:
        return 2
    if match_count == 4:
        return 3
    if match_count == 3:
        return 4
    if match_count == 2:
        return 5
    return None


def get_prize_by_rank(config, rank: int) -> int:
    return {
        1: config["prize_1"],
        2: config["prize_2"],
        3: config["prize_3"],
        4: config["prize_4"],
        5: config["prize_5"],
    }.get(rank, 0)


def judge_number(config, winning_number: str, target_number: str):
    match_count = count_match_digits(winning_number, target_number)
    rank = match_to_rank(match_count)

    if not rank:
        return None

    prize = get_prize_by_rank(config, rank)

    return {
        "rank": rank,
        "match_count": match_count,
        "prize": prize
    }



class JumboCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)
        bot.loop.create_task(self.jumbo_db.init_tables())

    # ------------------------------------------------------
    # 内部：管理者ロール判定（AdminCog と統一）
    # ------------------------------------------------------
    async def is_admin(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        return any(
            str(role.id) in admin_roles
            for role in interaction.user.roles
        )

    # ------------------------------------------------------
    # /年末ジャンボ開催
    # ------------------------------------------------------
    @app_commands.command(
        name="年末ジャンボ開催",
        description="年末ジャンボを開始し、購入パネルを生成します（管理者専用）"
    )
    @app_commands.describe(
        title="イベントタイトル",
        description="説明文",
        deadline="締切日（例：12-31 のみ）"
    )
    async def jumbo_start(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        deadline: str  # ← 例： "12-31"
    ):

        # 管理者チェック
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        # 今年の年を自動取得
        current_year = datetime.now().year

        # 期限パース（月-日 のみ）
        try:
            # "12-31" → datetime(current_year, 12, 31, 23, 59)
            month, day = map(int, deadline.split("-"))
            deadline_dt = datetime(current_year, month, day, 23, 59)
        except Exception:
            return await interaction.response.send_message(
                "❌ 期限形式は `MM-DD`（例：12-31）で入力してください。",
                ephemeral=True
            )

        # DBには naive datetime のまま保存
        await self.jumbo_db.set_config(guild_id, title, description, deadline_dt)

        # Discord表示用にUTCタイムスタンプへ変換
        ts = int(deadline_dt.replace(tzinfo=timezone.utc).timestamp())

        # 日本語曜日
        week = ["月", "火", "水", "木", "金", "土", "日"]
        w = week[deadline_dt.weekday()]

        deadline_str = (
            f"{deadline_dt.year}年"
            f"{deadline_dt.month}月"
            f"{deadline_dt.day}日"
            f"（{w}）23:59 締切"
        )

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=(
                f"{description}\n\n"
                f"**購入期限：{deadline_str}**\n"
                f"1口 = 1,000 rrc\n"
            ),
            color=0xF1C40F
        )


        view = JumboBuyView(self.bot, self.jumbo_db, guild_id)

        await interaction.response.send_message(
            f"🎫 **年末ジャンボを開始しました！**",
            ephemeral=True
        )

        await interaction.followup.send(embed=embed, view=view)

# ------------------------------------------------------
# /年末ジャンボ当選者発表
# ------------------------------------------------------
@app_commands.command(
    name="年末ジャンボ当選者発表",
    description="当選番号を元に年末ジャンボの当選者を発表します（管理者専用）"
)
async def jumbo_announce(self, interaction: discord.Interaction):

    # ★ 必ず defer
    await interaction.response.defer(ephemeral=True)

    # 管理者チェック
    if not await self.is_admin(interaction):
        return await interaction.followup.send(
            "❌ 管理者ロールが必要です。",
            ephemeral=True
        )

    guild_id = str(interaction.guild.id)

    # 開催設定取得
    config = await self.jumbo_db.get_config(guild_id)
    if not config:
        return await interaction.followup.send(
            "❌ 年末ジャンボが開催されていません。",
            ephemeral=True
        )

    if not config["winning_number"]:
        return await interaction.followup.send(
            "❌ 当選番号がまだ設定されていません。",
            ephemeral=True
        )

    winning_number = config["winning_number"]

    # 全購入番号取得
    entries = await self.jumbo_db.get_all_entries(guild_id)
    if not entries:
        return await interaction.followup.send(
            "⚠ 購入者がいません。",
            ephemeral=True
        )

    # 念のため当選履歴クリア
    await self.jumbo_db.clear_winners(guild_id)

    # 等賞ごとにまとめる
    results = {
        1: [],
        2: [],
        3: [],
        4: [],
        5: [],
    }

    # 判定処理
    for entry in entries:
        number = entry["number"]
        user_id = entry["user_id"]

        result = judge_number(config, winning_number, number)
        if not result:
            continue

        rank = result["rank"]
        match_count = result["match_count"]
        prize = result["prize"]

        # DB保存
        await self.jumbo_db.set_winner(
            guild_id=guild_id,
            rank=rank,
            number=number,
            user_id=user_id,
            match_count=match_count,
            prize=prize
        )

        results[rank].append({
            "user_id": user_id,
            "number": number
        })

    # ===========================
    # 発表Embed
    # ===========================
    embed = discord.Embed(
        title="🎉 当選番号発表！",
        color=0xF1C40F
    )

    embed.add_field(
        name="当選番号",
        value=f"**{winning_number}**",
        inline=False
    )

    for rank in [1, 2, 3, 4, 5]:
        prize = get_prize_by_rank(config, rank)
        winners = results[rank]

        if not winners:
            value = "いませんでした。"
        else:
            value = "\n".join(
                f"<@{w['user_id']}>　当選番号:`{w['number']}`"
                for w in winners
            )

        embed.add_field(
            name=f"第{rank}等　{prize:,} rrc",
            value=value,
            inline=False
        )

    await interaction.followup.send(embed=embed)



    # ------------------------------------------------------
    # /ジャンボ履歴リセット
    # ------------------------------------------------------
    @app_commands.command(
        name="ジャンボ履歴リセット",
        description="ジャンボの番号・設定・当選履歴をリセットします（管理者専用）"
    )
    async def jumbo_reset(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.jumbo_db.clear_entries(guild_id)
        await self.jumbo_db.clear_winners(guild_id)
        await self.jumbo_db.reset_config(guild_id)

        await interaction.response.send_message(
            "🧹 **ジャンボ履歴をリセットしました！**\n再度開催が可能です。",
            ephemeral=True
        )



# ------------------------------------------------------
# /年末ジャンボ設定
# ------------------------------------------------------
@app_commands.command(
    name="年末ジャンボ設定",
    description="当選番号と各等賞の賞金を設定します（管理者専用）"
)
@app_commands.describe(
    winning_number="当選番号（6桁）",
    prize_1="1等の賞金",
    prize_2="2等の賞金",
    prize_3="3等の賞金",
    prize_4="4等の賞金",
    prize_5="5等の賞金",
)
async def jumbo_set_prize(
    self,
    interaction: discord.Interaction,
    winning_number: str,
    prize_1: int,
    prize_2: int,
    prize_3: int,
    prize_4: int,
    prize_5: int,
):
    # ★ まず defer
    await interaction.response.defer(ephemeral=True)

    # 管理者チェック
    if not await self.is_admin(interaction):
        return await interaction.followup.send(
            "❌ 管理者ロールが必要です。",
            ephemeral=True
        )

    guild_id = str(interaction.guild.id)

    # 開催チェック
    config = await self.jumbo_db.get_config(guild_id)
    if not config:
        return await interaction.followup.send(
            "❌ 年末ジャンボが開催されていません。",
            ephemeral=True
        )

    # 当選番号チェック
    if not (winning_number.isdigit() and len(winning_number) == 6):
        return await interaction.followup.send(
            "❌ 当選番号は6桁の数字で入力してください。",
            ephemeral=True
        )

    # 保存
    await self.jumbo_db.set_prize_config(
        guild_id,
        winning_number,
        prize_1,
        prize_2,
        prize_3,
        prize_4,
        prize_5
    )

    # 確認用Embed
    embed = discord.Embed(
        title="🎯 年末ジャンボ 当選番号・賞金設定完了",
        color=0xF1C40F
    )
    embed.add_field(name="当選番号", value=f"**{winning_number}**", inline=False)
    embed.add_field(name="第1等", value=f"{prize_1:,} rrc", inline=False)
    embed.add_field(name="第2等", value=f"{prize_2:,} rrc", inline=False)
    embed.add_field(name="第3等", value=f"{prize_3:,} rrc", inline=False)
    embed.add_field(name="第4等", value=f"{prize_4:,} rrc", inline=False)
    embed.add_field(name="第5等", value=f"{prize_5:,} rrc", inline=False)

    await interaction.followup.send(embed=embed)


    # ------------------------------------------------------
    # /年末ジャンボ当選者賞金付与
    # ------------------------------------------------------
    @app_commands.command(
        name="年末ジャンボ当選者賞金付与",
        description="年末ジャンボの当選者へ賞金を付与します（管理者専用・一度のみ）"
    )
    async def jumbo_pay_prizes(self, interaction: discord.Interaction):

        # 管理者チェック
        if not await self.is_admin(interaction):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)

        # 設定取得
        config = await self.jumbo_db.get_config(guild_id)
        if not config:
            return await interaction.response.send_message(
                "❌ 年末ジャンボが開催されていません。",
                ephemeral=True
            )

        if config["prize_paid"]:
            return await interaction.response.send_message(
                "⚠️ すでに賞金は付与されています。",
                ephemeral=True
            )

        # 当選結果取得
        winners = await self.jumbo_db.get_all_winners(guild_id)
        if not winners:
            return await interaction.response.send_message(
                "⚠️ 当選者が存在しません。",
                ephemeral=True
            )

        # ユーザーごとに合算
        payout_map: dict[str, int] = {}

        for w in winners:
            user_id = w["user_id"]
            prize = w["prize"] or 0

            payout_map[user_id] = payout_map.get(user_id, 0) + prize

        # 実際に付与
        for user_id, total in payout_map.items():
            if total > 0:
                await self.bot.db.add_balance(user_id, guild_id, total)

        # 付与済みフラグON
        await self.jumbo_db.db.conn.execute("""
            UPDATE jumbo_config
            SET prize_paid = TRUE
            WHERE guild_id = $1
        """, guild_id)

        # 結果表示
        embed = discord.Embed(
            title="💰 年末ジャンボ 賞金付与完了",
            color=0x2ECC71
        )

        for user_id, total in payout_map.items():
            embed.add_field(
                name=f"<@{user_id}>",
                value=f"{total:,} rrc",
                inline=False
            )

        await interaction.response.send_message(embed=embed)


    # ------------------------------------------------------
    # /所持宝くじ番号確認
    # ------------------------------------------------------
    @app_commands.command(
        name="所持宝くじ番号確認",
        description="自分が所持している宝くじ番号を確認します"
    )
    @app_commands.describe(
        search="検索したい数字（1〜6桁・前方/後方一致）"
    )
    async def jumbo_my_numbers(
        self,
        interaction: discord.Interaction,
        search: str | None = None
    ):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        rows = await self.jumbo_db.get_user_numbers(guild_id, user_id)
        numbers = [r["number"] for r in rows]

        if not numbers:
            return await interaction.response.send_message(
                "🎟 まだ宝くじ番号を持っていません。",
                ephemeral=True
            )

        # 検索フィルタ
        if search:
            if not search.isdigit() or not (1 <= len(search) <= 6):
                return await interaction.response.send_message(
                    "❌ 検索は1〜6桁の数字で入力してください。",
                    ephemeral=True
                )

            numbers = [
                n for n in numbers
                if n.startswith(search) or n.endswith(search)
            ]

        if not numbers:
            return await interaction.response.send_message(
                "🔍 該当する番号は見つかりませんでした。",
                ephemeral=True
            )

        view = NumberListView(interaction.user, numbers)

        await interaction.response.send_message(
            embed=view.get_embed(),
            view=view,
            ephemeral=True
        )


# ======================================================
# setup
# ======================================================

async def setup(bot):
    cog = JumboCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))


















