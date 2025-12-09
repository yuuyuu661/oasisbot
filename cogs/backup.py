# cogs/backup.py
import io
import json
import datetime

import discord
from discord.ext import commands, tasks
from discord import app_commands


class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Bot 起動後に自動バックアップループ開始
        self.auto_backup.start()

    # ------------------------------------------------------
    # /backup_now
    #   現在の DB 全体を JSON にして、このチャンネルに送信
    # ------------------------------------------------------
    @app_commands.command(
        name="backup_now",
        description="DBのスナップショットをJSONでバックアップします（管理者ロール限定）"
    )
    async def backup_now(self, interaction: discord.Interaction):
        bot = self.bot

        if interaction.guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True
            )

        # 管理者ロールチェック（settings.admin_roles）
        settings = await bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ このコマンドを実行できるのは管理者ロール所持者のみです。",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        # DB 接続
        if bot.db.conn is None:
            await bot.db.connect()

        conn = bot.db.conn

        tables = [
            "users",
            "role_salaries",
            "settings",
            "subscription_settings",
            "interview_settings",
            "hotel_settings",
            "hotel_tickets",
            "hotel_rooms",
        ]

        backup = {
            "_meta": {
                "created_at": datetime.datetime.now().isoformat(),
                "guild_id": str(interaction.guild.id),
                "by_user": str(interaction.user.id),
                "type": "manual",
            }
        }

        for table in tables:
            rows = await conn.fetch(f"SELECT * FROM {table}")
            backup[table] = [dict(r) for r in rows]

        json_str = json.dumps(backup, ensure_ascii=False, indent=2)
        json_bytes = json_str.encode("utf-8")

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"oasis_backup_{ts}.json"

        file_obj = discord.File(
            io.BytesIO(json_bytes),
            filename=filename
        )

        # 手動バックアップは「コマンドを打ったチャンネル」に送信
        await interaction.channel.send(
            content="📦 手動バックアップを出力しました。",
            file=file_obj
        )

        await interaction.followup.send(
            "✅ バックアップJSONをこのチャンネルに送信しました。",
            ephemeral=True
        )

    # ------------------------------------------------------
    # 自動バックアップ（1時間ごと）
    #   settings.log_backup に設定したチャンネルへ送信
    # ------------------------------------------------------
    @tasks.loop(hours=1)
    async def auto_backup(self):
        bot = self.bot

        # DB 接続が切れていたら再接続
        if bot.db.conn is None:
            try:
                await bot.db.connect()
            except Exception as e:
                print(f"[auto_backup] DB connect error: {e}")
                return

        conn = bot.db.conn

        try:
            settings = await bot.db.get_settings()
        except Exception as e:
            print(f"[auto_backup] get_settings error: {e}")
            return

        backup_ch_id = settings.get("log_backup")
        if not backup_ch_id:
            # バックアップ用チャンネル未設定なら何もしない
            return

        for gid in getattr(bot, "GUILD_IDS", []):
            guild = bot.get_guild(gid)
            if guild is None:
                continue

            ch = guild.get_channel(int(backup_ch_id))
            if ch is None:
                continue

            try:
                tables = [
                    "users",
                    "role_salaries",
                    "settings",
                    "subscription_settings",
                    "interview_settings",
                    "hotel_settings",
                    "hotel_tickets",
                    "hotel_rooms",
                ]

                backup = {
                    "_meta": {
                        "created_at": datetime.datetime.now().isoformat(),
                        "guild_id": str(gid),
                        "type": "auto",
                    }
                }

                for table in tables:
                    rows = await conn.fetch(f"SELECT * FROM {table}")
                    backup[table] = [dict(r) for r in rows]

                json_str = json.dumps(backup, ensure_ascii=False, indent=2)
                json_bytes = json_str.encode("utf-8")

                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"oasis_autobackup_{ts}.json"

                file_obj = discord.File(
                    io.BytesIO(json_bytes),
                    filename=filename
                )

                await ch.send(
                    content=f"⏱ 自動バックアップを出力しました。（{ts}）",
                    file=file_obj
                )
                print(f"[auto_backup] sent for guild {gid} at {ts}")

            except Exception as e:
                print(f"[auto_backup] error in guild {gid}: {e}")

    @auto_backup.before_loop
    async def before_auto_backup(self):
        # Bot 準備完了まで待機
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    cog = BackupCog(bot)
    await bot.add_cog(cog)

    # ギルドスラッシュコマンド登録
    if hasattr(bot, "GUILD_IDS"):
        for gid in bot.GUILD_IDS:
            guild = discord.Object(id=gid)
            for cmd in cog.get_app_commands():
                bot.tree.add_command(cmd, guild=guild)
