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
        view = HotelPanelView(hotel_config)

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
# --- パネルビュー（チェックイン・チケット購入） ---
# ======================================================

class HotelPanelView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)
        self.config = config

        self.add_item(CheckinButton(config))
        self.add_item(TicketBuyDropdown(config))


# ======================================================
# --- チェックインボタン ---
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
            name=vc_name,
            overwrites=overwrites,
            user_limit=2
        )

        # 期限 24h
        expire = datetime.utcnow() + timedelta(hours=24)

        await interaction.client.db.save_room(
            str(vc.id), guild_id, user_id, expire
        )

        # --- ここで操作パネルを VC チャットへ送信 ---
        text_view = HotelRoomControlPanel(
            owner_id=user_id,
            manager_role_id=self.config["manager_role"],
            sub_role_id=self.config["sub_role"],
            config=self.config
        )

        await vc.send(
            f"🏨 **{vc_name}** へようこそ！\nこちらが操作パネルです👇",
            view=text_view
        )

        await interaction.response.send_message(
            f"🏨 {vc_name} を作成しました！（24時間後に自動削除）",
            ephemeral=True
        )
        # ======================================================
        # --- 高級ホテル 操作パネル（VCチャット用） ---
        # ======================================================

        class HotelRoomControlPanel(discord.ui.View):
        def __init__(self, owner_id, manager_role_id, sub_role_id, config):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.manager_role_id = int(manager_role_id)
        self.sub_role_id = int(sub_role_id)
        self.config = config

        # ▼ 10ボタン
        self.add_item(RoomAddMemberLimitButton())
        self.add_item(RoomRenameButton())
        self.add_item(RoomAllowMemberButton())
        self.add_item(RoomDenyMemberButton())
        self.add_item(RoomAdd1DayButton())
        self.add_item(RoomAdd3DayButton())
        self.add_item(RoomAdd10DayButton())
        self.add_item(RoomAddSubRoleButton())
        self.add_item(RoomCheckExpireButton())
        self.add_item(RoomCheckTicketsButton())

    # 共通：操作権限チェック
    async def interaction_check(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        # ホテル管理者 or ルーム所有者
        if str(user.id) == str(self.owner_id):
            return True

        manager_role = guild.get_role(self.manager_role_id)
        if manager_role in user.roles:
            return True

        await interaction.response.send_message(
            "❌ このパネルを操作できるのは「チェックインした本人」と「ホテル管理人ロール」のみです。",
            ephemeral=True
        )
        return False

  
        # ======================================================
        # --- ① 人数制限 +1（チケット1枚消費） ---
        # ======================================================

        class RoomAddMemberLimitButton(discord.ui.Button):
        def __init__(self):
        super().__init__(label="人数制限 +1（1枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.channel  # VCチャット → channel は VoiceChannel
        if not isinstance(vc, discord.VoiceChannel):
            return await interaction.response.send_message("❌ VC内でのみ使用できます。", ephemeral=True)

        # DB確認 → owner_id とギルド
        room = await interaction.client.db.get_room(str(vc.id))
        if not room:
            return await interaction.response.send_message("❌ ルーム情報が見つかりません。", ephemeral=True)

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        # 消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        # 人数追加
        new_limit = vc.user_limit + 1
        await vc.edit(user_limit=new_limit)

        await interaction.response.send_message(
            f"👥 ルームの人数制限を **{new_limit}人** に増やしました！（チケット1枚消費）",
            ephemeral=True
        )


        # ======================================================
        # --- ② VC名変更（無料） ---
        # ======================================================

        class RoomRenameButton(discord.ui.Button):
        def __init__(self):
        super().__init__(label="VC名変更（無料）", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):

        class RenameModal(discord.ui.Modal, title="VC名変更"):
            new_name = discord.ui.TextInput(label="新しいVC名", max_length=50)

            async def on_submit(self, modal_interaction: discord.Interaction):
                vc = modal_interaction.channel
                if isinstance(vc, discord.VoiceChannel):
                    await vc.edit(name=self.new_name.value)
                    await modal_interaction.response.send_message(
                        f"✏️ VC名を **{self.new_name.value}** に変更しました！",
                        ephemeral=True
                    )

        await interaction.response.send_modal(RenameModal())


# ======================================================
# --- ③ 接続許可（無料） ---
# ======================================================

class RoomAllowMemberButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="接続許可（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        vc = interaction.channel

        members = [m for m in guild.members if not m.bot]

        # ▼ ユーザー選択
        class AllowSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=m.display_name, value=str(m.id))
                    for m in members
                ]
                super().__init__(
                    placeholder="閲覧/接続を許可するユーザーを選択…",
                    min_values=1,
                    max_values=1,
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):
                target_id = int(self.values[0])
                target = guild.get_member(target_id)
                await vc.set_permissions(target, connect=True, view_channel=True)

                await select_interaction.response.send_message(
                    f"👤 **{target.display_name}** に接続許可を付与しました！",
                    ephemeral=True
                )

        view = discord.ui.View()
        view.add_item(AllowSelect())

        await interaction.response.send_message("許可するユーザーを選んでください👇", view=view, ephemeral=True)


# ======================================================
# --- ④ 接続拒否（無料） ---
# ======================================================

class RoomDenyMemberButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="接続拒否（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        vc = interaction.channel

        # 許可済みユーザー＝permissionが付与されているユーザー
        allowed = [
            p for p in vc.overwrites
            if isinstance(p, discord.Member) and vc.overwrites[p].view_channel
        ]

        if not allowed:
            return await interaction.response.send_message(
                "⚠ 現在、許可されているユーザーはいません。",
                ephemeral=True
            )

        class DenySelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=m.display_name, value=str(m.id))
                    for m in allowed
                ]
                super().__init__(
                    placeholder="拒否するユーザーを選択…",
                    min_values=1,
                    max_values=1,
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):
                target_id = int(self.values[0])
                target = guild.get_member(target_id)

                await vc.set_permissions(target, connect=False, view_channel=False)

                await select_interaction.response.send_message(
                    f"🚫 **{target.display_name}** の接続許可を削除しました。",
                    ephemeral=True
                )

        view = discord.ui.View()
        view.add_item(DenySelect())

        await interaction.response.send_message("拒否するユーザーを選択してください👇", view=view, ephemeral=True)
# ======================================================
# --- ⑤ 1日追加（1枚消費） ---
# ======================================================

class RoomAdd1DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="1日延長（1枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        if not isinstance(vc, discord.VoiceChannel):
            return await interaction.response.send_message("❌ VC内のみ使用できます。", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        room = await interaction.client.db.get_room(str(vc.id))
        if not room:
            return await interaction.response.send_message("❌ ルーム情報がありません。", ephemeral=True)

        expire = room["expire_at"] + timedelta(days=1)
        await interaction.client.db.save_room(str(vc.id), guild_id, room["owner_id"], expire)

        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        await interaction.response.send_message(
            "⏳ **1日延長** しました！",
            ephemeral=True
        )


# ======================================================
# --- ⑥ 3日追加（3枚消費） ---
# ======================================================

class RoomAdd3DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="3日延長（3枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        guild = interaction.guild
        guild_id = str(guild.id)
        user_id = str(interaction.user.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 3:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        room = await interaction.client.db.get_room(str(vc.id))
        if not room:
            return await interaction.response.send_message("❌ ルーム情報がありません。", ephemeral=True)

        expire = room["expire_at"] + timedelta(days=3)
        await interaction.client.db.save_room(str(vc.id), guild_id, room["owner_id"], expire)

        await interaction.client.db.remove_tickets(user_id, guild_id, 3)

        await interaction.response.send_message(
            "⏳ **3日延長しました！**",
            ephemeral=True
        )


# ======================================================
# --- ⑦ 10日追加（10枚消費） ---
# ======================================================

class RoomAdd10DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="10日延長（10枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 10:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        room = await interaction.client.db.get_room(str(vc.id))
        if not room:
            return await interaction.response.send_message("❌ ルーム情報がありません。", ephemeral=True)

        expire = room["expire_at"] + timedelta(days=10)
        await interaction.client.db.save_room(str(vc.id), guild_id, room["owner_id"], expire)

        await interaction.client.db.remove_tickets(user_id, guild_id, 10)

        await interaction.response.send_message(
            "⏳ **10日延長しました！**",
            ephemeral=True
        )


# ======================================================
# --- ⑧ サブ垢追加（無料） ---
# ======================================================

class RoomAddSubRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="サブ垢追加（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        guild = interaction.guild

        sub_role_id = interaction.view.sub_role_id
        sub_role = guild.get_role(sub_role_id)

        if not sub_role:
            return await interaction.response.send_message("❌ サブ垢ロールが見つかりません。", ephemeral=True)

        members = [m for m in guild.members if sub_role in m.roles]

        if not members:
            return await interaction.response.send_message("⚠ サブ垢ロールのユーザーがいません。", ephemeral=True)

        for m in members:
            await vc.set_permissions(m, connect=True, view_channel=True)

        await interaction.response.send_message(
            f"👥 サブ垢ロールのユーザー **{len(members)}名** を追加しました。",
            ephemeral=True
        )


# ======================================================
# --- ⑨ 期限確認（無料） ---
# ======================================================

class RoomCheckExpireButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="削除期限を確認（無料）", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        room = await interaction.client.db.get_room(str(vc.id))

        if not room:
            return await interaction.response.send_message("❌ ルーム情報が存在しません。", ephemeral=True)

        expire = room["expire_at"]
        now = datetime.utcnow()
        left = expire - now

        hours = int(left.total_seconds() // 3600)
        minutes = int((left.total_seconds() % 3600) // 60)

        await interaction.response.send_message(
            f"⏳ 削除まで **{hours}時間 {minutes}分** です。",
            ephemeral=True
        )


# ======================================================
# --- ⑩ チケット確認（無料） ---
# ======================================================

class RoomCheckTicketsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="チケット確認（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await interaction.client.db.get_tickets(user_id, guild_id)

        await interaction.response.send_message(
            f"🎫 現在の所持チケット: **{tickets}枚**",
            ephemeral=True
        )


# ======================================================
# --- setup ---
# ======================================================

async def setup(bot):
    cog = HotelCog(bot)
    await bot.add_cog(cog)

    # guild 固定同期
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
