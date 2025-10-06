"""
Company models for B2B account management
Enables multiple employees from same company to share quotes
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator
from enum import Enum
import uuid
import re

from .base import ObjectIdStr

class CompanySize(str, Enum):
    STARTUP = "startup"          # 1-10 employees
    SMALL = "small"              # 11-50 employees  
    MEDIUM = "medium"            # 51-200 employees
    LARGE = "large"              # 201-1000 employees
    ENTERPRISE = "enterprise"    # 1000+ employees

class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_APPROVAL = "pending_approval"

class Company(BaseModel):
    """Company account for B2B customers"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=2, max_length=100)
    legal_name: Optional[str] = Field(None, max_length=150)
    registration_number: Optional[str] = Field(None, max_length=50)
    vat_number: Optional[str] = Field(None, max_length=50)
    
    # Contact information
    primary_email: EmailStr
    phone: Optional[str] = None
    website: Optional[str] = None
    
    # Address information
    billing_address: Dict[str, str] = Field(default_factory=dict)
    shipping_address: Optional[Dict[str, str]] = None
    
    # Company details
    size: CompanySize = CompanySize.SMALL
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    # Account settings
    status: CompanyStatus = CompanyStatus.PENDING_APPROVAL
    credit_limit: Optional[float] = Field(None, ge=0)
    payment_terms: int = Field(default=30, ge=0, le=180)  # Days
    discount_rate: float = Field(default=0.0, ge=0, le=0.5)  # Max 50% discount
    
    # Assigned staff
    assigned_sales_rep: Optional[ObjectIdStr] = None
    account_manager: Optional[ObjectIdStr] = None
    
    # Tracking
    total_quotes: int = Field(default=0, ge=0)
    total_orders: int = Field(default=0, ge=0)
    total_revenue: float = Field(default=0.0, ge=0)
    last_order_date: Optional[datetime] = None
    
    # Settings for shared quotes
    quote_sharing_enabled: bool = Field(default=True)
    require_approval_for_quotes: bool = Field(default=False)
    max_quote_value_without_approval: Optional[float] = Field(default=10000.0, ge=0)
    
    # Metadata
    notes: Optional[str] = Field(None, max_length=1000)
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[ObjectIdStr] = None
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v and not re.match(r'^\+?[\d\s\-\(\)]{10,}$', v):
            raise ValueError('Invalid phone number format')
        return v
    
    @field_validator('website')
    @classmethod
    def validate_website(cls, v):
        if v and not re.match(r'^https?://', v):
            v = f"https://{v}"
        return v
    
    @field_validator('vat_number')
    @classmethod
    def validate_vat_number(cls, v):
        if v:
            # Basic validation for South African VAT numbers
            v = re.sub(r'[^\d]', '', v)  # Remove non-digits
            if len(v) != 10:
                raise ValueError('VAT number must be 10 digits')
        return v

class CompanyCreate(BaseModel):
    """Create new company account"""
    name: str = Field(..., min_length=2, max_length=100)
    legal_name: Optional[str] = Field(None, max_length=150)
    registration_number: Optional[str] = Field(None, max_length=50)
    vat_number: Optional[str] = Field(None, max_length=50)
    
    primary_email: EmailStr
    phone: Optional[str] = None
    website: Optional[str] = None
    
    billing_address: Dict[str, str] = Field(default_factory=dict)
    shipping_address: Optional[Dict[str, str]] = None
    
    size: CompanySize = CompanySize.SMALL
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    # Account settings
    payment_terms: int = Field(default=30, ge=0, le=180)
    
    # Quote settings
    quote_sharing_enabled: bool = Field(default=True)
    require_approval_for_quotes: bool = Field(default=False)
    max_quote_value_without_approval: Optional[float] = Field(default=10000.0, ge=0)

class CompanyUpdate(BaseModel):
    """Update company information"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    legal_name: Optional[str] = Field(None, max_length=150)
    registration_number: Optional[str] = Field(None, max_length=50)
    vat_number: Optional[str] = Field(None, max_length=50)
    
    primary_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    
    billing_address: Optional[Dict[str, str]] = None
    shipping_address: Optional[Dict[str, str]] = None
    
    size: Optional[CompanySize] = None
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    # Account settings (admin only)
    status: Optional[CompanyStatus] = None
    credit_limit: Optional[float] = Field(None, ge=0)
    payment_terms: Optional[int] = Field(None, ge=0, le=180)
    discount_rate: Optional[float] = Field(None, ge=0, le=0.5)
    
    # Quote settings
    quote_sharing_enabled: Optional[bool] = None
    require_approval_for_quotes: Optional[bool] = None
    max_quote_value_without_approval: Optional[float] = Field(None, ge=0)
    
    notes: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None

class CompanyEmployee(BaseModel):
    """Company employee information"""
    user_id: ObjectIdStr
    email: str
    first_name: str
    last_name: str
    position: Optional[str] = None
    role_in_company: str = "employee"  # employee, admin, approver
    can_create_quotes: bool = True
    can_approve_quotes: bool = False
    max_quote_value: Optional[float] = None
    joined_company_at: datetime
    status: str = "active"  # active, inactive

class CompanyResponse(BaseModel):
    """Company response model"""
    id: str
    name: str
    legal_name: Optional[str]
    primary_email: str
    phone: Optional[str]
    website: Optional[str]
    size: CompanySize
    industry: Optional[str]
    status: CompanyStatus
    quote_sharing_enabled: bool
    total_quotes: int
    total_orders: int
    employee_count: Optional[int] = None
    created_at: datetime

class CompanyDetailsResponse(CompanyResponse):
    """Detailed company response with full information"""
    registration_number: Optional[str]
    vat_number: Optional[str]
    billing_address: Dict[str, str]
    shipping_address: Optional[Dict[str, str]]
    description: Optional[str]
    credit_limit: Optional[float]
    payment_terms: int
    discount_rate: float
    assigned_sales_rep: Optional[ObjectIdStr]
    account_manager: Optional[ObjectIdStr]
    total_revenue: float
    last_order_date: Optional[datetime]
    require_approval_for_quotes: bool
    max_quote_value_without_approval: Optional[float]
    notes: Optional[str]
    tags: List[str]
    employees: Optional[List[CompanyEmployee]] = None
    updated_at: datetime
    created_by: Optional[ObjectIdStr]

# Export models
__all__ = [
    'Company', 'CompanyCreate', 'CompanyUpdate', 'CompanyResponse', 'CompanyDetailsResponse',
    'CompanyEmployee', 'CompanySize', 'CompanyStatus'
]
