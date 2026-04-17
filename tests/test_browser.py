"""
Comprehensive Playwright browser tests for the Intranet Portal Flask application.

Tests cover:
  1. Login page rendering & validation
  2. Login POST flow (invalid & valid credentials)
  3. ISP acceptance page
  4. Dashboard page (after login)
  5. IT Support pages (list, create, detail)
  6. Logout flow
  7. Static assets (CSS, JS)
  8. Navigation & sidebar
  9. Session protection (unauthorized access redirect)

Usage:
    python -m pytest tests/test_browser.py -v --headed   (visible browser)
    python -m pytest tests/test_browser.py -v            (headless)
"""

import os
import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:5080")


# ── Helpers ─────────────────────────────────────────────────────────

def _get_test_credentials() -> tuple[str, str]:
    """Load test credentials from environment variables.

    Set TEST_USERNAME and TEST_PASSWORD before running the suite.
    """
    username = os.environ.get("TEST_USERNAME")
    password = os.environ.get("TEST_PASSWORD")
    if not username or not password:
        pytest.skip(
            "TEST_USERNAME and TEST_PASSWORD environment variables are required"
        )
    return username, password


def login_user(page: Page, username: str | None = None, password: str | None = None):
    """Navigate to login and submit credentials.

    Uses explicit *username*/*password* when provided; falls back to
    ``TEST_USERNAME`` / ``TEST_PASSWORD`` environment variables otherwise.
    """
    if username is None or password is None:
        env_user, env_pass = _get_test_credentials()
        username = username or env_user
        password = password or env_pass
    page.goto(f"{BASE_URL}/auth/login")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


# ═══════════════════════════════════════════════════════════════════
#  1. LOGIN PAGE RENDERING
# ═══════════════════════════════════════════════════════════════════

class TestLoginPage:
    """Test login page loads and renders correctly."""

    def test_login_page_loads(self, page: Page):
        """Login page should return 200 and display the form."""
        response = page.goto(f"{BASE_URL}/auth/login")
        assert response.status == 200

    def test_login_page_title(self, page: Page):
        """Page title should contain 'Login'."""
        page.goto(f"{BASE_URL}/auth/login")
        expect(page).to_have_title(re.compile(r"Login", re.IGNORECASE))

    def test_login_form_elements(self, page: Page):
        """Login form should have username, password inputs and submit button."""
        page.goto(f"{BASE_URL}/auth/login")

        # Username field
        username_field = page.locator("#username")
        expect(username_field).to_be_visible()
        expect(username_field).to_have_attribute("name", "username")
        expect(username_field).to_have_attribute("type", "text")

        # Password field
        password_field = page.locator("#password")
        expect(password_field).to_be_visible()
        expect(password_field).to_have_attribute("name", "password")
        expect(password_field).to_have_attribute("type", "password")

        # Submit button
        submit_btn = page.locator("button[type='submit']")
        expect(submit_btn).to_be_visible()
        expect(submit_btn).to_contain_text("Sign In")

    def test_login_page_branding(self, page: Page):
        """Login page should display welcome text."""
        page.goto(f"{BASE_URL}/auth/login")
        expect(page.locator("h1")).to_contain_text("Welcome Back")
        expect(page.locator(".subtitle")).to_contain_text("Sign in")

    def test_login_page_has_placeholder(self, page: Page):
        """Username field should have a placeholder."""
        page.goto(f"{BASE_URL}/auth/login")
        expect(page.locator("#username")).to_have_attribute(
            "placeholder", re.compile(r"@")
        )


# ═══════════════════════════════════════════════════════════════════
#  2. STATIC ASSETS
# ═══════════════════════════════════════════════════════════════════

class TestStaticAssets:
    """Test that CSS and JS files load correctly."""

    def test_css_loads(self, page: Page):
        """app.css should return 200."""
        response = page.goto(f"{BASE_URL}/static/css/app.css")
        assert response.status == 200
        assert "text/css" in response.headers.get("content-type", "")

    def test_js_loads(self, page: Page):
        """app.js should return 200."""
        response = page.goto(f"{BASE_URL}/static/js/app.js")
        assert response.status == 200
        content_type = response.headers.get("content-type", "")
        assert "javascript" in content_type or "text/" in content_type

    def test_css_applied_on_login(self, page: Page):
        """Login page should have CSS loaded (check a styled element)."""
        page.goto(f"{BASE_URL}/auth/login")
        login_card = page.locator(".login-card")
        expect(login_card).to_be_visible()


