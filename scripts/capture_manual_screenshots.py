"""Capture complete set of screenshots for the comprehensive user manual."""
from playwright.sync_api import sync_playwright
import time
import os

BASE = "http://127.0.0.1:5080"
SHOTS = "static/screenshots"

os.makedirs(SHOTS, exist_ok=True)


def login(page, username="do.admin", password="Test@2025"):
    page.goto(f"{BASE}/auth/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(1)


def shot(page, name, full=False):
    path = f"{SHOTS}/{name}.png"
    page.screenshot(path=path, full_page=full)
    print(f"  [{name}] captured")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # ─── 1. LOGIN PAGE ───
        page.goto(f"{BASE}/auth/login")
        page.wait_for_load_state("networkidle")
        shot(page, "01_login")

        # ─── 2. LOGIN (filled) ───
        page.fill('input[name="username"]', "do.admin")
        page.fill('input[name="password"]', "Test@2025")
        shot(page, "02_login_filled")

        # Login
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # ─── 3. DASHBOARD ───
        page.goto(f"{BASE}/delivery-orders/dashboard")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot(page, "03_dashboard", full=True)

        # ─── 4. PRODUCTS LIST ───
        page.goto(f"{BASE}/delivery-orders/manage/products")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot(page, "04_products_list")

        # ─── 5. PRODUCT CREATE ───
        page.goto(f"{BASE}/delivery-orders/manage/products/new")
        page.wait_for_load_state("networkidle")
        shot(page, "05_product_create")

        # ─── 6. CUSTOMERS LIST ───
        page.goto(f"{BASE}/delivery-orders/manage/customers")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot(page, "06_customers_list")

        # ─── 7. CUSTOMER CREATE ───
        page.goto(f"{BASE}/delivery-orders/manage/customers/new")
        page.wait_for_load_state("networkidle")
        shot(page, "07_customer_create")

        # ─── 8. CREATE NEW DO ───
        page.goto(f"{BASE}/delivery-orders/create")
        page.wait_for_load_state("networkidle")
        shot(page, "08_do_create", full=True)

        # ─── 9. ORDER LIST (all) ───
        page.goto(f"{BASE}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot(page, "09_order_list")

        # ─── 10. ORDER LIST (filtered by status) ───
        page.goto(f"{BASE}/delivery-orders/orders?status=CONFIRMED")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot(page, "10_order_list_confirmed")

        # ─── 11. ORDER DETAIL (find a DRAFT order) ───
        page.goto(f"{BASE}/delivery-orders/orders?status=DRAFT")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        first = page.locator("table tbody tr:first-child a").first
        if first.count() > 0:
            first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)
            shot(page, "11_do_detail_draft", full=True)

        # ─── 12. ORDER DETAIL (SUBMITTED) ───
        page.goto(f"{BASE}/delivery-orders/orders?status=SUBMITTED")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        first = page.locator("table tbody tr:first-child a").first
        if first.count() > 0:
            first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)
            shot(page, "12_do_detail_submitted", full=True)

        # ─── 13. ORDER DETAIL (CONFIRMED - shows post-delivery tracking) ───
        page.goto(f"{BASE}/delivery-orders/orders?status=CONFIRMED")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        first = page.locator("table tbody tr:first-child a").first
        if first.count() > 0:
            first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)
            shot(page, "13_do_detail_confirmed", full=True)

        # ─── 14. ORDER DETAIL (DELIVERED) ───
        page.goto(f"{BASE}/delivery-orders/orders?status=DELIVERED")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        first = page.locator("table tbody tr:first-child a").first
        if first.count() > 0:
            first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)
            shot(page, "14_do_detail_delivered", full=True)

        # ─── 15. GRMS ───
        page.goto(f"{BASE}/delivery-orders/manage/grms")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot(page, "15_grms")

        # ─── 16. REPORTS ───
        page.goto(f"{BASE}/delivery-orders/manage/reports")
        page.wait_for_load_state("networkidle")
        shot(page, "16_reports")

        # ─── 17. ADMIN - USERS ───
        page.goto(f"{BASE}/admin/settings/users")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        shot(page, "17_admin_users")

        # ─── 18. ADMIN - MODULES ───
        page.goto(f"{BASE}/admin/settings/modules")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        shot(page, "18_admin_modules")

        # ─── 19. ADMIN - WORKFLOW ───
        page.goto(f"{BASE}/admin/settings/workflow")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        shot(page, "19_admin_workflow", full=True)

        # ─── 20. PRINT VIEW ───
        page.goto(f"{BASE}/delivery-orders/orders?status=CONFIRMED")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        first = page.locator("table tbody tr:first-child a").first
        if first.count() > 0:
            first.click()
            page.wait_for_load_state("networkidle")
            # Get the order URL and open print view
            url = page.url
            if "/detail/" in url:
                order_id = url.split("/detail/")[1].split("?")[0]
                page.goto(f"{BASE}/delivery-orders/print/{order_id}")
                page.wait_for_load_state("networkidle")
                time.sleep(0.5)
                shot(page, "20_print_view", full=True)

        browser.close()
        print("\nAll screenshots captured!")


if __name__ == "__main__":
    main()
