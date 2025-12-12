import motor.motor_asyncio
from config import Config

class Db:
    # --- Default Configurations (Memory Optimized) ---
    DEFAULT_CONFIG = {
        'caption': None,
        'duplicate': True,
        'forward_tag': False,
        'min_size': 0,
        'max_size': 0,
        'extension': None,
        'keywords': None,
        'protect': None,
        'button': None,
        'db_uri': None,
        'skip_duplicate': False,
        'filters': {
            'poll': True,
            'text': True,
            'audio': True,
            'voice': True,
            'video': True,
            'photo': True,
            'document': True,
            'animation': True,
            'sticker': True
        }
    }

    DEFAULT_FORWARD_DETAILS = {
        'chat_id': None,
        'forward_id': None,
        'toid': None,
        'last_id': None,
        'limit': None,
        'msg_id': None,
        'start_time': None,
        'fetched': 0,
        'offset': 0,
        'deleted': 0,
        'total': 0,
        'duplicate': 0,
        'skip': 0,
        'filtered': 0
    }

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        # Collections
        self.bot = self.db.bots
        self.userbot = self.db.userbot
        self.col = self.db.users
        self.nfy = self.db.notify  # Forwarding Tasks
        self.chl = self.db.channels

    # ==========================
    #  User Management
    # ==========================
    
    async def add_user(self, user_id, name):
        """Add a new user if they don't exist"""
        if not await self.is_user_exist(user_id):
            user = {
                'id': int(user_id),
                'name': name,
                'ban_status': {'is_banned': False, 'ban_reason': ""},
                'configs': self.DEFAULT_CONFIG.copy()
            }
            await self.col.insert_one(user)

    async def is_user_exist(self, user_id):
        user = await self.col.find_one({'id': int(user_id)})
        return bool(user)

    async def total_users_bots_count(self):
        """Get stats for Bot Status"""
        bcount = await self.bot.count_documents({})
        ucount = await self.col.count_documents({})
        return ucount, bcount

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    # ==========================
    #  Ban Logic
    # ==========================

    async def remove_ban(self, user_id):
        await self.col.update_one(
            {'id': int(user_id)}, 
            {'$set': {'ban_status': {'is_banned': False, 'ban_reason': ''}}}
        )

    async def ban_user(self, user_id, ban_reason="No Reason"):
        await self.col.update_one(
            {'id': int(user_id)}, 
            {'$set': {'ban_status': {'is_banned': True, 'ban_reason': ban_reason}}}
        )

    async def get_ban_status(self, user_id):
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return {'is_banned': False, 'ban_reason': ''}
        return user.get('ban_status', {'is_banned': False, 'ban_reason': ''})

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        return [user['id'] async for user in users]

    # ==========================
    #  Configurations
    # ==========================

    async def update_configs(self, user_id, configs):
        await self.col.update_one({'id': int(user_id)}, {'$set': {'configs': configs}})

    async def get_configs(self, user_id):
        user = await self.col.find_one({'id': int(user_id)})
        if user and 'configs' in user:
            # Merge with default to ensure new keys exist if schema changes
            config = self.DEFAULT_CONFIG.copy()
            config.update(user['configs'])
            return config
        return self.DEFAULT_CONFIG.copy()

    async def get_filters(self, user_id):
        """Returns list of disabled filters"""
        filters_list = []
        user_config = await self.get_configs(user_id)
        filters = user_config.get('filters', {})
        
        for k, v in filters.items():
            if v is False: # Check explicitly for False
                filters_list.append(str(k))
        return filters_list

    # ==========================
    #  Bots & Userbots
    # ==========================

    async def add_bot(self, datas):
        if not await self.is_bot_exist(datas['user_id']):
            await self.bot.insert_one(datas)

    async def remove_bot(self, user_id):
        await self.bot.delete_many({'user_id': int(user_id)})

    async def get_bot(self, user_id):
        return await self.bot.find_one({'user_id': int(user_id)})

    async def is_bot_exist(self, user_id):
        return bool(await self.bot.find_one({'user_id': int(user_id)}))
   
    async def add_userbot(self, datas):
        if not await self.is_userbot_exist(datas['user_id']):
            await self.userbot.insert_one(datas)

    async def remove_userbot(self, user_id):
        await self.userbot.delete_many({'user_id': int(user_id)})

    async def get_userbot(self, user_id):
        return await self.userbot.find_one({'user_id': int(user_id)})

    async def is_userbot_exist(self, user_id):
        return bool(await self.userbot.find_one({'user_id': int(user_id)}))
    
    # ==========================
    #  Channels
    # ==========================

    async def in_channel(self, user_id, chat_id):
        return bool(await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)}))

    async def add_channel(self, user_id, chat_id, title, username):
        if await self.in_channel(user_id, chat_id):
            return False
        return await self.chl.insert_one({
            "user_id": int(user_id), 
            "chat_id": int(chat_id), 
            "title": title, 
            "username": username
        })

    async def remove_channel(self, user_id, chat_id):
        if not await self.in_channel(user_id, chat_id):
            return False
        return await self.chl.delete_many({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_channel_details(self, user_id, chat_id):
        return await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_user_channels(self, user_id):
        channels = self.chl.find({"user_id": int(user_id)})
        return [channel async for channel in channels]

    # ==========================
    #  Forwarding Tasks
    # ==========================

    async def add_frwd(self, user_id):
        """Mark user as active forwarding"""
        # Use upsert to prevent duplicates
        await self.nfy.update_one(
            {'user_id': int(user_id)}, 
            {'$set': {'user_id': int(user_id)}}, 
            upsert=True
        )

    async def rmve_frwd(self, user_id=0, all_users=False):
        if all_users:
            return await self.nfy.delete_many({})
        return await self.nfy.delete_many({'user_id': int(user_id)})

    async def get_all_frwd(self):
        return self.nfy.find({})
  
    async def forward_count(self):
        return await self.nfy.count_documents({})
        
    async def is_forwad_exit(self, user_id):
        """Check if user has active forward task"""
        return bool(await self.nfy.find_one({'user_id': int(user_id)}))
        
    async def get_forward_details(self, user_id):
        user = await self.nfy.find_one({'user_id': int(user_id)})
        if user and 'details' in user:
            return user['details']
        return self.DEFAULT_FORWARD_DETAILS.copy()
   
    async def update_forward(self, user_id, details):
        await self.nfy.update_one(
            {'user_id': int(user_id)}, 
            {'$set': {'details': details}},
            upsert=True
        )

# --- Initialize Database ---
db = Db(Config.DATABASE_URI, Config.DATABASE_NAME)
