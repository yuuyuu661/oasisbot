import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button




# =========================
# Close Views
# =========================

class CloseAnonThreadView(View):
    def __init__(self, support_roles: list[int]):
        super().__init__(timeout=None)
        self.support_roles = support_roles

    @discord.ui.button(
        label="問い合わせ終了",
        style=discord.ButtonStyle.red,
        custom_id="anon_ticket_close_thread"
    )
    async def close_thread(self, interaction: discord.Interaction, button: Button):

        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message("スレッド専用です", ephemeral=True)

        if not any(r.id in self.support_roles for r in interaction.user.roles):
            return await interaction.response.send_message("対応担当のみ操作可能です", ephemeral=True)

        thread = interaction.channel

        await interaction.response.defer(ephemeral=True)

        owner_id = await interaction.client.db.get_anon_ticket_user(thread.id)

        await interaction.client.db.close_anon_ticket(thread.id)

        try:
            await thread.send("🔒 匿名相談は終了しました")
        except:
            pass

        try:
            await thread.edit(name=f"closed-{thread.name}", archived=True, locked=True)
        except:
            pass

        if owner_id:
            try:
                user = await interaction.client.fetch_user(owner_id)
                await user.send("🔒 匿名相談を終了しました")
            except:
                pass

        await interaction.followup.send("終了しました", ephemeral=True)


class CloseAnonDMView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="問い合わせ終了",
        style=discord.ButtonStyle.red,
        custom_id="anon_ticket_close_dm"
    )
    async def close_dm(self, interaction: discord.Interaction, button: Button):

        if interaction.guild:
            return await interaction.response.send_message("DM専用です", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        thread_id = await interaction.client.db.get_active_anon_ticket(interaction.user.id)

        if not thread_id:
            return await interaction.followup.send("アクティブな相談がありません", ephemeral=True)

        thread = interaction.client.get_channel(thread_id)

        await interaction.client.db.close_anon_ticket(thread_id)

        try:
            await thread.send("🔒 相談者が匿名相談を終了しました")
            await thread.edit(name=f"closed-{thread.name}", archived=True, locked=True)
        except:
            pass

        await interaction.followup.send("終了しました", ephemeral=True)


# =========================
# Panel View
# =========================

class AnonymousTicketCreateView(View):
    def __init__(self, title, body, first_msg, role_ids):
        super().__init__(timeout=None)
        self.title = title
        self.body = body
        self.first_msg = first_msg
        self.role_ids = role_ids

        self.add_item(Button(
            label="匿名で相談する",
            style=discord.ButtonStyle.blurple,  # 固定
            custom_id="anon_ticket_create"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("AnonymousTicketCog")
        await cog.handle_create(interaction, self)
        return False


# =========================
# Cog
# =========================

class AnonymousTicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(CloseAnonDMView())

    async def handle_create(self, interaction, view):

        await interaction.response.defer(ephemeral=True, thinking=True)

        thread_id = await self.bot.db.get_active_anon_ticket(interaction.user.id)
        if thread_id:
            return await interaction.followup.send("既に相談があります", ephemeral=True)

        try:
            dm = await interaction.user.create_dm()
            await dm.send(
                "匿名相談チケットです。\nここに送ると教会スタッフに匿名で転送されます。\nお悩みを教えてください。",
                view=CloseAnonDMView()
            )
        except:
            return await interaction.followup.send("DM送信できません", ephemeral=True)

        thread = await interaction.channel.create_thread(
            name=f"匿名相談-{interaction.user.id}",
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        await thread.add_user(self.bot.user)

        await self.bot.db.create_anon_ticket(thread.id, interaction.user.id, interaction.guild.id)

        for rid in view.role_ids:
            role = interaction.guild.get_role(rid)
            if role:
                try:
                    await thread.send(role.mention)
                except:
                    pass

        await thread.send(
            f"🕊 匿名相談が作成されました\n{view.first_msg}",
            view=CloseAnonThreadView(view.role_ids)
        )

        await interaction.followup.send("DMをご確認ください", ephemeral=True)

    # =========================
    # slash command
    # =========================

    @app_commands.command(name="匿名相談用チケット")
    async def anonymous_ticket_panel(
        self,
        interaction: discord.Interaction,
        タイトル: str,
        本文: str,
        初期メッセージ: str,
        対応ロール1: discord.Role,
    ):
        view = AnonymousTicketCreateView(
            タイトル,
            本文,
            初期メッセージ,
            [対応ロール1.id]
        )

        embed = discord.Embed(title=タイトル, description=本文)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("設置しました", ephemeral=True)

    # =========================
    # relay
    # =========================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        print("MESSAGE EVENT:", message.channel, type(message.channel), message.content)
    

        if message.author.bot:
            return

        # =========================
        # DM → Thread
        # =========================
        if isinstance(message.channel, discord.DMChannel):

            thread_id = await self.bot.db.get_active_anon_ticket(message.author.id)
            if not thread_id:
                return

            thread = self.bot.get_channel(thread_id)
            if not thread:
                return

            content = message.content.strip()
            attachments = message.attachments

            if not content and not attachments:
                return

            files = []
            for a in attachments:
                try:
                    files.append(await a.to_file())
                except:
                    pass

            try:
                await thread.send(
                    f"📩 匿名相談者:\n{content}" if content else "📩 画像・添付ファイル",
                    files=files if files else None
                )
            except:
                try:
                    await message.channel.send("⚠ 転送失敗")
                except:
                    pass
                return

            try:
                await message.add_reaction("✅")
            except:
                pass

            return

        # =========================
        # Thread → DM
        # =========================
        if isinstance(message.channel, discord.Thread):

            print("THREAD DETECTED:", message.channel.id)

            if message.author.bot:
                print("IGNORED BOT MESSAGE")
                return

            owner_id = await self.bot.db.get_anon_ticket_user(message.channel.id)
            print("OWNER ID:", owner_id)

            if not owner_id:
                print("NO OWNER FOUND")
                return

            if message.author.id == owner_id:
                print("IGNORED OWNER MESSAGE")
                return

            try:
                user = await self.bot.fetch_user(owner_id)
            except Exception as e:
                print("FETCH USER ERROR:", e)
                return

            content = message.content.strip()
            attachments = message.attachments

            if not content and not attachments:
                print("EMPTY MESSAGE")
                return

            files = []
            for a in attachments:
                try:
                    files.append(await a.to_file())
                except Exception as e:
                    print("FILE ERROR:", e)

            try:
                print("TRY SEND DM:", content)
                await user.send(
                    f"📨 神からのお告げ:\n{content}" if content else "📨 添付ファイル",
                    files=files if files else None
                )
                print("DM SENT OK")
            except discord.Forbidden:
                print("DM FORBIDDEN")
                await message.channel.send("⚠ 相談者のDMが閉じています")
            except Exception as e:
                print("DM SEND ERROR:", e)
                await message.channel.send("⚠ 転送失敗")


async def setup(bot):
    cog = AnonymousTicketCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            try:
                bot.tree.add_command(cmd, guild=discord.Object(id=gid))
            except Exception:
                pass
