import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

# =========================
# Close
# =========================

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="問い合わせ終了", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):

        thread = interaction.channel

        await interaction.response.send_message("5秒後に削除します", ephemeral=True)
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(seconds=5))

        await thread.delete()

# =========================
# Create Ticket Button
# =========================

class TicketCreateView(View):

    def __init__(self, title, message, first_msg, role_id):
        super().__init__(timeout=None)

        custom_id = f"ticket::{title}::{message}::{first_msg}::{role_id}"

        self.add_item(Button(
            label="問い合わせる",
            style=discord.ButtonStyle.green,
            custom_id=custom_id
        ))

# =========================
# Cog
# =========================

class TicketCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(CloseTicketView())

    # =========================
    # Create Panel
    # =========================

    @app_commands.command(name="チケット")
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        タイトル: str,
        本文: str,
        初期メッセージ: str,
        サポートロール: discord.Role
    ):

        view = TicketCreateView(
            タイトル,
            本文,
            初期メッセージ,
            サポートロール.id
        )

        embed = discord.Embed(
            title=タイトル,
            description=本文,
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )

    # =========================
    # Button Handler
    # =========================
    def safe_name(text):
        return "".join(c for c in text if c.isalnum() or c in "-_")[:80]

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):

        if not interaction.data:
            return

        cid = interaction.data.get("custom_id")

        if not cid:
            return

        if not cid.startswith("ticket::"):
            return

        _, title, message, first_msg, role_id = cid.split("::")

        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        thread = await channel.create_thread(
            name=f"{safe_name(title)}-{safe_name(user.name)}",
            type=discord.ChannelType.private_thread
        )

        await thread.add_user(user)

        role = guild.get_role(int(role_id))
        if role:
            for m in role.members:
                await thread.add_user(m)

        await interaction.response.send_message(
            f"作成しました {thread.mention}",
            ephemeral=True
        )

        await thread.send(
            f"{user.mention}\n{first_msg}",
            view=CloseTicketView()
        )

async def setup(bot):
    cog = TicketCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
