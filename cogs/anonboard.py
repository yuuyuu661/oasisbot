import re
import discord
from discord.ext import commands
from discord import app_commands


SETUP_ROLE_ID = 1445403813853925418

IMAGE_EXT_RE = re.compile(r"\.(?:png|jpg|jpeg|gif|webp)(?:\?.*)?$", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
MSG_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord\.com/channels/(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)"
)


def is_image_url(url: str) -> bool:
    if IMAGE_EXT_RE.search(url):
        return True
    cdn_like = (
        "cdn.discordapp.com",
        "media.discordapp.net",
        "images-ext",
        "pbs.twimg.com",
        "imgur.com",
    )
    return any(h in url for h in cdn_like)


def extract_first_image_url(text: str) -> str | None:
    for m in URL_RE.findall(text or ""):
        if is_image_url(m):
            return m
    return None


async def fetch_message_from_link(bot: commands.Bot, link: str) -> discord.Message | None:
    m = MSG_LINK_RE.match(link.strip())
    if not m:
        return None

    ch_id = int(m.group("channel_id"))
    msg_id = int(m.group("message_id"))

    ch = bot.get_channel(ch_id)
    if not isinstance(ch, (discord.TextChannel, discord.Thread)):
        return None

    try:
        return await ch.fetch_message(msg_id)
    except Exception:
        return None


