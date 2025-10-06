"""
Quote Management API Routes
Handles creation, management, and PDF generation of B2B quotes
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from bson import ObjectId
import io

from database import get_database
from auth import get_current_user, require_role
from pdf_service import pdf_generator
from models.base import ObjectIdStr
from models.auth import User
from services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quotes", tags=["quotes"])

# Pydantic Models

class QuoteItemRequest(BaseModel):
    """Individual item in a quote request"""
    product_id: ObjectIdStr
    product_name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., gt=0)
    unit_price: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)

class CustomerInfo(BaseModel):
    """Customer information for quotes"""
    name: str = Field(..., min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    email: str = Field(..., min_length=5, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)

class QuoteRequest(BaseModel):
    """Request to create a new quote"""
    customer_info: CustomerInfo
    items: List[QuoteItemRequest] = Field(..., min_items=1)
    notes: Optional[str] = Field(None, max_length=1000)
    requested_delivery_date: Optional[datetime] = None

class QuoteUpdate(BaseModel):
    """Request to update an existing quote"""
    customer_info: Optional[CustomerInfo] = None
    items: Optional[List[QuoteItemRequest]] = None
    status: Optional[str] = Field(None, pattern="^(draft|pending|approved|rejected|expired)$")
    notes: Optional[str] = Field(None, max_length=1000)
    admin_notes: Optional[str] = Field(None, max_length=1000)
    total_estimate: Optional[float] = Field(None, ge=0)

class QuoteResponse(BaseModel):
    """Quote response model"""
    id: ObjectIdStr
    customer_info: CustomerInfo
    items: List[QuoteItemRequest]
    status: str
    total_estimate: Optional[float]
    notes: Optional[str]
    admin_notes: Optional[str]
    created_by: ObjectIdStr
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    requested_delivery_date: Optional[datetime]

# Helper Functions

async def get_quote_by_id(quote_id: str, db) -> Optional[Dict[str, Any]]:
    """Retrieve a quote by ID"""
    try:
        quote = await db.quotes.find_one({"_id": ObjectId(quote_id)})
        return quote
    except Exception as e:
        logger.error(f"Error fetching quote {quote_id}: {str(e)}")
        return None

async def get_products_for_quote(items: List[QuoteItemRequest], db) -> List[Dict[str, Any]]:
    """Fetch product details for quote items"""
    product_ids = [ObjectId(item.product_id) for item in items]
    
    try:
        cursor = db.products.find({"_id": {"$in": product_ids}})
        products = await cursor.to_list(length=None)
        return products
    except Exception as e:
        logger.error(f"Error fetching products for quote: {str(e)}")
        return []

def calculate_quote_total(items: List[QuoteItemRequest]) -> Optional[float]:
    """Calculate total estimate for quote items"""
    total = 0.0
    has_pricing = False
    
    for item in items:
        if item.unit_price is not None:
            total += item.unit_price * item.quantity
            has_pricing = True
    
    return total if has_pricing else None

async def can_access_quote(quote: Dict[str, Any], user: User, db=None) -> bool:
    """Check if user can access a quote"""
    # Admins and managers can access all quotes
    if user.role in ['admin', 'manager']:
        return True
    
    # Users can access their own quotes
    if str(quote.get('created_by')) == str(user.id):
        return True
    
    # Company-based access control for shared quotes
    if user.company_id and db:
        try:
            # Get the company information
            company = await db.companies.find_one({"_id": ObjectId(user.company_id)})
            
            # Check if quote sharing is enabled for the company
            if company and company.get("quote_sharing_enabled", True):
                # Get the quote creator's user info
                quote_creator = await db.users.find_one({"_id": ObjectId(quote.get('created_by'))})
                
                # Allow access if the quote creator is from the same company
                if (quote_creator and 
                    quote_creator.get('company_id') == user.company_id):
                    return True
        except Exception as e:
            logger.error(f"Error checking company quote access: {str(e)}")
    
    return False

# API Endpoints

@router.post("/", response_model=QuoteResponse)
async def create_quote(
    quote_request: QuoteRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Create a new quote"""
    try:
        # Calculate total if prices are provided
        total_estimate = calculate_quote_total(quote_request.items)
        
        # Create quote document
        quote_doc = {
            "customer_info": quote_request.customer_info.dict(),
            "items": [item.dict() for item in quote_request.items],
            "status": "draft",
            "total_estimate": total_estimate,
            "notes": quote_request.notes,
            "admin_notes": None,
            "created_by": ObjectId(current_user.id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "requested_delivery_date": quote_request.requested_delivery_date
        }
        
        # Insert quote
        result = await db.quotes.insert_one(quote_doc)
        quote_doc["_id"] = result.inserted_id
        
        # Convert ObjectIds to strings for response
        quote_doc["id"] = str(quote_doc["_id"])
        quote_doc["created_by"] = str(quote_doc["created_by"])
        
        logger.info(f"Quote created: {quote_doc['id']} by user {current_user.email}")
        
        return QuoteResponse(**quote_doc)
        
    except Exception as e:
        logger.error(f"Error creating quote: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create quote")

@router.get("/", response_model=List[QuoteResponse])
async def list_quotes(
    status: Optional[str] = None,
    customer_email: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """List quotes with optional filtering"""
    try:
        # Build query filter
        query = {}
        
        # Role-based filtering
        if current_user.role not in ['admin', 'manager']:
            query["created_by"] = ObjectId(current_user.id)
        
        if status:
            query["status"] = status
            
        if customer_email:
            query["customer_info.email"] = {"$regex": customer_email, "$options": "i"}
        
        # Execute query
        cursor = db.quotes.find(query).skip(skip).limit(limit).sort("created_at", -1)
        quotes = await cursor.to_list(length=None)
        
        # Convert ObjectIds to strings
        response_quotes = []
        for quote in quotes:
            quote["id"] = str(quote["_id"])
            quote["created_by"] = str(quote["created_by"])
            response_quotes.append(QuoteResponse(**quote))
        
        return response_quotes
        
    except Exception as e:
        logger.error(f"Error listing quotes: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quotes")

@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get a specific quote by ID"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check access permissions
        if not await can_access_quote(quote, current_user, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Convert ObjectIds to strings
        quote["id"] = str(quote["_id"])
        quote["created_by"] = str(quote["created_by"])
        
        return QuoteResponse(**quote)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving quote {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quote")

@router.put("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: str,
    quote_update: QuoteUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Update an existing quote"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check permissions - only creator, admin, or manager can update
        if (str(quote.get('created_by')) != str(current_user.id) and 
            current_user.role not in ['admin', 'manager']):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Build update document
        update_doc = {"updated_at": datetime.utcnow()}
        
        if quote_update.customer_info:
            update_doc["customer_info"] = quote_update.customer_info.dict()
        
        if quote_update.items:
            update_doc["items"] = [item.dict() for item in quote_update.items]
            # Recalculate total if items changed
            update_doc["total_estimate"] = calculate_quote_total(quote_update.items)
        
        if quote_update.status is not None:
            update_doc["status"] = quote_update.status
        
        if quote_update.notes is not None:
            update_doc["notes"] = quote_update.notes
        
        # Only admin/manager can update admin notes and pricing
        if current_user.role in ['admin', 'manager']:
            if quote_update.admin_notes is not None:
                update_doc["admin_notes"] = quote_update.admin_notes
            
            if quote_update.total_estimate is not None:
                update_doc["total_estimate"] = quote_update.total_estimate
        
        # Update quote
        await db.quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": update_doc}
        )
        
        # Fetch updated quote
        updated_quote = await get_quote_by_id(quote_id, db)
        updated_quote["id"] = str(updated_quote["_id"])
        updated_quote["created_by"] = str(updated_quote["created_by"])
        
        logger.info(f"Quote updated: {quote_id} by user {current_user.email}")
        
        return QuoteResponse(**updated_quote)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating quote {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update quote")

@router.delete("/{quote_id}")
async def delete_quote(
    quote_id: str,
    current_user: User = Depends(require_role(['admin', 'manager'])),
    db=Depends(get_database)
):
    """Delete a quote (admin/manager only)"""
    try:
        result = await db.quotes.delete_one({"_id": ObjectId(quote_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        logger.info(f"Quote deleted: {quote_id} by user {current_user.email}")
        
        return {"message": "Quote deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting quote {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete quote")

@router.get("/{quote_id}/pdf")
async def download_quote_pdf(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Generate and download PDF for a quote"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check access permissions
        if not await can_access_quote(quote, current_user, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get product details for the quote
        products_data = await get_products_for_quote(
            [QuoteItemRequest(**item) for item in quote["items"]], 
            db
        )
        
        # Generate PDF
        pdf_bytes = await pdf_generator.generate_quote_pdf(quote, products_data)
        
        # Create filename
        customer_name = quote["customer_info"].get("company") or quote["customer_info"].get("name", "Customer")
        safe_customer_name = "".join(c for c in customer_name if c.isalnum() or c in " -_").strip()
        filename = f"Quote_{quote_id[:8]}_{safe_customer_name}.pdf"
        
        # Return PDF as streaming response
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF for quote {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate quote PDF")

@router.post("/{quote_id}/duplicate", response_model=QuoteResponse)
async def duplicate_quote(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Duplicate an existing quote for reordering"""
    try:
        original_quote = await get_quote_by_id(quote_id, db)
        
        if not original_quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check access permissions
        if not await can_access_quote(original_quote, current_user, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Create new quote based on original
        new_quote = {
            "customer_info": original_quote["customer_info"],
            "items": original_quote["items"],
            "status": "draft",
            "total_estimate": original_quote.get("total_estimate"),
            "notes": f"Duplicated from quote #{original_quote['_id']}",
            "admin_notes": None,
            "created_by": ObjectId(current_user.id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "requested_delivery_date": None
        }
        
        # Insert new quote
        result = await db.quotes.insert_one(new_quote)
        new_quote["_id"] = result.inserted_id
        
        # Convert ObjectIds to strings for response
        new_quote["id"] = str(new_quote["_id"])
        new_quote["created_by"] = str(new_quote["created_by"])
        
        logger.info(f"Quote duplicated: {quote_id} -> {new_quote['id']} by user {current_user.email}")
        
        return QuoteResponse(**new_quote)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating quote {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to duplicate quote")

@router.get("/{quote_id}/history")
async def get_quote_history(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get quote modification history and status changes"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check access permissions
        if not await can_access_quote(quote, current_user, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get quote history from quote_history collection (if it exists)
        history_items = []
        try:
            history_cursor = db.quote_history.find(
                {"quote_id": ObjectId(quote_id)}
            ).sort("timestamp", -1)
            
            async for item in history_cursor:
                history_items.append({
                    "id": str(item["_id"]),
                    "action": item.get("action", "unknown"),
                    "field_changed": item.get("field_changed"),
                    "old_value": item.get("old_value"),
                    "new_value": item.get("new_value"),
                    "changed_by": str(item.get("changed_by")),
                    "timestamp": item.get("timestamp"),
                    "notes": item.get("notes")
                })
        except:
            # History collection doesn't exist yet
            pass
        
        # If no history exists, create basic timeline from quote data
        if not history_items:
            history_items = [
                {
                    "id": "creation",
                    "action": "created",
                    "field_changed": "status",
                    "old_value": None,
                    "new_value": "draft",
                    "changed_by": str(quote.get("created_by")),
                    "timestamp": quote.get("created_at"),
                    "notes": "Quote created"
                },
                {
                    "id": "last_update",
                    "action": "updated",
                    "field_changed": "status",
                    "old_value": "draft",
                    "new_value": quote.get("status"),
                    "changed_by": str(quote.get("created_by")),
                    "timestamp": quote.get("updated_at"),
                    "notes": f"Quote status: {quote.get('status', 'unknown')}"
                }
            ]
            
            # Add email timestamps if available
            if quote.get("last_emailed_at"):
                history_items.append({
                    "id": "emailed",
                    "action": "emailed",
                    "field_changed": "status",
                    "old_value": None,
                    "new_value": "sent",
                    "changed_by": "system",
                    "timestamp": quote.get("last_emailed_at"),
                    "notes": "Quote emailed to customer"
                })
        
        return {
            "quote_id": quote_id,
            "quote_status": quote.get("status"),
            "history": sorted(history_items, key=lambda x: x.get("timestamp") or datetime.min, reverse=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving quote history {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quote history")

class StatusChangeRequest(BaseModel):
    """Request to change quote status"""
    new_status: str = Field(..., pattern="^(draft|pending|sent|approved|rejected|expired)$")
    admin_notes: Optional[str] = Field(None, max_length=500)
    notify_customer: bool = False

@router.post("/{quote_id}/status-change")
async def change_quote_status(
    quote_id: str,
    status_request: StatusChangeRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Change quote status with history tracking and optional customer notification"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check permissions
        can_change_status = (
            current_user.role in ['admin', 'manager'] or
            str(quote.get('created_by')) == str(current_user.id)
        )
        
        if not can_change_status:
            raise HTTPException(status_code=403, detail="Insufficient permissions to change quote status")
        
        old_status = quote.get("status", "draft")
        new_status = status_request.new_status
        
        if old_status == new_status:
            raise HTTPException(status_code=400, detail="Quote is already in the specified status")
        
        # Update quote status
        update_doc = {
            "status": new_status,
            "updated_at": datetime.utcnow()
        }
        
        if status_request.admin_notes and current_user.role in ['admin', 'manager']:
            update_doc["admin_notes"] = status_request.admin_notes
        
        await db.quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": update_doc}
        )
        
        # Record in history (create collection if it doesn't exist)
        history_entry = {
            "quote_id": ObjectId(quote_id),
            "action": "status_changed",
            "field_changed": "status",
            "old_value": old_status,
            "new_value": new_status,
            "changed_by": ObjectId(current_user.id),
            "timestamp": datetime.utcnow(),
            "notes": status_request.admin_notes or f"Status changed from {old_status} to {new_status}"
        }
        
        try:
            await db.quote_history.insert_one(history_entry)
        except Exception as history_error:
            logger.warning(f"Failed to record quote history: {str(history_error)}")
        
        # Send notification email if requested
        if status_request.notify_customer and quote.get("customer_info", {}).get("email"):
            def send_status_notification():
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    from services.email_service import email_service
                    loop.run_until_complete(
                        email_service.send_quote_status_notification(
                            quote_data=quote,
                            new_status=new_status,
                            recipient_email=quote["customer_info"]["email"],
                            admin_notes=status_request.admin_notes
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to send status notification email: {str(e)}")
                finally:
                    loop.close()
            
            background_tasks.add_task(send_status_notification)
        
        logger.info(f"Quote status changed: {quote_id} from {old_status} to {new_status} by user {current_user.email}")
        
        return {
            "message": "Quote status updated successfully",
            "old_status": old_status,
            "new_status": new_status,
            "notification_sent": status_request.notify_customer and bool(quote.get("customer_info", {}).get("email"))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing quote status {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to change quote status")

class BulkDiscountRequest(BaseModel):
    """Request to apply bulk discount to quote items"""
    discount_type: str = Field(..., pattern="^(percentage|fixed_amount)$")
    discount_value: float = Field(..., gt=0)
    apply_to_items: Optional[List[str]] = None  # Item indices, if None applies to all
    reason: Optional[str] = Field(None, max_length=200)

@router.post("/{quote_id}/bulk-discount")
async def apply_bulk_discount(
    quote_id: str,
    discount_request: BulkDiscountRequest,
    current_user: User = Depends(require_role(['admin', 'manager'])),
    db=Depends(get_database)
):
    """Apply bulk discount to quote items (admin/manager only)"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        items = quote.get("items", [])
        if not items:
            raise HTTPException(status_code=400, detail="Quote has no items to discount")
        
        # Apply discount to specified items or all items
        item_indices = discount_request.apply_to_items or list(range(len(items)))
        modified_items = items.copy()
        total_discount = 0.0
        
        for i in item_indices:
            if i >= len(items):
                continue
                
            item = modified_items[i]
            original_price = item.get("unit_price")
            
            if not original_price:
                continue
            
            if discount_request.discount_type == "percentage":
                # Percentage discount
                discount_amount = original_price * (discount_request.discount_value / 100)
                new_price = max(0, original_price - discount_amount)
            else:
                # Fixed amount discount
                new_price = max(0, original_price - discount_request.discount_value)
                discount_amount = original_price - new_price
            
            modified_items[i]["unit_price"] = new_price
            modified_items[i]["original_price"] = original_price
            modified_items[i]["discount_applied"] = discount_amount
            
            total_discount += discount_amount * item.get("quantity", 1)
        
        # Recalculate total estimate
        new_total = calculate_quote_total([QuoteItemRequest(**item) for item in modified_items])
        
        # Update quote
        update_doc = {
            "items": modified_items,
            "total_estimate": new_total,
            "discount_applied": total_discount,
            "discount_reason": discount_request.reason,
            "updated_at": datetime.utcnow()
        }
        
        await db.quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": update_doc}
        )
        
        # Record in history
        history_entry = {
            "quote_id": ObjectId(quote_id),
            "action": "discount_applied",
            "field_changed": "items",
            "old_value": f"Total: {quote.get('total_estimate', 0)}",
            "new_value": f"Total: {new_total} (Discount: R{total_discount:.2f})",
            "changed_by": ObjectId(current_user.id),
            "timestamp": datetime.utcnow(),
            "notes": f"{discount_request.discount_type} discount applied: {discount_request.discount_value}{'%' if discount_request.discount_type == 'percentage' else ''}"
        }
        
        try:
            await db.quote_history.insert_one(history_entry)
        except Exception as history_error:
            logger.warning(f"Failed to record discount history: {str(history_error)}")
        
        logger.info(f"Bulk discount applied to quote {quote_id}: R{total_discount:.2f} by user {current_user.email}")
        
        return {
            "message": "Bulk discount applied successfully",
            "total_discount": total_discount,
            "new_total": new_total,
            "items_affected": len(item_indices)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying bulk discount to quote {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to apply bulk discount")

class BulkQuoteAction(BaseModel):
    """Bulk action on multiple quotes"""
    quote_ids: List[str] = Field(..., min_items=1, max_items=50)
    action: str = Field(..., pattern="^(approve|reject|archive|delete)$")
    notes: Optional[str] = Field(None, max_length=500)
    notify_customers: bool = False

@router.post("/bulk-action")
async def bulk_quote_action(
    bulk_request: BulkQuoteAction,
    current_user: User = Depends(require_role(['admin', 'manager'])),
    db=Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Perform bulk actions on multiple quotes (admin/manager only)"""
    try:
        processed_quotes = []
        failed_quotes = []
        
        for quote_id in bulk_request.quote_ids:
            try:
                quote = await get_quote_by_id(quote_id, db)
                
                if not quote:
                    failed_quotes.append({"quote_id": quote_id, "reason": "Quote not found"})
                    continue
                
                old_status = quote.get("status")
                
                # Apply action
                if bulk_request.action in ["approve", "reject"]:
                    new_status = "approved" if bulk_request.action == "approve" else "rejected"
                    
                    # Update quote
                    await db.quotes.update_one(
                        {"_id": ObjectId(quote_id)},
                        {"$set": {
                            "status": new_status,
                            "admin_notes": bulk_request.notes,
                            "updated_at": datetime.utcnow()
                        }}
                    )
                    
                    # Record history
                    history_entry = {
                        "quote_id": ObjectId(quote_id),
                        "action": f"bulk_{bulk_request.action}",
                        "field_changed": "status",
                        "old_value": old_status,
                        "new_value": new_status,
                        "changed_by": ObjectId(current_user.id),
                        "timestamp": datetime.utcnow(),
                        "notes": bulk_request.notes or f"Bulk {bulk_request.action} action"
                    }
                    
                    try:
                        await db.quote_history.insert_one(history_entry)
                    except:
                        pass
                    
                    # Queue notification email if requested
                    if bulk_request.notify_customers and quote.get("customer_info", {}).get("email"):
                        def send_notification():
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            try:
                                from services.email_service import email_service
                                loop.run_until_complete(
                                    email_service.send_quote_status_notification(
                                        quote_data=quote,
                                        new_status=new_status,
                                        recipient_email=quote["customer_info"]["email"],
                                        admin_notes=bulk_request.notes
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Failed to send bulk notification email: {str(e)}")
                            finally:
                                loop.close()
                        
                        background_tasks.add_task(send_notification)
                    
                    processed_quotes.append({
                        "quote_id": quote_id,
                        "action": bulk_request.action,
                        "old_status": old_status,
                        "new_status": new_status
                    })
                
                elif bulk_request.action == "delete":
                    # Delete quote (only for drafts)
                    if quote.get("status") != "draft":
                        failed_quotes.append({
                            "quote_id": quote_id,
                            "reason": "Can only delete draft quotes"
                        })
                        continue
                    
                    await db.quotes.delete_one({"_id": ObjectId(quote_id)})
                    
                    processed_quotes.append({
                        "quote_id": quote_id,
                        "action": "deleted",
                        "old_status": old_status,
                        "new_status": "deleted"
                    })
                
                elif bulk_request.action == "archive":
                    # Archive quote (change status to archived)
                    await db.quotes.update_one(
                        {"_id": ObjectId(quote_id)},
                        {"$set": {
                            "status": "archived",
                            "admin_notes": bulk_request.notes,
                            "updated_at": datetime.utcnow()
                        }}
                    )
                    
                    processed_quotes.append({
                        "quote_id": quote_id,
                        "action": "archived",
                        "old_status": old_status,
                        "new_status": "archived"
                    })
                
            except Exception as quote_error:
                logger.error(f"Error processing quote {quote_id}: {str(quote_error)}")
                failed_quotes.append({
                    "quote_id": quote_id,
                    "reason": "Processing error"
                })
        
        logger.info(f"Bulk action {bulk_request.action} completed by {current_user.email}: {len(processed_quotes)} processed, {len(failed_quotes)} failed")
        
        return {
            "message": "Bulk action completed",
            "action": bulk_request.action,
            "processed_count": len(processed_quotes),
            "failed_count": len(failed_quotes),
            "processed_quotes": processed_quotes,
            "failed_quotes": failed_quotes
        }
        
    except Exception as e:
        logger.error(f"Error performing bulk quote action: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to perform bulk action")

class EmailQuoteRequest(BaseModel):
    """Request to email a quote to customer"""
    recipient_email: Optional[str] = None  # Use quote customer email if not provided
    include_pdf: bool = True
    custom_message: Optional[str] = Field(None, max_length=1000)
    send_copy_to_user: bool = False

@router.post("/{quote_id}/email")
async def email_quote(
    quote_id: str,
    email_request: EmailQuoteRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Email quote to customer"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check access permissions
        if not await can_access_quote(quote, current_user, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Determine recipient email
        recipient_email = email_request.recipient_email or quote["customer_info"].get("email")
        if not recipient_email:
            raise HTTPException(status_code=400, detail="No recipient email provided")
        
        # Get product details for the quote
        products_data = await get_products_for_quote(
            [QuoteItemRequest(**item) for item in quote["items"]], 
            db
        )
        
        # Send email in background
        def send_quote_email_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Send main email
                success = loop.run_until_complete(
                    email_service.send_quote_email(
                        quote_data=quote,
                        products_data=products_data,
                        recipient_email=recipient_email,
                        include_pdf=email_request.include_pdf,
                        custom_message=email_request.custom_message
                    )
                )
                
                if success and email_request.send_copy_to_user:
                    # Send copy to current user
                    loop.run_until_complete(
                        email_service.send_email(
                            to_emails=[current_user.email],
                            subject=f"Copy: Quote #{quote_id[:8].upper()} sent to {recipient_email}",
                            html_content=f"""
                            <p>This is a copy of the quote email sent to {recipient_email}.</p>
                            <p>Quote ID: {quote_id}</p>
                            <p>Sent by: {current_user.first_name} {current_user.last_name}</p>
                            """
                        )
                    )
                
                # Update quote status if it was sent successfully
                if success:
                    loop.run_until_complete(
                        db.quotes.update_one(
                            {"_id": ObjectId(quote_id)},
                            {"$set": {
                                "status": "sent" if quote.get("status") == "draft" else quote.get("status"),
                                "last_emailed_at": datetime.utcnow(),
                                "updated_at": datetime.utcnow()
                            }}
                        )
                    )
                
            except Exception as e:
                logger.error(f"Background email task failed: {str(e)}")
            finally:
                loop.close()
        
        background_tasks.add_task(send_quote_email_task)
        
        logger.info(f"Quote email queued: {quote_id} to {recipient_email} by user {current_user.email}")
        
        return {
            "message": "Quote email has been queued for sending",
            "recipient_email": recipient_email,
            "include_pdf": email_request.include_pdf
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing quote email {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to queue quote email")

@router.post("/{quote_id}/follow-up")
async def send_follow_up_email(
    quote_id: str,
    follow_up_type: str = "general",
    current_user: User = Depends(require_role(['admin', 'manager', 'sales_rep'])),
    db=Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Send follow-up email for a quote"""
    try:
        quote = await get_quote_by_id(quote_id, db)
        
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        
        # Check access permissions  
        if not await can_access_quote(quote, current_user, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        recipient_email = quote["customer_info"].get("email")
        if not recipient_email:
            raise HTTPException(status_code=400, detail="Quote has no customer email")
        
        # Validate follow-up type
        valid_types = ["general", "reminder", "expiring"]
        if follow_up_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid follow-up type. Must be one of: {valid_types}")
        
        # Send follow-up email in background
        def send_follow_up_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                success = loop.run_until_complete(
                    email_service.send_follow_up_email(
                        quote_data=quote,
                        recipient_email=recipient_email,
                        follow_up_type=follow_up_type
                    )
                )
                
                if success:
                    # Update quote with follow-up timestamp
                    loop.run_until_complete(
                        db.quotes.update_one(
                            {"_id": ObjectId(quote_id)},
                            {"$set": {
                                "last_follow_up_at": datetime.utcnow(),
                                "updated_at": datetime.utcnow()
                            }}
                        )
                    )
                    
            except Exception as e:
                logger.error(f"Background follow-up email task failed: {str(e)}")
            finally:
                loop.close()
        
        background_tasks.add_task(send_follow_up_task)
        
        logger.info(f"Follow-up email queued: {quote_id} ({follow_up_type}) by user {current_user.email}")
        
        return {
            "message": f"Follow-up email ({follow_up_type}) has been queued for sending",
            "recipient_email": recipient_email,
            "follow_up_type": follow_up_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing follow-up email {quote_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to queue follow-up email")

# Export router
__all__ = ['router']
