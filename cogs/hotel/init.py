# cogs/hotel/__init__.py

"""
高級ホテルシステム モジュール一式

構成：
- checkin.py          / チェックイン関連（パネル生成・初期設定）
- ticket_buttons.py   / チケット購入ボタン・確認モーダル
- room_panel.py       / VC 内操作パネル本体（View）
- room_buttons.py     / VC 内の10ボタン（人数、延長、許可など）
- setup.py            / Cog 登録エントリーポイント
"""

from .checkin import HotelCheckinCog
from .ticket_buttons import TicketButtonsCog
from .room_buttons import RoomButtonsCog

__all__ = [
    "HotelCheckinCog",
    "TicketButtonsCog",
    "RoomButtonsCog",
]
