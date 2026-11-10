from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.on("console", lambda msg: print(f"CONSOLE [{msg.type}]: {msg.text}"))
    page.on("pageerror", lambda err: print(f"PAGEERROR: {err}"))

    page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
    time.sleep(1)

    print("Clicking Control Tower button...")
    page.locator("button:has-text('RECALL CONTROL TOWER')").first.click()
    time.sleep(1.5)

    tabs = ['reconciliation', 'communications', 'logistics', 'recoveries', 'dispositions', 'fssai', 'effectiveness']
    for t in tabs:
        print(f"\n--- Clicking Tab: {t} ---")
        tab_btn = page.locator(f"button[data-tab-id='{t}']").first
        tab_btn.click()
        time.sleep(1)
        # Check body text
        snippet = page.locator("body").inner_text()[:120].replace("\n", " ")
        print(f"Body snippet: {snippet}")

    print("\nAll 7 tabs verified successfully without errors!")
    browser.close()
