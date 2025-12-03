# cogs/hotel/room_panel.py

import discord
from discord.ext import commands

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
    RoomCheckTicketsButton
)


class HotelRoomControlPanel(discord.ui.View):
    """
    高級ホテルの VC 内に生成される操作パネル本体
    （人数+1、名前変更、接続許可、期限延長、サブ垢追加など10ボタン）
    """

    def __init__(self, owner_id, manager_role_id, sub_role_id, config):
        super().__init__(timeout=None)

        self.owner_id = owner_id
        self.manager_role_id = int(manager_role_id)
        self.sub_role_id = int(sub_role_id)
        self.config = config

        # --- 10ボタンを登録 ---
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

    # ------------------------------------------------------
    # 操作権限チェック
    # ------------------------------------------------------
    async def interaction_check(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        # ルーム所有者 → OK
        if str(user.id) == str(self.owner_id):
            return True

        # ホテル管理人ロール所持者 → OK
        manager_role = guild.get_role(self.manager_role_id)
        if manager_role and manager_role in user.roles:
            return True

        # それ以外 → 拒否
        await interaction.response.send_message(
            "❌ このパネルを操作できるのは **チェックインした本人** と **ホテル管理人ロール** のみです。",
            ephemeral=True
        )
        return False


# ======================================================
# Cog（VCパネル本体）
# ======================================================

class RoomPanelCog(commands.Cog):
    """操作パネル本体 View の登録用"""

    def __init__(self, bot):
        self.bot = bot
