# cogs/jumbo/jumbo_purchase.py

import discord
from datetime import datetime
import random

# ======================================================
# 購入モーダル
# ======================================================

class JumboBuyModal(discord.ui.Modal):
    def __init__(self, bot, guild_id):
        super().__init__(title="年末ジャンボ購入")
        self.bot = bot
        self.guild_id = str(guild_id)

        self.count = discord.ui.TextInput(
            label="購入口数（1〜100）",
            placeholder="例：3",
            required=True,
            max_length=3
        )
        self.add_item(self.count)

    async def on_submit(self, interaction: discord.Interaction):
        # ---------------------------
        # 口数チェック
        # ---------------------------
        try:
            count = int(self.count.value)
        except ValueError:
            return await interaction.response.send_message(
                "❌ 数字を入力してください。",
                ephemeral=True
            )

        if not 1 <= count <= 100:
            return await interaction.response.send_message(
                "❌ 口数は1〜100です。",
                ephemeral=True
            )

        guild_id = self.guild_id
        user_id = str(interaction.user.id)

        # ---------------------------
        # 開催チェック
        # ---------------------------
        config = await self.bot.db.jumbo_get_config(guild_id)
        if not config or not config["is_open"]:
            return await interaction.response.send_message(
                "❌ 現在、購入できません。",
                ephemeral=True
            )

        if datetime.now() > config["deadline"]:
            return await interaction.response.send_message(
                "❌ 購入期限を過ぎています。",
                ephemeral=True
            )

        # ---------------------------
        # 残高チェック
        # ---------------------------
        PRICE = 1000
        cost = PRICE * count

        user = await self.bot.db.get_user(user_id, guild_id)
        if user["balance"] < cost:
            return await interaction.response.send_message(
                f"❌ 残高不足です。\n必要: {cost} rrc / 所持: {user['balance']} rrc",
                ephemeral=True
            )

        # ---------------------------
        # 残高減算
        # ---------------------------
        await self.bot.db.remove_balance(user_id, guild_id, cost)

        # ---------------------------
        # 番号生成
        # ---------------------------
        numbers = []
        for _ in range(count):
            while True:
                num = f"{random.randint(0, 999999):06d}"
                ok = await self.bot.db.jumbo_add_number(guild_id, user_id, num)
                if ok:
                    numbers.append(num)
                    break

        # ---------------------------
        # パネル即時更新
        # ---------------------------
        try:
            config = await self.bot.db.jumbo_get_config(guild_id)
            if config and config["panel_message_id"] and config["panel_channel_id"]:
                channel = self.bot.get_channel(int(config["panel_channel_id"]))
                if channel is None:
                    channel = await self.bot.fetch_channel(int(config["panel_channel_id"]))

                message = await channel.fetch_message(int(config["panel_message_id"]))
                if message.embeds:
                    embed = message.embeds[0]

                    issued = await self.bot.db.jumbo_count_entries(guild_id)
                    remaining = max(0, 999_999 - issued)

                    for i, field in enumerate(embed.fields):
                        if field.name.startswith("🎫 宝くじ残り枚数"):
                            embed.set_field_at(
                                i,
                                name="🎫 宝くじ残り枚数",
                                value=f"{remaining:,} 枚",
                                inline=False
                            )
                            break
                    else:
                        embed.add_field(
                            name="🎫 宝くじ残り枚数",
                            value=f"{remaining:,} 枚",
                            inline=False
                        )

                    await message.edit(embed=embed)
        except Exception as e:
            print("[JUMBO] instant panel update failed:", repr(e))

        # ---------------------------
        # DM通知
        # ---------------------------
        try:
            embed = discord.Embed(
                title="🎫 年末ジャンボ購入完了",
                description="以下の番号が付与されました！",
                color=0xF1C40F
            )
            embed.add_field(
                name="番号一覧",
                value="\n".join(f"・{n}" for n in numbers),
                inline=False
            )
            await interaction.user.send(embed=embed)
        except:
            pass

        await interaction.response.send_message(
            f"🎫 **{count}口購入完了！**\nDMに番号を送りました！",
            ephemeral=True
        )


# ======================================================
# 購入ボタン
# ======================================================

class JumboBuyButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label="🎟 購入する", style=discord.ButtonStyle.green)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        config = await self.view_ref.db.jumbo_get_config(self.view_ref.guild_id)
        if not config or not config["is_open"]:
            return await interaction.response.send_message(
                "❌ このジャンボは締め切られています。",
                ephemeral=True
            )

        await interaction.response.send_modal(
            JumboBuyModal(
                self.view_ref.bot,
                self.view_ref.guild_id
            )
        )

# ======================================================
# 締め切りボタン
# ======================================================

class JumboCloseButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label="⛔ 締め切り", style=discord.ButtonStyle.danger)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        settings = await self.view_ref.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者専用",
                ephemeral=True
            )

        await self.view_ref.db.jumbo_close_config(self.view_ref.guild_id)

        # ボタン無効化
        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="🔒 ジャンボを締め切りました",
            view=self.view
        )

# ======================================================
# パネル View
# ======================================================

class JumboBuyView(discord.ui.View):
    def __init__(self, bot, db, guild_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.db = db
        self.guild_id = str(guild_id)
        self.add_item(JumboBuyButton(self))
        self.add_item(JumboCloseButton(self))