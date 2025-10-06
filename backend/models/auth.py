"""
Authentication models for Stark Products API
User models, roles, and authentication-related data structures
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum
import uuid
import re

# User roles enum
class UserRole(str, Enum):
    ADMIN = "admin"           # Full system access
    MANAGER = "manager"       # Manage sales team and view all data  
    SALES_REP = "sales_rep"   # Handle assigned customers and quotes
    CUSTOMER = "customer"     # Regular customer account
    COMPANY_ADMIN = "company_admin"  # Admin for a company account

# Account status enum
class AccountStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"

# User models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    role: UserRole = UserRole.CUSTOMER
    status: AccountStatus = AccountStatus.PENDING_VERIFICATION
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    assigned_sales_rep: Optional[str] = None  # For customer accounts
    permissions: List[str] = []
    last_login: Optional[datetime] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None
    email_verified: bool = False
    email_verification_token: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None  # ID of user who created this account
    metadata: Dict[str, Any] = {}

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, hyphens and underscores')
        return v.lower()

    @field_validator('phone')
    @classmethod 
    def validate_phone(cls, v):
        if v and not re.match(r'^\+?[\d\s\-\(\)]{10,}$', v):
            raise ValueError('Invalid phone number format')
        return v

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    first_name: str
    last_name: str
    role: UserRole = UserRole.CUSTOMER
    company_name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v

class UserLogin(BaseModel):
    email_or_username: str
    password: str
    remember_me: bool = False

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    company_name: Optional[str] = None

class PasswordReset(BaseModel):
    token: str
    new_password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

# JWT Token models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    user_id: str
    email: str
    role: UserRole
    permissions: List[str]
    exp: datetime

# Export models
__all__ = [
    'UserRole', 'AccountStatus', 'User', 'UserCreate', 'UserLogin', 'UserUpdate',
    'PasswordReset', 'PasswordChange', 'Token', 'TokenData'
]