class PostModal(discord.ui.Modal, title="投稿内容を入力"):
    def __init__(self, cog: "AnonBoardCog", channel_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.channel_id = channel_id

        self.content_input = discord.ui.TextInput(
            label="本文",
            style=discord.TextStyle.paragraph,
            placeholder="ここにメッセージを入力",
            max_length=2000,
            required=True,
        )
        self.add_item(self.content_input)

        self.img_url_input = discord.ui.TextInput(
            label="画像URL（任意・画像は承認後に反映）",
            style=discord.TextStyle.short,
            placeholder="https://...",
            max_length=500,
            required=False,
        )
        self.add_item(self.img_url_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=False)

        board_ch = interaction.client.get_channel(self.channel_id)
        if not isinstance(board_ch, discord.TextChannel):
            return await interaction.followup.send("対象チャンネルが見つかりません。", ephemeral=True)

        board = await self.cog.bot.db.get_anon_board(self.channel_id)
        if not board:
            return await interaction.followup.send("このチャンネルは匿名掲示板として設定されていません。", ephemeral=True)

        anon_no = await self.cog.bot.db.increment_anon_counter(self.channel_id)
        display_name = str(anon_no)

        content = str(self.content_input.value).strip()
        if not content:
            return await interaction.followup.send("本文が空です。", ephemeral=True)

        img = str(self.img_url_input.value or "").strip()
        if not img:
            img = extract_first_image_url(content) or ""
        img = img.strip()
        has_image = bool(img)

        embed = discord.Embed(description=content, color=discord.Color.blurple())
        embed.set_footer(text=f"投稿者: {display_name}")
        published = await board_ch.send(embed=embed)

        await self.cog.bot.db.add_anon_post(
            message_id=published.id,
            channel_id=self.channel_id,
            author_id=interaction.user.id,
            anon_no=anon_no,
        )

        log_channel_id = board["log_channel_id"]
        log_ch = interaction.client.get_channel(log_channel_id) if log_channel_id else None

        if not has_image:
            if isinstance(log_ch, discord.TextChannel):
                le = discord.Embed(
                    title="📝 投稿ログ（画像なし）",
                    description=content,
                    color=discord.Color.dark_gray()
                )
                le.add_field(name="表示番号", value=str(anon_no), inline=True)
                le.add_field(name="投稿先", value=board_ch.mention, inline=True)
                le.add_field(name="本文メッセージ", value=f"[ジャンプ]({published.jump_url})", inline=False)
                le.add_field(name="送信者", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
                await log_ch.send(embed=le)

            await self.cog.repost_panel(board_ch.id)
            return await interaction.followup.send("匿名で投稿しました。", ephemeral=True)

        if not isinstance(log_ch, discord.TextChannel):
            await self.cog.repost_panel(board_ch.id)
            return await interaction.followup.send(
                "本文は公開しましたが、ログチャンネル未設定のため画像は承認待ちにできませんでした。",
                ephemeral=True
            )

        pending = discord.Embed(
            title="🕒 画像承認リクエスト",
            description=content,
            color=discord.Color.orange()
        )
        pending.add_field(name="表示番号", value=str(anon_no), inline=True)
        pending.add_field(name="投稿先", value=board_ch.mention, inline=True)
        pending.add_field(name="本文メッセージ", value=f"[ジャンプ]({published.jump_url})", inline=False)
        pending.add_field(name="送信者", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
        pending.set_image(url=img)

        view = ApprovalView(self.cog)
        log_msg = await log_ch.send(embed=pending, view=view)

        await self.cog.bot.db.add_pending(
            log_msg_id=log_msg.id,
            board_msg_id=published.id,
            channel_id=self.channel_id,
            author_id=interaction.user.id,
            anon_no=anon_no,
            content=content,
            img=img,
        )

        await self.cog.repost_panel(board_ch.id)
        await interaction.followup.send("本文を投稿しました。画像は承認待ちです。", ephemeral=True)


class ApprovalView(discord.ui.View):
    def __init__(self, cog: "AnonBoardCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="anonboard:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        pending = await self.cog.bot.db.get_pending(interaction.message.id)
        if not pending:
            return await interaction.response.send_message("承認待ち情報が見つかりません。", ephemeral=True)

        if not await self.cog.has_admin_role(interaction.user, pending["channel_id"]):
            return await interaction.response.send_message("承認権限がありません。", ephemeral=True)

        board_ch = interaction.client.get_channel(pending["channel_id"])
        if not isinstance(board_ch, discord.TextChannel):
            return await interaction.response.send_message("投稿先チャンネルが見つかりません。", ephemeral=True)

        try:
            target_msg = await board_ch.fetch_message(pending["board_message_id"])
        except Exception:
            return await interaction.response.send_message("本文メッセージが取得できませんでした。", ephemeral=True)

        desc = pending["content"] or ""
        new_embed = discord.Embed(description=desc, color=discord.Color.blurple())
        new_embed.set_footer(text=f"投稿者: {pending['anon_number']}")
        if pending["image_url"]:
            new_embed.set_image(url=pending["image_url"])

        await target_msg.edit(embed=new_embed)
        await self.cog.bot.db.set_post_image(target_msg.id, pending["image_url"])

        log_embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        log_embed.title = "✅ 承認・反映済み"
        log_embed.color = discord.Color.green()

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=log_embed, view=self)
        await self.cog.bot.db.delete_pending(interaction.message.id)
        await interaction.response.send_message("承認して掲示板に画像を反映しました。", ephemeral=True)

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        emoji="🛑",
        custom_id="anonboard:reject",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        pending = await self.cog.bot.db.get_pending(interaction.message.id)
        if not pending:
            return await interaction.response.send_message("承認待ち情報が見つかりません。", ephemeral=True)

        if not await self.cog.has_admin_role(interaction.user, pending["channel_id"]):
            return await interaction.response.send_message("承認権限がありません。", ephemeral=True)

        log_embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        log_embed.title = "⛔ 実施せず（本文は公開済み）"
        log_embed.color = discord.Color.red()

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=log_embed, view=self)
        await self.cog.bot.db.delete_pending(interaction.message.id)
        await interaction.response.send_message("却下しました（本文は公開済みのまま）。", ephemeral=True)


class BoardView(discord.ui.View):
    def __init__(self, cog: "AnonBoardCog", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(
        label="匿名で投稿",
        style=discord.ButtonStyle.primary,
        emoji="🕵️",
        custom_id="anonboard:post",
    )
    async def post_anon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PostModal(self.cog, self.channel_id))


class AnonBoardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def can_setup(self, member: discord.Member) -> bool:
        return any(role.id == SETUP_ROLE_ID for role in member.roles)

    async def has_admin_role(self, user: discord.abc.User, channel_id: int) -> bool:
        if not isinstance(user, discord.Member):
            return False

        board = await self.bot.db.get_anon_board(channel_id)
        if not board:
            return False

        admin_roles = board["admin_roles"] or []
        return any(role.id in admin_roles for role in user.roles)

    async def repost_panel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        # 直近50件から既存パネルを消す
        try:
            async for msg in channel.history(limit=50):
                if (
                    msg.author.id == self.bot.user.id
                    and msg.components
                    and msg.content.startswith("**匿名掲示板パネル**")
                ):
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                    break
        except Exception:
            pass

        view = BoardView(self, channel_id)
        await channel.send("**匿名掲示板パネル**\n下のボタンから投稿してください。", view=view)

    async def restore_views(self):
        self.bot.add_view(ApprovalView(self))

        rows = await self.bot.db.list_anon_boards()
        for row in rows:
            self.bot.add_view(BoardView(self, row["channel_id"]))

    @commands.Cog.listener()
    async def on_ready(self):
        if getattr(self.bot, "_anonboard_views_restored", False):
            return
        self.bot._anonboard_views_restored = True
        await self.restore_views()

    @app_commands.command(name="匿名掲示板設置", description="このチャンネルに匿名掲示板パネルを設置")
    @app_commands.describe(
        log_channel="投稿ログ送信先（画像承認用）",
        admin_role1="管理ロール1",
        admin_role2="管理ロール2",
        admin_role3="管理ロール3",
        admin_role4="管理ロール4",
        admin_role5="管理ロール5",
    )
    async def setup_board(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel,
        admin_role1: discord.Role,
        admin_role2: discord.Role | None = None,
        admin_role3: discord.Role | None = None,
        admin_role4: discord.Role | None = None,
        admin_role5: discord.Role | None = None,
    ):
        if not isinstance(interaction.user, discord.Member) or not self.can_setup(interaction.user):
            return await interaction.response.send_message("このコマンドを使えるロールではありません。", ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        roles = [
            r.id for r in [admin_role1, admin_role2, admin_role3, admin_role4, admin_role5]
            if r is not None
        ]
        roles = list(dict.fromkeys(roles))

        await self.bot.db.create_anon_board(
            channel_id=channel.id,
            guild_id=interaction.guild_id,
            log_channel=log_channel.id,
            roles=roles,
        )

        await self.repost_panel(channel.id)

        await interaction.response.send_message(
            f"匿名掲示板を設置しました：{channel.mention}\n"
            f"ログ：{log_channel.mention}\n"
            f"管理ロール数：{len(roles)}",
            ephemeral=True
        )

    @app_commands.command(name="匿名掲示板ログ変更", description="匿名掲示板のログチャンネルを変更")
    @app_commands.describe(log_channel="新しいログ送信先")
    async def set_log_channel(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel
    ):
        if not isinstance(interaction.user, discord.Member) or not self.can_setup(interaction.user):
            return await interaction.response.send_message("このコマンドを使えるロールではありません。", ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        board = await self.bot.db.get_anon_board(channel.id)
        if not board:
            return await interaction.response.send_message("このチャンネルは匿名掲示板ではありません。", ephemeral=True)

        await self.bot.db.create_anon_board(
            channel_id=channel.id,
            guild_id=interaction.guild_id,
            log_channel=log_channel.id,
            roles=board["admin_roles"] or [],
        )

        await interaction.response.send_message(
            f"ログチャンネルを {log_channel.mention} に変更しました。",
            ephemeral=True
        )

    @app_commands.command(name="匿名掲示板管理ロール変更", description="匿名掲示板の管理ロールを変更")
    @app_commands.describe(
        admin_role1="管理ロール1",
        admin_role2="管理ロール2",
        admin_role3="管理ロール3",
        admin_role4="管理ロール4",
        admin_role5="管理ロール5",
    )
    async def set_admin_roles(
        self,
        interaction: discord.Interaction,
        admin_role1: discord.Role,
        admin_role2: discord.Role | None = None,
        admin_role3: discord.Role | None = None,
        admin_role4: discord.Role | None = None,
        admin_role5: discord.Role | None = None,
    ):
        if not isinstance(interaction.user, discord.Member) or not self.can_setup(interaction.user):
            return await interaction.response.send_message("このコマンドを使えるロールではありません。", ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        board = await self.bot.db.get_anon_board(channel.id)
        if not board:
            return await interaction.response.send_message("このチャンネルは匿名掲示板ではありません。", ephemeral=True)

        roles = [
            r.id for r in [admin_role1, admin_role2, admin_role3, admin_role4, admin_role5]
            if r is not None
        ]
        roles = list(dict.fromkeys(roles))

        await self.bot.db.create_anon_board(
            channel_id=channel.id,
            guild_id=interaction.guild_id,
            log_channel=board["log_channel_id"],
            roles=roles,
        )

        await interaction.response.send_message(
            f"管理ロールを更新しました（{len(roles)}個）。",
            ephemeral=True
        )

    @app_commands.command(name="匿名掲示板番号リセット", description="匿名掲示板の連番を0に戻す")
    async def reset_counter(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not self.can_setup(interaction.user):
            return await interaction.response.send_message("このコマンドを使えるロールではありません。", ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        board = await self.bot.db.get_anon_board(channel.id)
        if not board:
            return await interaction.response.send_message("このチャンネルは匿名掲示板ではありません。", ephemeral=True)

        await self.bot.db.reset_anon_counter(channel.id)
        await interaction.response.send_message("匿名連番をリセットしました。", ephemeral=True)

    @app_commands.command(name="匿名掲示板パネル再掲", description="匿名掲示板パネルを最下部に再掲")
    async def repost_board_panel(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not self.can_setup(interaction.user):
            return await interaction.response.send_message("このコマンドを使えるロールではありません。", ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        board = await self.bot.db.get_anon_board(channel.id)
        if not board:
            return await interaction.response.send_message("このチャンネルは匿名掲示板ではありません。", ephemeral=True)

        await self.repost_panel(channel.id)
        await interaction.response.send_message("匿名掲示板パネルを再掲しました。", ephemeral=True)

    @app_commands.command(name="匿名掲示板reveal", description="匿名投稿の実投稿者を照会")
    @app_commands.describe(message_link="対象メッセージのリンク")
    async def reveal(self, interaction: discord.Interaction, message_link: str):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        if not await self.has_admin_role(interaction.user, channel.id):
            return await interaction.response.send_message("reveal権限がありません。", ephemeral=True)

        msg = await fetch_message_from_link(self.bot, message_link)
        if not msg:
            return await interaction.response.send_message("メッセージリンクが無効です。", ephemeral=True)

        post = await self.bot.db.get_anon_post(msg.id)
        if not post:
            return await interaction.response.send_message(
                "このメッセージの記録が見つかりません。匿名掲示板の投稿ではない可能性があります。",
                ephemeral=True
            )

        desc = (
            f"**表示番号**: {post['anon_number']}\n"
            f"**実投稿者**: <@{post['author_id']}>\n"
            f"**メッセージ**: {msg.jump_url}"
        )
        await interaction.response.send_message(desc, ephemeral=True)


async def setup(bot):
    cog = AnonBoardCog(bot)
    await bot.add_cog(cog)

    for gid in bot.GUILD_IDS:
        bot.tree.add_command(
            cog.anon_board_setup,
            guild=discord.Object(id=gid)
        )
