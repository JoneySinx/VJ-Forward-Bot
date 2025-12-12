import motor.motor_asyncio
import logging

# Logger Setup
logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self, uri, db_name, collection_name):
        self.uri = uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = None
        self.db = None
        self.files = None

    async def connect(self):
        """Establishes connection and verifies it"""
        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(self.uri)
            # Verify connection using a ping command
            await self.client.admin.command('ping')
            
            self.db = self.client[self.db_name]
            self.files = self.db[self.collection_name]
            return True
        except Exception as e:
            logger.error(f"Failed to connect to User DB: {e}")
            return False

    async def close(self):
        """Closes the connection"""
        if self.client:
            self.client.close()

    async def add_file(self, file_id):
        """Adds a file ID to the collection"""
        try:
            await self.files.insert_one({"file_id": file_id})
        except Exception:
            pass

    async def is_file_exist(self, file_id):
        """Checks if file ID exists"""
        f = await self.files.find_one({"file_id": file_id})
        return bool(f)
        
    async def get_all_files(self):
        """Returns all stored file IDs"""
        return self.files.find({})
        
    async def drop_all(self):
        """Deletes the entire collection (Clean up)"""
        await self.files.drop()

# ==============================================================================
#  Helper Function to Initialize Connection
# ==============================================================================

async def connect_user_db(user_id, uri, chat_id):
    """
    Connects to a user-provided MongoDB URI.
    Returns: (is_connected: bool, db_instance: MongoDB)
    """
    # Create unique DB and Collection names
    # Using specific names prevents mixing data between different tasks
    collection_name = f"task_{chat_id}" 
    db_name = f"ForwardBot_User_{user_id}"
    
    db = MongoDB(uri, db_name, collection_name)
    
    is_connected = await db.connect()
    
    return is_connected, db
