"""
End-to-end Playwright test for the Web Application hub and Delivery Order module.

Runs as a SINGLE browser session — login once, then navigate through every page
like a real user would, without closing the browser between tests.

Usage:
    cd app
    set TEST_USERNAME=sathish.narasimhan
    set TEST_PASSWORD=Malt*2025
    python -m pytest tests/test_webapp_session.py -v --headed     (visible)
    python -m pytest tests/test_webapp_session.py -v              (headless)
"""

import os
import re
import pytest
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, expect

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:5080")


# ── Fixtures: single browser + single context for the whole module ──

@pytest.fixture(scope="module")
def browser():
    """Launch ONE browser for all tests in this module."""
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not os.environ.get("HEADED"))
        yield b
        b.close()


@pytest.fixture(scope="module")
def context(browser: Browser):
    """Create ONE browser context (= one set of cookies) for all tests."""
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    yield ctx
    ctx.close()


@pytest.fixture(scope="module")
def page(context: BrowserContext):
    """Create ONE page (tab) used throughout the whole session."""
    p = context.new_page()
    yield p
    p.close()


# ── Helper ──────────────────────────────────────────────────────

def _creds() -> tuple[str, str]:
    u = os.environ.get("TEST_USERNAME")
    p = os.environ.get("TEST_PASSWORD")
    if not u or not p:
        pytest.skip("TEST_USERNAME and TEST_PASSWORD env vars required")
    return u, p


# ═══════════════════════════════════════════════════════════════
#  Tests run IN ORDER (same page, same session)
# ═══════════════════════════════════════════════════════════════

