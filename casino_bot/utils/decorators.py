# utils/decorators.py
# Error handling decorator for bot handlers

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError

logger = logging.getLogger(__name__)


def handle_errors(func):
    """
    Decorator that wraps handler functions with comprehensive error handling.
    Catches and logs Telegram API errors and unexpected exceptions.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except BadRequest as e:
            logger.error(f"BadRequest in {func.__name__}: {e}")
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Request Error</b>\n\n"
                        "Something went wrong with your request. Please try again."
                    )
            except Exception:
                pass
        except Forbidden as e:
            logger.error(f"Forbidden in {func.__name__}: {e}")
        except NetworkError as e:
            logger.error(f"NetworkError in {func.__name__}: {e}")
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Network Error</b>\n\n"
                        "Connection issue. Please try again later."
                    )
            except Exception:
                pass
        except TelegramError as e:
            logger.error(f"TelegramError in {func.__name__}: {e}")
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Error</b>\n\n"
                        "An error occurred. Please try again."
                    )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Unexpected Error</b>\n\n"
                        "Something went wrong. Please try again later."
                    )
            except Exception:
                pass
    return wrapper
