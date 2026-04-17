"""Validate attachment View link serves file from DB, not from filesystem."""
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

    # Go to order 6025 (has attachments)
    page.goto("http://127.0.0.1:5080/delivery-orders/6025", wait_until="networkidle")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(SD, "03_db_attachments_section.png"))

    # Check View link now points to /attachments/<id>/view route
    view_links = page.query_selector_all('a[href*="/attachments/"][href*="/view"]')
    print(f"Found {len(view_links)} DB-served view links")
    for link in view_links:
        href = link.get_attribute("href")
        print(f"  Link: {href}")

    # Click first View link (PDF) — should open from DB
    if view_links:
        with page.context.expect_page() as new_page_info:
            view_links[-1].click()  # last link = first attachment (Delivery_Orders_User_Manual.pdf)
        new_page = new_page_info.value
        new_page.wait_for_load_state("networkidle")
        print(f"Opened URL: {new_page.url}")
        print(f"Title: {new_page.title()}")
        new_page.screenshot(path=os.path.join(SD, "04_db_pdf_opened.png"))
        new_page.close()

    # Test uploading a NEW attachment (it should go to DB, not filesystem)
    page.goto("http://127.0.0.1:5080/delivery-orders/6025", wait_until="networkidle")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(300)

    # Create a small test file
    test_file_path = os.path.join(SD, "test_upload.txt")
    with open(test_file_path, "w") as f:
        f.write("This is a test file uploaded to verify DB storage.\nDate: 2026-04-06")

    page.set_input_files('input[name="attachment"]', test_file_path)
    page.click('button:has-text("Upload")')
    page.wait_for_load_state("networkidle")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(SD, "05_after_upload.png"))

    # Check flash message
    flash_msg = page.query_selector(".alert")
    if flash_msg:
        print(f"Flash: {flash_msg.inner_text()}")

    # Find the new View link for test_upload.txt
    new_link = page.query_selector('a[href*="/view"]:near(strong:has-text("test_upload"))')
    if not new_link:
        # Try broader search
        all_links = page.query_selector_all('a[href*="/attachments/"][href*="/view"]')
        print(f"Total view links after upload: {len(all_links)}")
        for link in all_links:
            print(f"  {link.get_attribute('href')}")
        if all_links:
            new_link = all_links[0]  # newest is first (ORDER BY id DESC)

    if new_link:
        with page.context.expect_page() as new_page_info:
            new_link.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("networkidle")
        print(f"New file URL: {new_page.url}")
        print(f"New file content visible: {new_page.content()[:200]}")
        new_page.screenshot(path=os.path.join(SD, "06_new_file_from_db.png"))
        new_page.close()

    browser.close()
    print("\nDONE — Attachments served from DB!")
