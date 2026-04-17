"""
Open detail & print views in a visible Edge browser to verify teal-themed layouts.
Usage:  python -m pytest tests/test_print_preview.py -s
"""

import time
import pytest
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5080"


def test_print_preview():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="msedge",
            slow_mo=300,
            args=["--start-maximized"],
        )
        ctx = browser.new_context(no_viewport=True)
        page = ctx.new_page()

        # ── Login as do.admin (sees prices) ─────────────
        page.goto(f"{BASE}/auth/login")
        page.wait_for_load_state("networkidle")
        page.fill("#username", "do.admin")
        page.fill("#password", "Test@2025")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        assert "/auth/login" not in page.url, "Login failed"

        # ── Open detail view ────────────────────────────
        page.goto(f"{BASE}/delivery-orders/6003")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="screenshots/detail_view.png", full_page=True)
        print("OK Detail view saved to screenshots/detail_view.png")
        time.sleep(4)

        # ── Open print view ─────────────────────────────
        page.goto(f"{BASE}/delivery-orders/6005/print")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="screenshots/print_preview.png", full_page=True)
        print("OK Print preview saved to screenshots/print_preview.png")
        time.sleep(4)

        browser.close()
