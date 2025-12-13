# cogs/chinchiro.py

import discord
import random
import asyncio
from discord.ext import commands
from discord import app_commands


# =========================
# ギルド限定（bot.py と一致させる）
# =========================

GUILD_IDS = [
    1444580349773348951,
    1420918259187712093,
]


# =========================
# 役・強さ・倍率定義
# =========================

ROLE_ORDER = {
    "ピンゾロ": 6,
    "ゾロ目": 5,
    "シゴロ": 4,
    "通常": 3,
    "ブタ": 2,
    "ヒフミ": 1,
}


def judge_role(dice: list[int]):
    a, b, c = sorted(dice)

    if a == b == c == 1:
        return "ピンゾロ", 5
    if a == b == c:
        return "ゾロ目", 3
    if [a, b, c] == [4, 5, 6]:
        return "シゴロ", 2
    if [a, b, c] == [1, 2, 3]:
        return "ヒフミ", -2
    if a == b or b == c:
        return "通常", max(a, b, c)
    return "ブタ", -1


# =========================
# 通貨処理（今回は未使用）
# =========================

async def add_rrc(user: discord.Member, amount: int):
    # 今回は計算表示のみ
    return


# =========================
# サイコロ演出（1.5秒）
# =========================

async def roll_animation(channel: discord.TextChannel, user: discord.Member):
    final = [random.randint(1, 6) for _ in range(3)]
    msg = await channel.send(
        f"🎲 **{user.display_name}** がサイコロを振っています…"
    )

    for _ in range(10):
        a = [random.randint(1, 6) for _ in range(3)]
        await msg.edit(content=f"🎲 {a[0]} | {a[1]} | {a[2]}")
        await asyncio.sleep(0.15)

    role, mult = judge_role(final)

    await msg.edit(
        content=(
            f"🎉 **結果：{final[0]} | {final[1]} | {final[2]}**\n"
            f"役：**{role}**"
        )
    )
    return role, mult


# =========================
# メイン Cog
# =========================

class ChinchiroCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, dict] = {}


    # -------------------------
    # /チンチロ
    # -------------------------
    @app_commands.command(name="チンチロ", description="チンチロを開始する")
    @app_commands.guilds(*GUILD_IDS)
    async def chinchiro(self, interaction: discord.Interaction, rate: int):
        gid = interaction.guild.id

        if gid in self.sessions:
            await interaction.response.send_message(
                "⚠️ すでにチンチロが進行中です",
                ephemeral=True
            )
            return

        self.sessions[gid] = {
            "rate": rate,
            "players": [],
            "parent": None,
            "results": {},
        }

        embed = discord.Embed(
            title="🎲 チンチロ",
            description=f"レート：{rate}rrc\n\n参加者："
        )

        await interaction.response.send_message(
            embed=embed,
            view=JoinView(self, gid)
        )


    # -------------------------
    # ゲーム本編
    # -------------------------
    async def start_game(self, channel: discord.TextChannel):
        session = self.sessions[channel.guild.id]
        parent = session["parent"]
        results = {}

        # 子の順番
        children = [p for p in session["players"] if p != parent]
        random.shuffle(children)

        for user in children:
            role, mult = await self.roll_turn(channel, user)
            results[user] = (role, mult)

        # 親
        role, mult = await self.roll_turn(channel, parent)
        results[parent] = (role, mult)

        session["results"] = results

        ledger = await self.calc_payout(session)
        await self.show_result(channel, ledger)

        await channel.send(
            "次はどうする？",
            view=ResultView(self, channel.guild.id)
        )


    async def roll_turn(self, channel: discord.TextChannel, user: discord.Member):
        for i in range(3):
            role, mult = await roll_animation(channel, user)
            if role != "ブタ":
                return role, mult
            await channel.send(f"⚠️ 役無し… 振り直し ({i + 1}/3)")
        return "ブタ", -1


    async def calc_payout(self, session: dict):
        rate = session["rate"]
        parent = session["parent"]
        results = session["results"]

        ledger = {p: 0 for p in session["players"]}
        p_role, p_mult = results[parent]

        for user, (role, mult) in results.items():
            if user == parent:
                continue

            if ROLE_ORDER[p_role] > ROLE_ORDER[role]:
                amt = rate * max(p_mult, 1)
                ledger[parent] += amt
                ledger[user] -= amt

            elif ROLE_ORDER[p_role] < ROLE_ORDER[role]:
                amt = rate * max(mult, 1)
                ledger[parent] -= amt
                ledger[user] += amt

        return ledger


    async def show_result(self, channel: discord.TextChannel, ledger: dict):
        lines = ["🎲 **リザルト**"]

        for user, amt in ledger.items():
            sign = "+" if amt >= 0 else ""
            lines.append(f"{user.display_name}　{sign}{amt}rrc")
            await add_rrc(user, amt)

        await channel.send("\n".join(lines))


    # -------------------------
    # /チンチロリセット
    # -------------------------
    @app_commands.command(name="チンチロリセット", description="チンチロを強制終了")
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.checks.has_permissions(administrator=True)
    async def chinchiro_reset(self, interaction: discord.Interaction):
        self.sessions.pop(interaction.guild.id, None)
        await interaction.response.send_message("✅ チンチロをリセットしました")


