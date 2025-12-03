# cogs/hotel/room_buttons.py

import discord
from datetime import timedelta, datetime


# ======================================================
# 共通基底クラス（親View参照を保持）
# ======================================================
class HotelButtonBase(discord.ui.Button):
    def __init__(self, parent, label, style):
        super().__init__(label=label, style=style)
        self.parent = parent  # ← これが超重要！


# ======================================================
# ① 人数制限 +1（1枚）
# ======================================================
class RoomAddMemberLimitButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "人数 +1（1枚）", discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.channel
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # チケット判定
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケット不足です。", ephemeral=True)

        # 消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        new_limit = (vc.user_limit or 2) + 1
        await vc.edit(user_limit=new_limit)

        await interaction.response.send_message(
            f"👥 人数上限を **{new_limit}人** に増やしました。",
            ephemeral=True
        )


# ======================================================
# ② VC名変更
# ======================================================
class RoomRenameButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "VC名変更（無料）", discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):

        class RenameModal(discord.ui.Modal, title="VC名変更"):
            new_name = discord.ui.TextInput(label="新しいVC名", max_length=50)

            async def on_submit(self, modal_interaction: discord.Interaction):
                vc = modal_interaction.channel
                await vc.edit(name=self.new_name.value)
                await modal_interaction.response.send_message(
                    f"✏️ 名称変更 → **{self.new_name.value}**",
                    ephemeral=True
                )

        await interaction.response.send_modal(RenameModal())


# ======================================================
# ③ 接続許可（ID検索対応）
# ======================================================
class RoomAllowMemberButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "接続許可（無料）", discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):

        class AllowModal(discord.ui.Modal, title="接続許可ユーザーID入力"):
            user_id_input = discord.ui.TextInput(
                label="ユーザーID",
                placeholder="例: 123456789012345678",
                required=True
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                user_id = self.user_id_input.value
                member = modal_interaction.guild.get_member(int(user_id))

                if not member:
                    return await modal_interaction.response.send_message(
                        "❌ 該当ユーザーが見つかりません。",
                        ephemeral=True
                    )

                vc = modal_interaction.channel
                await vc.set_permissions(member, connect=True, view_channel=True)

                await modal_interaction.response.send_message(
                    f"👤 **{member.display_name}** に接続権限を付与しました！",
                    ephemeral=True
                )

        await interaction.response.send_modal(AllowModal())


# ======================================================
# ④ 接続拒否
# ======================================================
class RoomDenyMemberButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "接続拒否（無料）", discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel

        allowed = [
            m for m, perms in vc.overwrites.items()
            if isinstance(m, discord.Member) and perms.view_channel
        ]

        if not allowed:
            return await interaction.response.send_message(
                "⚠ 現在許可済みユーザーはいません。",
                ephemeral=True
            )

        class DenySelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="拒否するユーザーを選択",
                    min_values=1,
                    max_values=1,
                    options=[
                        discord.SelectOption(
                            label=m.display_name,
                            value=str(m.id)
                        ) for m in allowed
                    ]
                )

            async def callback(self, select_interaction: discord.Interaction):
                target = vc.guild.get_member(int(self.values[0]))
                await vc.set_permissions(target, connect=False, view_channel=False)

                await select_interaction.response.send_message(
                    f"🚫 接続拒否 → {target.display_name}",
                    ephemeral=True
                )

        view = discord.ui.View()
        view.add_item(DenySelect())
        await interaction.response.send_message("拒否ユーザーを選択👇", view=view, ephemeral=True)


# ======================================================
# ⑤ 1日延長
# ======================================================
class RoomAdd1DayButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "1日延長（1枚）", discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.channel
        db = interaction.client.db
        room = await db.get_room(str(vc.id))

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        tickets = await db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケット不足。", ephemeral=True)

        expire = room["expire_at"] + timedelta(days=1)
        await db.save_room(str(vc.id), guild_id, room["owner_id"], expire)
        await db.remove_tickets(user_id, guild_id, 1)

        await interaction.response.send_message("⏳ **1日延長しました！**", ephemeral=True)


# ======================================================
# ⑥ 3日延長
# ======================================================
class RoomAdd3DayButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "3日延長（3枚）", discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.channel
        db = interaction.client.db
        room = await db.get_room(str(vc.id))

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await db.get_tickets(user_id, guild_id)
        if tickets < 3:
            return await interaction.response.send_message("❌ チケット不足。", ephemeral=True)

        expire = room["expire_at"] + timedelta(days=3)
        await db.save_room(str(vc.id), guild_id, room["owner_id"], expire)
        await db.remove_tickets(user_id, guild_id, 3)

        await interaction.response.send_message("⏳ **3日延長しました！**", ephemeral=True)


# ======================================================
# ⑦ 10日延長
# ======================================================
class RoomAdd10DayButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "10日延長（10枚）", discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.channel
        db = interaction.client.db
        room = await db.get_room(str(vc.id))

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await db.get_tickets(user_id, guild_id)
        if tickets < 10:
            return await interaction.response.send_message("❌ チケット不足。", ephemeral=True)

        expire = room["expire_at"] + timedelta(days=10)
        await db.save_room(str(vc.id), guild_id, room["owner_id"], expire)
        await db.remove_tickets(user_id, guild_id, 10)

        await interaction.response.send_message("⏳ **10日延長しました！**", ephemeral=True)


# ======================================================
# ⑧ サブ垢追加（人数 +1 のみ）
# ======================================================
class RoomAddSubRoleButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "サブ垢追加（無料）", discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.channel

        new_limit = (vc.user_limit or 2) + 1
        await vc.edit(user_limit=new_limit)

        await interaction.response.send_message(
            f"👥 **サブ垢枠 +1！** → 新上限：{new_limit}人",
            ephemeral=True
        )


# ======================================================
# ⑨ 期限確認
# ======================================================
class RoomCheckExpireButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "削除期限確認", discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.channel

        room = await interaction.client.db.get_room(str(vc.id))
        expire = room["expire_at"]

        left = expire - datetime.utcnow()
        hours = int(left.total_seconds() // 3600)
        minutes = int((left.total_seconds() % 3600) // 60)

        await interaction.response.send_message(
            f"⏳ 削除まで **{hours}時間 {minutes}分**",
            ephemeral=True
        )


# ======================================================
# ⑩ チケット確認
# ======================================================
class RoomCheckTicketsButton(HotelButtonBase):
    def __init__(self, parent):
        super().__init__(parent, "チケット確認", discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await interaction.client.db.get_tickets(user_id, guild_id)

        await interaction.response.send_message(
            f"🎫 所持チケット → **{tickets}枚**",
            ephemeral=True
        )
