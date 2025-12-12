import re
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import (
    ChannelPrivate, 
    ChannelInvalid, 
    UsernameInvalid, 
    UsernameNotModified
)
from hydrogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove,
    KeyboardButton
)

# --- Custom Modules ---
from .utils import STS
from database import db
from config import Temp
from script import Script

# Regex for parsing Telegram Links
# Support: t.me/c/123/456 (Private) & t.me/username/456 (Public)
LINK_REGEX = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")

@Client.on_message(filters.private & filters.command(["forward"]))
async def forward_command_handler(bot, message):
    user_id = message.from_user.id
    
    # 1. Check Bot/Userbot Availability
    _bot = await db.get_bot(user_id)
    if not _bot:
        _bot = await db.get_userbot(user_id)
        if not _bot:
            return await message.reply(
                "<b>⚠️ No Bot Found!</b>\nPlease add a Bot or Userbot in /settings first.",
                quote=True
            )

    # 2. Check Target Channels
    channels = await db.get_user_channels(user_id)
    if not channels:
        return await message.reply(
            "<b>⚠️ No Target Channel Found!</b>\nPlease add a Target Channel in /settings.",
            quote=True
        )

    # 3. Select Target Channel
    target_chat_id = None
    target_title = None

    if len(channels) > 1:
        # Create Keyboard
        buttons = []
        chan_map = {} # Map title to ID
        for channel in channels:
            buttons.append([KeyboardButton(channel['title'])])
            chan_map[channel['title']] = channel['chat_id']
        
        buttons.append([KeyboardButton("❌ Cancel")])
        
        question = await bot.ask(
            message.chat.id, 
            Script.TO_MSG, 
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        
        if question.text in ["/cancel", "❌ Cancel"]:
            return await message.reply(Script.CANCEL, reply_markup=ReplyKeyboardRemove())
            
        target_title = question.text
        target_chat_id = chan_map.get(target_title)
        
        if not target_chat_id:
            return await message.reply("<b>❌ Invalid Channel Selected!</b>", reply_markup=ReplyKeyboardRemove())
    else:
        # Auto-select if only one channel
        target_chat_id = channels[0]['chat_id']
        target_title = channels[0]['title']

    # 4. Get Source Chat (Link or Forward)
    # Remove keyboard before asking next question
    await message.reply("...", reply_markup=ReplyKeyboardRemove()).delete()
    
    source_prompt = await bot.ask(message.chat.id, Script.FROM_MSG)
    
    if source_prompt.text and source_prompt.text.startswith('/'):
        return await message.reply(Script.CANCEL)

    chat_id = None
    last_msg_id = None
    source_title = "Private Chat"

    # -- Logic: Parse Link --
    if source_prompt.text and not source_prompt.forward_date:
        match = LINK_REGEX.match(source_prompt.text.replace("?single", "").strip())
        if not match:
            return await message.reply('<b>❌ Invalid Post Link!</b>\nPlease send a valid link like <code>https://t.me/username/100</code>')
        
        identifier = match.group(1)
        last_msg_id = int(match.group(2))
        
        if identifier.isdigit():
            # Private Channel Link (t.me/c/12345/10) -> ID: -10012345
            chat_id = int(f"-100{identifier}")
        else:
            # Public Username
            chat_id = identifier

    # -- Logic: Parse Forward --
    elif source_prompt.forward_from_chat:
        last_msg_id = source_prompt.forward_from_message_id
        chat_id = source_prompt.forward_from_chat.id
        source_title = source_prompt.forward_from_chat.title
    else:
        return await message.reply("<b>❌ Invalid Input!</b>\nPlease Forward a message from the channel or Send its Link.")

    # -- Logic: Fetch Chat Title (Optional Check) --
    try:
        chat_info = await bot.get_chat(chat_id)
        source_title = chat_info.title
    except Exception:
        # If bot can't access chat yet (e.g. userbot needed), keep default title
        pass

    # 5. Get Skip Count
    skip_prompt = await bot.ask(message.chat.id, Script.SKIP_MSG)
    
    if skip_prompt.text.startswith('/'):
        return await message.reply(Script.CANCEL)
    
    try:
        skip_count = int(skip_prompt.text)
    except ValueError:
        return await message.reply("<b>❌ Error:</b> Please enter a valid number (Integer).")

    # 6. Final Confirmation
    forward_id = f"{user_id}-{skip_prompt.id}" # Unique ID based on message ID
    
    confirm_btn = [[
        InlineKeyboardButton('✅ Yes, Start', callback_data=f"start_public_{forward_id}"),
        InlineKeyboardButton('❌ No, Cancel', callback_data="close_btn")
    ]]
    
    # Store Data in STS (In-Memory) before confirmation
    STS(forward_id).store(chat_id, target_chat_id, skip_count, last_msg_id)
    
    await message.reply_text(
        text=Script.DOUBLE_CHECK.format(
            botname=_bot['name'], 
            botuname=_bot['username'], 
            from_chat=source_title, 
            to_chat=target_title, 
            skip=skip_count
        ),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(confirm_btn)
    )
