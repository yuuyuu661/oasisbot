import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418

ALLOWED_USER_IDS = {
    716667546241335328,
    969739156756508672,
}

CATEGORIES = {
    1: "①推しの子部門",
    2: "②女子声部門",
    3: "③男子声部門",
    4: "④最強仮メン部門",
    5: "⑤笑い方(笑い声)部門",
    6: "⑥泣き虫部門",
    7: "⑦ゆったり部門",
    8: "⑧おバカ部門",
    9: "⑨頭が賢い部門",
    10: "⑩ビジュアル部門男",
    11: "⑪ビジュアル部門女",
}


# =========================
# ページ切替
# =========================
class PageView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction):
        settings = await interaction.client.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if any(str(r.id) in admin_roles for r in interaction.user.roles):
            return True

        await interaction.response.send_message(
            "❌ 管理者のみ操作できます。",
            ephemeral=True
        )
        return False

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button):
        self.index = (self.index - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index])

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button):
        self.index = (self.index + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index])


# =========================
# コメントモーダル
# =========================
class CommentModal(discord.ui.Modal, title="コメント入力"):
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

        self.comment = discord.ui.TextInput(
            label="コメント（任意）",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            default=parent_view.comment or ""
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.comment = self.comment.value

        await interaction.response.edit_message(
            content=f"📝 コメントを保存しました\n現在コメント: {self.comment.value or 'なし'}",
            view=self.parent_view
        )


# =========================
# ユーザー選択
# =========================
class UserVoteSelect(discord.ui.UserSelect):
    def __init__(self, parent_view):
        super().__init__(
            placeholder="投票するユーザーを選択",
            min_values=1,
            max_values=1
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]

        if selected.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ 自分には投票できません。",
                ephemeral=True
            )

        if selected.bot:
            return await interaction.response.send_message(
                "❌ Botには投票できません。",
                ephemeral=True
            )

        self.parent_view.selected_user_id = selected.id

        await interaction.response.edit_message(
            content=f"✅ **{selected.display_name}** を選択しました",
            view=self.parent_view
        )


