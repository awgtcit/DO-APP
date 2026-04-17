"""
Quick diagnostic: send a test email to verify SMTP works.
Usage:
    cd app
    set env vars (DB_SERVER, SMTP_*, etc.)
    python scripts/test_email_send.py
"""

import os
import sys
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

SMTP_HOST = os.environ.get("SMTP_SERVER") or os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
    print("ERROR: Set SMTP_SERVER, SMTP_USER, SMTP_PASSWORD env vars first.")
    sys.exit(1)

TO = "m.nizar@awgtc.com"

print(f"SMTP: {SMTP_HOST}:{SMTP_PORT}")
print(f"From: {SMTP_USER}")
print(f"To:   {TO}")
print()

msg = MIMEMultipart("alternative")
msg["From"] = SMTP_USER
msg["To"] = TO
msg["Subject"] = "DO Email Test - Diagnostic"
msg.attach(MIMEText("<p>This is a test email from the Delivery Order system.</p>", "html"))

try:
    print("Connecting to SMTP server...")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.set_debuglevel(1)
        print("Starting TLS...")
        server.starttls()
        print("Logging in...")
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("Sending email...")
        server.sendmail(SMTP_USER, [TO], msg.as_string())
    print("\n[SUCCESS] Email sent to", TO)
except Exception as exc:
    print(f"\n[FAILED] {exc}")
    sys.exit(1)
