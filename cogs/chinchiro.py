import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime

class ChinchiroCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =========================
    # 卓開始
    # =========================
    @app_commands.command(name="チンチロ", description="チンチロ卓を開始")
    async def chinchiro_start(self, interaction: discord.Interaction):

        thread = interaction.channel

        # フォーラムスレ判定
        if not isinstance(thread, discord.Thread):
            return await interaction.response.send_message(
                "❌ フォーラムのスレ内で実行してください",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)
        thread_id = str(thread.id)

        # VC参加者取得
        vc_members = []
        for vc in guild.voice_channels:
            vc_members.extend(vc.members)

        vc_members = list(set(vc_members))

        if len(vc_members) < 2:
            return await interaction.response.send_message(
                "❌ VC参加者が2人以上必要です",
                ephemeral=True
            )

        # DB卓存在チェック
        existing = await self.bot.db._fetchrow("""
            SELECT thread_id FROM chinchiro_games
            WHERE thread_id=$1
        """, thread_id)

        if existing:
            return await interaction.response.send_message(
                "❌ このスレには既に卓があります",
                ephemeral=True
            )

        # 親ランダム決定
        parent = random.choice(vc_members)

        # 卓生成
        await self.bot.db._execute("""
            INSERT INTO chinchiro_games(
                thread_id,
                guild_id,
                host_id,
                parent_id,
                phase
            ) VALUES($1,$2,$3,$4,$5)
        """, thread_id, guild_id, str(interaction.user.id), str(parent.id), "lobby")

        # プレイヤー登録
        order = 0
        for m in vc_members:
            await self.bot.db._execute("""
                INSERT INTO chinchiro_players(
                    thread_id,
                    user_id,
                    is_parent,
                    turn_order
                ) VALUES($1,$2,$3,$4)
            """, thread_id, str(m.id), m.id == parent.id, order)
            order += 1

        # ロビー表示
        member_mentions = "\n".join([f"・{m.mention}" for m in vc_members])

        embed = discord.Embed(
            title="🎲 チンチロ卓が開かれました",
            description=(
                f"👑 親：{parent.mention}\n\n"
                f"参加者：\n{member_mentions}\n\n"
                "次のフェーズ：ベット開始"
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ChinchiroCog(bot))