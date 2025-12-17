# cogs/backup.py
import os
import json
import asyncio
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands


BACKUP_DIR = "backups"


class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_backup_task: asyncio.Task | None = None

    # --------------------------------------------------
    # 管理者判定
    # --------------------------------------------------
    async def is_admin(self, member: discord.Member) -> bool:
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if member.guild_permissions.administrator:
            return True

        return any(str(r.id) in admin_roles for r in member.roles)

    # --------------------------------------------------
    # バックアップデータ生成
    # --------------------------------------------------
    async def make_backup_payload(self, guild: discord.Guild) -> dict:
        await self.bot.db.connect()
        conn = self.bot.db.conn
        gid = str(guild.id)

        payload = {
            "meta": {
                "guild_id": gid,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        async def fetch(table: str, where: str | None = None, *params):
            if where:
                rows = await conn.fetch(f"SELECT * FROM {table} WHERE {where}", *params)
            else:
                rows = await conn.fetch(f"SELECT * FROM {table}")

            result = []
            for r in rows:
                d = dict(r)
                for k, v in d.items():
                    if isinstance(v, datetime):
                        d[k] = v.isoformat()
                result.append(d)

            payload[table] = result

        await fetch("users", "guild_id = $1", gid)
        await fetch("hotel_tickets", "guild_id = $1", gid)
        await fetch("hotel_rooms", "guild_id = $1", gid)
        await fetch("subscription_settings", "guild_id = $1", gid)
        await fetch("interview_settings", "guild_id = $1", gid)
        await fetch("hotel_settings", "guild_id = $1", gid)

        await fetch("settings")
        await fetch("role_salaries")

        return payload

    # --------------------------------------------------
    # バックアップ実行（1回）
    # --------------------------------------------------
    async def run_backup_once(self):
        for guild in self.bot.guilds:
            settings = await self.bot.db.get_settings()
            backup_ch_id = settings["log_backup"]

            if not backup_ch_id:
                continue

            channel = self.bot.get_channel(int(backup_ch_id))
            if not isinstance(channel, discord.TextChannel):
                continue

            payload = await self.make_backup_payload(guild)

            os.makedirs(BACKUP_DIR, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"backup_{guild.id}_{ts}.json"
            path = os.path.join(BACKUP_DIR, filename)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            await channel.send(
                content=f"⏰ 自動バックアップ ({guild.name}) `{ts}`",
                file=discord.File(path, filename=filename),
            )

            print(f"[auto_backup] SUCCESS guild={guild.id}")

    # --------------------------------------------------
    # 自動バックアップループ
    # --------------------------------------------------
    async def auto_backup_loop(self, minutes: int):
        print(f"[Backup] auto backup started: every {minutes} minutes")
        try:
            while True:
                await self.run_backup_once()
                await asyncio.sleep(minutes * 60)
        except asyncio.CancelledError:
            print("[Backup] auto backup stopped")

    # --------------------------------------------------
    # /自動バックアップ
    # --------------------------------------------------
    @app_commands.command(
        name="自動バックアップ",
        description="指定した分数ごとに自動バックアップを行います（管理者）",
    )
    @app_commands.describe(minutes="バックアップ間隔（分）")
    async def auto_backup_command(
        self,
        interaction: discord.Interaction,
        minutes: int,
    ):
        if not await self.is_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ 管理者権限が必要です。",
                ephemeral=True,
            )

        if minutes < 1:
            return await interaction.response.send_message(
                "⚠️ 1分以上を指定してください。",
                ephemeral=True,
            )

        if self.auto_backup_task and not self.auto_backup_task.done():
            self.auto_backup_task.cancel()

        self.auto_backup_task = asyncio.create_task(
            self.auto_backup_loop(minutes)
        )

        await interaction.response.send_message(
            f"✅ 自動バックアップを **{minutes}分間隔** で開始しました。",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /backup_now
    # --------------------------------------------------
    @app_commands.command(
        name="バックアップ",
        description="このサーバーのデータをバックアップします（管理者）",
    )
    async def backup_now(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ 管理者権限が必要です。",
                ephemeral=True,
            )

        guild = interaction.guild
        if guild is None:
            return

        settings = await self.bot.db.get_settings()
        backup_ch_id = settings["log_backup"]

        channel = self.bot.get_channel(int(backup_ch_id))
        if not isinstance(channel, discord.TextChannel):
            return

        await interaction.response.defer(ephemeral=True)

        payload = await self.make_backup_payload(guild)

        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{guild.id}_{ts}.json"
        path = os.path.join(BACKUP_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        await channel.send(
            content=f"📦 手動バックアップ ({guild.name}) `{ts}`",
            file=discord.File(path, filename=filename),
        )

        await interaction.followup.send("✅ 手動バックアップ完了", ephemeral=True)



# --------------------------------------------------
# setup（他の Cog と完全に同じ）
# --------------------------------------------------
async def setup(bot: commands.Bot):
    cog = BackupCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(
                cmd,
                guild=discord.Object(id=gid)
            )
