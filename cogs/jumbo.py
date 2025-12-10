import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import random


# ==========================================================
#  メイン Jumbo Cog（1ファイル構成）
# ==========================================================

class JumboCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------------
    # 管理者チェック
    # -------------------------
    async def is_admin(self, interaction: discord.Interaction):
        settings = await self.bot.db.get_settings()
        admin_roles = settings.get("admin_roles", [])
        admin_ids = {int(r) for r in admin_roles if r.isdigit()}
        return any(r.id in admin_ids for r in interaction.user.roles)

    # ======================================================
    # /jumbo_start
    # ======================================================
    @app_commands.command(
        name="jumbo_start",
        description="ジャンボを開始（購入パネルを設置）"
    )
    @app_commands.describe(
        title="タイトル",
        description="説明文",
        deadline="締切（例：2025-12-31 23:59）"
    )
    async def jumbo_start(self, interaction: discord.Interaction, title: str, description: str, deadline: str):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用です。", ephemeral=True)

        # 期限チェック
        try:
            dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
        except:
            return await interaction.response.send_message(
                "❌ 期限は YYYY-MM-DD HH:MM 形式で入力してください。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)

        # DB保存
        await self.bot.db.conn.execute(
            """
            INSERT INTO jumbo_config(guild_id, title, description, deadline)
            VALUES($1,$2,$3,$4)
            ON CONFLICT(guild_id)
            DO UPDATE SET title=$2, description=$3, deadline=$4
            """,
            guild_id, title, description, dt
        )

        # パネル
        embed = discord.Embed(
            title=f"🎉 {title}",
            description=(
                f"{description}\n\n"
                f"**購入期限：<t:{int(dt.timestamp())}:F>**\n\n"
                f"1口＝10,000spt\n最大10口まで購入できます。"
            ),
            color=0xF1C40F
        )

        view = JumboBuyView(self.bot, guild_id)

        await interaction.response.send_message("🎫 **ジャンボ開催！**", ephemeral=True)
        await interaction.followup.send(embed=embed, view=view)

    # ======================================================
    # /jumbo_draw
    # ======================================================
    @app_commands.command(
        name="jumbo_draw",
        description="ジャンボ抽選を開始（管理者専用）"
    )
    async def jumbo_draw(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        # データ取得
        config = await self.bot.db.conn.fetchrow(
            "SELECT * FROM jumbo_config WHERE guild_id=$1",
            guild_id
        )
        if not config:
            return await interaction.response.send_message("❌ 開催されていません。", ephemeral=True)

        entries = await self.bot.db.conn.fetch(
            "SELECT * FROM jumbo_entries WHERE guild_id=$1",
            guild_id
        )
        if not entries:
            return await interaction.response.send_message("❌ 購入者がいません。", ephemeral=True)

        await interaction.response.send_message("🎰 **抽選開始！**", ephemeral=False)

        # ===== 当選順 =====
        prize_counts = {
            "1等": 1,
            "2等": 1,
            "3等": 1,
            "4等": 1,
            "5等": 1,
            "6等": 5,
        }

        all_numbers = [e["number"] for e in entries]
        random.shuffle(all_numbers)

        result_text = "📢 **ジャンボ抽選結果**\n\n"

        idx = 0
        for prize, count in prize_counts.items():
            result_text += f"### 🎉 {prize}\n"
            for _ in range(count):
                if idx >= len(all_numbers):
                    result_text += "- 該当なし\n"
                    continue
                num = all_numbers[idx]
                idx += 1
                entry = next(e for e in entries if e["number"] == num)
                user = f"<@{entry['user_id']}>"
                result_text += f"- **{num}** → {user}\n"
            result_text += "\n"

        await interaction.followup.send(result_text)

    # ======================================================
    # /jumbo_reset
    # ======================================================
    @app_commands.command(
        name="jumbo_reset",
        description="ジャンボ履歴を全削除（管理者専用）"
    )
    async def jumbo_reset(self, interaction: discord.Interaction):

        if not await self.is_admin(interaction):
            return await interaction.response.send_message("❌ 管理者専用です。", ephemeral=True)

        guild_id = str(interaction.guild.id)

        await self.bot.db.conn.execute("DELETE FROM jumbo_config WHERE guild_id=$1", guild_id)
        await self.bot.db.conn.execute("DELETE FROM jumbo_entries WHERE guild_id=$1", guild_id)

        await interaction.response.send_message("🧹 ジャンボデータを初期化しました。", ephemeral=True)


# ==========================================================
# 購入ボタン View（1ファイルなので簡易版）
# ==========================================================

class JumboBuyView(discord.ui.View):

    def __init__(self, bot, guild_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="購入する（1口）", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):

        # ランダム6桁（重複なし）
        while True:
            num = f"{random.randint(0,999999):06}"
            exists = await self.bot.db.conn.fetchval(
                "SELECT 1 FROM jumbo_entries WHERE guild_id=$1 AND number=$2",
                self.guild_id, num
            )
            if not exists:
                break

        await self.bot.db.conn.execute(
            """
            INSERT INTO jumbo_entries(guild_id, user_id, number)
            VALUES($1,$2,$3)
            """,
            self.guild_id, str(interaction.user.id), num
        )

        await interaction.response.send_message(
            f"🎟 **購入完了！** あなたの番号は **{num}** です。",
            ephemeral=True
        )


# ==========================================================
# setup
# ==========================================================

async def setup(bot):
    await bot.add_cog(JumboCog(bot))
    print("🎫 Jumbo loaded (single file)")
