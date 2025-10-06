"""
Email Service for Stark Products
Handles professional quote emails, notifications, and follow-up communications for B2B customers
"""

import logging
import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
from jinja2 import Environment, DictLoader
import io

from config import settings
from pdf_service import pdf_generator

logger = logging.getLogger(__name__)

class EmailTemplates:
    """Email template management"""
    
    def __init__(self):
        # Use DictLoader for inline templates
        templates = {
            'base.html': """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background-color: #1F2937; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666; }
        .button { 
            display: inline-block; 
            padding: 12px 24px; 
            background-color: #3B82F6; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ company_name }}</h1>
        <p>Premium Bathroom Accessories</p>
    </div>
    <div class="content">
        {{ content }}
    </div>
    <div class="footer">
        <p>
            <strong>{{ company_name }}</strong><br>
            Phone: {{ company_phone }} | Email: {{ company_email }}<br>
            {{ company_address }}
        </p>
        <p style="margin-top: 10px;">
            This email was sent from Stark Products. Please do not reply to this automated message.
        </p>
    </div>
</body>
</html>
            """
        }
        
        self.env = Environment(loader=DictLoader(templates))
    
    def render_template(self, template_name: str = 'base.html', **kwargs) -> str:
        """Render email template with provided data"""
        try:
            template = self.env.get_template(template_name)
            return template.render(
                company_name=settings.company_name,
                company_phone=settings.company_phone,
                company_email=settings.company_email,
                company_address=settings.company_address,
                **kwargs
            )
        except Exception as e:
            logger.warning(f"Template rendering failed: {e}")
            # Return basic HTML if template fails
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="background-color: #1F2937; color: white; padding: 20px; text-align: center;">
                    <h1>{settings.company_name}</h1>
                    <p>Premium Bathroom Accessories</p>
                </div>
                <div style="padding: 20px;">
                    {kwargs.get('content', 'Email content')}
                </div>
                <div style="background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px;">
                    <p>{settings.company_name} | {settings.company_phone} | {settings.company_email}</p>
                </div>
            </body>
            </html>
            """

class EmailService:
    """Professional email service for B2B communications"""
    
    def __init__(self):
        self.templates = EmailTemplates()
        self.smtp_server = settings.mail_server
        self.smtp_port = settings.mail_port
        self.username = settings.mail_username
        self.password = settings.mail_password
        self.from_email = settings.mail_from
        self.from_name = settings.mail_from_name
    
    async def send_email(
        self,
        to_emails: Union[str, List[str]],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        """Send email with HTML content and optional attachments"""
        
        if not settings.email_configured:
            logger.warning("Email not configured - skipping email send")
            return False
        
        try:
            # Prepare email addresses
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ", ".join(to_emails)
            msg['Subject'] = subject
            
            if cc_emails:
                msg['Cc'] = ", ".join(cc_emails)
            
            # Add text content
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    if 'content' in attachment and 'filename' in attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment['content'])
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {attachment["filename"]}'
                        )
                        msg.attach(part)
            
            # Send email
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.username, self.password)
                
                # Prepare recipient list
                recipients = to_emails.copy()
                if cc_emails:
                    recipients.extend(cc_emails)
                if bcc_emails:
                    recipients.extend(bcc_emails)
                
                server.send_message(msg, to_addrs=recipients)
            
            logger.info(f"Email sent successfully to {to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    async def send_quote_email(
        self,
        quote_data: Dict[str, Any],
        products_data: List[Dict[str, Any]],
        recipient_email: str,
        include_pdf: bool = True,
        custom_message: Optional[str] = None
    ) -> bool:
        """Send professional quote email to customer"""
        
        try:
            customer_info = quote_data.get('customer_info', {})
            customer_name = customer_info.get('name', 'Valued Customer')
            company_name = customer_info.get('company', '')
            
            # Generate quote PDF if requested
            attachments = []
            if include_pdf:
                pdf_bytes = await pdf_generator.generate_quote_pdf(quote_data, products_data)
                quote_filename = f"Quote_{quote_data.get('id', 'draft')[:8]}"
                if company_name:
                    safe_company = "".join(c for c in company_name if c.isalnum() or c in " -_").strip()
                    quote_filename += f"_{safe_company}"
                quote_filename += ".pdf"
                
                attachments.append({
                    'content': pdf_bytes,
                    'filename': quote_filename
                })
            
            # Calculate totals for email
            total_items = len(quote_data.get('items', []))
            total_estimate = quote_data.get('total_estimate')
            
            # Prepare email content
            content_data = {
                'customer_name': customer_name,
                'company_name': company_name,
                'quote_id': quote_data.get('id', 'DRAFT')[:8].upper(),
                'quote_date': datetime.utcnow().strftime('%d %B %Y'),
                'total_items': total_items,
                'total_estimate': f"R {total_estimate:,.2f}" if total_estimate else "To be quoted",
                'custom_message': custom_message,
                'items': quote_data.get('items', []),
                'quote_expires': (datetime.utcnow() + timedelta(days=30)).strftime('%d %B %Y'),
                'include_pdf': include_pdf
            }
            
            # Email content
            email_content = f"""
            <h2>Thank you for your interest in Stark Products!</h2>
            
            <p>Dear {customer_name},</p>
            
            <p>Thank you for requesting a quote from Stark Products. Please find your personalized quotation {"attached as a PDF" if include_pdf else "details below"}.</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Quote Summary</h3>
                <p><strong>Quote Reference:</strong> #{content_data['quote_id']}</p>
                <p><strong>Quote Date:</strong> {content_data['quote_date']}</p>
                <p><strong>Total Items:</strong> {total_items}</p>
                <p><strong>Estimated Total:</strong> {content_data['total_estimate']}</p>
                <p><strong>Valid Until:</strong> {content_data['quote_expires']}</p>
            </div>
            
            {f"<div style='background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;'><p><strong>Personal Message:</strong></p><p>{custom_message}</p></div>" if custom_message else ""}
            
            <h3>What's Next?</h3>
            <ol>
                <li>Review your quote {"in the attached PDF" if include_pdf else "details"}</li>
                <li>Contact us if you have any questions or need modifications</li>
                <li>Reply to confirm your order when ready</li>
            </ol>
            
            <p>Our team is here to help with any questions you may have. We look forward to working with you!</p>
            
            <div style="margin: 30px 0;">
                <a href="tel:{settings.company_phone}" class="button">Call Us: {settings.company_phone}</a>
                <a href="mailto:{settings.company_email}" class="button">Email Us</a>
            </div>
            
            <p>Best regards,<br>
            <strong>The Stark Products Team</strong><br>
            Premium Bathroom Accessories</p>
            """
            
            # Render final email
            html_content = self.templates.render_template('base.html', content=email_content)
            
            # Subject line
            subject = f"Quote #{content_data['quote_id']} from Stark Products"
            if company_name:
                subject += f" - {company_name}"
            
            # Send email
            return await self.send_email(
                to_emails=recipient_email,
                subject=subject,
                html_content=html_content,
                attachments=attachments
            )
            
        except Exception as e:
            logger.error(f"Failed to send quote email: {str(e)}")
            return False
    
    async def send_quote_status_notification(
        self,
        quote_data: Dict[str, Any],
        new_status: str,
        recipient_email: str,
        admin_notes: Optional[str] = None
    ) -> bool:
        """Send notification when quote status changes"""
        
        try:
            customer_info = quote_data.get('customer_info', {})
            customer_name = customer_info.get('name', 'Valued Customer')
            quote_id = quote_data.get('id', 'DRAFT')[:8].upper()
            
            # Status-specific content
            status_messages = {
                'approved': {
                    'title': 'Great news! Your quote has been approved',
                    'message': 'We\'re pleased to confirm that your quote has been approved and is ready for processing.',
                    'action': 'Contact us to proceed with your order'
                },
                'rejected': {
                    'title': 'Quote Status Update',
                    'message': 'We\'ve reviewed your quote and unfortunately cannot proceed as submitted.',
                    'action': 'Contact us to discuss alternative options'
                },
                'expired': {
                    'title': 'Quote Expiration Notice',
                    'message': 'Your quote has expired as of today. We\'d be happy to provide a new quote.',
                    'action': 'Contact us for a new quote'
                }
            }
            
            status_info = status_messages.get(new_status, {
                'title': 'Quote Status Update',
                'message': f'Your quote status has been updated to: {new_status.title()}',
                'action': 'Contact us if you have any questions'
            })
            
            # Email content
            email_content = f"""
            <h2>{status_info['title']}</h2>
            
            <p>Dear {customer_name},</p>
            
            <p>{status_info['message']}</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Quote Reference:</strong> #{quote_id}</p>
                <p><strong>New Status:</strong> {new_status.title()}</p>
                <p><strong>Date:</strong> {datetime.utcnow().strftime('%d %B %Y')}</p>
            </div>
            
            {f"<div style='background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;'><p><strong>Additional Information:</strong></p><p>{admin_notes}</p></div>" if admin_notes else ""}
            
            <p><strong>Next Steps:</strong> {status_info['action']}</p>
            
            <div style="margin: 30px 0;">
                <a href="tel:{settings.company_phone}" class="button">Call Us: {settings.company_phone}</a>
                <a href="mailto:{settings.company_email}" class="button">Email Us</a>
            </div>
            
            <p>Thank you for choosing Stark Products.</p>
            
            <p>Best regards,<br>
            <strong>The Stark Products Team</strong></p>
            """
            
            # Render email
            html_content = self.templates.render_template('base.html', content=email_content)
            
            # Send email
            return await self.send_email(
                to_emails=recipient_email,
                subject=f"Quote #{quote_id} Status Update - {status_info['title']}",
                html_content=html_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send status notification: {str(e)}")
            return False
    
    async def send_follow_up_email(
        self,
        quote_data: Dict[str, Any],
        recipient_email: str,
        follow_up_type: str = "general"
    ) -> bool:
        """Send follow-up email for pending quotes"""
        
        try:
            customer_info = quote_data.get('customer_info', {})
            customer_name = customer_info.get('name', 'Valued Customer')
            quote_id = quote_data.get('id', 'DRAFT')[:8].upper()
            days_since_quote = (datetime.utcnow() - quote_data.get('created_at', datetime.utcnow())).days
            
            # Follow-up type content
            if follow_up_type == "reminder":
                title = "Friendly Reminder - Your Stark Products Quote"
                message = f"We wanted to follow up on the quote we sent you {days_since_quote} days ago."
            elif follow_up_type == "expiring":
                title = "Your Quote Expires Soon"
                message = "Your quote will expire in 3 days. We wanted to remind you in case you'd like to proceed."
            else:
                title = "Following Up on Your Quote"
                message = "We hope you've had a chance to review your quote from Stark Products."
            
            # Email content
            email_content = f"""
            <h2>{title}</h2>
            
            <p>Dear {customer_name},</p>
            
            <p>{message}</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Quote Reference:</strong> #{quote_id}</p>
                <p><strong>Quote Date:</strong> {quote_data.get('created_at', datetime.utcnow()).strftime('%d %B %Y')}</p>
                <p><strong>Total Items:</strong> {len(quote_data.get('items', []))}</p>
            </div>
            
            <p>We're here to help if you have any questions about:</p>
            <ul>
                <li>Product specifications or alternatives</li>
                <li>Pricing or payment terms</li>
                <li>Delivery schedules</li>
                <li>Installation services</li>
            </ul>
            
            <div style="margin: 30px 0;">
                <a href="tel:{settings.company_phone}" class="button">Call Us: {settings.company_phone}</a>
                <a href="mailto:{settings.company_email}" class="button">Email Us</a>
            </div>
            
            <p>We appreciate your interest and look forward to hearing from you soon.</p>
            
            <p>Best regards,<br>
            <strong>The Stark Products Team</strong></p>
            """
            
            # Render email
            html_content = self.templates.render_template('base.html', content=email_content)
            
            # Send email
            return await self.send_email(
                to_emails=recipient_email,
                subject=f"{title} - Quote #{quote_id}",
                html_content=html_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send follow-up email: {str(e)}")
            return False
    
    async def send_internal_notification(
        self,
        subject: str,
        message: str,
        recipient_emails: List[str],
        priority: str = "normal"
    ) -> bool:
        """Send internal notifications to staff"""
        
        try:
            # Priority styling
            priority_styles = {
                "high": {"color": "#dc3545", "bg": "#f8d7da"},
                "medium": {"color": "#fd7e14", "bg": "#fff3cd"},
                "normal": {"color": "#28a745", "bg": "#d4edda"}
            }
            
            style = priority_styles.get(priority, priority_styles["normal"])
            
            # Email content
            email_content = f"""
            <div style="background-color: {style['bg']}; color: {style['color']}; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Internal Notification - {priority.upper()} Priority</h3>
            </div>
            
            <p>{message}</p>
            
            <p><strong>Time:</strong> {datetime.utcnow().strftime('%d %B %Y at %H:%M')}</p>
            
            <p>This is an automated notification from the Stark Products system.</p>
            """
            
            # Render email
            html_content = self.templates.render_template('base.html', content=email_content)
            
            # Send email
            return await self.send_email(
                to_emails=recipient_emails,
                subject=f"[STARK PRODUCTS] {subject}",
                html_content=html_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send internal notification: {str(e)}")
            return False

# Create global email service instance
email_service = EmailService()

# Export main components
__all__ = ['EmailService', 'email_service']
