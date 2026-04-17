"""
Playwright browser tests for the Admin Settings module — with screenshots.

Covers:
  1. Dynamic sidebar rendering (icons from DB, Settings link for admin)
  2. Admin Settings dashboard page
  3. User management (list, create)
  4. Restricted words management
  5. Module management (list)
  6. Workflow editor (statuses + transitions)

Usage:
    $env:TEST_USERNAME="do.creator"; $env:TEST_PASSWORD="Test@2025"
    $env:ADMIN_USERNAME="do.admin"; $env:ADMIN_PASSWORD="Test@2025"
    python -m pytest tests/test_admin_settings.py -v --headed
"""

import os
import re
import pathlib
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:5080")
SCREENSHOTS_DIR = pathlib.Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


# ── Helpers ─────────────────────────────────────────────────────────

def _get_test_credentials() -> tuple[str, str]:
    username = os.environ.get("TEST_USERNAME")
    password = os.environ.get("TEST_PASSWORD")
    if not username or not password:
        pytest.skip("TEST_USERNAME and TEST_PASSWORD env vars required")
    return username, password


def _get_admin_credentials() -> tuple[str, str]:
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        pytest.skip("ADMIN_USERNAME and ADMIN_PASSWORD env vars required")
    return username, password


def _do_login(page: Page, username: str, password: str):
    """Perform login with given credentials."""
    page.goto(f"{BASE_URL}/auth/login")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


def _screenshot(page: Page, name: str):
    """Save a full-page screenshot to the screenshots folder."""
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  [Screenshot] {path}")


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def logged_in_page(browser):
    """Provide a browser page logged in as regular user."""
    username, password = _get_test_credentials()
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    _do_login(page, username, password)
    yield page
    context.close()


@pytest.fixture(scope="module")
def admin_page(browser):
    """Provide a browser page logged in as admin user (GroupID=1)."""
    username, password = _get_admin_credentials()
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    _do_login(page, username, password)
    yield page
    context.close()


# ═══════════════════════════════════════════════════════════════════
#  1. DYNAMIC SIDEBAR
# ═══════════════════════════════════════════════════════════════════

class TestDynamicSidebar:
    """Verify the sidebar renders dynamically from DB module config."""

    def test_sidebar_has_section_labels(self, logged_in_page: Page):
        """Sidebar should show Main and Modules sections."""
        page = logged_in_page
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        nav = page.locator(".sidebar__nav")
        expect(nav).to_be_visible()

        labels = nav.locator(".sidebar__section-label")
        label_texts = [labels.nth(i).text_content().strip() for i in range(labels.count())]
        assert "Main" in label_texts, f"Missing 'Main' section, got: {label_texts}"
        assert "Modules" in label_texts, f"Missing 'Modules' section, got: {label_texts}"

        _screenshot(page, "01_sidebar_section_labels")

    def test_sidebar_has_nav_items_with_svg_icons(self, logged_in_page: Page):
        """Each nav-item should contain an SVG icon from DB."""
        page = logged_in_page
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        nav_items = page.locator(".sidebar__nav .nav-item")
        count = nav_items.count()
        assert count >= 6, f"Expected at least 6 nav items, got {count}"

        first_svg = nav_items.first.locator("svg")
        expect(first_svg).to_be_visible()

        _screenshot(page, "02_sidebar_svg_icons")

    def test_dashboard_nav_item_is_active(self, logged_in_page: Page):
        """The Dashboard nav-item should have 'active' class on /."""
        page = logged_in_page
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        dashboard_link = page.locator(".nav-item", has_text="Dashboard")
        expect(dashboard_link).to_have_class(re.compile(r"active"))

        _screenshot(page, "03_dashboard_active")

    def test_settings_link_visible_for_admin(self, admin_page: Page):
        """Settings link should appear in Admin section for admin users."""
        page = admin_page
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        settings_link = page.locator(".nav-item", has_text="Settings")
        expect(settings_link).to_be_visible()
        href = settings_link.get_attribute("href")
        assert "/admin/settings" in href

        _screenshot(page, "04_admin_settings_link")


# ═══════════════════════════════════════════════════════════════════
#  2. ADMIN SETTINGS DASHBOARD
# ═══════════════════════════════════════════════════════════════════

