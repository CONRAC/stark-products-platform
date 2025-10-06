#!/usr/bin/env python3
"""
Sample products script for Stark Products
Adds sample bathroom accessories to demonstrate the live stock functionality
"""

import asyncio
import json
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import uuid
from config import settings

# Sample products data based on real Stark Products categories
SAMPLE_PRODUCTS = [
    {
        "id": str(uuid.uuid4()),
        "name": "Premium Towel Rail - Single Bar 600mm",
        "description": "High-quality stainless steel towel rail with brushed finish. Perfect for modern bathrooms.",
        "category": "Towel Rails",
        "price_estimate": 299.99,
        "stock_quantity": 45,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Stainless Steel 304",
            "finish": "Brushed Satin",
            "width": "600mm",
            "depth": "120mm"
        },
        "dimensions": "600mm x 120mm x 50mm",
        "material": "Stainless Steel 304",
        "finish": "Brushed Satin",
        "mounting_system": "Wall-mounted with concealed fixings",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Premium Towel Rail - Double Bar 800mm", 
        "description": "Double bar towel rail for maximum towel capacity. Premium quality construction.",
        "category": "Towel Rails",
        "price_estimate": 449.99,
        "stock_quantity": 28,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Stainless Steel 304",
            "finish": "Brushed Satin", 
            "width": "800mm",
            "depth": "150mm"
        },
        "dimensions": "800mm x 150mm x 50mm",
        "material": "Stainless Steel 304",
        "finish": "Brushed Satin",
        "mounting_system": "Wall-mounted with concealed fixings",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Modern Toilet Roll Holder - Single",
        "description": "Contemporary toilet roll holder with smooth operation and elegant design.",
        "category": "Toilet Roll Holders", 
        "price_estimate": 149.99,
        "stock_quantity": 67,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Stainless Steel 304",
            "finish": "Brushed Satin",
            "width": "180mm",
            "depth": "80mm"
        },
        "dimensions": "180mm x 80mm x 50mm",
        "material": "Stainless Steel 304",
        "finish": "Brushed Satin", 
        "mounting_system": "Wall-mounted with concealed fixings",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Luxury Shower Tray - 1200x800mm",
        "description": "Premium acrylic shower tray with anti-slip surface and integrated waste.",
        "category": "Shower Trays",
        "price_estimate": 1299.99,
        "stock_quantity": 12,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Acrylic with reinforcement",
            "finish": "Gloss White",
            "length": "1200mm",
            "width": "800mm",
            "depth": "40mm"
        },
        "dimensions": "1200mm x 800mm x 40mm",
        "material": "Reinforced Acrylic",
        "finish": "Gloss White",
        "mounting_system": "Floor-mounted with adjustable legs",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Elegant Soap Dish - Wall Mounted",
        "description": "Sleek soap dish with drainage design. Easy to clean and maintain.",
        "category": "Soap Dishes",
        "price_estimate": 89.99,
        "stock_quantity": 89,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Stainless Steel 304",
            "finish": "Brushed Satin",
            "width": "120mm", 
            "depth": "90mm"
        },
        "dimensions": "120mm x 90mm x 30mm",
        "material": "Stainless Steel 304",
        "finish": "Brushed Satin",
        "mounting_system": "Wall-mounted with concealed fixings",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Corner Bathroom Shelf - Double Tier",
        "description": "Space-saving corner shelf with two tiers. Perfect for toiletries and accessories.",
        "category": "Bathroom Shelves",
        "price_estimate": 399.99,
        "stock_quantity": 23,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Stainless Steel 304", 
            "finish": "Brushed Satin",
            "width": "250mm",
            "depth": "250mm",
            "height": "400mm"
        },
        "dimensions": "250mm x 250mm x 400mm",
        "material": "Stainless Steel 304",
        "finish": "Brushed Satin",
        "mounting_system": "Corner-mounted with wall fixings",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Professional Towel Rail - Extra Long 1000mm",
        "description": "Extra long towel rail for commercial or large residential bathrooms.",
        "category": "Towel Rails",
        "price_estimate": 599.99,
        "stock_quantity": 16,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Stainless Steel 316",
            "finish": "Brushed Satin",
            "width": "1000mm",
            "depth": "120mm"
        },
        "dimensions": "1000mm x 120mm x 50mm",
        "material": "Stainless Steel 316",
        "finish": "Brushed Satin",
        "mounting_system": "Wall-mounted with heavy-duty fixings",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Premium Shower Tray - Compact 900x900mm",
        "description": "Compact square shower tray ideal for smaller bathrooms. High-quality finish.",
        "category": "Shower Trays",
        "price_estimate": 899.99,
        "stock_quantity": 8,
        "images": ["https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3"],
        "specifications": {
            "material": "Acrylic with reinforcement",
            "finish": "Gloss White", 
            "length": "900mm",
            "width": "900mm",
            "depth": "40mm"
        },
        "dimensions": "900mm x 900mm x 40mm",
        "material": "Reinforced Acrylic",
        "finish": "Gloss White",
        "mounting_system": "Floor-mounted with adjustable legs",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
]

async def add_sample_products():
    """Add sample products to the database"""
    print("🚀 Adding sample products to Stark Products database...")
    print("=" * 60)
    
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.mongo_url)
        db = client[settings.db_name]
        
        # Check if products already exist
        existing_count = await db.products.count_documents({})
        print(f"📊 Current products in database: {existing_count}")
        
        if existing_count > 0:
            print("❓ Products already exist. Do you want to:")
            print("1. Add new products alongside existing ones")
            print("2. Replace all existing products") 
            print("3. Cancel operation")
            choice = input("Enter your choice (1/2/3): ").strip()
            
            if choice == "2":
                await db.products.delete_many({})
                print("🗑️  Deleted all existing products")
            elif choice == "3":
                print("❌ Operation cancelled")
                return
            # For choice "1" or any other input, continue with adding products
        
        # Insert sample products
        result = await db.products.insert_many(SAMPLE_PRODUCTS)
        
        print(f"✅ Successfully added {len(result.inserted_ids)} sample products!")
        print("\n📦 Added products:")
        for product in SAMPLE_PRODUCTS:
            stock_status = f"({product['stock_quantity']} in stock)" if product['stock_quantity'] > 0 else "(Out of stock)"
            print(f"   • {product['name']} - R{product['price_estimate']:.2f} {stock_status}")
        
        print(f"\n🌐 Your website at stark_products_website.html should now show live stock data!")
        print(f"📖 API docs available at: http://localhost:8001/docs")
        
    except Exception as e:
        print(f"❌ Error adding sample products: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(add_sample_products())
