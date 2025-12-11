# logger.py
# ============================================================
# 各種ログ送信ユーティリティ
# - 通貨ログ
# - 管理ログ
# - 給料ログ
# すべて端末言語に依存しない「日本語固定の日時表記」で送信
# ============================================================

from datetime import datetime, timezone, timedelta


# ------------------------------------------------------------
# 日本語固定の日時生成
# ------------------------------------------------------------
def format_jp_now() -> str:
    """
    現在時刻を「2025年01月01日 12:34:56」形式で返す。
    Discord の <t:timestamp:F> は使用しない。
    """
    dt = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    )
    return dt.strftime("%Y年%m月%d日 %H:%M:%S")


# ------------------------------------------------------------
# 通貨送金ログ
# ------------------------------------------------------------
async def log_pay(bot, settings, from_id, to_id, amount, memo=None):
    """通貨送金ログ"""

    channel_id = settings.get("log_pay")
    if not channel_id:
        return

    ch = bot.get_channel(int(channel_id))
    if not ch:
        return

    unit = settings["currency_unit"]
    now = format_jp_now()

    text = (
        "【通貨ログ】\n"
        f"送金者: <@{from_id}>\n"
        f"受取者: <@{to_id}>\n"
        f"金額: {amount} {unit}\n"
    )
    if memo:
        text += f"メモ: {memo}\n"

    text += f"日時: {now}"

    await ch.send(text)


# ------------------------------------------------------------
# 残高設定ログ
# ------------------------------------------------------------
async def log_manage(bot, settings, admin_id, target_id, action, amount, new_balance):
    """残高設定ログ"""

    channel_id = settings.get("log_manage")
    if not channel_id:
        return

    ch = bot.get_channel(int(channel_id))
    if not ch:
        return

    unit = settings["currency_unit"]
    now = format_jp_now()

    await ch.send(
        f"【管理ログ】\n"
        f"管理者: <@{admin_id}>\n"
        f"対象: <@{target_id}>\n"
        f"操作: {action}\n"
        f"変更額: {amount} {unit}\n"
        f"新残高: {new_balance} {unit}\n"
        f"日時: {now}"
    )


# ------------------------------------------------------------
# 給料配布ログ
# ------------------------------------------------------------
async def log_salary(bot, settings, executor_id, total_users, total_amount):
    """給料配布ログ"""

    channel_id = settings.get("log_salary")
    if not channel_id:
        return

    ch = bot.get_channel(int(channel_id))
    if not ch:
        return

    unit = settings["currency_unit"]
    now = format_jp_now()

    await ch.send(
        f"【給料ログ】\n"
        f"実行者: <@{executor_id}>\n"
        f"対象人数: {total_users}\n"
        f"合計配布額: {total_amount} {unit}\n"
        f"日時: {now}"
    )
