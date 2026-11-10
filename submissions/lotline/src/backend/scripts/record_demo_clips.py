import os
import time
import glob
from playwright.sync_api import sync_playwright

VIDEO_RAW_DIR = r"C:\Users\user\Documents\Lotline\backend\scripts\raw_video"
os.makedirs(VIDEO_RAW_DIR, exist_ok=True)

# Clean existing raw video files
for f in glob.glob(os.path.join(VIDEO_RAW_DIR, "*")):
    try:
        os.remove(f)
    except Exception:
        pass

def record_app_tour():
    print("Launching Playwright with video recording enabled...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=VIDEO_RAW_DIR,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        # Step 1: Dashboard Overview (0 - 15s)
        print("Navigating to LOTLINE Dashboard...")
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(4)

        # Smooth scroll to show KPIs and incident summary
        page.mouse.wheel(0, 300)
        time.sleep(3)

        # Step 2: Traceability Lineage Graph (15 - 35s)
        print("Examining Traceability Lineage Graph...")
        lineage_elem = page.locator("div:has-text('TRACEABILITY GRAPH')").first
        if lineage_elem.is_visible():
            lineage_elem.scroll_into_view_if_needed()
            time.sleep(4)

        # Hover over batches to show interaction
        for batch_id in ["FIN-401", "FIN-402", "FIN-403"]:
            badge = page.locator(f"text={batch_id}").first
            if badge.is_visible():
                badge.hover()
                time.sleep(1)

        # Step 3: Multi-Agent Workflow (35 - 55s)
        print("Examining Multi-Agent Workflow...")
        agent_elem = page.locator("div:has-text('LANGGRAPH MULTI-AGENT INVESTIGATION')").first
        if agent_elem.is_visible():
            agent_elem.scroll_into_view_if_needed()
            time.sleep(5)

        # Step 4: Proposed Actions and Human Approval (55 - 75s)
        print("Examining Proposed Actions...")
        action_elem = page.locator("div:has-text('RECALL RESPONSE ACTIONS')").first
        if action_elem.is_visible():
            action_elem.scroll_into_view_if_needed()
            time.sleep(5)

        # Audit Log
        audit_elem = page.locator("div:has-text('AUDIT LOG')").first
        if audit_elem.is_visible():
            audit_elem.scroll_into_view_if_needed()
            time.sleep(4)

        # Step 5: Switch to Control Tower (75 - 110s)
        print("Switching to Recall Control Tower...")
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(2)
        ctrl_btn = page.locator("button:has-text('RECALL CONTROL TOWER')").first
        if ctrl_btn.is_visible():
            ctrl_btn.click()
            time.sleep(3)

            # Tab 1: Mass Reconciliation
            print("Control Tower: Tab 1 Mass Reconciliation")
            page.locator("button[data-tab-id='reconciliation']").first.click()
            time.sleep(4)

            # Tab 3: Logistics Interception
            print("Control Tower: Tab 3 Logistics Interception")
            page.locator("button[data-tab-id='logistics']").first.click()
            time.sleep(4)

            # Tab 4: Physical Recovery
            print("Control Tower: Tab 4 Physical Recovery")
            page.locator("button[data-tab-id='recoveries']").first.click()
            time.sleep(4)

            # Tab 5: Controlled Dispositions
            print("Control Tower: Tab 5 Controlled Dispositions")
            page.locator("button[data-tab-id='dispositions']").first.click()
            time.sleep(4)

            # Tab 6: FSSAI FoSCoS Tracker
            print("Control Tower: Tab 6 FSSAI FoSCoS Tracker")
            page.locator("button[data-tab-id='fssai']").first.click()
            time.sleep(4)

            # Tab 7: Effectiveness & Closure Blockers
            print("Control Tower: Tab 7 Effectiveness & Closure Blockers")
            page.locator("button[data-tab-id='effectiveness']").first.click()
            time.sleep(5)

        # Step 6: Dossier Export Modal (110 - 125s)
        print("Opening Export Dossier Modal...")
        dossier_btn = page.locator("button:has-text('EXPORT DOSSIER')").first
        if dossier_btn.is_visible():
            dossier_btn.click()
            time.sleep(4)

        # Done recording
        print("Finishing recording session...")
        page.close()
        context.close()
        browser.close()
        print("Browser closed and video finalized.")

if __name__ == "__main__":
    record_app_tour()
