# cogs/janken_card.py
# =========================================================
# じゃんけんカード（2人専用 / 5回戦 or 先に3勝 / DM手札 / 60秒自動選択）
# 画像素材: gu1~5.jpg / cyo1~5.jpg / pa1~5.jpg
# =========================================================

from __future__ import annotations

import os
import random
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image
import io
from collections import Counter


# =========================================================
# 設定（ここだけ最初に確認）
# =========================================================

# 画像素材フォルダ（あなたの配置に合わせて調整してOK）
# 例: project_root/assets/janken/gu1.jpg ...
ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "janken")

# 参加者は2人固定
MAX_PLAYERS = 2

# 1ターンの選択猶予（秒）
TURN_TIMEOUT = 60

# 最大ラウンド
MAX_ROUNDS = 5

# 先にこの勝利数で勝ち
WIN_TARGET = 3


# =========================================================
# カード定義
# =========================================================

@dataclass(frozen=True)
class JCard:
    kind: str   # "gu" | "cyo" | "pa"
    star: int   # 1..5
    filename: str

    @property
    def label_jp(self) -> str:
        if self.kind == "gu":
            return "グー"
        if self.kind == "cyo":
            return "チョキ"
        return "パー"


def build_deck() -> List[JCard]:
    deck: List[JCard] = []
    for i in range(1, 6):
        deck.append(JCard("gu", i, f"gu{i}.jpg"))
        deck.append(JCard("cyo", i, f"cyo{i}.jpg"))
        deck.append(JCard("pa", i, f"pa{i}.jpg"))
    return deck  # 15枚


def judge(a: JCard, b: JCard) -> str:
    """
    戻り値:
      "A" / "B" / "draw"
    じゃんけん: gu > cyo, cyo > pa, pa > gu
    あいこ: star が高い方が勝ち、同starは引き分け
    """
    beats = {"gu": "cyo", "cyo": "pa", "pa": "gu"}

    if a.kind == b.kind:
        if a.star > b.star:
            return "A"
        if a.star < b.star:
            return "B"
        return "draw"

    if beats[a.kind] == b.kind:
        return "A"
    return "B"


def summarize_hand(hand: List[JCard]) -> str:
    """
    星は隠して、種類の枚数だけ返す（例：グー×3 / パー×2）
    """
    c = Counter([x.kind for x in hand])
    parts = []
    if c.get("gu", 0):
        parts.append(f"グー ×{c['gu']}")
    if c.get("cyo", 0):
        parts.append(f"チョキ ×{c['cyo']}")
    if c.get("pa", 0):
        parts.append(f"パー ×{c['pa']}")
    return "\n".join(parts) if parts else "（手札なし）"


# =========================================================
# 画像合成（横並び）
# =========================================================

def _load_card_image(card: JCard) -> Image.Image:
    path = os.path.join(ASSET_DIR, card.filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"カード画像が見つかりません: {path}")
    return Image.open(path).convert("RGBA")


