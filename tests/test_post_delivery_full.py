"""
Full post-delivery tracking test — navigate to a CONFIRMED order and test the new sections.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5080"
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots", "post_delivery")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def login(page, username, password):
    page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    return "/auth/login" not in page.url


def logout(page):
    page.goto(f"{BASE_URL}/auth/logout", wait_until="networkidle")


def go_to_confirmed_order(page):
    """Navigate to a CONFIRMED order by clicking a clickable-row."""
    page.goto(f"{BASE_URL}/delivery-orders/orders?status=CONFIRMED", wait_until="networkidle")
    row = page.query_selector("tr.clickable-row")
    if row:
        row.click()
        page.wait_for_load_state("networkidle")
        return True
    return False


def main():
    print("\n" + "="*70)
    print("  Post-Delivery Tracking — Full Feature Validation")
    print("="*70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        # ── TEST 1: Logistics user ──
        print("\n[1. Logistics] Login and check confirmed order...")
        login(page, "do.logistics", "Test@2025")

        if not go_to_confirmed_order(page):
            print("  FAIL: No CONFIRMED orders found")
            browser.close()
            return

        confirmed_order_url = page.url
        print(f"  Navigated to: {confirmed_order_url}")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_logistics_confirmed.png"))

        # Check sections exist
        logistics_hdr = page.query_selector(".post-delivery-header--logistics")
        sales_hdr = page.query_selector(".post-delivery-header--sales")
        print(f"  Logistics section: {'FOUND' if logistics_hdr else 'MISSING'}")
        print(f"  Sales section: {'FOUND' if sales_hdr else 'MISSING'}")

        # Check edit button on logistics
        log_edit = page.query_selector(".post-delivery-header--logistics .btn")
        print(f"  Logistics Edit btn: {'FOUND' if log_edit else 'HIDDEN'}")

        if log_edit:
            log_edit.click()
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_logistics_edit_mode.png"))

            # Fill in test data
            page.fill('input[name="exit_document_number"]', "EXIT-FUJ-2026-001")
            page.fill('input[name="fta_declaration_number"]', "FTA-DCL-2026-ABC")
            page.fill('input[name="sap_sales_invoice_number"]', "SAP-INV-2026-XYZ")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_logistics_fields_filled.png"))

            # Save
            page.click('button:has-text("Save Logistics Fields")')
            page.wait_for_load_state("networkidle")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_logistics_saved.png"))

            # Verify saved values
            values = page.query_selector_all("#logisticsView .pd-field-value")
            for v in values:
                print(f"    Saved value: {v.inner_text()}")

        # Check sales section - logistics should NOT have edit button
        sales_edit = page.query_selector(".post-delivery-header--sales .btn")
        print(f"  Sales Edit btn (should be hidden for logistics): {'FOUND' if sales_edit else 'HIDDEN - CORRECT'}")

        # Check attachments section is visible
        attach_section = page.query_selector('input[name="attachment"]')
        print(f"  Attachment upload: {'FOUND' if attach_section else 'MISSING'}")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_logistics_full_page.png"), full_page=True)
        logout(page)

        # ── TEST 2: Admin user ──
        print("\n[2. Admin] Login and check confirmed order...")
        login(page, "do.admin", "Test@2025")
        page.goto(confirmed_order_url, wait_until="networkidle")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_admin_confirmed.png"))

        log_edit = page.query_selector(".post-delivery-header--logistics .btn")
        sales_edit = page.query_selector(".post-delivery-header--sales .btn")
        print(f"  Admin Logistics Edit: {'FOUND' if log_edit else 'HIDDEN'}")
        print(f"  Admin Sales Edit: {'FOUND' if sales_edit else 'HIDDEN'}")

        # Verify logistics values persisted from previous test
        values = page.query_selector_all("#logisticsView .pd-field-value")
        for v in values:
            print(f"    Logistics value: {v.inner_text()}")

        # Edit sales fields
        if sales_edit:
            sales_edit.click()
            page.fill('input[name="customs_boe_number"]', "BOE-FE-2026-12345")
            page.fill('input[name="airway_bill_number"]', "AWB-1234567890")
            page.fill('input[name="iec_code"]', "IEC-EXP-ABCDEF")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_admin_sales_filled.png"))

            page.click('button:has-text("Save Sales Fields")')
            page.wait_for_load_state("networkidle")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_admin_sales_saved.png"))

            values = page.query_selector_all("#salesView .pd-field-value")
            for v in values:
                print(f"    Sales value: {v.inner_text()}")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_admin_full_page.png"), full_page=True)
        logout(page)

        # ── TEST 3: Finance user ──
        print("\n[3. Finance] Login and check confirmed order...")
        login(page, "do.finance", "Test@2025")
        page.goto(confirmed_order_url, wait_until="networkidle")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_finance_confirmed.png"))

        log_edit = page.query_selector(".post-delivery-header--logistics .btn")
        sales_edit = page.query_selector(".post-delivery-header--sales .btn")
        print(f"  Finance Logistics Edit: {'FOUND' if log_edit else 'HIDDEN - CORRECT'}")
        print(f"  Finance Sales Edit: {'FOUND' if sales_edit else 'HIDDEN - CORRECT'}")

        # Finance should see the read-only values
        values = page.query_selector_all(".pd-field-value")
        print(f"  Total field values visible: {len(values)}")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "11_finance_full_page.png"), full_page=True)
        logout(page)

        # ── TEST 4: Creator user ──
        print("\n[4. Creator] Login and check confirmed order...")
        login(page, "do.creator", "Test@2025")
        page.goto(confirmed_order_url, wait_until="networkidle")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "12_creator_confirmed.png"))

        log_section = page.query_selector(".post-delivery-header--logistics")
        sales_section = page.query_selector(".post-delivery-header--sales")
        log_edit = page.query_selector(".post-delivery-header--logistics .btn")
        sales_edit = page.query_selector(".post-delivery-header--sales .btn")
        print(f"  Creator sees logistics section: {'YES' if log_section else 'NO'}")
        print(f"  Creator sees sales section: {'YES' if sales_section else 'NO'}")
        print(f"  Creator Logistics Edit: {'FOUND' if log_edit else 'HIDDEN - CORRECT'}")
        print(f"  Creator Sales Edit: {'FOUND' if sales_edit else 'HIDDEN'}")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "13_creator_full_page.png"), full_page=True)
        logout(page)

        # ── TEST 5: Check DRAFT order does NOT show sections ──
        print("\n[5. Non-confirmed] Verify sections hidden on DRAFT...")
        login(page, "do.admin", "Test@2025")
        page.goto(f"{BASE_URL}/delivery-orders/orders?status=DRAFT", wait_until="networkidle")
        row = page.query_selector("tr.clickable-row")
        if row:
            row.click()
            page.wait_for_load_state("networkidle")
            log_section = page.query_selector(".post-delivery-header--logistics")
            sales_section = page.query_selector(".post-delivery-header--sales")
            print(f"  Logistics on DRAFT: {'VISIBLE - BUG' if log_section else 'HIDDEN - CORRECT'}")
            print(f"  Sales on DRAFT: {'VISIBLE - BUG' if sales_section else 'HIDDEN - CORRECT'}")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "14_draft_no_sections.png"), full_page=True)
        logout(page)

        browser.close()

    print("\n" + "="*70)
    print("  All tests completed. Check screenshots in screenshots/post_delivery/")
    print("="*70)


if __name__ == "__main__":
    main()
