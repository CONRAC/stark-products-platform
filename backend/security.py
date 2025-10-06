"""
Security utilities for Stark Products API
Includes rate limiting, input validation, and security headers
"""

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from collections import defaultdict
import re
import logging

from config import settings

logger = logging.getLogger(__name__)

# Rate limiting storage (in production, use Redis)
request_counts = defaultdict(lambda: defaultdict(int))
request_timestamps = defaultdict(lambda: defaultdict(list))

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    @staticmethod
    def get_client_id(request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use X-Forwarded-For if behind proxy, otherwise use client IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host
        
        # Add user agent for additional uniqueness
        user_agent = request.headers.get("User-Agent", "")
        return hashlib.sha256(f"{client_ip}:{user_agent}".encode()).hexdigest()[:16]
    
    @staticmethod
    def is_rate_limited(client_id: str, limit_per_minute: int = None, limit_per_hour: int = None) -> bool:
        """Check if client is rate limited"""
        current_time = time.time()
        
        # Use config defaults if not specified
        if limit_per_minute is None:
            limit_per_minute = settings.rate_limit_per_minute
        if limit_per_hour is None:
            limit_per_hour = settings.rate_limit_per_hour
        
        # Clean old timestamps
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        # Filter timestamps for the last minute and hour
        request_timestamps[client_id]["minute"] = [
            ts for ts in request_timestamps[client_id]["minute"] if ts > minute_ago
        ]
        request_timestamps[client_id]["hour"] = [
            ts for ts in request_timestamps[client_id]["hour"] if ts > hour_ago
        ]
        
        # Check limits
        minute_count = len(request_timestamps[client_id]["minute"])
        hour_count = len(request_timestamps[client_id]["hour"])
        
        if minute_count >= limit_per_minute or hour_count >= limit_per_hour:
            logger.warning(f"Rate limit exceeded for client {client_id}: {minute_count}/min, {hour_count}/hour")
            return True
        
        # Add current request timestamp
        request_timestamps[client_id]["minute"].append(current_time)
        request_timestamps[client_id]["hour"].append(current_time)
        
        return False

def rate_limit_dependency(request: Request):
    """FastAPI dependency for rate limiting"""
    if not settings.is_development:  # Skip rate limiting in development
        client_id = RateLimiter.get_client_id(request)
        
        if RateLimiter.is_rate_limited(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )

class InputValidator:
    """Input validation utilities"""
    
    # Common regex patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^\+?[\d\s\-\(\)]{10,}$')
    SQL_INJECTION_PATTERNS = [
        re.compile(r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)', re.IGNORECASE),
        re.compile(r'(\b(UNION|OR|AND)\b.*=.*\b(UNION|OR|AND)\b)', re.IGNORECASE),
        re.compile(r'[\'";]', re.IGNORECASE)
    ]
    XSS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE)
    ]
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        return bool(InputValidator.EMAIL_PATTERN.match(email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format"""
        return bool(InputValidator.PHONE_PATTERN.match(phone))
    
    @staticmethod
    def check_sql_injection(text: str) -> bool:
        """Check for potential SQL injection attempts"""
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if pattern.search(text):
                return True
        return False
    
    @staticmethod
    def check_xss(text: str) -> bool:
        """Check for potential XSS attempts"""
        for pattern in InputValidator.XSS_PATTERNS:
            if pattern.search(text):
                return True
        return False
    
    @staticmethod
    def sanitize_input(text: str, max_length: int = 1000) -> str:
        """Sanitize user input"""
        if not isinstance(text, str):
            return ""
        
        # Truncate to max length
        text = text[:max_length]
        
        # Remove potential XSS
        for pattern in InputValidator.XSS_PATTERNS:
            text = pattern.sub('', text)
        
        # Basic HTML escape
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        
        return text.strip()
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str] = None) -> bool:
        """Validate file extension"""
        if allowed_extensions is None:
            allowed_extensions = settings.allowed_extensions_list
        
        if not filename or '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in allowed_extensions

def validate_input_security(data: Dict) -> Dict:
    """Validate input data for security issues"""
    errors = []
    
    for key, value in data.items():
        if isinstance(value, str):
            if InputValidator.check_sql_injection(value):
                errors.append(f"Potential SQL injection detected in {key}")
            
            if InputValidator.check_xss(value):
                errors.append(f"Potential XSS detected in {key}")
    
    if errors:
        logger.warning(f"Security validation failed: {errors}")
        raise HTTPException(status_code=400, detail="Invalid input detected")
    
    return data

class SecurityHeaders:
    """Security headers middleware"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers"""
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' ws: wss:;"
            ),
        }
        
        if settings.is_production:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return headers

def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(length)

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash password with salt"""
    if salt is None:
        salt = secrets.token_hex(32)
    
    # Use PBKDF2 with SHA256
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # iterations
    )
    
    return password_hash.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify password against hash"""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, password_hash)

class SecurityAudit:
    """Security audit logging"""
    
    @staticmethod
    def log_security_event(event_type: str, client_id: str, details: Dict = None):
        """Log security-related events"""
        audit_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "client_id": client_id,
            "details": details or {}
        }
        
        logger.warning(f"SECURITY AUDIT: {audit_data}")
        
        # In production, send to security monitoring system
        if settings.is_production:
            # TODO: Integrate with security monitoring (e.g., Sentry, DataDog)
            pass
    
    @staticmethod
    def log_failed_auth(client_id: str, username: str = None):
        """Log failed authentication attempts"""
        SecurityAudit.log_security_event(
            "FAILED_AUTH",
            client_id,
            {"username": username, "timestamp": datetime.utcnow().isoformat()}
        )
    
    @staticmethod
    def log_rate_limit_exceeded(client_id: str):
        """Log rate limit violations"""
        SecurityAudit.log_security_event(
            "RATE_LIMIT_EXCEEDED",
            client_id,
            {"timestamp": datetime.utcnow().isoformat()}
        )
    
    @staticmethod
    def log_suspicious_input(client_id: str, input_type: str, content: str):
        """Log suspicious input attempts"""
        SecurityAudit.log_security_event(
            "SUSPICIOUS_INPUT",
            client_id,
            {
                "input_type": input_type,
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Security dependencies for FastAPI
security_scheme = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """Get current authenticated user (placeholder for future implementation)"""
    # TODO: Implement JWT token validation
    # For now, return None (no authentication)
    return None

# Export main components
__all__ = [
    'RateLimiter',
    'InputValidator', 
    'SecurityHeaders',
    'SecurityAudit',
    'rate_limit_dependency',
    'validate_input_security',
    'generate_secure_token',
    'hash_password',
    'verify_password',
    'get_current_user'
]
