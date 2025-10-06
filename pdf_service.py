"""
Professional PDF Quote Generation Service for Stark Products
Creates branded, shareable PDF quotes for B2B customers
"""

import io
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from config import settings

class StarkProductsPDFTemplate(BaseDocTemplate):
    """Custom PDF template with branded header and footer"""
    
    def __init__(self, filename, **kwargs):
        self.company_info = {
            'name': settings.company_name,
            'email': settings.company_email,
            'phone': settings.company_phone,
            'address': settings.company_address
        }
        BaseDocTemplate.__init__(self, filename, pagesize=A4, **kwargs)
        
        # Define frame for content
        frame = Frame(
            30*mm, 30*mm, A4[0] - 60*mm, A4[1] - 60*mm,
            leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0
        )
        
        # Create page template
        page_template = PageTemplate(
            id='main',
            frames=[frame],
            onPage=self.add_page_decorations
        )
        
        self.addPageTemplates([page_template])
    
    def add_page_decorations(self, canvas, doc):
        """Add header and footer to each page"""
        canvas.saveState()
        
        # Header
        self.draw_header(canvas)
        
        # Footer  
        self.draw_footer(canvas, doc)
        
        canvas.restoreState()
    
    def draw_header(self, canvas):
        """Draw company header with logo and contact info"""
        # Company name and tagline
        canvas.setFont("Helvetica-Bold", 24)
        canvas.setFillColor(colors.HexColor('#1F2937'))  # Dark gray
        canvas.drawString(30*mm, A4[1] - 25*mm, self.company_info['name'])
        
        canvas.setFont("Helvetica", 12)
        canvas.setFillColor(colors.HexColor('#6B7280'))  # Medium gray
        canvas.drawString(30*mm, A4[1] - 32*mm, "Premium Bathroom Accessories")
        
        # Contact information (right side)
        contact_y = A4[1] - 25*mm
        contact_x = A4[0] - 70*mm
        
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.HexColor('#374151'))
        
        contact_info = [
            f"Phone: {self.company_info['phone']}",
            f"Email: {self.company_info['email']}",
            f"Web: www.starkproducts.co.za"
        ]
        
        for i, info in enumerate(contact_info):
            canvas.drawString(contact_x, contact_y - (i * 12), info)
        
        # Horizontal line
        canvas.setStrokeColor(colors.HexColor('#E5E7EB'))
        canvas.setLineWidth(1)
        canvas.line(30*mm, A4[1] - 45*mm, A4[0] - 30*mm, A4[1] - 45*mm)
    
    def draw_footer(self, canvas, doc):
        """Draw footer with page numbers and company address"""
        # Page number
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.HexColor('#6B7280'))
        page_text = f"Page {doc.page}"
        canvas.drawRightString(A4[0] - 30*mm, 20*mm, page_text)
        
        # Company address
        canvas.setFont("Helvetica", 8)
        canvas.drawString(30*mm, 20*mm, self.company_info['address'])
        
        # Terms note
        canvas.drawString(30*mm, 12*mm, "Terms: Quote valid for 30 days. Prices exclude VAT. E&OE.")

