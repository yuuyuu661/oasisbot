import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta


class HotelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

        # 権限チェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

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
                ticket_price_30=$7
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

        # 権限チェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        hotel_config = await self.bot.db.conn.fetchrow(
            "SELECT * FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )

        if not hotel_config:
            return await interaction.response.send_message("❌ ホテル初期設定がまだ行われていません。", ephemeral=True)

        embed = discord.Embed(title=title, description=description, color=0xF4D03F)

        view = HotelPanelView(hotel_config)

        await interaction.response.send_message(embed=embed, view=view)

    # ======================================================
    # /チケット確認
    # ======================================================
    @app_commands.command(name="チケット確認", description="自分の所持チケット数を確認します")
    async def check_ticket(self, interaction: discord.Interaction):

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        count = await self.bot.db.get_tickets(user_id, guild_id)

        await interaction.response.send_message(
            f"🎫 現在の所持チケット: **{count}枚**",
            ephemeral=True
        )


# ======================================================
# ホテルパネルの View（チェックイン / チケット購入）
# ======================================================

class HotelPanelView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)
        self.config = config

        self.add_item(CheckinButton(config))
        self.add_item(TicketBuyDropdown(config))


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
        guild_id = str(guild.id)
        user_id = str(user.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        # 1人1室チェック
        existing = await interaction.client.db.conn.fetchval(
            "SELECT channel_id FROM hotel_rooms WHERE owner_id=$1 AND guild_id=$2",
            user_id, guild_id
        )
        if existing:
            return await interaction.response.send_message(
                "⚠ すでにあなた専用のホテルルームがあります。",
                ephemeral=True
            )

        # チケット消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        # VC作成場所 → パネルが送られたチャンネルと同じカテゴリ
        category = interaction.channel.category

        # VC名
        vc_name = f"{user.name}の高級ホテル"

        # VC作成
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
            user: discord.PermissionOverwrite(connect=True, view_channel=True)
        }

        manager_role = guild.get_role(int(self.config["manager_role"]))
        if manager_role:
            overwrites[manager_role] = discord.PermissionOverwrite(connect=True, view_channel=True)

        vc = await category.create_voice_channel(
            name=vc_name,
            overwrites=overwrites,
            user_limit=2
        )

        # 24時間後の期限
        expire = datetime.utcnow() + timedelta(hours=24)

        # DB保存
        await interaction.client.db.save_room(
            str(vc.id), guild_id, user_id, expire
        )

        await interaction.response.send_message(
            f"🏨 **{vc_name}** を作成しました！\n削除期限：24時間後",
            ephemeral=True
        )


# ======================================================
# チケット購入プルダウン
# ======================================================

class TicketBuyDropdown(discord.ui.Select):
    def __init__(self, config):

        options = [
            discord.SelectOption(label=f"1枚購入（{config['ticket_price_1']} rrc）", value="1"),
            discord.SelectOption(label=f"10枚購入（{config['ticket_price_10']} rrc）", value="10"),
            discord.SelectOption(label=f"30枚購入（{config['ticket_price_30']} rrc）", value="30"),
        ]

        super().__init__(placeholder="購入する枚数を選択…", min_values=1, max_values=1, options=options)
        self.config = config

    async def callback(self, interaction: discord.Interaction):

        choice = self.values[0]

        if choice == "1":
            price = self.config["ticket_price_1"]
            amount = 1
        elif choice == "10":
            price = self.config["ticket_price_10"]
            amount = 10
        else:
            price = self.config["ticket_price_30"]
            amount = 30

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # 残高確認
        user_data = await interaction.client.db.get_user(user_id, guild_id)
        if user_data["balance"] < price:
            return await interaction.response.send_message("❌ 残高が不足しています。", ephemeral=True)

        # 購入処理
        await interaction.client.db.remove_balance(user_id, guild_id, price)
        await interaction.client.db.add_tickets(user_id, guild_id, amount)

        # ログ
        log_ch = interaction.guild.get_channel(int(self.config["log_channel"]))
        if log_ch:
            await log_ch.send(
                f"🎫 {interaction.user.mention} が **{amount}枚** のチケットを購入しました。 （{price}rrc）"
            )

        await interaction.response.send_message(
            f"🎫 **チケット{amount}枚** を購入しました！",
            ephemeral=True
        )


# ======================================================
# setup
# ======================================================

async def setup(bot):
    cog = HotelCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
