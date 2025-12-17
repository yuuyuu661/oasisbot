# cogs/backup.py
import os
import json
import asyncio
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

BACKUP_DIR = "backups"

# bot.py と合わせる（ここだけは固定でOK）
GUILD_IDS = [
    1444580349773348951,
    1420918259187712093,
]


class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_backup_task: asyncio.Task | None = None

    # --------------------------------------------------
    # 共通: settings を安全に dict 化
    # --------------------------------------------------
    async def _get_settings_dict(self) -> dict:
        settings = await self.bot.db.get_settings()
        return dict(settings) if settings else {}

    # --------------------------------------------------
    # 管理者判定（settings.admin_roles + Discord管理者）
    # --------------------------------------------------
    async def is_admin(self, member: discord.Member) -> bool:
        settings = await self._get_settings_dict()
        admin_roles = settings.get("admin_roles") or []

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
                for k, v in list(d.items()):
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

        # グローバル系
        await fetch("settings")
        await fetch("role_salaries")

        return payload

    # --------------------------------------------------
    # バックアップ送信先チャンネル取得（安全）
    # --------------------------------------------------
    async def _get_backup_channel(self) -> discord.TextChannel | None:
        settings = await self._get_settings_dict()
        backup_ch_id = settings.get("log_backup")
        if not backup_ch_id:
            return None

        ch = self.bot.get_channel(int(backup_ch_id))
        if isinstance(ch, discord.TextChannel):
            return ch
        return None

    # --------------------------------------------------
    # バックアップ実行（1回）
    # --------------------------------------------------
    async def run_backup_once(self):
        channel = await self._get_backup_channel()
        if channel is None:
            print("[auto_backup] No valid backup channel. skipped")
            return

        for guild in self.bot.guilds:
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
    # /自動バックアップ（ギルド限定）
    # --------------------------------------------------
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.command(
        name="自動バックアップ",
        description="指定した分数ごとに自動バックアップを行います（管理者）",
    )
    @app_commands.describe(minutes="バックアップ間隔（分）")
    async def auto_backup_command(self, interaction: discord.Interaction, minutes: int):
        if interaction.guild is None:
            return await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)

        if not isinstance(interaction.user, discord.Member) or not await self.is_admin(interaction.user):
            return await interaction.response.send_message("❌ 管理者権限が必要です。", ephemeral=True)

        if minutes < 1:
            return await interaction.response.send_message("⚠️ 1分以上を指定してください。", ephemeral=True)

        # 送信先チャンネルが未設定なら開始させない
        channel = await self._get_backup_channel()
        if channel is None:
            return await interaction.response.send_message(
                "⚠️ バックアップ送信先チャンネル（log_backup）が未設定、または見つかりません。\n"
                "/初期設定 でバックアップ用チャンネルを設定してください。",
                ephemeral=True,
            )

        if self.auto_backup_task and not self.auto_backup_task.done():
            self.auto_backup_task.cancel()

        self.auto_backup_task = asyncio.create_task(self.auto_backup_loop(minutes))

        await interaction.response.send_message(
            f"✅ 自動バックアップを **{minutes}分間隔** で開始しました。\n"
            f"送信先: {channel.mention}\n"
            "再度実行すると間隔を上書きします。",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /バックアップ（手動）（ギルド限定）
    # --------------------------------------------------
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.command(
        name="バックアップ",
        description="このサーバーのデータをバックアップします（管理者）",
    )
    async def backup_now(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)

        if not isinstance(interaction.user, discord.Member) or not await self.is_admin(interaction.user):
            return await interaction.response.send_message("❌ 管理者権限が必要です。", ephemeral=True)

        channel = await self._get_backup_channel()
        if channel is None:
            return await interaction.response.send_message(
                "⚠️ バックアップ送信先チャンネル（log_backup）が未設定、または見つかりません。\n"
                "/初期設定 でバックアップ用チャンネルを設定してください。",
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
            f"✅ 手動バックアップ完了\n送信先: {channel.mention}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
