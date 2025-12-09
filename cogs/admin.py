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

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        uid = str(user.id)
        guild_id = str(interaction.guild.id)

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
    # /ロール送金（管理者ロール必須）
    # ------------------------------------------------------
        @app_commands.command(
        name="ロール送金",
        description="指定ロールを持つ全メンバーに一括送金します（管理者）"
    )
    async def role_pay(self, interaction: discord.Interaction, role: discord.Role, amount: int):

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

        # ▼ ホテル設定のサブ垢ロール取得
        hotel_config = await self.bot.db.conn.fetchrow(
            "SELECT sub_role FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )
        sub_role_id = hotel_config["sub_role"] if hotel_config else None
        sub_role = guild.get_role(int(sub_role_id)) if sub_role_id else None

        # ▼ 対象メンバー抽出（サブ垢ロールは除外）
        members = [
            m for m in guild.members
            if (role in m.roles)
            and not m.bot
            and not (sub_role and sub_role in m.roles)
        ]

        if not members:
            return await interaction.response.send_message(
                "⚠ 対象ユーザーがいません。（サブ垢ロール所持者は除外済み）",
                ephemeral=True
            )

        # ▼ 加算処理
        for member in members:
            await self.bot.db.add_balance(str(member.id), guild_id, amount)

        total = amount * len(members)

        await interaction.response.send_message(
            f"💰 ロール **{role.name}** を持つ **{len(members)}名** に "
            f"**{amount}{unit}** を送金しました！（合計：{total}{unit}）\n"
            f"※ サブ垢ロール所持者は自動的に除外されています。"
        )


        # 加算処理
        for member in members:
            await self.bot.db.add_balance(str(member.id), guild_id, amount)

        total = amount * len(members)

        await interaction.response.send_message(
            f"💰 ロール **{role.name}** を持つ **{len(members)}名** に "
            f"**{amount}{unit}** を送金しました！（合計：{total}{unit}）"
        )

    # --------------------------
    # /残高一覧（ギルド別）
    # --------------------------
    @app_commands.command(
        name="残高一覧",
        description="全ユーザーの残高を上位順に表示します（管理者限定）"
    )
    async def balance_list(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)
        rows = await self.bot.db.get_all_balances(guild_id)

        embed = discord.Embed(
            title="💰 残高一覧（上位順）",
            color=0xf1c40f
        )

        if not rows:
            embed.description = "データがありません。"
        else:
            lines = []
            for r in rows:
                lines.append(f"<@{r['user_id']}>：**{r['balance']}{unit}**")
            embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed)


# --------------------------
# setup（必須）
# --------------------------
async def setup(bot):
    cog = AdminCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))

