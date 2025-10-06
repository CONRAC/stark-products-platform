"""
Configuration management for Stark Products API
Handles environment variables, validation, and configuration defaults
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import EmailStr, field_validator
from enum import Enum

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Database Configuration
    mongo_url: str = "mongodb://localhost:27017"
    db_name: str = "stark_products"
    
    # Email Configuration
    mail_server: str = "smtp.gmail.com"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: str = ""
    mail_from: EmailStr = "noreply@starkproducts.co.za"
    mail_from_name: str = "Stark Products"
    
    # Security Configuration
    jwt_secret: str = "change-this-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # CORS Configuration
    cors_origins: str = "http://localhost:3000"
    
    # API Configuration
    api_prefix: str = "/api"
    api_version: str = "v1"
    max_upload_size: int = 10485760  # 10MB
    
    # Application Settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: LogLevel = LogLevel.INFO
    
    # Business Configuration
    company_name: str = "Stark Products"
    company_email: EmailStr = "info@starkproducts.co.za"
    company_phone: str = "+27 11 902 8678"
    company_address: str = "Stand 110, Black Reef Road, Wittkrante, Germiston"
    
    # Stock Management
    low_stock_threshold: int = 10
    stock_alert_email: EmailStr = "admin@starkproducts.co.za"
    
    # File Storage
    upload_dir: str = "./uploads"
    max_file_size: int = 5242880  # 5MB
    allowed_extensions: str = "jpg,jpeg,png,gif,webp"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_password: str = ""
    
    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000
    
    @field_validator('cors_origins')
    @classmethod
    def validate_cors_origins(cls, v):
        """Convert CORS origins string to list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    @field_validator('allowed_extensions')
    @classmethod
    def validate_allowed_extensions(cls, v):
        """Convert allowed extensions string to list"""
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(',') if ext.strip()]
        return v
    
    @field_validator('jwt_secret')
    @classmethod
    def validate_jwt_secret(cls, v, info):
        """Ensure JWT secret is secure in production"""
        # Access other fields through info.data
        environment = info.data.get('environment') if info.data else None
        if environment == Environment.PRODUCTION:
            if len(v) < 32 or v == "change-this-secret-key-in-production":
                raise ValueError("JWT secret must be at least 32 characters in production")
        return v
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        return self.cors_origins if isinstance(self.cors_origins, list) else [self.cors_origins]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Get allowed file extensions as a list"""
        return self.allowed_extensions if isinstance(self.allowed_extensions, list) else [self.allowed_extensions]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def email_configured(self) -> bool:
        """Check if email is properly configured"""
        return bool(self.mail_username and self.mail_password)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get application settings"""
    return settings

def setup_logging():
    """Setup application logging based on configuration"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    if settings.is_development:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    
    logging.basicConfig(
        level=getattr(logging, settings.log_level.value),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log') if not settings.is_development else logging.NullHandler()
        ]
    )
    
    # Reduce noise from some libraries in production
    if settings.is_production:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("motor").setLevel(logging.WARNING)

def validate_environment():
    """Validate that all required environment variables are set"""
    errors = []
    
    if settings.is_production:
        if not settings.mongo_url or settings.mongo_url == "mongodb://localhost:27017":
            errors.append("MONGO_URL must be set for production")
        
        if settings.jwt_secret == "change-this-secret-key-in-production":
            errors.append("JWT_SECRET must be changed for production")
        
        if settings.cors_origins == ["*"]:
            errors.append("CORS_ORIGINS should not be '*' in production")
    
    if errors:
        raise ValueError(f"Environment validation failed: {'; '.join(errors)}")

def create_upload_directories():
    """Create necessary upload directories"""
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (upload_path / "products").mkdir(exist_ok=True)
    (upload_path / "temp").mkdir(exist_ok=True)

# Initialize configuration
if __name__ != "__main__":
    setup_logging()
    validate_environment()
    create_upload_directories()
    
    logger = logging.getLogger(__name__)
    logger.info(f"Configuration loaded: Environment={settings.environment.value}")
    
    if settings.debug:
        logger.debug(f"Debug mode enabled")
        logger.debug(f"Database: {settings.db_name}")
        logger.debug(f"Email configured: {settings.email_configured}")
