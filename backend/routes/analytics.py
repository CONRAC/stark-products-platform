"""
Analytics API Routes
Provides business insights for dashboards including quote conversion, popular products, and company metrics
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from bson import ObjectId

from database import get_database
from auth import get_current_user, require_role
from models.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Response Models

class QuoteMetrics(BaseModel):
    """Quote metrics for analytics"""
    total_quotes: int
    active_quotes: int
    converted_quotes: int
    conversion_rate: float
    average_quote_value: Optional[float]
    total_quote_value: float

class ProductMetrics(BaseModel):
    """Product popularity metrics"""
    product_id: str
    product_name: str
    quote_count: int
    total_quantity: int
    total_value: Optional[float]
    category: Optional[str]

class CompanyMetrics(BaseModel):
    """Company performance metrics"""
    company_id: str
    company_name: str
    total_quotes: int
    total_value: float
    last_quote_date: Optional[datetime]
    status: str

class TimeSeriesData(BaseModel):
    """Time series data point"""
    date: str
    value: float
    count: int

class AnalyticsDashboardResponse(BaseModel):
    """Main analytics dashboard response"""
    period_start: datetime
    period_end: datetime
    quote_metrics: QuoteMetrics
    top_products: List[ProductMetrics]
    top_companies: List[CompanyMetrics]
    quote_trends: List[TimeSeriesData]
    revenue_trends: List[TimeSeriesData]

class StatusBreakdown(BaseModel):
    """Breakdown by status"""
    status: str
    count: int
    percentage: float

# Helper Functions

async def calculate_quote_metrics(db, start_date: datetime, end_date: datetime, user: User) -> QuoteMetrics:
    """Calculate quote metrics for the specified period"""
    try:
        # Build query filter based on user role
        query = {
            "created_at": {"$gte": start_date, "$lte": end_date}
        }
        
        # Role-based filtering
        if user.role not in ['admin', 'manager']:
            if user.company_id:
                # Get users from the same company
                company_users = await db.users.find({"company_id": user.company_id}).to_list(length=None)
                user_ids = [user["_id"] for user in company_users]
                query["created_by"] = {"$in": user_ids}
            else:
                query["created_by"] = ObjectId(user.id)
        
        # Get all quotes in period
        quotes = await db.quotes.find(query).to_list(length=None)
        
        total_quotes = len(quotes)
        active_quotes = len([q for q in quotes if q.get('status') in ['draft', 'pending', 'sent']])
        converted_quotes = len([q for q in quotes if q.get('status') in ['approved', 'accepted']])
        
        conversion_rate = (converted_quotes / total_quotes * 100) if total_quotes > 0 else 0.0
        
        # Calculate average and total quote values
        quote_values = [q.get('total_estimate', 0) for q in quotes if q.get('total_estimate')]
        total_quote_value = sum(quote_values)
        average_quote_value = sum(quote_values) / len(quote_values) if quote_values else None
        
        return QuoteMetrics(
            total_quotes=total_quotes,
            active_quotes=active_quotes,
            converted_quotes=converted_quotes,
            conversion_rate=round(conversion_rate, 2),
            average_quote_value=average_quote_value,
            total_quote_value=total_quote_value
        )
        
    except Exception as e:
        logger.error(f"Error calculating quote metrics: {str(e)}")
        return QuoteMetrics(
            total_quotes=0,
            active_quotes=0,
            converted_quotes=0,
            conversion_rate=0.0,
            average_quote_value=None,
            total_quote_value=0.0
        )

async def get_popular_products(db, start_date: datetime, end_date: datetime, user: User, limit: int = 10) -> List[ProductMetrics]:
    """Get most popular products based on quote frequency"""
    try:
        # Build query filter
        query = {
            "created_at": {"$gte": start_date, "$lte": end_date}
        }
        
        # Role-based filtering
        if user.role not in ['admin', 'manager']:
            if user.company_id:
                company_users = await db.users.find({"company_id": user.company_id}).to_list(length=None)
                user_ids = [user["_id"] for user in company_users]
                query["created_by"] = {"$in": user_ids}
            else:
                query["created_by"] = ObjectId(user.id)
        
        # Aggregate product popularity
        pipeline = [
            {"$match": query},
            {"$unwind": "$items"},
            {"$group": {
                "_id": "$items.product_id",
                "product_name": {"$first": "$items.product_name"},
                "quote_count": {"$sum": 1},
                "total_quantity": {"$sum": "$items.quantity"},
                "total_value": {"$sum": {"$multiply": ["$items.unit_price", "$items.quantity"]}}
            }},
            {"$sort": {"quote_count": -1}},
            {"$limit": limit}
        ]
        
        results = await db.quotes.aggregate(pipeline).to_list(length=None)
        
        popular_products = []
        for result in results:
            # Get product details
            product = await db.products.find_one({"_id": ObjectId(result["_id"])})
            
            popular_products.append(ProductMetrics(
                product_id=str(result["_id"]),
                product_name=result["product_name"],
                quote_count=result["quote_count"],
                total_quantity=result["total_quantity"],
                total_value=result.get("total_value"),
                category=product.get("category") if product else None
            ))
        
        return popular_products
        
    except Exception as e:
        logger.error(f"Error getting popular products: {str(e)}")
        return []

async def get_top_companies(db, start_date: datetime, end_date: datetime, user: User, limit: int = 10) -> List[CompanyMetrics]:
    """Get top companies by quote volume"""
    try:
        # Only admins and managers can see company metrics
        if user.role not in ['admin', 'manager']:
            return []
        
        # Aggregate company performance
        pipeline = [
            {"$match": {
                "created_at": {"$gte": start_date, "$lte": end_date}
            }},
            {"$lookup": {
                "from": "users",
                "localField": "created_by",
                "foreignField": "_id",
                "as": "user_info"
            }},
            {"$unwind": "$user_info"},
            {"$match": {
                "user_info.company_id": {"$ne": None}
            }},
            {"$group": {
                "_id": "$user_info.company_id",
                "total_quotes": {"$sum": 1},
                "total_value": {"$sum": "$total_estimate"},
                "last_quote_date": {"$max": "$created_at"}
            }},
            {"$sort": {"total_quotes": -1}},
            {"$limit": limit}
        ]
        
        results = await db.quotes.aggregate(pipeline).to_list(length=None)
        
        top_companies = []
        for result in results:
            # Get company details
            company = await db.companies.find_one({"_id": ObjectId(result["_id"])})
            
            if company:
                top_companies.append(CompanyMetrics(
                    company_id=str(result["_id"]),
                    company_name=company["name"],
                    total_quotes=result["total_quotes"],
                    total_value=result.get("total_value", 0.0) or 0.0,
                    last_quote_date=result.get("last_quote_date"),
                    status=company.get("status", "unknown")
                ))
        
        return top_companies
        
    except Exception as e:
        logger.error(f"Error getting top companies: {str(e)}")
        return []

async def get_quote_trends(db, start_date: datetime, end_date: datetime, user: User) -> List[TimeSeriesData]:
    """Get quote volume trends over time"""
    try:
        # Build query filter
        query = {
            "created_at": {"$gte": start_date, "$lte": end_date}
        }
        
        # Role-based filtering
        if user.role not in ['admin', 'manager']:
            if user.company_id:
                company_users = await db.users.find({"company_id": user.company_id}).to_list(length=None)
                user_ids = [user["_id"] for user in company_users]
                query["created_by"] = {"$in": user_ids}
            else:
                query["created_by"] = ObjectId(user.id)
        
        # Aggregate by day
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$created_at"
                    }
                },
                "count": {"$sum": 1},
                "value": {"$sum": "$total_estimate"}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        results = await db.quotes.aggregate(pipeline).to_list(length=None)
        
        trends = []
        for result in results:
            trends.append(TimeSeriesData(
                date=result["_id"],
                count=result["count"],
                value=result.get("value", 0.0) or 0.0
            ))
        
        return trends
        
    except Exception as e:
        logger.error(f"Error getting quote trends: {str(e)}")
        return []

# API Endpoints

@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
async def get_dashboard_analytics(
    days: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get comprehensive dashboard analytics"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Calculate all metrics concurrently
        quote_metrics = await calculate_quote_metrics(db, start_date, end_date, current_user)
        top_products = await get_popular_products(db, start_date, end_date, current_user, limit=10)
        top_companies = await get_top_companies(db, start_date, end_date, current_user, limit=10)
        quote_trends = await get_quote_trends(db, start_date, end_date, current_user)
        
        # Revenue trends are the same as quote trends for now
        revenue_trends = quote_trends
        
        return AnalyticsDashboardResponse(
            period_start=start_date,
            period_end=end_date,
            quote_metrics=quote_metrics,
            top_products=top_products,
            top_companies=top_companies,
            quote_trends=quote_trends,
            revenue_trends=revenue_trends
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboard analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard analytics")

@router.get("/quotes/status-breakdown", response_model=List[StatusBreakdown])
async def get_quote_status_breakdown(
    days: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get breakdown of quotes by status"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Build query filter
        query = {
            "created_at": {"$gte": start_date, "$lte": end_date}
        }
        
        # Role-based filtering
        if current_user.role not in ['admin', 'manager']:
            if current_user.company_id:
                company_users = await db.users.find({"company_id": current_user.company_id}).to_list(length=None)
                user_ids = [user["_id"] for user in company_users]
                query["created_by"] = {"$in": user_ids}
            else:
                query["created_by"] = ObjectId(current_user.id)
        
        # Aggregate by status
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        results = await db.quotes.aggregate(pipeline).to_list(length=None)
        total_quotes = sum(result["count"] for result in results)
        
        breakdown = []
        for result in results:
            percentage = (result["count"] / total_quotes * 100) if total_quotes > 0 else 0
            breakdown.append(StatusBreakdown(
                status=result["_id"],
                count=result["count"],
                percentage=round(percentage, 2)
            ))
        
        # Sort by count descending
        breakdown.sort(key=lambda x: x.count, reverse=True)
        
        return breakdown
        
    except Exception as e:
        logger.error(f"Error getting status breakdown: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve status breakdown")

@router.get("/products/popular", response_model=List[ProductMetrics])
async def get_popular_products_endpoint(
    days: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    limit: int = Query(20, description="Maximum number of products to return", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get most popular products"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        popular_products = await get_popular_products(db, start_date, end_date, current_user, limit)
        return popular_products
        
    except Exception as e:
        logger.error(f"Error getting popular products: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve popular products")

@router.get("/companies/top", response_model=List[CompanyMetrics])
async def get_top_companies_endpoint(
    days: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    limit: int = Query(20, description="Maximum number of companies to return", ge=1, le=100),
    current_user: User = Depends(require_role(['admin', 'manager'])),
    db=Depends(get_database)
):
    """Get top performing companies (admin/manager only)"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        top_companies = await get_top_companies(db, start_date, end_date, current_user, limit)
        return top_companies
        
    except Exception as e:
        logger.error(f"Error getting top companies: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve top companies")

