"""
Database connection and utilities for MongoDB
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """MongoDB connection manager"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(settings.mongo_url)
            self.database = self.client[settings.db_name]
            
            # Test the connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {settings.db_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def get_database(self) -> AsyncIOMotorDatabase:
        """Get the database instance"""
        if not self.database:
            await self.connect()
        return self.database

# Global database connection instance
db_connection = DatabaseConnection()

async def get_database() -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return await db_connection.get_database()

async def init_database():
    """Initialize database connection"""
    await db_connection.connect()

async def close_database():
    """Close database connection"""
    await db_connection.disconnect()

# Export the main function
__all__ = ['get_database', 'init_database', 'close_database']
