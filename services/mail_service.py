"""
Mail Service Module
Handles sending emails via SQL Server Database Mail
"""

import logging
from sqlalchemy import create_engine, text
import os
import urllib.parse
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
MAIL_LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs', 'mail')
os.makedirs(MAIL_LOG_DIR, exist_ok=True)


class MailService:
    """Handles sending emails through SQL Server Database Mail"""
    
    def __init__(self):
        """Initialize the mail service with database connection"""
        self.server = os.getenv('PAM_DB_SERVER', 'localhost')
        self.database = os.getenv('PAM_DB_DATABASE', 'PromoQuality')
        self.username = os.getenv('PAM_DB_USERNAME', '')
        self.password = os.getenv('PAM_DB_PASSWORD', '')
        self.driver = os.getenv('PAM_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        self.encrypt = os.getenv('PAM_DB_ENCRYPT', 'no').lower()
        self.trust_cert = os.getenv('PAM_DB_TRUST_CERT', 'yes').lower()
        self.timeout = int(os.getenv('PAM_DB_LOGIN_TIMEOUT', '15'))
        self._engine = None
    
    def _get_engine(self):
        """Get or create SQLAlchemy engine"""
        if self._engine is None:
            if self.username and self.password:
                # Windows or SQL authentication
                quoted_password = urllib.parse.quote_plus(self.password)
                connection_string = (
                    f"mssql+pyodbc://{self.username}:{quoted_password}@"
                    f"{self.server}/{self.database}?"
                    f"driver={urllib.parse.quote_plus(self.driver)}&"
                    f"Encrypt={self.encrypt}&"
                    f"TrustServerCertificate={'yes' if self.trust_cert == 'yes' else 'no'}&"
                    f"Connection Timeout={self.timeout}"
                )
            else:
                # Windows authentication
                connection_string = (
                    f"mssql+pyodbc://@{self.server}/{self.database}?"
                    f"driver={urllib.parse.quote_plus(self.driver)}&"
                    f"Trusted_Connection=yes&"
                    f"Encrypt={self.encrypt}&"
                    f"TrustServerCertificate={'yes' if self.trust_cert == 'yes' else 'no'}&"
                    f"Connection Timeout={self.timeout}"
                )
            self._engine = create_engine(connection_string)
        return self._engine
    
    def _log_email_to_file(self, recipients, subject, body, profile_name='PAM_MAIL_Profile'):
        """
        Log email to file for auditing and testing purposes
        
        Args:
            recipients (str): Email recipients
            subject (str): Email subject
            body (str): Email body
            profile_name (str): Mail profile name
        
        Returns:
            str: Path to the log file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = os.path.join(MAIL_LOG_DIR, f'email_{timestamp}.json')
        
        email_record = {
            'timestamp': datetime.now().isoformat(),
            'profile_name': profile_name,
            'recipients': recipients,
            'subject': subject,
            'body': body,
            'status': 'QUEUED'
        }
        
        with open(log_filename, 'w') as f:
            json.dump(email_record, f, indent=2)
        
        logger.info(f"Email logged to file: {log_filename}")
        return log_filename
    
    def send_approval_email(self, recipients, subject, body, profile_name='PAM_MAIL_Profile', body_format='HTML'):
        """
        Send approval email via SQL Server Database Mail
        Executes the exact EXEC statement word-for-word
        
        Args:
            recipients (str): Email address(es) to send to (comma-separated for multiple)
            subject (str): Email subject line
            body (str): Email body text (can contain HTML if body_format='HTML')
            profile_name (str): Name of the SQL Server mail profile to use (default: PAM_MAIL_Profile)
            body_format (str): Format of the body - 'HTML' or 'TEXT' (default: 'HTML')
        
        Returns:
            dict: Result status with success flag and message
        """
        try:
            engine = self._get_engine()
            
            with engine.connect() as connection:
                # Escape single quotes in parameters for SQL injection safety
                safe_profile = profile_name.replace("'", "''")
                safe_recipients = recipients.replace("'", "''")
                safe_subject = subject.replace("'", "''")
                safe_body = body.replace("'", "''")
                
                # Execute in msdb database context to access sp_send_dbmail
                # Using 3-part name to ensure it works from any database
                sql_statement = f"""EXEC msdb.dbo.sp_send_dbmail
    @profile_name = N'{safe_profile}',
    @recipients   = N'{safe_recipients}',
    @subject      = N'{safe_subject}',
    @body         = N'{safe_body}',
    @body_format  = '{body_format}'"""
                
                logger.info(f"Executing sp_send_dbmail - Profile: {profile_name}, Recipients: {recipients}, Subject: {subject}, Format: {body_format}")
                
                # Execute as raw SQL text (not parameterized)
                result = connection.execute(text(sql_statement))
                connection.commit()
                
                logger.info(f"✓✓✓ Email SENT successfully! ✓✓✓")
                logger.info(f"  Recipients: {recipients}")
                logger.info(f"  Subject: {subject}")
                return {
                    'success': True,
                    'message': f'✓ Approval email sent to {recipients}'
                }
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in sp_send_dbmail: {error_msg}")
            
            # Check if it's a permission error
            if 'permission' in error_msg.lower() or 'denied' in error_msg.lower():
                logger.error("Permission denied on sp_send_dbmail")
                return {
                    'success': False,
                    'message': f'Permission denied on sp_send_dbmail. DBA must run: GRANT EXECUTE ON msdb.dbo.sp_send_dbmail TO [Python_user]'
                }
            elif 'profile' in error_msg.lower():
                logger.error(f"Profile error: {error_msg}")
                return {
                    'success': False,
                    'message': f'Mail profile "{profile_name}" not found or not accessible. Error: {error_msg}'
                }
            else:
                # Other errors
                error_detail = f"Failed to send email: {error_msg}"
                logger.error(error_detail)
                return {
                    'success': False,
                    'message': error_detail
                }
    
    def send_test_email(self):
        """
        Send a test email to verify Database Mail is working
        
        Returns:
            dict: Result status with success flag and message
        """
        return self.send_approval_email(
            recipients='cade.holtzen1@t-mobile.com',
            subject='Test message',
            body='This is a test via Database Mail.'
        )

