# utils/helpers.py
# Helper functions for user management, validation, and game utilities

import random
import string
import re
import logging
from datetime import datetime
from collections import defaultdict

from telegram import Update

from config import (
    ADMIN_BALANCE, STARS_TO_USD, RANKS, GAME_TYPES, BOT_USERNAME
)
import database as db

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    return user_id in db.admin_list


def get_user_balance(user_id: int) -> float:
    """Get user's current balance. Admins get unlimited balance."""
    if is_admin(user_id):
        return ADMIN_BALANCE
    return db.user_balances[user_id]


def set_user_balance(user_id: int, amount: float):
    """Set user's balance to a specific amount. Admins are excluded."""
    if not is_admin(user_id):
        db.user_balances[user_id] = amount
        db.save_data()


def adjust_user_balance(user_id: int, amount: float):
    """Add or subtract from user's balance. Admins are excluded."""
    if not is_admin(user_id):
        db.user_balances[user_id] += amount
        db.save_data()


def get_user_link(user_id: int, name: str) -> str:
    """Generate an HTML user link for Telegram."""
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def get_or_create_profile(user_id: int, username: str = None) -> dict:
    """
    Get existing user profile or create a new one.
    
    Args:
        user_id: Telegram user ID
        username: Optional username to associate with the profile
        
    Returns:
        User profile dictionary
    """
    if user_id not in db.user_profiles:
        db.user_profiles[user_id] = {
            'user_id': user_id,
            'username': username or 'Unknown',
            'registration_date': datetime.now(),
            'xp': 0,
            'total_games': 0,
            'total_bets': 0.0,
            'total_wins': 0.0,
            'total_losses': 0.0,
            'games_won': 0,
            'games_lost': 0,
            'favorite_game': None,
            'biggest_win': 0.0,
            'game_counts': defaultdict(int)
        }
        db.save_data()
    
    # Update username mapping
    if username:
        username_lower = username.lower().lstrip('@')
        db.username_to_id[username_lower] = user_id
        db.save_data()
    
    return db.user_profiles[user_id]


def get_user_rank(xp: int) -> int:
    """
    Determine user's rank level based on XP.
    
    Args:
        xp: User's current XP
        
    Returns:
        Rank level (1-20)
    """
    current_rank = 1
    for level, data in RANKS.items():
        if xp >= data['xp_required']:
            current_rank = level
        else:
            break
    return current_rank


def get_rank_info(level: int) -> dict:
    """
    Get rank information for a specific level.
    
    Args:
        level: Rank level
        
    Returns:
        Dictionary with name, xp_required, and emoji
    """
    return RANKS.get(level, RANKS[1])


def add_xp(user_id: int, amount: int) -> int:
    """
    Add XP to a user's profile.
    
    Args:
        user_id: Telegram user ID
        amount: Amount of XP to add
        
    Returns:
        User's new total XP
    """
    profile = get_or_create_profile(user_id)
    profile['xp'] += amount
    db.save_data()
    return profile['xp']


def update_game_stats(user_id: int, game_type: str, bet_amount: float, 
                      win_amount: float, won: bool):
    """
    Update user's game statistics after a game.
    
    Args:
        user_id: Telegram user ID
        game_type: Type of game played
        bet_amount: Amount bet in stars
        win_amount: Amount won (if any)
        won: Whether the user won the game
    """
    profile = get_or_create_profile(user_id)
    profile['total_games'] += 1
    profile['total_bets'] += bet_amount
    
    if won:
        profile['games_won'] += 1
        profile['total_wins'] += win_amount
        if win_amount > profile['biggest_win']:
            profile['biggest_win'] = win_amount
        add_xp(user_id, int(bet_amount * 2) + 50)
    else:
        profile['games_lost'] += 1
        profile['total_losses'] += bet_amount
        add_xp(user_id, int(bet_amount * 0.5) + 10)
    
    profile['game_counts'][game_type] += 1
    
    # Determine favorite game
    max_count = 0
    fav_game = None
    for gt, count in profile['game_counts'].items():
        if count > max_count:
            max_count = count
            fav_game = gt
    profile['favorite_game'] = fav_game
    
    # Record game in history
    db.user_game_history[user_id].append({
        'game_type': game_type,
        'bet_amount': bet_amount,
        'win_amount': win_amount if won else 0,
        'won': won,
        'timestamp': datetime.now()
    })
    
    db.save_data()


def generate_transaction_id() -> str:
    """Generate a random transaction ID for withdrawals."""
    chars = string.ascii_letters + string.digits
    return 'stx' + ''.join(random.choice(chars) for _ in range(80))


def is_valid_ton_address(address: str) -> bool:
    """
    Validate a TON wallet address.
    
    Args:
        address: TON wallet address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not address:
        return False
    
    # Standard TON address pattern
    ton_pattern = r'^(UQ|EQ|kQ|0Q)[A-Za-z0-9_-]{46}$'
    if re.match(ton_pattern, address):
        return True
    
    # Raw address pattern
    raw_pattern = r'^-?[0-9]+:[a-fA-F0-9]{64}$'
    if re.match(raw_pattern, address):
        return True
    
    # Length check for other formats
    return len(address) >= 48 and len(address) <= 67


def check_bot_name_in_profile(user) -> bool:
    """
    Check if the bot username is in the user's profile name.
    
    Args:
        user: Telegram User object
        
    Returns:
        True if bot name found in profile, False otherwise
    """
    first_name = (user.first_name or "").lower()
    last_name = (user.last_name or "").lower()
    bot_name_lower = BOT_USERNAME.lower()
    return bot_name_lower in first_name or bot_name_lower in last_name


def is_private_chat(update: Update) -> bool:
    """Check if the message is from a private chat."""
    return update.effective_chat.type == "private"


def save_last_game_settings(user_id: int, game_type: str, bet_amount: int,
                            rounds: int, throws: int, bot_first: bool):
    """
    Save user's last game settings for repeat/double feature.
    
    Args:
        user_id: Telegram user ID
        game_type: Type of game
        bet_amount: Bet amount in stars
        rounds: Number of rounds
        throws: Number of throws per round
        bot_first: Whether bot rolled first
    """
    db.user_last_game_settings[user_id] = {
        'game_type': game_type,
        'bet_amount': bet_amount,
        'rounds': rounds,
        'throws': throws,
        'bot_first': bot_first
    }
    db.save_data()


def get_user_id_by_username(username: str) -> int:
    """
    Get user_id from username.
    
    Args:
        username: Telegram username (with or without @)
        
    Returns:
        User ID if found, None otherwise
    """
    username_lower = username.lower().lstrip('@')
    return db.username_to_id.get(username_lower)


def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """
    Create a text-based progress bar.
    
    Args:
        current: Current value
        total: Total/max value
        length: Length of the progress bar in characters
        
    Returns:
        String representation of progress bar
    """
    if total == 0:
        filled = 0
    else:
        filled = int((current / total) * length)
    empty = length - filled
    return "▓" * filled + "░" * empty
