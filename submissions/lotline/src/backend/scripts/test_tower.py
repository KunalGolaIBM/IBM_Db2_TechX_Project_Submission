from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    
    page.on("console", lambda m: print(f"CONSOLE [{m.type}]: {m.text}"))
    page.on("pageerror", lambda e: print(f"PAGEERROR: {e}"))
    
    page.goto("http://127.0.0.1:5173/")
    page.wait_for_timeout(2000)
    
    loc = page.locator("button:has-text('CONTROL TOWER')")
    print("Clicking button...")
    loc.first.click()
    page.wait_for_timeout(2000)
    
    print("Body text snippet:")
    print(page.locator("body").inner_text()[:400])
    
    browser.close()
