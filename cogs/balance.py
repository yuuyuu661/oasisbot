import inspect
import discord
from discord.ext import commands
from discord import app_commands

from logger import log_pay
from PIL import Image
import os
import io

BADGE_DIR = os.path.join(os.path.dirname(__file__), "assets", "badge")

BADGE_FILES = {
    "gold": "gold.png",
    "silver": "silver.png",
    "bronze": "bronze.png",
}
def build_badge_image(badges: list[str]) -> io.BytesIO | None:
    """
    badges: ["gold", "silver", ...]
    """
    if not badges:
        return None

    size = 20          # バッジ1枚の表示サイズ（小さめ）
    gap = 6            # 間隔

    imgs = []
    for b in badges:
        if b not in BADGE_FILES:
            continue
        path = os.path.join(BADGE_DIR, BADGE_FILES[b])
        img = Image.open(path).convert("RGBA")
        img = img.resize((size, size))
        imgs.append(img)

    if not imgs:
        print("NO IMAGES LOADED")
        print("BADGES:", badges)
        return None

    width = len(imgs) * size + (len(imgs) - 1) * gap
    height = size

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    x = 0
    for img in imgs:
        canvas.paste(img, (x, 0), img)
        x += size + gap

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    return buf

def load_badge_files():
    files = {}
    for f in os.listdir(BADGE_DIR):
        if f.endswith(".png"):
            name = os.path.splitext(f)[0]
            files[name] = f
    return files

BADGE_FILES = load_badge_files()

def get_badge_choices():
    return [
        app_commands.Choice(name=badge_name, value=badge_name)
        for badge_name in sorted(BADGE_FILES.keys())
    ]
    
class BalanceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ================================
    # 内部ヘルパー: 管理者判定
    # ================================
    async def _can_view_others(self, member: discord.Member) -> bool:
        """
        他ユーザーの残高を見てもよいかどうかを判定する。
        ・Discordの管理者権限
        ・settings.admin_roles に登録されたロール
        のどちらかを持っていれば True
        """
        # Discord の「サーバー管理者」権限
        if member.guild_permissions.administrator:
            return True

        # DB設定に登録されている管理者ロール
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        return any(str(r.id) in admin_roles for r in member.roles)

    # ================================
    # /bal 残高確認（指定ユーザーを見る場合は管理者ロール必須）
    # ================================
    @app_commands.command(
        name="bal",
        description="自分または指定ユーザーの残高を確認します"
    )
    @app_commands.describe(
        member="確認したいユーザー（省略時は自分）"
    )
    async def bal(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None
    ):
        bot = self.bot
        guild = interaction.guild
        user = interaction.user

        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True
            )

        db = bot.db

        # 対象ユーザー（未指定なら自分）
        target = member or user

        if target.id != user.id:
            settings = await db.get_settings()
            admin_roles = settings["admin_roles"] or []

            if not any(str(r.id) in admin_roles for r in user.roles):
                return await interaction.response.send_message(
                    "❌ 他ユーザーの残高を確認するには管理者ロールが必要です。",
                    ephemeral=True
                )

        try:
            # 残高
            row = await db.get_user(str(target.id), str(guild.id))
            # チケット枚数
            tickets = await db.get_tickets(str(target.id), str(guild.id))
            # ジャンボ購入数
            jumbo_count = await db.jumbo_get_user_count(
                str(guild.id),
                str(target.id)
            )

            # 通貨単位
            settings = await db.get_settings()
            unit = settings["currency_unit"]
        except Exception as e:
            print("bal error:", repr(e))
            if interaction.response.is_done():
                return await interaction.followup.send(
                    "内部エラーが発生しました。（bal）",
                    ephemeral=True
                )
            else:
                return await interaction.response.send_message(
                    "内部エラーが発生しました。（bal）",
                    ephemeral=True
                )

        await interaction.response.send_message(
            f"💰 **{target.display_name} の残高**\n"
            f"所持金: **{row['balance']} {unit}**\n"
            f"チケット: **{tickets}枚**\n"
            f"ジャンボ: **{jumbo_count}口 🎫**",
            ephemeral=True
        )

    # ================================
    # VC入室時 自動自己紹介リンク送信
    # ================================
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):

        # 入室のみ
        if not before.channel and after.channel:

            guild = member.guild
            guild_id = str(guild.id)

            settings = await self.bot.db.get_intro_auto_settings(guild_id)
            if not settings:
                return

            watch_channels = settings["channels"]

            intro_link = None

            for ch_id in watch_channels:
                ch = guild.get_channel(int(ch_id))
                if not ch:
                    continue

                async for msg in ch.history(oldest_first=True):
                    if msg.author.id == member.id:
                       intro_link = msg.jump_url
                        break

                if intro_link:
                    break

            if not intro_link:
                return

            send_channel = guild.get_channel(int(watch_channels[0]))

            if not send_channel:
                return

            await send_channel.send(
                f"📢 {member.mention} の自己紹介はこちら\n{intro_link}"
            )


    @app_commands.command(
        name="badge_add",
        description="ユーザーまたはロールにバッジ付与（管理者）"
    )
    @app_commands.describe(
        member="対象ユーザー",
        role="対象ロール",
        badge="付与するバッジ"
    )
    @app_commands.choices(badge=get_badge_choices())
    async def badge_add(
        self,
        interaction: discord.Interaction,
        badge: app_commands.Choice[str],
        member: discord.Member | None = None,
        role: discord.Role | None = None,
    ):
        guild = interaction.guild
        user = interaction.user
        badge_value = badge.value

        # 管理者チェック
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in user.roles):
            return await interaction.response.send_message(
                "❌ 管理者のみ実行できます。",
                ephemeral=True
            )

        if not member and not role:
            return await interaction.response.send_message(
                "❌ ユーザーまたはロールを指定してください。",
                ephemeral=True
            )

        if member and role:
            return await interaction.response.send_message(
                "❌ ユーザーとロールを同時指定できません。",
                ephemeral=True
            )

        # =========================
        # 個別付与
        # =========================
        if member:
            await self.bot.db.add_user_badge(
                str(member.id),
                str(guild.id),
                badge_value
            )

            return await interaction.response.send_message(
                f"🏅 {member.mention} に **{badge_value}** を付与しました。",
                ephemeral=True
            )

        # =========================
        # ロール付与
        # =========================
        members = role.members

        if not members:
            return await interaction.response.send_message(
                "このロールにはメンバーがいません。",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        count = 0
        for m in members:
            await self.bot.db.add_user_badge(
                str(m.id),
                str(guild.id),
                badge_value
            )
            count += 1

        await interaction.followup.send(
            f"🏅 {role.name} の {count}人に **{badge_value}** を付与しました。",
            ephemeral=True
        )


    @app_commands.command(
        name="badge_remove",
        description="ユーザーまたはロールからバッジ削除（管理者）"
    )
    @app_commands.describe(
        member="対象ユーザー",
        role="対象ロール",
        badge="削除するバッジ"
    )
    @app_commands.choices(badge=get_badge_choices())
    async def badge_remove(
        self,
        interaction: discord.Interaction,
        badge: app_commands.Choice[str],
        member: discord.Member | None = None,
        role: discord.Role | None = None,
    ):
        guild = interaction.guild
        user = interaction.user
        badge_value = badge.value

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in user.roles):
            return await interaction.response.send_message(
                "❌ 管理者のみ実行できます。",
                ephemeral=True
            )

        if not member and not role:
            return await interaction.response.send_message(
                "❌ ユーザーまたはロールを指定してください。",
                ephemeral=True
            )

        if member and role:
            return await interaction.response.send_message(
                "❌ ユーザーとロールを同時指定できません。",
                ephemeral=True
            )

        # 個別削除
        if member:
            await self.bot.db.remove_user_badge(
                str(member.id),
                str(guild.id),
                badge_value
            )

            return await interaction.response.send_message(
                f"🗑️ {member.mention} から **{badge_value}** を削除しました。",
                ephemeral=True
            )

        # ロール削除
        members = role.members

        if not members:
            return await interaction.response.send_message(
                "このロールにはメンバーがいません。",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        count = 0
        for m in members:
            await self.bot.db.remove_user_badge(
                str(m.id),
                str(guild.id),
                badge_value
            )
            count += 1

        await interaction.followup.send(
            f"🗑️ {role.name} の {count}人から **{badge_value}** を削除しました。",
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
        # 金額に応じてパネル色を決定
        if amount >= 1_000_000:
            color = 0xE74C3C  # 赤
        elif amount >= 500_000:
            color = 0xE67E22  # オレンジ
        elif amount >= 300_000:
            color = 0xF1C40F  # 黄色
        elif amount >= 100_000:
            color = 0x2ECC71  # 緑
        elif amount >= 10_000:
            color = 0x1ABC9C  # 水色
        else:
            color = 0x3498DB  # 青

        embed = discord.Embed(
            title="💸  送金完了！",
            description=(
                f"\n"
                f" **送金者**：{sender.mention}\n"
                f" **受取**：{member.mention}\n"
                f"\n"
            ),
            color=color
        )

        # 金額フィールド（見やすく太字）
        embed.add_field(
            name="  送金額",
            value=f"\n**{amount:,} {unit}**\n",
            inline=False
        )

        # メモ（任意）
        if memo:
            embed.add_field(
                name="📝  メモ",
                value=f"\n{memo}\n",
                inline=False
            )
        
        # ------------------------
        # バッジ画像生成
        # ------------------------
        print("===== PAY DEBUG =====")
        print("SENDER:", sender.id)
        print("TARGET:", member.id)
        print("====================")

        print("STEP1: get badges start")
        user_badges = await db.get_user_badges(
            str(sender.id),
            str(guild.id)
        )
        print("STEP2: user_badges =", user_badges)
        badge_buf = build_badge_image(user_badges)
        print("STEP3: badge_buf =", badge_buf)

        # ------------------------
        # 添付ファイル一覧
        # ------------------------
        files = []

        # 右上サムネ（今まで通り）
        pay_file = discord.File("pay.png", filename="pay.png")
        files.append(pay_file)
        embed.set_thumbnail(url="attachment://pay.png")

        # 下に表示するバッジ画像
        if badge_buf:
            badge_file = discord.File(badge_buf, filename="badges.png")
            files.append(badge_file)
            embed.set_image(url="attachment://badges.png")

        # ------------------------
        # 送信
        # ------------------------
        await interaction.response.send_message(
            embed=embed,
            files=files
        )
        # --- ログ ---
        try:
            sig = inspect.signature(log_pay)
            if "memo" in sig.parameters:
                await log_pay(
                    bot=bot,
                    settings=settings,
                    from_id=sender.id,
                    to_id=member.id,
                    amount=amount,
                    memo=memo,
                )
            else:
                await log_pay(
                    bot=bot,
                    settings=settings,
                    from_id=sender.id,
                    to_id=member.id,
                    amount=amount,
                )
        except Exception as e:
            print("log_pay error:", repr(e))

    @app_commands.command(name="自動自己紹介送信設定", description="VC入室時に自己紹介リンクを送信する設定")
    @app_commands.describe(
        category1="対象カテゴリー",
        category2="対象カテゴリー",
        category3="対象カテゴリー",
        category4="対象カテゴリー",
        category5="対象カテゴリー",
        ch1="監視テキストチャンネル",
        ch2="監視テキストチャンネル",
        ch3="監視テキストチャンネル",
        ch4="監視テキストチャンネル",
        ch5="監視テキストチャンネル",
    )
    async def intro_auto_setting(
        self,
        interaction: discord.Interaction,
        category1: discord.CategoryChannel,
        ch1: discord.TextChannel,
        category2: discord.CategoryChannel | None = None,
        category3: discord.CategoryChannel | None = None,
        category4: discord.CategoryChannel | None = None,
        category5: discord.CategoryChannel | None = None,
        ch2: discord.TextChannel | None = None,
        ch3: discord.TextChannel | None = None,
        ch4: discord.TextChannel | None = None,
        ch5: discord.TextChannel | None = None,
    ):
        categories = [c.id for c in [category1, category2, category3, category4, category5] if c]
        channels = [c.id for c in [ch1, ch2, ch3, ch4, ch5] if c]

        await self.bot.db.save_intro_auto_settings(
            str(interaction.guild.id),
            categories,
            channels
        )

        await interaction.response.send_message(
            f"✅ 自動自己紹介設定完了\n"
            f"カテゴリー数: {len(categories)}\n"
            f"監視チャンネル数: {len(channels)}",
            ephemeral=True
        )


# --------------------------
# setup（必須）
# --------------------------

async def setup(bot):
    cog = BalanceCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))

