import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import os
from jinja2 import Template
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")

        if not all([self.sender_email, self.sender_password]):
            logger.warning("Email service not configured. Missing SMTP credentials.")

    def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        template_vars: Dict[str, Any],
        html_template: Optional[str] = None,
        text_template: Optional[str] = None
    ) -> bool:
        """
        Send an email using a template with variable substitution.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            template_name: Name of the template to use (for logging)
            template_vars: Dictionary of variables to substitute in templates
            html_template: HTML template string (optional)
            text_template: Plain text template string (optional)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.sender_email or not self.sender_password:
            logger.error("Email service not configured")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = to_email

            # Prepare templates
            text_content = None
            html_content = None

            if text_template:
                template = Template(text_template)
                text_content = template.render(**template_vars)

            if html_template:
                template = Template(html_template)
                html_content = template.render(**template_vars)

            # Add text part
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)

            # Add HTML part (preferred by most email clients)
            if html_content:
                html_part = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(html_part)
            elif text_content:
                # If no HTML template, convert text to HTML
                html_content = text_content.replace('\n', '<br>')
                html_part = MIMEText(f"<html><body>{html_content}</body></html>", 'html', 'utf-8')
                msg.attach(html_part)

            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, to_email, text)
            server.quit()

            logger.info(f"Email sent successfully to {to_email} using template: {template_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def send_template_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        template_vars: Dict[str, Any]
    ) -> bool:
        """
        Send an email using predefined templates.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            template_name: Name of the predefined template
            template_vars: Dictionary of variables for template substitution

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from . import templates

        # Get template content
        template_content = getattr(templates, template_name, None)
        if not template_content:
            logger.error(f"Template '{template_name}' not found")
            return False

        html_template = template_content.get('html')
        text_template = template_content.get('text')
        default_subject = template_content.get('subject', subject)

        return self.send_email(
            to_email=to_email,
            subject=default_subject if subject == default_subject else subject,
            template_name=template_name,
            template_vars=template_vars,
            html_template=html_template,
            text_template=text_template
        )


# Global email service instance
email_service = EmailService()


def send_email_with_template(
    to_email: str,
    subject: str,
    template_name: str,
    template_vars: Dict[str, Any]
) -> bool:
    """
    Convenience function to send email with template.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        template_name: Name of the predefined template
        template_vars: Dictionary of variables for template substitution

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    return email_service.send_template_email(to_email, subject, template_name, template_vars)


def send_custom_email(
    to_email: str,
    subject: str,
    html_template: str,
    text_template: Optional[str] = None,
    template_vars: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send a custom email with provided templates.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_template: HTML template string
        text_template: Plain text template string (optional)
        template_vars: Dictionary of variables for template substitution (optional)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    template_vars = template_vars or {}
    return email_service.send_email(
        to_email=to_email,
        subject=subject,
        template_name="custom",
        template_vars=template_vars,
        html_template=html_template,
        text_template=text_template
    )