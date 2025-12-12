import asyncio
import logging
from logging.handlers import RotatingFileHandler
from typing import Union, Optional, AsyncGenerator

# --- Hydrogram Imports ---
from hydrogram import Client, idle, types
from hydrogram.errors import FloodWait

# --- Custom Modules ---
from config import Config
from plugins.regix import restart_forwards

# --- Logging Configuration ---
# लॉगिंग सेट की गई है ताकि एरर आने पर पता चल सके
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("bot.log", maxBytes=5000000, backupCount=10),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("VJ-Forward-Bot")

# --- Advanced Bot Class (Hydrogram) ---
class VJBot(Client):
    def __init__(self):
        super().__init__(
            name="VJ-Forward-Bot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            sleep_threshold=120,
            plugins=dict(root="plugins"),
        )

    async def start(self):
        """बोट स्टार्ट होने पर यह फंक्शन चलेगा"""
        await super().start()
        me = await self.get_me()
        logger.info(f"Bot Started as {me.first_name} (@{me.username})")
        
        # पिछले अधूरे काम को रीस्टार्ट करना
        try:
            await restart_forwards(self)
            logger.info("Restarted incomplete forwards successfully.")
        except Exception as e:
            logger.error(f"Error during restart_forwards: {e}")

    async def stop(self, *args):
        """बोट बंद होने पर यह फंक्शन चलेगा"""
        await super().stop()
        logger.info("Bot Stopped. Bye!")

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """
        यह फंक्शन मैसेज को एक-एक करके (Sequential) fetch करता है।
        Hydrogram में यह बड़े चैट्स को हैंडल करने के लिए बहुत अच्छा है।
        """
        current = offset
        while True:
            # एक बार में 200 मैसेज की लिमिट (Telegram API Limit)
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            
            # IDs की लिस्ट बनाना (Example: 100, 101, 102...)
            message_ids = list(range(current, current + new_diff + 1))
            
            try:
                # message_ids के जरिए मैसेज गेट करना
                messages = await self.get_messages(chat_id, message_ids)
                
                # अगर messages खाली है या None है
                if not messages:
                    return

                for message in messages:
                    # कभी-कभी डिलीटेड मैसेज के कारण None आ सकता है
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
        # बोट का ऑब्जेक्ट बनाना और स्टार्ट करना
        bot = VJBot()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