class TestSingleSession:
    """All tests share the same browser page — the session (cookies)
    survive across every test method, exactly like a real user."""

    # ── 1. Login ────────────────────────────────────────────────
    def test_01_login(self, page: Page):
        """Login once; all subsequent tests reuse this session."""
        user, pwd = _creds()
        page.goto(f"{BASE_URL}/auth/login")
        expect(page).to_have_title(re.compile(r"Login", re.IGNORECASE))

        page.fill("#username", user)
        page.fill("#password", pwd)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # Should land on dashboard (or ISP page)
        assert "/auth/login" not in page.url, "Still on login page after submit"

    # ── 2. Dashboard loads ──────────────────────────────────────
    def test_02_dashboard_loads(self, page: Page):
        """Dashboard page should render after login."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        # Should NOT redirect to login
        assert "/auth/login" not in page.url
        # Sidebar should be visible
        expect(page.locator(".sidebar")).to_be_visible()

    # ── 3. Sidebar has Web Application link ─────────────────────
    def test_03_sidebar_web_application_link(self, page: Page):
        """Sidebar should contain 'Web Application' navigation item."""
        link = page.locator("text=Web Application").first
        expect(link).to_be_visible()

    # ── 4. Navigate to Web Application hub ──────────────────────
    def test_04_web_application_hub_loads(self, page: Page):
        """Click sidebar 'Web Application' → hub grid should appear."""
        page.click("text=Web Application")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title(re.compile(r"Web Application", re.IGNORECASE))
        expect(page.locator("h1")).to_contain_text("Web Application")

    # ── 5. Module grid has 8 cards ──────────────────────────────
    def test_05_module_grid_cards(self, page: Page):
        """The hub should show 8 module cards."""
        cards = page.locator(".module-card")
        expect(cards).to_have_count(8)

    # ── 6. Module card labels ───────────────────────────────────
    def test_06_module_card_labels(self, page: Page):
        """Each expected module label should appear on the grid."""
        for label in ["Quality", "R. M. Store", "Production", "Finance",
                       "Technical", "Sales", "News", "IT"]:
            expect(page.locator(f"text={label}").first).to_be_visible()

    # ── 7. Sales card has Delivery Order link ───────────────────
    def test_07_sales_delivery_order_link(self, page: Page):
        """Sales card should have a 'Delivery Order' link."""
        link = page.locator(".module-link", has_text="Delivery Order")
        expect(link).to_be_visible()
        expect(link).to_have_attribute("href", "/delivery-orders")

    # ── 8. Click sub-module → Coming Soon page ──────────────────
    def test_08_coming_soon_page(self, page: Page):
        """Click a non-implemented sub-module → Coming Soon page."""
        page.goto(f"{BASE_URL}/web-application/")
        page.wait_for_load_state("networkidle")

        # Use exact role match to avoid matching 'QA Inspection'
        page.get_by_role("link", name="Inspection", exact=True).click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1")).to_contain_text("Inspection")
        expect(page.locator("text=under development")).to_be_visible()

    # ── 9. Coming Soon → Back to Web Application ────────────────
    def test_09_coming_soon_back_button(self, page: Page):
        """The 'Back to Web Application' button should navigate back."""
        # Ensure we're on a Coming Soon page first
        if "under development" not in (page.content() or ""):
            page.goto(f"{BASE_URL}/web-application/module/facility")
            page.wait_for_load_state("networkidle")

        page.locator("text=Back to Web Application").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_title(re.compile(r"Web Application", re.IGNORECASE))

    # ── 10. Navigate to Delivery Order Dashboard ────────────────
    def test_10_delivery_order_dashboard(self, page: Page):
        """Click 'Delivery Order' link → KPI dashboard."""
        page.locator(".module-link", has_text="Delivery Order").click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1")).to_contain_text("Delivery Orders")
        expect(page).to_have_title(re.compile(r"Delivery Orders", re.IGNORECASE))

    # ── 11. KPI bubbles visible ─────────────────────────────────
    def test_11_kpi_bubbles(self, page: Page):
        """Dashboard should show 6 KPI bubbles."""
        bubbles = page.locator(".kpi-bubble")
        expect(bubbles).to_have_count(6)

    # ── 12. KPI labels ──────────────────────────────────────────
    def test_12_kpi_labels(self, page: Page):
        """Each KPI bubble should have the correct label."""
        for label in ["Total", "Drafts", "Submitted", "Need Attach",
                       "Price Agreed", "Confirmed"]:
            expect(page.locator(f".kpi-bubble__label:has-text('{label}')")).to_be_visible()

    # ── 13. KPI values are numbers ──────────────────────────────
    def test_13_kpi_values_numeric(self, page: Page):
        """KPI circle values should be numeric."""
        circles = page.locator(".kpi-bubble__circle").all()
        for circle in circles:
            val = circle.inner_text().strip()
            assert val.isdigit(), f"Expected numeric KPI value, got '{val}'"

    # ── 14. Dashboard has action buttons ────────────────────────
    def test_14_dashboard_action_buttons(self, page: Page):
        """Dashboard should have 'New Order' and 'View Orders' buttons."""
        expect(page.locator("text=New Order").first).to_be_visible()
        expect(page.locator("text=View Orders").first).to_be_visible()

    # ── 15. Overview section ────────────────────────────────────
    def test_15_dashboard_overview(self, page: Page):
        """Dashboard should show Rejected and Cancelled stats."""
        expect(page.locator("text=Rejected").first).to_be_visible()
        expect(page.locator("text=Cancelled").first).to_be_visible()

    # ── 16. Navigate to Orders List ─────────────────────────────
    def test_16_orders_list_page(self, page: Page):
        """Click 'View Orders' → orders table appears."""
        page.locator("text=View Orders").first.click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1")).to_contain_text("Orders")
        expect(page).to_have_title(re.compile(r"Orders", re.IGNORECASE))

    # ── 17. Orders table has correct columns ────────────────────
    def test_17_orders_table_columns(self, page: Page):
        """Table headers should match expected columns."""
        for col in ["Order Date", "Order No", "On Behalf Of", "Loading Date",
                     "Bill To", "Created by", "Items", "Status"]:
            expect(page.locator(f"th:has-text('{col}')")).to_be_visible()

    # ── 18. Orders table has data rows ──────────────────────────
    def test_18_orders_table_has_rows(self, page: Page):
        """Table should have at least one data row (AWTFZC orders exist)."""
        rows = page.locator("#ordersTable tbody tr")
        assert rows.count() >= 1, "Expected at least 1 order row"

    # ── 19. Status filter dropdown ──────────────────────────────
    def test_19_status_filter_dropdown(self, page: Page):
        """Status filter should be present with options."""
        select = page.locator("select[name='status']")
        expect(select).to_be_visible()
        options = select.locator("option").all()
        assert len(options) >= 2, "Expected multiple status options"

    # ── 20. Search box ──────────────────────────────────────────
    def test_20_search_box(self, page: Page):
        """Search input should be present."""
        search = page.locator("input[name='search']")
        expect(search).to_be_visible()

    # ── 21. Order count badge ───────────────────────────────────
    def test_21_order_count_badge(self, page: Page):
        """Order count badge should show a number."""
        badge = page.locator(".order-count-badge")
        expect(badge).to_be_visible()
        val = badge.inner_text().strip()
        assert val.isdigit(), f"Expected numeric count, got '{val}'"

    # ── 22. Status pills visible ────────────────────────────────
    def test_22_status_pills(self, page: Page):
        """At least one status pill should be visible in the table."""
        pills = page.locator(".status-pill")
        assert pills.count() >= 1, "Expected at least 1 status pill"

    # ── 23. Click AWTFZC order row → detail page ────────────────
    def test_23_click_order_row(self, page: Page):
        """Click an order row → navigate to detail page."""
        first_row = page.locator("#ordersTable tbody tr.clickable-row").first
        # Grab the order number text before clicking
        order_no = first_row.locator("td:nth-child(2)").inner_text().strip()
        first_row.click()
        page.wait_for_load_state("networkidle")

        # Should be on detail page
        assert "/delivery-orders/" in page.url
        expect(page.locator("h1")).to_contain_text("AWTFZC")

    # ── 24. Detail page has Order Information section ────────────
    def test_24_detail_order_info(self, page: Page):
        """Detail page should show Order Information fields."""
        expect(page.locator("text=Order Information").first).to_be_visible()
        for field in ["PO Number", "Order Date", "Loading Date", "Delivery Terms"]:
            expect(page.locator(f"text={field}").first).to_be_visible()

    # ── 25. Detail page has Shipping section ─────────────────────
    def test_25_detail_shipping(self, page: Page):
        """Detail page should show Shipping section."""
        expect(page.locator("text=Shipping").first).to_be_visible()
        for field in ["Bill To", "Ship To", "Point of Exit", "Final Destination"]:
            expect(page.locator(f"text={field}").first).to_be_visible()

    # ── 26. Detail page has Audit section ────────────────────────
    def test_26_detail_audit(self, page: Page):
        """Detail page should show audit info with Created By/On."""
        expect(page.locator(".audit-row").first).to_be_visible()
        expect(page.locator("text=Created By").first).to_be_visible()
        expect(page.locator("text=Created On").first).to_be_visible()

    # ── 27. Detail page has Line Items ───────────────────────────
    def test_27_detail_line_items(self, page: Page):
        """Detail page should show items table with teal headers."""
        expect(page.locator(".items-teal").first).to_be_visible()
        # Check teal table headers
        for col in ["Item ID", "Item Description", "UOM", "Quantity"]:
            expect(page.locator(f"th:has-text('{col}')")).to_be_visible()

    # ── 28. Detail page shows status badge ───────────────────────
    def test_28_detail_status_badge(self, page: Page):
        """Detail page should show a large status badge."""
        status = page.locator(".status-large")
        expect(status).to_be_visible()
        val = status.inner_text().strip()
        assert val, "Status badge should not be empty"

    # ── 29. Detail breadcrumb ────────────────────────────────────
    def test_29_detail_breadcrumb(self, page: Page):
        """Breadcrumb should include Dashboard > Web Application > Delivery Order > Orders."""
        breadcrumb = page.locator(".page-header__breadcrumb")
        for crumb in ["Dashboard", "Web Application", "Delivery Order", "Orders"]:
            expect(breadcrumb.locator(f"text={crumb}").first).to_be_visible()

    # ── 30. Detail Back button → Orders list ─────────────────────
    def test_30_detail_back_button(self, page: Page):
        """Click 'Back' button → return to orders list."""
        page.locator("a.btn:has-text('Back')").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Orders")

    # ── 31. Navigate to Create Order page ────────────────────────
    def test_31_create_order_page(self, page: Page):
        """Click 'New Order' → create form appears."""
        page.locator("text=New Order").first.click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1")).to_contain_text("Create New Order")
        expect(page).to_have_title(re.compile(r"Create", re.IGNORECASE))

    # ── 32. Create form Section 1 fields ─────────────────────────
    def test_32_create_form_section1(self, page: Page):
        """Create form should have Section 1 — Order Details fields."""
        expect(page.locator("text=Order Details").first).to_be_visible()
        for name in ["po_date", "on_behalf_of", "loading_date",
                      "delivery_terms", "payment_terms", "transportation_mode"]:
            field = page.locator(f"[name='{name}']")
            expect(field).to_be_visible()

    # ── 33. Create form Section 2 fields ─────────────────────────
    def test_33_create_form_section2(self, page: Page):
        """Create form should have Section 2 — Shipping fields."""
        expect(page.locator("text=Shipping").first).to_be_visible()
        for name in ["bill_to", "ship_to", "point_of_exit", "currency"]:
            field = page.locator(f"[name='{name}']")
            expect(field).to_be_visible()

    # ── 34. Create form has dropdowns with options ───────────────
    def test_34_create_form_dropdowns(self, page: Page):
        """Delivery Terms and Transportation Mode should have options."""
        dt_select = page.locator("select[name='delivery_terms']")
        options = dt_select.locator("option").all()
        assert len(options) >= 2, "Delivery Terms dropdown should have options"

        tm_select = page.locator("select[name='transportation_mode']")
        options = tm_select.locator("option").all()
        assert len(options) >= 2, "Transportation Mode dropdown should have options"

    # ── 35. Create form Bill To dropdown loaded from DB ──────────
    def test_35_create_form_bill_to(self, page: Page):
        """Bill To dropdown should have at least one option from DB."""
        select = page.locator("select[name='bill_to']")
        options = select.locator("option").all()
        assert len(options) >= 2, "Bill To dropdown should have DB options"

    # ── 36. Create form has Last PO reference ────────────────────
    def test_36_create_form_last_po(self, page: Page):
        """Create form should show the last PO number as reference."""
        ref = page.locator(".last-po-ref")
        expect(ref).to_be_visible()
        expect(ref).to_contain_text("AWTFZC")

    # ── 37. Create form Back button ──────────────────────────────
    def test_37_create_form_back(self, page: Page):
        """Back button should navigate to dashboard."""
        page.locator("a.btn:has-text('Back')").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Delivery Orders")

    # ── 38. Filter orders by status ──────────────────────────────
    def test_38_filter_by_confirmed(self, page: Page):
        """Filter orders by 'CONFIRMED' status."""
        page.goto(f"{BASE_URL}/delivery-orders/orders?status=CONFIRMED")
        page.wait_for_load_state("networkidle")

        # All visible status pills should be CONFIRMED
        pills = page.locator(".status-pill").all()
        if pills:
            for pill in pills:
                assert pill.inner_text().strip() == "CONFIRMED"

    # ── 39. Search orders ────────────────────────────────────────
    def test_39_search_orders(self, page: Page):
        """Type a search term in the search box and submit."""
        page.goto(f"{BASE_URL}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")

        # Verify the search form works (just submit with empty to confirm)
        search_input = page.locator("input[name='search']")
        expect(search_input).to_be_visible()
        search_input.fill("test")
        page.locator("button:has-text('Search')").click()
        page.wait_for_load_state("networkidle")

        # Should still be on orders page (not error)
        expect(page.locator("h1")).to_contain_text("Orders")

    # ── 40. Direct URL to order detail ───────────────────────────
    def test_40_direct_url_order_detail(self, page: Page):
        """Load order 6002 directly by URL."""
        page.goto(f"{BASE_URL}/delivery-orders/6002")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1")).to_contain_text("AWTFZC")
        expect(page.locator("text=Order Information").first).to_be_visible()

    # ── 41. Multiple sub-module Coming Soon pages ────────────────
    def test_41_multiple_coming_soon(self, page: Page):
        """Several sub-modules should show Coming Soon pages."""
        for slug, expected in [
            ("customers", "Customers"),
            ("facility", "Facility"),
            ("gulf-news", "Gulf News"),
            ("forecast", "Forecast"),
        ]:
            page.goto(f"{BASE_URL}/web-application/module/{slug}")
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1")).to_contain_text(expected)
            expect(page.locator("text=under development")).to_be_visible()

    # ── 42. Web Application breadcrumb on Coming Soon ────────────
    def test_42_coming_soon_breadcrumb(self, page: Page):
        """Coming Soon pages should have breadcrumb with Web Application link."""
        page.goto(f"{BASE_URL}/web-application/module/facility")
        page.wait_for_load_state("networkidle")

        breadcrumb = page.locator(".page-header__breadcrumb")
        expect(breadcrumb.locator("text=Dashboard")).to_be_visible()
        expect(breadcrumb.locator("text=Web Application")).to_be_visible()

    # ── 43. Dashboard breadcrumb ─────────────────────────────────
    def test_43_do_dashboard_breadcrumb(self, page: Page):
        """DO Dashboard should have breadcrumb with Web Application."""
        page.goto(f"{BASE_URL}/delivery-orders/")
        page.wait_for_load_state("networkidle")

        breadcrumb = page.locator(".page-header__breadcrumb")
        expect(breadcrumb.locator("text=Web Application")).to_be_visible()

    # ── 44. Orders list breadcrumb ───────────────────────────────
    def test_44_orders_list_breadcrumb(self, page: Page):
        """Orders list should have breadcrumb chain."""
        page.goto(f"{BASE_URL}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")

        breadcrumb = page.locator(".page-header__breadcrumb")
        for crumb in ["Dashboard", "Web Application", "Delivery Order", "Orders"]:
            expect(breadcrumb.locator(f"text={crumb}").first).to_be_visible()

    # ── 45. Pagination visible when many orders ──────────────────
    def test_45_pagination(self, page: Page):
        """Orders list should show pagination if total > per_page."""
        page.goto(f"{BASE_URL}/delivery-orders/orders")
        page.wait_for_load_state("networkidle")

        badge = page.locator(".order-count-badge").inner_text().strip()
        if int(badge) > 20:
            pagination = page.locator(".pagination")
            expect(pagination).to_be_visible()

    # ── 46. Sidebar Delivery Orders link ─────────────────────────
    def test_46_sidebar_delivery_orders_link(self, page: Page):
        """Sidebar should have 'Delivery Orders' nav link."""
        link = page.locator(".sidebar a:has-text('Delivery Orders')")
        expect(link).to_be_visible()

    # ── 47. Navigate sidebar → Delivery Orders ───────────────────
    def test_47_sidebar_navigate_delivery_orders(self, page: Page):
        """Click sidebar 'Delivery Orders' → navigate to DO dashboard."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        page.locator(".sidebar a:has-text('Delivery Orders')").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Delivery Orders")

    # ── 48. Session persists across navigation ───────────────────
    def test_48_session_persists(self, page: Page):
        """Session should persist — no login redirect after 48 tests."""
        for url in [f"{BASE_URL}/", f"{BASE_URL}/web-application/",
                    f"{BASE_URL}/delivery-orders/",
                    f"{BASE_URL}/delivery-orders/orders"]:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            assert "/auth/login" not in page.url, f"Session expired on {url}"

    # ── 49. Full user journey: Hub → Sales → DO → List → Detail ─
    def test_49_full_user_journey(self, page: Page):
        """Simulate a complete user journey through the application."""
        # Start at Web Application hub
        page.goto(f"{BASE_URL}/web-application/")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Web Application")

        # Click Delivery Order in Sales card
        page.locator(".module-link", has_text="Delivery Order").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Delivery Orders")

        # Click View Orders
        page.locator("text=View Orders").first.click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Orders")

        # Click first order row
        first_row = page.locator("#ordersTable tbody tr.clickable-row").first
        if first_row.count():
            first_row.click()
            page.wait_for_load_state("networkidle")
            assert "/delivery-orders/" in page.url

            # Go back via breadcrumb
            page.locator(".page-header__breadcrumb a:has-text('Orders')").click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1")).to_contain_text("Orders")

    # ── 50. No console errors on key pages ───────────────────────
    def test_50_no_console_errors(self, page: Page):
        """Key pages should not produce JavaScript console errors."""
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        for url in [f"{BASE_URL}/web-application/",
                    f"{BASE_URL}/delivery-orders/",
                    f"{BASE_URL}/delivery-orders/orders"]:
            page.goto(url)
            page.wait_for_load_state("networkidle")

        # Filter out benign errors (favicon, etc.)
        real_errors = [e for e in errors if "favicon" not in e.lower()]
        assert len(real_errors) == 0, f"Console errors found: {real_errors}"