# =========================
# 部門投票View
# =========================
class VoteCategoryView(discord.ui.View):
    def __init__(self, bot, category_no: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.category_no = category_no
        self.selected_user_id = None
        self.comment = ""

        self.add_item(UserVoteSelect(self))

    @discord.ui.button(
        label="コメントを書く",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def comment_btn(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(CommentModal(self))

    @discord.ui.button(
        label="決定",
        style=discord.ButtonStyle.success,
        row=1
    )
    async def confirm_btn(self, interaction: discord.Interaction, button):
        if not self.selected_user_id:
            return await interaction.response.send_message(
                "❌ 先にユーザーを選択してください。",
                ephemeral=True
            )

        await self.bot.db._execute("""
            INSERT INTO sosenkyo_votes (
                guild_id,
                voter_id,
                category_no,
                target_user_id,
                comment
            )
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (guild_id, voter_id, category_no)
            DO UPDATE SET
                target_user_id = EXCLUDED.target_user_id,
                comment = EXCLUDED.comment,
                updated_at = NOW()
        """,
        str(interaction.guild.id),
        str(interaction.user.id),
        self.category_no,
        str(self.selected_user_id),
        self.comment
        )

        next_no = self.category_no + 1

        if next_no <= 11:
            await interaction.response.edit_message(
                content=f"✅ {CATEGORIES[self.category_no]} を保存しました",
                embed=discord.Embed(
                    title=CATEGORIES[next_no],
                    description="投票するユーザーを選んでください",
                    color=discord.Color.gold()
                ),
                view=VoteCategoryView(self.bot, next_no)
            )
        else:
            await interaction.response.edit_message(
                content="🎉 投票に参加してくれてありがとう！",
                embed=None,
                view=None
            )


# =========================
# 永続投票ボタン
# =========================
class SosenkyoVotePersistentView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="投票",
        style=discord.ButtonStyle.success,
        custom_id="sosenkyo_vote_start"
    )
    async def vote_button(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(
            embed=discord.Embed(
                title=CATEGORIES[1],
                description="投票するユーザーを選んでください",
                color=discord.Color.gold()
            ),
            view=VoteCategoryView(self.bot, 1),
            ephemeral=True
        )


# =========================
# Cog本体
# =========================
class SosenkyoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(SosenkyoVotePersistentView(bot))
        print("✅ 総選挙 persistent vote button restored")

    async def check_admin(self, interaction: discord.Interaction):
        # 特定ユーザー複数許可
        if interaction.user.id in ALLOWED_USER_IDS:
            return True

        # 固定管理者ロール
        if any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            return True

        # DB管理ロール
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if any(str(r.id) in admin_roles for r in interaction.user.roles):
            return True

        return False

    @app_commands.command(name="総選挙パネル設置")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def setup_panel(self, interaction: discord.Interaction, title: str, body: str):
        if not await self.check_admin(interaction):
            return await interaction.response.send_message(
                "❌ 管理者のみ使用できます。",
                ephemeral=True
            )

        embed = discord.Embed(title=title, description=body, color=discord.Color.gold())

        await interaction.channel.send(
            embed=embed,
            view=SosenkyoVotePersistentView(self.bot)
        )

        await interaction.response.send_message(
            "✅ 総選挙パネルを設置しました。",
            ephemeral=True
        )

    @app_commands.command(name="総選挙内容確認")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def check_comments(self, interaction: discord.Interaction, category_no: int, user: discord.Member):
        if not await self.check_admin(interaction):
            return await interaction.response.send_message("❌ 管理者のみ使用できます。", ephemeral=True)

        rows = await self.bot.db._fetch("""
            SELECT comment
            FROM sosenkyo_votes
            WHERE guild_id=$1
              AND category_no=$2
              AND target_user_id=$3
              AND comment IS NOT NULL
              AND comment != ''
            ORDER BY updated_at DESC
        """,
        str(interaction.guild.id),
        category_no,
        str(user.id))

        if not rows:
            return await interaction.response.send_message("コメントはまだありません。", ephemeral=True)

        pages = []
        current = ""

        for row in rows:
            text = f"・{row['comment']}\n"
            if len(current) + len(text) > 1800:
                pages.append(current)
                current = text
            else:
                current += text

        if current:
            pages.append(current)

        embeds = [
            discord.Embed(
                title=f"{CATEGORIES[category_no]} - {user.display_name}",
                description=page,
                color=discord.Color.blurple()
            )
            for page in pages
        ]

        await interaction.response.send_message(
            embed=embeds[0],
            view=PageView(embeds),
        )

    @app_commands.command(name="総選挙結果発表")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ranking(self, interaction: discord.Interaction):
        if not await self.check_admin(interaction):
            return await interaction.response.send_message("❌ 管理者のみ使用できます。", ephemeral=True)

        pages = []

        for no, name in CATEGORIES.items():
            rows = await self.bot.db._fetch("""
                SELECT target_user_id, COUNT(*) AS votes
                FROM sosenkyo_votes
                WHERE guild_id=$1
                  AND category_no=$2
                GROUP BY target_user_id
                ORDER BY votes DESC
                LIMIT 10
            """, str(interaction.guild.id), no)

            desc = ""
            for i, row in enumerate(rows, 1):
                user = interaction.guild.get_member(int(row["target_user_id"]))
                uname = user.display_name if user else row["target_user_id"]
                desc += f"**{i}位** {uname} - {row['votes']}票\n"

            pages.append(
                discord.Embed(
                    title=f"🏆 {name}",
                    description=desc or "投票なし",
                    color=discord.Color.gold()
                )
            )

        await interaction.response.send_message(
            embed=pages[0],
            view=PageView(pages),
        )

    @app_commands.command(name="総選挙投票リセット")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def reset_votes(self, interaction: discord.Interaction):
        if not await self.check_admin(interaction):
            return await interaction.response.send_message("❌ 管理者のみ使用できます。", ephemeral=True)

        await self.bot.db._execute("""
            DELETE FROM sosenkyo_votes
            WHERE guild_id = $1
        """, str(interaction.guild.id))

        await interaction.response.send_message(
            "🗑️ 総選挙投票をリセットしました。",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SosenkyoCog(bot))
