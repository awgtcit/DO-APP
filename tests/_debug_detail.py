"""Debug: fetch order detail page to see error."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://127.0.0.1:5080/auth/login", wait_until="networkidle")
    page.fill('input[name="username"]', "do.admin")
    page.fill('input[name="password"]', "Test@2025")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.goto("http://127.0.0.1:5080/delivery-orders/6025", wait_until="networkidle")
    content = page.content()
    # Print just the error part
    if "Traceback" in content or "Error" in content:
        # Extract error text
        from html import unescape
        import re
        # Find traceback
        match = re.search(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL)
        if match:
            print(unescape(match.group(1))[:3000])
        else:
            print(content[:3000])
    else:
        print("Page loaded OK, no error found")
        print(content[:2000])
    browser.close()
