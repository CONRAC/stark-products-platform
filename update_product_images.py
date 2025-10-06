"""
Update product images with better bathroom accessory photos
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

# Better image URLs for bathroom accessories
PRODUCT_IMAGES = {
    "towel": [
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1620626011761-996317b8d101?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1542718610-a1d656d1884c?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80"
    ],
    "toilet": [
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1561070791-2526d30994b5?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80"
    ],
    "shower": [
        "https://images.unsplash.com/photo-1620626011761-996317b8d101?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1540932239986-30128078f3c5?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80"
    ],
    "soap": [
        "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1596462502278-27bfdc403348?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80"
    ],
    "shelf": [
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1620626011761-996317b8d101?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80"
    ]
}

async def update_product_images():
    """Update product images based on product names"""
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.db_name]
    
    print("🖼️  Updating product images...")
    
    # Get all products
    products = await db.products.find({}).to_list(None)
    
    updated_count = 0
    for product in products:
        name = product.get('name', '').lower()
        new_images = []
        
        if 'towel' in name:
            new_images = PRODUCT_IMAGES['towel']
        elif 'toilet' in name:
            new_images = PRODUCT_IMAGES['toilet']
        elif 'shower' in name:
            new_images = PRODUCT_IMAGES['shower']
        elif 'soap' in name:
            new_images = PRODUCT_IMAGES['soap']
        elif 'shelf' in name:
            new_images = PRODUCT_IMAGES['shelf']
        else:
            # Default bathroom image
            new_images = ["https://images.unsplash.com/photo-1620626011761-996317b8d101?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80"]
        
        # Update the product
        await db.products.update_one(
            {"id": product["id"]},
            {"$set": {"images": new_images}}
        )
        updated_count += 1
        print(f"   ✅ Updated {product.get('name', 'Unknown')}")
    
    print(f"🎉 Successfully updated images for {updated_count} products!")
    client.close()

if __name__ == "__main__":
    asyncio.run(update_product_images())
