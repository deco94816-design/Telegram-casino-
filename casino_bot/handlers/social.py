# handlers/social.py
# Social commands: tip and bonus

import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import BONUS_AMOUNT, STARS_TO_USD, BOT_USERNAME
from utils.decorators import handle_errors
from utils.helpers import (
    is_admin,
    get_user_balance,
    adjust_user_balance,
    get_or_create_profile,
    get_user_link,
    get_user_id_by_username,
    check_bot_name_in_profile,
)
import database as db

logger = logging.getLogger(__name__)


@handle_errors
async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /bonus command."""
    user = update.effective_user
    user_id = user.id
    
    if user_id in db.user_bonus_claimed:
        await update.message.reply_html(
            "❌ <b>Bonus Already Claimed!</b>\n\n"
            "You have already claimed your profile bonus.\n"
            "This bonus can only be claimed once."
        )
        return
    
    if check_bot_name_in_profile(user):
        adjust_user_balance(user_id, BONUS_AMOUNT)
        db.user_bonus_claimed.add(user_id)
        db.save_data()
        
        balance = get_user_balance(user_id)
        balance_usd = balance * STARS_TO_USD
        
        await update.message.reply_html(
            f"🎁 <b>Bonus Claimed Successfully!</b>\n\n"
            f"✅ We found <b>'{BOT_USERNAME}'</b> in your profile name!\n\n"
            f"💰 You received: <b>{BONUS_AMOUNT} ⭐</b>\n"
            f"💵 New Balance: <b>{balance:,} ⭐</b> (${balance_usd:.2f})\n\n"
            f"🎉 Thank you for supporting us!"
        )
        
        logger.info(f"Bonus claimed by user {user_id} ({user.first_name})")
    else:
        await update.message.reply_html(
            f"❌ <b>Bonus Not Available</b>\n\n"
            f"To claim your <b>{BONUS_AMOUNT} ⭐</b> bonus, please add "
            f"<b>'{BOT_USERNAME}'</b> to your Telegram profile name.\n\n"
            f"📝 <b>How to claim:</b>\n"
            f"1️⃣ Go to Telegram Settings\n"
            f"2️⃣ Edit your profile\n"
            f"3️⃣ Add <b>'{BOT_USERNAME}'</b> to your First Name or Last Name\n"
            f"4️⃣ Come back and use /bonus again\n\n"
            f"💡 Example: \"John {BOT_USERNAME}\" or \"{BOT_USERNAME} Smith\""
        )


@handle_errors
async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /tip command."""
    user_id = update.effective_user.id
    message = update.message
    
    # Check if using /tip amount @username format
    if context.args and len(context.args) >= 2:
        try:
            tip_amount = int(context.args[0])
            target = context.args[1]
            
            if tip_amount < 1:
                await message.reply_html("❌ Tip amount must be at least 1 ⭐")
                return
            
            # Check if target is a username
            if target.startswith('@'):
                username = target.lstrip('@')
                recipient_id = get_user_id_by_username(username)
                
                if not recipient_id:
                    await message.reply_html(
                        f"❌ <b>User not found!</b>\n\n"
                        f"User @{username} has not interacted with the bot yet.\n"
                        f"They need to use the bot at least once before receiving tips."
                    )
                    return
                
                recipient_profile = db.user_profiles.get(recipient_id, {})
                recipient_name = recipient_profile.get('username', username)
            else:
                # Try to parse as user_id
                try:
                    recipient_id = int(target)
                    recipient_profile = db.user_profiles.get(recipient_id, {})
                    recipient_name = recipient_profile.get('username', 'User')
                except ValueError:
                    await message.reply_html("❌ Invalid user! Use @username or user ID.")
                    return
            
            if recipient_id == user_id:
                await message.reply_html("❌ You can't tip yourself!")
                return
            
            sender_balance = get_user_balance(user_id)
            if sender_balance < tip_amount:
                await message.reply_html(
                    f"❌ <b>Insufficient balance!</b>\n\n"
                    f"Your balance: {sender_balance} ⭐\n"
                    f"Tip amount: {tip_amount} ⭐"
                )
                return
            
            if not is_admin(user_id):
                db.user_balances[user_id] -= tip_amount
            
            adjust_user_balance(recipient_id, tip_amount)
            
            tip_usd = tip_amount * STARS_TO_USD
            sender_name = message.from_user.first_name
            
            sender_link = get_user_link(user_id, sender_name)
            recipient_link = get_user_link(recipient_id, recipient_name)
            
            await message.reply_html(
                f"💝 <b>Tip sent successfully!</b>\n\n"
                f"👤 From: {sender_link}\n"
                f"👤 To: {recipient_link}\n"
                f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
                f"🎉 Thank you for your generosity!"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=recipient_id,
                    text=(
                        f"🎁 <b>You received a tip!</b>\n\n"
                        f"👤 From: {sender_link}\n"
                        f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
                        f"💵 Your new balance: <b>{get_user_balance(recipient_id)} ⭐</b>"
                    ),
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.warning(f"Could not notify recipient {recipient_id}: {e}")
            
            logger.info(f"Tip: {user_id} ({sender_name}) -> {recipient_id} ({recipient_name}): {tip_amount} stars")
            return
            
        except ValueError:
            pass  # Fall through to reply-based tip
    
    # Reply-based tip
    if not message.reply_to_message:
        await message.reply_html(
            "💝 <b>Tip Command</b>\n\n"
            "<b>Method 1:</b> Reply to a user's message:\n"
            "/tip <amount>\n\n"
            "<b>Method 2:</b> Tip by username:\n"
            "/tip <amount> @username\n\n"
            "<b>Examples:</b>\n"
            "• /tip 100 (reply to message)\n"
            "• /tip 100 @username\n"
            "• /tip 50 @JohnDoe\n\n"
            "This will send stars from your balance to the user."
        )
        return
    
    if not context.args or len(context.args) == 0:
        await message.reply_html("❌ Please specify the amount to tip!\nExample: /tip 100")
        return
    
    try:
        tip_amount = int(context.args[0])
        
        if tip_amount < 1:
            await message.reply_html("❌ Tip amount must be at least 1 ⭐")
            return
        
        recipient_id = message.reply_to_message.from_user.id
        recipient_name = message.reply_to_message.from_user.first_name
        sender_name = message.from_user.first_name
        
        # Update username mapping for recipient
        if message.reply_to_message.from_user.username:
            db.username_to_id[message.reply_to_message.from_user.username.lower()] = recipient_id
            db.save_data()
        
        if recipient_id == user_id:
            await message.reply_html("❌ You can't tip yourself!")
            return
        
        sender_balance = get_user_balance(user_id)
        if sender_balance < tip_amount:
            await message.reply_html(
                f"❌ <b>Insufficient balance!</b>\n\n"
                f"Your balance: {sender_balance} ⭐\n"
                f"Tip amount: {tip_amount} ⭐"
            )
            return
        
        if not is_admin(user_id):
            db.user_balances[user_id] -= tip_amount
        
        adjust_user_balance(recipient_id, tip_amount)
        get_or_create_profile(recipient_id, recipient_name)
        
        tip_usd = tip_amount * STARS_TO_USD
        
        sender_link = get_user_link(user_id, sender_name)
        recipient_link = get_user_link(recipient_id, recipient_name)
        
        await message.reply_html(
            f"💝 <b>Tip sent successfully!</b>\n\n"
            f"👤 From: {sender_link}\n"
            f"👤 To: {recipient_link}\n"
            f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
            f"🎉 Thank you for your generosity!"
        )
        
        try:
            await context.bot.send_message(
                chat_id=recipient_id,
                text=(
                    f"🎁 <b>You received a tip!</b>\n\n"
                    f"👤 From: {sender_link}\n"
                    f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
                    f"💵 Your new balance: <b>{get_user_balance(recipient_id)} ⭐</b>"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Could not notify recipient {recipient_id}: {e}")
        
        logger.info(f"Tip: {user_id} ({sender_name}) -> {recipient_id} ({recipient_name}): {tip_amount} stars")
        
    except ValueError:
        await message.reply_html("❌ Invalid amount! Please enter a number.")