class TestAdminSettingsDashboard:
    """Test the /admin/settings index page."""

    def test_settings_index_page_loads(self, admin_page: Page):
        """Admin settings dashboard should load with setting cards."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings")
        page.wait_for_load_state("networkidle")

        heading = page.locator("h1, h2", has_text=re.compile(r"Settings|Admin", re.I))
        expect(heading.first).to_be_visible()

        cards = page.locator(".settings-card, .card, a[href*='admin/settings']")
        assert cards.count() >= 3, f"Expected at least 3 setting cards, got {cards.count()}"

        _screenshot(page, "05_settings_dashboard")


# ═══════════════════════════════════════════════════════════════════
#  3. USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

class TestUserManagement:
    """Test user CRUD pages."""

    def test_users_list_page(self, admin_page: Page):
        """User list page should show a table."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/users")
        page.wait_for_load_state("networkidle")

        table = page.locator("table")
        expect(table.first).to_be_visible()

        rows = page.locator("table tbody tr")
        assert rows.count() >= 1, "Expected at least 1 user row"

        _screenshot(page, "06_users_list")

    def test_user_create_form_loads(self, admin_page: Page):
        """New user form should load with required fields."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/users/new")
        page.wait_for_load_state("networkidle")

        expect(page.locator("[name='first_name']")).to_be_visible()
        expect(page.locator("[name='last_name']")).to_be_visible()
        expect(page.locator("[name='email']")).to_be_visible()
        expect(page.locator("[name='username']")).to_be_visible()
        expect(page.locator("[name='password']")).to_be_visible()

        _screenshot(page, "07_user_create_form")


# ═══════════════════════════════════════════════════════════════════
#  4. RESTRICTED WORDS
# ═══════════════════════════════════════════════════════════════════

class TestRestrictedWords:
    """Test restricted words management."""

    def test_restricted_words_page_loads(self, admin_page: Page):
        """Restricted words page should show word list + add form."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/restricted-words")
        page.wait_for_load_state("networkidle")

        word_input = page.locator("[name='word']")
        expect(word_input).to_be_visible()

        submit = page.locator("button[type='submit'], input[type='submit']")
        expect(submit.first).to_be_visible()

        _screenshot(page, "08_restricted_words")


# ═══════════════════════════════════════════════════════════════════
#  5. MODULE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

