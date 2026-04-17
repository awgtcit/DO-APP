"""
Full workflow end-to-end test for Delivery Orders.

Covers:
  1. Blank-submit validation (mandatory field gate)
  2. Create order -> fill required fields -> add line item -> Submit
  3. Finance login -> Price Agreed
  4. Logistics login -> Confirm
  5. QR code appears only after confirmation

Runs in a visible Edge browser so the tester can observe every step.
"""

import os, re, pytest, time
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://localhost:5080"

# -- Credentials --
CREATOR_USER = os.environ.get("TEST_USERNAME", "sathish.narasimhan")
CREATOR_PASS = os.environ.get("TEST_PASSWORD", "Malt*2025")

FINANCE_USER = "do.finance"
FINANCE_PASS = "Test@2025"

LOGISTICS_USER = "do.logistics"
LOGISTICS_PASS = "Test@2025"

SCREENSHOTS = os.path.join(os.path.dirname(__file__), "..", "screenshots")
os.makedirs(SCREENSHOTS, exist_ok=True)


# -- Helpers --

def login(page, username, password, label=""):
    """Login helper -- clears cookies, navigates to login page, authenticates."""
    # Clear all cookies to ensure a fresh session
    page.context.clear_cookies()

    # Go directly to the login page
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")

    # Wait for the login form to appear
    page.wait_for_selector("input[name='username']", state="visible", timeout=20000)

    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")

    # Handle ISP acceptance if shown
    if "information_security" in page.url.lower() or "isp" in page.url.lower():
        # Check the "I have read..." checkbox first to enable the Accept button
        checkbox = page.locator("#isp-accept")
        if checkbox.count() > 0 and not checkbox.is_checked():
            checkbox.check()

        accept_btn = page.locator("#accept-btn")
        if accept_btn.count() > 0:
            accept_btn.click()
            page.wait_for_load_state("networkidle")

    print(f"  [OK] Logged in as {username} ({label})")


def navigate_to_do_dashboard(page):
    """Navigate to the Delivery Order dashboard."""
    page.goto(f"{BASE_URL}/delivery-orders/")
    page.wait_for_load_state("networkidle")


def get_order_id_from_url(page) -> str:
    """Extract the order numeric id from the current URL."""
    m = re.search(r"/delivery-orders/(\d+)", page.url)
    return m.group(1) if m else ""


# -- Test --

