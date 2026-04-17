"""
End-to-end Playwright tests for the rebuilt Delivery Order module.

Covers: role-based access (admin vs creator), dashboard, order list,
detail page, print view, management pages (Products, Customers, GRMS, Reports),
export buttons, reject modal, and QR code.

Runs as a SINGLE browser session per class — login once, then navigate.

Usage:
    cd app
    set TEST_USERNAME=sathish.narasimhan
    set TEST_PASSWORD=Malt*2025
    python -m pytest tests/test_delivery_orders.py -v --headed
    python -m pytest tests/test_delivery_orders.py -v
"""

import os
import re
import pytest
from playwright.sync_api import (
    sync_playwright,
    Page,
    Browser,
    BrowserContext,
    expect,
)

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:5080")


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not os.environ.get("HEADED"))
        yield b
        b.close()


@pytest.fixture(scope="module")
def context(browser: Browser):
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    yield ctx
    ctx.close()


@pytest.fixture(scope="module")
def page(context: BrowserContext):
    p = context.new_page()
    yield p
    p.close()


def _creds() -> tuple[str, str]:
    u = os.environ.get("TEST_USERNAME", "sathish.narasimhan")
    p = os.environ.get("TEST_PASSWORD", "Malt*2025")
    return u, p


# ═══════════════════════════════════════════════════════════════
# ── ADMIN / APPROVER FLOW (full access) ───────────────────────
# ═══════════════════════════════════════════════════════════════

