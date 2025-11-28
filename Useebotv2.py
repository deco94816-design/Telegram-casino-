import logging
import random
import string
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
from collections import defaultdict
import asyncio
import os

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Userbot Configuration
USERBOT_API_ID = os.environ.get("USERBOT_API_ID", "28782318")
USERBOT_API_HASH = os.environ.get("USERBOT_API_HASH", "ea72ed0d16604c27198d5dd1a53f2a69")
USERBOT_SESSION = os.environ.get("USERBOT_SESSION", "userbot_session")

PROVIDER_TOKEN = ""
ADMIN_ID = 5709159932

user_games = {}
user_balances = defaultdict(float)
game_locks = defaultdict(asyncio.Lock)
user_withdrawals = {}
withdrawal_counter = 26356

user_profiles = {}
user_game_history = defaultdict(list)

# Payment request tracking
pending_payment_requests = {}

STARS_TO_USD = 0.0179
STARS_TO_TON = 0.01201014

GAME_TYPES = {
    'dice': {'emoji': '🎲', 'name': 'Dice', 'max_value': 6, 'icon': '🎲'},
    'bowl': {'emoji': '🎳', 'name': 'Bowling', 'max_value': 6, 'icon': '🎳'},
    'arrow': {'emoji': '🎯', 'name': 'Darts', 'max_value': 6, 'icon': '🎯'},
    'football': {'emoji': '⚽', 'name': 'Football', 'max_value': 5, 'icon': '🥅'},
    'basket': {'emoji': '🏀', 'name': 'Basketball', 'max_value': 5, 'icon': '🏀'}
}

COMMAND_TO_GAME = {
    '/dice': 'dice',
    '/dart': 'arrow',
    '/bowl': 'bowl',
    '/football': 'football',
    '/basket': 'basket'
}

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

class Game:
    def __init__(self, user_id, username, bet_amount, rounds, throw_count, game_type, chat_id=None):
        self.user_id = user_id
        self.username = username
        self.bet_amount = bet_amount
        self.total_rounds = rounds
        self.throw_count = throw_count
        self.game_type = game_type
        self.current_round = 0
        self.user_score = 0
        self.bot_score = 0
        self.user_results = []
        self.bot_results = []
        self.is_demo = False
        self.chat_id = chat_id

def get_or_create_profile(user_id, username=None):
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
    return user_profiles[user_id]

def get_user_rank(xp):
    current_rank = 1
    for level, data in RANKS.items():
        if xp >= data['xp_required']:
            current_rank = level
        else:
            break
    return current_rank

def get_rank_info(level):
    return RANKS.get(level, RANKS[1])

def add_xp(user_id, amount):
    profile = get_or_create_profile(user_id)
    profile['xp'] += amount
    return profile['xp']

def update_game_stats(user_id, game_type, bet_amount, win_amount, won):
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
    
    max_count = 0
    fav_game = None
    for gt, count in profile['game_counts'].items():
        if count > max_count:
            max_count = count
            fav_game = gt
    profile['favorite_game'] = fav_game
    
    user_game_history[user_id].append({
        'game_type': game_type,
        'bet_amount': bet_amount,
        'win_amount': win_amount if won else 0,
        'won': won,
        'timestamp': datetime.now()
    })

def generate_transaction_id():
    chars = string.ascii_letters + string.digits
    return 'stx' + ''.join(random.choice(chars) for _ in range(80))

def generate_payment_request_id():
    chars = string.ascii_letters + string.digits
    return 'pr_' + ''.join(random.choice(chars) for _ in range(16))

def is_valid_ton_address(address):
    if not address:
        return False
    ton_pattern = r'^(UQ|EQ|kQ|0Q)[A-Za-z0-9_-]{46}$'
    if re.match(ton_pattern, address):
        return True
    raw_pattern = r'^-?[0-9]+:[a-fA-F0-9]{64}$'
    if re.match(raw_pattern, address):
        return True
    return len(address) >= 48 and len(address) <= 67

