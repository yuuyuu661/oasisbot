import random
import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418


class TempVCCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # guild_id -> list[setting]
        self.vc_settings: dict[int, list[dict]] = {}

        # 作成された一時VC
        # created_vc_id -> source_vc_id
        self.created_vcs: dict[int, int] = {}

    async def cog_load(self):
        await self._restore_settings()

    async def _restore_settings(self):
        # =========================
        # 転送設定復元
        # =========================
        rows = await self.bot.db._fetch("""
            SELECT guild_id, source_vc_id, max_users, names_a, names_b, name_c
            FROM temp_vc_settings
        """)

        self.vc_settings.clear()

        for r in rows:
            gid = int(r["guild_id"])
            self.vc_settings.setdefault(gid, []).append({
                "source_vc_id": int(r["source_vc_id"]),
                "max_users": r["max_users"],
                "names_a": r["names_a"] or [],
                "names_b": r["names_b"] or [],
                "name_c": r["name_c"],
            })

        # =========================
        # 作成済みVC復元（←ここ追加）
        # =========================
        created_rows = await self.bot.db._fetch("""
            SELECT channel_id, source_vc_id
            FROM temp_created_vcs
        """)

        self.created_vcs.clear()

        for r in created_rows:
            self.created_vcs[int(r["channel_id"])] = int(r["source_vc_id"])

    @app_commands.command(name="vc転送設定", description="VC転送設定を追加します")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(
        指定vc="入室したら転送を発動する元VC",
        vc最大人数="生成VCの最大人数",
        vc名a="VC名A候補（カンマ区切り複数可）",
        vc名b="VC名B候補（カンマ区切り複数可）",
        vc名c="ユーザー名の後ろに付ける名前"
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
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "このコマンドを使う権限がありません。",
                ephemeral=True
            )
            return

        use_ab = bool(vc名a and vc名b)
        use_c = bool(vc名c)

        if use_ab and use_c:
            await interaction.response.send_message(
                "VC名A+B か VC名C のどちらか片方だけ指定してください。",
                ephemeral=True
            )
            return

        if not use_ab and not use_c:
            await interaction.response.send_message(
                "VC名A+B または VC名C を指定してください。",
                ephemeral=True
            )
            return

        if vc最大人数 < 0 or vc最大人数 > 99:
            await interaction.response.send_message(
                "VC最大人数は 0〜99 で指定してください。0 は無制限です。",
                ephemeral=True
            )
            return

        names_a = [x.strip() for x in vc名a.split(",") if x.strip()] if vc名a else []
        names_b = [x.strip() for x in vc名b.split(",") if x.strip()] if vc名b else []

        if use_ab and (not names_a or not names_b):
            await interaction.response.send_message(
                "VC名A と VC名B は空欄なしで指定してください。",
                ephemeral=True
            )
            return

        setting = {
            "source_vc_id": 指定vc.id,
            "max_users": vc最大人数,
            "names_a": names_a,
            "names_b": names_b,
            "name_c": vc名c,
        }

        guild_id = interaction.guild.id
        self.vc_settings.setdefault(guild_id, []).append(setting)

        await self.bot.db._execute("""
            INSERT INTO temp_vc_settings
            (guild_id, source_vc_id, max_users, names_a, names_b, name_c)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (guild_id, source_vc_id)
            DO UPDATE SET
                max_users = EXCLUDED.max_users,
                names_a = EXCLUDED.names_a,
                names_b = EXCLUDED.names_b,
                name_c = EXCLUDED.name_c
        """, str(guild_id), str(指定vc.id), vc最大人数, names_a, names_b, vc名c)

        await interaction.response.send_message(
            f"✅ VC転送設定を追加しました\n"
            f"対象VC: {指定vc.mention}\n"
            f"最大人数: {vc最大人数}",
            ephemeral=True
        )

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
        settings = self.vc_settings.get(guild.id, [])

        # まず、削除済みVC設定を掃除
        alive_settings = []
        changed = False

        for s in settings:
            src = guild.get_channel(s["source_vc_id"])
            if src is None:
                changed = True
                await self.bot.db._execute("""
                    DELETE FROM temp_vc_settings
                    WHERE guild_id = $1 AND source_vc_id = $2
                """, str(guild.id), str(s["source_vc_id"]))
            else:
                alive_settings.append(s)

        if changed:
            self.vc_settings[guild.id] = alive_settings
            settings = alive_settings

        # 入室時：トリガーVCに入ったら生成
        if after.channel is not None:
            matched = next(
                (s for s in settings if s["source_vc_id"] == after.channel.id),
                None
            )

            if matched is not None:
                base_channel = after.channel

                if matched["name_c"]:
                    vc_name = f"{member.display_name}{matched['name_c']}"
                else:
                    a = random.choice(matched["names_a"])
                    b = random.choice(matched["names_b"])
                    vc_name = f"{a}{b}"

                new_vc = await guild.create_voice_channel(
                    name=vc_name,
                    category=base_channel.category,
                    overwrites=base_channel.overwrites,
                    bitrate=base_channel.bitrate,
                    user_limit=matched["max_users"]
                )

                self.created_vcs[new_vc.id] = base_channel.id

                await self.bot.db._execute("""
                    INSERT INTO temp_created_vcs
                    (guild_id, channel_id, source_vc_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (channel_id) DO NOTHING
                """, str(guild.id), str(new_vc.id), str(base_channel.id))
                await member.move_to(new_vc)

        # 退出時：作成VCが空なら削除
        if before.channel is not None and before.channel.id in self.created_vcs:
            if len(before.channel.members) == 0:
                channel_id = before.channel.id

                self.created_vcs.pop(channel_id, None)

                await self.bot.db._execute("""
                    DELETE FROM temp_created_vcs
                    WHERE channel_id = $1
                """, str(channel_id))

                try:
                    await before.channel.delete()
                except discord.NotFound:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(TempVCCog(bot))
