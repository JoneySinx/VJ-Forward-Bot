import asyncio
import logging
import pytz # Timezone ke liye
from datetime import datetime
from logging.handlers import RotatingFileHandler
from hydrogram import Client, idle, types
from hydrogram.errors import FloodWait
from typing import Union, Optional, AsyncGenerator
from config import Config
from plugins.regix import restart_forwards

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
# Logger name cleaned
logger = logging.getLogger("Forward-Bot")

# --- Advanced Bot Class ---
class VJBot(Client):
    def __init__(self):
        super().__init__(
            name="Forward-Bot", # Clean Session Name
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            sleep_threshold=120,
            plugins=dict(root="plugins"),
        )

    async def start(self):
        """Runs when bot starts"""
        await super().start()
        me = await self.get_me()
        logger.info(f"Bot Started as {me.first_name} (@{me.username})")
        
        # --- Admin Alert Logic (IST Time) ---
        try:
            # Indian Timezone Set karein
            ist = pytz.timezone("Asia/Kolkata")
            now = datetime.now(ist)
            
            # Date aur Time format karein
            date_str = now.strftime("%d %B, %Y") # Ex: 12 December, 2025
            time_str = now.strftime("%I:%M:%S %p") # Ex: 10:30:00 PM
            
            # Message Text
            alert_msg = (
                f"<b>🟢 Service Restarted!</b>\n\n"
                f"<b>🤖 Bot:</b> @{me.username}\n"
                f"<b>📅 Date:</b> <code>{date_str}</code>\n"
                f"<b>⌚ Time:</b> <code>{time_str} IST</code>"
            )
            
            # Admin ko message bhejein
            if Config.BOT_OWNER:
                await self.send_message(chat_id=Config.BOT_OWNER, text=alert_msg)
                logger.info("Start alert sent to Admin.")
            else:
                logger.warning("BOT_OWNER ID not set in Config.")
                
        except Exception as e:
            logger.warning(f"Failed to send start alert: {e}")

        # --- Restart Pending Tasks ---
        try:
            await restart_forwards(self)
            logger.info("Restarted incomplete forwards successfully.")
        except Exception as e:
            logger.error(f"Error during restart_forwards: {e}")

    async def stop(self, *args):
        """Runs when bot stops"""
        await super().stop()
        logger.info("Bot Stopped. Bye!")

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            
            message_ids = list(range(current, current + new_diff + 1))
            
            try:
                messages = await self.get_messages(chat_id, message_ids)
                if not messages:
                    return

                for message in messages:
                    if message: 
                        yield message
                    current += 1
                    
            except FloodWait as e:
                logger.warning(f"FloodWait detected inside iter_messages. Sleeping for {e.value}s")
                await asyncio.sleep(e.value)
            except Exception as e:
                logger.error(f"Error in iter_messages: {e}")
                return

# --- Main Execution ---
if __name__ == "__main__":
    try:
        bot = VJBot()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
