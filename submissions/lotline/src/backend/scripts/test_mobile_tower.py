from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page_mob = browser.new_page(viewport={"width": 390, "height": 844})
    page_mob.goto("http://127.0.0.1:5173/", wait_until="networkidle")
    time.sleep(1)

    menu_btn = page_mob.locator("button[aria-label='Toggle Navigation Menu']").first
    menu_btn.click()
    time.sleep(1)

    # Click the button inside the mobile drawer
    mob_btn = page_mob.locator("div.xl\\:hidden button:has-text('CONTROL TOWER')").first
    print("mob_btn visible:", mob_btn.is_visible())
    mob_btn.click()
    time.sleep(2)

    snippet = page_mob.locator("body").inner_text()[:120].replace("\n", " ")
    print("Mobile Control Tower snippet:", snippet)

    browser.close()
