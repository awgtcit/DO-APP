"""
Playwright screenshot capture for DO User Manual.
Logs in as admin and captures every major page view.
Images saved to static/screenshots/
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5080"
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "screenshots")

# ── Login credentials (use an admin / approver account) ──
# Uses test admin user created by create_test_users.py
USERNAME = os.environ.get("DO_SCREENSHOT_USER", "do.admin")
PASSWORD = os.environ.get("DO_SCREENSHOT_PASS", "Test@2025")

# ── Pages to capture ──
PAGES = [
    # (filename, url_path, description, wait_selector, extra_actions)
    ("login",           "/auth/login",                      "Login Page",               "input#username",           None),
    ("dashboard",       "/delivery-orders/",                "Dashboard",                ".kpi-card, .management-section",  None),
    ("order_list",      "/delivery-orders/orders",          "Order List",               "table, .dataTables_wrapper",      None),
    ("create_order",    "/delivery-orders/create",          "Create New Order",         "form",                     None),
    ("products",        "/delivery-orders/manage/products", "Products Management",      "table",                    None),
    ("product_create",  "/delivery-orders/manage/products/create", "Add Product",       "form",                     None),
    ("customers",       "/delivery-orders/manage/customers","Customers Management",     "table",                    None),
    ("customer_create", "/delivery-orders/manage/customers/create","Add Customer",      "form",                     None),
    ("grms",            "/delivery-orders/manage/grms",     "GRMS List",                "table, .card",             None),
    ("reports",         "/delivery-orders/manage/reports",  "Reports",                  "form, .card",              None),
]


def capture_all():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            device_scale_factor=2,                      # Retina quality
        )
        page = context.new_page()

        # ─── 1. Capture Login page (before logging in) ───
        print("[1/N] Capturing login page ...")
        page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(
            path=os.path.join(SCREENSHOTS_DIR, "login.png"),
            full_page=True,
        )
        print("  ✓ login.png")

        # ─── 2. Log in ───
        print("[*] Logging in ...")
        page.fill("input#username", USERNAME)
        page.fill("input#password", PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Check if redirected to ISP page
        if "/isp" in page.url:
            print("  → ISP acceptance page detected, accepting ...")
            # Try to accept ISP
            accept_btn = page.query_selector('button[type="submit"]')
            if accept_btn:
                accept_btn.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)

        print(f"  ✓ Logged in → {page.url}")

        # ─── 3. Capture each page ───
        captures = [
            # (filename,        path,                                    description)
            ("dashboard",       "/delivery-orders/",                     "Dashboard"),
            ("order_list",      "/delivery-orders/orders",               "Order List"),
            ("create_order",    "/delivery-orders/create",               "Create New Order Form"),
            ("products",        "/delivery-orders/manage/products",      "Products List"),
            ("product_create",  "/delivery-orders/manage/products/create","Add Product Form"),
            ("customers",       "/delivery-orders/manage/customers",     "Customers List"),
            ("customer_create", "/delivery-orders/manage/customers/create","Add Customer Form"),
            ("grms",            "/delivery-orders/manage/grms",          "GRMS Records"),
            ("reports",         "/delivery-orders/manage/reports",       "Reports"),
        ]

        # Pages that are too tall for full_page screenshot (timeout)
        VIEWPORT_ONLY = {"products", "reports"}

        for i, (fname, path, desc) in enumerate(captures, 2):
            print(f"[{i}/{len(captures)+1}] Capturing {desc} ...")
            try:
                page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(1200)   # let JS render (DataTables etc.)

                # Scroll to bottom and back to trigger lazy elements
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(300)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(300)

                use_full = fname not in VIEWPORT_ONLY
                page.screenshot(
                    path=os.path.join(SCREENSHOTS_DIR, f"{fname}.png"),
                    full_page=use_full,
                    timeout=60000,
                )
                print(f"  ✓ {fname}.png")
            except Exception as e:
                print(f"  ✗ FAILED {fname}: {e}")

        # ─── 4. Try to capture an order detail & print view ───
        # Navigate to order list and click the first order if available
        print(f"[*] Attempting to capture order detail ...")
        try:
            page.goto(f"{BASE_URL}/delivery-orders/orders", wait_until="networkidle")
            page.wait_for_timeout(1000)

            # Find first order link in the table
            first_link = page.query_selector("table tbody tr:first-child a")
            if first_link:
                href = first_link.get_attribute("href")
                if href:
                    page.goto(f"{BASE_URL}{href}" if href.startswith("/") else href, wait_until="networkidle")
                    page.wait_for_timeout(1000)
                    page.screenshot(
                        path=os.path.join(SCREENSHOTS_DIR, "order_detail.png"),
                        full_page=True,
                    )
                    print("  ✓ order_detail.png")

                    # Try print view
                    print_link = page.query_selector('a[href*="/print"]')
                    if print_link:
                        print_href = print_link.get_attribute("href")
                        if print_href:
                            page.goto(
                                f"{BASE_URL}{print_href}" if print_href.startswith("/") else print_href,
                                wait_until="networkidle",
                            )
                            page.wait_for_timeout(1000)
                            page.screenshot(
                                path=os.path.join(SCREENSHOTS_DIR, "order_print.png"),
                                full_page=True,
                            )
                            print("  ✓ order_print.png")
                else:
                    print("  ⚠ No order link found")
            else:
                print("  ⚠ No orders in the list to capture detail")
        except Exception as e:
            print(f"  ✗ order_detail failed: {e}")

        browser.close()

    # List what we captured
    print("\n═══ Screenshots captured ═══")
    for f in sorted(os.listdir(SCREENSHOTS_DIR)):
        if f.endswith(".png"):
            size_kb = os.path.getsize(os.path.join(SCREENSHOTS_DIR, f)) / 1024
            print(f"  {f:30s} {size_kb:>7.1f} KB")
    print("════════════════════════════")


if __name__ == "__main__":
    capture_all()
