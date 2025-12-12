import asyncio
import logging
import pytz
from datetime import datetime
from logging.handlers import RotatingFileHandler
from hydrogram import Client, idle, types
from hydrogram.errors import FloodWait
from hydrogram.raw.types import ChannelForbidden # Monkeypatch ke liye
from typing import Union, Optional, AsyncGenerator
from config import Config
from plugins.regix import restart_forwards

# --- MONKEYPATCH (FIX FOR CRASH) ---
# Hydrogram bug fix: ChannelForbidden object needs 'verified' attribute
if not hasattr(ChannelForbidden, "verified"):
    setattr(ChannelForbidden, "verified", False)
# -----------------------------------

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("bot.log", maxBytes=5000000, backupCount=10),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("Forward-Bot")

# --- Advanced Bot Class ---
class VJBot(Client):
    def __init__(self):
        super().__init__(
            name="Forward-Bot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            sleep_threshold=120,
            plugins=dict(root="plugins"),
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        logger.info(f"Bot Started as {me.first_name} (@{me.username})")
        
        try:
            ist = pytz.timezone("Asia/Kolkata")
            now = datetime.now(ist)
            alert_msg = (
                f"<b>🟢 Service Restarted!</b>\n\n"
                f"<b>🤖 Bot:</b> @{me.username}\n"
                f"<b>📅 Date:</b> <code>{now.strftime('%d %B, %Y')}</code>\n"
                f"<b>⌚ Time:</b> <code>{now.strftime('%I:%M:%S %p')} IST</code>"
            )
            if Config.BOT_OWNER:
                await self.send_message(chat_id=Config.BOT_OWNER, text=alert_msg)
        except Exception as e:
            logger.warning(f"Failed to send start alert: {e}")

        try:
            await restart_forwards(self)
        except Exception as e:
            logger.error(f"Error during restart_forwards: {e}")

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot Stopped. Bye!")

    async def iter_messages(self, chat_id, limit, offset=0):
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0: return
            message_ids = list(range(current, current + new_diff + 1))
            try:
                messages = await self.get_messages(chat_id, message_ids)
                if not messages: return
                for message in messages:
                    if message: yield message
                    current += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                return

if __name__ == "__main__":
    try:
        bot = VJBot()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
