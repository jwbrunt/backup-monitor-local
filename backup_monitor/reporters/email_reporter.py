"""Email reporter for sending backup monitoring reports."""

import logging
import smtplib
import subprocess
import tempfile
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional


class EmailReporter:
    """Handles sending backup reports via email."""
    
    def __init__(self, smtp_server: str = None, smtp_port: int = 587, smtp_user: str = None,
                 smtp_pass: str = None, from_address: str = None, 
                 to_addresses: List[str] = None, use_tls: bool = True, use_sendemail: bool = False):
        """Initialize email reporter.
        
        Args:
            smtp_server: SMTP server hostname.
            smtp_port: SMTP server port.
            smtp_user: SMTP username.
            smtp_pass: SMTP password.
            from_address: From email address.
            to_addresses: List of recipient email addresses.
            use_tls: Whether to use TLS encryption.
            use_sendemail: Whether to use sendEmail command instead of SMTP.
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.from_address = from_address
        self.to_addresses = to_addresses or []
        self.use_tls = use_tls
        self.use_sendemail = use_sendemail
        self.logger = logging.getLogger(__name__)
        
        # Check sendEmail availability if requested
        if self.use_sendemail:
            if not self._check_sendemail_available():
                self.logger.warning("sendEmail not available, falling back to SMTP")
                self.use_sendemail = False
    
    def send_report(self, subject: str, text_content: Optional[str] = None,
                   html_content: Optional[str] = None) -> bool:
        """Send backup report via email.
        
        Args:
            subject: Email subject line.
            text_content: Plain text email content.
            html_content: HTML email content.
            
        Returns:
            True if email sent successfully.
        """
        if not self.to_addresses:
            self.logger.error("No recipient addresses configured")
            return False
        
        if not text_content and not html_content:
            self.logger.error("No content provided for email")
            return False
        
        try:
            if self.use_sendemail:
                return self._send_via_sendemail(subject, text_content, html_content)
            else:
                # Create message
                msg = self._create_message(subject, text_content, html_content)
                
                # Send email
                self._send_message(msg)
            
            self.logger.info(f"Email report sent successfully to {len(self.to_addresses)} recipients")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email report: {e}")
            return False
    
    def _create_message(self, subject: str, text_content: Optional[str],
                       html_content: Optional[str]) -> MIMEMultipart:
        """Create email message.
        
        Args:
            subject: Email subject.
            text_content: Plain text content.
            html_content: HTML content.
            
        Returns:
            Configured email message.
        """
        # Create message container
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_address
        msg['To'] = ', '.join(self.to_addresses)
        
        # Add text content
        if text_content:
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(text_part)
        
        # Add HTML content
        if html_content:
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
        
        return msg
    
    def _send_message(self, msg: MIMEMultipart) -> None:
        """Send email message via SMTP.
        
        Args:
            msg: Email message to send.
        """
        self.logger.debug(f"Connecting to SMTP server {self.smtp_server}:{self.smtp_port}")
        
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
                self.logger.debug("Started TLS encryption")
            
            if self.smtp_user and self.smtp_pass:
                server.login(self.smtp_user, self.smtp_pass)
                self.logger.debug(f"Authenticated as {self.smtp_user}")
            
            # Send email
            server.send_message(msg)
            self.logger.debug("Email message sent successfully")
    
    def send_test_email(self, subject: str = "Backup Monitor Test Email") -> bool:
        """Send a test email to verify configuration.
        
        Args:
            subject: Test email subject.
            
        Returns:
            True if test email sent successfully.
        """
        test_content = f"""
This is a test email from the Backup Monitor system.

Configuration:
- SMTP Server: {self.smtp_server}:{self.smtp_port}
- From: {self.from_address}
- Recipients: {', '.join(self.to_addresses)}
- TLS Enabled: {self.use_tls}

If you receive this email, the email configuration is working correctly.

Generated at: {self._get_timestamp()}
        """.strip()
        
        return self.send_report(subject, text_content=test_content)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def validate_configuration(self) -> List[str]:
        """Validate email configuration.
        
        Returns:
            List of validation errors (empty if valid).
        """
        errors = []
        
        if not self.smtp_server:
            errors.append("SMTP server not configured")
        
        if not self.from_address:
            errors.append("From address not configured")
        
        if not self.to_addresses:
            errors.append("No recipient addresses configured")
        
        # Validate email addresses
        import re
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        if self.from_address and not email_pattern.match(self.from_address):
            errors.append(f"Invalid from address: {self.from_address}")
        
        for addr in self.to_addresses:
            if not email_pattern.match(addr):
                errors.append(f"Invalid recipient address: {addr}")
        
        return errors
    
    def _check_sendemail_available(self) -> bool:
        """Check if sendEmail command is available.
        
        Returns:
            True if sendEmail is available.
        """
        try:
            result = subprocess.run(['which', 'sendEmail'], 
                                   capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _send_via_sendemail(self, subject: str, text_content: Optional[str] = None,
                           html_content: Optional[str] = None) -> bool:
        """Send email using sendEmail command.
        
        Args:
            subject: Email subject line.
            text_content: Plain text email content.
            html_content: HTML email content.
            
        Returns:
            True if email sent successfully.
        """
        # Prefer HTML content over text for sendEmail, but ensure we have content
        if html_content:
            content = html_content
            content_type = 'html'
        elif text_content:
            content = text_content
            content_type = 'text'
        else:
            self.logger.error("No content available for sendEmail")
            return False
        
        # Create temporary file for message content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        try:
            # Build sendEmail command
            cmd = ['sendEmail']
            cmd.extend(['-f', self.from_address])
            cmd.extend(['-t'] + self.to_addresses)
            cmd.extend(['-s', f"{self.smtp_server}:{self.smtp_port}"])
            
            if self.smtp_user:
                cmd.extend(['-xu', self.smtp_user])
            
            if self.smtp_pass:
                cmd.extend(['-xp', self.smtp_pass])
            
            cmd.extend(['-u', subject])
            cmd.extend(['-o', f'message-file={temp_file}'])
            
            # Set content type based on what we're sending
            cmd.extend(['-o', f'message-content-type={content_type}'])
            
            # Execute sendEmail command
            self.logger.debug(f"Executing sendEmail command: {' '.join(cmd[:8])}...")  # Don't log passwords
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.logger.info(f"Email sent successfully via sendEmail to {len(self.to_addresses)} recipients")
                return True
            else:
                self.logger.error(f"sendEmail failed with return code {result.returncode}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("sendEmail command timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error executing sendEmail: {e}")
            return False
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except OSError:
                pass  # Ignore cleanup errors
