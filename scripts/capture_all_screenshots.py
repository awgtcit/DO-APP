"""Capture all screenshots for the user manual - updated with latest features."""
from playwright.sync_api import sync_playwright
import time

BASE = "http://127.0.0.1:5080"
SHOTS = "static/screenshots"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # 1. Login page
        page.goto(f"{BASE}/auth/login")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"{SHOTS}/login.png", full_page=False)
        print("1. Login page captured")

        # Login as admin
        page.fill('input[name="username"]', "do.admin")
        page.fill('input[name="password"]', "Test@2025")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")

        # 2. Dashboard
        page.goto(f"{BASE}/delivery-orders/dashboard")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=f"{SHOTS}/dashboard.png", full_page=True)
        print("2. Dashboard captured")

        # 3. Create Order
        page.goto(f"{BASE}/delivery-orders/create")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        page.screenshot(path=f"{SHOTS}/create_order.png", full_page=True)
        print("3. Create Order captured")

        # 4. Order List
        page.goto(f"{BASE}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=f"{SHOTS}/order_list.png", full_page=False)
        print("4. Order List captured")

        # 5. Order Detail (find a confirmed order to show post-delivery fields)
        page.goto(f"{BASE}/delivery-orders/orders?status=CUSTOMS+DOCUMENT+UPDATED")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        # Click the first order link
        first_link = page.locator("table tbody tr:first-child td:first-child a")
        if first_link.count() > 0:
            first_link.click()
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)
            page.screenshot(path=f"{SHOTS}/order_detail.png", full_page=True)
            print("5. Order Detail (Customs Updated) captured")
        else:
            # Fallback: try any confirmed order
            page.goto(f"{BASE}/delivery-orders/orders?status=CONFIRMED")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            first_link = page.locator("table tbody tr:first-child td:first-child a")
            if first_link.count() > 0:
                first_link.click()
                page.wait_for_load_state("networkidle")
                time.sleep(0.5)
                page.screenshot(path=f"{SHOTS}/order_detail.png", full_page=True)
                print("5. Order Detail (Confirmed) captured")
            else:
                print("5. No confirmed/customs orders found for detail screenshot")

        # 6. Products
        page.goto(f"{BASE}/delivery-orders/manage/products")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        page.screenshot(path=f"{SHOTS}/products.png", full_page=False)
        print("6. Products captured")

        # 7. Product Create
        page.goto(f"{BASE}/delivery-orders/manage/products/new")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"{SHOTS}/product_create.png", full_page=False)
        print("7. Product Create captured")

        # 8. Customers
        page.goto(f"{BASE}/delivery-orders/manage/customers")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        page.screenshot(path=f"{SHOTS}/customers.png", full_page=False)
        print("8. Customers captured")

        # 9. Customer Create
        page.goto(f"{BASE}/delivery-orders/manage/customers/new")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"{SHOTS}/customer_create.png", full_page=False)
        print("9. Customer Create captured")

        # 10. GRMS
        page.goto(f"{BASE}/delivery-orders/manage/grms")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        page.screenshot(path=f"{SHOTS}/grms.png", full_page=False)
        print("10. GRMS captured")

        # 11. Reports
        page.goto(f"{BASE}/delivery-orders/manage/reports")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"{SHOTS}/reports.png", full_page=False)
        print("11. Reports captured")

        # 12. Admin Settings - Workflow
        page.goto(f"{BASE}/admin/settings/workflow")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        page.screenshot(path=f"{SHOTS}/workflow_editor.png", full_page=True)
        print("12. Workflow Editor captured")

        # 13. Admin Settings - Users
        page.goto(f"{BASE}/admin/settings/users")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        page.screenshot(path=f"{SHOTS}/admin_users.png", full_page=False)
        print("13. Admin Users captured")

        # 14. Admin Settings - Modules
        page.goto(f"{BASE}/admin/settings/modules")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        page.screenshot(path=f"{SHOTS}/admin_modules.png", full_page=False)
        print("14. Admin Modules captured")

        browser.close()
        print("\nAll screenshots captured!")


if __name__ == "__main__":
    main()