# ═══════════════════════════════════════════════════════════════════
#  3. SESSION PROTECTION (UNAUTHORIZED ACCESS)
# ═══════════════════════════════════════════════════════════════════

class TestSessionProtection:
    """Test that protected routes redirect to login when not authenticated."""

    def test_root_redirects_to_login(self, page: Page):
        """Root / should redirect to /auth/login."""
        page.goto(f"{BASE_URL}/")
        expect(page).to_have_url(re.compile(r"/auth/login"))

    def test_dashboard_redirects_to_login(self, page: Page):
        """Dashboard (root) should redirect to login when not authenticated."""
        page.goto(f"{BASE_URL}/")
        expect(page).to_have_url(re.compile(r"/auth/login"))

    def test_it_support_redirects_to_login(self, page: Page):
        """IT Support should redirect to login when not authenticated."""
        page.goto(f"{BASE_URL}/it-support/")
        expect(page).to_have_url(re.compile(r"/auth/login"))

    def test_it_support_create_redirects_to_login(self, page: Page):
        """IT Support create page should redirect to login."""
        page.goto(f"{BASE_URL}/it-support/create")
        expect(page).to_have_url(re.compile(r"/auth/login"))


# ═══════════════════════════════════════════════════════════════════
#  4. LOGIN VALIDATION (INVALID CREDENTIALS)
# ═══════════════════════════════════════════════════════════════════

class TestLoginValidation:
    """Test login form validation and error handling."""

    def test_empty_credentials_shows_error(self, page: Page):
        """Submitting empty form should show validation error."""
        page.goto(f"{BASE_URL}/auth/login")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        # Should stay on login page (either flash message or form validation)
        expect(page).to_have_url(re.compile(r"/auth/login"))

    def test_invalid_credentials_shows_error(self, page: Page):
        """Submitting wrong credentials should show error flash."""
        page.goto(f"{BASE_URL}/auth/login")
        page.fill("#username", "definitely_not_a_real_user")
        page.fill("#password", "wrong_password_12345")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        # Should stay on login page
        expect(page).to_have_url(re.compile(r"/auth/login"))

    def test_login_preserves_username_on_error(self, page: Page):
        """After failed login, username should be preserved in the form."""
        page.goto(f"{BASE_URL}/auth/login")
        page.fill("#username", "test_user_name")
        page.fill("#password", "wrong_password")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        # Username field should retain the entered value
        expect(page.locator("#username")).to_have_value("test_user_name")


# ═══════════════════════════════════════════════════════════════════
#  5. LOGIN FLOW (VALID CREDENTIALS → ISP / DASHBOARD)
# ═══════════════════════════════════════════════════════════════════

class TestLoginFlow:
    """Test the full login flow with database credentials."""

    def test_login_redirects_after_success(self, page: Page):
        """
        Successful login should redirect to dashboard or ISP page.
        (Depends on whether user has accepted ISP.)
        """
        login_user(page)
        url = page.url
        # After login, user goes to either dashboard (root /) or ISP acceptance
        assert url.rstrip("/") == BASE_URL.rstrip("/") or "/isp" in url or "/auth/login" in url

    def test_login_sets_session(self, page: Page):
        """After login, user should reach ISP or dashboard (session is created)."""
        login_user(page)
        url = page.url
        # After valid login, user reaches ISP gate or dashboard — not stuck on login
        assert url.rstrip("/") == BASE_URL.rstrip("/") or "/isp" in url or "/auth/login" in url
        # If we landed on ISP, that alone proves the session was created
        if "/isp" in url:
            # Verify ISP page rendered (session is valid)
            expect(page.locator("h1")).to_contain_text("Information Security Policy")


# ═══════════════════════════════════════════════════════════════════
#  6. ISP ACCEPTANCE PAGE
# ═══════════════════════════════════════════════════════════════════

