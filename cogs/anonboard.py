import os
import json
import re
import asyncio
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands


DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "anonboard.json")

URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
IMAGE_EXT_RE = re.compile(r"\.(?:png|jpg|jpeg|gif|webp)(?:\?.*)?$", re.IGNORECASE)
MSG_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord\.com/channels/(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)"
)


def ensure_data_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "boards": {},    # board_channel_id -> config
                    "posts": {},     # board_message_id -> post info
                    "pending": {}    # log_message_id -> pending info
                },
                f,
                ensure_ascii=False,
                indent=2
            )


class AnonBoardStorage:
    def __init__(self):
        ensure_data_file()
        self.lock = asyncio.Lock()

    async def load(self) -> dict:
        async with self.lock:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)

    async def save(self, data: dict):
        async with self.lock:
            tmp = DATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, DATA_FILE)

    async def get_board(self, channel_id: int) -> Optional[dict]:
        data = await self.load()
        return data["boards"].get(str(channel_id))

    async def set_board(self, channel_id: int, board_data: dict):
        data = await self.load()
        data["boards"][str(channel_id)] = board_data
        await self.save(data)

    async def delete_board(self, channel_id: int):
        data = await self.load()
        data["boards"].pop(str(channel_id), None)
        await self.save(data)

    async def all_boards(self) -> dict:
        data = await self.load()
        return data["boards"]

    async def get_post(self, message_id: int) -> Optional[dict]:
        data = await self.load()
        return data["posts"].get(str(message_id))

    async def set_post(self, message_id: int, post_data: dict):
        data = await self.load()
        data["posts"][str(message_id)] = post_data
        await self.save(data)

    async def delete_post(self, message_id: int):
        data = await self.load()
        data["posts"].pop(str(message_id), None)
        await self.save(data)

    async def get_pending(self, log_message_id: int) -> Optional[dict]:
        data = await self.load()
        return data["pending"].get(str(log_message_id))

    async def set_pending(self, log_message_id: int, pending_data: dict):
        data = await self.load()
        data["pending"][str(log_message_id)] = pending_data
        await self.save(data)

    async def delete_pending(self, log_message_id: int):
        data = await self.load()
        data["pending"].pop(str(log_message_id), None)
        await self.save(data)

    async def increment_counter(self, channel_id: int) -> int:
        data = await self.load()
        board = data["boards"].get(str(channel_id))
        if not board:
            return 0
        board["counter"] = int(board.get("counter", 0)) + 1
        value = board["counter"]
        await self.save(data)
        return value


def is_image_url(url: str) -> bool:
    if IMAGE_EXT_RE.search(url):
        return True
    cdn_like = (
        "cdn.discordapp.com",
        "media.discordapp.net",
        "images-ext",
        "pbs.twimg.com",
        "imgur.com"
    )
    return any(host in url for host in cdn_like)


def extract_first_image_url(text: str) -> Optional[str]:
    for url in URL_RE.findall(text or ""):
        if is_image_url(url):
            return url
    return None


async def fetch_message_from_link(bot: commands.Bot, link: str) -> Optional[discord.Message]:
    m = MSG_LINK_RE.match(link.strip())
    if not m:
        return None

    channel_id = int(m.group("channel_id"))
    message_id = int(m.group("message_id"))

    ch = bot.get_channel(channel_id)
    if not isinstance(ch, (discord.TextChannel, discord.Thread)):
        return None

    try:
        return await ch.fetch_message(message_id)
    except Exception:
        return None


