# main.py
# Entry point for the casino bot - registers all handlers and starts polling

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, logger
from database import load_data

# Import handlers
from handlers.basic import (
    start, help_command, balance_command, profile_command,
    history_command, cancel_command
)
from handlers.games import (
    play_command, dice_command, bowl_command, arrow_command,
    football_command, basket_command, demo_command, handle_game_emoji
)
from handlers.payments import (
    deposit_command, withdraw_command, custom_deposit,
    precheckout_callback, successful_payment, handle_text_message
)
from handlers.admin import (
    addadmin_command, removeadmin_command, listadmins_command,
    set_video_command, handle_video_message
)
from handlers.social import bonus_command, tip_command
from handlers.callbacks import button_callback


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    load_data()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
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
    
    # Handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(
        filters.VIDEO | filters.ANIMATION | filters.Document.VIDEO, 
        handle_video_message
    ))
    application.add_handler(MessageHandler(filters.Dice.ALL, handle_game_emoji))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_text_message
    ))
    
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
