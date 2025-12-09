import inspect
import discord
from discord.ext import commands
from discord import app_commands

from logger import log_pay


class BalanceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

# ================================
# /bal 残高確認（指定ユーザーは管理者のみ）
# ================================
@app_commands.command(
    name="bal",
    description="自分または指定ユーザーの残高を確認します"
)
@app_commands.describe(
    member="確認したいユーザー（省略時は自分）"
)
async def bal(self, interaction: discord.Interaction, member: discord.Member | None = None):

    guild = interaction.guild
    user = interaction.user
    db = self.bot.db

    if guild is None:
        return await interaction.response.send_message(
            "サーバー内でのみ使用できます。",
            ephemeral=True
        )

    # ▼ 見たい対象
    target = member or user

    # ▼ 他人の残高を見るときは管理者ロール必須
    if target.id != user.id:

        settings = await db.get_settings()
        admin_roles = settings.get("admin_roles", [])  # ['id', 'id', ...]

        # ロールIDの整数化セット
        admin_role_ids = {int(rid) for rid in admin_roles if rid.isdigit()}

        # 実行者が管理者ロールを持っているか
        has_admin = any(r.id in admin_role_ids for r in user.roles)

        if not has_admin:
            return await interaction.response.send_message(
                "❌ 他ユーザーの残高を確認するには管理者ロールが必要です。",
                ephemeral=True
            )

    # ▼ DB取得
    row = await db.get_user(str(target.id), str(guild.id))
    tickets = await db.get_tickets(str(target.id), str(guild.id))
    settings = await db.get_settings()
    unit = settings["currency_unit"]

    await interaction.response.send_message(
        f"💰 **{target.display_name} の残高**\n"
        f"所持金: **{row['balance']} {unit}**\n"
        f"チケット: **{tickets}枚**",
        ephemeral=True
    )



    # ================================
    # /pay 送金（メモ対応）
    # ================================
    @app_commands.command(
        name="pay",
        description="指定ユーザーに通貨を送金します（メモ対応）"
    )
    @app_commands.describe(
        member="送金先のユーザー",
        amount="送金額（整数）",
        memo="任意のメモ（省略可）"
    )
    async def pay(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
        memo: str | None = None
    ):
        bot = self.bot
        guild = interaction.guild
        sender = interaction.user

        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True
            )


        if amount <= 0:
            return await interaction.response.send_message(
                "送金額は1以上を指定してください。",
                ephemeral=True
            )

        db = bot.db

        try:
            settings = await db.get_settings()
            unit = settings["currency_unit"]

            # 残高チェック
            sender_row = await db.get_user(str(sender.id), str(guild.id))
            if sender_row["balance"] < amount:
                return await interaction.response.send_message(
                    f"残高が足りません。\n現在: {sender_row['balance']} {unit}",
                    ephemeral=True
                )

            # 送金実行
            await db.remove_balance(str(sender.id), str(guild.id), amount)
            await db.add_balance(str(member.id), str(guild.id), amount)
        except Exception as e:
            print("pay error:", repr(e))
            if interaction.response.is_done():
                return await interaction.followup.send(
                    "内部エラーが発生しました。（pay）",
                    ephemeral=True
                )
            else:
                return await interaction.response.send_message(
                    "内部エラーが発生しました。（pay）",
                    ephemeral=True
                )

        # --- 返信メッセージ ---
        msg = (
            f"💸 **送金完了！**\n"
            f"{sender.mention} → {member.mention}\n"
            f"送金額: **{amount} {unit}**"
        )
        if memo:
            msg += f"\n📝 メモ: {memo}"

        await interaction.response.send_message(msg)

        # --- ログ ---
        try:
            sig = inspect.signature(log_pay)
            if "memo" in sig.parameters:
                # memo 対応版 logger の場合
                await log_pay(
                    bot=bot,
                    settings=settings,
                    from_id=sender.id,
                    to_id=member.id,
                    amount=amount,
                    memo=memo,
                )
            else:
                # 旧 logger（memo なし）の場合
                await log_pay(
                    bot=bot,
                    settings=settings,
                    from_id=sender.id,
                    to_id=member.id,
                    amount=amount,
                )
        except Exception as e:
            print("log_pay error:", repr(e))


async def setup(bot: commands.Bot):
    """Cog を登録し、/bal と /pay を各ギルドに紐付ける"""
    cog = BalanceCog(bot)
    await bot.add_cog(cog)

    # 既存設計と同じ方式でギルドコマンドとして登録
    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
