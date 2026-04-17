"""Generate PDF from the user manual HTML using Playwright."""
from playwright.sync_api import sync_playwright
import os

HTML_PATH = os.path.abspath("static/user_manual.html")
PDF_PATH = os.path.abspath("static/DoApp_User_Manual_v4.0.pdf")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load the HTML file
        page.goto(f"file:///{HTML_PATH.replace(os.sep, '/')}")
        page.wait_for_load_state("networkidle")

        # Generate PDF
        page.pdf(
            path=PDF_PATH,
            format="A4",
            margin={"top": "20mm", "bottom": "22mm", "left": "18mm", "right": "18mm"},
            print_background=True,
            display_header_footer=True,
            header_template='<div style="font-size:8px;color:#94a3b8;width:100%;text-align:center;margin-top:10px;">AWGTC — Delivery Orders User Manual v4.0</div>',
            footer_template='<div style="font-size:8px;color:#94a3b8;width:100%;text-align:center;margin-bottom:10px;">Page <span class="pageNumber"></span> of <span class="totalPages"></span> — Confidential: Internal Use Only</div>',
        )

        browser.close()
        print(f"PDF generated: {PDF_PATH}")
        print(f"File size: {os.path.getsize(PDF_PATH) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
