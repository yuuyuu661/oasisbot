# cogs/jumbo/jumbo.py
from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime

from .jumbo_db import JumboDB
from .jumbo_purchase import JumboBuyView



# =====================================================
# 所持番号一覧 View
# =====================================================
class NumberListView(discord.ui.View):
    def __init__(self, user: discord.User, numbers: list[str]):
        super().__init__(timeout=180)
        self.user = user
        self.numbers = numbers
        self.page = 0
        self.per_page = 20

    def make_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_numbers = self.numbers[start:end]

        embed = discord.Embed(
            title="🎟 所持宝くじ番号一覧",
            color=0x3498DB
        )
        embed.description = "\n".join(f"`{n}`" for n in page_numbers) or "該当なし"
        total_pages = (len(self.numbers) - 1) // self.per_page + 1
        embed.set_footer(text=f"{self.page + 1} / {total_pages} ページ")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @discord.ui.button(label="⬅ 前へ")
    async def prev(self, interaction: discord.Interaction, _):
        self.page = max(0, self.page - 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="次へ ➡")
    async def next(self, interaction: discord.Interaction, _):
        max_page = (len(self.numbers) - 1) // self.per_page
        self.page = min(max_page, self.page + 1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


# =====================================================
# 判定ロジック（スライド一致）
# =====================================================
def rough_hit(winning: str, number: str, match_len: int) -> bool:
    """
    フェーズ1：連続 match_len 桁が含まれているか
    """
    for i in range(0, 6 - match_len + 1):
        if winning[i:i + match_len] in number:
            return True
    return False

def strict_hit(winning: str, number: str, match_len: int) -> bool:
    """
    フェーズ2：同じ位置で連続 match_len 桁が完全一致
    """
    for start in range(0, 6 - match_len + 1):
        for offset in range(match_len):
            if winning[start + offset] != number[start + offset]:
                break
        else:
            return True
    return False

# =====================================================
# 当選判定
# =====================================================

def calc_jumbo_results(winning: str, entries: list[dict]):
    RANK_RULES = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2}
    PRIZES = {1: 10_000_000, 2: 5_000_000, 3: 1_000_000, 4: 500_000, 5: 50_000}

    results: dict[int, list[dict]] = {r: [] for r in range(1, 6)}
    used_numbers: set[str] = set()

    for rank, match_len in RANK_RULES.items():
        candidates = []

        for e in entries:
            number = e["number"]
            if number in used_numbers:
                continue
            if rough_hit(winning, number, match_len):
                candidates.append(e)

        for e in candidates:
            number = e["number"]
            if strict_hit(winning, number, match_len):
                used_numbers.add(number)
                results[rank].append({
                    "user_id": e["user_id"],
                    "number": number,
                    "prize": PRIZES[rank],
                })

    return results


