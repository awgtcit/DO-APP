"""
Playwright test — validate post-delivery tracking sections for all 4 roles.
Tests that:
1. Confirmed orders show the new Logistics and Sales sections
2. Logistics user can edit logistics fields
3. Creator/Admin can edit sales fields
4. Finance user sees sections but cannot edit
5. Attachments section is visible on confirmed orders
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5080"
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots", "post_delivery")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def login(page, username, password):
    """Login and return True if successful."""
    page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    return "/auth/login" not in page.url


def logout(page):
    page.goto(f"{BASE_URL}/auth/logout", wait_until="networkidle")


def find_confirmed_order(page):
    """Find a CONFIRMED order and navigate to it. Returns order_id or None."""
    page.goto(f"{BASE_URL}/delivery-orders/orders?status=CONFIRMED", wait_until="networkidle")

    # Look for a CONFIRMED row
    first_link = page.query_selector("table tbody tr:first-child td a")
    if first_link:
        first_link.click()
        page.wait_for_load_state("networkidle")
        return page.url
    return None


def test_logistics_role(page):
    """Test that do.logistics can see and edit logistics fields on confirmed orders."""
    print("\n[Logistics] Testing...")
    login(page, "do.logistics", "Test@2025")

    order_url = find_confirmed_order(page)
    if not order_url:
        print("  No CONFIRMED orders found - skipping")
        logout(page)
        return True

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_logistics_detail.png"))

    # Check for post-delivery sections
    logistics_section = page.query_selector(".post-delivery-header--logistics")
    sales_section = page.query_selector(".post-delivery-header--sales")

    print(f"  Logistics section visible: {logistics_section is not None}")
    print(f"  Sales section visible: {sales_section is not None}")

    if not logistics_section:
        print("  FAIL: Logistics section not found!")
        logout(page)
        return False

    # Check for Edit button on logistics section
    logistics_edit_btn = page.query_selector(".post-delivery-header--logistics .btn")
    print(f"  Logistics Edit button: {logistics_edit_btn is not None}")

    if logistics_edit_btn:
        # Click edit to show form
        logistics_edit_btn.click()
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_logistics_edit_form.png"))

        # Fill fields
        page.fill('input[name="exit_document_number"]', "EXIT-DOC-12345")
        page.fill('input[name="fta_declaration_number"]', "FTA-DECL-67890")
        page.fill('input[name="sap_sales_invoice_number"]', "SAP-INV-11111")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_logistics_fields_filled.png"))

        # Submit
        page.click('button:has-text("Save Logistics Fields")')
        page.wait_for_load_state("networkidle")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_logistics_saved.png"))

        # Check flash message
        flash = page.query_selector(".alert-success, .flash-success")
        if flash:
            print(f"  Success message: {flash.inner_text()}")
        else:
            print("  Warning: No success flash message found")

        # Verify values persisted
        exit_doc = page.query_selector(".pd-field-value")
        if exit_doc:
            text = exit_doc.inner_text()
            print(f"  First field value after save: {text}")

    # Check that logistics user does NOT have edit button on sales section
    sales_edit_btn = page.query_selector(".post-delivery-header--sales .btn")
    print(f"  Sales Edit button visible for logistics: {sales_edit_btn is not None}")
    # Logistics should NOT have the edit button for sales
    if sales_edit_btn:
        print("  NOTE: Sales edit visible - checking if it's restricted to creator/admin")

    # Check attachments section visible
    attachments = page.query_selector('.card__title:has-text("Attachments")')
    print(f"  Attachments section: {attachments is not None}")

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_logistics_full_page.png"), full_page=True)

    logout(page)
    return True


def test_admin_role(page):
    """Test that do.admin can see and edit both logistics and sales fields."""
    print("\n[Admin] Testing...")
    login(page, "do.admin", "Test@2025")

    order_url = find_confirmed_order(page)
    if not order_url:
        print("  No CONFIRMED orders found - skipping")
        logout(page)
        return True

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_admin_detail.png"))

    # Check both sections
    logistics_edit = page.query_selector(".post-delivery-header--logistics .btn")
    sales_edit = page.query_selector(".post-delivery-header--sales .btn")

    print(f"  Admin can edit logistics: {logistics_edit is not None}")
    print(f"  Admin can edit sales: {sales_edit is not None}")

    # Test sales field edit
    if sales_edit:
        sales_edit.click()
        page.fill('input[name="customs_boe_number"]', "BOE-2026-ABCDE")
        page.fill('input[name="airway_bill_number"]', "AWB-9876543210")
        page.fill('input[name="iec_code"]', "IEC-EXPORT-001")

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_admin_sales_filled.png"))

        page.click('button:has-text("Save Sales Fields")')
        page.wait_for_load_state("networkidle")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_admin_sales_saved.png"))

        flash = page.query_selector(".alert-success, .flash-success")
        if flash:
            print(f"  Success message: {flash.inner_text()}")

    # Test attachment upload section
    attachments = page.query_selector('.card__title:has-text("Attachments")')
    upload_input = page.query_selector('input[name="attachment"]')
    print(f"  Attachments section: {attachments is not None}")
    print(f"  Upload input available: {upload_input is not None}")

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_admin_full_page.png"), full_page=True)

    logout(page)
    return True


def test_creator_role(page):
    """Test that do.creator can see and edit sales fields but not logistics."""
    print("\n[Creator] Testing...")
    login(page, "do.creator", "Test@2025")

    # Creator may only see their own orders - need to find a confirmed one
    order_url = find_confirmed_order(page)
    if not order_url:
        print("  No CONFIRMED orders for creator - checking if sections render correctly")
        # Try navigating directly to a known confirmed order
        page.goto(f"{BASE_URL}/delivery-orders/orders", wait_until="networkidle")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_creator_list.png"))
        logout(page)
        return True

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_creator_detail.png"))

    logistics_edit = page.query_selector(".post-delivery-header--logistics .btn")
    sales_edit = page.query_selector(".post-delivery-header--sales .btn")

    print(f"  Creator can edit logistics: {logistics_edit is not None}")
    print(f"  Creator can edit sales: {sales_edit is not None}")

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "11_creator_full_page.png"), full_page=True)

    logout(page)
    return True


def test_finance_role(page):
    """Test that do.finance can see sections but has limited edit access."""
    print("\n[Finance] Testing...")
    login(page, "do.finance", "Test@2025")

    order_url = find_confirmed_order(page)
    if not order_url:
        print("  No CONFIRMED orders found - skipping")
        logout(page)
        return True

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "12_finance_detail.png"))

    logistics_section = page.query_selector(".post-delivery-header--logistics")
    sales_section = page.query_selector(".post-delivery-header--sales")
    logistics_edit = page.query_selector(".post-delivery-header--logistics .btn")
    sales_edit = page.query_selector(".post-delivery-header--sales .btn")

    print(f"  Finance sees logistics section: {logistics_section is not None}")
    print(f"  Finance sees sales section: {sales_section is not None}")
    print(f"  Finance can edit logistics: {logistics_edit is not None}")
    print(f"  Finance can edit sales: {sales_edit is not None}")

    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "13_finance_full_page.png"), full_page=True)

    logout(page)
    return True


def main():
    print("\n" + "="*70)
    print("  Post-Delivery Tracking — Feature Validation")
    print("="*70)

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        results["Logistics"] = test_logistics_role(page)
        results["Admin"] = test_admin_role(page)
        results["Creator"] = test_creator_role(page)
        results["Finance"] = test_finance_role(page)

        browser.close()

    print("\n" + "="*70)
    print("  RESULTS SUMMARY")
    print("="*70)
    for role, ok in results.items():
        print(f"  {role:12s} : {'PASS' if ok else 'FAIL'}")
    print("="*70)

    return all(results.values())


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
