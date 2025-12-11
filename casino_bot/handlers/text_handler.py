# handlers/text_handler.py
# Text message handler for custom amounts and withdrawal flow

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes

from config import PROVIDER_TOKEN, STARS_TO_TON, MIN_WITHDRAWAL
from utils.decorators import handle_errors
from utils.helpers import get_user_balance, is_valid_ton_address
import database as db


@handle_errors
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages for custom amounts and withdrawal address."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Handle custom deposit amount
    if context.user_data.get('waiting_for_custom_amount'):
        await _handle_custom_deposit(update, context, user_id, text)
        return
    
    # Handle withdraw amount entry
    if context.user_data.get('withdraw_state') == 'waiting_amount':
        await _handle_withdraw_amount(update, context, user_id, text)
        return
    
    # Handle withdraw address entry
    if context.user_data.get('withdraw_state') == 'waiting_address':
        await _handle_withdraw_address(update, context, text)
        return


async def _handle_custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  user_id: int, text: str) -> None:
    """Handle custom deposit amount entry."""
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


async def _handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   user_id: int, text: str) -> None:
    """Handle withdrawal amount entry."""
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


async def _handle_withdraw_address(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    text: str) -> None:
    """Handle withdrawal address entry."""
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
