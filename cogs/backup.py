# cogs/backup.py
import os
import json
from datetime import datetime

import discord
from discord.ext import commands, tasks
from discord import app_commands


BACKUP_DIR = "backups"  # バックアップファイル保存用ディレクトリ


class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.auto_backup.start()
        print("[Backup] auto_backup started (cog_load)")    # --------------------------------------------------
    # ヘルパー：管理者判定（settings.admin_roles + Discord管理者権限）
    # --------------------------------------------------
    async def is_admin(self, member: discord.Member) -> bool:
        db = self.bot.db
        settings = await db.get_settings()
        settings_dict = dict(settings) if settings else {}
        admin_roles = settings_dict.get("admin_roles") or []

        # Discord の「サーバー管理者」権限を持っていればOK
        if member.guild_permissions.administrator:
            return True

        # settings に登録された管理ロールを持っていればOK
        return any(str(r.id) in admin_roles for r in member.roles)

    # --------------------------------------------------
    # ヘルパー：1ギルド分のバックアップデータを作る
    # --------------------------------------------------
    async def make_backup_payload(self, guild: discord.Guild) -> dict:
        """
        1つのギルドに関する DB データを JSON に詰める。
        既存の /backup_now や auto_backup と同じ構造で出力する想定。
        """
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
                # datetime 型は ISO 文字列に変換して保存
                for k, v in list(d.items()):
                    if isinstance(v, datetime):
                        d[k] = v.isoformat()
                rows.append(d)
            payload[table] = rows

        # ギルド依存のテーブル
        await fetch_table("users", "guild_id = $1", gid)
        await fetch_table("hotel_tickets", "guild_id = $1", gid)
        await fetch_table("hotel_rooms", "guild_id = $1", gid)
        await fetch_table("subscription_settings", "guild_id = $1", gid)
        await fetch_table("interview_settings", "guild_id = $1", gid)
        await fetch_table("hotel_settings", "guild_id = $1", gid)

        # グローバル系テーブル（settings, role_salaries）
        await fetch_table("settings")
        await fetch_table("role_salaries")

        return payload

    # --------------------------------------------------
    # /backup_now : 手動バックアップ
    # --------------------------------------------------
    @app_commands.command(
        name="backup_now",
        description="このサーバーのデータをバックアップします（管理者用）",
    )
    async def backup_now(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。", ephemeral=True
            )

        # 管理者チェック
        if not await self.is_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ このコマンドを実行する権限がありません。", ephemeral=True
            )

        # バックアップチャンネル設定取得
        settings = await self.bot.db.get_settings()
        settings_dict = dict(settings) if settings else {}
        backup_ch_id = settings_dict.get("log_backup")

        if not backup_ch_id:
            return await interaction.response.send_message(
                "⚠️ バックアップ送信先チャンネルが設定されていません。\n"
                "/初期設定 でバックアップ用チャンネルを設定してください。",
                ephemeral=True,
            )

        channel = self.bot.get_channel(int(backup_ch_id))
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "⚠️ 設定されているバックアップチャンネルが見つかりません。", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        # バックアップデータ生成
        payload = await self.make_backup_payload(guild)

        # ファイルに保存
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{guild.id}_{ts}.json"
        path = os.path.join(BACKUP_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # Discord に送信
        file = discord.File(path, filename=filename)
        await channel.send(
            content=f"📦 手動バックアップ ({guild.name}) `{ts}`", file=file
        )

        await interaction.followup.send(
            f"✅ 手動バックアップを実行しました。\n送信先: {channel.mention}",
            ephemeral=True,
        )

        print(f"[manual_backup] sent for guild {guild.id} at {ts}")

    # --------------------------------------------------
    # /restore_backup : バックアップから復元
    # --------------------------------------------------
    @app_commands.command(
        name="restore_backup",
        description="バックアップJSONファイルからこのサーバーのデータを復元します（危険）",
    )
    @app_commands.describe(
        file="以前 /backup_now や自動バックアップで取得した JSON ファイル"
    )
    async def restore_backup(
        self, interaction: discord.Interaction, file: discord.Attachment
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。", ephemeral=True
            )

        # 管理者チェック
        if not await self.is_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ このコマンドを実行する権限がありません。", ephemeral=True
            )

        if not file.filename.endswith(".json"):
            return await interaction.response.send_message(
                "⚠️ JSONファイルを指定してください。", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        # 添付JSONを読み込み
        try:
            raw = await file.read()
            backup = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return await interaction.followup.send(
                f"❌ JSONの読み込みに失敗しました: {e}", ephemeral=True
            )

        meta = backup.get("meta", {})
        backup_guild_id = str(meta.get("guild_id")) if meta.get("guild_id") else None

        # ギルドIDが異なるバックアップからの復元は拒否
        if backup_guild_id is None:
            return await interaction.followup.send(
                "❌ このバックアップには guild_id 情報が含まれていません。"
                "現在の形式のバックアップJSONのみ復元できます。",
                ephemeral=True,
            )

        if backup_guild_id != str(guild.id):
            return await interaction.followup.send(
                "❌ このバックアップは別のサーバー用です。\n"
                f"バックアップの guild_id: `{backup_guild_id}` / "
                f"このサーバー: `{guild.id}`",
                ephemeral=True,
            )

        # 実際のテーブルデータ部分を取り出す
        table_data: dict = {
            k: v for k, v in backup.items() if k != "meta" and isinstance(v, list)
        }

        if not table_data:
            return await interaction.followup.send(
                "❌ 復元対象データが見つかりませんでした。", ephemeral=True
            )

        conn = self.bot.db.conn
        if conn is None:
            await self.bot.db.connect()
            conn = self.bot.db.conn

        # 復元処理（トランザクション内でまとめて実行）
        from datetime import datetime as _dt

        try:
            async with conn.transaction():
                # テーブルごとに DELETE → INSERT
                for table_name, rows in table_data.items():
                    if not rows:
                        continue

                    # 1行目のキーで guild_id カラムの有無を判定
                    first_row = rows[0]
                    has_guild_id = "guild_id" in first_row

                    # 既存データを削除
                    if has_guild_id:
                        await conn.execute(
                            f"DELETE FROM {table_name} WHERE guild_id = $1",
                            str(guild.id),
                        )
                    else:
                        # settings や role_salaries などギルド非依存テーブル
                        await conn.execute(f"DELETE FROM {table_name}")

                    # 行を挿入
                    for row in rows:
                        cols = []
                        vals = []

                        for k, v in row.items():
                            # guild_id は常に現在のサーバーIDで上書き
                            if k == "guild_id":
                                v = str(guild.id)

                            # ISO文字列の日時を timestamp に戻す
                            if (
                                isinstance(v, str)
                                and (k.endswith("_at") or k.endswith("_time"))
                            ):
                                try:
                                    v = _dt.fromisoformat(v)
                                except Exception:
                                    pass

                            cols.append(k)
                            vals.append(v)

                        placeholders = ", ".join(
                            f"${i}" for i in range(1, len(cols) + 1)
                        )
                        col_names = ", ".join(cols)
                        sql = (
                            f"INSERT INTO {table_name} ({col_names}) "
                            f"VALUES ({placeholders})"
                        )
                        await conn.execute(sql, *vals)

        except Exception as e:
            return await interaction.followup.send(
                f"❌ 復元中にエラーが発生しました。\n{e}", ephemeral=True
            )

        await interaction.followup.send(
            "✅ バックアップからデータを復元しました。\n"
            "※ 既存データはこのバックアップ内容で上書きされています。",
            ephemeral=True,
        )

        print(
            f"[restore_backup] restored guild {guild.id} "
            f"from attachment {file.filename}"
        )

    # --------------------------------------------------
    # 自動バックアップ（1時間ごと）
    # --------------------------------------------------
    @tasks.loop(minutes=1)
    async def auto_backup(self):
        """
        手動バックアップと同じ処理を自動で定期実行する。
        Bot が所属する全ギルドが対象。
        """
        for guild in self.bot.guilds:
            if guild is None:
                continue

            # settings（共通設定）からバックアップチャンネルを取得
            settings = await self.bot.db.get_settings()
            settings_dict = dict(settings) if settings else {}
            backup_ch_id = settings_dict.get("log_backup")

            if not backup_ch_id:
                print(f"[auto_backup] No backup channel. skipped={guild.id}")
                continue

            channel = self.bot.get_channel(int(backup_ch_id))
            if not isinstance(channel, discord.TextChannel):
                print(f"[auto_backup] Invalid channel. skipped={guild.id}")
                continue

            try:
                # 手動バックアップと同じ処理
                payload = await self.make_backup_payload(guild)

                os.makedirs(BACKUP_DIR, exist_ok=True)
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                filename = f"backup_{guild.id}_{ts}.json"
                path = os.path.join(BACKUP_DIR, filename)

                # JSON 書き込み
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

                file = discord.File(path, filename=filename)

                # Discord へ送信
                await channel.send(
                    content=f"⏰ 自動バックアップ ({guild.name}) `{ts}`",
                    file=file
                )

                print(f"[auto_backup] SUCCESS guild={guild.id}")

            except Exception as e:
                print(f"[auto_backup] ERROR guild={guild.id}: {e}")

    @auto_backup.before_loop
    async def before_auto_backup(self):
        """
        自動バックアップ開始前に Bot の準備が整うまで待つ。
        """
        await self.bot.wait_until_ready()


# --------------------------
# setup（必須）
# --------------------------
async def setup(bot: commands.Bot):
    cog = BackupCog(bot)
    await bot.add_cog(cog)

    # 既存設計と同じく、各ギルドにスラッシュコマンドを登録
    for cmd in cog.get_app_commands():
        for gid in getattr(bot, "GUILD_IDS", []):
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))