"""Playwright test: verify KPI bubbles + admin workflow for new statuses."""
import re
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5080"


def _login(page, username="do.admin", password="Test@2025"):
    page.goto(f"{BASE}/auth/login")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_dashboard_kpi_bubbles():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        _login(page)

        # Check that KPI cards exist for both new statuses
        page.wait_for_selector(".kpi-card")

        customs_card = page.locator("a.kpi--customs-updated")
        assert customs_card.count() == 1, "Missing Customs Updated KPI card"
        assert customs_card.is_visible()
        print("Customs Updated KPI card: VISIBLE")

        delivered_card = page.locator("a.kpi--delivered")
        assert delivered_card.count() == 1, "Missing Delivered KPI card"
        assert delivered_card.is_visible()
        print("Delivered KPI card: VISIBLE")

        # Verify labels
        assert "Customs Updated" in customs_card.inner_text()
        assert "Delivered" in delivered_card.inner_text()
        print("KPI card labels: CORRECT")

        page.screenshot(path="tests/screenshot_dashboard_kpi.png", full_page=True)
        print("Dashboard screenshot saved")

        browser.close()


def test_admin_workflow_statuses():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        _login(page)

        page.goto(f"{BASE}/admin/settings/workflow")
        page.wait_for_load_state("networkidle")

        content = page.content()

        # Check for display_name or status_key
        has_customs = ("CUSTOMS DOCUMENT UPDATED" in content or
                       "Customs Document Updated" in content)
        assert has_customs, "Missing CUSTOMS DOCUMENT UPDATED in workflow"
        print("CUSTOMS DOCUMENT UPDATED: found in workflow page")

        has_delivered = ("DELIVERED" in content or "Delivered" in content)
        assert has_delivered, "Missing DELIVERED in workflow page"
        print("DELIVERED: found in workflow page")

        page.screenshot(path="tests/screenshot_workflow.png", full_page=True)
        print("Workflow screenshot saved")

        browser.close()


if __name__ == "__main__":
    test_dashboard_kpi_bubbles()
    test_admin_workflow_statuses()
    print("\nAll tests passed!")
