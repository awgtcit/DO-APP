"""
End-to-end Playwright tests for the new modules:
  - Documents (DMS)
  - Announcements
  - Facility
  - Employee Forum
  - ISP Status Admin

Runs as a SINGLE browser session — login once, then navigate through every
page like a real user would.

Usage:
    cd app
    set TEST_USERNAME=sathish.narasimhan
    set TEST_PASSWORD=Malt*2025
    python -m pytest tests/test_modules_session.py -v --headed   (visible)
    python -m pytest tests/test_modules_session.py -v            (headless)
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
    u = os.environ.get("TEST_USERNAME")
    p = os.environ.get("TEST_PASSWORD")
    if not u or not p:
        pytest.skip("TEST_USERNAME and TEST_PASSWORD env vars required")
    return u, p


# ═══════════════════════════════════════════════════════════════
#  Tests run IN ORDER — same page, same session
# ═══════════════════════════════════════════════════════════════

class TestModulesSession:
    """All tests share the same browser page."""

    # ── 1. Login ────────────────────────────────────────────────
    def test_01_login(self, page: Page):
        user, pwd = _creds()
        page.goto(f"{BASE_URL}/auth/login")
        page.fill("#username", user)
        page.fill("#password", pwd)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        assert "/auth/login" not in page.url, "Still on login page"

    def test_02_dashboard_loads(self, page: Page):
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        assert "/auth/login" not in page.url
        expect(page.locator(".sidebar")).to_be_visible()

    # ─────────────────────────────────────────────────────────────
    #  SIDEBAR NAVIGATION LINKS
    # ─────────────────────────────────────────────────────────────
    def test_03_sidebar_has_documents_link(self, page: Page):
        link = page.locator(".nav-item", has_text="Documents")
        expect(link).to_be_visible()

    def test_04_sidebar_has_announcements_link(self, page: Page):
        link = page.locator(".nav-item", has_text="Announcements")
        expect(link).to_be_visible()

    def test_05_sidebar_has_facility_link(self, page: Page):
        link = page.locator(".nav-item", has_text="Facility")
        expect(link).to_be_visible()

    def test_06_sidebar_has_forum_link(self, page: Page):
        link = page.locator(".nav-item", has_text="Employee Forum")
        expect(link).to_be_visible()

    def test_07_sidebar_has_isp_link(self, page: Page):
        link = page.locator(".nav-item", has_text="ISP Status")
        expect(link).to_be_visible()

    # ─────────────────────────────────────────────────────────────
    #  DOCUMENTS (DMS)
    # ─────────────────────────────────────────────────────────────
    def test_10_dms_departments_page(self, page: Page):
        """Navigate to DMS — department grid should load."""
        page.goto(f"{BASE_URL}/documents/")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Document Management")

    def test_11_dms_page_has_breadcrumb(self, page: Page):
        content = page.content()
        assert "breadcrumb" in content.lower() or "Home" in content

    def test_12_dms_page_has_stats(self, page: Page):
        """DMS should show KPI bubbles or stat cards."""
        # Either kpi-bubble or stat-card should be present
        stats = page.locator(".kpi-bubble, .stat-card")
        count = stats.count()
        assert count > 0, "Expected at least one stat element on DMS page"

    # ─────────────────────────────────────────────────────────────
    #  ANNOUNCEMENTS
    # ─────────────────────────────────────────────────────────────
    def test_20_announcements_page_loads(self, page: Page):
        """Navigate to Announcements list."""
        page.goto(f"{BASE_URL}/announcements/")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Announcements")

    def test_21_announcements_has_breadcrumb(self, page: Page):
        expect(page.locator(".breadcrumb")).to_be_visible()

    def test_22_announcements_has_search(self, page: Page):
        """Announcements page should have a search input."""
        search = page.locator("input[name='search']")
        expect(search).to_be_visible()

    def test_23_announcements_pagination_or_empty(self, page: Page):
        """Should show announcements or empty state."""
        content = page.content()
        has_table = ".data-table" in content or "card" in content
        has_empty = "empty-state" in content or "No announcements" in content
        assert has_table or has_empty, "Expected content or empty state"

    # ─────────────────────────────────────────────────────────────
    #  FACILITY
    # ─────────────────────────────────────────────────────────────
    def test_30_facility_page_loads(self, page: Page):
        """Navigate to Facility list."""
        page.goto(f"{BASE_URL}/facility/")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Facility")

    def test_31_facility_has_breadcrumb(self, page: Page):
        expect(page.locator(".breadcrumb")).to_be_visible()

    def test_32_facility_has_stats(self, page: Page):
        """Facility page should show stat cards (total/open/closed)."""
        stats = page.locator(".stat-card")
        count = stats.count()
        assert count >= 1, "Expected at least one stat card"

    def test_33_facility_has_filter(self, page: Page):
        """Should have filter chips or a filter form."""
        content = page.content()
        has_filter = "chip" in content or "filter" in content.lower() or "status" in content.lower()
        assert has_filter, "Expected filter elements on facility page"

    def test_34_facility_create_page_loads(self, page: Page):
        """Navigate to Facility create form."""
        page.goto(f"{BASE_URL}/facility/create")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("New")

    def test_35_facility_create_has_form(self, page: Page):
        """Create page should have subject and summary fields."""
        expect(page.locator("input[name='subject']")).to_be_visible()
        expect(page.locator("textarea[name='summary'], [name='summary']")).to_be_visible()

    # ─────────────────────────────────────────────────────────────
    #  EMPLOYEE FORUM
    # ─────────────────────────────────────────────────────────────
    def test_40_forum_page_loads(self, page: Page):
        """Navigate to Employee Forum directory."""
        page.goto(f"{BASE_URL}/forum/")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Employee Directory")

    def test_41_forum_has_breadcrumb(self, page: Page):
        expect(page.locator(".breadcrumb")).to_be_visible()

    def test_42_forum_has_stats(self, page: Page):
        """Forum should show directory stats."""
        stats = page.locator(".stat-card")
        count = stats.count()
        assert count >= 1, "Expected stat cards on forum page"

    def test_43_forum_has_search(self, page: Page):
        """Forum should have a search input."""
        search = page.locator("input[name='search']")
        expect(search).to_be_visible()

    def test_44_forum_has_department_filter(self, page: Page):
        """Forum should have a department dropdown filter."""
        select = page.locator("select[name='department']")
        expect(select).to_be_visible()

    def test_45_forum_has_table_or_empty(self, page: Page):
        """Should show employee table or empty state."""
        content = page.content()
        has_table = "data-table" in content
        has_empty = "empty-state" in content or "No employees" in content
        assert has_table or has_empty, "Expected table or empty state"

    def test_46_forum_birthdays_page(self, page: Page):
        """Birthdays page should load."""
        page.goto(f"{BASE_URL}/forum/birthdays")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1")).to_contain_text("Birthdays")

    def test_47_forum_birthdays_has_back_link(self, page: Page):
        """Birthdays page should have a back link to directory."""
        link = page.locator("text=Back to Directory")
        expect(link).to_be_visible()

    # ─────────────────────────────────────────────────────────────
    #  ISP STATUS ADMIN
    # ─────────────────────────────────────────────────────────────
    def test_50_isp_admin_page(self, page: Page):
        """ISP admin page should load (or redirect if not admin)."""
        page.goto(f"{BASE_URL}/isp-admin/")
        page.wait_for_load_state("networkidle")
        # Either loads successfully or redirects to dashboard (non-admin)
        url = page.url
        is_isp = "/isp-admin" in url
        is_dashboard = url.rstrip("/") == BASE_URL.rstrip("/")
        assert is_isp or is_dashboard, f"Unexpected URL: {url}"

    def test_51_isp_admin_content(self, page: Page):
        """If user is admin, ISP page should show records table."""
        if "/isp-admin" in page.url:
            expect(page.locator("h1")).to_contain_text("ISP")
            # Should have search and table
            content = page.content()
            assert "data-table" in content or "empty-state" in content

    def test_52_isp_admin_has_stats(self, page: Page):
        """If admin, should show acceptance stats."""
        if "/isp-admin" in page.url:
            stats = page.locator(".stat-card")
            count = stats.count()
            assert count >= 1, "Expected stat cards on ISP admin page"

    # ─────────────────────────────────────────────────────────────
    #  SESSION PROTECTION — new module routes
    # ─────────────────────────────────────────────────────────────

class TestNewModuleSessionProtection:
    """Verify unauthenticated users are redirected for new modules."""

    def test_60_dms_requires_auth(self, page: Page):
        ctx = page.context.browser.new_context()
        p = ctx.new_page()
        p.goto(f"{BASE_URL}/documents/")
        expect(p).to_have_url(re.compile(r"/auth/login"))
        p.close()
        ctx.close()

    def test_61_announcements_requires_auth(self, page: Page):
        ctx = page.context.browser.new_context()
        p = ctx.new_page()
        p.goto(f"{BASE_URL}/announcements/")
        expect(p).to_have_url(re.compile(r"/auth/login"))
        p.close()
        ctx.close()

    def test_62_facility_requires_auth(self, page: Page):
        ctx = page.context.browser.new_context()
        p = ctx.new_page()
        p.goto(f"{BASE_URL}/facility/")
        expect(p).to_have_url(re.compile(r"/auth/login"))
        p.close()
        ctx.close()

    def test_63_forum_requires_auth(self, page: Page):
        ctx = page.context.browser.new_context()
        p = ctx.new_page()
        p.goto(f"{BASE_URL}/forum/")
        expect(p).to_have_url(re.compile(r"/auth/login"))
        p.close()
        ctx.close()

    def test_64_isp_admin_requires_auth(self, page: Page):
        ctx = page.context.browser.new_context()
        p = ctx.new_page()
        p.goto(f"{BASE_URL}/isp-admin/")
        expect(p).to_have_url(re.compile(r"/auth/login"))
        p.close()
        ctx.close()