# =========================
# View：参加・締切
# =========================

class JoinView(discord.ui.View):
    def __init__(self, cog: ChinchiroCog, gid: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.gid = gid

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.cog.sessions[self.gid]

        if interaction.user not in session["players"]:
            session["players"].append(interaction.user)

        embed = interaction.message.embeds[0]
        embed.description = (
            f"レート：{session['rate']}rrc\n\n"
            "参加者：\n"
            + "\n".join(p.display_name for p in session["players"])
        )

        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="締め切り", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.cog.sessions[self.gid]

        if len(session["players"]) < 2:
            await interaction.response.send_message(
                "⚠️ 参加者が足りません",
                ephemeral=True
            )
            return

        self.clear_items()
        self.add_item(ParentButton(self.cog, self.gid))
        await interaction.response.edit_message(view=self)


# =========================
# View：親決め
# =========================

class ParentButton(discord.ui.Button):
    def __init__(self, cog: ChinchiroCog, gid: int):
        super().__init__(label="親決め", style=discord.ButtonStyle.primary)
        self.cog = cog
        self.gid = gid
        self.done: dict[discord.Member, str] = {}

    async def callback(self, interaction: discord.Interaction):
        session = self.cog.sessions[self.gid]

        if interaction.user in self.done:
            await interaction.response.send_message(
                "❌ すでに振っています",
                ephemeral=True
            )
            return

        dice = [random.randint(1, 6) for _ in range(3)]
        role, _ = judge_role(dice)
        self.done[interaction.user] = role

        await interaction.response.send_message(
            f"{dice} → **{role}**",
            ephemeral=True
        )

        if len(self.done) == len(session["players"]):
            parent = max(
                self.done.items(),
                key=lambda x: ROLE_ORDER[x[1]]
            )[0]

            session["parent"] = parent

            await interaction.channel.send(
                f"👑 親は **{parent.display_name}** です！"
            )

            await self.cog.start_game(interaction.channel)


# =========================
# View：続けて / 終了
# =========================

class ResultView(discord.ui.View):
    def __init__(self, cog: ChinchiroCog, gid: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.gid = gid

    @discord.ui.button(label="続けてプレイ", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.cog.sessions[self.gid]

        session["parent"] = max(
            session["results"].items(),
            key=lambda x: ROLE_ORDER[x[1][0]]
        )[0]

        await interaction.response.send_message("🔄 次のラウンドを開始します")
        await self.cog.start_game(interaction.channel)

    @discord.ui.button(label="終了", style=discord.ButtonStyle.danger)
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.sessions.pop(self.gid, None)
        await interaction.response.send_message("🏁 チンチロを終了しました")


# =========================
# setup
# =========================

async def setup(bot: commands.Bot):
    await bot.add_cog(ChinchiroCog(bot))
