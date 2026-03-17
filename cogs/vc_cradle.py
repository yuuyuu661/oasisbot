import discord
from discord.ext import commands
from discord import app_commands

TARGET_VC_ID = 1420918260328566869

ALLOWED_ROLES = {
    1445403813853925418,
    1445403608035364874
}

GUILD_ID = 1420918259187712093


class VCCradleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def has_permission(self, member: discord.Member):
        return any(r.id in ALLOWED_ROLES for r in member.roles)

    @app_commands.command(name="ゆりかご", description="指定ユーザーをゆりかごVCに移動")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def cradle(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        # 権限チェック
        if not self.has_permission(interaction.user):
            await interaction.response.send_message(
                "このコマンドを使用する権限がありません",
                ephemeral=True
            )
            return

        # VCチェック
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message(
                "そのユーザーはVCにいません",
                ephemeral=True
            )
            return

        # ⭐ すでにゆりかごにいるチェック
        if user.voice.channel.id == TARGET_VC_ID:
            await interaction.response.send_message(
                f"もう {user.display_name} はゆりかごにいます"
            )
            return

        target_vc = interaction.guild.get_channel(TARGET_VC_ID)

        if not target_vc:
            await interaction.response.send_message(
                "移動先VCが見つかりません",
                ephemeral=True
            )
            return

        try:
            await user.move_to(target_vc)
            await interaction.response.send_message(
                f"{user.display_name} をゆりかごへ移動しました"
            )

        except Exception as e:
            await interaction.response.send_message(
                f"移動失敗: {e}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(VCCradleCog(bot))
