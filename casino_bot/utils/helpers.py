# utils/helpers.py
# Helper functions for the casino bot

import random
import string
import re
from datetime import datetime
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from config import (
    ADMIN_BALANCE, STARS_TO_USD, GAME_TYPES, RANKS, BOT_USERNAME, logger
)
from database import (
    admin_list, user_balances, user_profiles, user_game_history,
    user_last_game_settings, username_to_id, user_games, save_data
)
from models import Game


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in admin_list


def get_user_balance(user_id: int) -> float:
    """Get user's balance. Admins have unlimited balance."""
    if is_admin(user_id):
        return ADMIN_BALANCE
    return user_balances[user_id]


def set_user_balance(user_id: int, amount: float):
    """Set user's balance (not applicable for admins)."""
    if not is_admin(user_id):
        user_balances[user_id] = amount
        save_data()


def adjust_user_balance(user_id: int, amount: float):
    """Adjust user's balance by the given amount (not applicable for admins)."""
    if not is_admin(user_id):
        user_balances[user_id] += amount
        save_data()


def get_user_link(user_id: int, name: str) -> str:
    """Generate a Telegram user mention link."""
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def get_or_create_profile(user_id: int, username: str = None) -> dict:
    """Get or create a user profile with default values."""
    if user_id not in user_profiles:
        user_profiles[user_id] = {
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
        save_data()
    
    # Update username mapping
    if username:
        username_lower = username.lower().lstrip('@')
        username_to_id[username_lower] = user_id
        save_data()
    
    return user_profiles[user_id]


def get_user_rank(xp: int) -> int:
    """Get the rank level based on XP."""
    current_rank = 1
    for level, data in RANKS.items():
        if xp >= data['xp_required']:
            current_rank = level
        else:
            break
    return current_rank


def get_rank_info(level: int) -> dict:
    """Get rank information for a given level."""
    return RANKS.get(level, RANKS[1])


def add_xp(user_id: int, amount: int) -> int:
    """Add XP to a user and return the new total."""
    profile = get_or_create_profile(user_id)
    profile['xp'] += amount
    save_data()
    return profile['xp']


def update_game_stats(user_id: int, game_type: str, bet_amount: float, 
                      win_amount: float, won: bool):
    """Update user's game statistics after a game."""
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
    
    # Update favorite game
    max_count = 0
    fav_game = None
    for gt, count in profile['game_counts'].items():
        if count > max_count:
            max_count = count
            fav_game = gt
    profile['favorite_game'] = fav_game
    
    # Add to game history
    user_game_history[user_id].append({
        'game_type': game_type,
        'bet_amount': bet_amount,
        'win_amount': win_amount if won else 0,
        'won': won,
        'timestamp': datetime.now()
    })
    
    save_data()


def generate_transaction_id() -> str:
    """Generate a unique transaction ID."""
    chars = string.ascii_letters + string.digits
    return 'stx' + ''.join(random.choice(chars) for _ in range(80))


def is_valid_ton_address(address: str) -> bool:
    """Validate a TON wallet address."""
    if not address:
        return False
    
    # Standard TON address format (UQ, EQ, kQ, 0Q prefix)
    ton_pattern = r'^(UQ|EQ|kQ|0Q)[A-Za-z0-9_-]{46}$'
    if re.match(ton_pattern, address):
        return True
    
    # Raw address format
    raw_pattern = r'^-?[0-9]+:[a-fA-F0-9]{64}$'
    if re.match(raw_pattern, address):
        return True
    
    # General length check
    return len(address) >= 48 and len(address) <= 67


def check_bot_name_in_profile(user) -> bool:
    """Check if the bot username is in user's profile name."""
    first_name = (user.first_name or "").lower()
    last_name = (user.last_name or "").lower()
    bot_name_lower = BOT_USERNAME.lower()
    return bot_name_lower in first_name or bot_name_lower in last_name


def is_private_chat(update: Update) -> bool:
    """Check if the message is from a private chat."""
    return update.effective_chat.type == "private"


def save_last_game_settings(user_id: int, game_type: str, bet_amount: int, 
                            rounds: int, throws: int, bot_first: bool):
    """Save user's last game settings for repeat/double feature."""
    user_last_game_settings[user_id] = {
        'game_type': game_type,
        'bet_amount': bet_amount,
        'rounds': rounds,
        'throws': throws,
        'bot_first': bot_first
    }
    save_data()


def get_user_id_by_username(username: str) -> int:
    """Get user_id from username."""
    username_lower = username.lower().lstrip('@')
    return username_to_id.get(username_lower)


def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Create a text-based progress bar."""
    if total == 0:
        filled = 0
    else:
        filled = int((current / total) * length)
    empty = length - filled
    return "▓" * filled + "░" * empty


async def start_repeat_game(context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                            chat_id: int, double: bool = False):
    """Start a repeat/double game based on last game settings."""
    import asyncio
    
    if user_id not in user_last_game_settings:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ No previous game found to repeat!",
            parse_mode='HTML'
        )
        return
    
    settings = user_last_game_settings[user_id]
    game_type = settings['game_type']
    bet_amount = settings['bet_amount']
    rounds = settings['rounds']
    throws = settings['throws']
    bot_first = settings['bot_first']
    
    if double:
        bet_amount = bet_amount * 2
    
    balance = get_user_balance(user_id)
    
    if balance < bet_amount and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ <b>Insufficient balance!</b>\n\n"
                 f"Required: <b>{bet_amount} ⭐</b>\n"
                 f"Your balance: <b>{balance} ⭐</b>\n\n"
                 f"Use /deposit to add more Stars.",
            parse_mode='HTML'
        )
        return
    
    if user_id in user_games:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ You already have an active game! Finish it first.",
            parse_mode='HTML'
        )
        return
    
    # Deduct balance
    if not is_admin(user_id):
        user_balances[user_id] -= bet_amount
        save_data()
    
    # Get username from profile
    profile = user_profiles.get(user_id, {})
    username = profile.get('username', 'Player')
    
    game = Game(
        user_id=user_id,
        username=username,
        bet_amount=bet_amount,
        rounds=rounds,
        throw_count=throws,
        game_type=game_type
    )
    game.is_demo = False
    game.bot_first = bot_first
    game.bot_rolled_this_round = False
    game.user_throws_this_round = 0
    user_games[user_id] = game
    
    game_info = GAME_TYPES[game_type]
    double_tag = " (DOUBLED!)" if double else ""
    
    if game.bot_first:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{game_info['icon']} <b>Game Started!{double_tag}</b>\n\n"
                 f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                 f"🔄 Rounds: <b>{rounds}</b>\n"
                 f"🎯 Throws per round: <b>{throws}</b>\n\n"
                 f"🤖 Bot is rolling first...",
            parse_mode='HTML'
        )
        
        await asyncio.sleep(1)
        bot_results = []
        for i in range(throws):
            bot_msg = await context.bot.send_dice(chat_id=chat_id, emoji=game_info['emoji'])
            bot_results.append(bot_msg.dice.value)
            await asyncio.sleep(0.3)
        
        game.bot_results.extend(bot_results)
        game.bot_rolled_this_round = True
        bot_total = sum(bot_results)
        
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🤖 <b>Bot's Round 1 total: {bot_total}</b>\n\n"
                 f"👤 Now it's your turn! Send {throws}x {game_info['emoji']}",
            parse_mode='HTML'
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{game_info['icon']} <b>Game Started!{double_tag}</b>\n\n"
                 f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                 f"🔄 Rounds: <b>{rounds}</b>\n"
                 f"🎯 Throws per round: <b>{throws}</b>\n\n"
                 f"👤 You roll first! Send {throws}x {game_info['emoji']}",
            parse_mode='HTML'
        )
