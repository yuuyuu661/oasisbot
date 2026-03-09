import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from pathlib import Path
from typing import Optional

# =========================
# 設定
# =========================
GUILD_ID = 1420918259187712093
STAMP_ROOT = Path("cogs/assets/stamps")
DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "stamp_data.json"

# 1ページに出す件数
PER_PAGE = 8

# 表示対応拡張子
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


# =========================
# データ保存
# =========================
def ensure_data_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(
            json.dumps({"favorites": {}, "recent": {}}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


def load_data():
    ensure_data_file()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    ensure_data_file()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_favorites(user_id: int) -> list[str]:
    data = load_data()
    return data.get("favorites", {}).get(str(user_id), [])


def set_user_favorites(user_id: int, favorites: list[str]):
    data = load_data()
    data.setdefault("favorites", {})[str(user_id)] = favorites
    save_data(data)


def get_user_recent(user_id: int) -> list[str]:
    data = load_data()
    return data.get("recent", {}).get(str(user_id), [])


def push_user_recent(user_id: int, stamp_key: str, limit: int = 20):
    data = load_data()
    recent = data.setdefault("recent", {}).get(str(user_id), [])

    if stamp_key in recent:
        recent.remove(stamp_key)

    recent.insert(0, stamp_key)
    recent = recent[:limit]

    data["recent"][str(user_id)] = recent
    save_data(data)


# =========================
# スタンプ走査
# =========================
def normalize_stamp_key(category: str, filename: str) -> str:
    return f"{category}/{filename}"


def scan_stamps() -> list[dict]:
    """
    戻り値例:
    [
      {
        "key": "reaction/hello.png",
        "category": "reaction",
        "filename": "hello.png",
        "name": "hello",
        "path": "stamps/reaction/hello.png"
      }
    ]
    """
    results = []

    if not STAMP_ROOT.exists():
        return results

    for category_dir in sorted(STAMP_ROOT.iterdir()):
        if not category_dir.is_dir():
            continue

        category = category_dir.name

        for f in sorted(category_dir.iterdir()):
            if not f.is_file():
                continue
            if f.suffix.lower() not in IMAGE_EXTS:
                continue

            results.append({
                "key": normalize_stamp_key(category, f.name),
                "category": category,
                "filename": f.name,
                "name": f.stem,
                "path": str(f)
            })

    return results


def build_category_choices(stamps: list[dict]) -> list[str]:
    cats = sorted({s["category"] for s in stamps})
    return ["all", "favorites", "recent"] + cats


def filter_stamps(
    stamps: list[dict],
    user_id: int,
    category: str = "all",
    query: str = ""
) -> list[dict]:
    q = query.strip().lower()
    favorites = set(get_user_favorites(user_id))
    recents = get_user_recent(user_id)

    if category == "favorites":
        filtered = [s for s in stamps if s["key"] in favorites]
    elif category == "recent":
        # recent順を維持
        key_to_stamp = {s["key"]: s for s in stamps}
        filtered = [key_to_stamp[k] for k in recents if k in key_to_stamp]
    elif category == "all":
        filtered = list(stamps)
    else:
        filtered = [s for s in stamps if s["category"] == category]

    if q:
        filtered = [
            s for s in filtered
            if q in s["name"].lower()
            or q in s["filename"].lower()
            or q in s["category"].lower()
        ]

    return filtered


def make_embed(
    stamps: list[dict],
    page: int,
    per_page: int,
    category: str,
    query: str,
    selected_index: Optional[int],
    user_id: int
) -> discord.Embed:
    total = len(stamps)
    max_page = max(0, (total - 1) // per_page)
    page = max(0, min(page, max_page))

    start = page * per_page
    end = start + per_page
    page_items = stamps[start:end]

    embed = discord.Embed(
        title="🖼 スタンプ一覧",
        color=0x2B2D31
    )

    cat_text = category
    if category == "all":
        cat_text = "すべて"
    elif category == "favorites":
        cat_text = "お気に入り"
    elif category == "recent":
        cat_text = "最近使った"

    desc = [
        f"**カテゴリ:** `{cat_text}`",
        f"**検索:** `{query or 'なし'}`",
        f"**件数:** `{total}`",
        f"**ページ:** `{page + 1}/{max_page + 1}`",
    ]
    embed.description = "\n".join(desc)

    if page_items:
        lines = []
        favorites = set(get_user_favorites(user_id))

        for idx, s in enumerate(page_items, start=1):
            star = "⭐" if s["key"] in favorites else "・"
            lines.append(f"`{idx}` {star} **{s['name']}**  `{s['category']}`")

        embed.add_field(
            name="候補",
            value="\n".join(lines),
            inline=False
        )

    else:
        embed.add_field(
            name="候補",
            value="該当するスタンプがありません。",
            inline=False
        )

    if page_items and selected_index is not None and 0 <= selected_index < len(page_items):
        selected = page_items[selected_index]
        embed.set_image(url=f"attachment://{selected['filename']}")
        embed.set_footer(text=f"選択中: {selected['category']}/{selected['filename']}")
    else:
        embed.set_footer(text="下の番号ボタンでプレビュー切替 / 送信ボタンで投稿")

    return embed


# =========================
# モーダル
# =========================
class StampSearchModal(discord.ui.Modal, title="スタンプ検索"):
    query = discord.ui.TextInput(
        label="検索ワード",
        placeholder="名前・カテゴリなど",
        required=False,
        max_length=100
    )

    def __init__(self, view: "StampBrowserView"):
        super().__init__()
        self.browser_view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.browser_view.query = str(self.query.value).strip()
        self.browser_view.page = 0
        self.browser_view.selected_index = 0
        await self.browser_view.refresh(interaction)


# =========================
# Select
# =========================
class CategorySelect(discord.ui.Select):
    def __init__(self, categories: list[str], current: str):
        options = []
        for c in categories[:25]:
            if c == "all":
                label = "すべて"
                desc = "すべてのスタンプ"
            elif c == "favorites":
                label = "お気に入り"
                desc = "お気に入り登録したスタンプ"
            elif c == "recent":
                label = "最近使った"
                desc = "最近使用したスタンプ"
            else:
                label = c
                desc = f"{c} カテゴリ"

            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=c,
                    description=desc[:100],
                    default=(c == current)
                )
            )

        super().__init__(
            placeholder="カテゴリを選択",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        view.category = self.values[0]
        view.page = 0
        view.selected_index = 0
        await view.refresh(interaction)


# =========================
# ボタン
# =========================
class PreviewButton(discord.ui.Button):
    def __init__(self, label_num: int, row: int):
        super().__init__(
            label=str(label_num),
            style=discord.ButtonStyle.secondary,
            row=row
        )
        self.label_num = label_num

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        local_index = self.label_num - 1
        view.selected_index = local_index
        await view.refresh(interaction)


class PrevPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="⬅️", style=discord.ButtonStyle.primary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        view.page = max(0, view.page - 1)
        view.selected_index = 0
        await view.refresh(interaction)


class NextPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="➡️", style=discord.ButtonStyle.primary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        view.page = min(view.max_page, view.page + 1)
        view.selected_index = 0
        await view.refresh(interaction)


class SearchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="検索", emoji="🔎", style=discord.ButtonStyle.success, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        await interaction.response.send_modal(StampSearchModal(view))


class ClearSearchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="検索解除", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        view.query = ""
        view.page = 0
        view.selected_index = 0
        await view.refresh(interaction)


class FavoriteToggleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="お気に入り切替", emoji="⭐", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        selected = view.get_selected_stamp()

        if not selected:
            await interaction.response.send_message("選択中のスタンプがありません。", ephemeral=True)
            return

        favorites = get_user_favorites(interaction.user.id)
        key = selected["key"]

        if key in favorites:
            favorites.remove(key)
        else:
            favorites.append(key)

        set_user_favorites(interaction.user.id, favorites)
        await view.refresh(interaction)


class SendStampButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="送信", emoji="📤", style=discord.ButtonStyle.success, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: StampBrowserView = self.view
        selected = view.get_selected_stamp()

        if not selected:
            await interaction.response.send_message("送信するスタンプを選んでください。", ephemeral=True)
            return

        if not os.path.exists(selected["path"]):
            await interaction.response.send_message("ファイルが見つかりません。", ephemeral=True)
            return

        push_user_recent(interaction.user.id, selected["key"])

        file = discord.File(selected["path"], filename=selected["filename"])

        # 先にephemeral更新
        await interaction.response.edit_message(
            embed=view.build_embed(),
            view=view,
            attachments=view.build_preview_attachments()
        )

        # チャットに送信
        await interaction.followup.send(file=file)


# =========================
# View
# =========================
class StampBrowserView(discord.ui.View):
    def __init__(self, user_id: int, stamps: list[dict]):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.all_stamps = stamps

        self.category = "all"
        self.query = ""
        self.page = 0
        self.selected_index = 0

        self.filtered_stamps: list[dict] = []
        self.max_page = 0

        self.rebuild()

    def get_filtered(self) -> list[dict]:
        return filter_stamps(
            self.all_stamps,
            self.user_id,
            self.category,
            self.query
        )

    def get_page_items(self) -> list[dict]:
        start = self.page * PER_PAGE
        end = start + PER_PAGE
        return self.filtered_stamps[start:end]

    def get_selected_stamp(self) -> Optional[dict]:
        page_items = self.get_page_items()
        if not page_items:
            return None

        if self.selected_index < 0 or self.selected_index >= len(page_items):
            self.selected_index = 0

        return page_items[self.selected_index]

    def rebuild(self):
        self.clear_items()

        self.filtered_stamps = self.get_filtered()
        self.max_page = max(0, (len(self.filtered_stamps) - 1) // PER_PAGE)

        if self.page > self.max_page:
            self.page = self.max_page

        page_items = self.get_page_items()
        if page_items:
            if self.selected_index >= len(page_items):
                self.selected_index = 0
        else:
            self.selected_index = 0

        categories = build_category_choices(self.all_stamps)
        self.add_item(CategorySelect(categories, self.category))

        # 1〜8の番号ボタン
        # row1に1-4, row2に5-8
        for i in range(4):
            btn = PreviewButton(i + 1, row=1)
            btn.disabled = i >= len(page_items)
            self.add_item(btn)

        for i in range(4, 8):
            btn = PreviewButton(i + 1, row=2)
            btn.disabled = i >= len(page_items)
            self.add_item(btn)

        self.add_item(PrevPageButton())
        self.add_item(NextPageButton())
        self.add_item(SearchButton())
        self.add_item(ClearSearchButton())
        self.add_item(FavoriteToggleButton())
        self.add_item(SendStampButton())

    def build_embed(self) -> discord.Embed:
        return make_embed(
            stamps=self.filtered_stamps,
            page=self.page,
            per_page=PER_PAGE,
            category=self.category,
            query=self.query,
            selected_index=self.selected_index,
            user_id=self.user_id
        )

    def build_preview_attachments(self) -> list[discord.File]:
        selected = self.get_selected_stamp()
        if not selected:
            return []

        if not os.path.exists(selected["path"]):
            return []

        # embed.set_image(url="attachment://...") 用
        return [discord.File(selected["path"], filename=selected["filename"])]

    async def refresh(self, interaction: discord.Interaction):
        self.rebuild()
        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self,
            attachments=self.build_preview_attachments()
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# =========================
# Cog
# =========================
class StampSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="スタンプ", description="スタンプ一覧を開きます")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def stamp(self, interaction: discord.Interaction):
        stamps = scan_stamps()

        if not STAMP_ROOT.exists():
            await interaction.response.send_message(
                f"`{STAMP_ROOT}` フォルダがありません。",
                ephemeral=True
            )
            return

        if not stamps:
            await interaction.response.send_message(
                "スタンプが見つかりませんでした。",
                ephemeral=True
            )
            return

        view = StampBrowserView(interaction.user.id, stamps)
        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            attachments=view.build_preview_attachments(),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(StampSystem(bot))

