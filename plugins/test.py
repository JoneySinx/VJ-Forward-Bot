import re
import asyncio
import logging
import random
from typing import Union, Optional, AsyncGenerator
from hydrogram import Client
from hydrogram.errors import FloodWait
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database import db
from config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)]\[buttonurl:/{0,2}(.+?)(:same)?])")

class ClientManager: 
    def __init__(self):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH

    async def add_bot(self, bot, user_id):
        prompt = "<b>🤖 Add Bot Mode</b>\nForward API Token from @BotFather."
        msg = await bot.ask(chat_id=user_id, text=prompt)
        if msg.text == '/cancel': return await msg.reply('Cancelled!')
        if not msg.forward_date: return await msg.reply("Error: Forward directly from BotFather.")
        
        bot_token_match = re.search(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', msg.text)
        bot_token = bot_token_match.group(0) if bot_token_match else None
        if not bot_token: return await msg.reply("Error: Invalid Token.")
        
        try:
            temp = Client("Temp", self.api_id, self.api_hash, bot_token=bot_token, in_memory=True)
            await temp.start(); info = temp.me; await temp.stop()
        except Exception as e: return await msg.reply(f"Invalid: {e}")

        await db.add_bot({'id': info.id, 'is_bot': True, 'user_id': user_id, 'name': info.first_name, 'token': bot_token, 'username': info.username})
        return True

    async def add_session(self, bot, user_id):
        disclaimer = "<b>Enter Phone Number:</b>\nExample: `+919876543210`"
        phone_msg = await bot.ask(chat_id=user_id, text=disclaimer)
        if phone_msg.text == '/cancel': return await phone_msg.reply('Cancelled!')
        
        client = Client(f"s_{user_id}", self.api_id, self.api_hash, in_memory=True)
        await client.connect()
        try:
            code = await client.send_code(phone_msg.text.strip())
            otp = await bot.ask(user_id, "Enter OTP (e.g. 1 2 3 4 5):", timeout=300)
            if otp.text == '/cancel': return await otp.reply('Cancelled.')
            try:
                await client.sign_in(phone_msg.text.strip(), code.phone_code_hash, otp.text.replace(" ", ""))
            except SessionPasswordNeeded:
                pwd = await bot.ask(user_id, "Enter 2FA Password:")
                await client.check_password(password=pwd.text)
            
            sess = await client.export_session_string()
            me = await client.get_me()
            await db.add_userbot({'id': me.id, 'is_bot': False, 'user_id': user_id, 'name': me.first_name, 'session': sess, 'username': me.username})
            return True
        except Exception as e:
            await bot.send_message(user_id, f"Error: {e}")
        finally:
            if client.is_connected: await client.disconnect()

async def get_client(data, is_bot=True):
    if is_bot: return Client("WB", Config.API_ID, Config.API_HASH, bot_token=data, in_memory=True)
    return Client("WU", Config.API_ID, Config.API_HASH, session_string=data, in_memory=True)

async def iter_messages(client, chat_id, limit, offset=0, filters=None, max_size=None):
    current = offset
    BATCH_SIZE = 100 
    
    while True:
        current_limit = min(BATCH_SIZE, limit - current)
        if current_limit <= 0: return
        
        message_ids = list(range(current, current + current_limit + 1))
        
        try:
            messages = await client.get_messages(chat_id, message_ids)
        except FloodWait as e:
            wait = e.value + random.randint(10, 20) # Extra safety on FloodWait
            logger.warning(f"FloodWait! Sleeping {wait}s")
            await asyncio.sleep(wait)
            continue
        except Exception: return

        if not messages: return

        for message in messages:
            current += 1
            if not message: continue
            
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
        
        # --- ULTRA SAFE DELAY (Fetching) ---
        # 5 se 10 second ka random delay har batch ke baad
        await asyncio.sleep(random.randint(5, 10))

def parse_buttons(text, markup=True):
    if not text: return None
    buttons = []
    for match in BTN_URL_REGEX.finditer(text):
        btn = InlineKeyboardButton(text=match.group(2), url=match.group(3).replace(" ", ""))
        if bool(match.group(4)) and buttons: buttons[-1].append(btn)
        else: buttons.append([btn])
    if markup and buttons: return InlineKeyboardMarkup(buttons)
    return buttons if buttons else None

