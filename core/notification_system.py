import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class NotificationSystem:
    """Simple notification system for device mapping alerts"""
    
    def __init__(self, email_to=None, email_from=None, smtp_server=None):
        self.email_to = email_to
        self.email_from = email_from
        self.smtp_server = smtp_server
        
    def create_desktop_alert(self, message, title="Device Mapping Alert"):
        """Create a Windows desktop notification"""
        try:
            import win10toast
            toaster = win10toast.ToastNotifier()
            toaster.show_toast(title, message, duration=10)
        except ImportError:
            print("💡 Install win10toast for desktop notifications: pip install win10toast")
            
    def create_alert_file(self, unmapped_count, new_count, timestamp=None):
        """Create a simple alert file that's easy to spot"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        alert_filename = f"🚨_MANUAL_ATTENTION_NEEDED_{timestamp}.txt"
        
        with open(alert_filename, 'w') as f:
            f.write("🚨 DEVICE MAPPING ALERT 🚨\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"📊 Summary:\n")
            f.write(f"   • New devices found: {new_count}\n")
            f.write(f"   • Devices needing manual mapping: {unmapped_count}\n\n")
            
            f.write("📋 What to do:\n")
            f.write("   1. Open unmapped_devices.csv in Excel\n")
            f.write("   2. Review the device names that couldn't be auto-mapped\n")
            f.write("   3. Add new patterns to create_correct_comprehensive_mapping.py\n")
            f.write("   4. Run the system again\n\n")
            
            f.write("📁 Files to check:\n")
            f.write("   • unmapped_devices.csv (devices needing attention)\n")
            f.write("   • new_devices_detected.csv (all new devices)\n")
            f.write("   • update_report_*.txt (detailed report)\n\n")
            
            f.write("🔄 Quick commands:\n")
            f.write("   • Test: python device_mapping_updater.py --check\n")
            f.write("   • Manual update: python device_mapping_updater.py --detect\n")
            
        print(f"🚨 Alert file created: {alert_filename}")
        return alert_filename
        
    def send_email_alert(self, unmapped_count, new_count):
        """Send email alert (if configured)"""
        if not all([self.email_to, self.email_from, self.smtp_server]):
            return
            
        subject = f"🚨 Device Mapping Alert: {unmapped_count} devices need attention"
        
        body = f"""
Device Mapping System Alert

Summary:
• New devices found: {new_count}
• Devices needing manual mapping: {unmapped_count}

Action Required:
Please review the unmapped_devices.csv file and add mapping rules for new device types.

Files to check:
• unmapped_devices.csv
• new_devices_detected.csv
• update_report_*.txt

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, 587)
            server.starttls()
            text = msg.as_string()
            server.sendmail(self.email_from, self.email_to, text)
            server.quit()
            
            print(f"📧 Email alert sent to {self.email_to}")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            
    def check_for_alerts(self):
        """Check if there are any alert files that need attention"""
        alert_files = [f for f in os.listdir('.') if f.startswith('🚨_MANUAL_ATTENTION_NEEDED_')]
        
        if alert_files:
            print(f"⚠️  Found {len(alert_files)} alert files:")
            for alert_file in sorted(alert_files):
                print(f"   📄 {alert_file}")
            print(f"\n💡 Delete these files after you've addressed the issues")
            return True
        else:
            print("✅ No manual attention alerts found")
            return False

# Example usage
if __name__ == "__main__":
    notifier = NotificationSystem()
    
    # Check for existing alerts
    notifier.check_for_alerts()
    
    # Example of creating an alert
    # notifier.create_alert_file(unmapped_count=3, new_count=15)
    # notifier.create_desktop_alert("3 devices need manual mapping rules!")
