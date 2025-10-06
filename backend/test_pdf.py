"""
Test script for PDF quote generation
"""

import asyncio
from datetime import datetime, timedelta
from pdf_service import pdf_generator

# Sample test data
sample_quote_data = {
    "id": "67412345678901234567890a",
    "customer_info": {
        "name": "John Smith",
        "company": "Smith Construction Ltd",
        "email": "john@smithconstruction.co.za",
        "phone": "+27 82 123 4567",
        "address": "123 Construction Ave, Johannesburg, 2000"
    },
    "items": [
        {
            "product_id": "67412345678901234567890b",
            "product_name": "Premium Towel Rail - Chrome",
            "quantity": 2,
            "unit_price": 450.00,
            "notes": "Wall mounted"
        },
        {
            "product_id": "67412345678901234567890c", 
            "product_name": "Modern Soap Dish - Matte Black",
            "quantity": 3,
            "unit_price": 125.00,
            "notes": "Counter mounted"
        },
        {
            "product_id": "67412345678901234567890d",
            "product_name": "Luxury Shower Tray - 1200x800",
            "quantity": 1,
            "unit_price": 2850.00,
            "notes": "Custom size - delivery in 2 weeks"
        }
    ],
    "status": "pending",
    "total_estimate": 3675.00,
    "notes": "Customer prefers chrome finishes. Installation required.",
    "admin_notes": "High-value customer - provide 5% discount if requested",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
    "expires_at": datetime.utcnow() + timedelta(days=30)
}

sample_products_data = [
    {
        "id": "67412345678901234567890b",
        "name": "Premium Towel Rail - Chrome",
        "material": "Stainless Steel",
        "dimensions": "600mm x 100mm x 50mm",
        "finish": "Chrome Plated",
        "category": "Towel Rails"
    },
    {
        "id": "67412345678901234567890c",
        "name": "Modern Soap Dish - Matte Black",
        "material": "Aluminum Alloy",
        "dimensions": "120mm x 90mm x 30mm", 
        "finish": "Matte Black Coating",
        "category": "Soap Dishes"
    },
    {
        "id": "67412345678901234567890d",
        "name": "Luxury Shower Tray - 1200x800",
        "material": "Acrylic Resin",
        "dimensions": "1200mm x 800mm x 50mm",
        "finish": "Anti-slip surface",
        "category": "Shower Trays"
    }
]

async def test_pdf_generation():
    """Test PDF generation with sample data"""
    try:
        print("Generating PDF quote...")
        
        pdf_bytes = await pdf_generator.generate_quote_pdf(
            sample_quote_data, 
            sample_products_data
        )
        
        # Save to file for testing
        filename = f"test_quote_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        with open(filename, 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"✅ PDF generated successfully: {filename}")
        print(f"   File size: {len(pdf_bytes):,} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ PDF generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_pdf_generation())
    if success:
        print("\n🎉 PDF generation test passed!")
    else:
        print("\n💥 PDF generation test failed!")
