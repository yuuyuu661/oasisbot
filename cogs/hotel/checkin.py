import discord
from datetime import datetime, timedelta

from .room_panel import HotelRoomControlPanel


class CheckinButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label="チェックイン（1枚消費）", style=discord.ButtonStyle.green)
        self.config = config

    async def callback(self, interaction: discord.Interaction):

        user = interaction.user
        guild = interaction.guild
        guild_id = str(guild.id)
        user_id = str(user.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        # 1人1室のみ
        existing = await interaction.client.db.conn.fetchval(
            "SELECT channel_id FROM hotel_rooms WHERE owner_id=$1 AND guild_id=$2",
            user_id, guild_id
        )
        if existing:
            return await interaction.response.send_message("⚠ すでにルームがあります。", ephemeral=True)

        # チケット消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        # VC作成（パネルと同じカテゴリ）
        category = interaction.channel.category
        vc_name = f"{user.name}の高級ホテル"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
            user: discord.PermissionOverwrite(connect=True, view_channel=True)
        }

        manager_role = guild.get_role(int(self.config["manager_role"]))
        if manager_role:
            overwrites[manager_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

        vc = await category.create_voice_channel(
            name=vc_name, overwrites=overwrites, user_limit=2
        )

        # 24時間期限
        expire = datetime.utcnow() + timedelta(hours=24)

        await interaction.client.db.save_room(str(vc.id), guild_id, user_id, expire)

        # 操作パネルをVCチャットに送信
        control_panel = HotelRoomControlPanel(
            owner_id=user_id,
            manager_role_id=self.config["manager_role"],
            sub_role_id=self.config["sub_role"],
            config=self.config
        )

        msg = f"🏨 **{vc_name}** へようこそ！\nこちらが操作パネルです👇"
        await vc.send(msg, view=control_panel)

        await interaction.response.send_message(
            f"🏨 {vc_name} を作成しました！（24時間後に自動削除）",
            ephemeral=True
        )

 　　　　# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
        # 📌 チェックインログ（embed）
        # ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
        log_channel = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_channel:
            embed = discord.Embed(
                title="🏨 高級ホテル：チェックイン",
                color=0xF4D03F
            )
            embed.add_field(name="ユーザー", value=user.mention, inline=False)
            embed.add_field(name="ルーム名", value=vc_name, inline=False)
            embed.add_field(
                name="チェックイン時刻",
                value=f"<t:{int(datetime.utcnow().timestamp())}:F>",
                inline=False
            )
            embed.add_field(
                name="自動削除予定",
                value=f"<t:{int(expire.timestamp())}:F>",
                inline=False
            )
            embed.add_field(
                name="VC ID",
                value=str(vc.id),
                inline=False
            )

            await log_channel.send(embed=embed)

