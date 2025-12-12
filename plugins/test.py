import re
import asyncio
import logging
from typing import Union, Optional, AsyncGenerator

# --- Hydrogram Imports ---
from hydrogram import Client, filters, types, enums
from hydrogram.errors import (
    FloodWait,
    AccessTokenExpired,
    AccessTokenInvalid,
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- Custom Modules ---
from database import db
from config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Constants ---
BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)]\[buttonurl:/{0,2}(.+?)(:same)?])")
SESSION_STRING_SIZE = 351

# ==============================================================================
#  Client Manager (Handles Login & Bot Addition)
# ==============================================================================
class ClientManager: 
    def __init__(self):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH

    async def add_bot(self, bot, message):
        """Add a forwarded bot token from BotFather"""
        user_id = message.from_user.id
        prompt = (
            "<b>🤖 Add Bot Mode</b>\n\n"
            "1. Go to @BotFather\n"
            "2. Create a new bot /newbot\n"
            "3. Forward the message with the **API Token** to me.\n\n"
            "<i>Type /cancel to stop.</i>"
        )
        msg = await bot.ask(chat_id=user_id, text=prompt)
        
        if msg.text == '/cancel':
            return await msg.reply('<b>Process Cancelled!</b>')
        
        # Validation
        if not msg.forward_date:
            return await msg.reply("<b>Error:</b> Please forward the message directly from BotFather.")
        
        # BotFather ID check (Optional but safe)
        if msg.forward_from and msg.forward_from.id != 93372553:
             return await msg.reply("<b>Error:</b> This message is not from @BotFather.")

        # Extract Token using Regex
        bot_token_match = re.search(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', msg.text)
        bot_token = bot_token_match.group(0) if bot_token_match else None
        
        if not bot_token:
            return await msg.reply("<b>Error:</b> Could not find a valid Bot Token.")

        # Test the Token
        try:
            temp_client = Client("TempBot", api_id=self.api_id, api_hash=self.api_hash, bot_token=bot_token, in_memory=True)
            await temp_client.start()
            bot_info = temp_client.me
            await temp_client.stop()
        except Exception as e:
            return await msg.reply(f"<b>Invalid Token:</b> `{e}`")

        # Save to DB
        details = {
            'id': bot_info.id,
            'is_bot': True,
            'user_id': user_id,
            'name': bot_info.first_name,
            'token': bot_token,
            'username': bot_info.username 
        }
        await db.add_bot(details)
        return True

    async def add_session(self, bot, message):
        """Interactive Wizard to add Userbot via Phone Number"""
        user_id = message.from_user.id
        
        disclaimer = (
            "<b>⚠️ DISCLAIMER: Add Userbot</b>\n\n"
            "Adding a Userbot allows the bot to forward from private channels.\n"
            "• Use a secondary account if possible.\n"
            "• We are not responsible for account bans.\n\n"
            "<b>Enter your Phone Number (with Country Code):</b>\n"
            "Example: `+919876543210`"
        )
        
        phone_msg = await bot.ask(chat_id=user_id, text=disclaimer)
        if phone_msg.text == '/cancel':
            return await phone_msg.reply('<b>Process Cancelled!</b>')
        
        phone_number = phone_msg.text.strip()
        
        # Create temporary client
        client = Client(f"session_{user_id}", api_id=self.api_id, api_hash=self.api_hash, in_memory=True)
        await client.connect()
        
        try:
            # Send OTP
            status_msg = await phone_msg.reply("Sending OTP...")
            try:
                code_data = await client.send_code(phone_number)
            except PhoneNumberInvalid:
                return await status_msg.edit('<b>Error:</b> Invalid Phone Number.')
            except FloodWait as e:
                return await status_msg.edit(f'<b>Error:</b> FloodWait. Try again in {e.value} seconds.')

            # Ask for OTP
            otp_prompt = (
                "<b>OTP Sent!</b>\n\n"
                "Check your Telegram Service Notifications.\n"
                "Enter the code like this: `1 2 3 4 5` (with spaces).\n\n"
                "<i>Type /cancel to cancel.</i>"
            )
            otp_msg = await bot.ask(user_id, otp_prompt, timeout=300)
            
            if otp_msg.text == '/cancel':
                return await otp_msg.reply('Cancelled.')

            phone_code = otp_msg.text.replace(" ", "")

            # Login
            try:
                await client.sign_in(phone_number, code_data.phone_code_hash, phone_code)
            except PhoneCodeInvalid:
                return await otp_msg.reply('<b>Error:</b> Invalid OTP.')
            except PhoneCodeExpired:
                return await otp_msg.reply('<b>Error:</b> OTP Expired.')
            except SessionPasswordNeeded:
                # 2FA Handling
                pwd_msg = await bot.ask(user_id, '<b>Two-Step Verification Enabled.</b>\nEnter your Password:', timeout=300)
                if pwd_msg.text == '/cancel':
                    return await pwd_msg.reply('Cancelled.')
                
                try:
                    await client.check_password(password=pwd_msg.text)
                except PasswordHashInvalid:
                    return await pwd_msg.reply('<b>Error:</b> Wrong Password.')

            # Export Session
            string_session = await client.export_session_string()
            user_info = await client.get_me()

            details = {
                'id': user_info.id,
                'is_bot': False,
                'user_id': user_id,
                'name': user_info.first_name,
                'session': string_session,
                'username': user_info.username
            }
            await db.add_userbot(details)
            return True

        except Exception as e:
            logger.error(f"Add Session Error: {e}")
            await bot.send_message(user_id, f"<b>Error:</b> {e}")
        finally:
            # Important: Always disconnect to free memory
            if client.is_connected:
                await client.disconnect()

# ==============================================================================
#  Helper Functions
# ==============================================================================

async def get_client(data, is_bot=True):
    """Factory to return a Client instance"""
    if is_bot:
        return Client("WorkerBot", Config.API_ID, Config.API_HASH, bot_token=data, in_memory=True)
    else:
        return Client("WorkerUser", Config.API_ID, Config.API_HASH, session_string=data, in_memory=True)

async def iter_messages(
    client,
    chat_id: Union[int, str],
    limit: int,
    offset: int = 0,
    filters: list = None,
    max_size: int = None,
) -> Optional[AsyncGenerator["types.Message", None]]:
    """
    Optimized message iterator
    filters: list of strings representing prohibited media types (e.g., ['video', 'photo', 'link'])
    """
    current = offset
    while True:
        # Fetch in batches of 200
        batch_size = min(200, limit - current)
        if batch_size <= 0:
            return

        # Generate ID list
        message_ids = list(range(current, current + batch_size + 1))
        
        try:
            messages = await client.get_messages(chat_id, message_ids)
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return

        # Handle case where all messages might be None (deleted)
        if not messages:
            return

        for message in messages:
            current += 1
            if not message:
                continue
                
            # Filter Logic: Check if message type is in the forbidden list
            is_filtered = False
            if filters:
                # 1. Standard Media Check
                for media_type in ['photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation']:
                    if getattr(message, media_type, None) and media_type in filters:
                        is_filtered = True
                        break
                
                # 2. Text Check
                if message.text and 'text' in filters:
                     is_filtered = True

                # 3. Link Filter Check (Advanced)
                # If 'link' is in filters, block messages containing URLs or Text Links
                if not is_filtered and 'link' in filters:
                    entities = (message.entities or []) + (message.caption_entities or [])
                    for entity in entities:
                        if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]:
                            is_filtered = True
                            break

            if is_filtered:
                yield "FILTERED"
            else:
                yield message