async def create_hand_image(hand: List[JCard]) -> discord.File:
    """
    左→右 = 1枚目→N枚目。ポーカーの create_hand_image をローカル版にしたもの。
    """
    if not hand:
        # 空手札のダミー画像
        img = Image.new("RGBA", (512, 256), (255, 255, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return discord.File(fp=buf, filename="hand.png")

    images = [_load_card_image(c) for c in hand]
    widths, heights = zip(*(i.size for i in images))
    total_width = sum(widths)
    max_height = max(heights)

    combined = Image.new("RGBA", (total_width, max_height))
    x = 0
    for im in images:
        combined.paste(im, (x, 0), im)
        x += im.width

    buf = io.BytesIO()
    combined.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(fp=buf, filename="hand.png")


# =========================================================
# ゲーム状態
# =========================================================

class JankenGame:
    def __init__(self, guild_id: int, channel_id: int, owner_id: int, rate: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.rate = rate

        self.players: List[int] = []
        self.started: bool = False

        self.deck: List[JCard] = []
        self.hands: Dict[int, List[JCard]] = {}
        self.wins: Dict[int, int] = {}
        self.round_no: int = 0

        # 今ラウンドの選択（index, card）
        self.selected: Dict[int, Optional[int]] = {}
        self.resolving: bool = False

        # タイムアウト管理（ラウンド単位でトークンを更新）
        self.round_token: int = 0

    def is_full(self) -> bool:
        return len(self.players) >= MAX_PLAYERS

    def other(self, uid: int) -> Optional[int]:
        for p in self.players:
            if p != uid:
                return p
        return None


# =========================================================
# View: 参加パネル
# =========================================================

class JankenPanelView(discord.ui.View):
    def __init__(self, cog: "JankenCardCog", game: JankenGame):
        super().__init__(timeout=None)
        self.cog = cog
        self.game = game

    def _is_owner(self, user_id: int) -> bool:
        return user_id == self.game.owner_id

    async def _refresh_panel(self, interaction: discord.Interaction):
        await self.cog._update_panel_message(interaction)

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success, custom_id="janken_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.started:
            await interaction.response.send_message("❌ すでに開始されています。", ephemeral=True)
            return

        if self.game.is_full() and interaction.user.id not in self.game.players:
            await interaction.response.send_message("❌ 参加枠が埋まっています。", ephemeral=True)
            return

        # 残高チェック（rate未満は参加不可）
        bal = await self.cog._get_balance(interaction.user.id, interaction.guild_id)
        if bal < self.game.rate:
            await interaction.response.send_message(
                f"❌ 残高不足で参加できません。（必要: {self.game.rate} / 現在: {bal}）",
                ephemeral=True
            )
            return

        if interaction.user.id not in self.game.players:
            self.game.players.append(interaction.user.id)
            self.game.wins[interaction.user.id] = 0
            self.game.selected[interaction.user.id] = None

        await interaction.response.send_message("✅ 参加しました！", ephemeral=True)

        # 2人揃ったら参加締切（参加ボタン無効化）
        if self.game.is_full():
            button.disabled = True

        await self._refresh_panel(interaction)

    @discord.ui.button(label="開始", style=discord.ButtonStyle.primary, custom_id="janken_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_owner(interaction.user.id):
            await interaction.response.send_message("❌ 開始できるのは主催者のみです。", ephemeral=True)
            return
        if self.game.started:
            await interaction.response.send_message("❌ すでに開始されています。", ephemeral=True)
            return
        if len(self.game.players) != MAX_PLAYERS:
            await interaction.response.send_message("❌ 参加者が2人揃っていません。", ephemeral=True)
            return

        self.game.started = True
        button.disabled = True
        # 参加ボタンも止める
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "janken_join":
                child.disabled = True

        await interaction.response.send_message("🃏 じゃんけんカードを開始します！", ephemeral=False)
        await self._refresh_panel(interaction)

        # ゲーム本体開始
        await self.cog._start_game(interaction, self.game)


# =========================================================
# View: DM（手札UI）
# =========================================================

class JankenHandView(discord.ui.View):
    def __init__(self, cog: "JankenCardCog", game: JankenGame, player_id: int):
        super().__init__(timeout=TURN_TIMEOUT)
        self.cog = cog
        self.game = game
        self.player_id = player_id

    async def on_timeout(self):
        # タイムアウト時に未選択なら自動選択を試みる
        await self.cog._auto_pick_if_needed(self.game, self.player_id)

    @discord.ui.button(label="🎴 カード選択", style=discord.ButtonStyle.success, custom_id="janken_choose")
    async def choose_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ あなた用のボタンではありません。")
            return
        if self.game.resolving:
            await interaction.response.send_message("⏳ いま勝敗処理中です。少し待ってね。")
            return
        if self.game.selected.get(self.player_id) is not None:
            await interaction.response.send_message("✅ すでに選択済みです。")
            return

        hand = self.game.hands.get(self.player_id, [])
        if not hand:
            await interaction.response.send_message("❌ 手札がありません。")
            return

        view = JankenSelectView(self.cog, self.game, self.player_id)
        await interaction.response.send_message("出すカードを選んでね👇", view=view)

    @discord.ui.button(label="👁 対戦相手の手札確認", style=discord.ButtonStyle.secondary, custom_id="janken_peek")
    async def peek_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ あなた用のボタンではありません。")
            return

        opp = self.game.other(self.player_id)
        if opp is None:
            await interaction.response.send_message("❌ 対戦相手が見つかりません。")
            return

        opp_hand = self.game.hands.get(opp, [])
        msg = "相手の手札情報（星は非公開）\n" + summarize_hand(opp_hand)
        await interaction.response.send_message(msg)


class JankenSelectView(discord.ui.View):
    def __init__(self, cog: "JankenCardCog", game: JankenGame, player_id: int):
        super().__init__(timeout=TURN_TIMEOUT)
        self.cog = cog
        self.game = game
        self.player_id = player_id
        self.choice_index: Optional[int] = None

        # 初期化時にselectを組む
        hand = self.game.hands.get(self.player_id, [])
        opts = []
        for i in range(len(hand)):
            opts.append(discord.SelectOption(label=f"{i+1}枚目", value=str(i)))
        self.select = discord.ui.Select(
            placeholder="出すカードを選択",
            min_values=1,
            max_values=1,
            options=opts
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ あなた用の選択ではありません。")
            return
        self.choice_index = int(self.select.values[0])
        await interaction.response.send_message(f"✅ {self.choice_index+1}枚目を選択しました。確定を押してね。")

    @discord.ui.button(label="確定", style=discord.ButtonStyle.primary)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ あなた用のボタンではありません。")
            return
        if self.choice_index is None:
            await interaction.response.send_message("❌ 先にプルダウンで選んでね。")
            return

        ok = await self.cog._confirm_choice(self.game, self.player_id, self.choice_index)
        if ok:
            # このViewは終了
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content="✅ カードを確定しました。相手の確定を待ってね。", view=self)
            self.stop()
        else:
            await interaction.response.send_message("❌ すでに確定済み or 無効な選択です。")


# =========================================================
# Cog本体
# =========================================================

class JankenCardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: Dict[Tuple[int, int], JankenGame] = {}  # (guild_id, channel_id) -> game
        self.panel_message_ids: Dict[Tuple[int, int], int] = {}  # panel message id

    # -----------------------------
    # 通貨（既存Botに合わせて吸収）
    # -----------------------------
    async def _get_balance(self, user_id: int, guild_id: int) -> int:
        row = await self.bot.db.get_user(str(user_id), str(guild_id))
        return int(row["balance"])


    async def _add_balance(self, user_id: int, amount: int, guild_id: int):
        await self.bot.db.add_balance(str(user_id), str(guild_id), amount)


    async def _sub_balance(self, user_id: int, amount: int, guild_id: int) -> bool:
        row = await self.bot.db.get_user(str(user_id), str(guild_id))
        if row["balance"] < amount:
            return False
        await self.bot.db.remove_balance(str(user_id), str(guild_id), amount)
        return True

    # -----------------------------
    # /じゃんけんカード
    # -----------------------------
    @app_commands.command(name="じゃんけんカード", description="じゃんけんカードゲーム（2人専用）")
    @app_commands.describe(rate="勝敗で移動するレート（整数）")
    async def janken_card(self, interaction: discord.Interaction, rate: int):
        await interaction.response.defer()
        
        if rate <= 0:
            await interaction.response.send_message("❌ rate は1以上で指定してください。", ephemeral=True)
            return

        if interaction.guild_id is None:
            await interaction.response.send_message("❌ サーバー内で実行してください。", ephemeral=True)
            return

        key = (interaction.guild_id, interaction.channel_id)
        if key in self.games and self.games[key].started:
            await interaction.response.send_message("❌ このチャンネルではすでにゲームが進行中です。", ephemeral=True)
            return

        # 既存があって未開始なら上書き再募集
        game = JankenGame(interaction.guild_id, interaction.channel_id, interaction.user.id, rate)
        self.games[key] = game

        # 主催者は自動参加（※仕様に合わせて外してもOK）
        bal = await self._get_balance(interaction.user.id, interaction.guild_id)
        if bal < rate:
            await interaction.response.send_message(
                f"❌ 主催者の残高が不足しています。（必要: {rate} / 現在: {bal}）",
                ephemeral=True
            )
            self.games.pop(key, None)
            return

        game.players.append(interaction.user.id)
        game.wins[interaction.user.id] = 0
        game.selected[interaction.user.id] = None

        embed = self._build_panel_embed(interaction.guild, game)
        view = JankenPanelView(self, game)

        await interaction.response.send_message(embed=embed, view=view)
        try:
            msg = await interaction.original_response()
            self.panel_message_ids[key] = msg.id
        except Exception:
            pass

    def _build_panel_embed(self, guild: discord.Guild, game: JankenGame) -> discord.Embed:
        embed = discord.Embed(
            title="🃏 じゃんけんカードゲーム",
            description=(
                "山札から5枚ランダムにお互いに配られたカードを使用し、下記ルールに沿ってじゃんけんを最大5回戦行う。\n"
                f"先に{WIN_TARGET}勝したら勝利。\n\n"
                "**山札の内訳は以下。**\n\n"
                "グー(⭐︎1〜⭐︎5)\n"
                "チョキ(⭐︎1〜⭐︎5)\n"
                "パー(⭐︎1〜⭐︎5)\n"
                "計15枚"
            ),
            color=discord.Color.blurple()
        )

        p_lines = []
        for pid in game.players:
            m = guild.get_member(pid)
            p_lines.append(f"・{m.display_name if m else pid}")
        while len(p_lines) < MAX_PLAYERS:
            p_lines.append("・（未参加）")

        embed.add_field(name="レート", value=str(game.rate), inline=True)
        embed.add_field(name="参加者", value="\n".join(p_lines), inline=False)

        if len(game.players) == MAX_PLAYERS and not game.started:
            embed.set_footer(text="✅ 参加者が揃いました。主催者が「開始」を押せます。")
        elif game.started:
            embed.set_footer(text="🎮 ゲーム進行中")
        else:
            embed.set_footer(text="参加ボタンで参加できます（2人まで）")

        return embed

    async def _update_panel_message(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            return
        key = (interaction.guild_id, interaction.channel_id)
        game = self.games.get(key)
        if not game:
            return

        # panel message を編集（interaction.message が取れる場合はそれを優先）
        embed = self._build_panel_embed(interaction.guild, game)
        view = JankenPanelView(self, game)

        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=view)
                return
        except Exception:
            pass

        # message id を覚えてる場合
        mid = self.panel_message_ids.get(key)
        if mid:
            try:
                ch = interaction.channel
                if isinstance(ch, discord.TextChannel):
                    msg = await ch.fetch_message(mid)
                    await msg.edit(embed=embed, view=view)
            except Exception:
                pass

    # -----------------------------
    # ゲーム開始
    # -----------------------------
    async def _start_game(self, interaction: discord.Interaction, game: JankenGame):
        # デッキ生成
        deck = build_deck()
        random.shuffle(deck)
        game.deck = deck

        # 5枚ずつ配布（重複なし・共通山札）
        p1, p2 = game.players[0], game.players[1]
        game.hands[p1] = [game.deck.pop() for _ in range(5)]
        game.hands[p2] = [game.deck.pop() for _ in range(5)]
        game.wins[p1] = 0
        game.wins[p2] = 0

        game.round_no = 0
        game.round_token += 1

        # 最初のDM配布
        await self._send_hand_dm(game, p1, first=True)
        await self._send_hand_dm(game, p2, first=True)

        # ラウンド開始
        await self._begin_round(interaction, game)

    async def _send_hand_dm(self, game: JankenGame, player_id: int, first: bool = False):
        user = self.bot.get_user(player_id) or await self.bot.fetch_user(player_id)
        hand = game.hands.get(player_id, [])
        file = await create_hand_image(hand)

        header = "🎴 あなたの手札はこちら：" if first else "🎴 次の手札はこちら："
        footer = f"\n（{TURN_TIMEOUT}秒以内に選ばないとランダムで出ます）"
        view = JankenHandView(self, game, player_id)

        try:
            await user.send(content=header + footer, file=file, view=view)
        except discord.Forbidden:
            # DM不可はこのゲーム仕様だと致命的なので、チャンネルへ通知
            ch = self.bot.get_channel(game.channel_id)
            if ch:
                await ch.send(f"⚠️ <@{player_id}> にDMを送れません。ゲームを中止してください。")

    async def _begin_round(self, interaction: discord.Interaction, game: JankenGame):
        if game.resolving:
            return
        game.round_no += 1
        game.round_token += 1
        token = game.round_token

        # 選択リセット
        for pid in game.players:
            game.selected[pid] = None

        # ラウンド開始告知
        p1, p2 = game.players
        await interaction.channel.send(
            f"🟦 **第{game.round_no}回戦** 開始！\n"
            f"先に{WIN_TARGET}勝で勝利（最大{MAX_ROUNDS}回戦）。\n"
            f"現在：<@{p1}> {game.wins[p1]}勝 / <@{p2}> {game.wins[p2]}勝"
        )

        # 60秒後に未確定を自動選択して、揃ったら解決へ
        async def _timeout_task():
            await asyncio.sleep(TURN_TIMEOUT)
            # トークンが変わってたら古いラウンドなので無視
            if game.round_token != token:
                return
            # 未確定を埋める
            for pid in game.players:
                await self._auto_pick_if_needed(game, pid)
            # 両者揃っていれば解決
            await self._try_resolve_round(interaction, game)

        asyncio.create_task(_timeout_task())

    async def _auto_pick_if_needed(self, game: JankenGame, player_id: int):
        if game.selected.get(player_id) is not None:
            return
        hand = game.hands.get(player_id, [])
        if not hand:
            return
        idx = random.randrange(0, len(hand))
        game.selected[player_id] = idx
        # DMで通知（軽め）
        user = self.bot.get_user(player_id)
        if user:
            try:
                await user.send(f"⏱️ 時間切れ！ {idx+1}枚目が自動で選ばれました。")
            except Exception:
                pass

    async def _confirm_choice(self, game: JankenGame, player_id: int, index: int) -> bool:
        if game.resolving:
            return False
        if game.selected.get(player_id) is not None:
            return False
        hand = game.hands.get(player_id, [])
        if not (0 <= index < len(hand)):
            return False
        game.selected[player_id] = index
        return True

    async def _try_resolve_round(self, interaction: discord.Interaction, game: JankenGame):
        if game.resolving:
            return
        if any(game.selected.get(pid) is None for pid in game.players):
            return
        await self._resolve_round(interaction, game)

    async def _resolve_round(self, interaction: discord.Interaction, game: JankenGame):
        game.resolving = True

        p1, p2 = game.players
        i1 = game.selected[p1]
        i2 = game.selected[p2]
        assert i1 is not None and i2 is not None

        h1 = game.hands[p1]
        h2 = game.hands[p2]
        c1 = h1[i1]
        c2 = h2[i2]

        # 判定
        result = judge(c1, c2)

        # 公開（星は公開OKの仕様だったので表示）
        line = (
            f"🂡 <@{p1}>：**{c1.label_jp}⭐{c1.star}**\n"
            f"🂡 <@{p2}>：**{c2.label_jp}⭐{c2.star}**\n"
        )

        if result == "A":
            game.wins[p1] += 1
            line += f"✅ 勝者：<@{p1}>"
        elif result == "B":
            game.wins[p2] += 1
            line += f"✅ 勝者：<@{p2}>"
        else:
            line += "🤝 引き分け（勝敗なし）"

        await interaction.channel.send(line)

        # 使用カードを除外（引き分けでも両者消費）
        # 高いindexからpopして安全に
        for pid, idx in sorted([(p1, i1), (p2, i2)], key=lambda x: x[1], reverse=True):
            hand = game.hands[pid]
            if 0 <= idx < len(hand):
                hand.pop(idx)

        # 勝利チェック
        winner_id: Optional[int] = None
        loser_id: Optional[int] = None

        if game.wins[p1] >= WIN_TARGET:
            winner_id, loser_id = p1, p2
        elif game.wins[p2] >= WIN_TARGET:
            winner_id, loser_id = p2, p1

        # まだ決着してない場合、残りラウンド/手札で継続
        if winner_id is None and game.round_no < MAX_ROUNDS and game.hands[p1] and game.hands[p2]:
            # 次の手札DM（残り枚数が減っていく）
            await self._send_hand_dm(game, p1, first=False)
            await self._send_hand_dm(game, p2, first=False)

            # 次ラウンド開始
            game.resolving = False
            await self._begin_round(interaction, game)
            return

        # 決着（5回戦終了 or 手札切れでも判定）
        if winner_id is None:
            # 勝利数で決定（同数なら引き分け）
            if game.wins[p1] > game.wins[p2]:
                winner_id, loser_id = p1, p2
            elif game.wins[p2] > game.wins[p1]:
                winner_id, loser_id = p2, p1
            else:
                # 引き分け
                await interaction.channel.send(
                    f"🏁 終了！ **引き分け**\n"
                    f"<@{p1}> {game.wins[p1]}勝 / <@{p2}> {game.wins[p2]}勝\n"
                    f"（レート移動なし）"
                )
                self._cleanup_game(game)
                return

        # 残高移動（敗者が払えないケースは参加時点で弾いてる想定だが念のため再チェック）
        guild_id = game.guild_id
        bal_loser = await self._get_balance(loser_id, guild_id)
        if bal_loser < game.rate:
            await interaction.channel.send(
                f"⚠️ 結果確定時点で敗者の残高が不足していました。（必要:{game.rate} / 現在:{bal_loser}）\n"
                f"今回は **移動なし** で終了します。"
            )
            self._cleanup_game(game)
            return

        ok = await self._sub_balance(loser_id, game.rate, guild_id)
        if not ok:
            await interaction.channel.send("⚠️ 減算に失敗しました。今回は移動なしで終了します。")
            self._cleanup_game(game)
            return

        await self._add_balance(winner_id, game.rate, guild_id)

        await interaction.channel.send(
            f"🏆 **勝者：<@{winner_id}>**\n"
            f"💸 <@{loser_id}> から **{game.rate}** を回収 → <@{winner_id}> に付与しました。\n"
            f"最終：<@{p1}> {game.wins[p1]}勝 / <@{p2}> {game.wins[p2]}勝"
        )

        self._cleanup_game(game)

    def _cleanup_game(self, game: JankenGame):
        key = (game.guild_id, game.channel_id)
        self.games.pop(key, None)
        self.panel_message_ids.pop(key, None)

    # -----------------------------
    # 起動時：永続View登録
    # -----------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        # 再起動後もボタンを生かしたい場合は add_view が必要。
        # ただし、gameを復元しないと押しても反応できないため、
        # 「稼働中セッションを永続化」していない限りは実害が少ない。
        # ここでは登録だけ（カスタムIDが一致すればDiscord側は押せる）
        try:
            self.bot.add_view(JankenPanelView(self, JankenGame(0, 0, 0, 1)))
        except Exception:
            pass


async def setup(bot: commands.Bot):

    await bot.add_cog(JankenCardCog(bot))