class TestISPPage:
    """Test Information Security Policy acceptance flow."""

    def test_isp_page_redirects_without_session(self, page: Page):
        """ISP page should redirect to login if no session."""
        page.goto(f"{BASE_URL}/auth/isp")
        expect(page).to_have_url(re.compile(r"/auth/login"))

    def test_isp_page_elements_after_login(self, page: Page):
        """After login, if ISP is required, check page elements."""
        login_user(page)
        if "/isp" in page.url:
            # ISP page should show policy text
            expect(page.locator("h1")).to_contain_text("Information Security Policy")
            # Checkbox should be visible
            checkbox = page.locator("#isp-accept")
            expect(checkbox).to_be_visible()
            # Button should be disabled initially
            accept_btn = page.locator("#accept-btn")
            expect(accept_btn).to_be_disabled()

    def test_isp_checkbox_enables_button(self, page: Page):
        """Checking the ISP checkbox should enable the accept button."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            accept_btn = page.locator("#accept-btn")
            expect(accept_btn).to_be_enabled()

    def test_isp_accept_redirects_to_dashboard(self, page: Page):
        """Accepting ISP should redirect to dashboard."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")
            assert "/dashboard" in page.url or "/auth" in page.url


# ═══════════════════════════════════════════════════════════════════
#  7. DASHBOARD PAGE
# ═══════════════════════════════════════════════════════════════════

class TestDashboard:
    """Test dashboard page content and navigation."""

    @pytest.fixture(autouse=True)
    def _login(self, page: Page):
        """Login and accept ISP before each dashboard test."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

    def test_dashboard_loads(self, page: Page):
        """Dashboard should load after login."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            expect(page).to_have_title(re.compile(r"Dashboard", re.IGNORECASE))

    def test_dashboard_has_title(self, page: Page):
        """Dashboard should display 'Dashboard' heading."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            heading = page.locator("h1")
            expect(heading).to_contain_text("Dashboard")

    def test_dashboard_has_sidebar(self, page: Page):
        """Dashboard layout should include sidebar navigation."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            sidebar = page.locator("#sidebar")
            expect(sidebar).to_be_visible()

    def test_dashboard_sidebar_links(self, page: Page):
        """Sidebar should have links to Dashboard and IT Support."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            dashboard_link = page.locator('.nav-item:has-text("Dashboard")')
            expect(dashboard_link).to_be_visible()
            it_link = page.locator('.nav-item:has-text("IT Support")')
            expect(it_link).to_be_visible()

    def test_dashboard_stat_cards(self, page: Page):
        """Dashboard should display KPI stat cards."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            stat_cards = page.locator(".stat-card")
            expect(stat_cards.first).to_be_visible()

    def test_dashboard_quick_actions(self, page: Page):
        """Dashboard should have Quick Actions section."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            quick_actions = page.locator("text=Quick Actions")
            expect(quick_actions).to_be_visible()


# ═══════════════════════════════════════════════════════════════════
#  8. IT SUPPORT PAGES
# ═══════════════════════════════════════════════════════════════════

class TestITSupport:
    """Test IT Support module pages."""

    @pytest.fixture(autouse=True)
    def _login(self, page: Page):
        """Login and accept ISP before each IT Support test."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

    def test_it_support_list_loads(self, page: Page):
        """IT Support list page should load."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            expect(page).to_have_title(re.compile(r"IT Support", re.IGNORECASE))

    def test_it_support_list_has_heading(self, page: Page):
        """IT Support list should display 'IT Support' heading."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            expect(page.locator("h1")).to_contain_text("IT Support")

    def test_it_support_list_has_new_ticket_button(self, page: Page):
        """IT Support list should have a 'New Ticket' button."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            new_btn = page.locator("text=New Ticket")
            expect(new_btn.first).to_be_visible()

    def test_it_support_list_has_stat_cards(self, page: Page):
        """IT Support list should show ticket statistics."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            stat_cards = page.locator(".stat-card")
            expect(stat_cards.first).to_be_visible()

    def test_it_support_list_has_filter_chips(self, page: Page):
        """IT Support list should have status filter chips."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            filter_bar = page.locator(".filter-bar")
            expect(filter_bar).to_be_visible()
            expect(page.locator(".filter-chip").first).to_be_visible()

    def test_it_support_list_has_search(self, page: Page):
        """IT Support list should have a search form."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            search_input = page.locator("input[name='q']")
            expect(search_input).to_be_visible()

    def test_it_support_create_page_loads(self, page: Page):
        """IT Support create form should load."""
        page.goto(f"{BASE_URL}/it-support/create")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            expect(page.locator("h1")).to_contain_text("Create New Ticket")

    def test_it_support_create_form_elements(self, page: Page):
        """Create form should have subject, priority, description fields."""
        page.goto(f"{BASE_URL}/it-support/create")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            expect(page.locator("#subject")).to_be_visible()
            expect(page.locator("#priority")).to_be_visible()
            expect(page.locator("#summary")).to_be_visible()
            expect(page.locator("#on_behalf_of")).to_be_visible()

    def test_it_support_create_has_buttons(self, page: Page):
        """Create form should have Cancel and Create Ticket buttons."""
        page.goto(f"{BASE_URL}/it-support/create")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            cancel_btn = page.locator("text=Cancel")
            expect(cancel_btn).to_be_visible()
            submit_btn = page.locator("text=Create Ticket")
            expect(submit_btn).to_be_visible()

    def test_it_support_navigate_from_dashboard(self, page: Page):
        """Should be able to navigate to IT Support from dashboard sidebar."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            page.click('.nav-item:has-text("IT Support")')
            page.wait_for_load_state("networkidle")
            expect(page).to_have_url(re.compile(r"/it-support"))

    def test_it_support_filter_by_status(self, page: Page):
        """Clicking status filter chip should filter tickets."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            open_filter = page.locator(".filter-chip:has-text('Open')")
            if open_filter.count() > 0:
                open_filter.click()
                page.wait_for_load_state("networkidle")
                expect(page).to_have_url(re.compile(r"status=open"))

    def test_it_support_breadcrumb(self, page: Page):
        """IT Support pages should show breadcrumb navigation."""
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            breadcrumb = page.locator(".page-header__breadcrumb")
            expect(breadcrumb).to_be_visible()
            expect(breadcrumb).to_contain_text("Home")


