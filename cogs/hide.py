import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import asyncio


def safe_name(text: str) -> str:
    return "".join(c for c in text if c.isalnum() or c in "-_ぁ-んァ-ヴー一-龯")[:80]


COLOR_MAP = {
    "赤": discord.ButtonStyle.red,
    "緑": discord.ButtonStyle.green,
    "青": discord.ButtonStyle.blurple,
    "灰": discord.ButtonStyle.gray,
}


# =========================
# topic helper
# =========================

def build_topic(owner_id: int) -> str:
    return f"anon_owner:{owner_id}"


def parse_owner_id(topic: str | None) -> int | None:
    if not topic:
        return None
    if not topic.startswith("anon_owner:"):
        return None
    try:
        return int(topic.split(":", 1)[1])
    except Exception:
        return None


# =========================
# Close Views
# =========================

class CloseAnonThreadView(View):
    """スレッド側の終了ボタン（対応ロール専用）"""

    def __init__(self, support_roles: list[int]):
        super().__init__(timeout=None)
        self.support_roles = support_roles

    @discord.ui.button(
        label="問い合わせ終了",
        style=discord.ButtonStyle.red,
        custom_id="anon_ticket_close_thread"
    )
    async def close_thread(self, interaction: discord.Interaction, button: Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("このボタンはスレッド内でのみ使えます", ephemeral=True)
            return

        if not any(r.id in self.support_roles for r in interaction.user.roles):
            await interaction.response.send_message(
                "対応担当のみ操作可能です",
                ephemeral=True
            )
            return

        thread = interaction.channel

        if thread.archived or thread.locked or thread.name.startswith("closed-"):
            await interaction.response.send_message("既に終了しています", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        owner_id = parse_owner_id(thread.topic)
        user = None
        if owner_id:
            user = interaction.client.get_user(owner_id)
            if user is None:
                try:
                    user = await interaction.client.fetch_user(owner_id)
                except Exception:
                    user = None

        try:
            await thread.send("🔒 この匿名相談は終了しました。")
        except Exception:
            pass

        try:
            await thread.edit(name=f"closed-{thread.name}")
        except Exception:
            pass

        try:
            await thread.edit(archived=True, locked=True)
        except Exception:
            pass

        if user:
            try:
                await user.send("🔒 匿名相談を終了しました。ご利用ありがとうございました。")
            except Exception:
                pass

        await interaction.followup.send("匿名相談を終了しました", ephemeral=True)


class CloseAnonDMView(View):
    """DM側の終了ボタン（作成者本人専用）"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="問い合わせ終了",
        style=discord.ButtonStyle.red,
        custom_id="anon_ticket_close_dm"
    )
    async def close_dm(self, interaction: discord.Interaction, button: Button):
        if interaction.guild is not None:
            await interaction.response.send_message("このボタンはDM専用です", ephemeral=True)
            return

        user = interaction.user
        bot = interaction.client

        await interaction.response.defer(ephemeral=True)

        thread = await find_active_thread_by_owner(bot, user.id)

        if not thread:
            await interaction.followup.send("現在アクティブな匿名相談はありません", ephemeral=True)
            return

        try:
            await thread.send("🔒 相談者が匿名相談を終了しました。")
        except Exception:
            pass

        try:
            if not thread.name.startswith("closed-"):
                await thread.edit(name=f"closed-{thread.name}")
        except Exception:
            pass

        try:
            await thread.edit(archived=True, locked=True)
        except Exception:
            pass

        try:
            await interaction.followup.send("匿名相談を終了しました", ephemeral=True)
        except Exception:
            pass

        try:
            await user.send("🔒 匿名相談を終了しました。")
        except Exception:
            pass


# =========================
# Panel View
# =========================

class AnonymousTicketCreateView(View):
    def __init__(self, title: str, body: str, first_msg: str, role_ids: list[int], color: str):
        super().__init__(timeout=None)
        self.panel_title = title
        self.panel_body = body
        self.first_msg = first_msg
        self.role_ids = role_ids

    @discord.ui.button(
        label="匿名で相談する",
        style=discord.ButtonStyle.blurple,
        custom_id="anon_ticket_create"
    )
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("AnonymousTicketCog")
        await cog.handle_create(interaction, self)


# =========================
# helper
# =========================

async def find_active_thread_by_owner(bot: commands.Bot, owner_id: int) -> discord.Thread | None:
    target_topic = build_topic(owner_id)

    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                # アクティブスレッド
                for th in channel.threads:
                    if th.archived:
                        continue
                    if th.topic == target_topic:
                        return th
            except Exception:
                continue

            # アーカイブは今回は探さない（アクティブ1件制限用途なので不要）
    return None


async def fetch_thread_user(thread: discord.Thread, bot: commands.Bot) -> discord.User | None:
    owner_id = parse_owner_id(thread.topic)
    if not owner_id:
        return None

    user = bot.get_user(owner_id)
    if user:
        return user

    try:
        return await bot.fetch_user(owner_id)
    except Exception:
        return None


# =========================
# Cog
# =========================

class AnonymousTicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(CloseAnonDMView())

    # =========================
    # slash command
    # =========================
    @app_commands.command(name="匿名相談用チケット", description="このチャンネルに匿名相談用チケットパネルを設置します")
    @app_commands.choices(
        ボタン色=[
            app_commands.Choice(name="赤", value="赤"),
            app_commands.Choice(name="緑", value="緑"),
            app_commands.Choice(name="青", value="青"),
            app_commands.Choice(name="灰", value="灰"),
        ]
    )
    async def anonymous_ticket_panel(
        self,
        interaction: discord.Interaction,
        タイトル: str,
        本文: str,
        初期メッセージ: str,
        ボタン色: app_commands.Choice[str],
        対応ロール1: discord.Role,
        対応ロール2: discord.Role = None,
        対応ロール3: discord.Role = None,
        対応ロール4: discord.Role = None,
        対応ロール5: discord.Role = None,
    ):
        await interaction.response.defer(ephemeral=True)

        role_ids = [
            r.id for r in [
                対応ロール1,
                対応ロール2,
                対応ロール3,
                対応ロール4,
                対応ロール5,
            ] if r is not None
        ]

        view = AnonymousTicketCreateView(
            タイトル,
            本文,
            初期メッセージ,
            role_ids,
            ボタン色.value
        )

        embed = discord.Embed(
            title=タイトル,
            description=本文,
            color=discord.Color.blurple()
        )

        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("匿名相談用チケットパネルを設置しました", ephemeral=True)



    # =========================
    # message relay
    # =========================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # -------------------------
        # DM → Thread
        # -------------------------
        if isinstance(message.channel, discord.DMChannel):
            thread = await find_active_thread_by_owner(self.bot, message.author.id)
            if not thread:
                return

            content = message.content.strip()
            attachments = message.attachments

            if not content and not attachments:
                return

            send_parts = []
            if content:
                send_parts.append(f"📩 匿名相談者:\n{content}")

            files = []
            for a in attachments:
                try:
                    files.append(await a.to_file())
                except Exception:
                    pass

            try:
                await thread.send(
                    "\n\n".join(send_parts) if send_parts else "📩 匿名相談者から画像・添付ファイルが届きました。",
                    files=files if files else None
                )
            except Exception:
                try:
                    await message.channel.send("転送に失敗しました。時間を置いてもう一度送ってください。")
                except Exception:
                    pass
                return

            try:
                await message.add_reaction("✅")
            except Exception:
                pass

            return

        # -------------------------
        # Thread → DM
        # -------------------------
        if isinstance(message.channel, discord.Thread):
            thread = message.channel
            owner_id = parse_owner_id(thread.topic)
            if not owner_id:
                return

            # close系メッセージは除外しなくてもよいが、bot以外だけ通す
            member = message.author
            if not isinstance(member, discord.Member):
                return

            # スレッド参加者側のみ送れるようにする
            # 相談者本人が万一入っても、topic上は匿名転送対象だが通常は入っていない
            user = await fetch_thread_user(thread, self.bot)
            if not user:
                return

            content = message.content.strip()
            attachments = message.attachments

            if not content and not attachments:
                return

            send_parts = []
            if content:
                send_parts.append(f"📨 運営:\n{content}")

            files = []
            for a in attachments:
                try:
                    files.append(await a.to_file())
                except Exception:
                    pass

            try:
                await user.send(
                    "\n\n".join(send_parts) if send_parts else "📨 運営から画像・添付ファイルが届きました。",
                    files=files if files else None
                )
            except discord.Forbidden:
                try:
                    await thread.send("⚠ 相談者にDMを送れませんでした。相談者側のDM設定をご確認ください。")
                except Exception:
                    pass
            except Exception:
                try:
                    await thread.send("⚠ 相談者への転送に失敗しました。")
                except Exception:
                    pass

async def handle_create(self, interaction: discord.Interaction, view: AnonymousTicketCreateView):

    guild = interaction.guild
    channel = interaction.channel
    user = interaction.user

    # 同時チケットチェック
    existing = await find_active_thread_by_owner(self.bot, user.id)
    if existing:
        await interaction.response.send_message(
            "既にアクティブな匿名相談チケットがあります",
            ephemeral=True
        )
        return

    # DM確認
    try:
        dm = await user.create_dm()
        await dm.send(
            "匿名相談用チケットのご利用ありがとうございます。\n"
            "このDMで送った内容が匿名で運営へ転送されます。\n"
            "お悩みは何ですか？",
            view=CloseAnonDMView()
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "DMを送れないため作成できませんでした。BotからのDMを許可してください。",
            ephemeral=True
        )
        return

    # スレッド作成
    safe_title = safe_name(view.panel_title) or "匿名相談"
    thread = await channel.create_thread(
        name=f"{safe_title}:匿名相談",
        type=discord.ChannelType.private_thread,
        invitable=False
    )

    await thread.edit(topic=build_topic(user.id))

    # 対応ロール追加
    added = set()
    for rid in view.role_ids:
        role = guild.get_role(rid)
        if not role:
            continue

        for m in role.members:
            if m.bot or m.id in added:
                continue
            try:
                await thread.add_user(m)
                added.add(m.id)
            except:
                pass

    await thread.send(
        "🕊 匿名相談チケットが作成されました。\n"
        "このスレッドのメッセージはBot経由で匿名転送されます。",
        view=CloseAnonThreadView(view.role_ids)
    )

    await interaction.response.send_message(
        "匿名相談チケットを作成しました。DMをご確認ください。",
        ephemeral=True
    )




async def setup(bot):
    cog = AnonymousTicketCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            try:
                bot.tree.add_command(cmd, guild=discord.Object(id=gid))
            except Exception:
                pass
