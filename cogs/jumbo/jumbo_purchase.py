# cogs/jumbo/jumbo_purchase.py

import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timezone, timedelta

from .jumbo_db import JumboDB


# ======================================================
# 購入モーダル
# ======================================================

class JumboBuyModal(discord.ui.Modal):
    def __init__(self, bot, jumbo_db, guild_id):
        super().__init__(title="年末ジャンボ購入")
        self.bot = bot
        self.jumbo_db = jumbo_db
        self.guild_id = guild_id

        self.count = discord.ui.TextInput(
            label="購入口数（1〜10）",
            placeholder="例：3",
            required=True,
            max_length=2
        )
        self.add_item(self.count)

    async def on_submit(self, interaction: discord.Interaction):

        # 口数チェック
        try:
            count = int(self.count.value)
        except:
            return await interaction.response.send_message("❌ 数字を入力してください。", ephemeral=True)

        if not 1 <= count <= 10:
            return await interaction.response.send_message("❌ 口数は1〜10です。", ephemeral=True)

        guild_id = str(self.guild_id)
        user_id = str(interaction.user.id)

        # ===========================
        # 開催設定チェック
        # ===========================
        config = await self.jumbo_db.get_config(guild_id)
        if not config or not config["is_open"]:
            return await interaction.response.send_message("❌ 現在、購入はできません。", ephemeral=True)

        deadline = config["deadline"]
        now = datetime.now(timezone.utc)
        if now > deadline:
            return await interaction.response.send_message("❌ 購入期限を過ぎています。", ephemeral=True)

        # ===========================
        # 残高チェック
        # ===========================
        PRICE = 10000  # 1口 = 10000 spt

        user_data = await self.bot.db.get_user(user_id, guild_id)

        cost = PRICE * count
        if user_data["balance"] < cost:
            return await interaction.response.send_message(
                f"❌ 残高不足です。\n必要: {cost} spt / 所持: {user_data['balance']} spt",
                ephemeral=True
            )

        # ===========================
        # 残高減算
        # ===========================
        await self.bot.db.remove_balance(user_id, guild_id, cost)

        # ===========================
        # 番号生成（6桁・被りなし）
        # ===========================
        numbers = []

        for _ in range(count):
            while True:
                num = f"{random.randint(0, 999999):06d}"
                ok = await self.jumbo_db.add_number(guild_id, user_id, num)
                if ok:
                    numbers.append(num)
                    break

        # ===========================
        # DM通知
        # ===========================
        try:
            embed = discord.Embed(
                title="🎫 年末ジャンボ購入完了",
                description="以下の番号が付与されました！",
                color=0xF1C40F
            )
            embed.add_field(
                name="番号一覧",
                value="\n".join([f"・{n}" for n in numbers]),
                inline=False
            )
            embed.set_footer(text="当選発表までお楽しみに…！")

            await interaction.user.send(embed=embed)

        except:
            pass  # DM閉じてても処理は成功扱い

        # ===========================
        # 購入完了メッセージ
        # ===========================
        await interaction.response.send_message(
            f"🎫 **{count}口購入完了！**\nDMに番号を送りました！",
            ephemeral=True
        )


# ======================================================
# 購入ボタン
# ======================================================

class JumboBuyButton(discord.ui.Button):
    def __init__(self, bot, jumbo_db, guild_id):
        super().__init__(label="🎟 購入する", style=discord.ButtonStyle.green)
        self.bot = bot
        self.jumbo_db = jumbo_db
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):

        modal = JumboBuyModal(self.bot, self.jumbo_db, self.guild_id)
        await interaction.response.send_modal(modal)


# ======================================================
# パネル View
# ======================================================

class JumboBuyView(discord.ui.View):
    def __init__(self, bot, jumbo_db, guild_id):
        super().__init__(timeout=None)
        self.add_item(JumboBuyButton(bot, jumbo_db, guild_id))