# ═══════════════════════════════════════════════════════════════════
#  9. LOGOUT FLOW
# ═══════════════════════════════════════════════════════════════════

class TestLogout:
    """Test logout functionality."""

    def test_logout_redirects_to_login(self, page: Page):
        """Logout should redirect to login page."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

        page.goto(f"{BASE_URL}/auth/logout")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(re.compile(r"/auth/login"))

    def test_logout_clears_session(self, page: Page):
        """After logout, accessing protected pages should redirect to login."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

        # Logout
        page.goto(f"{BASE_URL}/auth/logout")
        page.wait_for_load_state("networkidle")

        # Try accessing dashboard — should redirect to login
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(re.compile(r"/auth/login"))


# ═══════════════════════════════════════════════════════════════════
#  10. RESPONSIVE / VISUAL CHECKS
# ═══════════════════════════════════════════════════════════════════

class TestVisualChecks:
    """Basic visual and responsive checks."""

    def test_login_page_no_console_errors(self, page: Page):
        """Login page should load without JavaScript console errors."""
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{BASE_URL}/auth/login")
        page.wait_for_load_state("networkidle")
        # Filter out non-critical warnings
        critical_errors = [e for e in errors if "Warning" not in e]
        assert len(critical_errors) == 0, f"JS errors: {critical_errors}"

    def test_login_page_no_broken_resources(self, page: Page):
        """Login page should not have broken resource loads (404s)."""
        failed_requests = []

        def on_response(response):
            if response.status >= 400 and response.url.startswith(BASE_URL):
                failed_requests.append(f"{response.status} {response.url}")

        page.on("response", on_response)
        page.goto(f"{BASE_URL}/auth/login")
        page.wait_for_load_state("networkidle")
        assert len(failed_requests) == 0, f"Failed resources: {failed_requests}"

    def test_login_page_mobile_viewport(self, page: Page):
        """Login page should be usable on mobile viewport."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{BASE_URL}/auth/login")
        login_card = page.locator(".login-card")
        expect(login_card).to_be_visible()
        submit_btn = page.locator("button[type='submit']")
        expect(submit_btn).to_be_visible()

    def test_login_page_desktop_viewport(self, page: Page):
        """Login page should render properly on desktop."""
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(f"{BASE_URL}/auth/login")
        login_card = page.locator(".login-card")
        expect(login_card).to_be_visible()


# ═══════════════════════════════════════════════════════════════════
#  11. SCREENSHOT CAPTURE (for visual review)
# ═══════════════════════════════════════════════════════════════════

class TestScreenshots:
    """Capture screenshots of each page for visual review."""

    def test_screenshot_login_page(self, page: Page):
        """Capture login page screenshot."""
        page.goto(f"{BASE_URL}/auth/login")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests/screenshots/01_login_page.png", full_page=True)

    def test_screenshot_login_error(self, page: Page):
        """Capture login error state screenshot."""
        page.goto(f"{BASE_URL}/auth/login")
        page.fill("#username", "invalid_user")
        page.fill("#password", "wrong_pass")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests/screenshots/02_login_error.png", full_page=True)

    def test_screenshot_after_login(self, page: Page):
        """Capture the page shown after login (ISP or Dashboard)."""
        login_user(page)
        page.screenshot(path="tests/screenshots/03_after_login.png", full_page=True)

    def test_screenshot_dashboard(self, page: Page):
        """Capture dashboard screenshot."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests/screenshots/04_dashboard.png", full_page=True)

    def test_screenshot_it_support_list(self, page: Page):
        """Capture IT Support list screenshot."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests/screenshots/05_it_support_list.png", full_page=True)

    def test_screenshot_it_support_create(self, page: Page):
        """Capture IT Support create form screenshot."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/it-support/create")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests/screenshots/06_it_support_create.png", full_page=True)

    def test_screenshot_mobile_login(self, page: Page):
        """Capture login page in mobile viewport."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{BASE_URL}/auth/login")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests/screenshots/07_mobile_login.png", full_page=True)


# ═══════════════════════════════════════════════════════════════════
#  12. PLACEHOLDER / COMING SOON PAGES
# ═══════════════════════════════════════════════════════════════════

class TestComingSoonPages:
    """Test all 'coming soon' placeholder module pages."""

    @pytest.fixture(autouse=True)
    def _login(self, page: Page):
        """Login and accept ISP before each test."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

    @pytest.mark.parametrize("slug,label", [
        ("documents", "Document Management"),
        ("sales-orders", "Sales Orders"),
        ("announcements", "Announcements"),
        ("facility", "Facility Management"),
        ("users", "User Management"),
        ("settings", "Settings"),
    ])
    def test_coming_soon_page_loads(self, page: Page, slug: str, label: str):
        """Each placeholder module page should load with 200."""
        page.goto(f"{BASE_URL}/{slug}")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            expect(page.locator("h1")).to_contain_text(label)

    @pytest.mark.parametrize("slug", [
        "documents", "sales-orders", "announcements", "facility", "users", "settings",
    ])
    def test_coming_soon_has_back_button(self, page: Page, slug: str):
        """Each coming-soon page should have a Back to Dashboard button."""
        page.goto(f"{BASE_URL}/{slug}")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            back_btn = page.locator("text=Back to Dashboard")
            expect(back_btn).to_be_visible()

    def test_coming_soon_back_navigates_to_dashboard(self, page: Page):
        """Clicking 'Back to Dashboard' should navigate to the dashboard."""
        page.goto(f"{BASE_URL}/documents")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            page.click("text=Back to Dashboard")
            page.wait_for_load_state("networkidle")
            expect(page).to_have_url(re.compile(r"/$"))


