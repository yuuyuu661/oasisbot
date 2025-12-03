import discord
from discord.ext import commands
from datetime import datetime, timedelta


# ======================================================
# Utility：ログ送信用（共通）
# ======================================================
async def send_log_embed(guild, log_channel_id, *, title, fields):
    log_channel = guild.get_channel(int(log_channel_id))
    if not log_channel:
        return

    embed = discord.Embed(title=title, color=0xF4D03F)
    for name, value in fields:
        embed.add_field(name=name, value=value, inline=False)

    embed.timestamp = datetime.utcnow()
    await log_channel.send(embed=embed)


# ======================================================
# 人数 +1 ボタン
# ======================================================
class IncreaseLimitButton(discord.ui.Button):
    def __init__(self, room_data, config):
        super().__init__(label="人数を1人増やす（1枚消費）", style=discord.ButtonStyle.blurple)
        self.room_data = room_data
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        vc = guild.get_channel(int(self.room_data["channel_id"]))
        user_id = str(self.room_data["owner_id"])
        guild_id = str(guild.id)

        # チケット確認
        tickets = await interaction.client.db.get_tickets(user_id, guild_id)
        if tickets < 1:
            return await interaction.response.send_message("❌ チケット不足です。", ephemeral=True)

        # 消費
        await interaction.client.db.remove_tickets(user_id, guild_id, 1)

        # 上限 +1
        vc.user_limit = (vc.user_limit or 0) + 1
        await vc.edit(user_limit=vc.user_limit)

        await interaction.response.send_message(
            f"👥 上限人数を **{vc.user_limit}人** に変更しました！（1枚消費）",
            ephemeral=True
        )


# ======================================================
# 接続許可（UserSelect）
# ======================================================
class AllowUserSelect(discord.ui.Select):
    def __init__(self, room_data):
        options = [
            discord.SelectOption(label="検索してユーザーを選択", value="select")
        ]
        super().__init__(
            placeholder="接続許可するユーザーを選択",
            min_values=1,
            max_values=1,
            options=options
        )
        self.room_data = room_data

    async def callback(self, interaction: discord.Interaction):
        # 実際の選択画面を出す
        view = AllowUserSelectView(self.room_data)
        await interaction.response.send_message(
            "接続許可するユーザーを選択してください。",
            view=view,
            ephemeral=True
        )


class AllowUserSelectView(discord.ui.View):
    def __init__(self, room_data):
        super().__init__(timeout=60)
        self.add_item(UserPicker(room_data))


class UserPicker(discord.ui.UserSelect):
    def __init__(self, room_data):
        super().__init__(placeholder="接続許可するユーザーを選択", min_values=1, max_values=1)
        self.room_data = room_data

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        guild = interaction.guild
        vc = guild.get_channel(int(self.room_data["channel_id"]))

        await vc.set_permissions(
            target,
            connect=True,
            view_channel=True
        )

        await interaction.response.send_message(
            f"✅ {target.mention} を接続許可しました。",
            ephemeral=True
        )


# ======================================================
# サブ垢追加（人数+1のみ）
# ======================================================
class AddSubButton(discord.ui.Button):
    def __init__(self, room_data, config):
        super().__init__(label="サブ垢追加（人数+1）", style=discord.ButtonStyle.gray)
        self.room_data = room_data
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        vc = guild.get_channel(int(self.room_data["channel_id"]))

        # 上限 +1
        vc.user_limit = (vc.user_limit or 0) + 1
        await vc.edit(user_limit=vc.user_limit)

        await interaction.response.send_message(
            f"👥 サブ垢追加：上限が **{vc.user_limit}人** になりました。",
            ephemeral=True
        )


# ======================================================
# 延長ボタン（1日 / 3日 / 10日）
# ======================================================
class ExtendButton(discord.ui.Button):
    def __init__(self, label, days, cost, room_data, config):
        super().__init__(label=label, style=discord.ButtonStyle.green)
        self.days = days
        self.cost = cost
        self.room_data = room_data
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        guild_id = str(guild.id)
        owner_id = str(self.room_data["owner_id"])

        # チケット確認
        tickets = await interaction.client.db.get_tickets(owner_id, guild_id)
        if tickets < self.cost:
            return await interaction.response.send_message(
                f"❌ チケット不足（必要: {self.cost}枚）",
                ephemeral=True
            )

        # 消費
        await interaction.client.db.remove_tickets(owner_id, guild_id, self.cost)

        # 期限更新
        old_expire = self.room_data["expire_at"]
        new_expire = old_expire + timedelta(days=self.days)

        await interaction.client.db.conn.execute(
            "UPDATE hotel_rooms SET expire_at=$1 WHERE channel_id=$2",
            new_expire,
            self.room_data["channel_id"]
        )

        # ログ embed
        await send_log_embed(
            guild,
            self.config["log_channel"],
            title="⏳ 高級ホテル 延長ログ",
            fields=[
                ("ユーザー", f"<@{owner_id}>"),
                ("延長日数", f"{self.days}日"),
                ("旧期限", f"<t:{int(old_expire.timestamp())}:F>"),
                ("新期限", f"<t:{int(new_expire.timestamp())}:F>")
            ]
        )

        await interaction.response.send_message(
            f"⏳ 期限を **{self.days}日延長** しました！",
            ephemeral=True
        )
