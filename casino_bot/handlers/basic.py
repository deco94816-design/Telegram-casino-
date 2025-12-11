# handlers/basic.py
# Basic command handlers: /start, /help, /balance, /profile, /history, /play, /cancel

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import GAME_TYPES, STARS_TO_USD, logger
from utils.decorators import handle_errors
from utils.helpers import (
    is_admin, get_user_balance, get_or_create_profile,
    get_user_link, get_user_rank, get_rank_info, create_progress_bar
)
import database as db


@handle_errors
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - welcome message and main menu."""
    user = update.effective_user
    user_id = user.id
    
    get_or_create_profile(user_id, user.username or user.first_name)
    
    # Update username mapping
    if user.username:
        db.username_to_id[user.username.lower()] = user_id
        db.save_data()
    
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    profile = db.user_profiles.get(user_id, {})
    turnover = profile.get('total_bets', 0.0) * STARS_TO_USD
    
    admin_badge = " 👑" if is_admin(user_id) else ""
    
    welcome_text = (
        f"🐱 <b>Welcome to Iibrate Game{admin_badge}</b>\n\n"
        f"⭐️ Iibrate Game is the best online mini-games on Telegram\n\n"
        f"📢 <b>How to start winning?</b>\n\n"
        f"1. Make sure you have a balance. You can top up using the \"Deposit\" button.\n\n"
        f"2. Join one of our groups from the @Iibrate catalog.\n\n"
        f"3. Type /play and start playing!\n\n\n"
        f"💵 Balance: ${balance_usd:.2f}\n"
        f"👑 Game turnover: ${turnover:.2f}\n\n"
        f"🌐 <b>About us</b>\n"
        f"<a href='https://t.me/Iibrate'>Channel</a> | "
        f"<a href='https://t.me/Iibrates'>Chat</a> | "
        f"<a href='https://t.me/Iibratesupport'>Support</a>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Play", callback_data="show_games")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        welcome_text, 
        reply_markup=reply_markup, 
        disable_web_page_preview=True
    )


@handle_errors
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - show help information."""
    user_id = update.effective_user.id
    
    from config import BOT_USERNAME, BONUS_AMOUNT
    
    help_text = (
        "🎯 <b>How to Play:</b>\n\n"
        "1️⃣ Deposit Stars using /deposit or /depo\n"
        "2️⃣ Choose a game (/dice, /bowl, /arrow, /football, /basket)\n"
        "3️⃣ Select bet amount or use shortcuts:\n"
        "   • /dice 100 - Bet 100 stars\n"
        "   • /dice all - Bet entire balance\n"
        "   • /dice half - Bet half balance\n"
        "4️⃣ Choose rounds (1-3)\n"
        "5️⃣ Choose throws (1-3)\n"
        "6️⃣ Optionally let bot roll first\n"
        "7️⃣ Send your emojis!\n"
        "8️⃣ Higher total wins!\n\n"
        "🏆 Most rounds won = Winner!\n"
        "💎 Winner takes the pot!\n\n"
        "💝 <b>Tip Users:</b>\n"
        "• Reply to a message: /tip <amount>\n"
        "• By username: /tip <amount> @username\n\n"
        f"🎁 <b>Bonus:</b>\n"
        f"Add '{BOT_USERNAME}' to your profile name and use /bonus to get {BONUS_AMOUNT} ⭐!\n\n"
        "📝 <b>Command Aliases:</b>\n"
        "• /bal = /balance\n"
        "• /depo = /deposit\n\n"
    )
    
    if is_admin(user_id):
        help_text += (
            "👑 <b>Admin Commands:</b>\n"
            "/addadmin - Add new admin\n"
            "/removeadmin - Remove admin\n"
            "/listadmins - View all admins\n"
            "/demo - Test games without betting\n"
            "/video - Set withdraw video\n"
            "/video status - Check video status\n"
            "/video remove - Remove video\n"
        )
    
    await update.message.reply_html(help_text)


@handle_errors
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /balance command - show user's balance."""
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    admin_note = " (Admin - Unlimited)" if is_admin(user_id) else ""
    
    keyboard = [
        [
            InlineKeyboardButton("💳 Deposit", callback_data="balance_deposit"),
            InlineKeyboardButton("💎 Withdraw", callback_data="balance_withdraw"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"💰 <b>Your Balance</b>{admin_note}\n\n"
        f"⭐ Stars: <b>{balance:,} ⭐</b>\n"
        f"💵 USD: <b>${balance_usd:.2f}</b>",
        reply_markup=reply_markup
    )


@handle_errors
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command - show user's profile information."""
    user = update.effective_user
    user_id = user.id
    
    profile = get_or_create_profile(user_id, user.username or user.first_name)
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    rank_level = get_user_rank(profile['xp'])
    rank_info = get_rank_info(rank_level)
    
    admin_badge = " 👑" if is_admin(user_id) else ""
    user_link = get_user_link(user_id, user.first_name)
    
    if rank_level < 20:
        next_rank_info = get_rank_info(rank_level + 1)
        xp_progress = profile['xp'] - rank_info['xp_required']
        xp_needed = next_rank_info['xp_required'] - rank_info['xp_required']
        progress_bar = create_progress_bar(xp_progress, xp_needed)
        rank_display = (
            f"{rank_info['emoji']} {rank_info['name']} (Lvl {rank_level})\n"
            f"{progress_bar} {profile['xp']}/{next_rank_info['xp_required']} XP"
        )
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
        f"📢 <b>Profile{admin_badge}</b>\n\n"
        f"👤 User: {user_link}\n"
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


@handle_errors
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command - show user's game history."""
    user = update.effective_user
    user_id = user.id
    
    profile = get_or_create_profile(user_id, user.username or user.first_name)
    history = db.user_game_history.get(user_id, [])
    
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
            history_text += (
                f"{game_info['icon']} {game_info['name']} - {status} "
                f"(${bet_usd:.2f}) - {timestamp}\n"
            )
    
    await update.message.reply_html(history_text)


@handle_errors
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /play command - show game selection menu."""
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


@handle_errors
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command - cancel any ongoing operation."""
    user_id = update.effective_user.id
    
    cancelled = False
    
    if context.user_data.get('waiting_for_video'):
        context.user_data['waiting_for_video'] = False
        cancelled = True
    
    if context.user_data.get('waiting_for_custom_amount'):
        context.user_data['waiting_for_custom_amount'] = False
        cancelled = True
    
    if context.user_data.get('withdraw_state'):
        context.user_data['withdraw_state'] = None
        context.user_data['withdraw_amount'] = None
        context.user_data['withdraw_address'] = None
        cancelled = True
    
    if cancelled:
        await update.message.reply_html("✅ Operation cancelled.")
    else:
        await update.message.reply_html("ℹ️ Nothing to cancel.")