class PostModal(discord.ui.Modal, title="匿名掲示板に投稿"):
    def __init__(self, cog: "AnonBoardCog", board_channel_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.board_channel_id = board_channel_id

        self.content_input = discord.ui.TextInput(
            label="本文",
            style=discord.TextStyle.paragraph,
            placeholder="ここに投稿内容を入力",
            required=True,
            max_length=2000
        )
        self.add_item(self.content_input)

        self.image_input = discord.ui.TextInput(
            label="画像URL（任意・承認後に反映）",
            style=discord.TextStyle.short,
            placeholder="https://...",
            required=False,
            max_length=500
        )
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        board = await self.cog.storage.get_board(self.board_channel_id)
        if not board:
            return await interaction.followup.send("掲示板設定が見つかりません。", ephemeral=True)

        board_ch = interaction.guild.get_channel(self.board_channel_id)
        if not isinstance(board_ch, discord.TextChannel):
            return await interaction.followup.send("掲示板チャンネルが見つかりません。", ephemeral=True)

        content = self.content_input.value.strip()
        if not content:
            return await interaction.followup.send("本文が空です。", ephemeral=True)

        counter = await self.cog.storage.increment_counter(self.board_channel_id)
        display_name = str(counter)

        image_url = (self.image_input.value or "").strip()
        if not image_url:
            image_url = extract_first_image_url(content) or ""

        embed = discord.Embed(
            description=content,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"投稿者: {display_name}")

        published = await board_ch.send(embed=embed)

        await self.cog.storage.set_post(
            published.id,
            {
                "guild_id": interaction.guild_id,
                "board_channel_id": self.board_channel_id,
                "board_message_id": published.id,
                "anonymous": True,
                "anon_display": display_name,
                "author_id": interaction.user.id,
                "author_name": str(interaction.user),
                "author_display": interaction.user.display_name,
                "content": content,
                "img_url": None
            }
        )

        log_channel = interaction.guild.get_channel(board["log_channel_id"])
        if not image_url:
            if isinstance(log_channel, discord.TextChannel):
                log_embed = discord.Embed(
                    title="📝 匿名掲示板 投稿ログ",
                    description=content,
                    color=discord.Color.dark_gray()
                )
                log_embed.add_field(name="掲示板", value=board_ch.mention, inline=True)
                log_embed.add_field(name="表示名", value=display_name, inline=True)
                log_embed.add_field(name="送信者", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
                log_embed.add_field(name="投稿先", value=f"[ジャンプ]({published.jump_url})", inline=False)
                await log_channel.send(embed=log_embed)

            await self.cog.repost_panel(self.board_channel_id)
            return await interaction.followup.send("匿名で投稿しました。", ephemeral=True)

        if not isinstance(log_channel, discord.TextChannel):
            await self.cog.repost_panel(self.board_channel_id)
            return await interaction.followup.send(
                "本文は投稿しましたが、ログチャンネルが見つからないため画像は反映待ちにできませんでした。",
                ephemeral=True
            )

        pending_embed = discord.Embed(
            title="🕒 画像承認リクエスト",
            description=content,
            color=discord.Color.orange()
        )
        pending_embed.add_field(name="掲示板", value=board_ch.mention, inline=True)
        pending_embed.add_field(name="表示名", value=display_name, inline=True)
        pending_embed.add_field(name="送信者", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
        pending_embed.add_field(name="投稿先", value=f"[ジャンプ]({published.jump_url})", inline=False)
        pending_embed.set_image(url=image_url)

        log_msg = await log_channel.send(embed=pending_embed, view=ApprovalView(self.cog))

        await self.cog.storage.set_pending(
            log_msg.id,
            {
                "guild_id": interaction.guild_id,
                "board_channel_id": self.board_channel_id,
                "board_message_id": published.id,
                "log_message_id": log_msg.id,
                "author_id": interaction.user.id,
                "author_name": str(interaction.user),
                "author_display": interaction.user.display_name,
                "anon_display": display_name,
                "content": content,
                "img_url": image_url
            }
        )

        await self.cog.repost_panel(self.board_channel_id)
        await interaction.followup.send("本文を投稿しました。画像は管理者の承認後に反映されます。", ephemeral=True)


class ApprovalView(discord.ui.View):
    def __init__(self, cog: "AnonBoardCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="承認",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="anonboard:approve"
    )
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button):
        pending = await self.cog.storage.get_pending(interaction.message.id)
        if not pending:
            return await interaction.response.send_message("承認待ちデータが見つかりません。", ephemeral=True)

        board = await self.cog.storage.get_board(int(pending["board_channel_id"]))
        if not board:
            return await interaction.response.send_message("掲示板設定が見つかりません。", ephemeral=True)

        if not self.cog.has_admin_role(interaction.user, int(board["admin_role_id"])):
            return await interaction.response.send_message("承認権限がありません。", ephemeral=True)

        board_ch = interaction.guild.get_channel(int(pending["board_channel_id"]))
        if not isinstance(board_ch, discord.TextChannel):
            return await interaction.response.send_message("掲示板チャンネルが見つかりません。", ephemeral=True)

        try:
            target_msg = await board_ch.fetch_message(int(pending["board_message_id"]))
        except Exception:
            return await interaction.response.send_message("投稿メッセージが見つかりません。", ephemeral=True)

        base_desc = pending["content"]
        if target_msg.embeds:
            base_desc = target_msg.embeds[0].description or base_desc

        new_embed = discord.Embed(
            description=base_desc,
            color=discord.Color.blurple()
        )
        new_embed.set_footer(text=f"投稿者: {pending['anon_display']}")
        new_embed.set_image(url=pending["img_url"])

        await target_msg.edit(embed=new_embed)

        post = await self.cog.storage.get_post(target_msg.id)
        if post:
            post["img_url"] = pending["img_url"]
            await self.cog.storage.set_post(target_msg.id, post)

        done_embed = interaction.message.embeds[0].copy()
        done_embed.title = "✅ 承認済み"
        done_embed.color = discord.Color.green()

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=done_embed, view=self)
        await self.cog.storage.delete_pending(interaction.message.id)
        await interaction.response.send_message("画像を承認して反映しました。", ephemeral=True)

    @discord.ui.button(
        label="却下",
        style=discord.ButtonStyle.danger,
        emoji="🛑",
        custom_id="anonboard:reject"
    )
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        pending = await self.cog.storage.get_pending(interaction.message.id)
        if not pending:
            return await interaction.response.send_message("承認待ちデータが見つかりません。", ephemeral=True)

        board = await self.cog.storage.get_board(int(pending["board_channel_id"]))
        if not board:
            return await interaction.response.send_message("掲示板設定が見つかりません。", ephemeral=True)

        if not self.cog.has_admin_role(interaction.user, int(board["admin_role_id"])):
            return await interaction.response.send_message("却下権限がありません。", ephemeral=True)

        done_embed = interaction.message.embeds[0].copy()
        done_embed.title = "⛔ 却下済み（本文は投稿済み）"
        done_embed.color = discord.Color.red()

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=done_embed, view=self)
        await self.cog.storage.delete_pending(interaction.message.id)
        await interaction.response.send_message("画像投稿を却下しました。", ephemeral=True)


