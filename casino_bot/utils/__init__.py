# utils/__init__.py
# Utility functions and decorators for the casino bot

from .decorators import handle_errors
from .helpers import (
    is_admin,
    get_user_balance,
    set_user_balance,
    adjust_user_balance,
    get_user_link,
    get_or_create_profile,
    get_user_rank,
    get_rank_info,
    add_xp,
    update_game_stats,
    generate_transaction_id,
    is_valid_ton_address,
    check_bot_name_in_profile,
    is_private_chat,
    save_last_game_settings,
    get_user_id_by_username,
    create_progress_bar,
)

__all__ = [
    'handle_errors',
    'is_admin',
    'get_user_balance',
    'set_user_balance',
    'adjust_user_balance',
    'get_user_link',
    'get_or_create_profile',
    'get_user_rank',
    'get_rank_info',
    'add_xp',
    'update_game_stats',
    'generate_transaction_id',
    'is_valid_ton_address',
    'check_bot_name_in_profile',
    'is_private_chat',
    'save_last_game_settings',
    'get_user_id_by_username',
    'create_progress_bar',
]