@router.get("/quotes/trends", response_model=List[TimeSeriesData])
async def get_quote_trends_endpoint(
    days: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get quote volume trends over time"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        trends = await get_quote_trends(db, start_date, end_date, current_user)
        return trends
        
    except Exception as e:
        logger.error(f"Error getting quote trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quote trends")

@router.get("/summary")
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get high-level analytics summary"""
    try:
        # Build query filter based on user role
        query = {}
        
        # Role-based filtering
        if current_user.role not in ['admin', 'manager']:
            if current_user.company_id:
                company_users = await db.users.find({"company_id": current_user.company_id}).to_list(length=None)
                user_ids = [user["_id"] for user in company_users]
                query["created_by"] = {"$in": user_ids}
            else:
                query["created_by"] = ObjectId(current_user.id)
        
        # Get basic counts
        total_quotes = await db.quotes.count_documents(query)
        total_products = await db.products.count_documents({}) if current_user.role in ['admin', 'manager'] else None
        total_companies = await db.companies.count_documents({}) if current_user.role in ['admin', 'manager'] else None
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_query = {**query, "created_at": {"$gte": week_ago}}
        recent_quotes = await db.quotes.count_documents(recent_query)
        
        # Pending quotes requiring attention
        pending_query = {**query, "status": {"$in": ["draft", "pending"]}}
        pending_quotes = await db.quotes.count_documents(pending_query)
        
        summary = {
            "total_quotes": total_quotes,
            "recent_quotes": recent_quotes,
            "pending_quotes": pending_quotes,
            "user_role": current_user.role
        }
        
        # Add admin-only metrics
        if current_user.role in ['admin', 'manager']:
            summary.update({
                "total_products": total_products,
                "total_companies": total_companies,
                "total_users": await db.users.count_documents({})
            })
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics summary")

# Export router
__all__ = ['router']
