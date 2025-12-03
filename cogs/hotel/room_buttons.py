# cogs/hotel/room_buttons.py

import discord
from discord.ext import commands
from datetime import datetime, timedelta


# ======================================================
# 共通：ルーム情報取得
# ======================================================

async def get_room(interaction):
    vc = interaction.channel
    if not isinstance(vc, discord.VoiceChannel):
        await interaction.response.send_message("❌ VC 内でのみ使用できます。", ephemeral=True)
        return None, None

    room = await interaction.client.db.get_room(str(vc.id))
    if not room:
        await interaction.response.send_message("❌ ルーム情報が見つかりません。", ephemeral=True)
        return None, None

    return vc, room


# ======================================================
# ① 人数制限 +1（チケット1枚消費）
# ======================================================

class RoomAddMemberLimitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="人数制限 +1（1枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        vc, room = await get_room(interaction)
        if vc is None:
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

        # 延長処理
        new_limit = vc.user_limit + 1
        await vc.edit(user_limit=new_limit)

        # チケット消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        await interaction.response.send_message(
            f"👥 最大人数を **{new_limit}人** に増やしました！（1枚消費）",
            ephemeral=True
        )


# ======================================================
# ② VC名変更（モーダル）
# ======================================================

class RoomRenameButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="VC名変更（無料）", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        class RenameModal(discord.ui.Modal, title="VC名変更"):
            new_name = discord.ui.TextInput(label="新しいVC名", max_length=50)

            async def on_submit(self, modal_inter: discord.Interaction):
                vc = modal_inter.channel
                if isinstance(vc, discord.VoiceChannel):
                    await vc.edit(name=self.new_name.value)
                    await modal_inter.response.send_message(
                        f"✏️ VC名を **{self.new_name.value}** に変更しました！",
                        ephemeral=True
                    )

        await interaction.response.send_modal(RenameModal())


# ======================================================
# ③ 接続許可（ID / 名前検索）
# ======================================================

class RoomAllowMemberButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="接続許可（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):

        class AllowModal(discord.ui.Modal, title="接続許可・ユーザー検索"):
            query = discord.ui.TextInput(
                label="ユーザーID または 名前（部分一致OK）",
                required=True
            )

            async def on_submit(self, modal_inter: discord.Interaction):
                guild = modal_inter.guild
                vc = modal_inter.channel

                keyword = self.query.value

                # ID検索
                target = guild.get_member_named(keyword) or None

                # ID直接
                if keyword.isdigit():
                    target = guild.get_member(int(keyword))

                # 部分一致
                if not target:
                    for m in guild.members:
                        if keyword.lower() in m.display_name.lower():
                            target = m
                            break

                if not target:
                    return await modal_inter.response.send_message(
                        "❌ 該当ユーザーが見つかりません。",
                        ephemeral=True
                    )

                await vc.set_permissions(target, connect=True, view_channel=True)

                await modal_inter.response.send_message(
                    f"👤 **{target.display_name}** に接続許可を付与しました！",
                    ephemeral=True
                )

        await interaction.response.send_modal(AllowModal())


# ======================================================
# ④ 接続拒否（現在許可しているユーザー一覧）
# ======================================================

class RoomDenyMemberButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="接続拒否（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        vc, room = await get_room(interaction)
        if vc is None:
            return

        allowed = [
            m for m, overwrite in vc.overwrites.items()
            if isinstance(m, discord.Member)
            and overwrite.view_channel
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
                super().__init__(placeholder="拒否するユーザーを選択", options=options)

            async def callback(self, select_inter: discord.Interaction):
                target = interaction.guild.get_member(int(self.values[0]))
                await vc.set_permissions(target, view_channel=False, connect=False)

                await select_inter.response.send_message(
                    f"🚫 **{target.display_name}** の接続許可を削除しました。",
                    ephemeral=True
                )

        view = discord.ui.View()
        view.add_item(DenySelect())
        await interaction.response.send_message(
            "拒否するユーザーを選択してください👇",
            view=view,
            ephemeral=True
        )


# ======================================================
# ⑤ 1日延長（1枚）
# ======================================================

class RoomAdd1DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="1日延長（1枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        await apply_extension(interaction, days=1, cost=1)


# ======================================================
# ⑥ 3日延長（3枚）
# ======================================================

class RoomAdd3DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="3日延長（3枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        await apply_extension(interaction, days=3, cost=3)


# ======================================================
# ⑦ 10日延長（10枚）
# ======================================================

class RoomAdd10DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="10日延長（10枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        await apply_extension(interaction, days=10, cost=10)


# ======================================================
# 延長共通処理
# ======================================================

async def apply_extension(interaction, days, cost):
    vc, room = await get_room(interaction)
    if vc is None:
        return

    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    # チケット確認
    tickets = await interaction.client.db.get_tickets(user_id, guild_id)
    if tickets < cost:
        return await interaction.response.send_message("❌ チケットが不足しています。", ephemeral=True)

    # 延長
    new_expire = room["expire_at"] + timedelta(days=days)
    await interaction.client.db.save_room(str(vc.id), guild_id, room["owner_id"], new_expire)

    # 消費
    await interaction.client.db.remove_tickets(user_id, guild_id, cost)

    await interaction.response.send_message(
        f"⏳ **{days}日延長** しました！（{cost}枚消費）",
        ephemeral=True
    )

    # ログ送信
    settings = await interaction.client.db.conn.fetchrow(
        "SELECT log_channel FROM hotel_settings WHERE guild_id=$1",
        guild_id
    )
    log_ch = interaction.guild.get_channel(int(settings["log_channel"]))

    if log_ch:
        embed = discord.Embed(
            title="⏳ 高級ホテル：期限延長",
            color=0xF4D03F
        )
        embed.add_field(name="ユーザー", value=interaction.user.mention, inline=False)
        embed.add_field(name="延長日数", value=f"{days}日", inline=True)
        embed.add_field(name="新しい削除予定", value=f"<t:{int(new_expire.timestamp())}:F>")
        embed.add_field(name="VC", value=f"{vc.name}", inline=False)

        await log_ch.send(embed=embed)


# ======================================================
# ⑧ サブ垢追加（人数+1 ＆ サブ垢ロール持ち1名のみ追加）
# ======================================================

class RoomAddSubRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="サブ垢追加（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        vc, room = await get_room(interaction)
        if vc is None:
            return

        sub_role_id = interaction.view.sub_role_id
        sub_role = interaction.guild.get_role(sub_role_id)

        if not sub_role:
            return await interaction.response.send_message("❌ サブ垢ロールが見つかりません。", ephemeral=True)

        # モーダルでユーザー検索
        class SubAddModal(discord.ui.Modal, title="サブ垢追加・ユーザー検索"):
            query = discord.ui.TextInput(label="ユーザーID または 名前", required=True)

            async def on_submit(self, modal_inter: discord.Interaction):
                keyword = self.query.value
                guild = modal_inter.guild

                target = None

                # ID一致
                if keyword.isdigit():
                    target = guild.get_member(int(keyword))

                # 名前一致
                if not target:
                    for m in guild.members:
                        if keyword.lower() in m.display_name.lower():
                            target = m
                            break

                if not target:
                    return await modal_inter.response.send_message("❌ 見つかりません。", ephemeral=True)

                # サブ垢ロールを持っているかチェック
                if sub_role not in target.roles:
                    return await modal_inter.response.send_message(
                        "❌ このユーザーはサブ垢ロールを持っていません。",
                        ephemeral=True
                    )

                # VC人数+1
                new_limit = vc.user_limit + 1
                await vc.edit(user_limit=new_limit)

                # 権限付与
                await vc.set_permissions(target, view_channel=True, connect=True)

                await modal_inter.response.send_message(
                    f"👥 サブ垢ユーザー **{target.display_name}** を追加しました！（人数上限 {new_limit}）",
                    ephemeral=True
                )

        await interaction.response.send_modal(SubAddModal())


# ======================================================
# ⑨ 削除期限確認
# ======================================================

class RoomCheckExpireButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="削除期限を確認（無料）", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        vc, room = await get_room(interaction)
        if vc is None:
            return

        expire = room["expire_at"]

        left = expire - datetime.utcnow()
        hours = int(left.total_seconds() // 3600)
        minutes = int((left.total_seconds() % 3600) // 60)

        await interaction.response.send_message(
            f"⏳ 削除まで **{hours}時間 {minutes}分** です。",
            ephemeral=True
        )


# ======================================================
# ⑩ チケット確認
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
# Cog（外部登録用）
# ======================================================

class RoomButtonsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
