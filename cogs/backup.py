# cogs/backup.py
import os
import json
import asyncio
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands


BACKUP_DIR = "backups"  # バックアップファイル保存用ディレクトリ


class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_backup_task: asyncio.Task | None = None
        self.auto_backup_minutes: int | None = None

    # --------------------------------------------------
    # ヘルパー：管理者判定（settings.admin_roles + Discord管理者権限）
    # --------------------------------------------------
    async def is_admin(self, member: discord.Member) -> bool:
        db = self.bot.db
        settings = await db.get_settings()
        settings_dict = dict(settings) if settings else {}
        admin_roles = settings_dict.get("admin_roles") or []

        if member.guild_permissions.administrator:
            return True

        return any(str(r.id) in admin_roles for r in member.roles)

    # --------------------------------------------------
    # ヘルパー：1ギルド分のバックアップデータ生成
    # --------------------------------------------------
    async def make_backup_payload(self, guild: discord.Guild) -> dict:
        await self.bot.db.connect()
        conn = self.bot.db.conn
        gid = str(guild.id)

        payload: dict = {
            "meta": {
                "guild_id": gid,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        async def fetch_table(table: str, where: str | None = None, *params):
            rows = []
            if where:
                data = await conn.fetch(f"SELECT * FROM {table} WHERE {where}", *params)
            else:
                data = await conn.fetch(f"SELECT * FROM {table}")

            for r in data:
                d = dict(r)
                for k, v in list(d.items()):
                    if isinstance(v, datetime):
                        d[k] = v.isoformat()
                rows.append(d)

            payload[table] = rows

        await fetch_table("users", "guild_id = $1", gid)
        await fetch_table("hotel_tickets", "guild_id = $1", gid)
        await fetch_table("hotel_rooms", "guild_id = $1", gid)
        await fetch_table("subscription_settings", "guild_id = $1", gid)
        await fetch_table("interview_settings", "guild_id = $1", gid)
        await fetch_table("hotel_settings", "guild_id = $1", gid)

        await fetch_table("settings")
        await fetch_table("role_salaries")

        return payload

    # --------------------------------------------------
    # 実処理：バックアップ1回分
    # --------------------------------------------------
    async def run_backup_once(self):
        for guild in self.bot.guilds:
            settings = await self.bot.db.get_settings()
            settings_dict = dict(settings) if settings else {}
            backup_ch_id = settings_dict.get("log_backup")

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
                "❌ このコマンドを実行する権限がありません。",
                ephemeral=True,
            )

        if minutes < 1:
            return await interaction.response.send_message(
                "⚠️ 1分以上を指定してください。",
                ephemeral=True,
            )

        if self.auto_backup_task and not self.auto_backup_task.done():
            self.auto_backup_task.cancel()

        self.auto_backup_minutes = minutes
        self.auto_backup_task = asyncio.create_task(
            self.auto_backup_loop(minutes)
        )

        await interaction.response.send_message(
            f"✅ 自動バックアップを **{minutes}分間隔** で開始しました。\n"
            "再度実行すると間隔を上書きします。",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /backup_now（据え置き）
    # --------------------------------------------------
    @app_commands.command(
        name="backup_now",
        description="このサーバーのデータをバックアップします（管理者用）",
    )
    async def backup_now(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True,
            )

        if not await self.is_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ このコマンドを実行する権限がありません。",
                ephemeral=True,
            )

        settings = await self.bot.db.get_settings()
        settings_dict = dict(settings) if settings else {}
        backup_ch_id = settings_dict.get("log_backup")

        if not backup_ch_id:
            return await interaction.response.send_message(
                "⚠️ バックアップ送信先チャンネルが設定されていません。",
                ephemeral=True,
            )

        channel = self.bot.get_channel(int(backup_ch_id))
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "⚠️ バックアップチャンネルが見つかりません。",
                ephemeral=True,
            )

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

        await interaction.followup.send(
            f"✅ 手動バックアップを実行しました。\n送信先: {channel.mention}",
            ephemeral=True,
        )


# --------------------------
# setup
# --------------------------
async def setup(bot: commands.Bot):
    cog = BackupCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
