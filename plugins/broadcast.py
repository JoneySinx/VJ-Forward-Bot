import time
import asyncio
import datetime
import logging

# --- Hydrogram Imports ---
from hydrogram import Client, filters
from hydrogram.errors import (
    InputUserDeactivated, 
    UserNotParticipant, 
    FloodWait, 
    UserIsBlocked, 
    PeerIdInvalid
)

# --- Custom Modules ---
from database import db
from config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- HUD Design Template ---
BROADCAST_HUD = """
<b>╭──⌬ 📣 ʙʀᴏᴀᴅᴄᴀsᴛ sᴛᴀᴛᴜs</b>
<b>│</b>
<b>│</b>  {}
<b>│</b>  <code>{} %</code>
<b>│</b>
<b>├──╼ 📊 sᴛᴀᴛɪsᴛɪᴄs</b>
<b>│ 👥 ᴛᴏᴛᴀʟ   :</b> <code>{}</code>
<b>│ ✅ sᴜᴄᴄᴇss :</b> <code>{}</code>
<b>│ 🚫 ғᴀɪʟᴇᴅ  :</b> <code>{}</code>
<b>│</b>
<b>╰──╼ ⏳ ᴛɪᴍᴇ :</b> <code>{}</code>
"""

# ==============================================================================
#  Broadcast Logic
# ==============================================================================

async def send_msg(user_id, message):
    """Sends a message to a single user with error handling"""
    try:
        await message.copy(chat_id=int(user_id))
        return 200, None
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_msg(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return 400, "Deleted"
    except UserIsBlocked:
        return 400, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return 400, "Error"
    except Exception as e:
        return 500, "Error"

# ==============================================================================
#  Command Handler
# ==============================================================================

@Client.on_message(filters.command("broadcast") & filters.user(Config.BOT_OWNER) & filters.reply)
async def broadcast_handler(bot, message):
    # 1. Initialization
    users = await db.get_all_users()
    b_msg = message.reply_to_message
    
    status_msg = await message.reply_text(
        text='<b>🚀 Initializing Broadcast...</b>'
    )
    
    start_time = time.time()
    total_users = await db.total_users_count()
    
    # Counters
    done = 0
    success = 0
    blocked = 0
    deleted = 0
    failed = 0
    
    # 2. Loop through users
    async for user in users:
        # Check if user dict has ID
        if 'id' not in user:
            continue
            
        user_id = user['id']
        code, status = await send_msg(user_id, b_msg)
        
        # Update Counters
        if code == 200:
            success += 1
        else:
            if status == "Blocked": blocked += 1
            elif status == "Deleted": deleted += 1
            else: failed += 1
            
        done += 1
        
        # 3. Update Status Every 20 Users
        if done % 20 == 0:
            await update_status(
                status_msg, start_time, total_users, done, success, blocked, deleted, failed
            )

    # 4. Final Status
    await update_status(
        status_msg, start_time, total_users, done, success, blocked, deleted, failed, finished=True
    )

# ==============================================================================
#  Helper: Status Updater (HUD Style)
# ==============================================================================

async def update_status(msg, start_time, total, done, success, blocked, deleted, failed, finished=False):
    # Calculate Percentage
    try:
        percentage = int((done * 100) / total)
    except ZeroDivisionError:
        percentage = 0
        
    # Generate Progress Bar ▰▰▱▱
    filled_blocks = int(percentage / 10) 
    empty_blocks = 10 - filled_blocks
    progress_bar = f"{'▰' * filled_blocks}{'▱' * empty_blocks}"
    
    # Calculate Time Taken
    elapsed = datetime.timedelta(seconds=int(time.time() - start_time))
    
    # Failures count
    total_failed = blocked + deleted + failed
    
    # Format Text
    text = BROADCAST_HUD.format(
        progress_bar,
        percentage,
        total,
        success,
        total_failed,
        str(elapsed)
    )
    
    if finished:
        text += f"\n<b>✅ COMPLETED SUCCESSFULLY</b>\n\n<b>🗑 Deleted:</b> {deleted} | <b>🚫 Blocked:</b> {blocked}"
        
    try:
        await msg.edit(text)
    except Exception:
        pass
