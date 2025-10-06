"""
Company Management API Routes
Handles B2B company accounts and enables shared quote access
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from bson import ObjectId

from database import get_database
from auth import get_current_user, require_role
from models.base import ObjectIdStr
from models.auth import User
from models.company import (
    Company, CompanyCreate, CompanyUpdate, CompanyResponse, CompanyDetailsResponse,
    CompanyEmployee, CompanyStatus, CompanySize
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])

# Helper Functions

async def get_company_by_id(company_id: str, db) -> Optional[Dict[str, Any]]:
    """Retrieve a company by ID"""
    try:
        company = await db.companies.find_one({"_id": ObjectId(company_id)})
        return company
    except Exception as e:
        logger.error(f"Error fetching company {company_id}: {str(e)}")
        return None

async def get_company_employees(company_id: str, db) -> List[CompanyEmployee]:
    """Get all employees for a company"""
    try:
        # Find all users belonging to this company
        cursor = db.users.find({"company_id": company_id})
        users = await cursor.to_list(length=None)
        
        employees = []
        for user in users:
            employee = CompanyEmployee(
                user_id=str(user["_id"]),
                email=user["email"],
                first_name=user["first_name"],
                last_name=user["last_name"],
                position=user.get("position"),
                role_in_company=user.get("role_in_company", "employee"),
                can_create_quotes=user.get("can_create_quotes", True),
                can_approve_quotes=user.get("can_approve_quotes", False),
                max_quote_value=user.get("max_quote_value"),
                joined_company_at=user.get("joined_company_at", user["created_at"]),
                status=user.get("status", "active")
            )
            employees.append(employee)
        
        return employees
    except Exception as e:
        logger.error(f"Error fetching employees for company {company_id}: {str(e)}")
        return []

async def can_access_company(company: Dict[str, Any], user: User) -> bool:
    """Check if user can access company information"""
    # Admins and managers can access all companies
    if user.role in ['admin', 'manager']:
        return True
    
    # Users can access their own company
    if user.company_id == str(company.get('_id')):
        return True
    
    # Sales reps can access assigned companies
    if (user.role == 'sales_rep' and 
        str(user.id) == str(company.get('assigned_sales_rep'))):
        return True
    
    return False

async def can_manage_company(company: Dict[str, Any], user: User) -> bool:
    """Check if user can manage company settings"""
    # Admins and managers can manage all companies
    if user.role in ['admin', 'manager']:
        return True
    
    # Company admins can manage their own company
    if (user.company_id == str(company.get('_id')) and 
        user.role == 'company_admin'):
        return True
    
    return False

# API Endpoints

@router.post("/", response_model=CompanyResponse)
async def create_company(
    company_data: CompanyCreate,
    current_user: User = Depends(require_role(['admin', 'manager'])),
    db=Depends(get_database)
):
    """Create a new company account (admin/manager only)"""
    try:
        # Check if company with same name already exists
        existing = await db.companies.find_one({"name": company_data.name})
        if existing:
            raise HTTPException(status_code=400, detail="Company with this name already exists")
        
        # Check if company with same email exists
        existing_email = await db.companies.find_one({"primary_email": company_data.primary_email})
        if existing_email:
            raise HTTPException(status_code=400, detail="Company with this email already exists")
        
        # Create company document
        company_doc = {
            **company_data.dict(),
            "id": str(ObjectId()),  # Generate new ID
            "status": CompanyStatus.PENDING_APPROVAL,
            "total_quotes": 0,
            "total_orders": 0,
            "total_revenue": 0.0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": ObjectId(current_user.id)
        }
        
        # Insert company
        company_doc["_id"] = ObjectId(company_doc["id"])
        result = await db.companies.insert_one(company_doc)
        
        # Convert ObjectIds to strings for response
        company_doc["id"] = str(company_doc["_id"])
        company_doc["created_by"] = str(company_doc["created_by"])
        
        logger.info(f"Company created: {company_doc['name']} by user {current_user.email}")
        
        return CompanyResponse(**company_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating company: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create company")

@router.get("/", response_model=List[CompanyResponse])
async def list_companies(
    status: Optional[CompanyStatus] = None,
    size: Optional[CompanySize] = None,
    industry: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """List companies with optional filtering"""
    try:
        # Build query filter
        query = {}
        
        # Role-based filtering
        if current_user.role in ['admin', 'manager']:
            # Admins and managers can see all companies
            pass
        elif current_user.role == 'sales_rep':
            # Sales reps can see their assigned companies
            query["$or"] = [
                {"assigned_sales_rep": ObjectId(current_user.id)},
                {"account_manager": ObjectId(current_user.id)}
            ]
        else:
            # Regular users can only see their own company
            if current_user.company_id:
                query["_id"] = ObjectId(current_user.company_id)
            else:
                return []  # User has no company access
        
        if status:
            query["status"] = status
        
        if size:
            query["size"] = size
            
        if industry:
            query["industry"] = {"$regex": industry, "$options": "i"}
        
        # Execute query
        cursor = db.companies.find(query).skip(skip).limit(limit).sort("name", 1)
        companies = await cursor.to_list(length=None)
        
        # Convert ObjectIds to strings and add employee count
        response_companies = []
        for company in companies:
            company["id"] = str(company["_id"])
            
            # Get employee count
            employee_count = await db.users.count_documents({"company_id": str(company["_id"])})
            company["employee_count"] = employee_count
            
            response_companies.append(CompanyResponse(**company))
        
        return response_companies
        
    except Exception as e:
        logger.error(f"Error listing companies: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve companies")

@router.get("/{company_id}", response_model=CompanyDetailsResponse)
async def get_company(
    company_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get detailed company information"""
    try:
        company = await get_company_by_id(company_id, db)
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check access permissions
        if not await can_access_company(company, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Convert ObjectIds to strings
        company["id"] = str(company["_id"])
        if company.get("created_by"):
            company["created_by"] = str(company["created_by"])
        if company.get("assigned_sales_rep"):
            company["assigned_sales_rep"] = str(company["assigned_sales_rep"])
        if company.get("account_manager"):
            company["account_manager"] = str(company["account_manager"])
        
        # Get employees if user can see them
        if await can_manage_company(company, current_user) or current_user.role in ['admin', 'manager']:
            employees = await get_company_employees(company_id, db)
            company["employees"] = employees
        
        return CompanyDetailsResponse(**company)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve company")

@router.put("/{company_id}", response_model=CompanyDetailsResponse)
async def update_company(
    company_id: str,
    company_update: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Update company information"""
    try:
        company = await get_company_by_id(company_id, db)
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check permissions
        if not await can_manage_company(company, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Build update document
        update_doc = {"updated_at": datetime.utcnow()}
        
        # Basic company information
        for field in ['name', 'legal_name', 'registration_number', 'vat_number',
                     'primary_email', 'phone', 'website', 'billing_address',
                     'shipping_address', 'size', 'industry', 'description',
                     'quote_sharing_enabled', 'require_approval_for_quotes',
                     'max_quote_value_without_approval', 'notes', 'tags']:
            value = getattr(company_update, field, None)
            if value is not None:
                update_doc[field] = value
        
        # Admin-only fields
        if current_user.role in ['admin', 'manager']:
            for field in ['status', 'credit_limit', 'payment_terms', 'discount_rate']:
                value = getattr(company_update, field, None)
                if value is not None:
                    update_doc[field] = value
        
        # Check for duplicate name or email if being updated
        if 'name' in update_doc:
            existing = await db.companies.find_one({
                "name": update_doc['name'],
                "_id": {"$ne": ObjectId(company_id)}
            })
            if existing:
                raise HTTPException(status_code=400, detail="Company with this name already exists")
        
        if 'primary_email' in update_doc:
            existing = await db.companies.find_one({
                "primary_email": update_doc['primary_email'],
                "_id": {"$ne": ObjectId(company_id)}
            })
            if existing:
                raise HTTPException(status_code=400, detail="Company with this email already exists")
        
        # Update company
        await db.companies.update_one(
            {"_id": ObjectId(company_id)},
            {"$set": update_doc}
        )
        
        # Fetch updated company
        updated_company = await get_company_by_id(company_id, db)
        updated_company["id"] = str(updated_company["_id"])
        if updated_company.get("created_by"):
            updated_company["created_by"] = str(updated_company["created_by"])
        if updated_company.get("assigned_sales_rep"):
            updated_company["assigned_sales_rep"] = str(updated_company["assigned_sales_rep"])
        if updated_company.get("account_manager"):
            updated_company["account_manager"] = str(updated_company["account_manager"])
        
        # Get employees
        employees = await get_company_employees(company_id, db)
        updated_company["employees"] = employees
        
        logger.info(f"Company updated: {company_id} by user {current_user.email}")
        
        return CompanyDetailsResponse(**updated_company)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update company")

@router.delete("/{company_id}")
async def delete_company(
    company_id: str,
    current_user: User = Depends(require_role(['admin'])),
    db=Depends(get_database)
):
    """Delete a company (admin only)"""
    try:
        # Check if company has active users
        user_count = await db.users.count_documents({"company_id": company_id})
        if user_count > 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete company with {user_count} active employees"
            )
        
        # Check if company has quotes
        quote_count = await db.quotes.count_documents({"company_id": ObjectId(company_id)})
        if quote_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete company with {quote_count} existing quotes"
            )
        
        result = await db.companies.delete_one({"_id": ObjectId(company_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Company not found")
        
        logger.info(f"Company deleted: {company_id} by user {current_user.email}")
        
        return {"message": "Company deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete company")

@router.get("/{company_id}/employees", response_model=List[CompanyEmployee])
async def get_company_employees_endpoint(
    company_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get all employees for a company"""
    try:
        company = await get_company_by_id(company_id, db)
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check permissions
        if not await can_access_company(company, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        employees = await get_company_employees(company_id, db)
        return employees
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving employees for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve employees")

@router.get("/{company_id}/quotes")
async def get_company_quotes(
    company_id: str,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get all quotes for a company"""
    try:
        company = await get_company_by_id(company_id, db)
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check access permissions
        if not await can_access_company(company, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if company has quote sharing enabled
        if not company.get("quote_sharing_enabled", True):
            # Only allow access to own quotes if sharing is disabled
            if current_user.role not in ['admin', 'manager'] and current_user.company_id == company_id:
                # User can only see their own quotes
                query = {
                    "created_by": ObjectId(current_user.id)
                }
            else:
                query = {}
        else:
            # Find all quotes for users in this company
            user_ids = []
            cursor = db.users.find({"company_id": company_id}, {"_id": 1})
            async for user in cursor:
                user_ids.append(user["_id"])
            
            query = {
                "created_by": {"$in": user_ids}
            }
        
        if status:
            query["status"] = status
        
        # Execute query
        cursor = db.quotes.find(query).skip(skip).limit(limit).sort("created_at", -1)
        quotes = await cursor.to_list(length=None)
        
        # Convert ObjectIds to strings
        for quote in quotes:
            quote["id"] = str(quote["_id"])
            quote["created_by"] = str(quote["created_by"])
        
        return {
            "company_id": company_id,
            "company_name": company["name"],
            "quote_sharing_enabled": company.get("quote_sharing_enabled", True),
            "quotes": quotes,
            "total_count": len(quotes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving quotes for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve company quotes")

@router.post("/{company_id}/assign-sales-rep")
async def assign_sales_rep(
    company_id: str,
    sales_rep_id: str,
    current_user: User = Depends(require_role(['admin', 'manager'])),
    db=Depends(get_database)
):
    """Assign a sales representative to a company"""
    try:
        company = await get_company_by_id(company_id, db)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Verify sales rep exists and has correct role
        sales_rep = await db.users.find_one({"_id": ObjectId(sales_rep_id)})
        if not sales_rep:
            raise HTTPException(status_code=404, detail="Sales representative not found")
        
        if sales_rep.get("role") not in ['sales_rep', 'manager', 'admin']:
            raise HTTPException(status_code=400, detail="User is not a sales representative")
        
        # Update company
        await db.companies.update_one(
            {"_id": ObjectId(company_id)},
            {"$set": {
                "assigned_sales_rep": ObjectId(sales_rep_id),
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"Sales rep {sales_rep_id} assigned to company {company_id} by {current_user.email}")
        
        return {
            "message": "Sales representative assigned successfully",
            "sales_rep": {
                "id": sales_rep_id,
                "name": f"{sales_rep['first_name']} {sales_rep['last_name']}",
                "email": sales_rep["email"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning sales rep to company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign sales representative")

# Export router
__all__ = ['router']
