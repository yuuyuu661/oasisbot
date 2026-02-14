# cogs/hotel/hotel_cog.py

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
from typing import Optional

from .checkin import CheckinButton
from .ticket_dropdown import TicketBuyDropdown, TicketBuyExecuteButton
from .room_panel import HotelRoomControlPanel


class HotelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self._hotel_db_lock = asyncio.Lock()

        # ★ 自動削除監視タスクを起動
        self.bot.loop.create_task(self._hotel_expire_task())

        # ★ 永続View登録タスクを起動（ホテルパネル用）
        self.bot.loop.create_task(self._register_persistent_hotel_panels())

        # 追加：VC存在チェックによるDBクリーンアップ
        self.bot.loop.create_task(self._hotel_orphan_cleanup_task())

    # --------------------------------------------------
    # DBが使えるまで待つ（共通）
    # --------------------------------------------------
    async def _wait_db_ready(self):
        await self.bot.wait_until_ready()

        while True:
            try:
                if getattr(self.bot, "db", None) is None:
                    await asyncio.sleep(1)
                    continue

                await self.bot.db._ensure_pool()

                if self.bot.db.pool is None:
                    await asyncio.sleep(1)
                    continue

                break
            except Exception as e:
                print("[Hotel] waiting db error:", e)
                await asyncio.sleep(2)

    # ================================
    # 🔥 ホテル自動削除タスク
    # ================================
    async def _hotel_expire_task(self):
        await self._wait_db_ready()

        while not self.bot.is_closed():
            try:
                now = datetime.utcnow()

                async with self._hotel_db_lock:
                    rows = await self.bot.db._fetch(
                        "SELECT channel_id, guild_id, expire_at FROM hotel_rooms"
                    )

                for row in rows:
                    expire_at = row["expire_at"]
                    if expire_at and now >= expire_at:
                        guild_id = int(row["guild_id"])
                        channel_id = int(row["channel_id"])

                        guild = self.bot.get_guild(guild_id)
                        if guild:
                            vc = guild.get_channel(channel_id)
                            if vc:
                                try:
                                    await vc.delete(reason="高級ホテル：期限切れによる自動削除")
                                except Exception as e:
                                    print("Hotel auto delete VC error:", e)

                        async with self._hotel_db_lock:
                            await self.bot.db.delete_room(str(channel_id))

            except Exception as e:
                print("Hotel expire task error:", e)

            await asyncio.sleep(30)


    # ================================
    # ✅ 永続View登録（ホテルパネル）
    # ================================
    async def _register_persistent_hotel_panels(self):
        await self._wait_db_ready()

        try:
            rows = await self.bot.db._fetch("SELECT * FROM hotel_settings")
        except Exception as e:
            print("[Hotel] load hotel_settings failed:", repr(e))
            return

        for cfg in rows:
            try:
                guild_id = str(cfg["guild_id"])

                cfg_dict = dict(cfg)

                view = discord.ui.View(timeout=None)

                # ホテルパネル（チェックイン＋購入）
                view.add_item(CheckinButton(cfg, guild_id))

                selector = TicketBuyDropdown(cfg, guild_id)
                view.add_item(selector)
                view.add_item(TicketBuyExecuteButton(selector, cfg, guild_id))

                self.bot.add_view(view)
                print(f"[Hotel] persistent hotel panel view registered: guild={guild_id}")

            except Exception as e:
                print("[Hotel] persistent view register error:", repr(e))

        # ルーム操作パネル（インチャット用）はギルド共通で1回だけ登録
        self.bot.add_view(HotelRoomControlPanel())
        print("[Hotel] persistent room control panel registered")


    # ================================
    # VC削除 → DBクリーンアップ
    # ================================
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.VoiceChannel):
            room = await self.bot.db.get_room(str(channel.id))
            if room:
                await self.bot.db.delete_room(str(channel.id))
                print(f"[Hotel] Cleanup → Deleted room {channel.id} from DB")

    # ======================================================
    # /ホテル初期設定
    # 既存カテゴリを複数登録（空きがあるカテゴリを自動選択）
    # ======================================================
    @app_commands.command(name="ホテル初期設定", description="ホテル機能の初期設定を行います（管理者）")
    @app_commands.describe(
        manager_role="ホテル管理ロール",
        log_channel="ホテルログ送信先",
        sub_role="サブ垢ロール",
        price_1="チケット1枚の価格",
        price_10="チケット10枚の価格",
        price_30="チケット30枚の価格",
        category1="ホテルVCを作成するカテゴリ（優先1）",
        category2="ホテルVCを作成するカテゴリ（優先2）",
        category3="ホテルVCを作成するカテゴリ（優先3）",
        category4="ホテルVCを作成するカテゴリ（優先4）",
        category5="ホテルVCを作成するカテゴリ（優先5）",
    )
    async def hotel_setup(
        self,
        interaction: discord.Interaction,
        manager_role: discord.Role,
        log_channel: discord.TextChannel,
        sub_role: discord.Role,
        price_1: int,
        price_10: int,
        price_30: int,
        category1: discord.CategoryChannel,
        category2: Optional[discord.CategoryChannel] = None,
        category3: Optional[discord.CategoryChannel] = None,
        category4: Optional[discord.CategoryChannel] = None,
        category5: Optional[discord.CategoryChannel] = None,
    ):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        cats = [category1, category2, category3, category4, category5]
        category_ids = [str(c.id) for c in cats if c is not None]

        await self.bot.db._execute(
            """
            INSERT INTO hotel_settings (
                guild_id, manager_role, log_channel, sub_role,
                ticket_price_1, ticket_price_10, ticket_price_30,
                category_ids
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                manager_role=$2,
                log_channel=$3,
                sub_role=$4,
                ticket_price_1=$5,
                ticket_price_10=$6,
                ticket_price_30=$7,
                category_ids=$8;
            """,
            guild_id,
            str(manager_role.id),
            str(log_channel.id),
            str(sub_role.id),
            price_1,
            price_10,
            price_30,
            category_ids
        )

        text = "🏨 ホテル初期設定を更新しました！\n"
        text += "作成カテゴリ: " + ", ".join([f"<#{cid}>" for cid in category_ids])
        await interaction.response.send_message(text, ephemeral=True)

        # 任意：設定変更直後に永続Viewを再登録したい場合（重複登録しても害は小さい）
        # 必要なら有効化してください
        # try:
        #     cfg = await self.bot.db.conn.fetchrow("SELECT * FROM hotel_settings WHERE guild_id=$1", guild_id)
        #     if cfg:
        #         view = discord.ui.View(timeout=None)
        #         view.add_item(CheckinButton(cfg, guild_id))
        #         selector = TicketBuyDropdown(cfg, guild_id)
        #         view.add_item(selector)
        #         view.add_item(TicketBuyExecuteButton(selector, cfg, guild_id))
        #         self.bot.add_view(view)
        # except Exception as e:
        #     print("[Hotel] re-register persistent view after setup failed:", repr(e))

    # ======================================================
    # /ホテルパネル生成
    # ======================================================
    @app_commands.command(name="ホテルパネル生成", description="ホテルのチェックインパネルを生成します（管理者）")
    async def hotel_panel(self, interaction: discord.Interaction, title: str, description: str):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        hotel_config = await self.bot.db._fetchrow(
            "SELECT * FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )
        if not hotel_config:
            return await interaction.response.send_message(
                "❌ ホテル初期設定がまだ行われていません。",
                ephemeral=True
            )

        embed = discord.Embed(title=title, description=description, color=0xF4D03F)
        
        fg_dict = dict(hotel_config)
        
        # 永続Viewとして成立する構成（custom_id付き）
        view = discord.ui.View(timeout=None)
        view.add_item(CheckinButton(hotel_config, guild_id))

        selector = TicketBuyDropdown(hotel_config, guild_id)
        view.add_item(selector)
        view.add_item(TicketBuyExecuteButton(selector, hotel_config, guild_id))

        await interaction.response.send_message(embed=embed, view=view)

    # ======================================================
    # /チケット確認
    # ======================================================
    @app_commands.command(name="チケット確認", description="自分の所持チケット数を確認します")
    async def ticket_check_cmd(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        tickets = await self.bot.db.get_tickets(user_id, guild_id)
        await interaction.response.send_message(
            f"🎫 所持チケット: **{tickets}枚**",
            ephemeral=True
        )

    # ================================
    # /ホテルボタン再送（ルーム内パネル用）
    # ================================
    @app_commands.command(
        name="ホテルボタン再送",
        description="ホテルルームの操作パネルを再送します（Bot再起動で動かない場合用）"
    )
    async def hotel_resend_panel(self, interaction: discord.Interaction):
        vc = interaction.channel
        if not isinstance(vc, discord.VoiceChannel):
            return await interaction.response.send_message(
                "❌ このコマンドは VC のテキスト欄で実行してください。",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)

        room = await interaction.client.db.get_room(str(vc.id))
        if not room:
            return await interaction.response.send_message(
                "❌ このVCはホテルルームとして登録されていません。",
                ephemeral=True
            )

        owner_id = room["owner_id"]

        hotel_config = await interaction.client.db._fetchrow(
            "SELECT * FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )
        if not hotel_config:
            return await interaction.response.send_message(
                "❌ ホテル初期設定がまだ行われていません。",
                ephemeral=True
            )

        manager_role_id = int(hotel_config["manager_role"])
        sub_role_id = int(hotel_config["sub_role"])

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        user = interaction.user
        ok = False

        if str(user.id) == owner_id:
            ok = True
        elif any(r.id == manager_role_id for r in user.roles):
            ok = True
        elif any(str(r.id) in admin_roles for r in user.roles):
            ok = True

        if not ok:
            return await interaction.response.send_message(
                "❌ このルームの作成者・管理者・ホテルマネージャーのみが実行できます。",
                ephemeral=True
            )

        panel = HotelRoomControlPanel()
        await vc.send("🔄 **操作パネルを再送しました！**", view=panel)

        await interaction.response.send_message("🔄 パネルを再送しました！", ephemeral=True)

    # ======================================================
    # /ホテルリセット
    # ======================================================
    @app_commands.command(
        name="ホテルリセット",
        description="指定ユーザーのホテルルーム情報をリセットします（管理者）"
    )
    async def hotel_reset(self, interaction: discord.Interaction, target: discord.Member):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)
        user_id = str(target.id)

        room = await self.bot.db._fetchrow(
            "SELECT channel_id FROM hotel_rooms WHERE owner_id=$1 AND guild_id=$2",
            user_id, guild_id
        )

        if not room:
            return await interaction.response.send_message(
                f"⚠ {target.mention} は現在ホテルルームを所持していません。",
                ephemeral=True
            )

        channel_id = room["channel_id"]
        channel = guild.get_channel(int(channel_id))

        if channel:
            try:
                await channel.delete(reason="ホテルリセットによるVC削除")
            except Exception:
                pass

        await self.bot.db.delete_room(str(channel_id))

        await interaction.response.send_message(
            f"🧹 {target.mention} のホテルデータをリセットしました！\n再度チェックイン可能になっています。",
            ephemeral=True
        )

    # ============================================
    # /hotel_ticket : ホテルチケット増減・設定（管理用）
    # ============================================
    @app_commands.command(
        name="hotel_ticket",
        description="指定ユーザーの高級ホテルチケットを増減または設定します（管理用）"
    )
    @app_commands.describe(
        member="対象ユーザー",
        mode="add=付与, remove=減算, set=指定枚数に上書き",
        amount="枚数（0以上）"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="付与（増やす）", value="add"),
            app_commands.Choice(name="減算（減らす）", value="remove"),
            app_commands.Choice(name="設定（上書き）", value="set"),
        ]
    )
    async def hotel_ticket(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        mode: app_commands.Choice[str],
        amount: int,
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "サーバー内でのみ使用できます。",
                ephemeral=True
            )

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        is_admin_role = any(str(r.id) in admin_roles for r in interaction.user.roles)

        guild_id = str(guild.id)
        hotel_config = await self.bot.db._fetchrow(
            "SELECT * FROM hotel_settings WHERE guild_id=$1",
            guild_id
        )

        manager_role_id = hotel_config["manager_role"] if hotel_config else None
        has_manager_role = False
        if manager_role_id:
            has_manager_role = any(str(r.id) == manager_role_id for r in interaction.user.roles)

        if not (is_admin_role or has_manager_role):
            return await interaction.response.send_message(
                "❌ このコマンドを実行できるのは通貨管理ロールまたはホテル管理ロールのみです。",
                ephemeral=True
            )

        if amount < 0:
            return await interaction.response.send_message("枚数は 0 以上を指定してください。", ephemeral=True)

        user_id = str(member.id)

        if mode.value == "add":
            new_amount = await self.bot.db.add_tickets(user_id, guild_id, amount)
            op_text = f"+{amount}枚（付与）"
        elif mode.value == "remove":
            new_amount = await self.bot.db.remove_tickets(user_id, guild_id, amount)
            op_text = f"-{amount}枚（減算）"
        else:
            await self.bot.db._execute(
                """
                INSERT INTO hotel_tickets (user_id, guild_id, tickets)
                VALUES ($1,$2,$3)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET tickets=$3;
                """,
                user_id, guild_id, amount
            )
            new_amount = amount
            op_text = f"={amount}枚（上書き）"

        await interaction.response.send_message(
            f"🎫 {member.mention} の高級ホテルチケットを {op_text} しました。\n現在の所持枚数: **{new_amount}枚**",
            ephemeral=True
        )

        if hotel_config and hotel_config.get("log_channel"):
            log_ch = guild.get_channel(int(hotel_config["log_channel"]))
            if log_ch:
                embed = discord.Embed(title="🎫 ホテルチケット調整ログ", color=0xF4D03F)
                embed.add_field(name="対象ユーザー", value=f"{member.mention} (`{member.id}`)", inline=False)
                embed.add_field(name="操作", value=op_text, inline=True)
                embed.add_field(name="結果枚数", value=f"{new_amount}枚", inline=True)
                embed.add_field(name="実行者", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
                await log_ch.send(embed=embed)

    # ================================
    # 🧹 孤児ルーム（VCが無いのにDBに残る）を定期削除
    # ================================
    async def _hotel_orphan_cleanup_task(self):
        await self._wait_db_ready()

        while not self.bot.is_closed():
            try:
                async with self._hotel_db_lock:
                    rows = await self.bot.db._fetch(
                        "SELECT channel_id, guild_id, expire_at FROM hotel_rooms"
                    )

                for row in rows:
                    channel_id = int(row["channel_id"])
                    guild_id = int(row["guild_id"])

                    guild = self.bot.get_guild(guild_id)
                    if guild is None:
                        continue

                    ch = guild.get_channel(channel_id)
                    if ch is None or not isinstance(ch, discord.VoiceChannel):
                        async with self._hotel_db_lock:
                            await self.bot.db.delete_room(str(channel_id))
                        print(f"[Hotel] Orphan cleanup → deleted DB room {channel_id}")

            except Exception as e:
                print("[Hotel] Orphan cleanup task error:", e)

            await asyncio.sleep(300)

async def setup(bot):
    await bot.add_cog(HotelCog(bot))

    if hasattr(bot, "GUILD_IDS"):
        for gid in bot.GUILD_IDS:
            guild = discord.Object(id=gid)
            try:
                synced = await bot.tree.sync(guild=guild)
                print(f"[Hotel] Synced {len(synced)} cmds → guild {gid}")
            except Exception as e:
                print(f"[Hotel] Sync failed for {gid}: {e}")

    print("🏨 Hotel module loaded successfully!")

