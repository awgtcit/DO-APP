"""
Playwright validation script — tests login for all 4 DO roles
and verifies the application is working correctly.
"""
import sys
import os

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5080"
USERS = [
    ("do.creator", "Test@2025", "Creator"),
    ("do.finance", "Test@2025", "Finance"),
    ("do.logistics", "Test@2025", "Logistics"),
    ("do.admin", "Test@2025", "Admin"),
]
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots", "validation")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def test_user_login_and_dashboard(page, username, password, role_label):
    """Login as a user, verify dashboard loads, take screenshots."""
    print(f"\n{'='*60}")
    print(f"Testing: {role_label} ({username})")
    print(f"{'='*60}")

    # Go to login
    page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"{role_label}_01_login.png"))

    # Fill login form
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    # Check if login succeeded
    current_url = page.url
    print(f"  After login URL: {current_url}")
    page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"{role_label}_02_after_login.png"))

    if "/auth/login" in current_url:
        # Check for error messages
        error = page.query_selector(".alert-danger, .flash-danger, .error")
        err_text = error.inner_text() if error else "Unknown login error"
        print(f"  LOGIN FAILED: {err_text}")
        return False

    print(f"  Login successful!")

    # Navigate to delivery orders dashboard
    page.goto(f"{BASE_URL}/delivery-orders/", wait_until="networkidle")
    page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"{role_label}_03_do_dashboard.png"))
    print(f"  DO Dashboard loaded: {page.url}")

    # Check for KPI stats
    kpi_cards = page.query_selector_all(".kpi-card, .stat-card, .card")
    print(f"  KPI/Cards found: {len(kpi_cards)}")

    # Navigate to order list
    page.goto(f"{BASE_URL}/delivery-orders/orders", wait_until="networkidle")
    page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"{role_label}_04_order_list.png"))
    print(f"  Order list loaded: {page.url}")

    # Check for order rows
    order_rows = page.query_selector_all("table tbody tr")
    print(f"  Order rows found: {len(order_rows)}")

    # If there are orders, click the first one
    if order_rows:
        first_link = page.query_selector("table tbody tr:first-child a")
        if first_link:
            first_link.click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"{role_label}_05_order_detail.png"))
            print(f"  Order detail loaded: {page.url}")

    # Logout
    page.goto(f"{BASE_URL}/auth/logout", wait_until="networkidle")
    print(f"  Logged out.")

    return True


def main():
    print("\n" + "="*70)
    print("  DoApp Validation — Testing all 4 DO roles")
    print("="*70)

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        for username, password, role_label in USERS:
            try:
                ok = test_user_login_and_dashboard(page, username, password, role_label)
                results[role_label] = "PASS" if ok else "FAIL"
            except Exception as e:
                print(f"  ERROR: {e}")
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"{role_label}_ERROR.png"))
                results[role_label] = f"ERROR: {e}"

        browser.close()

    print("\n" + "="*70)
    print("  RESULTS SUMMARY")
    print("="*70)
    for role, result in results.items():
        print(f"  {role:12s} : {result}")
    print("="*70)

    return all(v == "PASS" for v in results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
