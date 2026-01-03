# cogs/admin.py
import discord
from discord.ext import commands
from discord import app_commands

from logger import log_manage
from paginator import Paginator


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
    async def set_balance(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        amount: int,
        mode: str
    ):

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

        # 操作モード分岐
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

        # 新しい残高を取得
        new_bal = (await self.bot.db.get_user(uid, guild_id))["balance"]

        # ログ処理
        await log_manage(
            self.bot,
            settings,
            str(interaction.user.id),
            uid,
            mode,
            amount,
            new_bal
        )

        # 返答 → 実行者のみ
        await interaction.response.send_message(
            f"📝 <@{uid}> の残高を **{mode}** しました。\n"
            f"現在：**{new_bal}{unit}**",
            ephemeral=True
        )

    # ------------------------------------------------------
    # /ロール送金（送金・引き落とし共通）
    # ------------------------------------------------------
    @app_commands.command(
        name="ロール送金",
        description="指定ロールを持つ全メンバーに一括送金または引き落としを行います（管理者）"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="送金", value="pay"),
            app_commands.Choice(name="引き落とし", value="deduct"),
        ]
    )
    async def role_pay(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        action: app_commands.Choice[str],
        amount: int
    ):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者チェック
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

        # サブ垢ロール取得（ホテル設定）
        hotel_config = await self.bot.db.conn.fetchrow(
            "SELECT sub_role FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )
        sub_role_id = hotel_config["sub_role"] if hotel_config else None
        sub_role = guild.get_role(int(sub_role_id)) if sub_role_id else None

        # 対象メンバー抽出
        members = [
            m for m in guild.members
            if role in m.roles
            and not m.bot
            and not (sub_role and sub_role in m.roles)
        ]

        if not members:
            return await interaction.response.send_message(
                "⚠ 対象ユーザーがいません。",
                ephemeral=True
            )

        # 処理分岐
        if action.value == "pay":
            for member in members:
                await self.bot.db.add_balance(str(member.id), guild_id, amount)

            verb = "送金"
            sign = "+"

        else:  # deduct
            for member in members:
                await self.bot.db.add_balance(str(member.id), guild_id, -amount)

            verb = "引き落とし"
            sign = "-"

        total = amount * len(members)

        await interaction.response.send_message(
            f"💰 ロール **{role.name}** を持つ **{len(members)}名** に対して\n"
            f"**{verb}** を実行しました。\n"
            f"金額：**{sign}{amount}{unit}** × {len(members)}人\n"
            f"合計：**{sign}{total}{unit}**"
        )

    # --------------------------
    # /残高一覧（ギルド別）
    # --------------------------
    @app_commands.command(
        name="残高一覧",
        description="全ユーザーの残高を上位順に表示します（管理者限定）"
    )
    async def balance_list(self, interaction: discord.Interaction):

        # 設定取得
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者ロールチェック（サーバー管理者 or admin_roles）
        is_admin_role = any(str(r.id) in admin_roles for r in interaction.user.roles)
        if not (interaction.user.guild_permissions.administrator or is_admin_role):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True
            )

        guild_id = str(guild.id)
        rows = await self.bot.db.get_all_balances(guild_id)

        if not rows:
            embed = discord.Embed(
                title="💰 残高一覧（上位順）",
                description="データがありません。",
                color=0xf1c40f
            )
            return await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        # 残高でソート（降順）
        rows.sort(key=lambda r: r["balance"], reverse=True)

        # 1ページあたりの件数
        per_page = 10
        total = len(rows)
        page_count = (total + per_page - 1) // per_page

        pages: list[discord.Embed] = []

        for page_index in range(page_count):
            start = page_index * per_page
            end = start + per_page
            chunk = rows[start:end]

            lines = []
            for i, r in enumerate(chunk, start=start + 1):
                lines.append(f"{i}. <@{r['user_id']}>：**{r['balance']}{unit}**")

            embed = discord.Embed(
                title="💰 残高一覧（上位順）",
                description="\n".join(lines),
                color=0xf1c40f
            )
            embed.set_footer(
                text=f"ページ {page_index + 1}/{page_count} | ユーザー数: {total}"
            )
            pages.append(embed)

        # ページ数に応じて出し分け
        if len(pages) == 1:
            # 1ページだけなら普通に送信（エフェメラル）
            await interaction.response.send_message(
                embed=pages[0],
                ephemeral=True
            )
        else:
            # 複数ページなら Paginator を使う（エフェメラル）
            view = Paginator(pages)
            await interaction.response.send_message(
                embed=pages[0],
                view=view,
                ephemeral=True
            )


# --------------------------
# setup（必須）
# --------------------------

async def setup(bot):
    cog = AdminCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))





