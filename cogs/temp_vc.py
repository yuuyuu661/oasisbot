import json
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
        # created vc id -> source vc id
        self.created_vcs: dict[int, int] = {}

    async def cog_load(self):
        await self.bot.wait_until_ready()
        await self._restore_settings()

    async def _restore_settings(self):
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

    @app_commands.command(name="vc転送設定")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def vc_transfer_setting(
        self,
        interaction: discord.Interaction,
        指定vc: discord.VoiceChannel,
        vc最大人数: int,
        vc名a: str | None = None,
        vc名b: str | None = None,
        vc名c: str | None = None,
    ):
        if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        use_ab = bool(vc名a and vc名b)
        use_c = bool(vc名c)

        if not use_ab and not use_c:
            return await interaction.response.send_message(
                "A+B か C のどちらかを指定してください", ephemeral=True
            )

        names_a = [x.strip() for x in vc名a.split(",")] if vc名a else []
        names_b = [x.strip() for x in vc名b.split(",")] if vc名b else []

        setting = {
            "source_vc_id": 指定vc.id,
            "max_users": vc最大人数,
            "names_a": names_a,
            "names_b": names_b,
            "name_c": vc名c,
    await bot.add_cog(TempVCCog(bot))
