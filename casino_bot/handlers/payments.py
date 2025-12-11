# handlers/payments.py
# Payment handlers: /deposit, /withdraw, /custom, invoice and payment processing

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import PROVIDER_TOKEN, STARS_TO_TON, MIN_WITHDRAWAL, logger
from utils.decorators import handle_errors
from utils.helpers import is_private_chat, get_user_balance, adjust_user_balance
import database as db


@handle_errors
async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /deposit command - show deposit options."""
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
async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /withdraw command - show withdrawal info."""
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
    
    # Reset withdraw state
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
async def custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /custom command for custom deposit amounts."""
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


async def send_invoice(query, amount: int) -> None:
    """Send a payment invoice to the user."""
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
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pre-checkout query - approve payment."""
    query = update.pre_checkout_query
    await query.answer(ok=True)


@handle_errors
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful payment - credit user's balance."""
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
