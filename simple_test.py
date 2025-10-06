"""
Simple test to see what's wrong with the server
"""

print("🔍 Testing what's wrong...")

try:
    print("1. Testing config import...")
    from config import settings
    print("✅ Config works!")
    print(f"   Database: {settings.db_name}")
    
    print("\n2. Testing database connection...")
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncio
    
    async def test_db():
        client = AsyncIOMotorClient(settings.mongo_url)
        await client.admin.command('ping')
        client.close()
        return True
    
    result = asyncio.run(test_db())
    print("✅ Database connection works!")
    
    print("\n3. Testing server import...")
    import server
    print("✅ Server import works!")
    
    print("\n4. Testing app creation...")
    app = server.app
    print("✅ FastAPI app created!")
    
    print("\n🎉 Everything looks good! Let's start the server...")
    
except Exception as e:
    print(f"❌ Error found: {str(e)}")
    print(f"   Type: {type(e).__name__}")
    
    import traceback
    traceback.print_exc()

print("\n💡 Next: Try running the server manually...")
