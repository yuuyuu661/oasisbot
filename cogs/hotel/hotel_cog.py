import discord
from discord.ext import commands
from discord import app_commands

from .checkin import CheckinButton
from .ticket_dropdown import TicketBuyDropdown


class HotelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # VC削除イベント
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

        # 管理者ロール判定
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

        # ここが重要：新しいパネル構成
        view = discord.ui.View(timeout=None)
        view.add_item(CheckinButton(hotel_config))
        view.add_item(TicketBuyDropdown(hotel_config))

        await interaction.response.send_message(embed=embed, view=view)

    # ======================================================
    # /チケット確認
    # ======================================================
    @app_commands.command(name="チケット確認", description="自分の所持チケット数を確認します")
    async def ticket_check_cmd(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await self.bot.db.get_tickets(user_id, guild_id)
        await interaction.response.send_message(f"🎫 所持チケット: **{tickets}枚**", ephemeral=True)


# ======================================================
# パネルビュー（チェックイン＆購入）
# ======================================================

class HotelPanelView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)
        self.config = config

        self.add_item(CheckinButton(config))
        self.add_item(TicketBuyDropdown(config))



