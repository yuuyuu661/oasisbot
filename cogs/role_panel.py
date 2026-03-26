import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1420918259187712093
PANEL_ADMIN_ROLE = 1445403813853925418

class RolePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================
    # ロール付与パネル
    # =========================
    @app_commands.command(name="ロール付与パネル", description="ロール付与パネルを設置します")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(
        title="パネルタイトル",
        body="本文",
        emoji1="絵文字1",
        role1="ロール1",
        emoji2="絵文字2",
        role2="ロール2",
        emoji3="絵文字3",
        role3="ロール3",
        emoji4="絵文字4",
        role4="ロール4",
        emoji5="絵文字5",
        role5="ロール5"
    )
    async def role_panel(
        self,
        interaction: discord.Interaction,
        title: str,
        body: str,
        emoji1: str,
        role1: discord.Role,
        emoji2: str = None,
        role2: discord.Role = None,
        emoji3: str = None,
        role3: discord.Role = None,
        emoji4: str = None,
        role4: discord.Role = None,
        emoji5: str = None,
        role5: discord.Role = None,
    ):

        # ⭐ 権限チェック追加（ここだけ）
        if PANEL_ADMIN_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message(
                "このコマンドは管理者のみ使用できます",
                ephemeral=True
            )

        embed = discord.Embed(
            title=title,
            description=body,
            color=discord.Color.blue()
        )

        msg = await interaction.channel.send(embed=embed)

        pairs = [
            (emoji1, role1),
            (emoji2, role2),
            (emoji3, role3),
            (emoji4, role4),
            (emoji5, role5),
        ]

        valid_pairs = [(e, r) for e, r in pairs if e and r]

        for emoji, role in valid_pairs:
            await msg.add_reaction(emoji)

        if not hasattr(self.bot, "role_panels"):
            self.bot.role_panels = {}

        self.bot.role_panels[msg.id] = {
            str(e): r.id for e, r in valid_pairs
        }

        await interaction.response.send_message("設置しました", ephemeral=True)

    # =========================
    # リアクション付与
    # =========================
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        if payload.user_id == self.bot.user.id:
            return

        if not hasattr(self.bot, "role_panels"):
            return

        panel = self.bot.role_panels.get(payload.message_id)
        if not panel:
            return

        emoji = str(payload.emoji)
        role_id = panel.get(emoji)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)

        if role:
            await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):

        if not hasattr(self.bot, "role_panels"):
            return

        panel = self.bot.role_panels.get(payload.message_id)
        if not panel:
            return

        emoji = str(payload.emoji)
        role_id = panel.get(emoji)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)

        if role:
            await member.remove_roles(role)


async def setup(bot):
    await bot.add_cog(RolePanel(bot))
