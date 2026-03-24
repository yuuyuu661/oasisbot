import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import asyncio

def safe_name(text):
    return "".join(c for c in text if c.isalnum() or c in "-_ぁ-んァ-ヴー一-龯")[:80]


COLOR_MAP = {
    "赤": discord.ButtonStyle.red,
    "緑": discord.ButtonStyle.green,
    "青": discord.ButtonStyle.blurple,
    "灰": discord.ButtonStyle.gray,
}

# =========================
# Close
# =========================

class CloseTicketView(View):
    def __init__(self, support_roles):
        super().__init__(timeout=None)
        self.support_roles = support_roles

    @discord.ui.button(label="問い合わせ終了", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):

        # ⭐ サポートロールのみ
        if not any(r.id in self.support_roles for r in interaction.user.roles):
            await interaction.response.send_message(
                "サポート担当のみ操作可能です",
                ephemeral=True
            )
            return

        thread = interaction.channel

        if thread.name.startswith("closed-"):
            await interaction.response.send_message("既に終了しています", ephemeral=True)
            return

        await interaction.response.send_message("問い合わせを終了しました", ephemeral=True)

        try:
            await thread.edit(name=f"closed-{thread.name}")
        except:
            pass

        try:
            await thread.edit(archived=True, locked=True)
        except:
            pass


# =========================
# Create Ticket Button
# =========================

class TicketCreateView(View):

    def __init__(self, title, message, first_msg, role_ids, color):
        super().__init__(timeout=None)

        self.first_msg = first_msg
        self.role_ids = role_ids

        role_str = ",".join(str(r) for r in role_ids)

        custom_id = f"ticket::{title}::{message}::{role_str}"

        self.add_item(Button(
            label="問い合わせる",
            style=COLOR_MAP[color],
            custom_id=custom_id
        ))

# =========================
# Cog
# =========================

class TicketCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        pass

    @app_commands.command(name="チケット")
    @app_commands.checks.has_role(1310906528517062770)
    @app_commands.choices(
        ボタン色=[
            app_commands.Choice(name="赤", value="赤"),
            app_commands.Choice(name="緑", value="緑"),
            app_commands.Choice(name="青", value="青"),
            app_commands.Choice(name="灰", value="灰"),
        ]
    )
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        タイトル: str,
        本文: str,
        初期メッセージ: str,
        ボタン色: app_commands.Choice[str],
        サポートロール1: discord.Role,
        サポートロール2: discord.Role = None,
        サポートロール3: discord.Role = None,
        サポートロール4: discord.Role = None,
        サポートロール5: discord.Role = None
    ):

        await interaction.response.defer()

        role_ids = [
            r.id for r in [
                サポートロール1,
                サポートロール2,
                サポートロール3,
                サポートロール4,
                サポートロール5
            ] if r is not None
        ]

        view = TicketCreateView(
            タイトル,
            本文,
            初期メッセージ,
            role_ids,
            ボタン色.value
        )

        embed = discord.Embed(
            title=タイトル,
            description=本文,
            color=discord.Color.green()
        )

        await interaction.followup.send(
            embed=embed,
            view=view
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):

        if not interaction.data:
            return

        cid = interaction.data.get("custom_id")
        if not cid:
            return

        if not cid.startswith("ticket::"):
            return

        await interaction.response.defer(ephemeral=True)

        _, title, message, role_str = cid.split("::")
        role_ids = [int(x) for x in role_str.split(",")]

        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        safe_user = safe_name(user.display_name)

        for th in channel.threads:
            if not th.archived and th.name.endswith(f"{safe_user}様"):
                await interaction.followup.send("既に問い合わせチケットがあります", ephemeral=True)
                return


        # ⭐ 新スレッド名仕様
        thread = await channel.create_thread(
            name=f"{safe_name(title)}:{safe_name(user.display_name)}様",
            type=discord.ChannelType.private_thread
        )

        roles = []
        for rid in role_ids:
            role = guild.get_role(rid)
            if role:
                roles.append(role.mention)

        await thread.send(
            f"{user.mention} {' '.join(roles)}"
        )

        await thread.send(
            message,
            view=CloseTicketView(role_ids)
        )

        await interaction.followup.send(
            f"作成しました {thread.mention}",
            ephemeral=True
        )

async def setup(bot):
    cog = TicketCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
