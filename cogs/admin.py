# cogs/admin.py
import discord
from discord.ext import commands
from discord import app_commands

from logger import log_manage


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------
    # /残高設定（ギルド別）
    # --------------------------
    @app_commands.command(
        name="残高設定",
        description="ユーザーの残高を設定・増加・減少（管理者）"
    )
    async def set_balance(self, interaction: discord.Interaction, user: discord.User, amount: int, mode: str):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者ロールチェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        uid = str(user.id)
        guild_id = str(interaction.guild.id)

        # モード分岐
        if mode == "設定":
            await self.bot.db.set_balance(uid, guild_id, amount)
        elif mode == "増加":
            await self.bot.db.add_balance(uid, guild_id, amount)
        elif mode == "減少":
            await self.bot.db.remove_balance(uid, guild_id, amount)
        else:
            return await interaction.response.send_message(
                "モードは 設定 / 増加 / 減少 から選んでください。",
                ephemeral=True
            )

        new_bal = (await self.bot.db.get_user(uid, guild_id))["balance"]

        # ログ送信
        await log_manage(
            self.bot,
            settings,
            str(interaction.user.id),
            uid,
            mode,
            amount,
            new_bal
        )

        await interaction.response.send_message(
            f"📝 <@{uid}> の残高を **{mode}** しました。\n"
            f"現在：**{new_bal}{unit}**"
        )

    # ------------------------------------------------------
    # /ロール送金（サブ垢除外）
    # ------------------------------------------------------
    @app_commands.command(
        name="ロール送金",
        description="指定ロールを持つ全メンバーに一括送金します（管理者）"
    )
    async def role_pay(self, interaction: discord.Interaction, role: discord.Role, amount: int):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者ロール必須
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ このコマンドを実行する権限がありません。",
                ephemeral=True
            )

        if amount <= 0:
            return await interaction.response.send_message(
                "❌ 金額は1以上で指定してください。",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)

        # ▼ ホテル設定のサブ垢ロール取得
        hotel_config = await self.bot.db.conn.fetchrow(
            "SELECT sub_role FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )
        sub_role_id = hotel_config["sub_role"] if hotel_config else None
        sub_role = guild.get_role(int(sub_role_id)) if sub_role_id else None

        # ▼ 対象メンバー（サブ垢除外）
        members = [
            m for m in guild.members
            if (role in m.roles)
            and not m.bot
            and not (sub_role and sub_role in m.roles)
        ]

        if not members:
            return await interaction.response.send_message(
                "⚠ 対象ユーザーがいません。（サブ垢ロール所持者は除外）",
                ephemeral=True
            )

        # 残高加算
        for member in members:
            await self.bot.db.add_balance(str(member.id), guild_id, amount)

        total = amount * len(members)

        await interaction.response.send_message(
            f"💰 ロール **{role.name}** を持つ **{len(members)}名** に "
            f"**{amount}{unit}** を送金しました！（合計：{total}{unit}）\n"
            f"※ サブ垢ロールは自動で除外されています。"
        )

    # --------------------------
    # /残高一覧（ページング + 並び替え）
    # --------------------------
    @app_commands.command(
        name="残高一覧",
        description="全ユーザーの残高をページ式で表示します（管理者限定）"
    )
    async def balance_list(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者ロールチェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)
        rows = await self.bot.db.get_all_balances(guild_id)

        if not rows:
            return await interaction.response.send_message(
                "⚠ データがありません。",
                ephemeral=True
            )

        # ページビュー作成
        view = BalanceListView(
            rows=rows,
            unit=unit,
            title="💰 残高一覧（上位順）",
            reverse=False
        )

        embed = view.get_page_embed(0)

        await interaction.response.send_message(embed=embed, view=view)


# =====================================================
#   📘 ページングビュー（完全修正版）
# =====================================================
class BalanceListView(discord.ui.View):
    def __init__(self, rows, unit, title, reverse=False):
        super().__init__(timeout=120)

        self.unit = unit
        self.title = title
        self.reverse = reverse
        self.rows_raw = rows  # [{user_id, balance}, ...]
        self.page = 0
        self.PAGE_SIZE = 20

        self.refresh_sorted_rows()

    # 並び替え処理
    def refresh_sorted_rows(self):
        if self.reverse:
            # 低い順（0円除外）
            self.rows = [r for r in self.rows_raw if r["balance"] > 0]
            self.rows.sort(key=lambda r: r["balance"])
        else:
            # 高い順
            self.rows = sorted(self.rows_raw, key=lambda r: r["balance"], reverse=True)

        self.max_page = max(0, (len(self.rows) - 1) // self.PAGE_SIZE)

    # 指定ページの embed を生成
    def get_page_embed(self, page: int):
        self.page = page

        start = page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        chunk = self.rows[start:end]

        embed = discord.Embed(
            title=self.title + ("（低い順）" if self.reverse else ""),
            color=0xf1c40f
        )

        if not chunk:
            embed.description = "データなし"
            return embed

        lines = []
        for r in chunk:
            uid = r["user_id"]
            bal = r["balance"]
            lines.append(f"<@{uid}>：**{bal}{self.unit}**")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Page {self.page+1} / {self.max_page+1}")

        return embed

    # ---------- 前へ ----------
    @discord.ui.button(label="◀ 前へ", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        else:
            return await interaction.response.send_message("これ以上前はありません。", ephemeral=True)

        embed = self.get_page_embed(self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    # ---------- 次へ ----------
    @discord.ui.button(label="次へ ▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
        else:
            return await interaction.response.send_message("これ以上先はありません。", ephemeral=True)

        embed = self.get_page_embed(self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    # ---------- 低い順 ----------
    @discord.ui.button(label="🔄 低い順", style=discord.ButtonStyle.secondary)
    async def sort_reverse(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.reverse = True
        self.refresh_sorted_rows()
        self.page = 0

        embed = self.get_page_embed(0)
        await interaction.response.edit_message(embed=embed, view=self)

    # ---------- 高い順 ----------
    @discord.ui.button(label="🔝 高い順", style=discord.ButtonStyle.secondary)
    async def sort_normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.reverse = False
        self.refresh_sorted_rows()
        self.page = 0

        embed = self.get_page_embed(0)
        await interaction.response.edit_message(embed=embed, view=self)


# --------------------------
# setup（必須）
# --------------------------
async def setup(bot):
    cog = AdminCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
                        # 🔒 すでに登録済みならスキップ
        if cmd.name in bot._added_app_commands:
            continue

        # ✅ 初回登録
        bot._added_app_commands.add(cmd.name)
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
