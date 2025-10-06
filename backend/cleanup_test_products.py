"""
Clean up test products with invalid data from MongoDB
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

async def cleanup_test_products():
    """Remove products with 'string' as name or description"""
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.db_name]
    
    print("🧹 Cleaning up test products...")
    
    # Delete products with 'string' values
    result = await db.products.delete_many({
        "$or": [
            {"name": "string"},
            {"description": "string"},
            {"material": "string"},
            {"finish": "string"}
        ]
    })
    
    print(f"✅ Removed {result.deleted_count} test products")
    
    # Count remaining products
    count = await db.products.count_documents({})
    print(f"📊 Total products remaining: {count}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(cleanup_test_products())
