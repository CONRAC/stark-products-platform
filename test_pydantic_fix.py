"""
Simple test to verify Pydantic v2 compatibility
"""

try:
    print("Testing Pydantic v2 compatibility...")
    
    # Test basic imports
    from models.base import ObjectIdStr, PyObjectId, MongoBaseModel
    print("✅ Base models imported successfully")
    
    # Test company model
    from models.company import CompanyCreate, CompanySize
    print("✅ Company models imported successfully")
    
    # Test a simple company creation
    company = CompanyCreate(
        name="Test Company",
        primary_email="test@company.com",
        size=CompanySize.SMALL
    )
    print(f"✅ Company model created: {company.name}")
    
    # Test analytics models
    from routes.analytics import QuoteMetrics
    
    metrics = QuoteMetrics(
        total_quotes=10,
        active_quotes=5,
        converted_quotes=2,
        conversion_rate=20.0,
        average_quote_value=5000.0,
        total_quote_value=50000.0
    )
    print(f"✅ Analytics model created: {metrics.conversion_rate}% conversion")
    
    print("\n🎉 All Pydantic v2 compatibility tests passed!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
