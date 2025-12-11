# database.py
# Data persistence and storage for the casino bot

import json
import os
from datetime import datetime
from collections import defaultdict
import asyncio

from config import DATA_FILE, ADMIN_ID, logger

# ==================== DATA STRUCTURES ====================

# Admin management
admin_list = {ADMIN_ID}

# User game sessions
user_games = {}

# User balances (defaultdict for automatic 0 balance)
user_balances = defaultdict(float)

# Game locks to prevent concurrent game issues
game_locks = defaultdict(asyncio.Lock)

# User withdrawal records
user_withdrawals = {}

# Withdrawal counter for unique IDs
withdrawal_counter = 26356

# User profiles with stats
user_profiles = {}

# User game history
user_game_history = defaultdict(list)

# Track users who have claimed bonus
user_bonus_claimed = set()

# Track last game settings for repeat/double feature
user_last_game_settings = {}

# Username to user_id mapping
username_to_id = {}

# Withdraw video file_id (set by admin via /video command)
withdraw_video_file_id = None


# ==================== DATA PERSISTENCE ====================

def save_data():
    """Save all data to JSON file."""
    global withdraw_video_file_id
    try:
        data = {
            'user_balances': dict(user_balances),
            'user_profiles': {},
            'user_game_history': {},
            'user_bonus_claimed': list(user_bonus_claimed),
            'user_withdrawals': user_withdrawals,
            'withdrawal_counter': withdrawal_counter,
            'admin_list': list(admin_list),
            'username_to_id': username_to_id,
            'user_last_game_settings': user_last_game_settings,
            'withdraw_video_file_id': withdraw_video_file_id
        }
        
        # Convert user_profiles with proper serialization
        for user_id, profile in user_profiles.items():
            profile_copy = dict(profile)
            if 'registration_date' in profile_copy:
                profile_copy['registration_date'] = profile_copy['registration_date'].isoformat()
            if 'game_counts' in profile_copy:
                profile_copy['game_counts'] = dict(profile_copy['game_counts'])
            data['user_profiles'][str(user_id)] = profile_copy
        
        # Convert user_game_history with proper serialization
        for user_id, history in user_game_history.items():
            serialized_history = []
            for game in history:
                game_copy = dict(game)
                if 'timestamp' in game_copy:
                    game_copy['timestamp'] = game_copy['timestamp'].isoformat()
                serialized_history.append(game_copy)
            data['user_game_history'][str(user_id)] = serialized_history
        
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Error saving data: {e}")


def load_data():
    """Load all data from JSON file."""
    global user_balances, user_profiles, user_game_history, user_bonus_claimed
    global user_withdrawals, withdrawal_counter, admin_list, username_to_id
    global user_last_game_settings, withdraw_video_file_id
    
    try:
        if not os.path.exists(DATA_FILE):
            logger.info("No data file found, starting fresh")
            return
        
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        # Load user balances
        user_balances.update({int(k): float(v) for k, v in data.get('user_balances', {}).items()})
        
        # Load user profiles
        for user_id_str, profile in data.get('user_profiles', {}).items():
            user_id = int(user_id_str)
            if 'registration_date' in profile:
                profile['registration_date'] = datetime.fromisoformat(profile['registration_date'])
            if 'game_counts' in profile:
                profile['game_counts'] = defaultdict(int, profile['game_counts'])
            user_profiles[user_id] = profile
        
        # Load user game history
        for user_id_str, history in data.get('user_game_history', {}).items():
            user_id = int(user_id_str)
            deserialized_history = []
            for game in history:
                if 'timestamp' in game:
                    game['timestamp'] = datetime.fromisoformat(game['timestamp'])
                deserialized_history.append(game)
            user_game_history[user_id] = deserialized_history
        
        # Load other data
        user_bonus_claimed.update(set(data.get('user_bonus_claimed', [])))
        user_withdrawals.update(data.get('user_withdrawals', {}))
        withdrawal_counter = data.get('withdrawal_counter', 26356)
        admin_list.update(set(data.get('admin_list', [ADMIN_ID])))
        username_to_id.update(data.get('username_to_id', {}))
        user_last_game_settings.update({int(k): v for k, v in data.get('user_last_game_settings', {}).items()})
        withdraw_video_file_id = data.get('withdraw_video_file_id', None)
        
        logger.info("Data loaded successfully")
    except Exception as e:
        logger.error(f"Error loading data: {e}")


def get_withdraw_video_file_id():
    """Get the current withdraw video file ID."""
    return withdraw_video_file_id


def set_withdraw_video_file_id(file_id):
    """Set the withdraw video file ID."""
    global withdraw_video_file_id
    withdraw_video_file_id = file_id
    save_data()


def get_withdrawal_counter():
    """Get the current withdrawal counter."""
    return withdrawal_counter


def increment_withdrawal_counter():
    """Increment and return the new withdrawal counter."""
    global withdrawal_counter
    withdrawal_counter += 1
    save_data()
    return withdrawal_counter
