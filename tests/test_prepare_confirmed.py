"""Check order statuses and find/transition a test order to CONFIRMED."""
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


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        # Login as admin to see all orders and their statuses
        login(page, "do.admin", "Test@2025")

        # Check each status filter
        for status in ["CONFIRMED", "PRICE AGREED", "SUBMITTED", "DRAFT"]:
            page.goto(f"{BASE_URL}/delivery-orders/orders?status={status}", wait_until="networkidle")
            rows = page.query_selector_all("table tbody tr")
            print(f"{status:20s}: {len(rows)} orders")

            if status == "PRICE AGREED" and rows:
                # If we have PRICE AGREED orders, the logistics user can confirm them
                first_link = page.query_selector("table tbody tr:first-child td a")
                if first_link:
                    order_url = first_link.get_attribute("href")
                    print(f"  -> Found PRICE AGREED order: {order_url}")

        # Now let's use logistics user to confirm a PRICE AGREED order
        logout(page)
        login(page, "do.logistics", "Test@2025")

        page.goto(f"{BASE_URL}/delivery-orders/orders?status=PRICE AGREED", wait_until="networkidle")
        first_link = page.query_selector("table tbody tr:first-child td a")
        if first_link:
            first_link.click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "20_price_agreed_detail.png"))

            # Look for Confirm button
            confirm_btn = page.query_selector('button:has-text("Confirm")')
            if confirm_btn:
                print("  Found Confirm button, clicking...")
                page.on("dialog", lambda d: d.accept())
                confirm_btn.click()
                page.wait_for_load_state("networkidle")
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "21_after_confirm.png"))
                print(f"  After confirm URL: {page.url}")

                # Check for post-delivery sections
                logistics_section = page.query_selector(".post-delivery-header--logistics")
                sales_section = page.query_selector(".post-delivery-header--sales")
                print(f"  Logistics section visible: {logistics_section is not None}")
                print(f"  Sales section visible: {sales_section is not None}")

                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "22_confirmed_with_sections.png"), full_page=True)
            else:
                print("  No Confirm button found")
                # Show all buttons
                buttons = page.query_selector_all("button")
                for btn in buttons:
                    print(f"    Button: {btn.inner_text()}")
        else:
            print("  No PRICE AGREED orders found")
            # Try SUBMITTED orders with finance to price agree first
            logout(page)
            login(page, "do.finance", "Test@2025")

            page.goto(f"{BASE_URL}/delivery-orders/orders?status=SUBMITTED", wait_until="networkidle")
            first_link = page.query_selector("table tbody tr:first-child td a")
            if first_link:
                first_link.click()
                page.wait_for_load_state("networkidle")

                # Price agree
                price_btn = page.query_selector('button:has-text("Price Agreed")')
                if price_btn:
                    print("  Found Price Agreed button, clicking...")
                    page.on("dialog", lambda d: d.accept())
                    price_btn.click()
                    page.wait_for_load_state("networkidle")
                    print(f"  After price agree: {page.url}")

                    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "23_after_price_agree.png"))

                    # Now confirm with logistics
                    order_url = page.url
                    logout(page)
                    login(page, "do.logistics", "Test@2025")
                    page.goto(order_url, wait_until="networkidle")

                    confirm_btn = page.query_selector('button:has-text("Confirm")')
                    if confirm_btn:
                        print("  Found Confirm button, clicking...")
                        confirm_btn.click()
                        page.wait_for_load_state("networkidle")
                        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "24_confirmed.png"), full_page=True)

                        logistics_section = page.query_selector(".post-delivery-header--logistics")
                        sales_section = page.query_selector(".post-delivery-header--sales")
                        print(f"  Logistics section visible: {logistics_section is not None}")
                        print(f"  Sales section visible: {sales_section is not None}")

        browser.close()


if __name__ == "__main__":
    main()
