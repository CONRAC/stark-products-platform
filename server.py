from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import pandas as pd
import aiofiles
from enum import Enum

# Import configuration
from config import settings, get_settings

# Import authentication
from auth_routes import auth_router, users_router

# Import quote routes
from routes.quotes import router as quotes_router

# Import company routes
from routes.companies import router as companies_router

# Import analytics routes
from routes.analytics import router as analytics_router

# MongoDB connection using settings
try:
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.db_name]
    logger.info(f"Connected to MongoDB: {settings.db_name}")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    client = None
    db = None

# Create the main app without a prefix
app = FastAPI(
    title="Stark Products API", 
    version=settings.api_version,
    debug=settings.debug,
    description="API for Stark Products - Premium Bathroom Accessories Management System"
)

# Create a router with the configured prefix
api_router = APIRouter(prefix=settings.api_prefix)

# Security
security = HTTPBearer()

# Email configuration using settings
mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

try:
    mail = FastMail(mail_config) if settings.email_configured else None
except Exception as e:
    logging.warning(f"Email configuration failed: {e}")
    mail = None

# Enums
class ProductCategory(str, Enum):
    TOWEL_RAILS = "Towel Rails"
    SHOWER_TRAYS = "Shower Trays" 
    SOAP_DISHES = "Soap Dishes"
    TOILET_ROLL_HOLDERS = "Toilet Roll Holders"
    BATHROOM_SHELVES = "Bathroom Shelves"
    GENERAL_ACCESSORIES = "General Bathroom Accessories"
    OTHER_PRODUCTS = "Other Products"

class QuoteStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"

# Models
class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    category: ProductCategory
    price_estimate: Optional[float] = None
    stock_quantity: int = 0
    images: List[str] = []
    specifications: Dict[str, Any] = {}
    dimensions: Optional[str] = None
    material: Optional[str] = None
    finish: Optional[str] = None
    mounting_system: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductCreate(BaseModel):
    name: str
    description: str
    category: ProductCategory
    price_estimate: Optional[float] = None
    stock_quantity: int = 0
    images: List[str] = []
    specifications: Dict[str, Any] = {}
    dimensions: Optional[str] = None
    material: Optional[str] = None
    finish: Optional[str] = None
    mounting_system: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ProductCategory] = None
    price_estimate: Optional[float] = None
    stock_quantity: Optional[int] = None
    images: Optional[List[str]] = None
    specifications: Optional[Dict[str, Any]] = None
    dimensions: Optional[str] = None
    material: Optional[str] = None
    finish: Optional[str] = None
    mounting_system: Optional[str] = None

class QuoteItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: Optional[float] = None

