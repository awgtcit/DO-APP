"""
Live browser demo — full Delivery Order workflow across three users.

Demonstrates the corrected workflow:
  1. do.creator  → Creates a DO and Submits it         (DRAFT → SUBMITTED)
  2. do.finance  → Marks price agreed                  (SUBMITTED → PRICE AGREED)
  3. do.logistics → Confirms the order                 (PRICE AGREED → CONFIRMED)

Opens a real Edge browser so you can watch each step.

Usage:
    cd app
    python tests/test_do_workflow.py
"""

import os
import time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5080"
PASSWORD = "Test@2025"

SHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots", "workflow")
os.makedirs(SHOTS_DIR, exist_ok=True)

step_num = 0


def snap(page, name):
    """Take a full-page screenshot."""
    global step_num
    step_num += 1
    path = os.path.join(SHOTS_DIR, f"{step_num:02d}_{name}.png")
    page.screenshot(path=path, full_page=True)
    print(f"   📸  {step_num:02d}_{name}.png")


def login(page, username):
    """Logout then log in as a different user."""
    page.goto(f"{BASE}/auth/logout")
    page.wait_for_load_state("networkidle")
    page.goto(f"{BASE}/auth/login")
    page.wait_for_load_state("networkidle")
    page.fill("#username", username)
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    assert "/auth/login" not in page.url, f"Login failed for {username}"
    print(f"   ✅  Logged in as {username}")


def assert_status(page, expected):
    """Verify the status badge on the detail page."""
    badge = page.locator(".status-large")
    badge.wait_for(state="visible", timeout=5000)
    text = badge.inner_text().strip().upper()
    assert expected.upper() in text, f"Expected status '{expected}', got '{text}'"
    print(f"   ✔  Status is: {text}")


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            channel="msedge",
            slow_mo=400,
            args=["--start-maximized"],
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            no_viewport=True,
        )
        page = context.new_page()

        # Auto-accept browser confirm() dialogs
        page.on("dialog", lambda d: d.accept())

        print("\n" + "=" * 60)
        print("  DELIVERY ORDER — FULL WORKFLOW DEMO")
        print("=" * 60)

        # ────────────────────────────────────────────────────────
        # STEP 1: CREATOR — create & submit
        # ────────────────────────────────────────────────────────
        print("\n── STEP 1: do.creator creates & submits a DO ──")

        login(page, "do.creator")
        snap(page, "creator_logged_in")

        # Navigate to DO dashboard
        page.goto(f"{BASE}/delivery-orders/")
        page.wait_for_load_state("networkidle")
        snap(page, "creator_do_dashboard")

        # Click "New Order"
        page.click("a:has-text('New Order')")
        page.wait_for_load_state("networkidle")
        snap(page, "creator_create_form")

        # Fill required fields
        page.fill("input[name='po_date']", "2026-02-27")

        # Select first available "On Behalf Of"
        on_behalf = page.locator("select[name='on_behalf_of'] option:not([value=''])")
        if on_behalf.count() > 0:
            first_val = on_behalf.first.get_attribute("value")
            page.select_option("select[name='on_behalf_of']", first_val)

        # Optional fields to make it look real
        page.fill("input[name='payment_terms']", "BANK")

        # Select delivery terms
        dt_opts = page.locator("select[name='delivery_terms'] option:not([value=''])")
        if dt_opts.count() > 0:
            page.select_option("select[name='delivery_terms']", dt_opts.first.get_attribute("value"))

        snap(page, "creator_form_filled")

        # Submit form
        page.click("button[type='submit']:has-text('Create Order')")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        snap(page, "creator_order_created")

        # Should be on detail page now, status = DRAFT
        assert_status(page, "DRAFT")

        # Grab the order URL for later
        order_url = page.url
        print(f"   📄  Order URL: {order_url}")

        # Click "Submit" button to move DRAFT → SUBMITTED
        submit_btn = page.locator("button:has-text('Submit')")
        submit_btn.wait_for(state="visible", timeout=5000)
        snap(page, "creator_before_submit")
        submit_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        snap(page, "creator_submitted")
        assert_status(page, "SUBMITTED")
        print("   🚀  Order submitted successfully!")

        # ────────────────────────────────────────────────────────
        # STEP 2: FINANCE — mark Price Agreed
        # ────────────────────────────────────────────────────────
        print("\n── STEP 2: do.finance marks Price Agreed ──")

        login(page, "do.finance")
        snap(page, "finance_logged_in")

        # Go to the same order
        page.goto(order_url)
        page.wait_for_load_state("networkidle")
        snap(page, "finance_order_detail")
        assert_status(page, "SUBMITTED")

        # Finance should see "Price Agreed" button
        pa_btn = page.locator("button:has-text('Price Agreed')")
        pa_btn.wait_for(state="visible", timeout=5000)
        print("   ✔  'Price Agreed' button is visible for finance")
        snap(page, "finance_before_price_agreed")

        # Verify finance does NOT see "Confirm" button (that's logistics)
        confirm_btn = page.locator("button:has-text('Confirm')")
        assert confirm_btn.count() == 0, "Finance should NOT see Confirm button at SUBMITTED stage"
        print("   ✔  'Confirm' button is NOT visible (correct — requires logistics)")

        # Click "Price Agreed"
        pa_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        snap(page, "finance_price_agreed")
        assert_status(page, "PRICE AGREED")
        print("   💰  Price Agreed marked successfully!")

        # ────────────────────────────────────────────────────────
        # STEP 3: LOGISTICS — confirm the order
        # ────────────────────────────────────────────────────────
        print("\n── STEP 3: do.logistics confirms the order ──")

        login(page, "do.logistics")
        snap(page, "logistics_logged_in")

        # Go to the same order
        page.goto(order_url)
        page.wait_for_load_state("networkidle")
        snap(page, "logistics_order_detail")
        assert_status(page, "PRICE AGREED")

        # Logistics should see "Confirm" button
        confirm_btn = page.locator("button:has-text('Confirm')")
        confirm_btn.wait_for(state="visible", timeout=5000)
        print("   ✔  'Confirm' button is visible for logistics")
        snap(page, "logistics_before_confirm")

        # Verify logistics does NOT see "Price Agreed" button
        pa_btn = page.locator("button:has-text('Price Agreed')")
        assert pa_btn.count() == 0, "Logistics should NOT see Price Agreed button"
        print("   ✔  'Price Agreed' button is NOT visible (correct — requires finance)")

        # Click "Confirm"
        confirm_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        snap(page, "logistics_confirmed")
        assert_status(page, "CONFIRMED")
        print("   ✅  Order CONFIRMED successfully!")

        # ────────────────────────────────────────────────────────
        # SUMMARY
        # ────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  ✅ WORKFLOW COMPLETE!")
        print("  DRAFT → SUBMITTED → PRICE AGREED → CONFIRMED")
        print("")
        print("  Roles verified:")
        print("    do.creator   → Created & Submitted")
        print("    do.finance   → Price Agreed (no Confirm btn)")
        print("    do.logistics → Confirmed   (no Price Agreed btn)")
        print("=" * 60)

        snap(page, "workflow_complete")

        # Pause so user can inspect
        print("\n   Browser will stay open for 10 seconds...")
        time.sleep(10)

        context.close()
        browser.close()


if __name__ == "__main__":
    run()
