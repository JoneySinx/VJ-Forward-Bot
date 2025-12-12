import os
from os import environ

class Config:
    # Telegram API Credentials
    # Get these from https://my.telegram.org
    API_ID = int(environ.get("API_ID", "0")) 
    API_HASH = environ.get("API_HASH", "")
    BOT_TOKEN = environ.get("BOT_TOKEN", "") 
    
    # Session Name (Useful if using string sessions)
    BOT_SESSION = environ.get("BOT_SESSION", "vjbot") 
    
    # Database Configuration (MongoDB)
    DATABASE_URI = environ.get("DATABASE_URI", "")
    DATABASE_NAME = environ.get("DATABASE_NAME", "vj-forward-bot")
    
    # Owner ID (Admin)
    # Default to 0 to prevent crash if not set
    BOT_OWNER = int(environ.get("BOT_OWNER", "0"))

class Temp(object): 
    # Runtime Variables (बोट चलते समय ये डेटा hold करेंगे)
    LOCK = {}           # Lock for chat processes
    CANCEL = {}         # To handle cancellation requests
    FORWARDINGS = 0     # Counter for active forwards
    BANNED_USERS = []   # List of banned users
    IS_FRWD_CHAT = []   # List of chats currently forwarding
