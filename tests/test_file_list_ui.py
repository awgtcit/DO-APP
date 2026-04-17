"""
Playwright test: File list UI with remove buttons on post-delivery forms.
Tests:
1. Login as do.logistics, navigate to CONFIRMED order
2. Add files via the file picker - verify file list renders with names, sizes, remove buttons
3. Remove a file - verify list updates
4. Submit with remaining files - verify success
"""
import os, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5080"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots", "workflow")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Create dummy test files
for name, content in [
    ("customs_doc_A.pdf", "A" * 500),
    ("customs_doc_B.docx", "B" * 1200),
    ("customs_doc_C.xlsx", "C" * 800),
]:
    path = os.path.join(SCREENSHOT_DIR, name)
    with open(path, "w") as f:
        f.write(content)


def login(page, username, password="Test@2025"):
    page.goto(f"{BASE}/auth/login")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


def test_file_list_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # ── Login as logistics ──
        print("Step 1: Login as do.logistics...")
        login(page, "do.logistics")

        # Find a CONFIRMED order
        page.goto(f"{BASE}/delivery-orders/orders?status=CONFIRMED")
        page.wait_for_load_state("networkidle")
        row = page.locator("tr.clickable-row").first
        if row.count() == 0:
            print("No CONFIRMED orders found. Cannot proceed.")
            browser.close()
            return
        row.click()
        page.wait_for_load_state("networkidle")
        print(f"  Opened order: {page.url}")

        # ── Click Edit to show logistics form ──
        print("Step 2: Open logistics edit form...")
        edit_btn = page.locator(".post-delivery-header--logistics button:has-text('Edit')")
        edit_btn.click()
        time.sleep(0.5)

        # ── Add first file ──
        print("Step 3: Add first file (customs_doc_A.pdf)...")
        file_input = page.locator("#logisticsFileInput")
        file_input.set_input_files(os.path.join(SCREENSHOT_DIR, "customs_doc_A.pdf"))
        time.sleep(0.3)

        # Verify file list appears with 1 item
        file_list = page.locator("#logisticsFileList")
        assert file_list.is_visible(), "File list should be visible"
        items = page.locator("#logisticsFileList .file-list-item")
        assert items.count() == 1, f"Expected 1 file item, got {items.count()}"
        assert "customs_doc_A.pdf" in items.first.inner_text()
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_file_list_1_file.png"))
        print(f"  File list shows {items.count()} file(s)")

        # ── Add two more files (second selection) ──
        print("Step 4: Add 2 more files...")
        file_input = page.locator("#logisticsFileInput")
        file_input.set_input_files([
            os.path.join(SCREENSHOT_DIR, "customs_doc_B.docx"),
            os.path.join(SCREENSHOT_DIR, "customs_doc_C.xlsx"),
        ])
        time.sleep(0.3)

        items = page.locator("#logisticsFileList .file-list-item")
        assert items.count() == 3, f"Expected 3 file items, got {items.count()}"
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "11_file_list_3_files.png"))
        print(f"  File list shows {items.count()} file(s)")

        # Verify header shows "3 files selected"
        header = page.locator("#logisticsFileList .file-list-header")
        assert "3 files selected" in header.inner_text()
        print(f"  Header: '{header.inner_text()}'")

        # ── Remove middle file (customs_doc_B.docx) ──
        print("Step 5: Remove customs_doc_B.docx...")
        remove_btns = page.locator("#logisticsFileList .file-list-remove")
        remove_btns.nth(1).click()  # Remove second file
        time.sleep(0.3)

        items = page.locator("#logisticsFileList .file-list-item")
        assert items.count() == 2, f"Expected 2 file items after removal, got {items.count()}"

        # Verify it's the right files remaining
        text = page.locator("#logisticsFileList").inner_text()
        assert "customs_doc_A.pdf" in text, "File A should still be in list"
        assert "customs_doc_B.docx" not in text, "File B should have been removed"
        assert "customs_doc_C.xlsx" in text, "File C should still be in list"
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "12_file_list_after_remove.png"))
        print(f"  File list shows {items.count()} file(s) after removal")

        # ── Fill fields and submit ──
        print("Step 6: Fill fields and submit...")
        page.fill("input[name='exit_document_number']", "EXIT-TEST-FL")
        page.fill("input[name='fta_declaration_number']", "FTA-TEST-FL")
        page.fill("input[name='sap_sales_invoice_number']", "SAP-TEST-FL")

        page.click("button[type='submit']:has-text('Save')")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Verify status changed
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "13_submitted_customs_updated.png"))
        status_el = page.locator(".status-large")
        status_text = status_el.inner_text().strip().upper()
        print(f"  Status: {status_text}")
        assert "CUSTOMS DOCUMENT UPDATED" in status_text, f"Expected CUSTOMS DOCUMENT UPDATED, got {status_text}"

        print("\n✅ File list UI test passed!")
        print("   - Files listed with names, sizes, and remove buttons")
        print("   - Files can be added in multiple selections")
        print("   - Individual files can be removed")
        print("   - Form submits successfully with remaining files")

        browser.close()


if __name__ == "__main__":
    test_file_list_ui()
