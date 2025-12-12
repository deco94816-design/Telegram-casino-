# handlers/admin.py
# Admin commands: addadmin, removeadmin, listadmins, video, cancel

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID, ADMIN_BALANCE
from utils.decorators import handle_errors
from utils.helpers import is_admin
import database as db

logger = logging.getLogger(__name__)


@handle_errors
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /addadmin command."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "👑 <b>Add Admin</b>\n\n"
            "Usage: /addadmin <user_id>\n"
            "Example: /addadmin 123456789\n\n"
            f"Current admins: {len(db.admin_list)}"
        )
        return
    
    try:
        new_admin_id = int(context.args[0])
        
        if new_admin_id in db.admin_list:
            await update.message.reply_html(f"⚠️ User <code>{new_admin_id}</code> is already an admin!")
            return
        
        db.admin_list.add(new_admin_id)
        db.user_balances[new_admin_id] = ADMIN_BALANCE
        db.save_data()
        
        await update.message.reply_html(
            f"✅ <b>New admin added successfully!</b>\n\n"
            f"👤 User ID: <code>{new_admin_id}</code>\n"
            f"💰 Balance: <b>{ADMIN_BALANCE:,} ⭐</b>\n"
            f"👑 Total admins: {len(db.admin_list)}"
        )
        
        logger.info(f"Admin {user_id} added new admin: {new_admin_id}")
        
    except ValueError:
        await update.message.reply_html("❌ Invalid user ID! Please enter a valid number.")


@handle_errors
async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /removeadmin command."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "👑 <b>Remove Admin</b>\n\n"
            "Usage: /removeadmin <user_id>\n"
            "Example: /removeadmin 123456789"
        )
        return
    
    try:
        remove_admin_id = int(context.args[0])
        
        if remove_admin_id == ADMIN_ID:
            await update.message.reply_html("❌ Cannot remove the main admin!")
            return
        
        if remove_admin_id not in db.admin_list:
            await update.message.reply_html(f"⚠️ User <code>{remove_admin_id}</code> is not an admin!")
            return
        
        db.admin_list.remove(remove_admin_id)
        db.save_data()
        
        await update.message.reply_html(
            f"✅ <b>Admin removed successfully!</b>\n\n"
            f"👤 User ID: <code>{remove_admin_id}</code>\n"
            f"👑 Remaining admins: {len(db.admin_list)}"
        )
        
        logger.info(f"Admin {user_id} removed admin: {remove_admin_id}")
        
    except ValueError:
        await update.message.reply_html("❌ Invalid user ID! Please enter a valid number.")


@handle_errors
async def listadmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /listadmins command."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    admin_text = "👑 <b>Admin List</b>\n\n"
    admin_text += f"Total admins: {len(db.admin_list)}\n\n"
    
    for idx, admin_id in enumerate(db.admin_list, 1):
        is_main = " (Main Admin)" if admin_id == ADMIN_ID else ""
        admin_text += f"{idx}. <code>{admin_id}</code>{is_main}\n"
    
    await update.message.reply_html(admin_text)


@handle_errors
async def set_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to set the withdraw video."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>Admin only command.</b>")
        return
    
    # Check if admin wants to view current video status
    if context.args and context.args[0].lower() == 'status':
        withdraw_video = db.get_withdraw_video()
        if withdraw_video:
            await update.message.reply_html(
                "🎬 <b>Withdraw Video Status</b>\n\n"
                f"✅ Video is set\n"
                f"📎 File ID: <code>{withdraw_video[:50]}...</code>"
            )
        else:
            await update.message.reply_html(
                "🎬 <b>Withdraw Video Status</b>\n\n"
                "❌ No video set yet\n\n"
                "Use /video to set one."
            )
        return
    
    # Check if admin wants to remove video
    if context.args and context.args[0].lower() == 'remove':
        if db.get_withdraw_video():
            db.clear_withdraw_video()
            await update.message.reply_html(
                "✅ <b>Withdraw video removed!</b>\n\n"
                "The /withdraw command will now send text only."
            )
        else:
            await update.message.reply_html("❌ No video is currently set.")
        return
    
    context.user_data['waiting_for_video'] = True
    await update.message.reply_html(
        "🎬 <b>Set Withdraw Video</b>\n\n"
        "Send a video or MP4 file now.\n\n"
        "This video will be sent with every /withdraw command.\n\n"
        "📝 <b>Other options:</b>\n"
        "• /video status - Check current video\n"
        "• /video remove - Remove current video\n"
        "• /cancel - Cancel this operation"
    )


@handle_errors
async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video upload from admin for withdraw feature."""
    user_id = update.effective_user.id
    
    # Only process if admin is waiting to set video
    if not context.user_data.get('waiting_for_video'):
        return
    
    if not is_admin(user_id):
        return
    
    # Get video from message (can be video or animation/GIF)
    video = update.message.video or update.message.animation or update.message.document
    
    if not video:
        await update.message.reply_html(
            "❌ <b>Invalid file!</b>\n\n"
            "Please send a valid video file (MP4, etc.)\n\n"
            "Use /cancel to abort."
        )
        return
    
    # Check if it's a document, verify it's a video type
    if update.message.document:
        mime_type = update.message.document.mime_type or ""
        if not mime_type.startswith('video/'):
            await update.message.reply_html(
                "❌ <b>Invalid file type!</b>\n\n"
                "Please send a video file (MP4, etc.)\n\n"
                "Use /cancel to abort."
            )
            return
    
    db.set_withdraw_video(video.file_id)
    context.user_data['waiting_for_video'] = False
    
    await update.message.reply_html(
        "✅ <b>Withdraw video set successfully!</b>\n\n"
        "This video will now be sent with all /withdraw messages.\n\n"
        "📝 <b>Commands:</b>\n"
        "• /video status - Check current video\n"
        "• /video remove - Remove video\n"
        "• /video - Set new video"
    )
    
    logger.info(f"Admin {user_id} set withdraw video: {video.file_id[:50]}...")


@handle_errors
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing operation."""
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
