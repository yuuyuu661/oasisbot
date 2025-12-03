import discord
from datetime import datetime, timedelta


# ======================================================
# ① 人数制限 +1（チケット1枚）
# ======================================================

class RoomAddMemberLimitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="人数制限 +1（1枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        if not isinstance(vc, discord.VoiceChannel):
            return await interaction.response.send_message("❌ VC内でのみ使用できます。", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケット不足です。", ephemeral=True)

        # DB確認
        room = await interaction.client.db.get_room(str(vc.id))
        if not room:
            return await interaction.response.send_message("❌ ルーム情報が見つかりません。", ephemeral=True)

        # 消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        # 上限追加
        new_limit = (vc.user_limit or 0) + 1
        await vc.edit(user_limit=new_limit)

        await interaction.response.send_message(
            f"👥 人数制限を **{new_limit}人** に更新しました！（1枚消費）",
            ephemeral=True
        )


# ======================================================
# ② VC名変更（無料）
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
# ③ 接続許可（無料）
# ======================================================

class RoomAllowMemberButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="接続許可（ユーザーID入力）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):

        class AllowModal(discord.ui.Modal, title="接続許可"):
            user_input = discord.ui.TextInput(
                label="ユーザーID または メンション",
                placeholder="例）123456789012345678 or @ユーザー",
                required=True
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                raw = self.user_input.value.strip()

                # メンション → ID 取得
                if raw.startswith("<@") and raw.endswith(">"):
                    raw = raw.replace("<@", "").replace(">", "").replace("!", "")

                if not raw.isdigit():
                    return await modal_interaction.response.send_message(
                        "❌ ユーザーIDが正しくありません。",
                        ephemeral=True
                    )

                user_id = int(raw)
                member = modal_interaction.guild.get_member(user_id)

                if member is None:
                    return await modal_interaction.response.send_message(
                        "❌ メンバーが見つかりません。",
                        ephemeral=True
                    )

                vc = modal_interaction.channel
                await vc.set_permissions(member, connect=True, view_channel=True)

                await modal_interaction.response.send_message(
                    f"👤 {member.mention} を接続許可しました！",
                    ephemeral=True
                )

        await interaction.response.send_modal(AllowModal())



# ======================================================
# ④ 接続拒否（無料）
# ======================================================

class RoomDenyMemberButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="接続拒否（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild
        vc = interaction.channel

        allowed = [
            m for m in vc.overwrites
            if isinstance(m, discord.Member) and vc.overwrites[m].view_channel
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
                    placeholder="接続拒否するユーザーを選択",
                    options=options,
                    min_values=1,
                    max_values=1
                )

            async def callback(self, si: discord.Interaction):
                target = guild.get_member(int(self.values[0]))

                await vc.set_permissions(target, connect=False, view_channel=False)
                await si.response.send_message(
                    f"🚫 **{target.display_name}** の接続許可を削除しました。",
                    ephemeral=True
                )

        v = discord.ui.View()
        v.add_item(DenySelect())

        await interaction.response.send_message(
            "接続拒否するユーザーを選択してください👇",
            view=v,
            ephemeral=True
        )


# ======================================================
# ⑤ 1日延長（1枚）
# ======================================================

class RoomAdd1DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="1日延長（1枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        if not isinstance(vc, discord.VoiceChannel):
            return await interaction.response.send_message("❌ VC内のみ使用できます。", ephemeral=True)

        room = await interaction.client.db.get_room(str(vc.id))
        if not room:
            return await interaction.response.send_message("❌ ルーム情報がありません。", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケット不足です。", ephemeral=True)

        expire = room["expire_at"] + timedelta(days=1)
        await interaction.client.db.save_room(str(vc.id), guild_id, room["owner_id"], expire)
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        await interaction.response.send_message("⏳ **1日延長しました！**", ephemeral=True)


# ======================================================
# ⑥ 3日延長（3枚）
# ======================================================

class RoomAdd3DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="3日延長（3枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 3:
            return await interaction.response.send_message("❌ チケット不足です。", ephemeral=True)

        room = await interaction.client.db.get_room(str(vc.id))
        expire = room["expire_at"] + timedelta(days=3)

        await interaction.client.db.save_room(str(vc.id), guild_id, room["owner_id"], expire)
        await interaction.client.db.remove_tickets(user_id, guild_id, 3)

        await interaction.response.send_message("⏳ **3日延長しました！**", ephemeral=True)


# ======================================================
# ⑦ 10日延長（10枚）
# ======================================================

class RoomAdd10DayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="10日延長（10枚）", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 10:
            return await interaction.response.send_message("❌ チケット不足です。", ephemeral=True)

        room = await interaction.client.db.get_room(str(vc.id))
        expire = room["expire_at"] + timedelta(days=10)

        await interaction.client.db.save_room(str(vc.id), guild_id, room["owner_id"], expire)
        await interaction.client.db.remove_tickets(user_id, guild_id, 10)

        await interaction.response.send_message("⏳ **10日延長しました！**", ephemeral=True)


# ======================================================
# ⑧ サブ垢追加（無料）
# ======================================================

class RoomAddSubRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="サブ垢追加（無料）", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        guild = interaction.guild

        sub_role = guild.get_role(interaction.view.sub_role_id)
        if not sub_role:
            return await interaction.response.send_message("❌ サブ垢ロールが見つかりません。", ephemeral=True)

        members = [m for m in guild.members if sub_role in m.roles]

        for m in members:
            await vc.set_permissions(m, view_channel=True, connect=True)

        await interaction.response.send_message(
            f"👥 サブ垢ロール所持者 **{len(members)}名** を追加しました！",
            ephemeral=True
        )


# ======================================================
# ⑨ 削除期限確認（無料）
# ======================================================

class RoomCheckExpireButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="削除期限確認（無料）", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):

        vc = interaction.channel
        room = await interaction.client.db.get_room(str(vc.id))

        expire = room["expire_at"]
        now = datetime.utcnow()
        diff = expire - now

        hours = int(diff.total_seconds() // 3600)
        minutes = int((diff.total_seconds() % 3600) // 60)

        await interaction.response.send_message(
            f"⏳ この部屋は **{hours}時間 {minutes}分後** に削除されます。",
            ephemeral=True
        )


# ======================================================
# ⑩ チケット確認（無料）
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

