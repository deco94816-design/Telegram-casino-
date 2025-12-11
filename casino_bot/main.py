# main.py
# Entry point for the casino bot - registers all handlers and starts polling

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
import database as db

# Import all handlers
from handlers import (
    # Basic commands
    start,
    help_command,
    balance_command,
    profile_command,
    history_command,
    play_command,
    # Game commands
    dice_command,
    bowl_command,
    arrow_command,
    football_command,
    basket_command,
    demo_command,
    handle_game_emoji,
    # Payment commands
    deposit_command,
    withdraw_command,
    custom_deposit,
    precheckout_callback,
    successful_payment,
    handle_text_message,
    # Admin commands
    addadmin_command,
    removeadmin_command,
    listadmins_command,
    set_video_command,
    handle_video_message,
    cancel_command,
    # Social commands
    tip_command,
    bonus_command,
    # Callbacks
    button_callback,
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: Update, context):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_html(
                "❌ <b>An unexpected error occurred</b>\n\n"
                "Please try again later. If the problem persists, contact support."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")


def main():
    """Main function to start the bot."""
    # Load saved data on startup
    db.load_data()
    
    # Initialize game locks
    db.init_game_locks()
    
    # Build the application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # ==================== COMMAND HANDLERS ====================
    
    # Basic commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("bal", balance_command))  # Alias
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("depo", deposit_command))  # Alias
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("custom", custom_deposit))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("bonus", bonus_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Game commands
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("bowl", bowl_command))
    application.add_handler(CommandHandler("arrow", arrow_command))
    application.add_handler(CommandHandler("football", football_command))
    application.add_handler(CommandHandler("basket", basket_command))
    application.add_handler(CommandHandler("demo", demo_command))
    
    # Admin commands
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("listadmins", listadmins_command))
    application.add_handler(CommandHandler("video", set_video_command))
    
    # Tip command
    application.add_handler(CommandHandler("tip", tip_command))
    
    # ==================== OTHER HANDLERS ====================
    
    # Callback query handler (inline buttons)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # Video message handler (for admin video upload)
    application.add_handler(MessageHandler(
        filters.VIDEO | filters.ANIMATION | filters.Document.VIDEO, 
        handle_video_message
    ))
    
    # Game emoji handler (dice messages)
    application.add_handler(MessageHandler(filters.Dice.ALL, handle_game_emoji))
    
    # Text message handler (for custom amounts and withdrawals)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_text_message
    ))
    
    # Start the bot
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
