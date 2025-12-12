# handlers/payments.py
# Payment handlers: deposit, withdraw, invoices, and payment processing

import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import MIN_WITHDRAWAL, STARS_TO_TON, STARS_TO_USD, PROVIDER_TOKEN
from utils.decorators import handle_errors
from utils.helpers import (
    is_admin,
    get_user_balance,
    adjust_user_balance,
    is_private_chat,
    is_valid_ton_address,
    generate_transaction_id,
)
import database as db

logger = logging.getLogger(__name__)


@handle_errors
async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /deposit and /depo commands."""
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
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        "💳 <b>Select deposit amount:</b>",
        reply_markup=reply_markup
    )


@handle_errors
async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /withdraw command."""
    user_id = update.effective_user.id
    
    if not is_private_chat(update):
        bot_info = await context.bot.get_me()
        await update.message.reply_html(
            "🔒 <b>Private Command Only</b>\n\n"
            "For your security, the /withdraw command can only be used in a private chat with the bot.\n\n"
            f"👉 <a href='https://t.me/{bot_info.username}?start=withdraw'>Click here to open DM</a>\n\n"
            "Or search for @{} and start a private conversation.".format(bot_info.username)
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
    
    # Send with video if set, otherwise just text
    withdraw_video = db.get_withdraw_video()
    if withdraw_video:
        try:
            await update.message.reply_video(
                video=withdraw_video,
                caption=welcome_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send withdraw video: {e}")
            # Fallback to text if video fails
            await update.message.reply_html(welcome_text, reply_markup=reply_markup)
    else:
        await update.message.reply_html(welcome_text, reply_markup=reply_markup)


@handle_errors
async def custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /custom command for custom deposit amounts."""
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "💳 <b>Custom Deposit</b>\n\n"
            "Usage: /custom <amount>\n"
            "Example: /custom 150\n\n"
            "Minimum: 1 ⭐\n"
            "Maximum: 2500 ⭐"
        )
        return
    
    try:
        amount = int(context.args[0])
        
        if amount < 1:
            await update.message.reply_html("❌ Minimum deposit is 1 ⭐")
            return
        
        if amount > 2500:
            await update.message.reply_html("❌ Maximum deposit is 2500 ⭐")
            return
        
        title = f"Deposit {amount} Stars"
        description = f"Add {amount} ⭐ to your game balance"
        payload = f"deposit_{amount}_{update.effective_user.id}"
        prices = [LabeledPrice("Stars", amount)]
        
        await update.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency="XTR",
            prices=prices
        )
    except ValueError:
        await update.message.reply_html("❌ Invalid amount! Please enter a number.")


async def send_invoice(query, amount: int):
    """
    Send a payment invoice for deposit.
    
    Args:
        query: Callback query object
        amount: Amount of stars to deposit
    """
    title = f"Deposit {amount} Stars"
    description = f"Add {amount} ⭐ to your game balance"
    payload = f"deposit_{amount}_{query.from_user.id}"
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
        f"💳 Invoice for <b>{amount} ⭐</b> sent!\n"
        f"Complete the payment to add Stars to your balance.",
        parse_mode=ParseMode.HTML
    )


@handle_errors
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout queries for payments."""
    query = update.pre_checkout_query
    await query.answer(ok=True)


@handle_errors
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment notifications."""
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    
    amount = payment.total_amount
    adjust_user_balance(user_id, amount)
    
    balance = get_user_balance(user_id)
    
    await update.message.reply_html(
        f"✅ <b>Payment successful!</b>\n\n"
        f"💰 Added: <b>{amount} ⭐</b>\n"
        f"💳 New balance: <b>{balance:,} ⭐</b>"
    )


@handle_errors
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for custom deposits and withdrawals."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Handle custom deposit amount input
    if context.user_data.get('waiting_for_custom_amount'):
        try:
            amount = int(text)
            if amount < 1:
                await update.message.reply_html("❌ Minimum deposit is 1 ⭐")
                return
            if amount > 2500:
                await update.message.reply_html("❌ Maximum deposit is 2500 ⭐")
                return
            
            context.user_data['waiting_for_custom_amount'] = False
            
            title = f"Deposit {amount} Stars"
            description = f"Add {amount} ⭐ to your game balance"
            payload = f"deposit_{amount}_{user_id}"
            prices = [LabeledPrice("Stars", amount)]
            
            await update.message.reply_invoice(
                title=title,
                description=description,
                payload=payload,
                provider_token=PROVIDER_TOKEN,
                currency="XTR",
                prices=prices
            )
        except ValueError:
            await update.message.reply_html("❌ Please enter a valid number.")
        return
    
    # Handle withdrawal amount input
    if context.user_data.get('withdraw_state') == 'waiting_amount':
        try:
            amount = int(text)
            balance = get_user_balance(user_id)
            
            if amount < MIN_WITHDRAWAL:
                await update.message.reply_html(f"❌ Minimum withdrawal is {MIN_WITHDRAWAL} ⭐")
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
    
    # Handle withdrawal address input
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


async def process_withdrawal_confirmation(query, context: ContextTypes.DEFAULT_TYPE):
    """
    Process confirmed withdrawal request.
    
    Args:
        query: Callback query object
        context: Bot context
    """
    user_id = query.from_user.id
    
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
        db.user_balances[user_id] -= stars_amount
    
    exchange_id = db.increment_withdrawal_counter()
    
    ton_amount = round(stars_amount * STARS_TO_TON, 8)
    transaction_id = generate_transaction_id()
    
    now = datetime.now()
    created_date = now.strftime("%Y-%m-%d %H:%M")
    hold_until = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
    
    db.user_withdrawals[str(user_id)] = {
        'exchange_id': exchange_id,
        'stars': stars_amount,
        'ton_amount': ton_amount,
        'address': ton_address,
        'transaction_id': transaction_id,
        'created': created_date,
        'hold_until': hold_until,
        'status': 'on_hold'
    }
    
    db.save_data()
    
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
