import discord
from discord.ext import commands
from discord import app_commands

class SubscriptionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ======================================================
    # /サブスクパネル設定（管理者ロール必須）
    # ======================================================
    @app_commands.command(name="サブスクパネル設定", description="サブスク設定を登録します（管理者）")
    async def subscription_setting(
        self,
        interaction: discord.Interaction,
        standard_role: discord.Role,
        standard_price: int,
        regular_role: discord.Role,
        regular_price: int,
        premium_role: discord.Role,
        premium_price: int,
        log_channel: discord.TextChannel
    ):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        # 権限チェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)

        # UPSERT
        await self.bot.db.conn.execute("""
            INSERT INTO subscription_settings (
                guild_id,
                standard_role, standard_price,
                regular_role, regular_price,
                premium_role, premium_price,
                log_channel
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                standard_role=$2, standard_price=$3,
                regular_role=$4, regular_price=$5,
                premium_role=$6, premium_price=$7,
                log_channel=$8
        """,
        guild_id,
        str(standard_role.id), standard_price,
        str(regular_role.id), regular_price,
        str(premium_role.id), premium_price,
        str(log_channel.id)
        )

        await interaction.response.send_message(
            "🛠 サブスク設定を更新しました！", ephemeral=True
        )

    # ======================================================
    # /サブスクパネル生成（管理者ロール必須）
    # ======================================================
    @app_commands.command(name="サブスクパネル生成", description="サブスク加入パネルを生成します（管理者）")
    async def subscription_panel(self, interaction: discord.Interaction, message: str):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        # 設定を取得
        guild_id = str(interaction.guild.id)
        data = await self.bot.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1",
            guild_id
        )

        if not data:
            return await interaction.response.send_message("❌ サブスク設定がありません。", ephemeral=True)

        view = discord.ui.View(timeout=None)

        # 3つのプランボタン
        view.add_item(SubscribeButton("standard", f"スタンダードプラン {data['standard_price']}rrc"))
        view.add_item(SubscribeButton("regular", f"レギュラープラン {data['regular_price']}rrc"))
        view.add_item(SubscribeButton("premium", f"プレミアムプラン {data['premium_price']}rrc"))

        # 退会ボタン
        view.add_item(UnsubscribeButton("サブスク退会"))

        await interaction.response.send_message(content=message, view=view)


    # ======================================================
    # /サブスク更新（管理者ロール必須）
    # ======================================================
    @app_commands.command(name="サブスク更新", description="サブスク加入者の更新処理を実行します")
    async def subscription_update(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        # 権限チェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)

        config = await self.bot.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1",
            guild_id
        )

        if not config:
            return await interaction.response.send_message("❌ サブスク設定がありません。")

        # 各プランの情報
        roles_info = [
            ("standard", config["standard_role"], config["standard_price"]),
            ("regular", config["regular_role"], config["regular_price"]),
            ("premium", config["premium_role"], config["premium_price"])
        ]

        log_channel = guild.get_channel(int(config["log_channel"]))

        success = []
        failed = []

        for plan, role_id, price in roles_info:
            role = guild.get_role(int(role_id))
            if not role:
                continue

            for member in role.members:
                # 残高確認
                user = await self.bot.db.get_user(str(member.id), guild_id)

                if user["balance"] >= price:
                    # 減算
                    await self.bot.db.remove_balance(str(member.id), guild_id, price)
                    success.append(member)

                else:
                    # 残高不足 → 退会
                    await member.remove_roles(role)
                    failed.append(member)

                    # DM 通知
                    try:
                        await member.send(
                            f"残高不足のため、{plan}プランから退会しました。"
                        )
                    except:
                        pass

        # ログ出力
        log_text = f"【サブスク更新】\n成功：{len(success)}名\n失敗：{len(failed)}名\n\n"

        if success:
            log_text += "**成功者**\n" + "\n".join([m.mention for m in success]) + "\n\n"

        if failed:
            log_text += "**失敗（退会）**\n" + "\n".join([m.mention for m in failed])

        await log_channel.send(log_text)
        await interaction.response.send_message("更新処理が完了しました。")


# ======================================================
# ボタン UI
# ======================================================

class SubscribeButton(discord.ui.Button):
    def __init__(self, plan_key, label):
        super().__init__(label=label, style=discord.ButtonStyle.green)
        self.plan_key = plan_key

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        guild_id = str(guild.id)

        # サブスク設定読み込み
        config = await interaction.client.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1",
            guild_id
        )

        # 既存プラン確認（複数加入防止）
        roles = [
            config["standard_role"],
            config["regular_role"],
            config["premium_role"]
        ]

        for rid in roles:
            role = guild.get_role(int(rid))
            if role in interaction.user.roles:
                return await interaction.response.send_message(
                    "❌ すでに他のサブスクに加入しています。\n退会してから加入してください。",
                    ephemeral=True
                )

        # プラン情報取得
        if self.plan_key == "standard":
            role_id = config["standard_role"]
            price = config["standard_price"]
        elif self.plan_key == "regular":
            role_id = config["regular_role"]
            price = config["regular_price"]
        else:
            role_id = config["premium_role"]
            price = config["premium_price"]

        role = guild.get_role(int(role_id))

        # 残高確認
        user_data = await interaction.client.db.get_user(str(interaction.user.id), guild_id)
        if user_data["balance"] < price:
            return await interaction.response.send_message("❌ 残高が足りません。", ephemeral=True)

        # ロール付与 + 残高減少
        await interaction.user.add_roles(role)
        await interaction.client.db.remove_balance(str(interaction.user.id), guild_id, price)

        await interaction.response.send_message(
            f"🎉 {role.name} に加入しました！",
            ephemeral=True
        )


class UnsubscribeButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        guild_id = str(guild.id)

        config = await interaction.client.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1",
            guild_id
        )

        roles = [
            config["standard_role"],
            config["regular_role"],
            config["premium_role"]
        ]

        removed = False
        for rid in roles:
            role = guild.get_role(int(rid))
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                removed = True

        if removed:
            msg = "📝 サブスク退会が完了しました。"
        else:
            msg = "⚠ サブスクに加入していません。"

        await interaction.response.send_message(msg, ephemeral=True)


# ======================================================
# setup
# ======================================================
async def setup(bot):
    cog = SubscriptionCog(bot)
    await bot.add_cog(cog)
    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
