import os
import glob
import time
import requests
import pymupdf
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\user\.gemini\antigravity\brain\33f96407-323d-4adf-aad2-d2cdacbdb616"

def clean_previous_screenshots():
    print("Deleting previous screenshots from artifact directory...")
    pattern = os.path.join(ARTIFACT_DIR, "*.png")
    for f in glob.glob(pattern):
        try:
            os.remove(f)
            print(f"Deleted old screenshot: {os.path.basename(f)}")
        except Exception as e:
            print(f"Could not delete {f}: {e}")

def generate_and_render_dossier():
    print("\nGenerating Phase 5 Regulatory Dossier PDF from backend...")
    res = requests.get(
        "http://127.0.0.1:8000/api/incidents/INC-2026-001/dossier?include_fssai=true&operator_name=Chief+Safety+Officer",
        timeout=30
    )
    if res.status_code != 200:
        raise RuntimeError(f"Dossier generation failed: {res.status_code} {res.text}")

    pdf_path = os.path.join(ARTIFACT_DIR, "LOTLINE-RECALL-DOSSIER-INC-2026-001.pdf")
    with open(pdf_path, "wb") as f:
        f.write(res.content)
    print(f"Saved PDF to {pdf_path} ({len(res.content)} bytes)")

    # Render pages with pymupdf
    doc = pymupdf.open(pdf_path)
    print(f"Rendering {doc.page_count} PDF dossier pages to PNG...")
    for idx, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        out_name = f"lotline_phase5_dossier_page_{idx + 1}.png"
        pix.save(os.path.join(ARTIFACT_DIR, out_name))
        print(f"Rendered {out_name}")

def capture_ui_evidence():
    print("\nLaunching Playwright Chromium for UI evidence capture...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Desktop 1920x1080 - Overview Dashboard
        ctx_desktop = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = ctx_desktop.new_page()
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(2)
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_desktop_overview_1920.png"), full_page=False)
        print("Captured desktop overview 1920x1080")

        # 2. Tablet 1024x768 - Overview Dashboard
        ctx_tablet = browser.new_context(viewport={"width": 1024, "height": 768})
        page_tab = ctx_tablet.new_page()
        page_tab.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(1.5)
        page_tab.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_tablet_overview_1024.png"), full_page=False)
        print("Captured tablet overview 1024x768")

        # 3. Mobile 390x844 - Overview Dashboard
        ctx_mobile = browser.new_context(viewport={"width": 390, "height": 844})
        page_mob = ctx_mobile.new_page()
        page_mob.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(1.5)
        page_mob.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_mobile_overview_390.png"), full_page=False)
        print("Captured mobile overview 390x844")

        # 4. Desktop - Switch to Recall Control Tower
        print("Switching to Recall Control Tower on Desktop...")
        control_tower_btn = page.locator("button:has-text('RECALL CONTROL TOWER')").first
        if control_tower_btn.is_visible():
            control_tower_btn.click()
            time.sleep(2)

            # Tab 1: Mass Reconciliation
            page.locator("button[data-tab-id='reconciliation']").first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_mass_reconciliation.png"), full_page=False)
            print("Captured Control Tower Tab 1 (Mass Reconciliation)")

            # Tab 2: Consignee Comms
            page.locator("button[data-tab-id='communications']").first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_communications.png"), full_page=False)
            print("Captured Control Tower Tab 2 (Consignee Comms)")

            # Tab 3: Logistics Interception
            page.locator("button[data-tab-id='logistics']").first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_logistics.png"), full_page=False)
            print("Captured Control Tower Tab 3 (Logistics Interception)")

            # Tab 4: Recovery Reconciliation
            page.locator("button[data-tab-id='recoveries']").first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_recovery.png"), full_page=False)
            print("Captured Control Tower Tab 4 (Recovery Reconciliation)")

            # Tab 5: Product Disposition
            page.locator("button[data-tab-id='dispositions']").first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_dispositions.png"), full_page=False)
            print("Captured Control Tower Tab 5 (Product Disposition)")

            # Tab 6: FSSAI FoSCoS Tracker
            page.locator("button[data-tab-id='fssai']").first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_fssai_tracker.png"), full_page=False)
            print("Captured Control Tower Tab 6 (FSSAI FoSCoS Tracker)")

            # Tab 7: Effectiveness & Closure
            page.locator("button[data-tab-id='effectiveness']").first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_closure_blockers.png"), full_page=False)
            print("Captured Control Tower Tab 7 (Effectiveness & Closure)")

        # 5. Mobile Control Tower (390x844)
        print("Switching to Mobile Control Tower...")
        menu_btn = page_mob.locator("button[aria-label='Toggle Navigation Menu']").first
        if menu_btn.is_visible():
            menu_btn.click()
            time.sleep(0.5)
            mob_ctrl_btn = page_mob.locator("div.xl\\:hidden button:has-text('CONTROL TOWER')").first
            if mob_ctrl_btn.is_visible():
                mob_ctrl_btn.click()
                time.sleep(2)
                page_mob.screenshot(path=os.path.join(ARTIFACT_DIR, "lotline_phase5_control_tower_mobile_390.png"), full_page=False)
                print("Captured mobile Control Tower 390x844")

        browser.close()
        print("\nAll Phase 5 evidence screenshots successfully captured!")

if __name__ == "__main__":
    clean_previous_screenshots()
    generate_and_render_dossier()
    capture_ui_evidence()