class CustomerInfo(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None

class Quote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_info: CustomerInfo
    items: List[QuoteItem]
    status: QuoteStatus = QuoteStatus.PENDING
    total_estimate: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class QuoteCreate(BaseModel):
    customer_info: CustomerInfo
    items: List[QuoteItem]
    notes: Optional[str] = None

class QuoteUpdate(BaseModel):
    customer_info: Optional[CustomerInfo] = None
    items: Optional[List[QuoteItem]] = None
    status: Optional[QuoteStatus] = None
    total_estimate: Optional[float] = None
    notes: Optional[str] = None

class StockUpdate(BaseModel):
    product_id: str
    stock_quantity: int

# Helper Functions
async def get_product_by_id(product_id: str) -> Optional[Product]:
    product_doc = await db.products.find_one({"id": product_id})
    if product_doc:
        return Product(**product_doc)
    return None

async def calculate_quote_total(items: List[QuoteItem]) -> float:
    total = 0.0
    for item in items:
        if item.unit_price:
            total += item.unit_price * item.quantity
    return total

# Basic Routes
@api_router.get("/")
async def root():
    return {"message": "Stark Products API - Bathroom Accessories Management System"}

@api_router.get("/health")
async def health_check():
    health_status = {"status": "healthy", "timestamp": datetime.utcnow()}
    
    # Check database connection
    if db is not None:
        try:
            await db.command("ping")
            health_status["database"] = "connected"
        except Exception as e:
            health_status["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["database"] = "not configured"
        health_status["status"] = "degraded"
    
    return health_status

# Simple health check at root level for Railway
@app.get("/health")
async def simple_health():
    return {"status": "ok"}

# Product Management Routes
@api_router.post("/products", response_model=Product)
async def create_product(product: ProductCreate):
    """Create a new product"""
    product_dict = product.dict()
    product_obj = Product(**product_dict)
    
    await db.products.insert_one(product_obj.dict())
    return product_obj

@api_router.get("/products", response_model=List[Product])
async def get_products(
    category: Optional[ProductCategory] = None,
    search: Optional[str] = None,
    in_stock_only: bool = False,
    limit: int = 50,
    offset: int = 0
):
    """Get all products with optional filtering"""
    query = {}
    
    if category:
        query["category"] = category
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    if in_stock_only:
        query["stock_quantity"] = {"$gt": 0}
    
    products = await db.products.find(query).skip(offset).limit(limit).to_list(limit)
    return [Product(**product) for product in products]

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get a specific product by ID"""
    product = await get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@api_router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, update_data: ProductUpdate):
    """Update a product"""
    existing_product = await get_product_by_id(product_id)
    if not existing_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.utcnow()
    
    await db.products.update_one({"id": product_id}, {"$set": update_dict})
    
    updated_product = await get_product_by_id(product_id)
    return updated_product

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    """Delete a product"""
    result = await db.products.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}

# Category Routes
@api_router.get("/categories")
async def get_categories():
    """Get all available product categories"""
    return [{"value": cat.value, "label": cat.value} for cat in ProductCategory]

@api_router.get("/categories/{category}/products", response_model=List[Product])
async def get_products_by_category(category: ProductCategory, limit: int = 50):
    """Get products by category"""
    products = await db.products.find({"category": category}).limit(limit).to_list(limit)
    return [Product(**product) for product in products]

# Legacy quote routes removed - using new quotes router with authentication

# Stock Management Routes
@api_router.post("/stock/update")
async def update_stock(stock_updates: List[StockUpdate]):
    """Update stock quantities for multiple products"""
    updated_count = 0
    
    for update in stock_updates:
        result = await db.products.update_one(
            {"id": update.product_id},
            {
                "$set": {
                    "stock_quantity": update.stock_quantity,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        if result.modified_count > 0:
            updated_count += 1
    
    return {"message": f"Updated stock for {updated_count} products"}

@api_router.post("/stock/import-csv")
async def import_stock_csv(file: UploadFile = File(...)):
    """Import stock data from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        contents = await file.read()
        df = pd.read_csv(pd.io.common.StringIO(contents.decode('utf-8')))
        
        # Expected columns: product_id, stock_quantity
        required_columns = ['product_id', 'stock_quantity']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must contain columns: {required_columns}"
            )
        
        updated_count = 0
        for _, row in df.iterrows():
            result = await db.products.update_one(
                {"id": str(row['product_id'])},
                {
                    "$set": {
                        "stock_quantity": int(row['stock_quantity']),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            if result.modified_count > 0:
                updated_count += 1
        
        return {
            "message": f"Successfully updated stock for {updated_count} products",
            "total_rows": len(df)
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")

@api_router.get("/stock/report")
async def get_stock_report():
    """Get stock report showing low stock items"""
    low_stock_products = await db.products.find(
        {"stock_quantity": {"$lt": settings.low_stock_threshold}}
    ).to_list(100)
    
    total_products = await db.products.count_documents({})
    out_of_stock = await db.products.count_documents({"stock_quantity": 0})
    
    return {
        "total_products": total_products,
        "out_of_stock": out_of_stock,
        "low_stock_items": [Product(**product) for product in low_stock_products],
        "low_stock_count": len(low_stock_products)
    }

# Email sending moved to new quotes router with authentication

# Include the routers in the main app
app.include_router(api_router)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(quotes_router, prefix=settings.api_prefix)
app.include_router(companies_router, prefix=settings.api_prefix)
app.include_router(analytics_router, prefix=settings.api_prefix)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at root
@app.get("/")
async def serve_home():
    return FileResponse('static/index.html')

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging is configured in config.py
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    if client:
        client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)