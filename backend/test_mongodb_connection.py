"""
Test MongoDB Atlas Connection
Simple script to verify your database connection is working
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

async def test_connection():
    """Test MongoDB Atlas connection"""
    
    print("🔗 Testing MongoDB Atlas Connection...")
    print(f"Database: {settings.db_name}")
    print(f"Connection URL: {settings.mongo_url[:50]}..." if len(settings.mongo_url) > 50 else settings.mongo_url)
    
    try:
        # Create client
        client = AsyncIOMotorClient(settings.mongo_url)
        
        # Test connection
        print("\n📡 Attempting to connect...")
        await client.admin.command('ping')
        print("✅ MongoDB Atlas connection successful!")
        
        # Get database
        db = client[settings.db_name]
        
        # Test database access
        print(f"\n📊 Testing database '{settings.db_name}'...")
        collections = await db.list_collection_names()
        print(f"✅ Database access successful!")
        print(f"   Collections found: {len(collections)}")
        
        if collections:
            print(f"   Collection names: {', '.join(collections)}")
        else:
            print("   No collections yet (this is normal for a new database)")
        
        # Test write operation
        print(f"\n✍️ Testing write operation...")
        test_collection = db.connection_test
        
        result = await test_collection.insert_one({
            "test": True,
            "message": "MongoDB Atlas connection test",
            "timestamp": "2024-10-02T12:00:00Z"
        })
        
        print(f"✅ Write test successful! Document ID: {result.inserted_id}")
        
        # Clean up test document
        await test_collection.delete_one({"_id": result.inserted_id})
        print("🧹 Test document cleaned up")
        
        # Close connection
        client.close()
        
        print(f"\n🎉 All tests passed! Your MongoDB Atlas setup is ready!")
        print(f"\n🚀 Next steps:")
        print(f"   1. Your database '{settings.db_name}' is connected and ready")
        print(f"   2. You can now run: python server.py")
        print(f"   3. Visit: http://localhost:8001/docs to see your API")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print(f"\n🔧 Troubleshooting tips:")
        print(f"   1. Check your MongoDB Atlas connection string in .env file")
        print(f"   2. Make sure your IP address is whitelisted in Atlas")
        print(f"   3. Verify your username/password are correct")
        print(f"   4. Check if your cluster is running")
        
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
