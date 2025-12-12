# handlers/__init__.py
# Handler modules for the casino bot

from .basic import (
    start,
    help_command,
    balance_command,
    profile_command,
    history_command,
    play_command,
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
    handle_text_message,
)

from .admin import (
    addadmin_command,
    removeadmin_command,
    listadmins_command,
    set_video_command,
    handle_video_message,
    cancel_command,
)

from .social import (
    tip_command,
    bonus_command,
)

from .callbacks import button_callback

__all__ = [
    # Basic
    'start',
    'help_command',
    'balance_command',
    'profile_command',
    'history_command',
    'play_command',
    # Games
    'dice_command',
    'bowl_command',
    'arrow_command',
    'football_command',
    'basket_command',
    'demo_command',
    'handle_game_emoji',
    # Payments
    'deposit_command',
    'withdraw_command',
    'custom_deposit',
    'precheckout_callback',
    'successful_payment',
    'handle_text_message',
    # Admin
    'addadmin_command',
    'removeadmin_command',
    'listadmins_command',
    'set_video_command',
    'handle_video_message',
    'cancel_command',
    # Social
    'tip_command',
    'bonus_command',
    # Callbacks
    'button_callback',
]
