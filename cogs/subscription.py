import discord
from discord.ext import commands
from discord import app_commands


# ======================================================
# メイン Cog
# ======================================================

class SubscriptionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------
    # /サブスクパネル設定（管理者ロール必須）
    # --------------------------------------------------
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

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

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

        await interaction.response.send_message("🛠 サブスク設定を更新しました！", ephemeral=True)

    # --------------------------------------------------
    # /サブスクパネル生成（管理者ロール必須）
    # --------------------------------------------------
    @app_commands.command(name="サブスクパネル生成", description="サブスクパネルを生成します（管理者）")
    async def subscription_panel(self, interaction: discord.Interaction, message: str):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        config = await self.bot.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1",
            guild_id
        )

        if not config:
            return await interaction.response.send_message("❌ サブスク設定がありません。", ephemeral=True)

        view = SubscriptionPanelView(config=config)

        await interaction.response.send_message(message, view=view)


    # --------------------------------------------------
    # /サブスク更新（管理者ロール必須）
    # --------------------------------------------------
    @app_commands.command(name="サブスク更新", description="サブスク継続処理を行います（管理者）")
    async def subscription_update(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message("❌ 管理者ロールが必要です。", ephemeral=True)

        guild = interaction.guild
        guild_id = str(guild.id)

        config = await self.bot.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1", guild_id
        )

        if not config:
            return await interaction.response.send_message("❌ サブスク設定がありません。")

        log_channel = guild.get_channel(int(config["log_channel"]))

        plans = [
            ("standard", config["standard_role"], config["standard_price"]),
            ("regular", config["regular_role"], config["regular_price"]),
            ("premium", config["premium_role"], config["premium_price"])
        ]

        success = []
        failed = []

        for key, role_id, price in plans:
            role = guild.get_role(int(role_id))
            if not role:
                continue

            for member in role.members:
                user = await self.bot.db.get_user(str(member.id), guild_id)

                # 更新可能
                if user["balance"] >= price:
                    await self.bot.db.remove_balance(str(member.id), guild_id, price)
                    success.append(member)
                else:
                    # 残高不足 → 退会
                    await member.remove_roles(role)
                    failed.append(member)

                    try:
                        await member.send(f"残高不足のため、{key}プランから退会しました。")
                    except:
                        pass

        # ログ
        text = f"【サブスク更新】\n成功：{len(success)}名\n失敗：{len(failed)}名\n\n"

        if success:
            text += "**成功**\n" + "\n".join([m.mention for m in success]) + "\n\n"
        if failed:
            text += "**失敗（退会）**\n" + "\n".join([m.mention for m in failed])

        await log_channel.send(text)
        await interaction.response.send_message("更新が完了しました。")


# ======================================================
# パネルの View
# ======================================================

class SubscriptionPanelView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)
        self.config = config

        self.add_item(PlanButton("standard", f"スタンダード {config['standard_price']}rrc"))
        self.add_item(PlanButton("regular", f"レギュラー {config['regular_price']}rrc"))
        self.add_item(PlanButton("premium", f"プレミアム {config['premium_price']}rrc"))
        self.add_item(UnsubscribeButton("サブスク退会"))


# ======================================================
# プラン加入ボタン（確認ビューを表示する）
# ======================================================

class PlanButton(discord.ui.Button):
    def __init__(self, plan_key, label):
        super().__init__(label=label, style=discord.ButtonStyle.green)
        self.plan_key = plan_key

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        guild_id = str(guild.id)

        config = await interaction.client.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1", guild_id
        )

        # プラン情報
        if self.plan_key == "standard":
            role_id = config["standard_role"]
            price = config["standard_price"]
            plan_name = "スタンダードプラン"
        elif self.plan_key == "regular":
            role_id = config["regular_role"]
            price = config["regular_price"]
            plan_name = "レギュラープラン"
        else:
            role_id = config["premium_role"]
            price = config["premium_price"]
            plan_name = "プレミアムプラン"

        # ⭐ 確認ビューを返す
        view = ConfirmSubscribeView(
            role_id=role_id,
            price=price,
            plan_name=plan_name,
            plan_key=self.plan_key
        )

        await interaction.response.send_message(
            f"**{plan_name}（{price}rrc）に加入しますか？**",
            ephemeral=True,
            view=view
        )


# ======================================================
# 加入確認ビュー（加入 / キャンセル）
# ======================================================

class ConfirmSubscribeView(discord.ui.View):
    def __init__(self, role_id, price, plan_name, plan_key):
        super().__init__(timeout=30)
        self.role_id = role_id
        self.price = price
        self.plan_name = plan_name
        self.plan_key = plan_key

    @discord.ui.button(label="加入する", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild
        guild_id = str(guild.id)
        role = guild.get_role(int(self.role_id))

        config = await interaction.client.db.conn.fetchrow(
            "SELECT * FROM subscription_settings WHERE guild_id=$1",
            guild_id
        )

        # 多重加入防止
        for rid in [
            config["standard_role"],
            config["regular_role"],
            config["premium_role"]
        ]:
            r = guild.get_role(int(rid))
            if r in interaction.user.roles:
                return await interaction.response.send_message(
                    "❌ 他のサブスクに加入しています。\n退会してから加入してください。",
                    ephemeral=True
                )

        # 残高確認
        user_data = await interaction.client.db.get_user(str(interaction.user.id), guild_id)

        if user_data["balance"] < self.price:
            return await interaction.response.send_message("❌ 残高が不足しています。", ephemeral=True)

        # 加入処理
        await interaction.user.add_roles(role)
        await interaction.client.db.remove_balance(str(interaction.user.id), guild_id, self.price)

        await interaction.response.send_message(
            f"🎉 **{self.plan_name} に加入しました！**",
            ephemeral=True
        )

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("キャンセルしました。", ephemeral=True)


# ======================================================
# 退会ボタン
# ======================================================

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
