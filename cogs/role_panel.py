import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1420918259187712093
PANEL_ADMIN_ROLE = 1445403813853925418


class RolePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # メモリ上のキャッシュを必ず用意
        if not hasattr(self.bot, "role_panels"):
            self.bot.role_panels = {}

    # =========================
    # Cogロード時にDBから復元
    # =========================
    async def cog_load(self):
        await self.restore_role_panels()

    async def restore_role_panels(self):
        """
        DBに保存されているロールパネル情報を
        self.bot.role_panels に復元する
        """
        if not hasattr(self.bot, "db"):
            print("RolePanel: bot.db がないため復元をスキップ")
            return

        try:
            rows = await self.bot.db.load_role_panels()

            self.bot.role_panels = {}

            for row in rows:
                message_id = int(row["message_id"])
                panel_data = row["panel_data"] or {}

                # 念のため key=value を文字列/整数で整える
                self.bot.role_panels[message_id] = {
                    str(emoji): int(role_id)
                    for emoji, role_id in panel_data.items()
                }

            print(f"ROLE PANEL LOADED: {len(rows)}")
        except Exception as e:
            print(f"RolePanel restore error: {e}")

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
        if PANEL_ADMIN_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message(
                "このコマンドは管理者のみ使用できます",
                ephemeral=True
            )

        pairs = [
            (emoji1, role1),
            (emoji2, role2),
            (emoji3, role3),
            (emoji4, role4),
            (emoji5, role5),
        ]

        valid_pairs = [(e, r) for e, r in pairs if e and r]

        if not valid_pairs:
            return await interaction.response.send_message(
                "最低1つは絵文字とロールを指定してください",
                ephemeral=True
            )

        embed = discord.Embed(
            title=title,
            description=body,
            color=discord.Color.blue()
        )

        await interaction.response.defer(ephemeral=True)

        msg = await interaction.channel.send(embed=embed)

        for emoji, role in valid_pairs:
            await msg.add_reaction(emoji)

        panel_data = {
            str(e): r.id for e, r in valid_pairs
        }

        # メモリ保存
        self.bot.role_panels[msg.id] = panel_data

        # DB保存
        asyncio.create_task(
            self.bot.db.save_role_panel(
                message_id=msg.id,
                guild_id=interaction.guild_id,
                data=panel_data
            )
        )

        await interaction.followup.send("設置しました", ephemeral=True)

    # =========================
    # リアクション付与
    # =========================
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        if payload.guild_id is None:
            return

        panel = self.bot.role_panels.get(payload.message_id)
        if not panel:
            return

        emoji = str(payload.emoji)
        role_id = panel.get(emoji)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        role = guild.get_role(role_id)
        if role is None:
            return

        try:
            await member.add_roles(role, reason="ロール付与パネル")
        except Exception as e:
            print(f"RolePanel add role error: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id is None:
            return

        panel = self.bot.role_panels.get(payload.message_id)
        if not panel:
            return

        emoji = str(payload.emoji)
        role_id = panel.get(emoji)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        role = guild.get_role(role_id)
        if role is None:
            return

        try:
            await member.remove_roles(role, reason="ロール付与パネル解除")
        except Exception as e:
            print(f"RolePanel remove role error: {e}")


async def setup(bot):
    await bot.add_cog(RolePanel(bot))
