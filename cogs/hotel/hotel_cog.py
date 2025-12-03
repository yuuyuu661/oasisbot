# cogs/hotel/hotel_cog.py

import discord
from discord.ext import commands
from discord import app_commands

from .checkin import CheckinButton
from .ticket_dropdown import TicketBuyDropdown, TicketBuyExecuteButton


class HotelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================================
    # VC削除 → DBクリーンアップ
    # ================================
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.VoiceChannel):
            room = await self.bot.db.get_room(str(channel.id))
            if room:
                await self.bot.db.delete_room(str(channel.id))
                print(f"[Hotel] Cleanup → Deleted room {channel.id} from DB")

    # ======================================================
    # /ホテル初期設定
    # ======================================================
    @app_commands.command(name="ホテル初期設定", description="ホテル機能の初期設定を行います（管理者）")
    async def hotel_setup(
        self,
        interaction: discord.Interaction,
        manager_role: discord.Role,
        log_channel: discord.TextChannel,
        sub_role: discord.Role,
        price_1: int,
        price_10: int,
        price_30: int
    ):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.bot.db.conn.execute(
            """
            INSERT INTO hotel_settings (
                guild_id, manager_role, log_channel, sub_role,
                ticket_price_1, ticket_price_10, ticket_price_30
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                manager_role=$2,
                log_channel=$3,
                sub_role=$4,
                ticket_price_1=$5,
                ticket_price_10=$6,
                ticket_price_30=$7;
            """,
            guild_id,
            str(manager_role.id),
            str(log_channel.id),
            str(sub_role.id),
            price_1,
            price_10,
            price_30
        )

        await interaction.response.send_message("🏨 ホテル初期設定を更新しました！", ephemeral=True)

    # ======================================================
    # /ホテルパネル生成
    # ======================================================
    @app_commands.command(name="ホテルパネル生成", description="ホテルのチェックインパネルを生成します（管理者）")
    async def hotel_panel(self, interaction: discord.Interaction, title: str, description: str):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        hotel_config = await self.bot.db.conn.fetchrow(
            "SELECT * FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )
        if not hotel_config:
            return await interaction.response.send_message(
                "❌ ホテル初期設定がまだ行われていません。",
                ephemeral=True
            )

        embed = discord.Embed(title=title, description=description, color=0xF4D03F)

        # ================================
        # 新しい 完成版パネル
        # ================================
        view = discord.ui.View(timeout=None)

        # チェックイン
        view.add_item(CheckinButton(hotel_config))

        # プルダウン（選択）
        selector = TicketBuyDropdown(hotel_config)
        view.add_item(selector)

        # 購入実行ボタン（プルダウン値を読む）
        view.add_item(TicketBuyExecuteButton(selector, hotel_config))

        await interaction.response.send_message(embed=embed, view=view)

    # ======================================================
    # /チケット確認
    # ======================================================
    @app_commands.command(name="チケット確認", description="自分の所持チケット数を確認します")
    async def ticket_check_cmd(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await self.bot.db.get_tickets(user_id, guild_id)
        await interaction.response.send_message(
            f"🎫 所持チケット: **{tickets}枚**",
            ephemeral=True
        )

    # ======================================================
    # /ホテルリセット
    # ======================================================
    @app_commands.command(
        name="ホテルリセット",
        description="指定ユーザーのホテルルーム情報をリセットします（管理者）"
    )
    async def hotel_reset(self, interaction: discord.Interaction, target: discord.Member):

        # 管理者ロール判定
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)
        user_id = str(target.id)

        # DBに登録されているルームを検索
        room = await self.bot.db.conn.fetchrow(
            "SELECT channel_id FROM hotel_rooms WHERE owner_id=$1 AND guild_id=$2",
            user_id, guild_id
        )

        if not room:
            return await interaction.response.send_message(
                f"⚠ {target.mention} は現在ホテルルームを所持していません。",
                ephemeral=True
            )

        channel_id = room["channel_id"]
        channel = guild.get_channel(int(channel_id))

        # ボイスチャンネルが残っている場合 → 削除
        if channel:
            try:
                await channel.delete(reason="ホテルリセットによるVC削除")
            except Exception:
                pass

        # DBのレコード削除
        await self.bot.db.delete_room(str(channel_id))

        await interaction.response.send_message(
            f"🧹 {target.mention} のホテルデータをリセットしました！\n"
            f"再度チェックイン可能になっています。",
            ephemeral=True
        )

# ======================================================
# 旧UI互換：HotelPanelView
# 使わない場合は残してもOK
# ======================================================
class HotelPanelView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)

        selector = TicketBuyDropdown(config)

        self.add_item(CheckinButton(config))
        self.add_item(selector)
        self.add_item(TicketBuyExecuteButton(selector, config))


# ======================================================
# setup（必須）
# ======================================================
async def setup(bot):
    await bot.add_cog(HotelCog(bot))

    if hasattr(bot, "GUILD_IDS"):
        for gid in bot.GUILD_IDS:
            guild = discord.Object(id=gid)
            try:
                synced = await bot.tree.sync(guild=guild)
                print(f"[Hotel] Synced {len(synced)} cmds → guild {gid}")
            except Exception as e:
                print(f"[Hotel] Sync failed for {gid}: {e}")

    print("🏨 Hotel module loaded successfully!")

