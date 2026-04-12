import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1420918259187712093

# 実行可能ロール
ALLOWED_ROLE_IDS = {
    1445403813853925418,
    1445403695197065236,
}


class RoleVCCheckCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================
    # ロール人数確認
    # =========================
    @app_commands.command(
        name="ロール人数確認",
        description="指定カテゴリー内VCの指定ロール接続人数を表示"
    )
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def check_role_vc_count(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        role: discord.Role
    ):
        # -------------------------
        # 実行権限チェック
        # -------------------------
        if not any(r.id in ALLOWED_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ このコマンドを使う権限がありません。",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=False)

        lines = []
        total_count = 0

        # 指定カテゴリ内のVCのみ対象
        voice_channels = [
            ch for ch in category.channels
            if isinstance(ch, discord.VoiceChannel)
        ]

        if not voice_channels:
            return await interaction.followup.send(
                "❌ このカテゴリー内にVCがありません。"
            )

        for vc in voice_channels:
            # 指定ロール持ちだけ抽出
            members = [
                m for m in vc.members
                if role in m.roles
            ]

            if not members:
                continue

            total_count += len(members)

            member_names = "\n".join([f"・{m.display_name}" for m in members])

            lines.append(
                f"## 🎤 VC名: {vc.name}　人数 {len(members)}名\n"
                f"{member_names}"
            )

        if not lines:
            return await interaction.followup.send(
                f"📭 カテゴリー **{category.name}** 内に\n"
                f"ロール **{role.name}** を持つVC接続者はいません。"
            )

        text = (
            f"# 📊 ロール人数確認\n"
            f"カテゴリー: **{category.name}**\n"
            f"対象ロール: **{role.name}**\n"
            f"合計: **{total_count}名**\n\n"
            + "\n\n".join(lines)
        )

        await interaction.followup.send(text)


async def setup(bot):
    await bot.add_cog(RoleVCCheckCog(bot))