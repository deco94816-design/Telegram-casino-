# config.py
# Configuration constants, tokens, and game definitions for the casino bot

import logging

# ==================== LOGGING CONFIGURATION ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== BOT CONFIGURATION ====================
BOT_TOKEN = "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y"
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

PROVIDER_TOKEN = ""
ADMIN_ID = 5709159932
BOT_USERNAME = "Iibrate"
DATA_FILE = "bot_data.json"

# ==================== ADMIN BALANCE ====================
ADMIN_BALANCE = 9999999999

# ==================== CURRENCY CONVERSION ====================
STARS_TO_USD = 0.0179
STARS_TO_TON = 0.01201014

# ==================== LIMITS ====================
MIN_WITHDRAWAL = 200
BONUS_AMOUNT = 20
INITIAL_WITHDRAWAL_COUNTER = 26356

# ==================== GAME TYPES CONFIGURATION ====================
GAME_TYPES = {
    'dice': {'emoji': '🎲', 'name': 'Dice', 'max_value': 6, 'icon': '🎲'},
    'bowl': {'emoji': '🎳', 'name': 'Bowling', 'max_value': 6, 'icon': '🎳'},
    'arrow': {'emoji': '🎯', 'name': 'Darts', 'max_value': 6, 'icon': '🎯'},
    'football': {'emoji': '⚽', 'name': 'Football', 'max_value': 5, 'icon': '🥅'},
    'basket': {'emoji': '🏀', 'name': 'Basketball', 'max_value': 5, 'icon': '🏀'}
}

# ==================== RANK SYSTEM ====================
RANKS = {
    1: {"name": "Newcomer", "xp_required": 0, "emoji": "🌱"},
    2: {"name": "Beginner", "xp_required": 100, "emoji": "🌿"},
    3: {"name": "Amateur", "xp_required": 300, "emoji": "🌾"},
    4: {"name": "Player", "xp_required": 600, "emoji": "⭐"},
    5: {"name": "Regular", "xp_required": 1000, "emoji": "🌟"},
    6: {"name": "Enthusiast", "xp_required": 1500, "emoji": "✨"},
    7: {"name": "Skilled", "xp_required": 2200, "emoji": "💫"},
    8: {"name": "Expert", "xp_required": 3000, "emoji": "🔥"},
    9: {"name": "Veteran", "xp_required": 4000, "emoji": "💎"},
    10: {"name": "Master", "xp_required": 5200, "emoji": "👑"},
    11: {"name": "Grand Master", "xp_required": 6500, "emoji": "🏆"},
    12: {"name": "Champion", "xp_required": 8000, "emoji": "🥇"},
    13: {"name": "Elite", "xp_required": 10000, "emoji": "💠"},
    14: {"name": "Pro", "xp_required": 12500, "emoji": "🎖"},
    15: {"name": "Star", "xp_required": 15500, "emoji": "⚡"},
    16: {"name": "Superstar", "xp_required": 19000, "emoji": "🌠"},
    17: {"name": "Legend", "xp_required": 23000, "emoji": "🔱"},
    18: {"name": "Mythic", "xp_required": 28000, "emoji": "🐉"},
    19: {"name": "Immortal", "xp_required": 35000, "emoji": "👼"},
    20: {"name": "God", "xp_required": 50000, "emoji": "🌌"}
}
