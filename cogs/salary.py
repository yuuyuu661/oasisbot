# cogs/salary.py

import discord
from discord.ext import commands
from discord import app_commands

from logger import log_salary


class SalaryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------
    # /給料設定
    # --------------------------
    @app_commands.command(name="給料設定", description="指定ロールの給料額を設定します（管理者）")
    async def set_salary(self, interaction: discord.Interaction, role: discord.Role, amount: int):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者ロールチェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        # 給料設定
        await self.bot.db.set_salary(str(role.id), amount)

        # これは今まで通り公開でも問題ないと思うのでそのまま
        await interaction.response.send_message(
            f"📝 ロール **{role.name}** の給料を **{amount}{unit}** に設定しました。"
        )

    # --------------------------
    # /給料一覧
    # --------------------------
    @app_commands.command(name="給料一覧", description="設定されている給料一覧を表示します")
    async def salary_list(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者ロールチェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        salaries = await self.bot.db.get_salaries()

        embed = discord.Embed(title="👜 給料一覧", color=0xe67e22)

        if not salaries:
            embed.description = "設定なし。"
        else:
            lines = []
            for s in salaries:
                role = interaction.guild.get_role(int(s["role_id"]))
                role_name = role.name if role else f"不明ロール ({s['role_id']})"
                lines.append(f"**{role_name}**：{s['salary']} {unit}")
            embed.description = "\n".join(lines)

        # ここはもともと管理者向け情報なのでエフェメラルにしておく
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------------
    # /給料確認
    # --------------------------
    @app_commands.command(name="給料確認", description="自分のロールに基づく給料合計を表示します")
    async def check_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        unit = settings["currency_unit"]

        rows = await self.bot.db.get_salaries()
        salary_map = {row["role_id"]: row["salary"] for row in rows}

        total = 0
        desc = ""

        for role in interaction.user.roles:
            if str(role.id) in salary_map:
                total += salary_map[str(role.id)]
                desc += f"- {role.name}: {salary_map[str(role.id)]}{unit}\n"

        if total == 0:
            return await interaction.response.send_message(
                "あなたのロールには給料設定がありません。",
                ephemeral=True
            )

        embed = discord.Embed(
            title="💰 給料確認",
            description=desc + f"\n**合計：{total}{unit}**",
            color=0xFFD700
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------------
    # /給料配布（ギルド別）
    # --------------------------
    @app_commands.command(name="給料配布", description="給料を全メンバーに配布します（管理者）")
    async def give_salary(self, interaction: discord.Interaction):

        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []
        unit = settings["currency_unit"]

        # 管理者ロールチェック
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        # ここから try で囲って、失敗時も必ず何か返すようにしておく
        try:
            salary_list = await self.bot.db.get_salaries()
            salary_map = {row["role_id"]: row["salary"] for row in salary_list}

            guild = interaction.guild
            guild_id = str(guild.id)

            # ホテル設定からサブ垢ロールID取得
            hotel_config = await self.bot.db.conn.fetchrow(
                "SELECT sub_role FROM hotel_settings WHERE guild_id=$1",
                guild_id
            )
            sub_role_id = hotel_config["sub_role"] if hotel_config else None

            total_users = 0
            total_amount = 0

            for member in guild.members:
                if member.bot:
                    continue

                # サブ垢ロール持ちは除外
                if sub_role_id and (role := guild.get_role(int(sub_role_id))) and role in member.roles:
                    continue

                add_amount = 0
                for role in member.roles:
                    if str(role.id) in salary_map:
                        add_amount += salary_map[str(role.id)]

                if add_amount > 0:
                    await self.bot.db.add_balance(str(member.id), guild_id, add_amount)
                    total_users += 1
                    total_amount += add_amount

            # ログ送信
            await log_salary(
                self.bot, settings,
                str(interaction.user.id),
                total_users,
                total_amount
            )

        except Exception as e:
            # ここでエラー内容をコンソールに出す
            print("[give_salary] error:", repr(e))

            # Interaction の応答がまだならエラーメッセージを返す
            if not interaction.response.is_done():
                return await interaction.response.send_message(
                    "内部エラーが発生しました。（/給料配布）",
                    ephemeral=True
                )
            else:
                return await interaction.followup.send(
                    "内部エラーが発生しました。（/給料配布）",
                    ephemeral=True
                )
            
        # 正常時のメッセージ → 実行者のみ見える
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"🎉 **{total_users}人** に **{total_amount}{unit}** を配布しました。",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"🎉 **{total_users}人** に **{total_amount}{unit}** を配布しました。",
                ephemeral=True
            )

# --------------------------
# setup（必須）
# --------------------------
async def setup(bot):
    cog = SalaryCog(bot)
    await bot.add_cog(cog)

    for cmd in cog.get_app_commands():
        for gid in bot.GUILD_IDS:
            bot.tree.add_command(cmd, guild=discord.Object(id=gid))
