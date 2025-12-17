# cogs/interview.py
import discord
from discord.ext import commands
from discord import app_commands


class InterviewCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------------
    # /面接設定（管理者ロール必須）
    # --------------------------------------------------------
    @app_commands.command(name="面接設定", description="面接システムの設定を行います（管理者）")
    async def interview_settings(
        self,
        interaction: discord.Interaction,
        interviewer_role: discord.Role,
        wait_role: discord.Role,
        done_role: discord.Role,
        reward_amount: int,
        log_channel: discord.TextChannel
    ):
        settings = await self.bot.db.get_settings()
        admin_roles = settings["admin_roles"] or []

        # ★ 初期設定に登録された管理者ロールで判定
        if not any(str(r.id) in admin_roles for r in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ このコマンドは管理者ロールを持つユーザーのみ使用できます。",
                ephemeral=True
            )

        guild_id = str(interaction.guild.id)

        # interview_settings に UPSERT（INSERT or UPDATE）
        await self.bot.db.conn.execute("""
            INSERT INTO interview_settings (
                guild_id, interviewer_role, wait_role, done_role, reward_amount, log_channel
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                interviewer_role = $2,
                wait_role = $3,
                done_role = $4,
                reward_amount = $5,
                log_channel = $6
        """,
        guild_id,
        str(interviewer_role.id),
        str(wait_role.id),
        str(done_role.id),
        reward_amount,
        str(log_channel.id),
        )

        await interaction.response.send_message(
            f"🛠 **面接設定を保存しました！**\n\n"
            f"- 面接者ロール：{interviewer_role.mention}\n"
            f"- 面接待ちロール：{wait_role.mention}\n"
            f"- 面接済みロール：{done_role.mention}\n"
            f"- 通貨付与額：{reward_amount}\n"
            f"- ログチャンネル：{log_channel.mention}"
        )

    # --------------------------------------------------------
    # /面接通過
    # --------------------------------------------------------
    @app_commands.command(name="面接通過", description="VC内の面接対象者を処理します")
    async def interview_pass(self, interaction: discord.Interaction):

        guild = interaction.guild
        guild_id = str(guild.id)

        # 設定を取得
        row = await self.bot.db.conn.fetchrow(
            "SELECT * FROM interview_settings WHERE guild_id=$1",
            guild_id
        )

        if not row:
            return await interaction.response.send_message(
                "❌ 面接設定がまだ行われていません。`/面接設定` を行ってください。",
                ephemeral=True
            )

        interviewer_role_id = row["interviewer_role"]
        wait_role_id = row["wait_role"]
        done_role_id = row["done_role"]
        reward_amount = row["reward_amount"]
        log_channel_id = row["log_channel"]

        # 権限チェック（面接者ロール）
        if interviewer_role_id not in [str(r.id) for r in interaction.user.roles]:
            return await interaction.response.send_message(
                "❌ あなたは面接者ロールを持っていません。",
                ephemeral=True
            )

        # VC参加確認
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ VCに参加している状態で使用してください。",
                ephemeral=True
            )

        vc = interaction.user.voice.channel
        members = vc.members

        wait_role = guild.get_role(int(wait_role_id))
        done_role = guild.get_role(int(done_role_id))

        processed = []

        for member in members:
            if member.bot:
                continue

            if wait_role in member.roles:
                # ロール変更
                await member.remove_roles(wait_role)
                await member.add_roles(done_role)

                # 通貨付与
                await self.bot.db.set_balance(str(member.id), guild_id, reward_amount)

                processed.append(member)

        # ログ送信
        log_channel = guild.get_channel(int(log_channel_id))

        log_msg = (
            f"【面接通過】\n"
            f"実行者：{interaction.user.mention}\n"
            f"VC：{vc.mention}\n"
            f"人数：{len(processed)}\n"
            f"付与額：{reward_amount}\n\n"
        )

        if processed:
            log_msg += "\n".join([f"- {m.mention}" for m in processed])
        else:
            log_msg += "該当者なし"

        if log_channel:
            await log_channel.send(log_msg)

        await interaction.response.send_message(f"処理完了：{len(processed)}名")

# --------------------------------------------------------
# setup（必須）
# --------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(InterviewCog(bot))