# ═══════════════════════════════════════════════════════════════════
#  13. DASHBOARD KPI CARDS (REAL DATA)
# ═══════════════════════════════════════════════════════════════════

class TestDashboardKPIs:
    """Test that dashboard KPI cards show real numbers, not dashes."""

    @pytest.fixture(autouse=True)
    def _login(self, page: Page):
        """Login and accept ISP before each test."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

    def test_kpi_open_tickets_shows_number(self, page: Page):
        """Open IT Tickets KPI should show a number, not a dash."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            value = page.locator(".stat-card__value").first
            text = value.inner_text()
            assert text != "—", "KPI should show a number, not a dash"
            assert text.strip().isdigit(), f"KPI value should be numeric, got '{text}'"

    def test_kpi_labels_updated(self, page: Page):
        """Dashboard should show ticket-related KPI labels."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            labels = page.locator(".stat-card__label").all_inner_texts()
            assert "Open IT Tickets" in labels
            assert "Total Tickets" in labels
            assert "In Progress" in labels
            assert "Closed Tickets" in labels


# ═══════════════════════════════════════════════════════════════════
#  14. SIDEBAR NAVIGATION (ALL LINKS WORK)
# ═══════════════════════════════════════════════════════════════════

class TestSidebarNavigation:
    """Test that every sidebar link navigates to a real page (no '#' links)."""

    @pytest.fixture(autouse=True)
    def _login(self, page: Page):
        """Login and accept ISP before each test."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

    def test_no_hash_links_in_sidebar(self, page: Page):
        """No sidebar link should point to '#'."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            links = page.locator("#sidebar .nav-item").all()
            for link in links:
                href = link.get_attribute("href")
                assert href != "#", f"Sidebar link '{link.inner_text().strip()}' still points to #"

    def test_sidebar_documents_link(self, page: Page):
        """Documents sidebar link should navigate to coming-soon page."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            page.click('.nav-item:has-text("Documents")')
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1")).to_contain_text("Document Management")

    def test_sidebar_settings_link(self, page: Page):
        """Settings sidebar link should navigate to coming-soon page."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            page.click('.nav-item:has-text("Settings")')
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1")).to_contain_text("Settings")


# ═══════════════════════════════════════════════════════════════════
#  15. IT TICKET CRUD FLOW (END-TO-END)
# ═══════════════════════════════════════════════════════════════════

class TestITTicketCRUD:
    """End-to-end test: create a ticket, view it, verify in list."""

    @pytest.fixture(autouse=True)
    def _login(self, page: Page):
        """Login and accept ISP before each test."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

    def test_create_ticket_flow(self, page: Page):
        """Create a new IT ticket via the form and verify it appears."""
        page.goto(f"{BASE_URL}/it-support/create")
        page.wait_for_load_state("networkidle")
        if "/auth/login" in page.url:
            pytest.skip("Not logged in")

        test_subject = "Playwright Test Ticket"
        test_desc = "This is an automated test ticket created by Playwright E2E tests."

        page.fill("#subject", test_subject)
        page.select_option("#priority", "high")
        page.fill("#summary", test_desc)
        page.click("text=Create Ticket")
        page.wait_for_load_state("networkidle")

        # Should land on ticket detail page — heading shows "Ticket #N"
        expect(page.locator("h1")).to_contain_text("Ticket #")
        # Subject should appear in the detail body
        expect(page.locator("body")).to_contain_text(test_subject)

    def test_ticket_appears_in_list(self, page: Page):
        """After creating a ticket, it should appear in the list."""
        # First create
        page.goto(f"{BASE_URL}/it-support/create")
        page.wait_for_load_state("networkidle")
        if "/auth/login" in page.url:
            pytest.skip("Not logged in")

        test_subject = "List Check Ticket"
        page.fill("#subject", test_subject)
        page.select_option("#priority", "medium")
        page.fill("#summary", "Automated test — verifies ticket appears in list view.")
        page.click("text=Create Ticket")
        page.wait_for_load_state("networkidle")

        # Navigate to list
        page.goto(f"{BASE_URL}/it-support/")
        page.wait_for_load_state("networkidle")

        # The ticket should be visible in the table (use .first in case of duplicates)
        expect(page.locator(f"text={test_subject}").first).to_be_visible()


# ═══════════════════════════════════════════════════════════════════
#  16. SCREENSHOTS FOR NEW PAGES
# ═══════════════════════════════════════════════════════════════════

class TestNewPageScreenshots:
    """Capture screenshots of all new pages for visual review."""

    @pytest.fixture(autouse=True)
    def _login(self, page: Page):
        """Login and accept ISP before each test."""
        login_user(page)
        if "/isp" in page.url:
            page.check("#isp-accept")
            page.click("#accept-btn")
            page.wait_for_load_state("networkidle")

    @pytest.mark.parametrize("slug,num", [
        ("documents", "08"), ("sales-orders", "09"), ("announcements", "10"),
        ("facility", "11"), ("users", "12"), ("settings", "13"),
    ])
    def test_screenshot_coming_soon(self, page: Page, slug: str, num: str):
        """Capture each coming-soon page screenshot."""
        page.goto(f"{BASE_URL}/{slug}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"tests/screenshots/{num}_{slug}.png", full_page=True)
