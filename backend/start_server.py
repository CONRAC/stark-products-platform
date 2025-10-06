"""
Start Stark Products Server with visible output
"""

print("🚀 Starting Stark Products API Server...")
print("=" * 50)

# Import and setup
from config import settings
import uvicorn

print(f"📊 Database: {settings.db_name}")
print(f"🌐 Server will run at: http://localhost:8001")
print(f"📖 API Documentation: http://localhost:8001/docs")
print(f"🔧 Environment: {settings.environment}")
print("=" * 50)

print("🔄 Starting server... (Press Ctrl+C to stop)")
print("")

# Start the server
if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0", 
        port=8001, 
        reload=True,
        log_level="info"
    )
