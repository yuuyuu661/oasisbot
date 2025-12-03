# cogs/hotel/checkin.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

from .room_panel import HotelRoomControlPanel
from .ticket_buttons import TicketBuyButton1, TicketBuyButton10, TicketBuyButton30


class HotelCheckinCog(commands.Cog):
    """ホテルの初期設定・パネル生成・チェックインを担当"""

    def __init__(self, bot):
        self.bot = bot

    # ======================================================
    # /ホテル初期設定
    # ======================================================
    @app_commands.command(
        name="ホテル初期設定",
        description="ホテル機能の初期設定を行います（管理者）"
    )
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
        # 管理者ロール判定
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)

        # DB保存
        await self.bot.db.conn.execute("""
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

        await interaction.response.send_message(
            "🏨 ホテル初期設定を更新しました！",
            ephemeral=True
        )

    # ======================================================
    # /ホテルパネル生成（チケット購入ボタン表示）
    # ======================================================
    @app_commands.command(
        name="ホテルパネル生成",
        description="ホテルのチェックインパネルを生成します（管理者）"
    )
    async def hotel_panel(self, interaction: discord.Interaction, title: str, description: str):

        # 管理者ロール判定
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

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

        embed = discord.Embed(
            title=title,
            description=description,
            color=0xF4D03F
        )

        # チケットボタン3つ＋チェックインボタン
        view = discord.ui.View(timeout=None)
        view.add_item(CheckinButton(hotel_config))
        view.add_item(TicketBuyButton1(hotel_config))
        view.add_item(TicketBuyButton10(hotel_config))
        view.add_item(TicketBuyButton30(hotel_config))

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
# チェックインボタン
# ======================================================
class CheckinButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label="チェックイン（1枚消費）", style=discord.ButtonStyle.green)
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        user_id = str(user.id)
        guild_id = str(guild.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message(
                "❌ チケットが不足しています。",
                ephemeral=True
            )

        # 既存ルーム確認（VCが存在しない場合はDBを削除して再作成可）
        existing = await interaction.client.db.conn.fetchrow(
            "SELECT channel_id FROM hotel_rooms WHERE owner_id=$1 AND guild_id=$2",
            user_id, guild_id
        )
        if existing:
            channel = guild.get_channel(int(existing["channel_id"]))
            if channel is not None:
                return await interaction.response.send_message(
                    "⚠ すでにルームがあります。",
                    ephemeral=True
                )
            else:
                # VC削除済 → DB削除
                await interaction.client.db.delete_room(existing["channel_id"])

        # チケット消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        # VC作成（パネルと同じカテゴリ）
        category = interaction.channel.category
        vc_name = f"{user.name}の高級ホテル"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
            user: discord.PermissionOverwrite(connect=True, view_channel=True)
        }

        # ホテル管理人ロール
        manager_role = guild.get_role(int(self.config["manager_role"]))
        if manager_role:
            overwrites[manager_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

        vc = await category.create_voice_channel(
            name=vc_name,
            overwrites=overwrites,
            user_limit=2
        )

        expire = datetime.utcnow() + timedelta(hours=24)

        # DBへ保存
        await interaction.client.db.save_room(
            str(vc.id), guild_id, user_id, expire
        )

        # VCチャットに操作パネル送信
        control_view = HotelRoomControlPanel(
            owner_id=user_id,
            manager_role_id=self.config["manager_role"],
            sub_role_id=self.config["sub_role"],
            config=self.config
        )

        await vc.send(
            f"🏨 **{vc_name}** へようこそ！\nこちらが操作パネルです👇",
            view=control_view
        )

        await interaction.response.send_message(
            f"🏨 {vc_name} を作成しました！（24時間後に自動削除）",
            ephemeral=True
        )

        # -------------------------------------------------
        # チェックインログ（embed）
        # -------------------------------------------------
        log_channel = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_channel:
            embed = discord.Embed(
                title="🏨 高級ホテル：チェックイン",
                color=0xF4D03F
            )
            embed.add_field(name="ユーザー", value=user.mention, inline=False)
            embed.add_field(name="チェックイン時刻", value=f"<t:{int(datetime.utcnow().timestamp())}:F>")
            embed.add_field(name="自動削除予定", value=f"<t:{int(expire.timestamp())}:F>")
            embed.add_field(name="VC", value=f"{vc.name}（ID: {vc.id}）", inline=False)

            await log_channel.send(embed=embed)
