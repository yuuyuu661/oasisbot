import discord
from discord.ext import commands
from discord import app_commands


def find_emoji(bot, name_or_id: str):
    if name_or_id.isdigit():
        return bot.get_emoji(int(name_or_id))

    for e in bot.emojis:
        if e.name == name_or_id:
            return e
    return None


class StampCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stamp", description="返信したメッセージにスタンプを付ける")
    @app_commands.describe(emoji="絵文字名またはID")
    async def stamp(self, interaction: discord.Interaction, emoji: str):

        if not interaction.channel:
            return await interaction.response.send_message("チャンネル取得失敗", ephemeral=True)

        if not interaction.message.reference:
            return await interaction.response.send_message(
                "スタンプを付けたい投稿に返信して実行してください",
                ephemeral=True
            )

        ref = interaction.message.reference

        try:
            msg = await interaction.channel.fetch_message(ref.message_id)
        except:
            return await interaction.response.send_message("メッセージ取得失敗", ephemeral=True)

        emoji_obj = find_emoji(self.bot, emoji)
        if not emoji_obj:
            return await interaction.response.send_message("絵文字が見つかりません", ephemeral=True)

        try:
            await msg.add_reaction(emoji_obj)
            await interaction.response.send_message("スタンプ付与", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"失敗: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(StampCog(bot))
