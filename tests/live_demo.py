"""
Live browser demo — opens your real Chrome and walks through every page,
takes a screenshot of each, so you can review styling and errors.
"""

import os
import time
import re
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5080"
USER = "sathish.narasimhan"
PASS = "Malt*2025"
SHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
os.makedirs(SHOTS_DIR, exist_ok=True)


def snap(page, name):
    """Take a full-page screenshot."""
    path = os.path.join(SHOTS_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    print(f"   📸 Screenshot saved: screenshots/{name}.png")


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            channel="msedge",
            slow_mo=200,
            args=["--start-maximized"],
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            no_viewport=True,
        )
        page = context.new_page()

        print("\n=== LIVE BROWSER DEMO WITH SCREENSHOTS ===\n")

        # 1. LOGIN
        print("1. Login Page...")
        page.goto(f"{BASE}/auth/login")
        page.wait_for_load_state("networkidle")
        snap(page, "01_login_page")
        page.fill("#username", USER)
        page.fill("#password", PASS)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        snap(page, "02_after_login")

        # 2. DO DASHBOARD
        print("2. DO Dashboard...")
        page.goto(f"{BASE}/delivery-orders/")
        page.wait_for_load_state("networkidle")
        snap(page, "03_do_dashboard")

        # 3. ORDER LIST
        print("3. Orders List...")
        page.goto(f"{BASE}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")
        snap(page, "04_orders_list")

        # 4. FILTER CONFIRMED
        print("4. Filter CONFIRMED...")
        page.goto(f"{BASE}/delivery-orders/orders?status=CONFIRMED")
        page.wait_for_load_state("networkidle")
        snap(page, "05_orders_confirmed")

        # 5. ORDER DETAIL
        print("5. Order Detail...")
        first_row = page.locator("table tbody tr.clickable-row").first
        if first_row.count():
            first_row.click()
            page.wait_for_load_state("networkidle")
            snap(page, "06_order_detail")
            
            match = re.search(r"/delivery-orders/(\d+)", page.url)
            if match:
                order_id = match.group(1)

                # 6. PRINT VIEW
                print("6. Print View...")
                page.goto(f"{BASE}/delivery-orders/{order_id}/print")
                page.wait_for_load_state("networkidle")
                snap(page, "07_print_view")

        # 7. CREATE FORM
        print("7. Create Order Form...")
        page.goto(f"{BASE}/delivery-orders/create")
        page.wait_for_load_state("networkidle")
        snap(page, "08_create_form")

        # 8. PRODUCTS
        print("8. Products Management...")
        page.goto(f"{BASE}/delivery-orders/manage/products")
        page.wait_for_load_state("networkidle")
        snap(page, "09_products")

        # 9. PRODUCT CREATE FORM
        print("9. Product Create Form...")
        page.goto(f"{BASE}/delivery-orders/manage/products/create")
        page.wait_for_load_state("networkidle")
        snap(page, "10_product_form")

        # 10. CUSTOMERS
        print("10. Customers Management...")
        page.goto(f"{BASE}/delivery-orders/manage/customers")
        page.wait_for_load_state("networkidle")
        snap(page, "11_customers")

        # 11. CUSTOMER CREATE FORM
        print("11. Customer Create Form...")
        page.goto(f"{BASE}/delivery-orders/manage/customers/create")
        page.wait_for_load_state("networkidle")
        snap(page, "12_customer_form")

        # 12. GRMS
        print("12. GRMS...")
        page.goto(f"{BASE}/delivery-orders/manage/grms")
        page.wait_for_load_state("networkidle")
        snap(page, "13_grms")

        # 13. REPORTS
        print("13. Reports...")
        page.goto(f"{BASE}/delivery-orders/manage/reports")
        page.wait_for_load_state("networkidle")
        snap(page, "14_reports")

        # 14. WEB APP HUB
        print("14. Web Application Hub...")
        page.goto(f"{BASE}/web-application/")
        page.wait_for_load_state("networkidle")
        snap(page, "15_webapp_hub")

        # 15. IT SUPPORT
        print("15. IT Support...")
        page.goto(f"{BASE}/it-support/")
        page.wait_for_load_state("networkidle")
        snap(page, "16_it_support")

        # 16. DMS
        print("16. DMS...")
        page.goto(f"{BASE}/dms/")
        page.wait_for_load_state("networkidle")
        snap(page, "17_dms")

        # 17. ANNOUNCEMENTS
        print("17. Announcements...")
        page.goto(f"{BASE}/announcements/")
        page.wait_for_load_state("networkidle")
        snap(page, "18_announcements")

        # 18. FACILITY
        print("18. Facility Management...")
        page.goto(f"{BASE}/facility/")
        page.wait_for_load_state("networkidle")
        snap(page, "19_facility")

        # 19. EMPLOYEE FORUM
        print("19. Employee Forum...")
        page.goto(f"{BASE}/forum/")
        page.wait_for_load_state("networkidle")
        snap(page, "20_forum")

        # 20. ISP ADMIN
        print("20. ISP Admin...")
        page.goto(f"{BASE}/isp-admin/")
        page.wait_for_load_state("networkidle")
        snap(page, "21_isp_admin")

        print("\n" + "=" * 50)
        print("  DONE — All screenshots saved to app/screenshots/")
        print("=" * 50)

        browser.close()


if __name__ == "__main__":
    run()
