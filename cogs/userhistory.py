import discord
from discord.ext import commands
from discord import app_commands
import json
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

GUILD_ID = 1420918259187712093
ADMIN_ROLE_ID = 1445403813853925418

LEAVE_LOG_CHANNEL = 1480429037435490355
REJOIN_LOG_CHANNEL = 1466693608366276793


class UserHistoryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================
    # 退出ログ
    # =========================
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):

        roles = [r for r in member.roles if r.name != "@everyone"]

        await self.bot.db._execute("""
            INSERT INTO user_join_leave_logs (guild_id, user_id, action, roles)
            VALUES ($1, $2, 'leave', $3)
        """, str(member.guild.id), str(member.id),
           json.dumps([r.name for r in roles]))

        channel = member.guild.get_channel(1480429037435490355)

        if channel:
            # 🔥 メンション形式
            role_text = " / ".join([r.mention for r in roles]) if roles else "なし"

            now = datetime.now(JST).strftime("%Y/%m/%d %H:%M")

            await channel.send(
                f"👋 {member.mention} がサーバーを退出しました\n"
                f"{now}\n\n"
                f"📜 退出時所持ロール:\n{role_text}"
            )

    # =========================
    # 参加 / 再参加
    # =========================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        guild_id = str(member.guild.id)
        user_id = str(member.id)

        row = await self.bot.db._fetchrow("""
            SELECT COUNT(*) AS cnt
            FROM user_join_leave_logs
            WHERE guild_id = $1
              AND user_id = $2
              AND action = 'leave'
        """, guild_id, user_id)

        is_return = row["cnt"] > 0

        last_roles = []

        if is_return:
            last = await self.bot.db._fetchrow("""
                SELECT roles
                FROM user_join_leave_logs
                WHERE guild_id = $1
                  AND user_id = $2
                  AND action = 'leave'
                ORDER BY created_at DESC
                LIMIT 1
            """, guild_id, user_id)

            if last and last["roles"]:
                last_roles = json.loads(last["roles"])

        action = "rejoin" if is_return else "join"

        await self.bot.db._execute("""
            INSERT INTO user_join_leave_logs (guild_id, user_id, action, roles)
            VALUES ($1, $2, $3, $4)
        """, guild_id, user_id, action, "[]")

        if not is_return:
            return

        channel = member.guild.get_channel(1466693608366276793)

        if channel:
            # 🔥 名前 → ロールに変換
            role_mentions = []
            for name in last_roles:
                role = discord.utils.get(member.guild.roles, name=name)
                if role:
                    role_mentions.append(role.mention)
                else:
                    role_mentions.append(name)

            role_text = " / ".join(role_mentions) if role_mentions else "なし"

            now = datetime.now(JST).strftime("%Y/%m/%d %H:%M")

            await channel.send(
                f"🔄 {member.mention} がサーバー再参加しました\n"
                f"{now}\n\n"
                f"📜 過去所持ロール:\n{role_text}"
            )

    @app_commands.command(
        name="ユーザー履歴確認",
        description="ユーザーの入退出履歴を確認"
    )
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def user_history(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ):
        await interaction.response.defer(ephemeral=True)

        # 管理者チェック
        if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.followup.send(
                "❌ 管理者ロールが必要です。",
                ephemeral=True
            )

        logs = await self.bot.db._fetch("""
            SELECT action, roles, created_at
            FROM user_join_leave_logs
            WHERE guild_id = $1
              AND user_id = $2
            ORDER BY created_at ASC
        """, str(interaction.guild.id), str(user.id))

        # =========================
        # 現在の所属状態
        # =========================
        member = interaction.guild.get_member(user.id)

        # ロールメンション化
        def format_roles(role_names: list[str]):
            if not member or not role_names:
                return "なし"

            role_mentions = []
            for name in role_names:
                role = discord.utils.get(member.guild.roles, name=name)
                if role:
                    role_mentions.append(role.mention)
                else:
                    role_mentions.append(name)

            return " / ".join(role_mentions)

        # =========================
        # 説明文生成
        # =========================
        description = ""

        if logs:
            for log in logs:
                time = log["created_at"].strftime("%Y/%m/%d %H:%M")
                roles = json.loads(log["roles"]) if log["roles"] else []

                if log["action"] == "join":
                    description += f"{time}　サーバー参加\n\n"

                elif log["action"] == "rejoin":
                    description += f"{time}　サーバー再参加\n\n"

                elif log["action"] == "leave":
                    role_text = format_roles(roles)
                    description += (
                        f"{time}　サーバー退出\n"
                        f"退出時ロール: {role_text}\n\n"
                    )

        # =========================
        # 履歴なしでも現在表示
        # =========================
        if member:
            roles = [r.name for r in member.roles if r.name != "@everyone"]
            role_text = format_roles(roles)

            description += (
                f"現在: サーバー所属中\n"
                f"所持ロール: {role_text}"
            )
        else:
            description += "現在: サーバー未所属"

        # =========================
        # Embed
        # =========================
        embed = discord.Embed(
            title="📜 ユーザー履歴",
            description=description,
            color=discord.Color.blue()
        )

        # 🔥 上に移動＆メンション化
        embed.add_field(name="ユーザー名", value=user.name, inline=False)
        embed.add_field(name="ID", value=user.mention, inline=False)

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(UserHistoryCog(bot))
