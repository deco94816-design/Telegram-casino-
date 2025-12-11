# handlers/games.py
# Game command handlers: /play, /dice, /bowl, /arrow, /football, /basket, /demo

import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import GAME_TYPES, STARS_TO_USD, logger
from database import user_games, user_balances, game_locks, save_data
from models import Game
from utils.decorators import handle_errors
from utils.helpers import (
    is_admin, get_user_balance, get_or_create_profile, get_user_link,
    update_game_stats, adjust_user_balance, save_last_game_settings
)


@handle_errors
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /play command - Show game selection menu."""
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


async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    """Internal function to start a game from command."""
    user_id = update.effective_user.id
    
    async with game_locks[user_id]:
        if user_id in user_games:
            await update.message.reply_html(
                "❌ You already have an active game! Finish it first."
            )
            return
        
        balance = get_user_balance(user_id)
        
        # Check for bet amount in args
        bet_amount = None
        if context.args and len(context.args) > 0:
            arg = context.args[0].lower()
            if arg == 'all':
                bet_amount = int(balance)
            elif arg == 'half':
                bet_amount = int(balance / 2)
            else:
                try:
                    bet_amount = int(arg)
                except ValueError:
                    await update.message.reply_html("❌ Invalid bet amount! Use a number, 'all', or 'half'.")
                    return
            
            if bet_amount < 1:
                await update.message.reply_html("❌ Bet amount must be at least 1 ⭐")
                return
            
            if bet_amount > balance and not is_admin(user_id):
                await update.message.reply_html(
                    f"❌ Insufficient balance!\n"
                    f"Your balance: <b>{balance} ⭐</b>\n"
                    f"Bet amount: <b>{bet_amount} ⭐</b>"
                )
                return
            
            context.user_data['bet_amount'] = bet_amount
            context.user_data['game_type'] = game_type
            context.user_data['is_demo'] = False
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("1 Round", callback_data=f"rounds_{game_type}_1"),
                    InlineKeyboardButton("2 Rounds", callback_data=f"rounds_{game_type}_2"),
                ],
                [
                    InlineKeyboardButton("3 Rounds", callback_data=f"rounds_{game_type}_3"),
                ],
                [
                    InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_html(
                f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                f"💰 Bet: <b>{bet_amount} ⭐</b>\n\n"
                f"Select number of rounds:",
                reply_markup=reply_markup
            )
            return
        
        if balance < 1 and not is_admin(user_id):
            await update.message.reply_html(
                "❌ Insufficient balance! Use /deposit to add Stars.\n"
                f"Your balance: <b>{balance} ⭐</b>"
            )
            return
        
        context.user_data['game_type'] = game_type
        context.user_data['is_demo'] = False
        
        game_info = GAME_TYPES[game_type]
        keyboard = [
            [
                InlineKeyboardButton("10 ⭐", callback_data=f"bet_{game_type}_10"),
                InlineKeyboardButton("25 ⭐", callback_data=f"bet_{game_type}_25"),
            ],
            [
                InlineKeyboardButton("50 ⭐", callback_data=f"bet_{game_type}_50"),
                InlineKeyboardButton("100 ⭐", callback_data=f"bet_{game_type}_100"),
            ],
            [
                InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(
            f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
            f"💰 Choose your bet:\n"
            f"Your balance: <b>{balance:,} ⭐</b>",
            reply_markup=reply_markup
        )


async def start_game_from_callback(query, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    """Internal function to start a game from callback query."""
    user_id = query.from_user.id
    
    async with game_locks[user_id]:
        if user_id in user_games:
            await query.edit_message_text(
                "❌ You already have an active game! Finish it first.",
                parse_mode=ParseMode.HTML
            )
            return
        
        balance = get_user_balance(user_id)
        
        if balance < 1 and not is_admin(user_id):
            await query.edit_message_text(
                "❌ Insufficient balance! Use /deposit to add Stars.\n"
                f"Your balance: <b>{balance} ⭐</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        context.user_data['game_type'] = game_type
        context.user_data['is_demo'] = False
        
        game_info = GAME_TYPES[game_type]
        keyboard = [
            [
                InlineKeyboardButton("10 ⭐", callback_data=f"bet_{game_type}_10"),
                InlineKeyboardButton("25 ⭐", callback_data=f"bet_{game_type}_25"),
            ],
            [
                InlineKeyboardButton("50 ⭐", callback_data=f"bet_{game_type}_50"),
                InlineKeyboardButton("100 ⭐", callback_data=f"bet_{game_type}_100"),
            ],
            [
                InlineKeyboardButton("◀️ Back to Games", callback_data="show_games"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
            f"💰 Choose your bet:\n"
            f"Your balance: <b>{balance:,} ⭐</b>",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )


@handle_errors
async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /dice command - Start a dice game."""
    await start_game_command(update, context, 'dice')


@handle_errors
async def bowl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bowl command - Start a bowling game."""
    await start_game_command(update, context, 'bowl')


@handle_errors
async def arrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /arrow command - Start a darts game."""
    await start_game_command(update, context, 'arrow')


@handle_errors
async def football_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /football command - Start a football game."""
    await start_game_command(update, context, 'football')


@handle_errors
async def basket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /basket command - Start a basketball game."""
    await start_game_command(update, context, 'basket')


