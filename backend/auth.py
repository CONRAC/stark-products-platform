"""
Authentication and Authorization module for Stark Products API
Handles JWT tokens, user management, and role-based access control
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid
import re
import logging

from config import settings
from security import SecurityAudit, RateLimiter

logger = logging.getLogger(__name__)

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

# Authentication utilities
class AuthManager:
    def __init__(self):
        self.secret_key = settings.jwt_secret
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_access_token_expire_minutes
        self.refresh_token_expire_days = settings.jwt_refresh_token_expire_days
        
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, expected_type: str = "access") -> TokenData:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Verify token type
            token_type = payload.get("type")
            if token_type != expected_type:
                raise HTTPException(status_code=401, detail="Invalid token type")
            
            # Extract token data
            user_id = payload.get("sub")
            email = payload.get("email")
            role = payload.get("role")
            permissions = payload.get("permissions", [])
            exp = datetime.fromtimestamp(payload.get("exp"))
            
            if not user_id or not email:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            
            return TokenData(
                user_id=user_id,
                email=email,
                role=role,
                permissions=permissions,
                exp=exp
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.JWTError as e:
            logger.error(f"JWT Error: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")
    
    def create_tokens(self, user: User) -> Token:
        """Create both access and refresh tokens for user"""
        token_data = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "permissions": user.permissions
        }
        
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token({"sub": user.id})
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60
        )

# Global auth manager instance
auth_manager = AuthManager()

# Role-based permissions
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        "users:create", "users:read", "users:update", "users:delete",
        "products:create", "products:read", "products:update", "products:delete",
        "quotes:create", "quotes:read", "quotes:update", "quotes:delete",
        "analytics:read", "system:admin"
    ],
    UserRole.MANAGER: [
        "users:read", "users:update",
        "products:read", "products:update",
        "quotes:create", "quotes:read", "quotes:update",
        "analytics:read"
    ],
    UserRole.SALES_REP: [
        "products:read",
        "quotes:create", "quotes:read", "quotes:update",
        "customers:read"
    ],
    UserRole.CUSTOMER: [
        "products:read",
        "quotes:create", "quotes:read"
    ],
    UserRole.COMPANY_ADMIN: [
        "products:read",
        "quotes:create", "quotes:read", "quotes:update",
        "company:manage"
    ]
}

def get_user_permissions(role: UserRole) -> List[str]:
    """Get permissions for a user role"""
    return ROLE_PERMISSIONS.get(role, [])

# Security dependencies
security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user"""
    from server import db  # Import here to avoid circular dependency
    
    try:
        # Verify JWT token
        token_data = auth_manager.verify_token(credentials.credentials)
        
        # Get user from database
        user_doc = await db.users.find_one({"id": token_data.user_id})
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")
        
        user = User(**user_doc)
        
        # Check if user account is active
        if user.status != AccountStatus.ACTIVE:
            raise HTTPException(status_code=401, detail="Account is not active")
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(status_code=401, detail="Account is temporarily locked")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        # Log security event
        client_id = RateLimiter.get_client_id(request)
        SecurityAudit.log_failed_auth(client_id)
        raise HTTPException(status_code=401, detail="Authentication failed")

async def require_permissions(required_permissions: List[str]):
    """Dependency to require specific permissions"""
    def permission_checker(current_user: User = Depends(get_current_user)):
        user_permissions = get_user_permissions(current_user.role)
        user_permissions.extend(current_user.permissions)  # Add custom permissions
        
        for permission in required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Insufficient permissions. Required: {permission}"
                )
        return current_user
    
    return permission_checker

def require_role(required_roles: List[UserRole]):
    """Dependency to require specific roles"""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {[role.value for role in required_roles]}"
            )
        return current_user
    
    return role_checker

# Convenience functions for common role checks
async def require_admin(current_user: User = Depends(get_current_user)):
    """Require admin role"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

async def require_staff(current_user: User = Depends(get_current_user)):
    """Require staff role (admin, manager, or sales rep)"""
    staff_roles = [UserRole.ADMIN, UserRole.MANAGER, UserRole.SALES_REP]
    if current_user.role not in staff_roles:
        raise HTTPException(status_code=403, detail="Staff access required")
    return current_user

# Optional authentication (for endpoints that work with or without auth)
async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None

# Export main components
__all__ = [
    'User', 'UserCreate', 'UserLogin', 'UserUpdate', 'UserRole', 'AccountStatus',
    'Token', 'TokenData', 'PasswordReset', 'PasswordChange',
    'AuthManager', 'auth_manager',
    'get_current_user', 'get_current_user_optional',
    'require_permissions', 'require_role', 'require_admin', 'require_staff',
    'get_user_permissions', 'ROLE_PERMISSIONS'
]
