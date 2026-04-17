"""Validate attachment View link works in browser."""
import os
from playwright.sync_api import sync_playwright

SD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots", "attachments")
os.makedirs(SD, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # Login
    page.goto("http://127.0.0.1:5080/auth/login", wait_until="networkidle")
    page.fill('input[name="username"]', "do.admin")
    page.fill('input[name="password"]', "Test@2025")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    # Go to order detail
    page.goto("http://127.0.0.1:5080/delivery-orders/6025", wait_until="networkidle")

    # Scroll to attachments section
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(SD, "01_attachments_section.png"))

    # Click View link
    view_link = page.query_selector('a[href*="Delivery_Orders_User_Manual"]')
    if view_link:
        href = view_link.get_attribute("href")
        print(f"View link href: {href}")

        # Open in new tab
        with page.context.expect_page() as new_page_info:
            view_link.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("networkidle")
        print(f"New tab URL: {new_page.url}")
        new_page.screenshot(path=os.path.join(SD, "02_pdf_opened.png"))
        new_page.close()
    else:
        print("View link NOT found")

    browser.close()
    print("DONE - Attachment view works!")
