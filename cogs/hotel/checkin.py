import discord
from datetime import datetime, timedelta

from .room_panel import HotelRoomControlPanel

CATEGORY_CHILD_LIMIT = 50


def _pick_available_category(guild: discord.Guild, category_ids: list[str]) -> discord.CategoryChannel | None:
    for cid in category_ids:
        cat = guild.get_channel(int(cid))
        if isinstance(cat, discord.CategoryChannel) and len(cat.channels) < CATEGORY_CHILD_LIMIT:
            return cat
    return None


class CheckinButton(discord.ui.Button):
    def __init__(self, config, guild_id: str):
        super().__init__(
            label="チェックイン（1枚消費）",
            style=discord.ButtonStyle.green,
            custom_id=f"hotel_checkin_{guild_id}",
        )
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        guild_id = str(guild.id)
        user_id = str(user.id)

        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        existing = await interaction.client.db.conn.fetchval(
            "SELECT channel_id FROM hotel_rooms WHERE owner_id=$1 AND guild_id=$2",
            user_id, guild_id
        )
        if existing:
            return await interaction.response.send_message("⚠ すでにルームがあります。", ephemeral=True)

        # 作成先カテゴリ選択（category_ids優先、無ければ従来挙動）
        category_ids = self.config.get("category_ids") or []
        category = None

        if isinstance(category_ids, (list, tuple)) and len(category_ids) > 0:
            category = _pick_available_category(guild, list(category_ids))
            if category is None:
                return await interaction.response.send_message(
                    "❌ 高級ホテル用カテゴリが満杯です。管理者に空きカテゴリ追加または整理を依頼してください。",
                    ephemeral=True
                )

        if category is None:
            category = interaction.channel.category

        if category is None:
            return await interaction.response.send_message(
                "❌ 作成先カテゴリが決められません。ホテル初期設定でカテゴリを指定してください。",
                ephemeral=True
            )

        # チケット消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        vc_name = f"{user.name}の高級ホテル"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
            user: discord.PermissionOverwrite(connect=True, view_channel=True),
        }

        manager_role = guild.get_role(int(self.config["manager_role"]))
        if manager_role:
            overwrites[manager_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

        vc = await category.create_voice_channel(
            name=vc_name, overwrites=overwrites, user_limit=2
        )

        expire = datetime.utcnow() + timedelta(hours=24)
        await interaction.client.db.save_room(str(vc.id), guild_id, user_id, expire)

        from .room_panel import HotelRoomControlPanel
        control_panel = HotelRoomControlPanel()

        msg = f"🏨 **{vc_name}** へようこそ！\nこちらが操作パネルです👇"
        await vc.send(msg, view=control_panel)

        await interaction.response.send_message(
            f"🏨 {vc_name} を作成しました！（24時間後に自動削除）",
            ephemeral=True
        )

        log_channel = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_channel:
            embed = discord.Embed(title="🏨 高級ホテル：チェックイン", color=0xF4D03F)
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
            embed.add_field(name="VC ID", value=str(vc.id), inline=False)
            await log_channel.send(embed=embed)
