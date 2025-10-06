"""
Authentication API routes for Stark Products
Handles user registration, login, password management, and user operations
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.security import HTTPAuthorizationCredentials

from auth import (
    User, UserCreate, UserLogin, UserUpdate, UserRole, AccountStatus,
    Token, PasswordReset, PasswordChange, auth_manager,
    get_current_user, get_current_user_optional, require_admin, require_staff
)
from security import RateLimiter, SecurityAudit, validate_input_security
from config import settings

# Create router
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

# User management router  
users_router = APIRouter(prefix="/users", tags=["User Management"])

async def get_db():
    """Get database connection - imported to avoid circular dependency"""
    from server import db
    return db

async def send_verification_email(email: str, token: str):
    """Send email verification email"""
    # TODO: Implement email sending using the mail service
    # This is a placeholder for the email verification functionality
    print(f"TODO: Send verification email to {email} with token {token}")

async def send_password_reset_email(email: str, token: str):
    """Send password reset email"""
    # TODO: Implement email sending using the mail service
    print(f"TODO: Send password reset email to {email} with token {token}")

# Authentication endpoints
@auth_router.post("/register", response_model=dict)
async def register_user(
    user_data: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """Register a new user account"""
    
    # Rate limiting for registration
    client_id = RateLimiter.get_client_id(request)
    if RateLimiter.is_rate_limited(client_id, limit_per_minute=5):
        raise HTTPException(status_code=429, detail="Too many registration attempts")
    
    # Validate input for security issues
    validate_input_security(user_data.dict())
    
    # Check if user already exists
    existing_user = await db.users.find_one({
        "$or": [
            {"email": user_data.email},
            {"username": user_data.username}
        ]
    })
    
    if existing_user:
        if existing_user["email"] == user_data.email:
            raise HTTPException(status_code=400, detail="Email already registered")
        else:
            raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user object
    hashed_password = auth_manager.hash_password(user_data.password)
    verification_token = secrets.token_urlsafe(32)
    
    user = User(
        email=user_data.email,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role if user_data.role != UserRole.ADMIN else UserRole.CUSTOMER,  # Prevent self-promotion to admin
        company_name=user_data.company_name,
        phone=user_data.phone,
        position=user_data.position,
        email_verification_token=verification_token,
        status=AccountStatus.PENDING_VERIFICATION
    )
    
    # Add hashed password to user document (not in the model for security)
    user_doc = user.dict()
    user_doc["password_hash"] = hashed_password
    
    # Insert user into database
    await db.users.insert_one(user_doc)
    
    # Send verification email
    background_tasks.add_task(send_verification_email, user.email, verification_token)
    
    # Log security event
    SecurityAudit.log_security_event("USER_REGISTERED", client_id, {
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    })
    
    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "email": user.email,
        "verification_required": True
    }

@auth_router.post("/login", response_model=dict)
async def login_user(
    login_data: UserLogin,
    request: Request,
    db = Depends(get_db)
):
    """Authenticate user and return JWT tokens"""
    
    client_id = RateLimiter.get_client_id(request)
    
    # Rate limiting for login attempts
    if RateLimiter.is_rate_limited(client_id, limit_per_minute=10):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    
    # Find user by email or username
    user_doc = await db.users.find_one({
        "$or": [
            {"email": login_data.email_or_username.lower()},
            {"username": login_data.email_or_username.lower()}
        ]
    })
    
    if not user_doc:
        SecurityAudit.log_failed_auth(client_id, login_data.email_or_username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = User(**user_doc)
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        time_left = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
        raise HTTPException(
            status_code=401, 
            detail=f"Account locked. Try again in {time_left} minutes"
        )
    
    # Verify password
    if not auth_manager.verify_password(login_data.password, user_doc["password_hash"]):
        # Increment login attempts
        new_attempts = user.login_attempts + 1
        update_data = {"login_attempts": new_attempts}
        
        # Lock account after 5 failed attempts
        if new_attempts >= 5:
            update_data["locked_until"] = datetime.utcnow() + timedelta(minutes=30)
        
        await db.users.update_one({"id": user.id}, {"$set": update_data})
        
        SecurityAudit.log_failed_auth(client_id, login_data.email_or_username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check account status
    if user.status == AccountStatus.SUSPENDED:
        raise HTTPException(status_code=401, detail="Account suspended")
    
    if user.status == AccountStatus.INACTIVE:
        raise HTTPException(status_code=401, detail="Account deactivated")
    
    # Reset login attempts and update last login
    await db.users.update_one(
        {"id": user.id},
        {
            "$set": {
                "login_attempts": 0,
                "locked_until": None,
                "last_login": datetime.utcnow()
            }
        }
    )
    
    # Create JWT tokens
    tokens = auth_manager.create_tokens(user)
    
    # Log successful login
    SecurityAudit.log_security_event("USER_LOGIN", client_id, {
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    })
    
    return {
        "message": "Login successful",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "company_name": user.company_name
        },
        "tokens": tokens.dict()
    }

@auth_router.post("/logout")
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Logout current user (invalidate token on client side)"""
    
    client_id = RateLimiter.get_client_id(request)
    
    # Log logout event
    SecurityAudit.log_security_event("USER_LOGOUT", client_id, {
        "user_id": current_user.id,
        "email": current_user.email
    })
    
    return {"message": "Logged out successfully"}

