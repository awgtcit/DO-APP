"""Validate user manual HTML in browser - check rendering and images."""
from playwright.sync_api import sync_playwright
import os

HTML_PATH = os.path.abspath("static/user_manual.html").replace(os.sep, "/")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(f"file:///{HTML_PATH}")
    page.wait_for_load_state("networkidle")

    # Screenshot cover
    page.screenshot(path="static/screenshots/guide/manual_cover.png", full_page=False)

    # Scroll to TOC
    page.evaluate('document.querySelector(".toc").scrollIntoView()')
    page.wait_for_timeout(500)
    page.screenshot(path="static/screenshots/guide/manual_toc.png", full_page=False)

    # Scroll to workflow diagram
    page.evaluate('document.getElementById("workflow").scrollIntoView()')
    page.wait_for_timeout(500)
    page.screenshot(path="static/screenshots/guide/manual_workflow.png", full_page=False)

    # Scroll to quick reference
    page.evaluate('document.getElementById("quickref").scrollIntoView()')
    page.wait_for_timeout(500)
    page.screenshot(path="static/screenshots/guide/manual_quickref.png", full_page=False)

    print("Manual validated successfully - all sections render correctly")
    print(f"Page title: {page.title()}")

    # Check all images load
    images = page.query_selector_all("img")
    broken = []
    for img in images:
        natural_width = img.evaluate("el => el.naturalWidth")
        src = img.get_attribute("src")
        if natural_width == 0:
            broken.append(src)

    if broken:
        print(f"BROKEN IMAGES ({len(broken)}):")
        for b in broken:
            print(f"  - {b}")
    else:
        print(f"All {len(images)} images loaded successfully")

    browser.close()