class TestFullWorkflow:
    """Full DO workflow -- visible browser, sequential steps."""

    @pytest.fixture(scope="class")
    def shared(self):
        """Shared state between tests."""
        return {"order_id": None, "po_number": None}

    @pytest.fixture(scope="class")
    def browser_ctx(self):
        """Launch a visible Edge browser for the entire test class."""
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=False,
            channel="msedge",
            slow_mo=400,
            args=["--start-maximized"],
        )
        context = browser.new_context(no_viewport=True)
        context.set_default_timeout(30000)
        page = context.new_page()
        # Auto-accept all confirm() dialogs
        page.on("dialog", lambda dialog: dialog.accept())
        yield page
        browser.close()
        pw.stop()

    # -- 1. Creator: create order with blank fields --
    def test_01_creator_login(self, browser_ctx, shared):
        """Login as the order creator."""
        login(browser_ctx, CREATOR_USER, CREATOR_PASS, "Creator")
        navigate_to_do_dashboard(browser_ctx)
        expect(browser_ctx.locator("h1")).to_contain_text("Delivery Order")

    def test_02_create_new_order(self, browser_ctx, shared):
        """Create a minimal order (only required fields: date & on-behalf-of)."""
        page = browser_ctx
        page.locator("a:has-text('New Order')").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Create")

        # Fill only the two required create-form fields
        page.fill("input[name='po_date']", "2026-02-27")
        page.select_option("select[name='on_behalf_of']", index=1)  # first manager

        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # Should land on detail page with DRAFT status
        assert "/delivery-orders/" in page.url
        order_id = get_order_id_from_url(page)
        assert order_id, "Should navigate to the new order detail page"
        shared["order_id"] = order_id

        # Capture PO number
        h1_text = page.locator("h1").inner_text()
        shared["po_number"] = h1_text.strip()
        print(f"  [OK] Created order {shared['po_number']} (id={order_id})")

        expect(page.locator(".status-large")).to_contain_text("DRAFT")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_01_draft.png"))

    # -- 2. Try to submit with blank mandatory fields --
    def test_03_blank_submit_blocked(self, browser_ctx, shared):
        """Submit should fail -- no line items, no bill-to, ship-to, etc."""
        page = browser_ctx

        # Click Submit button (confirm dialog auto-accepted by fixture)
        submit_btn = page.locator("button:has-text('Submit')")
        expect(submit_btn).to_be_visible()
        submit_btn.click()
        page.wait_for_load_state("networkidle")

        # Should stay on the detail page with warning flash messages
        assert shared["order_id"] in page.url
        expect(page.locator(".status-large")).to_contain_text("DRAFT")

        # Check for validation error messages in toast container
        toasts = page.locator(".toast")
        expect(toasts.first).to_be_visible()
        flash_text = toasts.all_inner_texts()
        combined = " ".join(flash_text).lower()
        assert "required" in combined or "line item" in combined, \
            f"Expected validation error messages, got: {flash_text}"
        print(f"  [OK] Blank submit blocked with validation errors")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_02_blank_submit_blocked.png"))

    # -- 3. Fill required fields via Edit --
    def test_04_fill_required_fields(self, browser_ctx, shared):
        """Edit the order to fill all mandatory fields."""
        page = browser_ctx

        edit_btn = page.locator("a:has-text('Edit')")
        expect(edit_btn).to_be_visible()
        edit_btn.click()
        page.wait_for_load_state("networkidle")

        # Fill Loading Date
        page.fill("input[name='loading_date']", "2026-03-05")

        # Fill Delivery Terms
        page.select_option("select[name='delivery_terms']", index=1)

        # Fill Bill To
        page.select_option("select[name='bill_to']", index=1)

        # Fill Ship To
        page.select_option("select[name='ship_to']", index=1)

        # Fill Point of Exit
        page.select_option("select[name='point_of_exit']", index=1)

        # Fill Final Destination
        page.fill("input[name='final_destination']", "Test Destination")

        # Save
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".status-large")).to_contain_text("DRAFT")
        print(f"  [OK] Required fields filled via Edit")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_03_fields_filled.png"))

    # -- 4. Add a line item --
    def test_05_add_line_item(self, browser_ctx, shared):
        """Add at least one line item to the order."""
        page = browser_ctx

        # Scroll to add-item form
        add_form = page.locator(".add-item-form")
        expect(add_form).to_be_visible()
        add_form.scroll_into_view_if_needed()

        # Select a product
        page.select_option("select[name='product_id']", index=1)

        # Fill quantity and unit price
        page.fill("input[name='quantity']", "100")
        page.fill("input[name='unit_price']", "50")

        # Click Add
        page.click(".add-item-form button[type='submit']")
        page.wait_for_load_state("networkidle")

        # Verify item appears in the table
        items_table = page.locator(".items-teal tbody tr")
        assert items_table.count() >= 1, "Should have at least one line item"
        print(f"  [OK] Line item added")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_04_item_added.png"))

    # -- 5. Submit again -- should succeed now --
    def test_06_submit_order(self, browser_ctx, shared):
        """Submit the order -- should succeed with all fields filled."""
        page = browser_ctx

        # Scroll back up to action buttons
        page.locator(".order-actions").scroll_into_view_if_needed()

        submit_btn = page.locator("button:has-text('Submit')")
        expect(submit_btn).to_be_visible()
        submit_btn.click()
        page.wait_for_load_state("networkidle")

        # Status should now be SUBMITTED
        expect(page.locator(".status-large")).to_contain_text("SUBMITTED")

        # No QR code should appear yet
        qr = page.locator(".qr-section")
        expect(qr).to_have_count(0)

        print(f"  [OK] Order submitted -- status is SUBMITTED")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_05_submitted.png"))

    # -- 6. Finance: Price Agreed --
    def test_07_finance_price_agreed(self, browser_ctx, shared):
        """Login as do.finance and set Price Agreed."""
        page = browser_ctx

        # Logout and login as finance
        login(page, FINANCE_USER, FINANCE_PASS, "Finance")

        # Navigate to the order
        page.goto(f"{BASE_URL}/delivery-orders/{shared['order_id']}")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".status-large")).to_contain_text("SUBMITTED")

        # Click Price Agreed
        pa_btn = page.locator("button:has-text('Price Agreed')")
        expect(pa_btn).to_be_visible()
        pa_btn.click()
        page.wait_for_load_state("networkidle")

        expect(page.locator(".status-large")).to_contain_text("PRICE AGREED")

        # No QR code should appear yet (only after CONFIRMED)
        qr = page.locator(".qr-section")
        expect(qr).to_have_count(0)

        print(f"  [OK] Finance set Price Agreed -- no QR yet")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_06_price_agreed.png"))

    # -- 7. Logistics: Confirm --
    def test_08_logistics_confirm(self, browser_ctx, shared):
        """Login as do.logistics and confirm the order."""
        page = browser_ctx

        # Logout and login as logistics
        login(page, LOGISTICS_USER, LOGISTICS_PASS, "Logistics")

        # Navigate to the order
        page.goto(f"{BASE_URL}/delivery-orders/{shared['order_id']}")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".status-large")).to_contain_text("PRICE AGREED")

        # Click Confirm
        confirm_btn = page.locator("button:has-text('Confirm')")
        expect(confirm_btn).to_be_visible()
        confirm_btn.click()
        page.wait_for_load_state("networkidle")

        expect(page.locator(".status-large")).to_contain_text("CONFIRMED")
        print(f"  [OK] Logistics confirmed the order")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_07_confirmed.png"))

    # -- 8. QR code visible after confirmation --
    def test_09_qr_code_appears(self, browser_ctx, shared):
        """QR code should now be visible on the confirmed order."""
        page = browser_ctx

        qr = page.locator(".qr-section")
        expect(qr).to_be_visible()

        qr_img = page.locator(".qr-section img")
        expect(qr_img).to_be_visible()

        # Verify QR code route returns a valid image
        src = qr_img.get_attribute("src")
        assert "qr" in src.lower(), \
            f"QR image src should reference QR route: {src}"

        print(f"  [OK] QR code is visible after confirmation")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_08_qr_visible.png"))

    # -- 9. Print view also shows QR --
    def test_10_print_view_with_qr(self, browser_ctx, shared):
        """Print view should also show the QR code for confirmed order."""
        page = browser_ctx

        # Open print view in same tab for testing
        page.goto(f"{BASE_URL}/delivery-orders/{shared['order_id']}/print")
        page.wait_for_load_state("networkidle")

        qr = page.locator(".qr-section")
        expect(qr).to_be_visible()

        print(f"  [OK] Print view shows QR code")
        page.screenshot(path=os.path.join(SCREENSHOTS, "wf_09_print_qr.png"))

    # -- 10. Summary --
    def test_11_workflow_complete(self, browser_ctx, shared):
        """Workflow test complete -- print summary."""
        print(f"\n{'='*60}")
        print(f"  WORKFLOW TEST COMPLETE")
        print(f"  Order: {shared.get('po_number', 'N/A')}")
        print(f"  ID:    {shared.get('order_id', 'N/A')}")
        print(f"  Flow:  DRAFT -> SUBMITTED -> PRICE AGREED -> CONFIRMED")
        print(f"  QR:    Visible only after CONFIRMED [OK]")
        print(f"  Validation: Blank submit blocked [OK]")
        print(f"{'='*60}")