class TestModuleManagement:
    """Test module config pages."""

    def test_modules_list_page(self, admin_page: Page):
        """Module list should show all 9 seeded module cards."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/modules")
        page.wait_for_load_state("networkidle")

        cards = page.locator(".mod-card")
        assert cards.count() >= 9, f"Expected at least 9 module cards, got {cards.count()}"

        # Each card should have a toggle switch and a 3-dot menu
        first_card = cards.first
        toggle = first_card.locator(".toggle-switch")
        expect(toggle).to_be_visible()

        menu_btn = first_card.locator(".mod-menu__trigger")
        expect(menu_btn).to_be_visible()

        _screenshot(page, "09_modules_cards")

    def test_modules_search_filter(self, admin_page: Page):
        """Search bar should filter module cards by name."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/modules")
        page.wait_for_load_state("networkidle")

        search_input = page.locator("#moduleSearch")
        expect(search_input).to_be_visible()

        # Type a partial module name
        search_input.fill("delivery")
        page.wait_for_timeout(200)

        visible_cards = page.locator(".mod-card:visible")
        assert visible_cards.count() >= 1, "Expected at least 1 card matching 'delivery'"
        assert visible_cards.count() < page.locator(".mod-card").count(), "Expected filter to hide some cards"

        _screenshot(page, "09b_modules_search")

        # Clear search should show all again
        search_input.fill("")
        page.wait_for_timeout(200)
        assert page.locator(".mod-card:visible").count() >= 9

    def test_modules_three_dot_menu(self, admin_page: Page):
        """Clicking 3-dot menu should show Access Control dropdown."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/modules")
        page.wait_for_load_state("networkidle")

        # Click the first card's 3-dot menu
        first_menu_btn = page.locator(".mod-menu__trigger").first
        first_menu_btn.click()

        dropdown = page.locator(".mod-menu__dropdown").first
        expect(dropdown).to_be_visible()

        access_link = dropdown.locator(".mod-menu__item", has_text="Access Control")
        expect(access_link).to_be_visible()

        _screenshot(page, "09c_modules_menu")


# ═══════════════════════════════════════════════════════════════════
#  6. WORKFLOW EDITOR
# ═══════════════════════════════════════════════════════════════════

class TestWorkflowEditor:
    """Test workflow status + transition editor."""

    def test_workflow_page_loads(self, admin_page: Page):
        """Workflow page should load with module tabs."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/workflow")
        page.wait_for_load_state("networkidle")

        page_text = page.text_content("body")
        assert any(
            kw in page_text
            for kw in ["Delivery Order", "delivery_orders", "DMS", "IT Support"]
        ), "Expected workflow module tabs/selectors"

        _screenshot(page, "10_workflow_overview")

    def test_workflow_shows_statuses(self, admin_page: Page):
        """Workflow page should display status rows."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/workflow?module=delivery_orders")
        page.wait_for_load_state("networkidle")

        page_text = page.text_content("body")
        assert "DRAFT" in page_text or "Draft" in page_text, "Expected DO status DRAFT"
        assert "SUBMITTED" in page_text or "Submitted" in page_text, "Expected DO status SUBMITTED"

        _screenshot(page, "11_workflow_statuses")

    def test_workflow_shows_transitions(self, admin_page: Page):
        """Workflow page should display transition rules."""
        page = admin_page
        page.goto(f"{BASE_URL}/admin/settings/workflow?module=delivery_orders")
        page.wait_for_load_state("networkidle")

        page_text = page.text_content("body")
        has_transitions = (
            "CONFIRMED" in page_text or "Confirmed" in page_text or
            "PRICE AGREED" in page_text or "Price Agreed" in page_text
        )
        assert has_transitions, "Expected workflow transitions to be visible"

        _screenshot(page, "12_workflow_transitions")


# ═══════════════════════════════════════════════════════════════════
#  7. MODULE ACCESS — ROLE-CENTRIC UI
# ═══════════════════════════════════════════════════════════════════

class TestModuleAccessRoles:
    """Test the role-centric role assignment UI on module access pages."""

    MODULE_ACCESS_URL = f"{BASE_URL}/admin/settings/modules/5/access"

    # ── helpers ──────────────────────────────────────────────────

    def _find_module_with_roles(self, page: Page) -> str:
        """Navigate to modules list, find one with roles (DO, DMS, or IT Support)
        and return its access URL. Falls back to module 5."""
        page.goto(f"{BASE_URL}/admin/settings/modules")
        page.wait_for_load_state("networkidle")

        # Look for "Access" links in the modules table
        access_links = page.locator("a[href*='/access']")
        count = access_links.count()
        for i in range(count):
            href = access_links.nth(i).get_attribute("href")
            if href:
                return href
        return self.MODULE_ACCESS_URL

    # ── tests ────────────────────────────────────────────────────

    def test_role_tabs_visible(self, admin_page: Page):
        """Module access page should show clickable role tabs."""
        page = admin_page
        page.goto(self.MODULE_ACCESS_URL)
        page.wait_for_load_state("networkidle")

        tabs = page.locator(".role-tab")
        count = tabs.count()
        assert count >= 2, f"Expected at least 2 role tabs, got {count}"

        # First tab should be active by default
        first_tab = tabs.first
        expect(first_tab).to_have_class(re.compile(r"role-tab--active"))

        _screenshot(page, "13_role_tabs")

    def test_role_tab_click_switches_panel(self, admin_page: Page):
        """Clicking a different role tab should show that role's panel."""
        page = admin_page
        page.goto(self.MODULE_ACCESS_URL)
        page.wait_for_load_state("networkidle")

        tabs = page.locator(".role-tab")
        assert tabs.count() >= 2, "Need at least 2 role tabs for switching test"

        # Click the second tab
        second_tab = tabs.nth(1)
        role_key = second_tab.get_attribute("data-role")
        second_tab.click()

        # The second tab should now be active
        expect(second_tab).to_have_class(re.compile(r"role-tab--active"))

        # Its panel should be visible
        panel = page.locator(f"#panel_{role_key}")
        expect(panel).to_be_visible()

        # First tab should no longer be active
        first_tab = tabs.first
        expect(first_tab).not_to_have_class(re.compile(r"role-tab--active"))

        _screenshot(page, "14_role_tab_switch")

    def test_role_panel_has_add_user_form(self, admin_page: Page):
        """Each role panel should have an 'Add User' form."""
        page = admin_page
        page.goto(self.MODULE_ACCESS_URL)
        page.wait_for_load_state("networkidle")

        # Check the first visible panel
        panels = page.locator(".role-panel")
        assert panels.count() >= 1, "Expected at least 1 role panel"

        first_panel = panels.first
        # The add-user form has action=assign_role
        add_form = first_panel.locator("form").filter(
            has=page.locator("input[name='action'][value='assign_role']")
        )
        expect(add_form).to_be_attached()

        # Should have a user select dropdown
        user_select = add_form.locator("select[name='emp_id']")
        expect(user_select).to_be_visible()

        _screenshot(page, "15_role_panel_add_form")

    def test_assign_and_remove_user_role(self, admin_page: Page):
        """Assign a user to a role, verify they appear, then remove them."""
        page = admin_page
        page.goto(self.MODULE_ACCESS_URL)
        page.wait_for_load_state("networkidle")

        # Pick the last role tab (less likely to have assignments)
        tabs = page.locator(".role-tab")
        last_tab = tabs.last
        role_key = last_tab.get_attribute("data-role")
        last_tab.click()

        panel = page.locator(f"#panel_{role_key}")
        expect(panel).to_be_visible()

        # Find the add-user form in this panel
        add_form = panel.locator("form").filter(
            has=page.locator("input[name='action'][value='assign_role']")
        )
        user_select = add_form.locator("select[name='emp_id']")
        options = user_select.locator("option[value]:not([value=''])")

        # Skip if no users available to assign
        opt_count = options.count()
        if opt_count == 0:
            _screenshot(page, "16_no_users_to_assign")
            pytest.skip("No users available to assign")

        # Pick the first available user
        first_option = options.first
        emp_id = first_option.get_attribute("value")
        user_select.select_option(value=emp_id)

        _screenshot(page, "16_before_assign")

        # Submit the form — accept any confirm dialog
        page.on("dialog", lambda d: d.accept())
        add_form.locator("button[type='submit']").click()
        page.wait_for_load_state("networkidle")

        _screenshot(page, "17_after_assign")

        # Re-click the same role tab (page reloaded, so tab may have reset)
        target_tab = page.locator(f".role-tab[data-role='{role_key}']")
        target_tab.click()

        panel = page.locator(f"#panel_{role_key}")

        # Verify user appears in the panel
        panel_text = panel.text_content()
        assert emp_id in panel_text, f"Expected assigned user {emp_id} in panel"

        # Now find the revoke form for this specific user
        revoke_form = panel.locator("form").filter(
            has=page.locator(f"input[name='emp_id'][value='{emp_id}']")
        ).filter(
            has=page.locator("input[name='action'][value='revoke_role']")
        )
        remove_btn = revoke_form.locator("button[type='submit']")
        remove_btn.click()
        page.wait_for_load_state("networkidle")

        _screenshot(page, "18_after_remove")

        # Verify user is gone — they should be back in the dropdown
        target_tab = page.locator(f".role-tab[data-role='{role_key}']")
        target_tab.click()
        panel = page.locator(f"#panel_{role_key}")
        add_form = panel.locator("form").filter(
            has=page.locator("input[name='action'][value='assign_role']")
        )
        user_select = add_form.locator("select[name='emp_id']")
        select_text = user_select.text_content()
        assert emp_id in select_text, f"Expected user {emp_id} back in dropdown after removal"

    def test_role_tab_count_updates(self, admin_page: Page):
        """Role tab badge should show the correct count of assigned users."""
        page = admin_page
        page.goto(self.MODULE_ACCESS_URL)
        page.wait_for_load_state("networkidle")

        tabs = page.locator(".role-tab")
        assert tabs.count() >= 1

        # Each tab should have a count badge
        for i in range(tabs.count()):
            tab = tabs.nth(i)
            count_badge = tab.locator(".role-tab__count")
            expect(count_badge).to_be_visible()
            count_text = count_badge.text_content().strip()
            assert count_text.isdigit(), f"Expected numeric count, got '{count_text}'"

        _screenshot(page, "19_role_tab_counts")