class QuotePDFGenerator:
    """Generate professional PDF quotes for B2B customers"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Define custom paragraph styles"""
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            textColor=colors.HexColor('#1F2937'),
            alignment=TA_LEFT
        ))
        
        # Section heading style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'], 
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#374151'),
            fontName='Helvetica-Bold'
        ))
        
        # Customer info style
        self.styles.add(ParagraphStyle(
            name='CustomerInfo',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=3,
            leftIndent=0
        ))
        
        # Table header style
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=colors.white,
            alignment=TA_CENTER
        ))
        
        # Notes style
        self.styles.add(ParagraphStyle(
            name='Notes',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=10,
            leftIndent=10,
            rightIndent=10,
            textColor=colors.HexColor('#6B7280')
        ))
    
    async def generate_quote_pdf(self, quote_data: Dict[str, Any], products_data: List[Dict[str, Any]]) -> bytes:
        """
        Generate a professional PDF quote
        
        Args:
            quote_data: Quote information from database
            products_data: List of products with details
            
        Returns:
            bytes: PDF content as bytes
        """
        
        # Create PDF buffer
        buffer = io.BytesIO()
        
        # Create document with custom template
        doc = StarkProductsPDFTemplate(buffer)
        
        # Build document content
        story = []
        
        # Quote header
        story.extend(self._create_quote_header(quote_data))
        
        # Customer information
        story.extend(self._create_customer_section(quote_data))
        
        # Quote items table
        story.extend(self._create_items_table(products_data, quote_data))
        
        # Pricing summary
        story.extend(self._create_pricing_summary(quote_data))
        
        # Terms and notes
        story.extend(self._create_terms_section(quote_data))
        
        # Next steps
        story.extend(self._create_next_steps_section())
        
        # Build PDF
        doc.build(story)
        
        # Return PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def _create_quote_header(self, quote_data: Dict[str, Any]) -> List:
        """Create quote header section"""
        story = []
        
        # Quote title and number
        quote_title = f"QUOTATION #{quote_data.get('id', 'DRAFT')[:8].upper()}"
        story.append(Paragraph(quote_title, self.styles['CustomTitle']))
        
        # Quote details table
        quote_details = [
            ['Quote Date:', datetime.utcnow().strftime('%d %B %Y')],
            ['Valid Until:', (datetime.utcnow() + timedelta(days=30)).strftime('%d %B %Y')],
            ['Status:', quote_data.get('status', 'pending').title()],
            ['Reference:', quote_data.get('id', 'DRAFT')[:12]]
        ]
        
        details_table = Table(quote_details, colWidths=[40*mm, 60*mm])
        details_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        story.append(details_table)
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_customer_section(self, quote_data: Dict[str, Any]) -> List:
        """Create customer information section"""
        story = []
        
        customer = quote_data.get('customer_info', {})
        
        story.append(Paragraph("CUSTOMER DETAILS", self.styles['SectionHeader']))
        
        customer_info = []
        if customer.get('name'):
            customer_info.append(f"<b>Contact:</b> {customer['name']}")
        if customer.get('company'):
            customer_info.append(f"<b>Company:</b> {customer['company']}")
        if customer.get('email'):
            customer_info.append(f"<b>Email:</b> {customer['email']}")
        if customer.get('phone'):
            customer_info.append(f"<b>Phone:</b> {customer['phone']}")
        if customer.get('address'):
            customer_info.append(f"<b>Address:</b> {customer['address']}")
        
        for info in customer_info:
            story.append(Paragraph(info, self.styles['CustomerInfo']))
        
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_items_table(self, products_data: List[Dict[str, Any]], quote_data: Dict[str, Any]) -> List:
        """Create quote items table"""
        story = []
        
        story.append(Paragraph("QUOTE ITEMS", self.styles['SectionHeader']))
        
        # Table headers
        headers = ['Description', 'Qty', 'Unit Price', 'Total Price']
        
        # Table data
        table_data = [headers]
        
        quote_items = quote_data.get('items', [])
        
        for item in quote_items:
            # Find product details
            product = next((p for p in products_data if p.get('id') == item.get('product_id')), {})
            
            description = f"{item.get('product_name', 'Unknown Product')}"
            if product.get('material'):
                description += f"\nMaterial: {product['material']}"
            if product.get('dimensions'):
                description += f"\nDimensions: {product['dimensions']}"
                
            quantity = str(item.get('quantity', 1))
            unit_price = f"R {item.get('unit_price', 0):,.2f}" if item.get('unit_price') else 'TBQ'
            
            if item.get('unit_price'):
                total_price = f"R {(item.get('unit_price', 0) * item.get('quantity', 1)):,.2f}"
            else:
                total_price = 'TBQ'
            
            table_data.append([description, quantity, unit_price, total_price])
        
        # Create table
        col_widths = [80*mm, 20*mm, 30*mm, 35*mm]
        items_table = Table(table_data, colWidths=col_widths)
        
        # Style the table
        table_style = [
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Center align qty, prices
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Left align descriptions
            
            # Borders and padding
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]
        
        # Alternate row colors
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F9FAFB')))
        
        items_table.setStyle(TableStyle(table_style))
        
        story.append(items_table)
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_pricing_summary(self, quote_data: Dict[str, Any]) -> List:
        """Create pricing summary section"""
        story = []
        
        total_estimate = quote_data.get('total_estimate', 0)
        
        if total_estimate:
            # Pricing breakdown
            subtotal = float(total_estimate)
            vat_rate = 0.15  # 15% VAT in South Africa
            vat_amount = subtotal * vat_rate
            total_incl_vat = subtotal + vat_amount
            
            pricing_data = [
                ['Subtotal (excl. VAT):', f"R {subtotal:,.2f}"],
                ['VAT (15%):', f"R {vat_amount:,.2f}"],
                ['', ''],  # Separator
                ['TOTAL (incl. VAT):', f"R {total_incl_vat:,.2f}"]
            ]
            
            pricing_table = Table(pricing_data, colWidths=[120*mm, 40*mm])
            pricing_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -2), 'Helvetica'),
                ('FONTNAME', (1, 0), (1, -2), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -2), 10),
                ('FONTSIZE', (0, -1), (-1, -1), 12),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1F2937')),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#374151')),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            
            story.append(pricing_table)
        else:
            story.append(Paragraph(
                "<b>PRICING:</b> To be quoted upon confirmation of requirements.",
                self.styles['Notes']
            ))
        
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_terms_section(self, quote_data: Dict[str, Any]) -> List:
        """Create terms and conditions section"""
        story = []
        
        story.append(Paragraph("TERMS & CONDITIONS", self.styles['SectionHeader']))
        
        terms = [
            "• Quote validity: 30 days from date of issue",
            "• Prices exclude VAT and delivery charges",
            "• Payment terms: 30 days from invoice date",
            "• Delivery: 7-14 working days from order confirmation",
            "• Installation services available at additional cost",
            "• All products carry manufacturer warranty",
            "• Prices subject to stock availability"
        ]
        
        for term in terms:
            story.append(Paragraph(term, self.styles['Normal']))
        
        # Add custom notes if provided
        if quote_data.get('notes'):
            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>ADDITIONAL NOTES:</b>", self.styles['SectionHeader']))
            story.append(Paragraph(quote_data['notes'], self.styles['Notes']))
        
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_next_steps_section(self) -> List:
        """Create next steps section"""
        story = []
        
        story.append(Paragraph("NEXT STEPS", self.styles['SectionHeader']))
        
        next_steps = """
        <b>To proceed with this quotation:</b><br/>
        1. Review all items and pricing<br/>
        2. Contact us to discuss any modifications<br/>
        3. Confirm your order via email or phone<br/>
        4. We'll prepare your products for delivery<br/><br/>
        
        <b>Questions or need to negotiate pricing?</b><br/>
        Contact our sales team for personalized service.
        """
        
        story.append(Paragraph(next_steps, self.styles['Normal']))
        
        return story

# Global PDF generator instance
pdf_generator = QuotePDFGenerator()

# Export main components
__all__ = ['QuotePDFGenerator', 'pdf_generator']
