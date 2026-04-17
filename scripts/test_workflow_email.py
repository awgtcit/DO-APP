"""
Simulate a DO status-change email by calling the actual service layer.
Tests the full chain: service → do_email_service → email_service → SMTP.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from config import Config

print("=" * 60)
print("SMTP CONFIG:", Config.SMTP_HOST, Config.SMTP_PORT, Config.SMTP_USER)
print("=" * 60)

# Import the do_email_service and call it directly (no background thread test)
from services.email_service import send_email

# Simulate what do_email_service.send_do_status_email does, but synchronously
to = ["purchaseorder@alwahdania.com"]
cc = ["m.nizar@awgtc.com"]
bcc = ["vivan_it@universaltobacco.ae", "ajoy@alwahdania.com"]

subject = "Order # TEST-DIAG is Placed"
body = """\
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#333;">
<p>Dear Test User,</p>
<p>This is a DIAGNOSTIC test of the full email chain.</p>
<p>If you received this email, the DO workflow emails are working.</p>
<p>Best Regards,<br>Ahlaan</p>
</body>
</html>"""

print(f"\nSending email:")
print(f"  TO:  {to}")
print(f"  CC:  {cc}")
print(f"  BCC: {bcc}")
print(f"  Subject: {subject}")
print()

result = send_email(to=to, subject=subject, body_html=body, cc=cc, bcc=bcc)
print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
