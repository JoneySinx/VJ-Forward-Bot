import time
from database import db
from .test import parse_buttons

# Global Dictionary to hold active task status in memory
STATUS = {}

class STS:
    def __init__(self, task_id):
        self.id = task_id
        self.data = STATUS

    def verify(self):
        """Check if the task ID exists in memory"""
        return self.data.get(self.id)

    def store(self, from_chat, to_chat, skip, limit):
        """Initialize a new task"""
        self.data[self.id] = {
            "FROM": from_chat, 
            'TO': to_chat, 
            'total_files': 0, 
            'skip': skip, 
            'limit': limit,
            'fetched': skip, 
            'filtered': 0, 
            'deleted': 0, 
            'duplicate': 0, 
            'total': limit, 
            'start': 0
        }
        self.get(full=True)
        return self

    def get(self, value=None, full=False):
        """Retrieve task data. If full=True, sets attributes to self."""
        values = self.data.get(self.id)
        
        if not values:
            return None

        if not full:
            return values.get(value)
            
        # Dynamically set attributes for easier access (e.g., self.fetched)
        for k, v in values.items():
            setattr(self, k, v)
        return self

    # --- FIX: Changed 'time_update' back to 'time' ---
    def add(self, key=None, value=1, time=False, start_time=None):
        """Update counters or start time"""
        if self.id not in self.data:
            return

        if time:
            current_time = start_time if start_time is not None else __import__('time').time()
            self.data[self.id].update({'start': current_time})
        else:
            current_val = self.data[self.id].get(key, 0)
            self.data[self.id].update({key: current_val + value})

    def divide(self, num, by):
        """Safe division to avoid ZeroDivisionError"""
        if not by or int(by) == 0:
            by = 1
        return int(num) / by

    def delete(self):
        """Clears the task from memory (Important for RAM optimization)"""
        if self.id in self.data:
            del self.data[self.id]

    async def get_data(self, user_id):
        """Fetches all necessary settings for the user"""
        # 1. Get Bot or Userbot
        bot = await db.get_bot(user_id)
        if bot is None:
            bot = await db.get_userbot(user_id)
            
        # 2. Get Filters and Configs
        filters = await db.get_filters(user_id)
        configs = await db.get_configs(user_id)
        
        # 3. Process Configs
        min_size = configs.get('min_size', 0)
        max_size = configs.get('max_size', 0)
        
        # Check Duplicate Logic
        skip_dup = bool(configs.get('duplicate'))
        
        # Parse Custom Buttons
        raw_button = configs.get('button', '')
        button = parse_buttons(raw_button) if raw_button else None

        # Prepared Data Dictionary
        datas = {
            'filters': filters,
            'keywords': configs.get('keywords'),
            'min_size': min_size,
            'max_size': max_size,
            'extensions': configs.get('extension'),
            'skip_duplicate': skip_dup,
            'db_uri': configs.get('db_uri')
        }

        return (
            bot, 
            configs.get('caption'), 
            configs.get('forward_tag'), 
            datas, 
            configs.get('protect'), 
            button
        )
