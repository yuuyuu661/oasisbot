import discord

from .room_buttons import (
    RoomAddMemberLimitButton,
    RoomRenameButton,
    RoomAllowMemberButton,
    RoomDenyMemberButton,
    RoomAdd1DayButton,
    RoomAdd3DayButton,
    RoomAdd10DayButton,
    RoomAddSubRoleButton,
    RoomCheckExpireButton,
    RoomCheckTicketsButton,
)


class HotelRoomControlPanel(discord.ui.View):
    """
    高級ホテルの操作パネル（VC内に生成されるメニュー）
    """
    def __init__(self, owner_id, manager_role_id, sub_role_id, config):
        super().__init__(timeout=None)
        self.owner_id = str(owner_id)
        self.manager_role_id = int(manager_role_id)
        self.sub_role_id = int(sub_role_id)
        self.config = config

        # ▼ 10ボタンを登録
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

    # --------------------------------------------------
    # 共通の権限チェック
    # --------------------------------------------------
    async def interaction_check(self, interaction: discord.Interaction):

        user = interaction.user
        guild = interaction.guild

        # ① チェックインした本人
        if str(user.id) == self.owner_id:
            return True

        # ② ホテル管理人ロール
        manager_role = guild.get_role(self.manager_role_id)
        if manager_role and manager_role in user.roles:
            return True

        # どちらでもない場合
        await interaction.response.send_message(
            "❌ このパネルを操作できるのは「チェックインした本人」と「ホテル管理人ロール」のみです。",
            ephemeral=True
        )
        return False