class BoardView(discord.ui.View):
    def __init__(self, cog: "AnonBoardCog", board_channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.board_channel_id = board_channel_id

    @discord.ui.button(
        label="匿名で投稿",
        style=discord.ButtonStyle.primary,
        emoji="🕵️",
        custom_id="anonboard:post"
    )
    async def post_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.channel_id != self.board_channel_id:
            return await interaction.response.send_message("この掲示板パネルは別チャンネル用です。", ephemeral=True)

        await interaction.response.send_modal(PostModal(self.cog, self.board_channel_id))


class AnonBoardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = AnonBoardStorage()

    async def cog_load(self):
        self.bot.add_view(ApprovalView(self))

        boards = await self.storage.all_boards()
        for channel_id in boards.keys():
            self.bot.add_view(BoardView(self, int(channel_id)))

    def has_admin_role(self, member: discord.Member, role_id: int) -> bool:
        return any(role.id == role_id for role in member.roles)

    async def repost_panel(self, board_channel_id: int):
        board = await self.storage.get_board(board_channel_id)
        if not board:
            return

        guild = self.bot.get_guild(int(board["guild_id"]))
        if not guild:
            return

        ch = guild.get_channel(board_channel_id)
        if not isinstance(ch, discord.TextChannel):
            return

        old_panel_id = board.get("panel_message_id")
        if old_panel_id:
            try:
                old_msg = await ch.fetch_message(int(old_panel_id))
                await old_msg.delete()
            except Exception:
                pass

        msg = await ch.send(
            "**匿名掲示板パネル**\n下のボタンから匿名投稿できます。",
            view=BoardView(self, board_channel_id)
        )
        board["panel_message_id"] = msg.id
        await self.storage.set_board(board_channel_id, board)

    @app_commands.command(name="匿名掲示板設置", description="このチャンネルに匿名掲示板パネルを設置します")
    @app_commands.describe(
        管理ロール="画像承認と投稿者開示ができるロール",
        ログチャンネル="承認ログを送るチャンネル"
    )
    async def setup_board(
        self,
        interaction: discord.Interaction,
        管理ロール: discord.Role,
        ログチャンネル: discord.TextChannel
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        if not self.has_admin_role(interaction.user, 管理ロール.id):
            return await interaction.response.send_message(
                f"{管理ロール.mention} を持っているユーザーだけ設置できます。",
                ephemeral=True
            )

        board_channel = interaction.channel

        board_data = {
            "guild_id": interaction.guild_id,
            "board_channel_id": board_channel.id,
            "panel_message_id": None,
            "admin_role_id": 管理ロール.id,
            "log_channel_id": ログチャンネル.id,
            "counter": 0
        }
        await self.storage.set_board(board_channel.id, board_data)
        await self.repost_panel(board_channel.id)

        await interaction.response.send_message(
            f"匿名掲示板を設置しました。\n"
            f"掲示板: {board_channel.mention}\n"
            f"管理ロール: {管理ロール.mention}\n"
            f"ログチャンネル: {ログチャンネル.mention}",
            ephemeral=True
        )



    @app_commands.command(name="匿名掲示板パネル再設置", description="匿名掲示板パネルを再設置します")
    async def repost_board_panel(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message("テキストチャンネルで実行してください。", ephemeral=True)

        board = await self.storage.get_board(interaction.channel.id)
        if not board:
            return await interaction.response.send_message("このチャンネルに匿名掲示板設定はありません。", ephemeral=True)

        if not self.has_admin_role(interaction.user, int(board["admin_role_id"])):
            return await interaction.response.send_message("再設置権限がありません。", ephemeral=True)

        await self.repost_panel(interaction.channel.id)
        await interaction.response.send_message("匿名掲示板パネルを再設置しました。", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnonBoardCog(bot))
