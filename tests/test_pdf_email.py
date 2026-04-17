"""
Quick test: trigger a SUBMITTED email with PDF attachment.

Creates a new DO as do.creator, fills ALL required fields,
submits it, and checks server logs for PDF attachment.
"""

import os, sys, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5080"
PASSWORD = "Test@2025"


def login(page, username):
    page.goto(f"{BASE}/auth/logout")
    page.wait_for_load_state("networkidle")
    page.goto(f"{BASE}/auth/login")
    page.wait_for_load_state("networkidle")
    page.fill("#username", username)
    page.fill("#password", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    assert "/auth/login" not in page.url, f"Login failed for {username}"
    print(f"  Logged in as {username}")


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            channel="msedge",
            slow_mo=300,
            args=["--start-maximized"],
        )
        context = browser.new_context(no_viewport=True)
        context.set_default_timeout(15000)
        page = context.new_page()
        page.on("dialog", lambda d: d.accept())

        print("\n== PDF ATTACHMENT TEST ==\n")

        # --- CREATOR: create a DO with all required fields ---
        login(page, "do.creator")
        page.goto(f"{BASE}/delivery-orders/")
        page.wait_for_load_state("networkidle")
        page.click("a:has-text('New Order')")
        page.wait_for_load_state("networkidle")

        # Fill required fields
        page.fill("input[name='po_date']", "2026-02-28")

        # On Behalf Of
        obo = page.locator("select[name='on_behalf_of'] option:not([value=''])")
        if obo.count() > 0:
            page.select_option("select[name='on_behalf_of']", obo.first.get_attribute("value"))

        page.fill("input[name='payment_terms']", "BANK")

        # Delivery terms
        dt = page.locator("select[name='delivery_terms'] option:not([value=''])")
        if dt.count() > 0:
            page.select_option("select[name='delivery_terms']", dt.first.get_attribute("value"))

        # Loading date
        page.fill("input[name='loading_date']", "2026-03-15")

        # Bill To
        bt = page.locator("select[name='bill_to'] option:not([value=''])")
        if bt.count() > 0:
            page.select_option("select[name='bill_to']", bt.first.get_attribute("value"))

        # Ship To
        st = page.locator("select[name='ship_to'] option:not([value=''])")
        if st.count() > 0:
            page.select_option("select[name='ship_to']", st.first.get_attribute("value"))

        # Point of Exit
        poe = page.locator("select[name='point_of_exit'] option:not([value=''])")
        if poe.count() > 0:
            page.select_option("select[name='point_of_exit']", poe.first.get_attribute("value"))

        # Final Destination
        page.fill("input[name='final_destination']", "Dubai, UAE")

        # Point of Discharge
        pod_field = page.locator("input[name='point_of_discharge']")
        if pod_field.count() > 0:
            pod_field.fill("Jebel Ali Port")

        print("  Form filled with all required fields")

        # Create order
        page.click("button[type='submit']:has-text('Create Order')")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)

        # Verify DRAFT
        badge = page.locator(".status-large")
        badge.wait_for(state="visible", timeout=5000)
        status = badge.inner_text().strip().upper()
        print(f"  Status: {status}")
        assert "DRAFT" in status, f"Expected DRAFT, got {status}"

        order_url = page.url
        print(f"  Order URL: {order_url}")

        # Add a line item (required for submission)
        prod_select = page.locator("select[name='product_id']")
        prod_select.wait_for(state="visible", timeout=5000)
        prod_opts = page.locator("select[name='product_id'] option:not([value=''])")
        if prod_opts.count() > 0:
            page.select_option("select[name='product_id']", prod_opts.first.get_attribute("value"))
        page.fill("input[name='quantity']", "100")
        page.fill("input[name='unit_price']", "10.50")
        page.click("button[type='submit']:has-text('Add')")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        print("  Line item added")

        # Submit the order (DRAFT -> SUBMITTED)
        submit_btn = page.locator("button:has-text('Submit')")
        submit_btn.wait_for(state="visible", timeout=5000)
        submit_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        badge = page.locator(".status-large")
        badge.wait_for(state="visible", timeout=5000)
        status = badge.inner_text().strip().upper()
        print(f"  Status after submit: {status}")

        if "SUBMITTED" in status:
            print("  ORDER SUBMITTED! Email with PDF attachment should be sending...")
            print("  Check Flask server logs for PDF generation + email send")
            time.sleep(5)  # Wait for background email thread
        else:
            # Check for flash errors
            flash = page.locator(".flash-message, .alert, .error")
            if flash.count() > 0:
                print(f"  Flash message: {flash.first.inner_text()}")
            print(f"  Submit may have failed — status is {status}")

        print("\n  Browser stays open for 8 seconds...")
        time.sleep(8)

        context.close()
        browser.close()
        print("\n== DONE ==")


if __name__ == "__main__":
    run()