# =====================================================
# Jumbo Cog
# =====================================================
class JumboCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.jumbo_db = JumboDB(bot)

    # ★DB初期化
    @commands.Cog.listener()
    async def on_ready(self):
        await self.jumbo_db.init_tables()
        print("[JUMBO] DB tables ready")
        # ★ 10秒更新ループを起動（多重起動防止）
        if not self.panel_updater.is_running():
            self.panel_updater.start()
            print("[JUMBO] panel_updater started")

    # -------------------------------------------------
    # 管理者判定
    # -------------------------------------------------
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        return any(str(r.id) in admin_roles for r in interaction.user.roles)

    # -------------------------------------------------
    # /年末ジャンボ開催
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ開催")
    async def jumbo_start(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        deadline: str,
    ):
        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用", ephemeral=True)

        try:
            year, month, day = map(int, deadline.split("-"))
            deadline_dt = datetime(year, month, day, 23, 59)
        except Exception:
                return await interaction.response.send_message(
                    "❌ 期限は YYYY-MM-DD（例: 2025-12-31）",
                    ephemeral=True
                )

        guild_id = str(interaction.guild.id)
        await self.jumbo_db.set_config(guild_id, title, description, deadline_dt)

        issued = await self.jumbo_db.count_entries(guild_id)
        remaining = 999_999 - issued

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=(
                f"{description}\n\n"
                f"締切：{deadline_dt.strftime('%Y/%m/%d')}\n"
                f"1口 = 1,000 rrc"
            ),
            color=0xF1C40F
        )

        embed.add_field(
            name="🎫 宝くじ残り枚数",
            value=f"{remaining:,} 枚",
            inline=False
        )

        view = JumboBuyView(self.bot, self.jumbo_db, guild_id)

        await interaction.response.send_message("🎫 ジャンボを開始しました", ephemeral=True)
        panel_msg = await interaction.followup.send(embed=embed, view=view)

        print(
            "[JUMBO] panel sent",
            "guild=", guild_id,
            "channel=", panel_msg.channel.id,
            "message=", panel_msg.id
        )
        # ★ パネル情報をDBに保存
        print("[JUMBO] saving panel message to DB")
        
        await self.jumbo_db.set_panel_message(
            guild_id=guild_id,
            channel_id=str(panel_msg.channel.id),
            message_id=str(panel_msg.id),
        )
        print("[JUMBO] panel message saved")


    # -------------------------------------------------
    # /年末ジャンボ当選者発表（ページ化対応版）
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ当選者発表")
    async def jumbo_announce(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            if not await self.is_admin(interaction):
                return await interaction.followup.send("❌ 管理者専用")

            guild_id = str(interaction.guild.id)

            # --- 当選番号取得 ---
            config = await self.jumbo_db.get_config(guild_id)
            if not config or not config["winning_number"]:
                return await interaction.followup.send("❌ 当選番号が未設定です")

            winning = config["winning_number"]

            # --- 購入番号取得 ---
            entries = await self.jumbo_db.get_all_entries(guild_id)
            if not entries:
                return await interaction.followup.send("⚠ 購入者がいません")

            # --- 判定（共通関数） ---
            results = calc_jumbo_results(winning, entries)

            PRIZES = {1: 10_000_000, 2: 5_000_000, 3: 1_000_000, 4: 500_000, 5: 50_000}

            def split_lines(lines, max_chars=900):
                pages, buf = [], ""
                for line in lines:
                    if len(buf) + len(line) + 1 > max_chars:
                        pages.append(buf)
                        buf = line
                    else:
                        buf += "\n" + line if buf else line
                if buf:
                    pages.append(buf)
                return pages

            embeds: list[discord.Embed] = []

            for rank in range(1, 6):
                prize = PRIZES[rank]
                winners = results[rank]

                lines = [f"<@{w['user_id']}> `{w['number']}`" for w in winners] if winners else ["いませんでした。"]
                pages = split_lines(lines)

                for i, page_text in enumerate(pages):
                    embed = discord.Embed(title="🎉 年末ジャンボ 当選者発表", color=0xF1C40F)
                    embed.add_field(name="🎯 当選番号", value=f"**{winning}**", inline=False)
                    embed.add_field(name=f"第{rank}等（{prize:,} rrc）", value=page_text, inline=False)
                    embed.set_footer(text=f"第{rank}等 {i + 1} / {len(pages)}")
                    embeds.append(embed)

            if not embeds:
                return await interaction.followup.send("⚠ 表示できる結果がありません")

            class ResultPageView(discord.ui.View):
                def __init__(self, user: discord.User, embeds: list[discord.Embed]):
                    super().__init__(timeout=300)
                    self.user = user
                    self.embeds = embeds
                    self.page = 0

                async def interaction_check(self, i: discord.Interaction) -> bool:
                    return i.user.id == self.user.id

                @discord.ui.button(label="◀ 前へ")
                async def prev(self, i: discord.Interaction, _):
                    self.page = max(0, self.page - 1)
                    await i.response.edit_message(embed=self.embeds[self.page], view=self)

                @discord.ui.button(label="次へ ▶")
                async def next(self, i: discord.Interaction, _):
                    self.page = min(len(self.embeds) - 1, self.page + 1)
                    await i.response.edit_message(embed=self.embeds[self.page], view=self)

            await interaction.followup.send(embed=embeds[0], view=ResultPageView(interaction.user, embeds))

        except Exception as e:
            print("[JUMBO announce ERROR]", repr(e))
            # defer() 済みだから followup で返す
            await interaction.followup.send("❌ 内部エラー（ログ確認してね）")

    # -------------------------------------------------
    # /年末ジャンボ設定
    # -------------------------------------------------
    @app_commands.command(name="年末ジャンボ設定")
    async def jumbo_set_prize(self, interaction: discord.Interaction, winning_number: str):
        await interaction.response.defer(ephemeral=True)

        if not await self.is_admin(interaction):
            return await interaction.followup.send("❌ 管理者専用")

        if not winning_number.isdigit() or len(winning_number) != 6:
            return await interaction.followup.send("❌ 当選番号は6桁です")

        await self.jumbo_db.set_winning_number(str(interaction.guild.id), winning_number)
        await interaction.followup.send("🎯 当選番号を設定しました！")

    # -------------------------------------------------
    # /所持宝くじ番号を確認
    # -------------------------------------------------
    @app_commands.command(name="所持宝くじ番号を確認")
    async def jumbo_my_numbers(self, interaction: discord.Interaction, search: str | None = None):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        rows = await self.jumbo_db.get_user_numbers(guild_id, user_id)
        numbers = [r["number"] for r in rows]

        if search:
            numbers = [n for n in numbers if search in n]

        if not numbers:
            return await interaction.response.send_message("該当なし", ephemeral=True)

        view = NumberListView(interaction.user, numbers)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    # -------------------------------------------------
    # /ジャンボ履歴リセット
    # -------------------------------------------------
    @app_commands.command(name="ジャンボ履歴リセット")
    async def jumbo_reset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            if not await self.is_admin(interaction):
                return await interaction.followup.send("❌ 管理者専用")

            guild_id = str(interaction.guild.id)

            await self.jumbo_db.clear_entries(guild_id)
            await self.jumbo_db.clear_winners(guild_id)
            await self.jumbo_db.reset_config(guild_id)

            await interaction.followup.send("🧹 ジャンボ履歴をすべてリセットしました")

        except Exception as e:
            # ★ これが無いと「考え中…」になる
            print("[JUMBO reset ERROR]", repr(e))
            await interaction.followup.send(
                "❌ リセット中にエラーが発生しました。\n管理者にログを確認してもらってください。"
            )


    # -------------------------------------------------
    # /ジャンボ賞金給付
    # -------------------------------------------------
    @app_commands.command(name="ジャンボ賞金給付")
    async def jumbo_pay(self, interaction: discord.Interaction, rank: int):
        await interaction.response.defer(ephemeral=True)

        try:
            if not await self.is_admin(interaction):
                return await interaction.followup.send("❌ 管理者専用")

            if rank not in (1, 2, 3, 4, 5):
                return await interaction.followup.send("❌ 等級は1〜5です")

            guild_id = str(interaction.guild.id)

            config = await self.jumbo_db.get_config(guild_id)
            if not config or not config["winning_number"]:
                return await interaction.followup.send("❌ 当選番号が未設定です")

            paid_ranks = await self.bot.db.jumbo_get_paid_ranks(guild_id)
            if rank in paid_ranks:
                return await interaction.followup.send(f"⚠ 第{rank}等はすでに給付済みです")

            entries = await self.jumbo_db.get_all_entries(guild_id)
            if not entries:
                return await interaction.followup.send("⚠ 購入者がいません")

            results = calc_jumbo_results(config["winning_number"], entries)
            winners = results[rank]

            PRIZES = {1: 10_000_000, 2: 5_000_000, 3: 1_000_000, 4: 500_000, 5: 50_000}
            prize = PRIZES[rank]

            # ----------------------------
            # ユーザー単位に集計
            # ----------------------------
            user_stats = defaultdict(lambda: {"count": 0, "total": 0})

            for w in winners:
                uid = w["user_id"]
                user_stats[uid]["count"] += 1
                user_stats[uid]["total"] += prize

            # ----------------------------
            # 残高付与
            # ----------------------------
            for uid, data in user_stats.items():
                await self.bot.db.add_balance(uid, guild_id, data["total"])

            await self.bot.db.jumbo_add_paid_rank(guild_id, rank)

            # ----------------------------
            # 表示用テキスト作成
            # ----------------------------
            lines = [
                f"<@{uid}>　**{data['count']}口当選**　**{data['total']:,} rrc**"
                for uid, data in user_stats.items()
            ]

            def split_lines(lines, max_chars=900):
                pages, buf = [], ""
                for line in lines:
                    if len(buf) + len(line) + 1 > max_chars:
                        pages.append(buf)
                        buf = line
                    else:
                        buf += "\n" + line if buf else line
                if buf:
                    pages.append(buf)
                return pages

            pages = split_lines(lines)

            embeds = []
            for i, page in enumerate(pages):
                embed = discord.Embed(
                    title=f"✅ 第{rank}等 賞金給付完了",
                    description=page,
                    color=0x2ECC71
                )
                embed.add_field(
                    name="当選者数",
                    value=f"{len(user_stats)}人",
                    inline=False
                )
                embed.set_footer(text=f"{i + 1} / {len(pages)} ページ")
                embeds.append(embed)

            class PayResultView(discord.ui.View):
                def __init__(self, user, embeds):
                    super().__init__(timeout=300)
                    self.user = user
                    self.embeds = embeds
                    self.page = 0

                async def interaction_check(self, interaction):
                    return interaction.user.id == self.user.id

                @discord.ui.button(label="◀ 前へ")
                async def prev(self, interaction, _):
                    self.page = max(0, self.page - 1)
                    await interaction.response.edit_message(
                        embed=self.embeds[self.page],
                        view=self
                    )

                @discord.ui.button(label="次へ ▶")
                async def next(self, interaction, _):
                    self.page = min(len(self.embeds) - 1, self.page + 1)
                    await interaction.response.edit_message(
                        embed=self.embeds[self.page],
                        view=self
                    )

            await interaction.followup.send(
                embed=embeds[0],
                view=PayResultView(interaction.user, embeds)
            )


    @tasks.loop(seconds=10)
    async def panel_updater(self):
        rows = await self.bot.db.conn.fetch("""
            SELECT guild_id, panel_channel_id, panel_message_id
            FROM jumbo_config
            WHERE is_open = TRUE
              AND panel_message_id IS NOT NULL
        """)

        for row in rows:
            guild_id = row["guild_id"]
            channel_id = row["panel_channel_id"]
            message_id = row["panel_message_id"]

            try:
                issued = await self.jumbo_db.count_entries(guild_id)
                remaining = max(0, 999_999 - issued)

                channel = self.bot.get_channel(int(channel_id))
                if channel is None:
                    try:
                        channel = await self.bot.fetch_channel(int(channel_id))
                    except:
                        continue

                message = await channel.fetch_message(int(message_id))
                if not message.embeds:
                    continue

                embed = message.embeds[0]

                found = False
                for i, field in enumerate(embed.fields):
                    if field.name.startswith("🎫 宝くじ残り枚数"):
                        found = True
                        new_value = f"{remaining:,} 枚"
                        if field.value == new_value:
                            break

                        embed.set_field_at(
                            i,
                            name="🎫 宝くじ残り枚数",
                            value=new_value,
                            inline=False
                        )
                        await message.edit(embed=embed)
                        break

                if not found:
                    embed.add_field(
                        name="🎫 宝くじ残り枚数",
                        value=f"{remaining:,} 枚",
                        inline=False
                    )
                    await message.edit(embed=embed)

            except Exception as e:
                print("[JUMBO] panel updater error:", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(JumboCog(bot))
































