from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=False)
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1:5080/auth/login")
    pg.fill('input[name="username"]', "do.admin")
    pg.fill('input[name="password"]', "Test@2025")
    pg.click('button[type="submit"]')
    pg.wait_for_load_state("networkidle")
    pg.goto("http://127.0.0.1:5080/admin/settings/workflow")
    pg.wait_for_load_state("networkidle")
    print("URL:", pg.url)
    pg.screenshot(path="tests/screenshot_workflow_debug.png", full_page=True)
    text = pg.inner_text("body")
    print("Body text (first 3000 chars):")
    print(text[:3000])
    b.close()