@handle_errors
async def demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /demo command - Admin only demo mode for testing games."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ This command is only for administrators.")
        return
    
    if user_id in user_games:
        await update.message.reply_html(
            "❌ You already have an active game! Finish it first."
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("🎲 Dice", callback_data="demo_game_dice"),
            InlineKeyboardButton("🎳 Bowl", callback_data="demo_game_bowl"),
        ],
        [
            InlineKeyboardButton("🎯 Arrow", callback_data="demo_game_arrow"),
            InlineKeyboardButton("🥅 Football", callback_data="demo_game_football"),
        ],
        [
            InlineKeyboardButton("🏀 Basketball", callback_data="demo_game_basket"),
        ],
        [
            InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        f"🎮 <b>DEMO MODE</b> 🔑\n\n"
        f"🎯 Choose a game to test:\n"
        f"(No Stars will be deducted)",
        reply_markup=reply_markup
    )


@handle_errors
async def handle_game_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dice emoji messages during active games."""
    user_id = update.effective_user.id
    
    if user_id not in user_games:
        return
    
    game = user_games[user_id]
    game_info = GAME_TYPES[game.game_type]
    emoji = game_info['emoji']
    
    message = update.message
    if not message.dice:
        return
    
    if message.dice.emoji != emoji:
        return
    
    user_value = message.dice.value
    game.user_results.append(user_value)
    game.user_throws_this_round += 1
    
    if game.user_throws_this_round >= game.throw_count:
        await asyncio.sleep(0.5)
        
        if not game.bot_rolled_this_round:
            bot_results = []
            for _ in range(game.throw_count):
                bot_msg = await message.reply_dice(emoji=emoji)
                bot_results.append(bot_msg.dice.value)
                await asyncio.sleep(0.3)
            
            game.bot_results.extend(bot_results)
        
        round_start = (game.current_round) * game.throw_count
        user_round_total = sum(game.user_results[round_start:round_start + game.throw_count])
        bot_round_total = sum(game.bot_results[round_start:round_start + game.throw_count])
        
        game.current_round += 1
        
        game.bot_rolled_this_round = False
        game.user_throws_this_round = 0
        
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
            if game.bot_first:
                await message.reply_html(
                    f"<b>Round {game.current_round} Results:</b>\n\n"
                    f"👤 Your total: <b>{user_round_total}</b>\n"
                    f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                    f"{round_result}\n\n"
                    f"📊 Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                    f"🤖 Bot is rolling for Round {game.current_round + 1}..."
                )
                
                await asyncio.sleep(1)
                bot_results = []
                for _ in range(game.throw_count):
                    bot_msg = await message.reply_dice(emoji=emoji)
                    bot_results.append(bot_msg.dice.value)
                    await asyncio.sleep(0.3)
                
                game.bot_results.extend(bot_results)
                game.bot_rolled_this_round = True
                bot_total = sum(bot_results)
                
                await asyncio.sleep(1)
                await message.reply_html(
                    f"🤖 <b>Bot's Round {game.current_round + 1} total: {bot_total}</b>\n\n"
                    f"👤 Your turn! Send {game.throw_count}x {emoji}"
                )
            else:
                await message.reply_html(
                    f"<b>Round {game.current_round} Results:</b>\n\n"
                    f"👤 Your total: <b>{user_round_total}</b>\n"
                    f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                    f"{round_result}\n\n"
                    f"📊 Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                    f"👤 Send {game.throw_count}x {emoji} for Round {game.current_round + 1}!"
                )
        else:
            # Game over
            demo_tag = " (DEMO)" if game.is_demo else ""
            
            user_link = get_user_link(user_id, game.username)
            
            if game.user_score > game.bot_score:
                winnings = game.bet_amount * 2
                if not game.is_demo:
                    adjust_user_balance(user_id, winnings)
                    update_game_stats(user_id, game.game_type, game.bet_amount, winnings, True)
                result_text = f"🎉 <b>{user_link} WON!{demo_tag}</b> 🎉\n\n💰 Winnings: <b>{winnings} ⭐</b>"
            elif game.bot_score > game.user_score:
                if not game.is_demo:
                    update_game_stats(user_id, game.game_type, game.bet_amount, 0, False)
                result_text = f"😔 <b>{user_link} lost!{demo_tag}</b>\n\n💸 Lost: <b>{game.bet_amount} ⭐</b>"
            else:
                if not game.is_demo:
                    adjust_user_balance(user_id, game.bet_amount)
                result_text = f"🤝 <b>It's a tie!{demo_tag}</b>\n\n💰 Bet returned: <b>{game.bet_amount} ⭐</b>"
            
            balance = get_user_balance(user_id)
            
            # Create repeat/double buttons (only for non-demo games)
            if not game.is_demo:
                double_bet = game.bet_amount * 2
                keyboard = [
                    [
                        InlineKeyboardButton(f"🔄 Repeat ({game.bet_amount} ⭐)", callback_data="game_repeat"),
                        InlineKeyboardButton(f"⏫ Double ({double_bet} ⭐)", callback_data="game_double"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None
            
            await message.reply_html(
                f"<b>Final Round Results:</b>\n\n"
                f"👤 Your total: <b>{user_round_total}</b>\n"
                f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                f"{round_result}\n\n"
                f"📊 Final Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                f"{result_text}\n\n"
                f"💰 Balance: <b>{balance:,} ⭐</b>",
                reply_markup=reply_markup
            )
            
            del user_games[user_id]
