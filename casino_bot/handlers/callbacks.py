# handlers/callbacks.py
# All callback query handlers for inline buttons

import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import (
    GAME_TYPES, STARS_TO_USD, STARS_TO_TON, MIN_WITHDRAWAL, logger
)
from database import (
    user_games, user_balances, user_withdrawals, save_data,
    get_withdraw_video_file_id, increment_withdrawal_counter
)
from models import Game
from utils.decorators import handle_errors
from utils.helpers import (
    is_admin, get_user_balance, start_repeat_game, save_last_game_settings,
    generate_transaction_id
)
from handlers.games import start_game_from_callback
from handlers.payments import send_invoice


@handle_errors
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    try:
        # Handle repeat/double buttons
        if data == "game_repeat":
            await start_repeat_game(context, user_id, query.message.chat_id, double=False)
            return
        
        if data == "game_double":
            await start_repeat_game(context, user_id, query.message.chat_id, double=True)
            return
        
        # Handle balance inline buttons
        if data == "balance_deposit":
            keyboard = [
                [
                    InlineKeyboardButton("10 ⭐", callback_data="deposit_10"),
                    InlineKeyboardButton("25 ⭐", callback_data="deposit_25"),
                ],
                [
                    InlineKeyboardButton("50 ⭐", callback_data="deposit_50"),
                    InlineKeyboardButton("100 ⭐", callback_data="deposit_100"),
                ],
                [
                    InlineKeyboardButton("250 ⭐", callback_data="deposit_250"),
                    InlineKeyboardButton("500 ⭐", callback_data="deposit_500"),
                ],
                [
                    InlineKeyboardButton("💳 Custom Amount", callback_data="deposit_custom"),
                ],
                [
                    InlineKeyboardButton("◀️ Back", callback_data="back_to_balance"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "💳 <b>Select deposit amount:</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "balance_withdraw":
            if query.message.chat.type != "private":
                bot_info = await context.bot.get_me()
                await query.edit_message_text(
                    "🔒 <b>Private Command Only</b>\n\n"
                    "For your security, withdrawals can only be done in a private chat with the bot.\n\n"
                    f"👉 <a href='https://t.me/{bot_info.username}?start=withdraw'>Click here to open DM</a>\n\n"
                    "Then use /withdraw command.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            
            welcome_text = (
                "✨ <b>Welcome to Stars Withdrawal!</b>\n\n"
                "<b>Withdraw:</b>\n"
                "1 ⭐️ = $0.0179 = 0.01201014 TON\n\n"
                f"<b>Minimum withdrawal: {MIN_WITHDRAWAL} ⭐</b>\n\n"
                "<blockquote>⚙️ <b>Good to know:</b>\n"
                "• When you exchange stars through a channel or bot, Telegram keeps a 15% fee and applies a 21-day hold.\n"
                "• We send TON immediately—factoring in this fee and a small service premium.</blockquote>"
            )
            
            keyboard = [[InlineKeyboardButton("💎 Withdraw", callback_data="start_withdraw")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # For callback, we need to handle video differently
            withdraw_video_file_id = get_withdraw_video_file_id()
            if withdraw_video_file_id:
                try:
                    await query.message.delete()
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=withdraw_video_file_id,
                        caption=welcome_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Failed to send withdraw video in callback: {e}")
                    await query.edit_message_text(
                        welcome_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
            else:
                await query.edit_message_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            return
        
        if data == "back_to_balance":
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
            
            await query.edit_message_text(
                f"💰 <b>Your Balance</b>{admin_note}\n\n"
                f"⭐ Stars: <b>{balance:,} ⭐</b>\n"
                f"💵 USD: <b>${balance_usd:.2f}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
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
        
        if data.startswith("play_game_"):
            game_type = data.replace("play_game_", "")
            await start_game_from_callback(query, context, game_type)
            return
        
        if data == "start_withdraw":
            context.user_data['withdraw_state'] = 'waiting_amount'
            
            # Try to edit caption if it's a video message, otherwise edit text
            try:
                await query.edit_message_caption(
                    caption=f"💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                            f"Minimum: {MIN_WITHDRAWAL} ⭐\n"
                            f"Example: 100",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                try:
                    await query.edit_message_text(
                        f"💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                        f"Minimum: {MIN_WITHDRAWAL} ⭐\n"
                        f"Example: 100",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Failed to edit message for withdraw: {e}")
            return
        
        if data == "confirm_withdraw":
            stars_amount = context.user_data.get('withdraw_amount', 0)
            ton_address = context.user_data.get('withdraw_address', '')
            
            balance = get_user_balance(user_id)
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
            
            if not is_admin(user_id):
                user_balances[user_id] -= stars_amount
            
            exchange_id = increment_withdrawal_counter()
            
            ton_amount = round(stars_amount * STARS_TO_TON, 8)
            transaction_id = generate_transaction_id()
            
            now = datetime.now()
            created_date = now.strftime("%Y-%m-%d %H:%M")
            hold_until = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
            
            user_withdrawals[str(user_id)] = {
                'exchange_id': exchange_id,
                'stars': stars_amount,
                'ton_amount': ton_amount,
                'address': ton_address,
                'transaction_id': transaction_id,
                'created': created_date,
                'hold_until': hold_until,
                'status': 'on_hold'
            }
            
            save_data()
            
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
                f"📝 Reason: Iibrate game rating is negative. Placed on 14-day hold."
            )
            
            await query.edit_message_text(
                receipt_text,
                parse_mode=ParseMode.HTML
            )
            
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
        
        if data.startswith("deposit_"):
            if data == "deposit_custom":
                await query.edit_message_text(
                    "💳 <b>Custom Deposit</b>\n\n"
                    "Please send the amount you want to deposit.\n\n"
                    "Example: Just type <code>150</code>\n\n"
                    "Minimum: 1 ⭐\n"
                    "Maximum: 2500 ⭐",
                    parse_mode=ParseMode.HTML
                )
                context.user_data['waiting_for_custom_amount'] = True
                return
            
            amount = int(data.split("_")[1])
            await send_invoice(query, amount)
            return
        
        if data.startswith("demo_game_"):
            if not is_admin(user_id):
                await query.answer("❌ Admin only!", show_alert=True)
                return
            
            game_type = data.split("_")[2]
            context.user_data['game_type'] = game_type
            context.user_data['is_demo'] = True
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("10 ⭐", callback_data=f"demo_bet_{game_type}_10"),
                    InlineKeyboardButton("25 ⭐", callback_data=f"demo_bet_{game_type}_25"),
                ],
                [
                    InlineKeyboardButton("50 ⭐", callback_data=f"demo_bet_{game_type}_50"),
                    InlineKeyboardButton("100 ⭐", callback_data=f"demo_bet_{game_type}_100"),
                ],
                [
                    InlineKeyboardButton("Back ◀️", callback_data="back_to_demo_menu"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🎮 <b>DEMO: {game_info['name']}</b> 🔑\n\n"
                f"💰 Choose demo bet:\n"
                f"(No Stars will be deducted)",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "back_to_demo_menu":
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
            await query.edit_message_text(
                f"🎮 <b>DEMO MODE</b> 🔑\n\n"
                f"🎯 Choose a game to test:\n"
                f"(No Stars will be deducted)",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("demo_bet_"):
            if not is_admin(user_id):
                await query.answer("❌ Admin only!", show_alert=True)
                return
            
            parts = data.split("_")
            game_type = parts[2]
            bet_amount = int(parts[3])
            
            context.user_data['bet_amount'] = bet_amount
            context.user_data['game_type'] = game_type
            context.user_data['is_demo'] = True
            
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
                    InlineKeyboardButton("Back ◀️", callback_data=f"demo_game_{game_type}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select rounds:</b> 🔑\n"
                f"Demo Bet: <b>{bet_amount} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("bet_"):
            parts = data.split("_")
            game_type = parts[1]
            bet_amount = int(parts[2])
            balance = get_user_balance(user_id)
            
            if balance < bet_amount and not is_admin(user_id):
                await query.edit_message_text(
                    "❌ Insufficient balance! Use /deposit to add Stars."
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
                    InlineKeyboardButton("Back ◀️", callback_data=f"back_to_bet_{game_type}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select number of rounds:</b>\n"
                f"Bet: <b>{bet_amount} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("back_to_bet_"):
            game_type = data.split("_")[3]
            balance = get_user_balance(user_id)
            
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
            return
        
        if data.startswith("rounds_"):
            parts = data.split("_")
            game_type = parts[1]
            rounds = int(parts[2])
            
            context.user_data['rounds'] = rounds
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("1 Throw", callback_data=f"throws_{game_type}_1"),
                    InlineKeyboardButton("2 Throws", callback_data=f"throws_{game_type}_2"),
                ],
                [
                    InlineKeyboardButton("3 Throws", callback_data=f"throws_{game_type}_3"),
                ],
                [
                    InlineKeyboardButton("Back ◀️", callback_data=f"bet_{game_type}_{context.user_data.get('bet_amount', 10)}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            is_demo = context.user_data.get('is_demo', False)
            demo_tag = " 🔑" if is_demo else ""
            
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select throws per round:</b>{demo_tag}\n"
                f"Rounds: <b>{rounds}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("throws_"):
            parts = data.split("_")
            game_type = parts[1]
            throws = int(parts[2])
            
            bet_amount = context.user_data.get('bet_amount', 10)
            rounds = context.user_data.get('rounds', 1)
            is_demo = context.user_data.get('is_demo', False)
            
            context.user_data['throws'] = throws
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("👤 I roll first", callback_data=f"start_game_{game_type}_user"),
                ],
                [
                    InlineKeyboardButton("🤖 Bot rolls first", callback_data=f"start_game_{game_type}_bot"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            demo_tag = " 🔑 DEMO" if is_demo else ""
            
            await query.edit_message_text(
                f"{game_info['icon']} <b>Who should roll first?{demo_tag}</b>\n\n"
                f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                f"🔄 Rounds: <b>{rounds}</b>\n"
                f"🎯 Throws per round: <b>{throws}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("start_game_"):
            parts = data.split("_")
            game_type = parts[2]
            who_first = parts[3]
            
            bet_amount = context.user_data.get('bet_amount', 10)
            rounds = context.user_data.get('rounds', 1)
            throws = context.user_data.get('throws', 1)
            is_demo = context.user_data.get('is_demo', False)
            
            if not is_demo and not is_admin(user_id):
                balance = get_user_balance(user_id)
                if balance < bet_amount:
                    await query.edit_message_text(
                        "❌ Insufficient balance! Use /deposit to add Stars."
                    )
                    return
                user_balances[user_id] -= bet_amount
                save_data()
            
            game = Game(
                user_id=user_id,
                username=query.from_user.username or query.from_user.first_name,
                bet_amount=bet_amount,
                rounds=rounds,
                throw_count=throws,
                game_type=game_type
            )
            game.is_demo = is_demo
            game.bot_first = (who_first == 'bot')
            game.bot_rolled_this_round = False
            game.user_throws_this_round = 0
            user_games[user_id] = game
            
            # Save game settings for repeat/double feature
            if not is_demo:
                save_last_game_settings(user_id, game_type, bet_amount, rounds, throws, game.bot_first)
            
            game_info = GAME_TYPES[game_type]
            demo_tag = " 🔑 DEMO" if is_demo else ""
            
            if game.bot_first:
                await query.edit_message_text(
                    f"{game_info['icon']} <b>Game Started!{demo_tag}</b>\n\n"
                    f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                    f"🔄 Rounds: <b>{rounds}</b>\n"
                    f"🎯 Throws per round: <b>{throws}</b>\n\n"
                    f"🤖 Bot is rolling first...",
                    parse_mode=ParseMode.HTML
                )
                
                await asyncio.sleep(1)
                bot_results = []
                for i in range(throws):
                    bot_msg = await query.message.reply_dice(emoji=game_info['emoji'])
                    bot_results.append(bot_msg.dice.value)
                    await asyncio.sleep(0.3)
                
                game.bot_results.extend(bot_results)
                game.bot_rolled_this_round = True
                bot_total = sum(bot_results)
                
                await asyncio.sleep(1)
                await query.message.reply_html(
                    f"🤖 <b>Bot's Round 1 total: {bot_total}</b>\n\n"
                    f"👤 Now it's your turn! Send {throws}x {game_info['emoji']}"
                )
            else:
                await query.edit_message_text(
                    f"{game_info['icon']} <b>Game Started!{demo_tag}</b>\n\n"
                    f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                    f"🔄 Rounds: <b>{rounds}</b>\n"
                    f"🎯 Throws per round: <b>{throws}</b>\n\n"
                    f"👤 You roll first! Send {throws}x {game_info['emoji']}",
                    parse_mode=ParseMode.HTML
                )
            return
        
        if data == "cancel_game":
            if user_id in user_games:
                del user_games[user_id]
            await query.edit_message_text(
                "❌ Game cancelled.",
                parse_mode=ParseMode.HTML
            )
            return
            
    except Exception as e:
        logger.error(f"Button callback error: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ An error occurred. Please try again.",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
