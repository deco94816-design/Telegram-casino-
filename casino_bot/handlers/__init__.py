# handlers/__init__.py
# Handler imports for the casino bot

from .basic import (
    start,
    help_command,
    balance_command,
    profile_command,
    history_command,
    play_command,
    cancel_command,
)
from .games import (
    dice_command,
    bowl_command,
    arrow_command,
    football_command,
    basket_command,
    demo_command,
    handle_game_emoji,
)
from .payments import (
    deposit_command,
    withdraw_command,
    custom_deposit,
    precheckout_callback,
    successful_payment,
)
from .admin import (
    addadmin_command,
    removeadmin_command,
    listadmins_command,
    set_video_command,
    handle_video_message,
)
from .social import (
    tip_command,
    bonus_command,
)
from .callbacks import button_callback
from .text_handler import handle_text_message

__all__ = [
    # Basic handlers
    'start',
    'help_command',
    'balance_command',
    'profile_command',
    'history_command',
    'play_command',
    'cancel_command',
    # Game handlers
    'dice_command',
    'bowl_command',
    'arrow_command',
    'football_command',
    'basket_command',
    'demo_command',
    'handle_game_emoji',
    # Payment handlers
    'deposit_command',
    'withdraw_command',
    'custom_deposit',
    'precheckout_callback',
    'successful_payment',
    # Admin handlers
    'addadmin_command',
    'removeadmin_command',
    'listadmins_command',
    'set_video_command',
    'handle_video_message',
    # Social handlers
    'tip_command',
    'bonus_command',
    # Callback handler
    'button_callback',
    # Text handler
    'handle_text_message',
]