def create_progress_bar(current, total, length=10):
    if total == 0:
        filled = 0
    else:
        filled = int((current / total) * length)
    empty = length - filled
    return "▓" * filled + "░" * empty

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    get_or_create_profile(user_id, user.username or user.first_name)
    
    balance = user_balances[user_id]
    balance_usd = balance * STARS_TO_USD
    
    profile = user_profiles.get(user_id, {})
    turnover = profile.get('total_bets', 0.0) * STARS_TO_USD
    
    welcome_text = (
        f"🐱 <b>Welcome to lenarao Game</b>\n\n"
        f"⭐️ Lenrao Game is the best online mini-games on Telegram\n\n"
        f"📢 <b>How to start winning?</b>\n\n"
        f"1. Make sure you have a balance. You can top up using /deposit command.\n\n"
        f"2. Join one of our groups from the @lenrao catalog.\n\n"
        f"3. Type /dice, /dart, /bowl, /football, or /basket in the group to play!\n\n\n"
        f"💵 Balance: ${balance_usd:.2f}\n"
        f"👑 Game turnover: ${turnover:.2f}\n\n"
        f"🌐 <b>About us</b>\n"
        f"<a href='https://t.me/lenrao'>Channel</a> | <a href='https://t.me/lenraochat'>Chat</a> | <a href='https://t.me/lenraosupport'>Support</a>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Play", callback_data="show_games")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup, disable_web_page_preview=True)

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_or_create_profile(user_id, update.effective_user.username or update.effective_user.first_name)
    
    keyboard = [
        [
            InlineKeyboardButton("🎲 Dice", callback_data="play_game_dice"),
            InlineKeyboardButton("🎳 Bowling", callback_data="play_game_bowl"),
        ],
        [
            InlineKeyboardButton("🎯 Darts", callback_data="play_game_arrow"),
            InlineKeyboardButton("⚽ Football", callback_data="play_game_football"),
        ],
        [
            InlineKeyboardButton("🏀 Basketball", callback_data="play_game_basket"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "🎮 <b>Select a game to play:</b>\n\n"
        "🎲 <b>Dice</b> - Roll the dice and beat the bot!\n"
        "🎳 <b>Bowling</b> - Strike your way to victory!\n"
        "🎯 <b>Darts</b> - Aim for the bullseye!\n"
        "⚽ <b>Football</b> - Score goals and win!\n"
        "🏀 <b>Basketball</b> - Shoot hoops for stars!",
        reply_markup=reply_markup
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    profile = get_or_create_profile(user_id, user.username or user.first_name)
    balance = user_balances[user_id]
    balance_usd = balance * STARS_TO_USD
    
    rank_level = get_user_rank(profile['xp'])
    rank_info = get_rank_info(rank_level)
    
    if rank_level < 20:
        next_rank_info = get_rank_info(rank_level + 1)
        xp_progress = profile['xp'] - rank_info['xp_required']
        xp_needed = next_rank_info['xp_required'] - rank_info['xp_required']
        progress_bar = create_progress_bar(xp_progress, xp_needed)
        rank_display = f"{rank_info['emoji']} {rank_info['name']} (Lvl {rank_level})\n{progress_bar} {profile['xp']}/{next_rank_info['xp_required']} XP"
    else:
        rank_display = f"{rank_info['emoji']} {rank_info['name']} (MAX LEVEL)\n🌌 {profile['xp']} XP"
    
    fav_game = profile.get('favorite_game')
    if fav_game and fav_game in GAME_TYPES:
        fav_game_display = f"{GAME_TYPES[fav_game]['icon']} {GAME_TYPES[fav_game]['name']}"
    else:
        fav_game_display = "?"
    
    biggest_win = profile.get('biggest_win', 0)
    if biggest_win > 0:
        biggest_win_display = f"${biggest_win * STARS_TO_USD:.2f}"
    else:
        biggest_win_display = "?"
    
    reg_date = profile.get('registration_date', datetime.now())
    reg_date_str = reg_date.strftime("%Y-%m-%d %H:%M")
    
    total_bets_usd = profile.get('total_bets', 0) * STARS_TO_USD
    total_wins_usd = profile.get('total_wins', 0) * STARS_TO_USD
    
    profile_text = (
        f"📢 <b>Profile</b>\n\n"
        f"ℹ️ User ID: <code>{user_id}</code>\n"
        f"⬆️ Rank: {rank_display}\n"
        f"💵 Balance: ${balance_usd:.2f}\n\n"
        f"⚡️ Total games: {profile.get('total_games', 0)}\n"
        f"Total bets: ${total_bets_usd:.2f}\n"
        f"Total wins: ${total_wins_usd:.2f}\n\n"
        f"🎲 Favorite game: {fav_game_display}\n"
        f"🎉 Biggest win: {biggest_win_display}\n\n"
        f"🕒 Registration date: {reg_date_str}"
    )
    
    await update.message.reply_html(profile_text)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    profile = get_or_create_profile(user_id, user.username or user.first_name)
    history = user_game_history.get(user_id, [])
    
    total_games = profile.get('total_games', 0)
    total_bets = profile.get('total_bets', 0)
    total_wins = profile.get('total_wins', 0)
    total_losses = profile.get('total_losses', 0)
    games_won = profile.get('games_won', 0)
    games_lost = profile.get('games_lost', 0)
    
    total_wagered = total_bets
    net_profit = total_wins - total_losses
    
    total_bets_usd = total_bets * STARS_TO_USD
    total_wins_usd = total_wins * STARS_TO_USD
    total_losses_usd = total_losses * STARS_TO_USD
    total_wagered_usd = total_wagered * STARS_TO_USD
    net_profit_usd = net_profit * STARS_TO_USD
    
    if total_games > 0:
        win_rate = (games_won / total_games) * 100
    else:
        win_rate = 0
    
    history_text = (
        f"📊 <b>Game History</b>\n\n"
        f"🎮 <b>Total Games Played:</b> {total_games}\n"
        f"✅ Games Won: {games_won}\n"
        f"❌ Games Lost: {games_lost}\n"
        f"📈 Win Rate: {win_rate:.1f}%\n\n"
        f"💰 <b>Financial Summary:</b>\n"
        f"💵 Total Bets: ${total_bets_usd:.2f}\n"
        f"🏆 Total Wins: ${total_wins_usd:.2f}\n"
        f"📉 Total Losses: ${total_losses_usd:.2f}\n"
        f"🔄 Total Wagered: ${total_wagered_usd:.2f}\n"
        f"{'📈' if net_profit >= 0 else '📉'} Net Profit: ${net_profit_usd:.2f}\n"
    )
    
    if history:
        history_text += "\n📜 <b>Recent Games:</b>\n"
        recent_games = history[-5:]
        for game in reversed(recent_games):
            game_type = game['game_type']
            game_info = GAME_TYPES.get(game_type, {'icon': '🎮', 'name': 'Unknown'})
            status = "✅ Won" if game['won'] else "❌ Lost"
            bet_usd = game['bet_amount'] * STARS_TO_USD
            timestamp = game['timestamp'].strftime("%m/%d %H:%M")
            history_text += f"{game_info['icon']} {game_info['name']} - {status} (${bet_usd:.2f}) - {timestamp}\n"
    
    await update.message.reply_html(history_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎯 <b>How to Play:</b>\n\n"
        "1️⃣ Deposit Stars using /deposit in groups\n"
        "2️⃣ Use game commands: /dice, /dart, /bowl, /football, /basket\n"
        "3️⃣ Select bet amount\n"
        "4️⃣ Choose rounds (1-3)\n"
        "5️⃣ Choose throws (1-3)\n"
        "6️⃣ Send your emojis in the group!\n"
        "7️⃣ Bot responds instantly\n"
        "8️⃣ Higher total wins!\n\n"
        "🏆 Most rounds won = Winner!\n"
        "💎 Winner takes the pot!"
    )
    await update.message.reply_html(help_text)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = user_balances[user_id]
    balance_usd = balance * STARS_TO_USD
    await update.message.reply_html(
        f"💰 Your balance: <b>{balance} ⭐</b> (${balance_usd:.2f})"
    ) 
# ==================== PART 2: PAYMENT, WITHDRAWAL & CALLBACK HANDLERS ====================

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['withdraw_state'] = None
    context.user_data['withdraw_amount'] = None
    context.user_data['withdraw_address'] = None
    
    welcome_text = (
        "✨ <b>Welcome to Stars Withdrawal !</b>\n\n"
        "<b>Withdraw:</b>\n"
        "1 ⭐️ = $0.0179 = 0.01201014 TON\n\n"
        "<blockquote>⚙️ <b>Good to know:</b>\n"
        "• When you exchange stars through a channel or bot, Telegram keeps a 15% fee and applies a 21-day hold.\n"
        "• We send TON immediately—factoring in this fee and a small service premium.</blockquote>"
    )
    
    keyboard = [[InlineKeyboardButton("💎 Withdraw", callback_data="start_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    try:
        if data == "show_games":
            keyboard = [
                [
                    InlineKeyboardButton("🎲 Dice", callback_data="play_game_dice"),
                    InlineKeyboardButton("🎳 Bowling", callback_data="play_game_bowl"),
                ],
                [
                    InlineKeyboardButton("🎯 Darts", callback_data="play_game_arrow"),
                    InlineKeyboardButton("⚽ Football", callback_data="play_game_football"),
                ],
                [
                    InlineKeyboardButton("🏀 Basketball", callback_data="play_game_basket"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🎮 <b>Select a game to play:</b>\n\n"
                "🎲 <b>Dice</b> - Roll the dice and beat the bot!\n"
                "🎳 <b>Bowling</b> - Strike your way to victory!\n"
                "🎯 <b>Darts</b> - Aim for the bullseye!\n"
                "⚽ <b>Football</b> - Score goals and win!\n"
                "🏀 <b>Basketball</b> - Shoot hoops for stars!",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "start_withdraw":
            context.user_data['withdraw_state'] = 'waiting_amount'
            await query.edit_message_text(
                "💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                "Example: 100",
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "confirm_withdraw":
            global withdrawal_counter
            
            stars_amount = context.user_data.get('withdraw_amount', 0)
            ton_address = context.user_data.get('withdraw_address', '')
            
            balance = user_balances[user_id]
            if balance < stars_amount:
                await query.edit_message_text(
                    "❌ <b>Insufficient balance!</b>\n\n"
                    f"Your balance: {balance} ⭐\n"
                    f"Requested: {stars_amount} ⭐\n\n"
                    "Use /withdraw to try again.",
                    parse_mode=ParseMode.HTML
                )
                context.user_data['withdraw_state'] = None
                return
            
            user_balances[user_id] -= stars_amount
            withdrawal_counter += 1
            exchange_id = withdrawal_counter
            
            ton_amount = round(stars_amount * STARS_TO_TON, 8)
            transaction_id = generate_transaction_id()
            
            now = datetime.now()
            created_date = now.strftime("%Y-%m-%d %H:%M")
            hold_until = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
            
            user_withdrawals[user_id] = {
                'exchange_id': exchange_id,
                'stars': stars_amount,
                'ton_amount': ton_amount,
                'address': ton_address,
                'transaction_id': transaction_id,
                'created': created_date,
                'hold_until': hold_until,
                'status': 'on_hold'
            }
            
            receipt_text = (
                f"📄 <b>Stars withdraw exchange #{exchange_id}</b>\n\n"
                f"📊 Exchange status: Processing\n"
                f"⭐️ Stars withdrawal: {stars_amount}\n"
                f"💎 TON amount: {ton_amount}\n\n"
                f"<b>Sale:</b>\n"
                f"🏷 Top-up status: Paid\n"
                f"🗓 Created: {created_date}\n"
                f"🏦 TON address: <code>{ton_address}</code>\n"
                f"🧾 Transaction ID: <code>{transaction_id}</code>\n\n"
                f"💸 Withdrawal status: On hold\n"
                f"💎 TON amount: {ton_amount}\n"
                f"🗓 Withdrawal created: {created_date}\n"
                f"⏳ On hold until: {hold_until}\n"
                f"📝 Reason: Lenrao game rating is negative. Placed on 14-day hold."
            )
            
            await query.edit_message_text(receipt_text, parse_mode=ParseMode.HTML)
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            return
        
        if data == "cancel_withdraw":
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            await query.edit_message_text(
                "❌ <b>Withdrawal cancelled.</b>\n\n"
                "Use /withdraw to start again.",
                parse_mode=ParseMode.HTML
            )
            return
            
    except Exception as e:
        logger.error(f"Button callback error: {e}")
        await query.edit_message_text(
            "❌ An error occurred. Please try again.",
            parse_mode=ParseMode.HTML
        )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('withdraw_state') == 'waiting_amount':
        try:
            amount = int(text)
            balance = user_balances[user_id]
            
            if amount < 1:
                await update.message.reply_html("❌ Minimum withdrawal is 1 ⭐")
                return
            
            if amount > balance:
                await update.message.reply_html(
                    f"❌ Insufficient balance!\n\n"
                    f"Your balance: {balance} ⭐\n"
                    f"Requested: {amount} ⭐"
                )
                return
            
            context.user_data['withdraw_amount'] = amount
            context.user_data['withdraw_state'] = 'waiting_address'
            
            ton_amount = round(amount * STARS_TO_TON, 8)
            
            await update.message.reply_html(
                f"💎 <b>Withdrawal Amount:</b> {amount} ⭐\n"
                f"💰 <b>TON Amount:</b> {ton_amount}\n\n"
                f"📝 <b>Enter your TON wallet address:</b>"
            )
        except ValueError:
            await update.message.reply_html("❌ Please enter a valid number.")
        return
    
    if context.user_data.get('withdraw_state') == 'waiting_address':
        if not is_valid_ton_address(text):
            await update.message.reply_html(
                "❌ <b>Invalid TON address!</b>\n\n"
                "Please enter a valid TON wallet address."
            )
            return
        
        context.user_data['withdraw_address'] = text
        
        stars_amount = context.user_data.get('withdraw_amount', 0)
        ton_amount = round(stars_amount * STARS_TO_TON, 8)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"📋 <b>Withdrawal Summary:</b>\n\n"
            f"⭐️ Stars: {stars_amount}\n"
            f"💎 TON: {ton_amount}\n"
            f"🏦 Address: <code>{text}</code>\n\n"
            f"Confirm withdrawal?",
            reply_markup=reply_markup
        )
        return

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    
    amount = payment.total_amount
    user_balances[user_id] += amount
    
    # Check if this was from a userbot request
    payload = payment.invoice_payload
    request_id = None
    
    if payload.startswith("deposit_") and payload.count("_") >= 3:
        parts = payload.split("_")
        if len(parts) >= 4:
            request_id = parts[3]
    
    success_message = (
        f"✅ <b>Payment Successful!</b>\n\n"
        f"💰 Added: <b>{amount} ⭐</b>\n"
        f"💳 New balance: <b>{user_balances[user_id]} ⭐</b>"
    )
    
    await update.message.reply_html(success_message)
    
    # Notify userbot if this was a group payment request
    if request_id and request_id in pending_payment_requests:
        request_data = pending_payment_requests[request_id]
        request_data['payment_success'] = True
        request_data['new_balance'] = user_balances[user_id]
        
        # Clean up old request after 60 seconds
        async def cleanup():
            await asyncio.sleep(60)
            if request_id in pending_payment_requests:
                del pending_payment_requests[request_id]
        
        asyncio.create_task(cleanup())
    """Handle /profile command"""
    try:
        user = update.effective_user
        user_id = user.id
        
        profile = get_or_create_profile(user_id, user.username or user.first_name)
        if not profile:
            await update.message.reply_html("❌ Error loading profile.")
            return
            
        balance = user_balances[user_id]
        balance_usd = balance * STARS_TO_USD
        
        rank_level = get_user_rank(profile['xp'])
        rank_info = get_rank_info(rank_level)
        
        if rank_level < 20:
            next_rank_info = get_rank_info(rank_level + 1)
            xp_progress = profile['xp'] - rank_info['xp_required']
            xp_needed = next_rank_info['xp_required'] - rank_info['xp_required']
            progress_bar = create_progress_bar(xp_progress, xp_needed)
            rank_display = f"{rank_info['emoji']} {rank_info['name']} (Lvl {rank_level})\n{progress_bar} {profile['xp']}/{next_rank_info['xp_required']} XP"
        else:
            rank_display = f"{rank_info['emoji']} {rank_info['name']} (MAX LEVEL)\n🌌 {profile['xp']} XP"
        
        fav_game = profile.get('favorite_game')
        if fav_game and fav_game in GAME_TYPES:
            fav_game_display = f"{GAME_TYPES[fav_game]['icon']} {GAME_TYPES[fav_game]['name']}"
        else:
            fav_game_display = "None yet"
        
        biggest_win = profile.get('biggest_win', 0)
        biggest_win_display = f"${biggest_win * STARS_TO_USD:.2f}" if biggest_win > 0 else "$0.00"
        
        reg_date = profile.get('registration_date', datetime.now())
        reg_date_str = reg_date.strftime("%Y-%m-%d %H:%M")
        
        total_bets_usd = profile.get('total_bets', 0) * STARS_TO_USD
        total_wins_usd = profile.get('total_wins', 0) * STARS_TO_USD
        
        profile_text = (
            f"📢 <b>Profile</b>\n\n"
            f"ℹ️ User ID: <code>{user_id}</code>\n"
            f"⬆️ Rank: {rank_display}\n"
            f"💵 Balance: ${balance_usd:.2f}\n\n"
            f"⚡️ Total games: {profile.get('total_games', 0)}\n"
            f"Total bets: ${total_bets_usd:.2f}\n"
            f"Total wins: ${total_wins_usd:.2f}\n\n"
            f"🎲 Favorite game: {fav_game_display}\n"
            f"🎉 Biggest win: {biggest_win_display}\n\n"
            f"🕒 Registration date: {reg_date_str}"
        )
        
        await update.message.reply_html(profile_text)
        
    except Exception as e:
        logger.error(f"Error in profile command: {e}")
        await update.message.reply_html("❌ An error occurred. Please try again.")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command"""
    try:
        user = update.effective_user
        user_id = user.id
        
        profile = get_or_create_profile(user_id, user.username or user.first_name)
        if not profile:
            await update.message.reply_html("❌ Error loading history.")
            return
            
        history = user_game_history.get(user_id, [])
        
        total_games = profile.get('total_games', 0)
        total_bets = profile.get('total_bets', 0)
        total_wins = profile.get('total_wins', 0)
        total_losses = profile.get('total_losses', 0)
        games_won = profile.get('games_won', 0)
        games_lost = profile.get('games_lost', 0)
        
        net_profit = total_wins - total_losses
        
        total_bets_usd = total_bets * STARS_TO_USD
        total_wins_usd = total_wins * STARS_TO_USD
        total_losses_usd = total_losses * STARS_TO_USD
        net_profit_usd = net_profit * STARS_TO_USD
        
        win_rate = (games_won / total_games) * 100 if total_games > 0 else 0
        
        history_text = (
            f"📊 <b>Game History</b>\n\n"
            f"🎮 <b>Total Games Played:</b> {total_games}\n"
            f"✅ Games Won: {games_won}\n"
            f"❌ Games Lost: {games_lost}\n"
            f"📈 Win Rate: {win_rate:.1f}%\n\n"
            f"💰 <b>Financial Summary:</b>\n"
            f"💵 Total Bets: ${total_bets_usd:.2f}\n"
            f"🏆 Total Wins: ${total_wins_usd:.2f}\n"
            f"📉 Total Losses: ${total_losses_usd:.2f}\n"
            f"{'📈' if net_profit >= 0 else '📉'} Net Profit: ${net_profit_usd:.2f}\n"
        )
        
        if history:
            history_text += "\n📜 <b>Recent Games:</b>\n"
            recent_games = history[-5:]
            for game in reversed(recent_games):
                game_type = game['game_type']
                game_info = GAME_TYPES.get(game_type, {'icon': '🎮', 'name': 'Unknown'})
                status = "✅ Won" if game['won'] else "❌ Lost"
                bet_usd = game['bet_amount'] * STARS_TO_USD
                timestamp = game['timestamp'].strftime("%m/%d %H:%M")
                history_text += f"{game_info['icon']} {game_info['name']} - {status} (${bet_usd:.2f}) - {timestamp}\n"
        
        await update.message.reply_html(history_text)
        
    except Exception as e:
        logger.error(f"Error in history command: {e}")
        await update.message.reply_html("❌ An error occurred. Please try again.")

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /withdraw command"""
    try:
        user_id = update.effective_user.id
        context.user_data['withdraw_state'] = None
        context.user_data['withdraw_amount'] = None
        context.user_data['withdraw_address'] = None
        
        welcome_text = (
            "✨ <b>Welcome to Stars Withdrawal!</b>\n\n"
            "<b>Withdraw:</b>\n"
            "1 ⭐️ = $0.0179 = 0.01201014 TON\n\n"
            "<blockquote>⚙️ <b>Good to know:</b>\n"
            "• When you exchange stars through a channel or bot, Telegram keeps a 15% fee and applies a 21-day hold.\n"
            "• We send TON immediately—factoring in this fee and a small service premium.</blockquote>"
        )
        
        keyboard = [[InlineKeyboardButton("💎 Withdraw", callback_data="start_withdraw")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(welcome_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in withdraw command: {e}")
        await update.message.reply_html("❌ An error occurred. Please try again.")

async def handle_payment_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment request from userbot"""
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if not data.startswith("pay_"):
            return
        
        parts = data.split("_")
        if len(parts) < 4:
            await query.edit_message_text("❌ Invalid payment request.")
            return
        
        request_id = parts[1]
        user_id = int(parts[2])
        amount = int(parts[3])
        
        if request_id not in pending_payment_requests:
            await query.edit_message_text("❌ Payment request expired or invalid.")
            return
        
        request_data = pending_payment_requests[request_id]
        
        # Send invoice
        title = f"Deposit {amount} Stars"
        description = f"Add {amount} ⭐ to your game balance"
        payload = f"deposit_{amount}_{user_id}_{request_id}"
        prices = [LabeledPrice("Stars", amount)]
        
        await query.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency="XTR",
            prices=prices
        )
        
        await query.edit_message_text(
            f"💳 <b>Payment Invoice Sent!</b>\n\n"
            f"Amount: {amount} ⭐\n"
            f"Please complete the payment to add Stars to your balance.",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in handle_payment_request: {e}")
        try:
            await query.edit_message_text("❌ An error occurred processing payment.")
        except:
            pass

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout query"""
    try:
        query = update.pre_checkout_query
        await query.answer(ok=True)
    except Exception as e:
        logger.error(f"Error in precheckout callback: {e}")
        try:
            await query.answer(ok=False, error_message="Payment processing error")
        except:
            pass

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment"""
    try:
        user_id = update.effective_user.id
        payment = update.message.successful_payment
        
        amount = payment.total_amount
        user_balances[user_id] += amount
        
        # Check if this was from a userbot request
        payload = payment.invoice_payload
        request_id = None
        
        if payload.startswith("deposit_") and payload.count("_") >= 3:
            parts = payload.split("_")
            if len(parts) >= 4:
                request_id = parts[3]
        
        success_message = (
            f"✅ <b>Payment Successful!</b>\n\n"
            f"💰 Added: <b>{amount} ⭐</b>\n"
            f"💳 New balance: <b>{user_balances[user_id]} ⭐</b>"
        )
        
        await update.message.reply_html(success_message)
        
        # Notify userbot if this was a group payment request
        if request_id and request_id in pending_payment_requests:
            request_data = pending_payment_requests[request_id]
            chat_id = request_data.get('chat_id')
            original_message_id = request_data.get('message_id')
            
            # Store success for userbot to check
            request_data['payment_success'] = True
            request_data['new_balance'] = user_balances[user_id]
            
            # Clean up old request after 60 seconds
            async def cleanup():
                await asyncio.sleep(60)
                if request_id in pending_payment_requests:
                    del pending_payment_requests[request_id]
            
            asyncio.create_task(cleanup())
        
    except Exception as e:
        logger.error(f"Error in successful payment: {e}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for withdrawal flow"""
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if context.user_data.get('withdraw_state') == 'waiting_amount':
            try:
                amount = int(text)
                balance = user_balances[user_id]
                
                if amount < 1:
                    await update.message.reply_html("❌ Minimum withdrawal is 1 ⭐")
                    return
                
                if amount > balance:
                    await update.message.reply_html(
                        f"❌ Insufficient balance!\n\n"
                        f"Your balance: {balance} ⭐\n"
                        f"Requested: {amount} ⭐"
                    )
                    return
                
                context.user_data['withdraw_amount'] = amount
                context.user_data['withdraw_state'] = 'waiting_address'
                
                ton_amount = round(amount * STARS_TO_TON, 8)
                
                await update.message.reply_html(
                    f"💎 <b>Withdrawal Amount:</b> {amount} ⭐\n"
                    f"💰 <b>TON Amount:</b> {ton_amount}\n\n"
                    f"📝 <b>Enter your TON wallet address:</b>"
                )
            except ValueError:
                await update.message.reply_html("❌ Please enter a valid number.")
            return
        
        if context.user_data.get('withdraw_state') == 'waiting_address':
            if not is_valid_ton_address(text):
                await update.message.reply_html(
                    "❌ <b>Invalid TON address!</b>\n\n"
                    "Please enter a valid TON wallet address."
                )
                return
            
            context.user_data['withdraw_address'] = text
            
            stars_amount = context.user_data.get('withdraw_amount', 0)
            ton_amount = round(stars_amount * STARS_TO_TON, 8)
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_html(
                f"📋 <b>Withdrawal Summary:</b>\n\n"
                f"⭐️ Stars: {stars_amount}\n"
                f"💎 TON: {ton_amount}\n"
                f"🏦 Address: <code>{text}</code>\n\n"
                f"Confirm withdrawal?",
                reply_markup=reply_markup
            )
            return
            
    except Exception as e:
        logger.error(f"Error in handle_text_message: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        # Payment request handling
        if data.startswith("pay_"):
            await handle_payment_request(update, context)
            return
        
        # Withdrawal flow
        if data == "start_withdraw":
            context.user_data['withdraw_state'] = 'waiting_amount'
            await query.edit_message_text(
                "💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                "Example: 100",
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "confirm_withdraw":
            global withdrawal_counter
            
            stars_amount = context.user_data.get('withdraw_amount', 0)
            ton_address = context.user_data.get('withdraw_address', '')
            
            balance = user_balances[user_id]
            if balance < stars_amount:
                await query.edit_message_text(
                    "❌ <b>Insufficient balance!</b>\n\n"
                    f"Your balance: {balance} ⭐\n"
                    f"Requested: {stars_amount} ⭐\n\n"
                    "Use /withdraw to try again.",
                    parse_mode=ParseMode.HTML
                )
                context.user_data['withdraw_state'] = None
                return
            
            user_balances[user_id] -= stars_amount
            withdrawal_counter += 1
            exchange_id = withdrawal_counter
            
            ton_amount = round(stars_amount * STARS_TO_TON, 8)
            transaction_id = generate_transaction_id()
            
            now = datetime.now()
            created_date = now.strftime("%Y-%m-%d %H:%M")
            hold_until = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
            
            user_withdrawals[user_id] = {
                'exchange_id': exchange_id,
                'stars': stars_amount,
                'ton_amount': ton_amount,
                'address': ton_address,
                'transaction_id': transaction_id,
                'created': created_date,
                'hold_until': hold_until,
                'status': 'on_hold'
            }
            
            receipt_text = (
                f"📄 <b>Stars withdraw exchange #{exchange_id}</b>\n\n"
                f"📊 Exchange status: Processing\n"
                f"⭐️ Stars withdrawal: {stars_amount}\n"
                f"💎 TON amount: {ton_amount}\n\n"
                f"<b>Sale:</b>\n"
                f"🏷 Top-up status: Paid\n"
                f"🗓 Created: {created_date}\n"
                f"🏦 TON address: <code>{ton_address}</code>\n"
                f"🧾 Transaction ID: <code>{transaction_id}</code>\n\n"
                f"💸 Withdrawal status: On hold\n"
                f"💎 TON amount: {ton_amount}\n"
                f"🗓 Withdrawal created: {created_date}\n"
                f"⏳ On hold until: {hold_until}\n"
                f"📝 Reason: Lenrao game rating is negative. Placed on 14-day hold."
            )
            
            await query.edit_message_text(receipt_text, parse_mode=ParseMode.HTML)
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            return
        
        if data == "cancel_withdraw":
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            await query.edit_message_text(
                "❌ <b>Withdrawal cancelled.</b>\n\n"
                "Use /withdraw to start again.",
                parse_mode=ParseMode.HTML
            )
            return
            
    except Exception as e:
        logger.error(f"Error in button callback: {e}")
        try:
            await query.edit_message_text("❌ An error occurred. Please try again.", parse_mode=ParseMode.HTML)
        except:
            pass
# ==================== PART 3: USERBOT & MAIN FUNCTION ====================

async def setup_userbot(bot_username):
    """Setup and start userbot for group gameplay"""
    if not USERBOT_API_ID or not USERBOT_API_HASH:
        logger.warning("⚠️ Userbot credentials not provided.")
        return None
    
    try:
        from telethon import TelegramClient, events, Button
        
        userbot = TelegramClient(USERBOT_SESSION, int(USERBOT_API_ID), USERBOT_API_HASH)
        userbot.bot_username = bot_username
        
        @userbot.on(events.NewMessage(pattern=r'^/deposit$'))
        async def handle_deposit_command(event):
            try:
                if not event.is_group:
                    return
                
                user_id = event.sender_id
                chat_id = event.chat_id
                
                request_id = generate_payment_request_id()
                
                pending_payment_requests[request_id] = {
                    'user_id': user_id,
                    'chat_id': chat_id,
                    'message_id': event.id,
                    'timestamp': datetime.now()
                }
                
                balance = user_balances[user_id]
                balance_usd = balance * STARS_TO_USD
                
                keyboard = [
                    [
                        Button.inline("10 ⭐", f"udeposit_{request_id}_10"),
                        Button.inline("25 ⭐", f"udeposit_{request_id}_25"),
                    ],
                    [
                        Button.inline("50 ⭐", f"udeposit_{request_id}_50"),
                        Button.inline("100 ⭐", f"udeposit_{request_id}_100"),
                    ],
                    [
                        Button.inline("250 ⭐", f"udeposit_{request_id}_250"),
                        Button.inline("500 ⭐", f"udeposit_{request_id}_500"),
                    ]
                ]
                
                deposit_text = (
                    f"💳 <b>Deposit Stars</b>\n\n"
                    f"💰 Current Balance: <b>{balance} ⭐</b> (${balance_usd:.2f})\n\n"
                    f"Select amount to deposit:"
                )
                
                await event.respond(deposit_text, buttons=keyboard, parse_mode='html', reply_to=event.id)
                logger.info(f"Deposit request created: {request_id}")
                
            except Exception as e:
                logger.error(f"Error handling deposit: {e}")
        
        @userbot.on(events.CallbackQuery(pattern=r'^udeposit_'))
        async def handle_deposit_callback(event):
            try:
                data = event.data.decode('utf-8')
                parts = data.split("_")
                
                if len(parts) < 3:
                    await event.answer("❌ Invalid request")
                    return
                
                request_id = parts[1]
                amount = int(parts[2])
                
                if request_id not in pending_payment_requests:
                    await event.answer("❌ Request expired", alert=True)
                    return
                
                request_data = pending_payment_requests[request_id]
                user_id = request_data['user_id']
                
                if event.sender_id != user_id:
                    await event.answer("❌ Not your request", alert=True)
                    return
                
                await event.answer()
                
                await event.edit(
                    f"💳 <b>Processing...</b>\n\nAmount: {amount} ⭐",
                    parse_mode='html'
                )
                
                payment_keyboard = [[
                    Button.url("💳 Pay Now", f"https://t.me/{userbot.bot_username}?start=pay_{request_id}_{user_id}_{amount}")
                ]]
                
                payment_text = (
                    f"💰 <b>Payment Request</b>\n\n"
                    f"Amount: <b>{amount} ⭐</b>\n\n"
                    f"Click button to pay:"
                )
                
                await userbot.send_message(userbot.bot_username, payment_text, buttons=payment_keyboard, parse_mode='html')
                await asyncio.sleep(1)
                
                await userbot.send_message(request_data['chat_id'], payment_text, buttons=payment_keyboard, parse_mode='html')
                
                await event.edit(f"✅ <b>Payment link sent!</b>\n\nAmount: {amount} ⭐", parse_mode='html')
                
                logger.info(f"Payment forwarded: {amount} stars")
                
                async def check_payment():
                    for _ in range(60):
                        await asyncio.sleep(1)
                        if request_data.get('payment_success'):
                            new_balance = request_data.get('new_balance', user_balances[user_id])
                            await userbot.send_message(
                                request_data['chat_id'],
                                f"✅ <b>Payment Successful!</b>\n\nAmount: {amount} ⭐\nNew Balance: {new_balance} ⭐",
                                parse_mode='html'
                            )
                            break
                
                asyncio.create_task(check_payment())
                
            except Exception as e:
                logger.error(f"Error in deposit callback: {e}")
        
        @userbot.on(events.NewMessage(pattern=r'^/(dice|dart|bowl|football|basket)$'))
        async def handle_game_command(event):
            try:
                if not event.is_group:
                    return
                
                user_id = event.sender_id
                chat_id = event.chat_id
                username = (event.sender.username or event.sender.first_name or "Player")
                
                if user_id in user_games:
                    await event.respond("❌ You already have an active game!", reply_to=event.id)
                    return
                
                command = event.raw_text.lower()
                game_type = COMMAND_TO_GAME.get(command)
                
                if not game_type:
                    return
                
                get_or_create_profile(user_id, username)
                balance = user_balances[user_id]
                
                if balance < 1:
                    await event.respond(
                        f"❌ Insufficient balance! Use /deposit\nBalance: <b>{balance} ⭐</b>",
                        reply_to=event.id, parse_mode='html'
                    )
                    return
                
                game_info = GAME_TYPES[game_type]
                
                keyboard = [
                    [Button.inline("10 ⭐", f"bet_{game_type}_10"), Button.inline("25 ⭐", f"bet_{game_type}_25")],
                    [Button.inline("50 ⭐", f"bet_{game_type}_50"), Button.inline("100 ⭐", f"bet_{game_type}_100")],
                    [Button.inline("❌ Cancel", "cancel_game")]
                ]
                
                msg = await event.respond(
                    f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                    f"💰 Choose bet:\nBalance: <b>{balance} ⭐</b>",
                    buttons=keyboard, reply_to=event.id, parse_mode='html'
                )
                
                if not hasattr(userbot, 'game_contexts'):
                    userbot.game_contexts = {}
                
                userbot.game_contexts[user_id] = {
                    'chat_id': chat_id, 'game_type': game_type,
                    'message_id': msg.id, 'username': username
                }
                
                logger.info(f"Game initiated: {game_type} by {user_id}")
                
            except Exception as e:
                logger.error(f"Error in game command: {e}")
        
        @userbot.on(events.CallbackQuery)
        async def handle_game_callback(event):
            try:
                data = event.data.decode('utf-8')
                user_id = event.sender_id
                
                if not hasattr(userbot, 'game_contexts'):
                    userbot.game_contexts = {}
                
                context = userbot.game_contexts.get(user_id, {})
                
                if data == "cancel_game":
                    if user_id in user_games:
                        del user_games[user_id]
                    if user_id in userbot.game_contexts:
                        del userbot.game_contexts[user_id]
                    await event.edit("❌ Game cancelled.", parse_mode='html')
                    return
                
                if data.startswith("bet_"):
                    parts = data.split("_")
                    game_type = parts[1]
                    bet_amount = int(parts[2])
                    
                    if user_balances[user_id] < bet_amount:
                        await event.answer("❌ Insufficient balance!", alert=True)
                        return
                    
                    await event.answer()
                    context['bet_amount'] = bet_amount
                    context['game_type'] = game_type
                    
                    game_info = GAME_TYPES[game_type]
                    keyboard = [
                        [Button.inline("1 Round", f"rounds_{game_type}_1"), Button.inline("2 Rounds", f"rounds_{game_type}_2")],
                        [Button.inline("3 Rounds", f"rounds_{game_type}_3")],
                        [Button.inline("◀️ Back", f"back_bet_{game_type}")]
                    ]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>Select rounds:</b>\nBet: <b>{bet_amount} ⭐</b>",
                        buttons=keyboard, parse_mode='html'
                    )
                    return
                
                if data.startswith("rounds_"):
                    parts = data.split("_")
                    game_type = parts[1]
                    rounds = int(parts[2])
                    
                    await event.answer()
                    context['rounds'] = rounds
                    
                    game_info = GAME_TYPES[game_type]
                    keyboard = [
                        [Button.inline("1 Throw", f"throws_{game_type}_1"), Button.inline("2 Throws", f"throws_{game_type}_2")],
                        [Button.inline("3 Throws", f"throws_{game_type}_3")],
                        [Button.inline("◀️ Back", f"bet_{game_type}_{context.get('bet_amount', 10)}")]
                    ]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>Select throws:</b>\nRounds: <b>{rounds}</b>",
                        buttons=keyboard, parse_mode='html'
                    )
                    return
                
                if data.startswith("throws_"):
                    parts = data.split("_")
                    game_type = parts[1]
                    throws = int(parts[2])
                    
                    bet_amount = context.get('bet_amount', 10)
                    rounds = context.get('rounds', 1)
                    username = context.get('username', 'Player')
                    chat_id = context.get('chat_id')
                    
                    if user_balances[user_id] < bet_amount:
                        await event.answer("❌ Insufficient balance!", alert=True)
                        return
                    
                    user_balances[user_id] -= bet_amount
                    
                    game = Game(user_id, username, bet_amount, rounds, throws, game_type, chat_id)
                    user_games[user_id] = game
                    
                    game_info = GAME_TYPES[game_type]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>Game Started!</b>\n\n"
                        f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                        f"🔄 Rounds: <b>{rounds}</b>\n"
                        f"🎯 Throws: <b>{throws}</b>\n\n"
                        f"Send {throws}x {game_info['emoji']} to play!",
                        parse_mode='html'
                    )
                    
                    logger.info(f"Game started: {game_type}")
                    return
                
                if data.startswith("back_bet_"):
                    game_type = data.split("_")[2]
                    balance = user_balances[user_id]
                    game_info = GAME_TYPES[game_type]
                    
                    keyboard = [
                        [Button.inline("10 ⭐", f"bet_{game_type}_10"), Button.inline("25 ⭐", f"bet_{game_type}_25")],
                        [Button.inline("50 ⭐", f"bet_{game_type}_50"), Button.inline("100 ⭐", f"bet_{game_type}_100")],
                        [Button.inline("❌ Cancel", "cancel_game")]
                    ]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>{game_info['name']}</b>\n\nBalance: <b>{balance} ⭐</b>",
                        buttons=keyboard, parse_mode='html'
                    )
                    return
                
            except Exception as e:
                logger.error(f"Error in game callback: {e}")
        
        @userbot.on(events.NewMessage)
        async def handle_game_dice(event):
            try:
                user_id = event.sender_id
                
                if user_id not in user_games or not event.dice:
                    return
                
                game = user_games[user_id]
                game_info = GAME_TYPES[game.game_type]
                
                if event.dice.emoticon != game_info['emoji']:
                    return
                
                game.user_results.append(event.dice.value)
                
                if len(game.user_results) % game.throw_count == 0:
                    await asyncio.sleep(0.5)
                    
                    bot_results = []
                    for _ in range(game.throw_count):
                        await userbot.send_message(game.chat_id, file=event.dice)
                        bot_results.append(random.randint(1, game_info['max_value']))
                        await asyncio.sleep(0.3)
                    
                    game.bot_results.extend(bot_results)
                    
                    round_start = game.current_round * game.throw_count
                    user_total = sum(game.user_results[round_start:round_start + game.throw_count])
                    bot_total = sum(bot_results)
                    
                    game.current_round += 1
                    
                    if user_total > bot_total:
                        game.user_score += 1
                        result = "✅ You won this round!"
                    elif bot_total > user_total:
                        game.bot_score += 1
                        result = "❌ Bot won this round!"
                    else:
                        result = "🤝 Tie!"
                    
                    await asyncio.sleep(2)
                    
                    if game.current_round < game.total_rounds:
                        await userbot.send_message(
                            game.chat_id,
                            f"<b>Round {game.current_round} Results:</b>\n\n"
                            f"👤 You: <b>{user_total}</b>\n🤖 Bot: <b>{bot_total}</b>\n\n{result}\n\n"
                            f"📊 Score: <b>{game.user_score}</b> - <b>{game.bot_score}</b>\n\n"
                            f"Send {game.throw_count}x {game_info['emoji']} for Round {game.current_round + 1}!",
                            parse_mode='html'
                        )
                    else:
                        if game.user_score > game.bot_score:
                            winnings = game.bet_amount * 2
                            user_balances[user_id] += winnings
                            update_game_stats(user_id, game.game_type, game.bet_amount, winnings, True)
                            final_result = f"🎉 <b>YOU WON!</b> 🎉\n\n💰 Winnings: <b>{winnings} ⭐</b>"
                        elif game.bot_score > game.user_score:
                            update_game_stats(user_id, game.game_type, game.bet_amount, 0, False)
                            final_result = f"😔 <b>You lost!</b>\n\n💸 Lost: <b>{game.bet_amount} ⭐</b>"
                        else:
                            user_balances[user_id] += game.bet_amount
                            final_result = f"🤝 <b>Tie!</b>\n\n💰 Returned: <b>{game.bet_amount} ⭐</b>"
                        
                        await userbot.send_message(
                            game.chat_id,
                            f"<b>Final Results:</b>\n\n👤 You: <b>{user_total}</b>\n🤖 Bot: <b>{bot_total}</b>\n\n"
                            f"📊 Final Score: <b>{game.user_score}</b> - <b>{game.bot_score}</b>\n\n"
                            f"{final_result}\n\n💰 Balance: <b>{user_balances[user_id]} ⭐</b>",
                            parse_mode='html'
                        )
                        
                        del user_games[user_id]
                        if hasattr(userbot, 'game_contexts') and user_id in userbot.game_contexts:
                            del userbot.game_contexts[user_id]
                
            except Exception as e:
                logger.error(f"Error handling dice: {e}")
        
        await userbot.start()
        logger.info("✅ Userbot started!")
        return userbot
        
    except Exception as e:
        logger.error(f"❌ Userbot setup failed: {e}")
        return None

def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("profile", profile_command))
        application.add_handler(CommandHandler("history", history_command))
        application.add_handler(CommandHandler("withdraw", withdraw_command))
        application.add_handler(CommandHandler("play", play_command))
        
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        
        logger.info("🤖 Bot starting...")
        
        async def post_init(app):
            try:
                bot_info = await app.bot.get_me()
                bot_username = bot_info.username
                logger.info(f"✅ Bot: @{bot_username}")
                
                userbot = await setup_userbot(bot_username)
                if userbot:
                    app.bot_data['userbot'] = userbot
                    logger.info("✅ System ready!")
                else:
                    logger.warning("⚠️ Userbot not available")
            except Exception as e:
                logger.error(f"Error in post_init: {e}")
        
        application.post_init = post_init
        
        logger.info("🚀 Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
    """Setup and start userbot for group gameplay"""
    if not USERBOT_API_ID or not USERBOT_API_HASH:
        logger.warning("⚠️ Userbot credentials not provided. Group gameplay will not be available.")
        logger.info("To enable group gameplay, set USERBOT_API_ID and USERBOT_API_HASH environment variables")
        return None
    
    try:
        from telethon import TelegramClient, events, Button
        from telethon.tl.custom import Message
        
        # Create userbot client
        userbot = TelegramClient(USERBOT_SESSION, int(USERBOT_API_ID), USERBOT_API_HASH)
        
        # Store bot reference
        userbot.bot_username = bot_username
        
        @userbot.on(events.NewMessage(pattern=r'^/deposit$'))
        async def handle_deposit_command(event):
            """Handle /deposit command in groups"""
            try:
                if not event.is_group:
                    return
                
                user_id = event.sender_id
                chat_id = event.chat_id
                
                # Create payment request
                request_id = generate_payment_request_id()
                
                # Store request data
                pending_payment_requests[request_id] = {
                    'user_id': user_id,
                    'chat_id': chat_id,
                    'message_id': event.id,
                    'timestamp': datetime.now()
                }
                
                # Get current balance
                balance = user_balances[user_id]
                balance_usd = balance * STARS_TO_USD
                
                # Create inline menu
                keyboard = [
                    [
                        Button.inline("10 ⭐", f"udeposit_{request_id}_10"),
                        Button.inline("25 ⭐", f"udeposit_{request_id}_25"),
                    ],
                    [
                        Button.inline("50 ⭐", f"udeposit_{request_id}_50"),
                        Button.inline("100 ⭐", f"udeposit_{request_id}_100"),
                    ],
                    [
                        Button.inline("250 ⭐", f"udeposit_{request_id}_250"),
                        Button.inline("500 ⭐", f"udeposit_{request_id}_500"),
                    ]
                ]
                
                deposit_text = (
                    f"💳 <b>Deposit Stars</b>\n\n"
                    f"💰 Current Balance: <b>{balance} ⭐</b> (${balance_usd:.2f})\n\n"
                    f"Select amount to deposit:"
                )
                
                await event.respond(
                    deposit_text,
                    buttons=keyboard,
                    parse_mode='html',
                    reply_to=event.id
                )
                
                logger.info(f"Deposit request created: {request_id} for user {user_id} in chat {chat_id}")
                
            except Exception as e:
                logger.error(f"Error handling deposit command: {e}")
                await event.respond("❌ An error occurred. Please try again.")
        
        @userbot.on(events.CallbackQuery(pattern=r'^udeposit_'))
        async def handle_deposit_callback(event):
            """Handle deposit amount selection"""
            try:
                data = event.data.decode('utf-8')
                parts = data.split("_")
                
                if len(parts) < 3:
                    await event.answer("❌ Invalid request")
                    return
                
                request_id = parts[1]
                amount = int(parts[2])
                
                if request_id not in pending_payment_requests:
                    await event.answer("❌ Request expired", alert=True)
                    return
                
                request_data = pending_payment_requests[request_id]
                user_id = request_data['user_id']
                
                # Only the requester can click
                if event.sender_id != user_id:
                    await event.answer("❌ This is not your request", alert=True)
                    return
                
                await event.answer()
                
                # Update message to show processing
                await event.edit(
                    f"💳 <b>Processing payment request...</b>\n\n"
                    f"Amount: {amount} ⭐\n"
                    f"Please wait...",
                    parse_mode='html'
                )
                
                # Create payment button for bot
                payment_keyboard = [[
                    Button.url(
                        "💳 Pay Now",
                        f"https://t.me/{userbot.bot_username}?start=pay_{request_id}_{user_id}_{amount}"
                    )
                ]]
                
                # Send payment request notification
                payment_text = (
                    f"💰 <b>Payment Request</b>\n\n"
                    f"Amount: <b>{amount} ⭐</b>\n"
                    f"User ID: <code>{user_id}</code>\n\n"
                    f"Click the button below to complete payment:"
                )
                
                # Send to bot privately and get the message
                bot_message = await userbot.send_message(
                    userbot.bot_username,
                    payment_text,
                    buttons=payment_keyboard,
                    parse_mode='html'
                )
                
                # Wait a bit for payment processing
                await asyncio.sleep(2)
                
                # Forward payment message to group (without reply tag)
                forwarded_msg = await userbot.send_message(
                    request_data['chat_id'],
                    payment_text,
                    buttons=payment_keyboard,
                    parse_mode='html'
                )
                
                # Update the original deposit message
                await event.edit(
                    f"✅ <b>Payment link sent!</b>\n\n"
                    f"Amount: {amount} ⭐\n"
                    f"Click the 'Pay Now' button above to complete your deposit.",
                    parse_mode='html'
                )
                
                logger.info(f"Payment request forwarded for {amount} stars to user {user_id}")
                
                # Monitor payment completion
                async def check_payment():
                    for _ in range(60):  # Check for 60 seconds
                        await asyncio.sleep(1)
                        if request_data.get('payment_success'):
                            new_balance = request_data.get('new_balance', user_balances[user_id])
                            await userbot.send_message(
                                request_data['chat_id'],
                                f"✅ <b>Payment Successful!</b>\n\n"
                                f"User: {user_id}\n"
                                f"Amount: {amount} ⭐\n"
                                f"New Balance: {new_balance} ⭐",
                                parse_mode='html'
                            )
                            break
                
                asyncio.create_task(check_payment())
                
            except Exception as e:
                logger.error(f"Error in deposit callback: {e}")
                try:
                    await event.answer("❌ Error processing request", alert=True)
                except:
                    pass
        
        @userbot.on(events.NewMessage(pattern=r'^/(dice|dart|bowl|football|basket)$'))
        async def handle_game_command(event):
            """Handle game commands in groups"""
            try:
                if not event.is_group:
                    return
                
                user_id = event.sender_id
                chat_id = event.chat_id
                username = event.sender.username or event.sender.first_name or "Player"
                
                # Check if user already has active game
                if user_id in user_games:
                    await event.respond(
                        "❌ You already have an active game! Finish it first.",
                        reply_to=event.id
                    )
                    return
                
                command = event.raw_text.lower()
                game_type = COMMAND_TO_GAME.get(command)
                
                if not game_type:
                    return
                
                # Get or create profile
                get_or_create_profile(user_id, username)
                
                balance = user_balances[user_id]
                
                if balance < 1:
                    await event.respond(
                        "❌ Insufficient balance! Use /deposit to add Stars.\n"
                        f"Your balance: <b>{balance} ⭐</b>",
                        reply_to=event.id,
                        parse_mode='html'
                    )
                    return
                
                game_info = GAME_TYPES[game_type]
                
                # Create bet selection keyboard
                keyboard = [
                    [
                        Button.inline("10 ⭐", f"bet_{game_type}_10"),
                        Button.inline("25 ⭐", f"bet_{game_type}_25"),
                    ],
                    [
                        Button.inline("50 ⭐", f"bet_{game_type}_50"),
                        Button.inline("100 ⭐", f"bet_{game_type}_100"),
                    ],
                    [
                        Button.inline("❌ Cancel", "cancel_game"),
                    ]
                ]
                
                msg = await event.respond(
                    f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                    f"💰 Choose your bet:\n"
                    f"Your balance: <b>{balance} ⭐</b>",
                    buttons=keyboard,
                    reply_to=event.id,
                    parse_mode='html'
                )
                
                # Store game setup context
                if not hasattr(userbot, 'game_contexts'):
                    userbot.game_contexts = {}
                
                userbot.game_contexts[user_id] = {
                    'chat_id': chat_id,
                    'game_type': game_type,
                    'message_id': msg.id,
                    'username': username
                }
                
                logger.info(f"Game {game_type} initiated by user {user_id} in chat {chat_id}")
                
            except Exception as e:
                logger.error(f"Error handling game command: {e}")
                await event.respond("❌ An error occurred. Please try again.")
        
        @userbot.on(events.CallbackQuery)
        async def handle_game_callback(event):
            """Handle game setup callbacks"""
            try:
                data = event.data.decode('utf-8')
                user_id = event.sender_id
                
                if not hasattr(userbot, 'game_contexts'):
                    userbot.game_contexts = {}
                
                context = userbot.game_contexts.get(user_id, {})
                
                if data == "cancel_game":
                    if user_id in user_games:
                        del user_games[user_id]
                    if user_id in userbot.game_contexts:
                        del userbot.game_contexts[user_id]
                    await event.edit("❌ Game cancelled.", parse_mode='html')
                    return
                
                if data.startswith("bet_"):
                    parts = data.split("_")
                    game_type = parts[1]
                    bet_amount = int(parts[2])
                    
                    balance = user_balances[user_id]
                    if balance < bet_amount:
                        await event.answer("❌ Insufficient balance!", alert=True)
                        return
                    
                    await event.answer()
                    
                    context['bet_amount'] = bet_amount
                    context['game_type'] = game_type
                    
                    game_info = GAME_TYPES[game_type]
                    keyboard = [
                        [
                            Button.inline("1 Round", f"rounds_{game_type}_1"),
                            Button.inline("2 Rounds", f"rounds_{game_type}_2"),
                        ],
                        [
                            Button.inline("3 Rounds", f"rounds_{game_type}_3"),
                        ],
                        [
                            Button.inline("◀️ Back", f"back_bet_{game_type}"),
                        ]
                    ]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>Select number of rounds:</b>\n"
                        f"Bet: <b>{bet_amount} ⭐</b>",
                        buttons=keyboard,
                        parse_mode='html'
                    )
                    return
                
                if data.startswith("rounds_"):
                    parts = data.split("_")
                    game_type = parts[1]
                    rounds = int(parts[2])
                    
                    await event.answer()
                    
                    context['rounds'] = rounds
                    
                    game_info = GAME_TYPES[game_type]
                    keyboard = [
                        [
                            Button.inline("1 Throw", f"throws_{game_type}_1"),
                            Button.inline("2 Throws", f"throws_{game_type}_2"),
                        ],
                        [
                            Button.inline("3 Throws", f"throws_{game_type}_3"),
                        ],
                        [
                            Button.inline("◀️ Back", f"bet_{game_type}_{context.get('bet_amount', 10)}"),
                        ]
                    ]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>Select throws per round:</b>\n"
                        f"Rounds: <b>{rounds}</b>",
                        buttons=keyboard,
                        parse_mode='html'
                    )
                    return
                
                if data.startswith("throws_"):
                    parts = data.split("_")
                    game_type = parts[1]
                    throws = int(parts[2])
                    
                    bet_amount = context.get('bet_amount', 10)
                    rounds = context.get('rounds', 1)
                    username = context.get('username', 'Player')
                    chat_id = context.get('chat_id')
                    
                    balance = user_balances[user_id]
                    if balance < bet_amount:
                        await event.answer("❌ Insufficient balance!", alert=True)
                        return
                    
                    # Deduct bet amount
                    user_balances[user_id] -= bet_amount
                    
                    # Create game
                    game = Game(
                        user_id=user_id,
                        username=username,
                        bet_amount=bet_amount,
                        rounds=rounds,
                        throw_count=throws,
                        game_type=game_type,
                        chat_id=chat_id
                    )
                    user_games[user_id] = game
                    
                    game_info = GAME_TYPES[game_type]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>Game Started!</b>\n\n"
                        f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                        f"🔄 Rounds: <b>{rounds}</b>\n"
                        f"🎯 Throws per round: <b>{throws}</b>\n\n"
                        f"Send {throws}x {game_info['emoji']} to play Round 1!",
                        parse_mode='html'
                    )
                    
                    logger.info(f"Game started: {game_type} for user {user_id}")
                    return
                
                if data.startswith("back_bet_"):
                    game_type = data.split("_")[2]
                    balance = user_balances[user_id]
                    
                    game_info = GAME_TYPES[game_type]
                    keyboard = [
                        [
                            Button.inline("10 ⭐", f"bet_{game_type}_10"),
                            Button.inline("25 ⭐", f"bet_{game_type}_25"),
                        ],
                        [
                            Button.inline("50 ⭐", f"bet_{game_type}_50"),
                            Button.inline("100 ⭐", f"bet_{game_type}_100"),
                        ],
                        [
                            Button.inline("❌ Cancel", "cancel_game"),
                        ]
                    ]
                    
                    await event.edit(
                        f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                        f"💰 Choose your bet:\n"
                        f"Your balance: <b>{balance} ⭐</b>",
                        buttons=keyboard,
                        parse_mode='html'
                    )
                    return
                
            except Exception as e:
                logger.error(f"Error in game callback: {e}")
                try:
                    await event.answer("❌ Error occurred", alert=True)
                except:
                    pass
        
        @userbot.on(events.NewMessage)
        async def handle_game_dice(event):
            """Handle dice/game emoji messages"""
            try:
                user_id = event.sender_id
                
                if user_id not in user_games:
                    return
                
                if not event.dice:
                    return
                
                game = user_games[user_id]
                game_info = GAME_TYPES[game.game_type]
                emoji = game_info['emoji']
                
                if event.dice.emoticon != emoji:
                    return
                
                user_value = event.dice.value
                game.user_results.append(user_value)
                
                if len(game.user_results) % game.throw_count == 0:
                    await asyncio.sleep(0.5)
                    
                    bot_results = []
                    for _ in range(game.throw_count):
                        bot_msg = await userbot.send_message(
                            game.chat_id,
                            file=event.dice
                        )
                        # Note: We can't get bot dice value in userbot, so we'll simulate
                        bot_results.append(random.randint(1, game_info['max_value']))
                        await asyncio.sleep(0.3)
                    
                    game.bot_results.extend(bot_results)
                    
                    round_start = (game.current_round) * game.throw_count
                    user_round_total = sum(game.user_results[round_start:round_start + game.throw_count])
                    bot_round_total = sum(bot_results)
                    
                    game.current_round += 1
                    
                    if user_round_total > bot_round_total:
                        game.user_score += 1
                        round_result = "✅ You won this round!"
                    elif bot_round_total > user_round_total:
                        game.bot_score += 1
                        round_result = "❌ Bot won this round!"
                    else:
                        round_result = "🤝 This round is a tie!"
                    
                    await asyncio.sleep(2)
                    
                    if game.current_round < game.total_rounds:
                        await userbot.send_message(
                            game.chat_id,
                            f"<b>Round {game.current_round} Results:</b>\n\n"
                            f"👤 Your total: <b>{user_round_total}</b>\n"
                            f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                            f"{round_result}\n\n"
                            f"📊 Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                            f"Send {game.throw_count}x {emoji} for Round {game.current_round + 1}!",
                            parse_mode='html'
                        )
                    else:
                        if game.user_score > game.bot_score:
                            winnings = game.bet_amount * 2
                            user_balances[user_id] += winnings
                            update_game_stats(user_id, game.game_type, game.bet_amount, winnings, True)
                            result_text = f"🎉 <b>YOU WON!</b> 🎉\n\n💰 Winnings: <b>{winnings} ⭐</b>"
                        elif game.bot_score > game.user_score:
                            update_game_stats(user_id, game.game_type, game.bet_amount, 0, False)
                            result_text = f"😔 <b>You lost!</b>\n\n💸 Lost: <b>{game.bet_amount} ⭐</b>"
                        else:
                            user_balances[user_id] += game.bet_amount
                            result_text = f"🤝 <b>It's a tie!</b>\n\n💰 Bet returned: <b>{game.bet_amount} ⭐</b>"
                        
                        balance = user_balances[user_id]
                        
                        await userbot.send_message(
                            game.chat_id,
                            f"<b>Final Round Results:</b>\n\n"
                            f"👤 Your total: <b>{user_round_total}</b>\n"
                            f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                            f"{round_result}\n\n"
                            f"📊 Final Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                            f"{result_text}\n\n"
                            f"💰 Balance: <b>{balance} ⭐</b>",
                            parse_mode='html'
                        )
                        
                        del user_games[user_id]
                        if hasattr(userbot, 'game_contexts') and user_id in userbot.game_contexts:
                            del userbot.game_contexts[user_id]
                
            except Exception as e:
                logger.error(f"Error handling game dice: {e}")
        
        await userbot.start()
        logger.info("✅ Userbot started successfully!")
        logger.info("🎮 Group gameplay enabled!")
        logger.info("💳 Payment handling enabled!")
        
        return userbot
        
    except ImportError:
        logger.error("❌ Telethon not installed. Install with: pip install telethon")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to setup userbot: {e}")
        return None

# ==================== MAIN FUNCTION ====================
def main():
    """Main function to run bot and userbot"""
    try:
        # Create bot application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("profile", profile_command))
        application.add_handler(CommandHandler("history", history_command))
        application.add_handler(CommandHandler("withdraw", withdraw_command))
        
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        
        logger.info("🤖 Bot starting...")
        
        # Start userbot in background
        async def post_init(app):
            try:
                bot_info = await app.bot.get_me()
                bot_username = bot_info.username
                logger.info(f"✅ Bot connected as @{bot_username}")
                
                userbot = await setup_userbot(bot_username)
                if userbot:
                    app.bot_data['userbot'] = userbot
                    logger.info("✅ System ready! Bot and Userbot are running.")
                else:
                    logger.warning("⚠️ Userbot not started. Only bot functions available.")
            except Exception as e:
                logger.error(f"Error in post_init: {e}")
        
        application.post_init = post_init
        
        # Run bot
        logger.info("🚀 Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Fatal error in main: {e}")
        raise

if __name__ == "__main__":
    main()
