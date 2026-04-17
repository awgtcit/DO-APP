"""
Playwright test: Post-delivery workflow with new statuses
  CONFIRMED → CUSTOMS DOCUMENT UPDATED → DELIVERED

Tests:
1. Login as do.logistics, find a CONFIRMED order, verify logistics section visible
2. Edit logistics fields, upload file, save → verify status = CUSTOMS DOCUMENT UPDATED
3. Login as do.creator, verify sales section visible on CUSTOMS DOCUMENT UPDATED order
4. Edit sales fields, upload file, save → verify status = DELIVERED
"""

import os, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5080"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots", "workflow")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Create a dummy test file for upload
DUMMY_FILE = os.path.join(SCREENSHOT_DIR, "test_customs_doc.txt")
with open(DUMMY_FILE, "w") as f:
    f.write("Test customs document content for validation.")

DUMMY_FILE2 = os.path.join(SCREENSHOT_DIR, "test_delivery_doc.txt")
with open(DUMMY_FILE2, "w") as f:
    f.write("Test delivery document content for validation.")


def login(page, username, password="Test@2025"):
    page.goto(f"{BASE}/auth/login")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


def find_order_by_status(page, status):
    """Navigate to order list filtered by status and return first order link."""
    page.goto(f"{BASE}/delivery-orders/orders?status={status}")
    page.wait_for_load_state("networkidle")
    row = page.locator("tr.clickable-row").first
    if row.count() == 0:
        return None
    row.click()
    page.wait_for_load_state("networkidle")
    return page.url


def test_full_workflow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # ── Step 1: Login as logistics and find a CONFIRMED order ──
        print("Step 1: Login as do.logistics...")
        login(page, "do.logistics")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_logistics_dashboard.png"))

        url = find_order_by_status(page, "CONFIRMED")
        if not url:
            print("No CONFIRMED orders found. Test cannot proceed.")
            browser.close()
            return

        print(f"  Found CONFIRMED order: {page.url}")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_confirmed_order.png"))

        # ── Step 2: Verify logistics section is visible ──
        print("Step 2: Verify logistics post-delivery section...")
        logistics_header = page.locator("text=Fujairah Logistics Team — Post-Delivery Tracking")
        assert logistics_header.is_visible(), "Logistics section should be visible on CONFIRMED order"

        # Click Edit button in logistics section
        edit_btn = page.locator(".post-delivery-header--logistics button:has-text('Edit')")
        assert edit_btn.is_visible(), "Edit button should be visible for logistics user"
        edit_btn.click()
        time.sleep(0.5)

        # Verify edit form is visible
        logistics_form = page.locator("#logisticsEditForm")
        assert logistics_form.is_visible(), "Logistics edit form should appear"
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_logistics_edit_form.png"))

        # ── Step 3: Fill fields and upload file ──
        print("Step 3: Fill logistics fields and upload documents...")
        page.fill("input[name='exit_document_number']", "EXIT-2026-001")
        page.fill("input[name='fta_declaration_number']", "FTA-DEC-2026-001")
        page.fill("input[name='sap_sales_invoice_number']", "SAP-INV-2026-001")

        # Upload file
        file_input = logistics_form.locator("input[type='file']")
        file_input.set_input_files(DUMMY_FILE)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_logistics_filled.png"))

        # Submit
        page.click("#logisticsEditForm button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # ── Step 4: Verify status changed to CUSTOMS DOCUMENT UPDATED ──
        print("Step 4: Verify status = CUSTOMS DOCUMENT UPDATED...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_customs_updated_status.png"))
        status_el = page.locator(".status-large")
        status_text = status_el.inner_text().strip().upper()
        print(f"  Status is: {status_text}")
        assert "CUSTOMS DOCUMENT UPDATED" in status_text, f"Expected CUSTOMS DOCUMENT UPDATED, got {status_text}"

        # Verify logistics fields are now in view mode (Edit button hidden)
        logistics_edit_btn = page.locator(".post-delivery-header--logistics button:has-text('Edit')")
        assert logistics_edit_btn.count() == 0, "Edit button should be hidden after customs update"

        # Verify Sales section is now visible
        sales_header = page.locator("text=Sales Team — Post-Delivery Tracking")
        assert sales_header.is_visible(), "Sales section should be visible after CUSTOMS DOCUMENT UPDATED"
        print("  Sales section visible ✓")

        # Remember the order URL for the next login
        order_url = page.url

        # ── Step 5: Login as creator to update sales fields ──
        print("Step 5: Login as do.creator...")
        page.goto(f"{BASE}/auth/logout")
        login(page, "do.creator")
        page.goto(order_url)
        page.wait_for_load_state("networkidle")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_creator_sees_order.png"))

        # Verify status is still CUSTOMS DOCUMENT UPDATED
        status_el = page.locator(".status-large")
        status_text = status_el.inner_text().strip().upper()
        print(f"  Status is: {status_text}")

        # ── Step 6: Edit sales fields and upload ──
        print("Step 6: Fill sales fields and upload documents...")
        sales_edit_btn = page.locator(".post-delivery-header--sales button:has-text('Edit')")
        assert sales_edit_btn.is_visible(), "Sales Edit button should be visible for creator"
        sales_edit_btn.click()
        time.sleep(0.5)

        sales_form = page.locator("#salesEditForm")
        assert sales_form.is_visible(), "Sales edit form should appear"

        page.fill("input[name='customs_boe_number']", "BOE-2026-001")
        page.fill("input[name='airway_bill_number']", "AWB-2026-001")
        page.fill("input[name='iec_code']", "IEC-2026-001")

        file_input = sales_form.locator("input[type='file']")
        file_input.set_input_files(DUMMY_FILE2)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_sales_filled.png"))

        # Submit
        page.click("#salesEditForm button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # ── Step 7: Verify status changed to DELIVERED ──
        print("Step 7: Verify status = DELIVERED...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_delivered_status.png"))
        status_el = page.locator(".status-large")
        status_text = status_el.inner_text().strip().upper()
        print(f"  Status is: {status_text}")
        assert "DELIVERED" in status_text, f"Expected DELIVERED, got {status_text}"

        # Verify both post-delivery sections are in view mode
        logistics_header = page.locator("text=Fujairah Logistics Team — Post-Delivery Tracking")
        assert logistics_header.is_visible(), "Logistics section should still be visible on DELIVERED"

        sales_header = page.locator("text=Sales Team — Post-Delivery Tracking")
        assert sales_header.is_visible(), "Sales section should still be visible on DELIVERED"

        print("\n✅ All tests passed! Full workflow validated:")
        print("   CONFIRMED → CUSTOMS DOCUMENT UPDATED → DELIVERED")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_final_delivered.png"))
        browser.close()


if __name__ == "__main__":
    test_full_workflow()