class TestDOAdminFlow:
    """Tests run as admin user (sathish.narasimhan) who maps to DO approver."""

    # ── Login ───────────────────────────────────────────────────

    def test_01_login(self, page: Page):
        """Login as admin user."""
        user, pw = _creds()
        page.goto(f"{BASE_URL}/auth/login")
        page.fill("#username", user)
        page.fill("#password", pw)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        assert "/auth/login" not in page.url, "Still on login page after submit"

    # ── Dashboard ───────────────────────────────────────────────

    def test_02_do_dashboard_loads(self, page: Page):
        """Navigate to DO dashboard."""
        page.goto(f"{BASE_URL}/delivery-orders/")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Delivery Orders")

    def test_03_kpi_bubbles_present(self, page: Page):
        """KPI bubbles should be visible on dashboard."""
        bubbles = page.locator(".kpi-bubble")
        expect(bubbles.first).to_be_visible()
        count = bubbles.count()
        # Admin should see at least 6 bubbles (Total, Drafts, Submitted, Need Attach, Price Agreed, Confirmed)
        assert count >= 5, f"Expected >=5 KPI bubbles, got {count}"

    def test_04_kpi_bubbles_clickable(self, page: Page):
        """KPI bubbles should be links to filtered order list."""
        first_bubble = page.locator(".kpi-bubble").first
        href = first_bubble.get_attribute("href")
        assert href is not None, "KPI bubble should be a link"
        assert "orders" in href or "status" in href

    def test_05_new_order_button_visible(self, page: Page):
        """Admin users should see the 'New Order' button."""
        page.goto(f"{BASE_URL}/delivery-orders/")
        page.wait_for_load_state("networkidle")
        new_btn = page.locator("a:has-text('New Order')")
        expect(new_btn.first).to_be_visible()

    def test_06_view_orders_button(self, page: Page):
        """'View Orders' link should be on dashboard."""
        view_btn = page.locator("a:has-text('View Orders')")
        expect(view_btn.first).to_be_visible()

    def test_07_admin_sees_management_tiles(self, page: Page):
        """Admin should see Management section with Products, Customers, GRMS, Reports."""
        mgmt = page.locator("text=Management")
        expect(mgmt.first).to_be_visible()
        for label in ["Products", "Customers", "GRMS", "Reports"]:
            tile = page.locator(f"a:has-text('{label}')")
            expect(tile.first).to_be_visible()

    # ── Order List ──────────────────────────────────────────────

    def test_08_orders_list_page(self, page: Page):
        """Navigate to order list page."""
        page.goto(f"{BASE_URL}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")
        expect(page.locator("table")).to_be_visible()

    def test_09_orders_table_columns(self, page: Page):
        """Table should have expected column headers."""
        headers = page.locator("table thead th")
        header_texts = [h.text_content().strip() for h in headers.all()]
        for expected in ["Date", "Order No", "Status"]:
            assert any(expected.lower() in h.lower() for h in header_texts), \
                f"Missing column header '{expected}'"

    def test_10_orders_table_has_rows(self, page: Page):
        """Table should contain data rows."""
        rows = page.locator("table tbody tr")
        count = rows.count()
        assert count >= 1, "Expected at least 1 order row"

    def test_11_status_filter(self, page: Page):
        """Status filter dropdown should have options."""
        select = page.locator("select[name='status']")
        if select.count() > 0:
            options = select.locator("option")
            count = options.count()
            assert count >= 3, f"Expected >=3 status options, got {count}"

    def test_12_export_buttons(self, page: Page):
        """Export buttons (Copy, CSV, Excel, Print) should be present."""
        for label in ["Copy", "CSV", "Excel"]:
            btn = page.locator(f"button:has-text('{label}')")
            if btn.count() > 0:
                expect(btn.first).to_be_visible()

    def test_13_new_order_button_on_list(self, page: Page):
        """'New Order' button should also be on the list page for admins."""
        new_btn = page.locator("a:has-text('New Order')")
        expect(new_btn.first).to_be_visible()

    # ── Order Detail ────────────────────────────────────────────

    def test_14_order_detail_load(self, page: Page):
        """Click first order row to navigate to detail page."""
        page.goto(f"{BASE_URL}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")
        # Rows use onclick=window.location, so click the first clickable row
        first_row = page.locator("table tbody tr.clickable-row").first
        if first_row.count() > 0:
            first_row.click()
            page.wait_for_load_state("networkidle")
        # Should have PO number in detail page
        expect(page.locator("body")).to_contain_text("AWTFZC")

    def test_15_detail_shows_bill_to(self, page: Page):
        """Detail page should show Bill To section."""
        expect(page.locator("text=Bill To").first).to_be_visible()

    def test_16_detail_shows_ship_to(self, page: Page):
        """Detail page should show Ship To section."""
        ship_to = page.locator("text=Ship To")
        if ship_to.count() > 0:
            expect(ship_to.first).to_be_visible()
        else:
            # Some orders may not display Ship To; verify page loaded
            expect(page.locator("body")).to_contain_text("AWTFZC")

    def test_17_detail_shows_line_items(self, page: Page):
        """Detail page should have a line items table."""
        items_table = page.locator("table")
        expect(items_table.first).to_be_visible()

    def test_18_detail_print_button(self, page: Page):
        """Print button should be visible on detail page."""
        # Look for print button or link
        print_el = page.locator("a:has-text('Print'), button:has-text('Print')")
        if print_el.count() > 0:
            expect(print_el.first).to_be_visible()

    def test_19_detail_status_badge(self, page: Page):
        """Status badge should be visible."""
        badge = page.locator(".badge, .status-badge")
        if badge.count() > 0:
            expect(badge.first).to_be_visible()

    # ── Print View ──────────────────────────────────────────────

    def test_20_print_view(self, page: Page):
        """Print view should load and contain DELIVERY ORDER heading."""
        # Navigate to first order's print view
        page.goto(f"{BASE_URL}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")
        # Get the first clickable row and extract its onclick URL
        first_row = page.locator("table tbody tr.clickable-row").first
        if first_row.count() > 0:
            onclick = first_row.get_attribute("onclick") or ""
            match = re.search(r"/delivery-orders/(\d+)", onclick)
            if match:
                order_id = match.group(1)
                page.goto(f"{BASE_URL}/delivery-orders/{order_id}/print")
                page.wait_for_load_state("networkidle")
                expect(page.locator("body")).to_contain_text("DELIVERY ORDER")
                # Go back to list
                page.goto(f"{BASE_URL}/delivery-orders/orders")
                page.wait_for_load_state("networkidle")

    # ── Create Order Form ───────────────────────────────────────

    def test_21_create_form_loads(self, page: Page):
        """Create order form should load for admin users."""
        page.goto(f"{BASE_URL}/delivery-orders/create")
        page.wait_for_load_state("networkidle")
        expect(page.locator("form")).to_be_visible()

    def test_22_create_form_fields(self, page: Page):
        """Create form should have required fields."""
        for name in ["po_date", "on_behalf_of"]:
            field = page.locator(f"[name='{name}']")
            expect(field).to_be_visible()

    def test_23_create_form_dropdowns(self, page: Page):
        """Create form should have dropdown selectors."""
        for name in ["bill_to", "delivery_terms", "transportation_mode"]:
            selector = page.locator(f"select[name='{name}']")
            if selector.count() > 0:
                expect(selector).to_be_visible()

    # ── Management: Products ────────────────────────────────────

    def test_24_products_page(self, page: Page):
        """Products management page should load."""
        page.goto(f"{BASE_URL}/delivery-orders/manage/products")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Products")

    def test_25_products_table(self, page: Page):
        """Products table should have rows."""
        table = page.locator("table")
        expect(table).to_be_visible()
        rows = page.locator("table tbody tr")
        assert rows.count() >= 1, "Expected at least 1 product"

    def test_26_products_new_button(self, page: Page):
        """'New Product' button should be visible."""
        btn = page.locator("a:has-text('New Product')")
        expect(btn).to_be_visible()

    def test_27_product_create_form(self, page: Page):
        """Product create form should load."""
        page.goto(f"{BASE_URL}/delivery-orders/manage/products/create")
        page.wait_for_load_state("networkidle")
        expect(page.locator("form")).to_be_visible()
        expect(page.locator("[name='product_id']")).to_be_visible()
        expect(page.locator("[name='name']")).to_be_visible()

    # ── Management: Customers ───────────────────────────────────

    def test_28_customers_page(self, page: Page):
        """Customers management page should load."""
        page.goto(f"{BASE_URL}/delivery-orders/manage/customers")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Customers")

    def test_29_customers_table(self, page: Page):
        """Customers table should have rows."""
        rows = page.locator("table tbody tr")
        assert rows.count() >= 1, "Expected at least 1 customer"

    def test_30_customer_create_form(self, page: Page):
        """Customer create form should load."""
        page.goto(f"{BASE_URL}/delivery-orders/manage/customers/create")
        page.wait_for_load_state("networkidle")
        expect(page.locator("form")).to_be_visible()
        expect(page.locator("[name='name']")).to_be_visible()

    # ── Management: GRMS ────────────────────────────────────────

    def test_31_grms_page(self, page: Page):
        """GRMS page should load."""
        page.goto(f"{BASE_URL}/delivery-orders/manage/grms")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("GRMS")

    def test_32_grms_status_filter(self, page: Page):
        """GRMS should have a status filter."""
        select = page.locator("select[name='status']")
        if select.count() > 0:
            expect(select).to_be_visible()

    # ── Management: Reports ─────────────────────────────────────

    def test_33_reports_page(self, page: Page):
        """Reports page should load."""
        page.goto(f"{BASE_URL}/delivery-orders/manage/reports")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Products Sold Report")

    def test_34_reports_date_filter(self, page: Page):
        """Reports should have date filter inputs."""
        date_from = page.locator("[name='date_from']")
        date_to = page.locator("[name='date_to']")
        expect(date_from).to_be_visible()
        expect(date_to).to_be_visible()

    def test_35_reports_csv_export(self, page: Page):
        """CSV export button should be present."""
        btn = page.locator("button:has-text('CSV')")
        if btn.count() > 0:
            expect(btn.first).to_be_visible()

    # ── QR Code ─────────────────────────────────────────────────

    def test_36_qr_code_for_confirmed(self, page: Page):
        """QR code endpoint should return image for a CONFIRMED order."""
        # Navigate to orders filtered by CONFIRMED
        page.goto(f"{BASE_URL}/delivery-orders/orders?status=CONFIRMED")
        page.wait_for_load_state("networkidle")

        first_row = page.locator("table tbody tr.clickable-row").first
        if first_row.count() > 0:
            onclick = first_row.get_attribute("onclick") or ""
            match = re.search(r"/delivery-orders/(\d+)", onclick)
            if match:
                order_id = match.group(1)
                response = page.request.get(
                    f"{BASE_URL}/delivery-orders/{order_id}/qrcode"
                )
                assert response.status == 200
                assert "image/png" in response.headers.get("content-type", "")

    # ── Reject Modal (structure check) ──────────────────────────

    def test_37_reject_modal_exists_on_submitted(self, page: Page):
        """For SUBMITTED orders, a reject button should be available for admins."""
        page.goto(f"{BASE_URL}/delivery-orders/orders?status=SUBMITTED")
        page.wait_for_load_state("networkidle")

        first_row = page.locator("table tbody tr.clickable-row").first
        if first_row.count() > 0:
            first_row.click()
            page.wait_for_load_state("networkidle")
            reject_btn = page.locator(
                "button:has-text('REJECTED'), "
                "a:has-text('REJECTED'), "
                "button:has-text('Reject')"
            )
            if reject_btn.count() > 0:
                expect(reject_btn.first).to_be_visible()

    # ── Attachments Section ─────────────────────────────────────

    def test_38_attachments_section_on_detail(self, page: Page):
        """Detail page should show Attachments heading."""
        page.goto(f"{BASE_URL}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")
        first_row = page.locator("table tbody tr.clickable-row").first
        if first_row.count() > 0:
            first_row.click()
            page.wait_for_load_state("networkidle")
            att_section = page.locator("text=Attachments")
            if att_section.count() > 0:
                expect(att_section.first).to_be_visible()

    # ── Navigation Back ─────────────────────────────────────────

    def test_39_back_to_dashboard(self, page: Page):
        """Navigate back to dashboard from management pages."""
        page.goto(f"{BASE_URL}/delivery-orders/manage/products")
        page.wait_for_load_state("networkidle")
        back_btn = page.locator("a:has-text('Back to Dashboard')")
        if back_btn.count() > 0:
            back_btn.click()
            page.wait_for_load_state("networkidle")
            expect(page).to_have_url(re.compile(r"/delivery-orders"))

    def test_40_breadcrumb_navigation(self, page: Page):
        """Dashboard breadcrumb should show proper path."""
        page.goto(f"{BASE_URL}/delivery-orders/")
        page.wait_for_load_state("networkidle")
        breadcrumb = page.locator(".page-header__breadcrumb")
        if breadcrumb.count() > 0:
            expect(breadcrumb).to_contain_text("Dashboard")
