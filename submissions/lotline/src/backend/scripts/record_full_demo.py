import os
import time
import glob
from playwright.sync_api import sync_playwright

RAW_DIR = r"C:\Users\user\Documents\Lotline\backend\scripts\raw_video"
os.makedirs(RAW_DIR, exist_ok=True)

# Clean existing raw video files
for f in glob.glob(os.path.join(RAW_DIR, "*")):
    try:
        os.remove(f)
    except Exception:
        pass

def run():
    print("[1/2] Recording timed 115s high-fidelity walkthrough...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=RAW_DIR,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        # 0:00 - 0:15: Dashboard Overview & KPIs
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(5)
        page.mouse.wheel(0, 250)
        time.sleep(6)

        # 0:15 - 0:35: Lineage Tree
        lineage = page.locator("div:has-text('TRACEABILITY GRAPH')").first
        if lineage.is_visible():
            lineage.scroll_into_view_if_needed()
            time.sleep(4)
        for b in ["FIN-401", "FIN-402", "FIN-403"]:
            badge = page.locator(f"text={b}").first
            if badge.is_visible():
                badge.hover()
                time.sleep(2)
        time.sleep(4)

        # 0:35 - 0:55: LangGraph Multi-Agent Investigation
        agents = page.locator("div:has-text('LANGGRAPH MULTI-AGENT INVESTIGATION')").first
        if agents.is_visible():
            agents.scroll_into_view_if_needed()
            time.sleep(8)
        time.sleep(4)

        # 0:55 - 1:15: Proposed Mitigation Actions & Human-in-the-Loop
        actions = page.locator("div:has-text('RECALL RESPONSE ACTIONS')").first
        if actions.is_visible():
            actions.scroll_into_view_if_needed()
            time.sleep(6)

        # Audit Log
        audit = page.locator("div:has-text('AUDIT LOG')").first
        if audit.is_visible():
            audit.scroll_into_view_if_needed()
            time.sleep(6)

        # 1:15 - 1:55: Recall Execution Control Tower
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(2)
        ctrl_btn = page.locator("button:has-text('RECALL CONTROL TOWER')").first
        if ctrl_btn.is_visible():
            ctrl_btn.click()
            time.sleep(3)

            # Tab 1: Mass Reconciliation
            page.locator("button[data-tab-id='reconciliation']").first.click()
            time.sleep(5)

            # Tab 2: Consignee Communications
            page.locator("button[data-tab-id='communications']").first.click()
            time.sleep(5)

            # Tab 3: Logistics Interception
            page.locator("button[data-tab-id='logistics']").first.click()
            time.sleep(5)

            # Tab 4: Physical Recovery
            page.locator("button[data-tab-id='recoveries']").first.click()
            time.sleep(5)

            # Tab 5: Controlled Dispositions
            page.locator("button[data-tab-id='dispositions']").first.click()
            time.sleep(5)

            # Tab 6: FSSAI FoSCoS Tracker
            page.locator("button[data-tab-id='fssai']").first.click()
            time.sleep(5)

            # Tab 7: Effectiveness & Closure Blockers
            page.locator("button[data-tab-id='effectiveness']").first.click()
            time.sleep(6)

        # 1:55 - 2:05: Live Dossier Export Modal
        dossier_btn = page.locator("button:has-text('EXPORT DOSSIER')").first
        if dossier_btn.is_visible():
            dossier_btn.click()
            time.sleep(6)

        page.close()
        context.close()
        browser.close()
        print("Walkthrough recorded successfully.")

if __name__ == "__main__":
    run()
