
import re
import asyncio
import logging
from typing import Union, Optional, AsyncGenerator

# --- Hydrogram Imports ---
from hydrogram import Client, filters, types, enums
from hydrogram.errors import (
    FloodWait,
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

class ClientManager: 
    def __init__(self):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH

    async def add_bot(self, bot, user_id):
        """Add a forwarded bot token"""
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
        
        if not msg.forward_date:
            return await msg.reply("<b>Error:</b> Please forward the message directly from BotFather.")
        
        if msg.forward_from and msg.forward_from.id != 93372553:
             return await msg.reply("<b>Error:</b> This message is not from @BotFather.")

        bot_token_match = re.search(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', msg.text)
        bot_token = bot_token_match.group(0) if bot_token_match else None
        
        if not bot_token:
            return await msg.reply("<b>Error:</b> Could not find a valid Bot Token.")

        try:
            temp_client = Client("TempBot", api_id=self.api_id, api_hash=self.api_hash, bot_token=bot_token, in_memory=True)
            await temp_client.start()
            bot_info = temp_client.me
            await temp_client.stop()
        except Exception as e:
            return await msg.reply(f"<b>Invalid Token:</b> `{e}`")

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

    async def add_session(self, bot, user_id):
        """Add Userbot Session"""
        disclaimer = (
            "<b>⚠️ DISCLAIMER: Add Userbot</b>\n\n"
            "<b>Enter your Phone Number (with Country Code):</b>\n"
            "Example: `+919876543210`"
        )
        
        phone_msg = await bot.ask(chat_id=user_id, text=disclaimer)
        if phone_msg.text == '/cancel':
            return await phone_msg.reply('<b>Process Cancelled!</b>')
        
        phone_number = phone_msg.text.strip()
        client = Client(f"session_{user_id}", api_id=self.api_id, api_hash=self.api_hash, in_memory=True)
        await client.connect()
        
        try:
            status_msg = await phone_msg.reply("Sending OTP...")
            try:
                code_data = await client.send_code(phone_number)
            except PhoneNumberInvalid:
                return await status_msg.edit('<b>Error:</b> Invalid Phone Number.')
            except FloodWait as e:
                return await status_msg.edit(f'<b>Error:</b> FloodWait. Try again in {e.value} seconds.')

            otp_prompt = "<b>OTP Sent!</b>\nEnter code (e.g., `1 2 3 4 5`):"
            otp_msg = await bot.ask(user_id, otp_prompt, timeout=300)
            
            if otp_msg.text == '/cancel': return await otp_msg.reply('Cancelled.')

            phone_code = otp_msg.text.replace(" ", "")

            try:
                await client.sign_in(phone_number, code_data.phone_code_hash, phone_code)
            except PhoneCodeInvalid:
                return await otp_msg.reply('<b>Error:</b> Invalid OTP.')
            except PhoneCodeExpired:
                return await otp_msg.reply('<b>Error:</b> OTP Expired.')
            except SessionPasswordNeeded:
                pwd_msg = await bot.ask(user_id, '<b>Two-Step Verification Enabled.</b>\nEnter Password:', timeout=300)
                if pwd_msg.text == '/cancel': return await pwd_msg.reply('Cancelled.')
                try:
                    await client.check_password(password=pwd_msg.text)
                except PasswordHashInvalid:
                    return await pwd_msg.reply('<b>Error:</b> Wrong Password.')

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
            if client.is_connected:
                await client.disconnect()

# ==============================================================================
#  Helper Functions
# ==============================================================================

async def get_client(data, is_bot=True):
    if is_bot:
        return Client("WorkerBot", Config.API_ID, Config.API_HASH, bot_token=data, in_memory=True)
    else:
        return Client("WorkerUser", Config.API_ID, Config.API_HASH, session_string=data, in_memory=True)

async def iter_messages(client, chat_id, limit, offset=0, filters=None, max_size=None):
    """
    Super Optimized iterator with STRONG Anti-Flood delays
    """
    current = offset
    
    # Batch size reduced to 100 to stay safer
    BATCH_SIZE = 100 
    
    while True:
        current_limit = min(BATCH_SIZE, limit - current)
        if current_limit <= 0: return
        
        message_ids = list(range(current, current + current_limit + 1))
        
        try:
            messages = await client.get_messages(chat_id, message_ids)
        except FloodWait as e:
            # Smart Sleep: Wait longer if hit limit
            wait_time = e.value + 5
            logger.warning(f"FloodWait hit! Sleeping for {wait_time}s...")
            await asyncio.sleep(wait_time)
            continue
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return

        if not messages: return

        for message in messages:
            current += 1
            if not message: continue
            
            # Filter Logic
            is_filtered = False
            if filters:
                for media in ['photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation']:
                    if getattr(message, media, None) and media in filters:
                        is_filtered = True; break
                if message.text and 'text' in filters: is_filtered = True
                if not is_filtered and 'link' in filters:
                    entities = (message.entities or []) + (message.caption_entities or [])
                    for entity in entities:
                        if entity.type.name in ["URL", "TEXT_LINK"]:
                            is_filtered = True; break
            
            if is_filtered: yield "FILTERED"
            else: yield message
        
        # --- STRONG ANTI-FLOOD DELAY ---
        # Increased to 3 seconds between batches. 
        # Slower speed but safer from 28s bans.
        await asyncio.sleep(3) 

def parse_buttons(text, markup=True):
    if not text: return None
    buttons = []
    for match in BTN_URL_REGEX.finditer(text):
        btn = InlineKeyboardButton(text=match.group(2), url=match.group(3).replace(" ", ""))
        if bool(match.group(4)) and buttons: buttons[-1].append(btn)
        else: buttons.append([btn])
    if markup and buttons: return InlineKeyboardMarkup(buttons)
    return buttons if buttons else None