@auth_router.post("/verify-email")
async def verify_email(
    token: str,
    db = Depends(get_db)
):
    """Verify user email with verification token"""
    
    user_doc = await db.users.find_one({"email_verification_token": token})
    if not user_doc:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    # Activate user account
    await db.users.update_one(
        {"id": user_doc["id"]},
        {
            "$set": {
                "status": AccountStatus.ACTIVE,
                "email_verified": True,
                "email_verification_token": None,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Email verified successfully"}

@auth_router.post("/forgot-password")
async def forgot_password(
    email: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """Request password reset"""
    
    client_id = RateLimiter.get_client_id(request)
    
    # Rate limiting
    if RateLimiter.is_rate_limited(client_id, limit_per_minute=3):
        raise HTTPException(status_code=429, detail="Too many password reset requests")
    
    user_doc = await db.users.find_one({"email": email.lower()})
    if not user_doc:
        # Don't reveal if email exists - always return success
        return {"message": "If the email exists, a password reset link has been sent"}
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    await db.users.update_one(
        {"id": user_doc["id"]},
        {
            "$set": {
                "password_reset_token": reset_token,
                "password_reset_expires": expires_at,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Send reset email
    background_tasks.add_task(send_password_reset_email, email, reset_token)
    
    return {"message": "If the email exists, a password reset link has been sent"}

@auth_router.post("/reset-password")
async def reset_password(
    reset_data: PasswordReset,
    db = Depends(get_db)
):
    """Reset password with token"""
    
    user_doc = await db.users.find_one({
        "password_reset_token": reset_data.token,
        "password_reset_expires": {"$gt": datetime.utcnow()}
    })
    
    if not user_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Hash new password
    new_password_hash = auth_manager.hash_password(reset_data.new_password)
    
    # Update password and clear reset token
    await db.users.update_one(
        {"id": user_doc["id"]},
        {
            "$set": {
                "password_hash": new_password_hash,
                "password_reset_token": None,
                "password_reset_expires": None,
                "login_attempts": 0,
                "locked_until": None,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Password reset successfully"}

@auth_router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Change user password"""
    
    # Get current password hash
    user_doc = await db.users.find_one({"id": current_user.id})
    
    # Verify current password
    if not auth_manager.verify_password(password_data.current_password, user_doc["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Hash new password
    new_password_hash = auth_manager.hash_password(password_data.new_password)
    
    # Update password
    await db.users.update_one(
        {"id": current_user.id},
        {
            "$set": {
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Password changed successfully"}

@auth_router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@auth_router.put("/me", response_model=User)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Update current user profile"""
    
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    await db.users.update_one({"id": current_user.id}, {"$set": update_data})
    
    # Return updated user
    updated_user_doc = await db.users.find_one({"id": current_user.id})
    return User(**updated_user_doc)

# User management endpoints (for admins)
@users_router.get("/", response_model=List[User])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    role: Optional[UserRole] = None,
    status: Optional[AccountStatus] = None,
    current_user: User = Depends(require_staff),
    db = Depends(get_db)
):
    """List users (staff only)"""
    
    query = {}
    if role:
        query["role"] = role
    if status:
        query["status"] = status
    
    # Non-admins can only see customers
    if current_user.role != UserRole.ADMIN:
        query["role"] = UserRole.CUSTOMER
    
    users = await db.users.find(query).skip(skip).limit(limit).to_list(limit)
    return [User(**user) for user in users]

@users_router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_staff),
    db = Depends(get_db)
):
    """Get user by ID (staff only)"""
    
    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = User(**user_doc)
    
    # Non-admins can only view customers or their own profile
    if current_user.role != UserRole.ADMIN:
        if user.role != UserRole.CUSTOMER and user.id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return user

@users_router.post("/", response_model=User)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db = Depends(get_db)
):
    """Create new user (admin only)"""
    
    # Check if user already exists
    existing_user = await db.users.find_one({
        "$or": [
            {"email": user_data.email},
            {"username": user_data.username}
        ]
    })
    
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user
    hashed_password = auth_manager.hash_password(user_data.password)
    
    user = User(
        email=user_data.email,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
        company_name=user_data.company_name,
        phone=user_data.phone,
        position=user_data.position,
        status=AccountStatus.ACTIVE,  # Admin-created users are active immediately
        email_verified=True,
        created_by=current_user.id
    )
    
    user_doc = user.dict()
    user_doc["password_hash"] = hashed_password
    
    await db.users.insert_one(user_doc)
    
    return user

@users_router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(require_admin),
    db = Depends(get_db)
):
    """Update user (admin only)"""
    
    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    await db.users.update_one({"id": user_id}, {"$set": update_data})
    
    updated_user_doc = await db.users.find_one({"id": user_id})
    return User(**updated_user_doc)

@users_router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db = Depends(get_db)
):
    """Delete user (admin only)"""
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}

# Export routers
__all__ = ['auth_router', 'users_router']
