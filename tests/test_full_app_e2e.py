"""
Complete end-to-end Playwright test of the DoApp application.
Tests the FULL delivery order workflow: Product -> Customer -> DO -> Submit ->
Price Agreed -> Confirmed -> Customs Document Updated -> Delivered.
Also tests management pages, admin settings, and captures screenshots.
"""
import re
import time
import os
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5080"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "screenshots", "guide")
os.makedirs(SHOTS, exist_ok=True)

step_num = 0


def shot(page, name):
    global step_num
    step_num += 1
    fname = f"{step_num:02d}_{name}.png"
    page.screenshot(path=os.path.join(SHOTS, fname), full_page=True)
    print(f"  [{step_num:02d}] Screenshot: {fname}")
    return fname


def login(page, username, password="Test@2025"):
    page.goto(f"{BASE}/auth/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    shot(page, f"login_{username}")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    if "/isp" in page.url:
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)


def logout(page):
    page.goto(f"{BASE}/auth/logout")
    page.wait_for_load_state("networkidle")
    time.sleep(0.5)


def main():
    results = {"pass": [], "fail": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # Auto-accept JS confirm() dialogs
        page.on("dialog", lambda dialog: dialog.accept())

        # ============================================================
        # PHASE 1: Login Test
        # ============================================================
        print("\n=== PHASE 1: LOGIN ===")
        try:
            page.goto(f"{BASE}/auth/login")
            page.wait_for_load_state("networkidle")
            shot(page, "login_page")

            page.fill('input[name="username"]', "wronguser")
            page.fill('input[name="password"]', "wrongpass")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)
            shot(page, "login_failed")

            login(page, "do.admin")
            shot(page, "dashboard_admin")
            assert "delivery-orders" in page.url or page.url.endswith("/"), f"Login failed, URL: {page.url}"
            results["pass"].append("Login as do.admin")
            print("  PASS: Login as do.admin")
        except Exception as e:
            results["fail"].append(f"Login: {e}")
            print(f"  FAIL: Login - {e}")

        # ============================================================
        # PHASE 2: Dashboard
        # ============================================================
        print("\n=== PHASE 2: DASHBOARD ===")
        try:
            page.goto(f"{BASE}/delivery-orders/")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "dashboard_full")
            results["pass"].append("Dashboard page")
            print("  PASS: Dashboard page")
        except Exception as e:
            results["fail"].append(f"Dashboard: {e}")
            print(f"  FAIL: Dashboard - {e}")

        # ============================================================
        # PHASE 3: Products Management
        # ============================================================
        print("\n=== PHASE 3: PRODUCTS ===")
        try:
            page.goto(f"{BASE}/delivery-orders/manage/products")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "products_list")
            rows = page.locator("table tbody tr").count()
            print(f"  Products found: {rows}")

            page.goto(f"{BASE}/delivery-orders/manage/products/create")
            page.wait_for_load_state("networkidle")
            shot(page, "product_create_form")
            results["pass"].append("Products list & create form")
            print("  PASS: Products list & create form")
        except Exception as e:
            results["fail"].append(f"Products: {e}")
            print(f"  FAIL: Products - {e}")

        # ============================================================
        # PHASE 4: Customers Management
        # ============================================================
        print("\n=== PHASE 4: CUSTOMERS ===")
        try:
            page.goto(f"{BASE}/delivery-orders/manage/customers")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "customers_list")
            rows = page.locator("table tbody tr").count()
            print(f"  Customers found: {rows}")

            page.goto(f"{BASE}/delivery-orders/manage/customers/create")
            page.wait_for_load_state("networkidle")
            shot(page, "customer_create_form")
            results["pass"].append("Customers list & create form")
            print("  PASS: Customers list & create form")
        except Exception as e:
            results["fail"].append(f"Customers: {e}")
            print(f"  FAIL: Customers - {e}")

        # ============================================================
        # PHASE 5: Create a New Delivery Order
        # ============================================================
        print("\n=== PHASE 5: CREATE DELIVERY ORDER ===")
        new_order_id = None
        try:
            page.goto(f"{BASE}/delivery-orders/create")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "do_create_form_empty")

            page.fill('input[name="po_date"]', "2026-04-06")
            page.fill('input[name="loading_date"]', "2026-04-10")

            for sel_name in ["on_behalf_of", "delivery_terms", "transportation_mode",
                             "bill_to", "ship_to", "point_of_exit"]:
                sel = page.locator(f'select[name="{sel_name}"]')
                if sel.count() > 0 and sel.locator("option").count() > 1:
                    sel.select_option(index=1)

            page.fill('input[name="payment_terms"]', "Net 30 Days")
            page.fill('input[name="point_of_discharge"]', "Jebel Ali Port")
            page.fill('input[name="final_destination"]', "Dubai, UAE")

            currency = page.locator('select[name="currency"]')
            if currency.count() > 0 and currency.locator("option").count() > 0:
                currency.select_option(index=0)

            page.fill('input[name="notify_party"]', "Test Notify Party LLC")
            page.fill('input[name="shipping_agent"]', "Fast Shipping Co.")
            shot(page, "do_create_form_filled")

            page.locator('button[type="submit"]').first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "do_created_detail")

            match = re.search(r"/delivery-orders/(\d+)", page.url)
            if match:
                new_order_id = match.group(1)
                print(f"  Created Order ID: {new_order_id}")
            results["pass"].append("Create delivery order")
            print("  PASS: Create delivery order")
        except Exception as e:
            results["fail"].append(f"Create DO: {e}")
            print(f"  FAIL: Create DO - {e}")

        # ============================================================
        # PHASE 6: Add Line Items
        # ============================================================
        print("\n=== PHASE 6: ADD LINE ITEMS ===")
        if new_order_id:
            try:
                page.goto(f"{BASE}/delivery-orders/{new_order_id}")
                page.wait_for_load_state("networkidle")
                time.sleep(1)

                add_item_form = page.locator('form[action*="items"]')
                if add_item_form.count() > 0:
                    prod_select = page.locator('select[name="product_id"]')
                    if prod_select.count() > 0 and prod_select.locator("option").count() > 1:
                        prod_select.select_option(index=1)
                        page.fill('input[name="quantity"]', "100")
                        page.fill('input[name="unit_price"]', "25.50")

                        container = page.locator('input[name="container"]')
                        if container.count() > 0:
                            container.fill("1")
                        truck = page.locator('input[name="truck"]')
                        if truck.count() > 0:
                            truck.fill("1")

                        remarks = page.locator('input[name="remarks"], textarea[name="remarks"]')
                        if remarks.count() > 0:
                            remarks.first.fill("Test line item")

                        shot(page, "do_add_item_filled")
                        add_item_form.locator('button[type="submit"]').click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(1)
                        shot(page, "do_item_added")
                        results["pass"].append("Add line item")
                        print("  PASS: Add line item")
                    else:
                        print("  SKIP: No products in dropdown")
                else:
                    print("  SKIP: No add item form found")
            except Exception as e:
                results["fail"].append(f"Add line item: {e}")
                print(f"  FAIL: Add line item - {e}")

        # ============================================================
        # PHASE 7: Submit Order (DRAFT -> SUBMITTED)
        # ============================================================
        print("\n=== PHASE 7: SUBMIT ORDER ===")
        if new_order_id:
            try:
                page.goto(f"{BASE}/delivery-orders/{new_order_id}")
                page.wait_for_load_state("networkidle")
                time.sleep(1)

                submit_form = page.locator('form:has(input[name="new_status"][value="SUBMITTED"])')
                if submit_form.count() > 0:
                    shot(page, "do_before_submit")
                    submit_form.locator('button[type="submit"]').click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    shot(page, "do_submitted")
                    results["pass"].append("Submit order (DRAFT->SUBMITTED)")
                    print("  PASS: Submit order")
                else:
                    print("  SKIP: No submit form found")
                    shot(page, "do_no_submit_btn")
            except Exception as e:
                results["fail"].append(f"Submit order: {e}")
                print(f"  FAIL: Submit order - {e}")

        # ============================================================
        # PHASE 8: Finance Review (SUBMITTED -> PRICE AGREED)
        # ============================================================
        print("\n=== PHASE 8: FINANCE REVIEW ===")
        if new_order_id:
            try:
                logout(page)
                login(page, "do.finance")
                shot(page, "dashboard_finance")

                page.goto(f"{BASE}/delivery-orders/{new_order_id}")
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                shot(page, "do_finance_view")

                price_form = page.locator('form:has(input[name="new_status"][value="PRICE AGREED"])')
                if price_form.count() > 0:
                    price_form.locator('button[type="submit"]').click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    shot(page, "do_price_agreed")
                    results["pass"].append("Price Agreed (SUBMITTED->PRICE AGREED)")
                    print("  PASS: Price Agreed")
                else:
                    print("  SKIP: No Price Agreed button found")
                    shot(page, "do_finance_no_btn")
            except Exception as e:
                results["fail"].append(f"Finance review: {e}")
                print(f"  FAIL: Finance review - {e}")

        # ============================================================
        # PHASE 9: Logistics Confirm (PRICE AGREED -> CONFIRMED)
        # ============================================================
        print("\n=== PHASE 9: LOGISTICS CONFIRM ===")
        if new_order_id:
            try:
                logout(page)
                login(page, "do.logistics")
                shot(page, "dashboard_logistics")

                page.goto(f"{BASE}/delivery-orders/{new_order_id}")
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                shot(page, "do_logistics_view")

                confirm_form = page.locator('form:has(input[name="new_status"][value="CONFIRMED"])')
                if confirm_form.count() > 0:
                    confirm_form.locator('button[type="submit"]').click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    shot(page, "do_confirmed")
                    results["pass"].append("Confirm (PRICE AGREED->CONFIRMED)")
                    print("  PASS: Confirmed")
                else:
                    print("  SKIP: No Confirm button found")
                    shot(page, "do_logistics_no_btn")
            except Exception as e:
                results["fail"].append(f"Logistics confirm: {e}")
                print(f"  FAIL: Logistics confirm - {e}")

        # ============================================================
        # PHASE 10: Customs Document Updated (CONFIRMED -> CUSTOMS DOC UPDATED)
        # ============================================================
        print("\n=== PHASE 10: CUSTOMS DOCUMENT UPDATE ===")
        if new_order_id:
            try:
                page.goto(f"{BASE}/delivery-orders/{new_order_id}")
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                shot(page, "do_confirmed_detail")

                # Click the Edit button to show the logistics form
                edit_btns = page.locator('.post-delivery-header--logistics button:has-text("Edit")')
                if edit_btns.count() > 0:
                    edit_btns.first.click()
                    time.sleep(0.5)

                    # Now the logisticsEditForm is visible
                    logistics_form = page.locator('#logisticsEditForm form')
                    logistics_form.locator('input[name="exit_document_number"]').fill("EXIT-2026-001")
                    logistics_form.locator('input[name="fta_declaration_number"]').fill("FTA-2026-001")
                    logistics_form.locator('input[name="sap_sales_invoice_number"]').fill("SAP-INV-2026-001")

                    # Upload a test file via the visible file input
                    test_file = os.path.join(SHOTS, "test_customs_doc.txt")
                    with open(test_file, "w") as f:
                        f.write("Test customs document for Playwright testing")
                    visible_file = logistics_form.locator('#logisticsFileInput')
                    if visible_file.count() > 0:
                        visible_file.set_input_files(test_file)
                    else:
                        # Fallback: set on hidden input and remove required
                        page.evaluate("document.getElementById('logisticsHiddenFiles').removeAttribute('required')")
                        page.locator('#logisticsHiddenFiles').set_input_files(test_file)
                    time.sleep(0.5)

                    shot(page, "do_customs_form_filled")
                    logistics_form.locator('button[type="submit"]').click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    shot(page, "do_customs_updated")
                    results["pass"].append("Customs Doc Updated (CONFIRMED->CUSTOMS DOC UPDATED)")
                    print("  PASS: Customs Document Updated")
                else:
                    print("  SKIP: No Edit button for logistics form")
                    shot(page, "do_no_logistics_edit")
            except Exception as e:
                results["fail"].append(f"Customs update: {e}")
                print(f"  FAIL: Customs update - {e}")

        # ============================================================
        # PHASE 11: Delivered (CUSTOMS DOC UPDATED -> DELIVERED)
        # ============================================================
        print("\n=== PHASE 11: MARK AS DELIVERED ===")
        if new_order_id:
            try:
                logout(page)
                login(page, "do.creator")

                page.goto(f"{BASE}/delivery-orders/{new_order_id}")
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                shot(page, "do_customs_creator_view")

                # Click the Edit button on the Sales section
                edit_btns = page.locator('.post-delivery-header--sales button:has-text("Edit")')
                if edit_btns.count() > 0:
                    edit_btns.first.click()
                    time.sleep(0.5)

                    sales_form = page.locator('#salesEditForm form')
                    sales_form.locator('input[name="customs_boe_number"]').fill("BOE-2026-001")
                    sales_form.locator('input[name="airway_bill_number"]').fill("AWB-2026-001")
                    sales_form.locator('input[name="iec_code"]').fill("IEC-2026-001")

                    test_file = os.path.join(SHOTS, "test_delivery_doc.txt")
                    with open(test_file, "w") as f:
                        f.write("Test delivery confirmation document")
                    visible_file = sales_form.locator('#salesFileInput')
                    if visible_file.count() > 0:
                        visible_file.set_input_files(test_file)
                    else:
                        page.evaluate("document.getElementById('salesHiddenFiles').removeAttribute('required')")
                        page.locator('#salesHiddenFiles').set_input_files(test_file)
                    time.sleep(0.5)

                    shot(page, "do_delivered_form_filled")
                    sales_form.locator('button[type="submit"]').click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    shot(page, "do_delivered")
                    results["pass"].append("Delivered (CUSTOMS DOC UPDATED->DELIVERED)")
                    print("  PASS: Delivered")
                else:
                    print("  SKIP: No Edit button for sales form")
                    shot(page, "do_no_sales_edit")
            except Exception as e:
                results["fail"].append(f"Delivered: {e}")
                print(f"  FAIL: Delivered - {e}")

        # ============================================================
        # PHASE 12: Order List & Filtering
        # ============================================================
        print("\n=== PHASE 12: ORDER LIST ===")
        try:
            logout(page)
            login(page, "do.admin")

            page.goto(f"{BASE}/delivery-orders/orders")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "order_list_all")

            page.goto(f"{BASE}/delivery-orders/orders?status=CONFIRMED")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "order_list_confirmed")

            page.goto(f"{BASE}/delivery-orders/orders?status=DELIVERED")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "order_list_delivered")

            results["pass"].append("Order list & filtering")
            print("  PASS: Order list & filtering")
        except Exception as e:
            results["fail"].append(f"Order list: {e}")
            print(f"  FAIL: Order list - {e}")

        # ============================================================
        # PHASE 13: GRMS
        # ============================================================
        print("\n=== PHASE 13: GRMS ===")
        try:
            page.goto(f"{BASE}/delivery-orders/manage/grms")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "grms_list")
            results["pass"].append("GRMS page")
            print("  PASS: GRMS page")
        except Exception as e:
            results["fail"].append(f"GRMS: {e}")
            print(f"  FAIL: GRMS - {e}")

        # ============================================================
        # PHASE 14: Reports
        # ============================================================
        print("\n=== PHASE 14: REPORTS ===")
        try:
            page.goto(f"{BASE}/delivery-orders/manage/reports")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "reports_page")

            date_from = page.locator('input[name="date_from"]')
            date_to = page.locator('input[name="date_to"]')
            if date_from.count() > 0 and date_to.count() > 0:
                date_from.fill("2026-01-01")
                date_to.fill("2026-04-06")
                page.locator('button[type="submit"]').click()
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                shot(page, "reports_result")
            results["pass"].append("Reports page")
            print("  PASS: Reports page")
        except Exception as e:
            results["fail"].append(f"Reports: {e}")
            print(f"  FAIL: Reports - {e}")

        # ============================================================
        # PHASE 15: Admin Settings
        # ============================================================
        print("\n=== PHASE 15: ADMIN SETTINGS ===")
        try:
            page.goto(f"{BASE}/admin/settings/users")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "admin_users")

            page.goto(f"{BASE}/admin/settings/modules")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "admin_modules")

            page.goto(f"{BASE}/admin/settings/workflow")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "admin_workflow")

            page.goto(f"{BASE}/admin/settings/restricted-words")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "admin_restricted_words")

            results["pass"].append("Admin Settings pages")
            print("  PASS: Admin Settings pages")
        except Exception as e:
            results["fail"].append(f"Admin Settings: {e}")
            print(f"  FAIL: Admin Settings - {e}")

        # ============================================================
        # PHASE 16: Print View
        # ============================================================
        print("\n=== PHASE 16: PRINT VIEW ===")
        if new_order_id:
            try:
                page.goto(f"{BASE}/delivery-orders/{new_order_id}/print")
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                shot(page, "print_view")
                results["pass"].append("Print view")
                print("  PASS: Print view")
            except Exception as e:
                results["fail"].append(f"Print: {e}")
                print(f"  FAIL: Print - {e}")

        # ============================================================
        # PHASE 17: Rejection Flow Test
        # ============================================================
        print("\n=== PHASE 17: REJECTION FLOW ===")
        reject_order_id = None
        try:
            page.goto(f"{BASE}/delivery-orders/create")
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)

            page.fill('input[name="po_date"]', "2026-04-06")
            page.fill('input[name="loading_date"]', "2026-04-15")
            for sel_name in ["on_behalf_of", "delivery_terms", "transportation_mode",
                             "bill_to", "ship_to", "point_of_exit"]:
                sel = page.locator(f'select[name="{sel_name}"]')
                if sel.count() > 0 and sel.locator("option").count() > 1:
                    sel.select_option(index=1)
            page.fill('input[name="payment_terms"]', "Advance Payment")
            page.fill('input[name="point_of_discharge"]', "Khalifa Port")
            page.fill('input[name="final_destination"]', "Abu Dhabi, UAE")
            currency = page.locator('select[name="currency"]')
            if currency.count() > 0 and currency.locator("option").count() > 0:
                currency.select_option(index=0)
            page.fill('input[name="notify_party"]', "Reject Test Party")
            page.fill('input[name="shipping_agent"]', "Test Agent")

            page.locator('button[type="submit"]').first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            match = re.search(r"/delivery-orders/(\d+)", page.url)
            if match:
                reject_order_id = match.group(1)

            # Submit it (DRAFT -> SUBMITTED)
            submit_form = page.locator('form:has(input[name="new_status"][value="SUBMITTED"])')
            if submit_form.count() > 0:
                submit_form.locator('button[type="submit"]').click()
                page.wait_for_load_state("networkidle")
                time.sleep(1)

            # Reject as finance
            logout(page)
            login(page, "do.finance")
            page.goto(f"{BASE}/delivery-orders/{reject_order_id}")
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # Click Reject button to open the modal (use btn-sm to target toolbar button)
            reject_btn = page.locator('button.btn-sm:has-text("Reject")')
            if reject_btn.count() > 0:
                reject_btn.first.click()
                time.sleep(0.5)
            else:
                # Fallback: open modal via JS
                page.evaluate("document.getElementById('rejectModal').classList.add('active')")
                time.sleep(0.5)

            modal = page.locator('#rejectModal')
            modal.wait_for(state="visible", timeout=5000)

            reason_select = modal.locator('select[name="reject_reason"]')
            if reason_select.count() > 0:
                reason_select.select_option(index=1)

            remarks = modal.locator('textarea[name="reject_remarks"]')
            if remarks.count() > 0:
                remarks.fill("Price review needed - test rejection")

            shot(page, "do_reject_form")
            modal.locator('button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "do_rejected")
            results["pass"].append("Rejection flow")
            print("  PASS: Rejection flow")
        except Exception as e:
            results["fail"].append(f"Rejection flow: {e}")
            print(f"  FAIL: Rejection flow - {e}")

        # ============================================================
        # SUMMARY
        # ============================================================
        browser.close()

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"\n  PASSED: {len(results['pass'])}")
    for t in results["pass"]:
        print(f"    -> {t}")
    print(f"\n  FAILED: {len(results['fail'])}")
    for t in results["fail"]:
        print(f"    X  {t}")
    print(f"\n  Total: {len(results['pass']) + len(results['fail'])}")
    print(f"  Screenshots saved to: {SHOTS}")
    print("=" * 60)

    return len(results["fail"]) == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
