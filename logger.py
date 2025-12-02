# logger.py

async def log_pay(bot, settings, from_id, to_id, amount):
    """通貨送金ログ"""
    channel_id = settings["log_pay"]
    if not channel_id:
        return

    ch = bot.get_channel(int(channel_id))
    if not ch:
        return

    await ch.send(
        f"【通貨ログ】\n"
        f"送金者: <@{from_id}>\n"
        f"受取者: <@{to_id}>\n"
        f"金額: {amount} {settings['currency_unit']}\n"
        f"日時: <t:{int(__import__('time').time())}:F>"
    )


async def log_manage(bot, settings, admin_id, target_id, action, amount, new_balance):
    """残高設定ログ"""
    channel_id = settings["log_manage"]
    if not channel_id:
        return

    ch = bot.get_channel(int(channel_id))
    if not ch:
        return

    await ch.send(
        f"【管理ログ】\n"
        f"管理者: <@{admin_id}>\n"
        f"対象: <@{target_id}>\n"
        f"操作: {action}\n"
        f"変更額: {amount}\n"
        f"新残高: {new_balance}\n"
        f"日時: <t:{int(__import__('time').time())}:F>"
    )


async def log_salary(bot, settings, executor_id, total_users, total_amount):
    """給料配布ログ"""
    channel_id = settings["log_salary"]
    if not channel_id:
        return

    ch = bot.get_channel(int(channel_id))
    if not ch:
        return

    await ch.send(
        f"【給料ログ】\n"
        f"実行者: <@{executor_id}>\n"
        f"対象人数: {total_users}\n"
        f"合計配布額: {total_amount} {settings['currency_unit']}\n"
        f"日時: <t:{int(__import__('time').time())}:F>"
    )