# ==============================================================================
#  Button Parsing
# ==============================================================================

def parse_buttons(text, markup=True):
    """Parses markdown-style buttons: [Name][buttonurl:link]"""
    if not text:
        return None
        
    buttons = []
    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 0:
            btn_text = match.group(2)
            btn_url = match.group(3).replace(" ", "")
            
            # Create button object
            btn = InlineKeyboardButton(text=btn_text, url=btn_url)

            # Check for :same flag (to put on same row)
            if bool(match.group(4)) and buttons:
                buttons[-1].append(btn)
            else:
                buttons.append([btn])
                
    if markup and buttons:
       return InlineKeyboardMarkup(buttons)
    return buttons if buttons else None

# ==============================================================================
#  Commands (Settings Reset)
# ==============================================================================

@Client.on_message(filters.private & filters.command('reset'))
async def reset_settings(bot, m):
    # Fetch default config from database logic (or hardcode fallback)
    # Using hardcoded minimal default to avoid import loops with database.py
    default_config = {
        'caption': None,
        'duplicate': True,
        'filters': {
            'poll': True, 'text': True, 'audio': True, 'voice': True, 'video': True,
            'photo': True, 'document': True, 'animation': True, 'sticker': True, 'link': True
        }
    }
    await db.update_configs(m.from_user.id, default_config)
    await m.reply("✅ Settings have been reset to default.")

@Client.on_message(filters.command('resetall') & filters.user(Config.BOT_OWNER))
async def reset_all_users(bot, message):
    sts = await message.reply("⏳ Resetting all users...")
    users = await db.get_all_users()
    
    success = 0
    failed = 0
    
    # Minimal Default
    default_config = {
        'caption': None,
        'duplicate': True,
        'filters': {
            'poll': True, 'text': True, 'audio': True, 'voice': True, 'video': True,
            'photo': True, 'document': True, 'animation': True, 'sticker': True, 'link': True
        }
    }
    
    async for user in users:
        try:
            await db.update_configs(user['id'], default_config)
            success += 1
        except Exception:
            failed += 1
            
    await sts.edit(
        f"<b>✅ Complete</b>\n\n"
        f"Success: {success}\n"
        f"Failed: {failed}"
    )
