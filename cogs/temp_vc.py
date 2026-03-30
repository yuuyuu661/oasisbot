import random
import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418


class TempVCCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # guild_id -> setting
        self.vc_settings = {}

        # 作成VC記録
        self.created_vcs = set()

    # ==================================================
    # VC転送設定
    # ==================================================
    @app_commands.command(name="vc転送設定")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(
        指定vc="入室トリガーVC",
        vc最大人数="複製VCの最大人数",
        vc名a="VC名A候補（,区切り複数可）",
        vc名b="VC名B候補（,区切り複数可）",
        vc名c="ユーザー名の後ろに付けるVC名"
    )
    async def vc_transfer_setting(
        self,
        interaction: discord.Interaction,
        指定vc: discord.VoiceChannel,
        vc最大人数: int,
        vc名a: str | None = None,
        vc名b: str | None = None,
        vc名c: str | None = None,
    ):
        # 権限確認
        if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message(
                "このコマンドは管理者のみ使用できます。",
                ephemeral=True
            )

        # A+B または C のどちらか
        use_ab = vc名a and vc名b
        use_c = vc名c is not None

        if not use_ab and not use_c:
            return await interaction.response.send_message(
                "VC名A+B か VC名C のどちらかを指定してください。",
                ephemeral=True
            )

        self.vc_settings[interaction.guild.id] = {
            "source_vc_id": 指定vc.id,
            "max_users": vc最大人数,
            "names_a": [x.strip() for x in vc名a.split(",")] if vc名a else [],
            "names_b": [x.strip() for x in vc名b.split(",")] if vc名b else [],
            "name_c": vc名c
        }

        await interaction.response.send_message(
            f"✅ VC転送設定を保存しました\n監視VC: {指定vc.name}",
            ephemeral=True
        )

    # ==================================================
    # 入退室監視
    # ==================================================
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        if member.bot:
            return

        guild = member.guild
        setting = self.vc_settings.get(guild.id)
        if not setting:
            return

        trigger_id = setting["source_vc_id"]

        # 指定VCに入った時
        if after.channel and after.channel.id == trigger_id:
            base_channel = after.channel

            # VC名生成
            if setting["name_c"]:
                vc_name = f"{member.display_name}{setting['name_c']}"
            else:
                a = random.choice(setting["names_a"])
                b = random.choice(setting["names_b"])
                vc_name = f"{a}{b}"

            # 同じカテゴリ・権限で複製
            new_vc = await guild.create_voice_channel(
                name=vc_name,
                category=base_channel.category,
                overwrites=base_channel.overwrites,
                bitrate=base_channel.bitrate,
                user_limit=setting["max_users"]
            )

            self.created_vcs.add(new_vc.id)

            # ユーザー移動
            await member.move_to(new_vc)

        # 空VC自動削除
        if before.channel and before.channel.id in self.created_vcs:
            if len(before.channel.members) == 0:
                self.created_vcs.remove(before.channel.id)
                await before.channel.delete()


async def setup(bot: commands.Bot):
    await bot.add_cog(TempVCCog(bot))