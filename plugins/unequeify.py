import re
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- Custom Modules ---
from database import db
from config import Temp
from .test import get_client
from script import Script

# --- Constants ---
# Regex for parsing Telegram Links
LINK_REGEX = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")

# HUD Design for De-Duplication
UNEQUIFY_HUD = """
<b>╭──⌬ ♻️ ᴜɴᴇǫᴜɪғʏ (ᴅᴇ-ᴅᴜᴘ)</b>
<b>│</b>
<b>│</b>  {}
<b>│</b>  <code>{}</code>
<b>│</b>
<b>├──╼ 📊 sᴛᴀᴛɪsᴛɪᴄs</b>
<b>│ 🔍 sᴄᴀɴɴᴇᴅ :</b> <code>{}</code>
<b>│ 🗑 ᴅᴇʟᴇᴛᴇᴅ :</b> <code>{}</code>
<b>│ 📁 ᴜɴɪǫᴜᴇ  :</b> <code>{}</code>
<b>│</b>
<b>╰──╼ 🤖 sᴛᴀᴛᴜs :</b> <code>{}</code>
"""

# Buttons
CANCEL_BTN = InlineKeyboardMarkup([[InlineKeyboardButton('🛑 Stop Process', callback_data='terminate_frwd')]])
COMPLETED_BTN = InlineKeyboardMarkup([[InlineKeyboardButton('✅ Completed', url='https://t.me/VJ_Botz')]])

# ==============================================================================
#  Command: /unequify
# ==============================================================================

@Client.on_message(filters.command("unequify") & filters.private)
async def unequify_handler(client, message):
    user_id = message.from_user.id
    
    # 1. Check Locks
    if Temp.LOCK.get(user_id):
        return await message.reply("<b>⚠️ Wait!</b> A task is already running.")
    
    Temp.CANCEL[user_id] = False

    # 2. Check Userbot
    _bot = await db.get_userbot(user_id)
    if not _bot:
        return await message.reply(
            "<b>⚠️ Userbot Required!</b>\nTo delete messages, I need a Userbot (Session).\nAdd it in /settings.",
            quote=True
        )

    # 3. Get Target Chat
    target_prompt = await client.ask(
        user_id, 
        text="<b>❪ TARGET CHAT ❫\n\nForward a message from the Target Chat or send its Link.\n\n/cancel - To Stop</b>"
    )
    
    if target_prompt.text and target_prompt.text.startswith("/"):
        return await message.reply("<b>❌ Process Cancelled.</b>")

    chat_id = None
    chat_username = None

    # Parse Link
    if target_prompt.text and not target_prompt.forward_date:
        match = LINK_REGEX.match(target_prompt.text.replace("?single", "").strip())
        if not match:
            return await message.reply('<b>❌ Invalid Link!</b>')
        
        identifier = match.group(1)
        if identifier.isdigit():
            chat_id = int(f"-100{identifier}")
        else:
            chat_id = identifier # Username
            
    # Parse Forward
    elif target_prompt.forward_from_chat:
        chat_id = target_prompt.forward_from_chat.id
    else:
        return await message.reply("<b>❌ Invalid Input!</b>")

    # 4. Confirmation
    confirm = await client.ask(
        user_id, 
        text="<b>⚠️ WARNING:</b> This will delete duplicate files from the chat.\nType <code>/yes</code> to confirm."
    )
    if confirm.text.lower() != '/yes':
        return await message.reply("<b>❌ Cancelled.</b>")

    status_msg = await message.reply("<b>🔄 Initializing Userbot...</b>")
    
    # 5. Start Userbot
    try:
        userbot = await get_client(_bot['session'], is_bot=False)
        await userbot.start()
    except Exception as e:
        return await status_msg.edit(f"<b>❌ Userbot Login Failed:</b> `{e}`")

    # 6. Verify Permissions
    try:
        test = await userbot.send_message(chat_id, "Testing Permissions...")
        await test.delete()
    except Exception:
        await userbot.stop()
        return await status_msg.edit("<b>❌ Error:</b> Userbot must be an <b>Admin</b> in the target chat with Delete permissions.")

    # ==========================================================================
    #  Core Logic: De-Duplication
    # ==========================================================================
    
    Temp.LOCK[user_id] = True
    
    unique_files = set() # To store file_unique_id
    duplicate_ids = []   # To store message_ids to delete
    
    total_scanned = 0
    deleted_count = 0
    
    try:
        # Initial HUD Update
        await update_hud(status_msg, total_scanned, deleted_count, 0, "Scanning...", CANCEL_BTN)

        async for msg in userbot.search_messages(chat_id=chat_id, filter=enums.MessagesFilter.DOCUMENT):
            # Check Cancellation
            if Temp.CANCEL.get(user_id):
                await update_hud(status_msg, total_scanned, deleted_count, len(unique_files), "Cancelled", COMPLETED_BTN)
                break
            
            if not msg.document:
                continue

            # logic: file_unique_id is constant for the same file content
            uid = msg.document.file_unique_id
            
            if uid in unique_files:
                duplicate_ids.append(msg.id)
            else:
                unique_files.add(uid)
            
            total_scanned += 1

            # Update HUD every 200 messages
            if total_scanned % 200 == 0:
                await update_hud(status_msg, total_scanned, deleted_count, len(unique_files), "Scanning...", CANCEL_BTN)

            # Batch Delete (Every 100 duplicates)
            if len(duplicate_ids) >= 100:
                await userbot.delete_messages(chat_id, duplicate_ids)
                deleted_count += len(duplicate_ids)
                duplicate_ids = [] # Reset batch
                await update_hud(status_msg, total_scanned, deleted_count, len(unique_files), "Deleting...", CANCEL_BTN)

        # Delete remaining duplicates
        if duplicate_ids:
            await userbot.delete_messages(chat_id, duplicate_ids)
            deleted_count += len(duplicate_ids)

        await update_hud(status_msg, total_scanned, deleted_count, len(unique_files), "Completed", COMPLETED_BTN)

    except Exception as e:
        await status_msg.edit(f"<b>❌ Error:</b> `{e}`")
    finally:
        Temp.LOCK[user_id] = False
        await userbot.stop()


# ==============================================================================
#  Helper: HUD Updater
# ==============================================================================

async def update_hud(msg, scanned, deleted, unique, status, markup):
    # Simple Loading Bar Logic
    # Cycle through ▰ positions based on scanned count for animation effect
    cycle = (scanned // 50) % 6
    bar = ["▱"] * 6
    if status != "Completed":
        bar[cycle] = "▰"
    else:
        bar = ["▰"] * 6 # Full bar on complete
        
    progress_bar = "".join(bar)
    
    text = UNEQUIFY_HUD.format(
        progress_bar,
        status,
        scanned,
        deleted,
        unique,
        status
    )
    
    try:
        await msg.edit(text, reply_markup=markup)
    except Exception:
        pass
