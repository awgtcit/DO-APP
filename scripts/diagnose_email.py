"""
Diagnose email sending through the actual app Config and email_service.
Run from the app/ directory with env vars set.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

from config import Config

print("=" * 60)
print("SMTP CONFIGURATION CHECK")
print("=" * 60)
print(f"  SMTP_HOST     = {Config.SMTP_HOST!r}")
print(f"  SMTP_PORT     = {Config.SMTP_PORT!r}")
print(f"  SMTP_USER     = {Config.SMTP_USER!r}")
print(f"  SMTP_PASSWORD = {'***' + Config.SMTP_PASSWORD[-4:] if Config.SMTP_PASSWORD else '(empty)'}")
print()

if not Config.SMTP_HOST:
    print("FATAL: SMTP_HOST is empty!")
    print(f"  SMTP_HOST env = {os.environ.get('SMTP_HOST')!r}")
    print(f"  SMTP_SERVER env = {os.environ.get('SMTP_SERVER')!r}")
    sys.exit(1)

if not Config.SMTP_USER:
    print("FATAL: SMTP_USER is empty!")
    sys.exit(1)

print("Config looks OK. Attempting direct SMTP send...")
print()

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

to_addr = "m.nizar@awgtc.com"
subject = "DO App Email Diagnostic Test"
body = "<html><body><p>This is a diagnostic test from the DO app email service.</p></body></html>"

msg = MIMEMultipart("alternative")
msg["From"] = Config.SMTP_USER
msg["To"] = to_addr
msg["Subject"] = subject
msg.attach(MIMEText(body, "html"))

try:
    print(f"Connecting to {Config.SMTP_HOST}:{Config.SMTP_PORT} ...")
    server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15)
    server.set_debuglevel(1)
    server.ehlo()
    print("Starting TLS...")
    server.starttls()
    server.ehlo()
    print(f"Logging in as {Config.SMTP_USER}...")
    server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
    print("Login OK! Sending email...")
    server.sendmail(Config.SMTP_USER, [to_addr], msg.as_string())
    server.quit()
    print()
    print(f"SUCCESS: Email sent to {to_addr}")
except Exception as e:
    print()
    print(f"FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
