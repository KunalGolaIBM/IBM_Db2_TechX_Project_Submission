# Verification, Screenshots & Visual Proof: BAKEBOX Choco AI

This directory documents execution traces, architectural flow, and visual verification screenshots demonstrating the real-world deployment, IBM Db2 database integration, and autonomous customer support capabilities of **BAKEBOX - CHOCO AI**.

A full interactive video walkthrough demonstrating the live queries, order tracking, and cake recommendation cards is available on YouTube:  
**[Watch Video Walkthrough (YouTube)](https://youtu.be/NLrRq6FX358?si=oZM-EGpaBt4AOSVM)**

---

## 1. Visual Verification & Production Screenshots

### 1.1 IBM Db2 Live Database & Vector Store Verification
#### `01_ibm_db2_extension_tables.png`
![IBM Db2 Developer Extension](01_ibm_db2_extension_tables.png)

> [!NOTE]
> **Storefront Prototype Screenshots vs Evaluated Backend Submission Scope:**  
> Screenshots `01`–`11` were captured from the broader **BAKEBOX 2.0 React + FastAPI Full-Stack Prototype** shown in our YouTube walkthrough.
> This self-contained hackathon submission (`submissions/bakebox-choco-ai/`) packages the complete verified **IBM Db2 12.1 backend, AI/RAG engine, REST API (`10` routes + `/demo` playground), RBAC SQL scripts, `15`-SKU catalog (`25` knowledge nodes), and `79`-test suite (`78` offline + `1` opt-in live-Db2 smoke test)**:
> - **Verified Submission Schema (`src/ingest.py`):** `BB_CHUNKS_VECTOR` (`DB2LlamaVS`), `BB_ORDERS` + `BB_ORDER_ITEMS` (`FK_BB_ORDER ON DELETE CASCADE`), `BB_CAKES`, `BB_INVENTORY`, `BB_RECIPES`, `BB_INGREDIENT_COMPONENTS`, `BB_AUDIT_LOG`, `BB_USER_CONVERSATION_BUFFER`, views `V_ACTIVE_BAKERY_ORDERS` & `V_MASKED_BAKERY_ORDERS`, sequence `SEQ_BB_ORDER_ID`, and SQL PL `SP_RESERVE_CAKE_STOCK`.

- **Component:** IBM Db2 Developer Extension in Visual Studio Code (Prototype Schema Snapshot).
- **Connection:** Live instance connected at `localhost@IBMDB201`.
- **Database Objects Highlighted in Prototype Capture:** Active relational catalog, order line items, conversation history buffer, and dense vector chunks (`METADATA_JSON` / vector embeddings).

---

### 1.2 Customer Storefront & Catalog Experience (Full-Stack Prototype)
#### `07_storefront_catalog_overview.png`
![Storefront Catalog Overview](07_storefront_catalog_overview.png)
- **Component:** Companion React 18 Storefront UI (`BAKEBOX AI 2.0` external prototype repo).
- **Operational Capabilities:** Branch indicators (*Branch 1: Bhagel Chaupal, Khatoti Kua (Mathura) | Branch 2: Gosna (Mathura)*), 3–4 hours fresh-bake badge, Pure Veg Khoaa Eggless indicator, and truffle/KitKat/specialty tiers.
- **Note on Submission Dataset:** `submissions/bakebox-choco-ai/data/sample_catalog.json` includes **15 curated SKUs** spanning *Red Velvet, Black Forest, Pineapple, Strawberry, Belgian Chocolate Truffle, KitKat Border, Butterscotch, and Oven Fresh Patties* (+ 3 supplementary cake nodes + 7 policy chunks = **25 Db2 RAG nodes**).

#### `09_product_catalog_grid_actions.png`
![Product Catalog Grid Actions](09_product_catalog_grid_actions.png)
- **Component:** Strawberry Collection Catalog Grid with Direct **Ask CHOCO** & Cart Actions in the companion prototype storefront (`BB-STR-04-05kg`, ₹299.0).

---

### 1.3 Autonomous Master Baker & AI Advisory (CHOCO AI)
#### `10_ask_choco_contextual_query.png`
![Ask CHOCO Contextual Query](10_ask_choco_contextual_query.png)
- **Component:** 1-Click Contextual Cake Advisory Trigger.
- **Action:** Clicking "Ask CHOCO" on a cake card auto-injects the exact cake name, SKU ID (`BB-STR-04-05kg`), flavor, and weight into the chat session, displaying the real-time reasoning state: *"CHOCO master baker is retrieving catalog & reasoning..."*.

#### `11_choco_master_baker_recommendation.png`
![CHOCO Master Baker Recommendation](11_choco_master_baker_recommendation.png)
- **Component:** CHOCO AI Precision Recommendation Response.
- **Output:** Generates a warm, bilingual (Hinglish/English) recommendation detailing SKU verification, recommended party size (4-6 people), transparent pricing (₹299.00), base customizations (100% Pure Khoaa/Mawa eggless base), and visual design features directly retrieved from Db2 hybrid RAG.

---

### 1.4 Live Order Tracking & Transactional Db2 Queries
#### `02_choco_order_status_confirmed.png`
![CHOCO Order Status Confirmed](02_choco_order_status_confirmed.png)
- **Component:** Live Order Tracking via Agentic Tool Calling (Prototype UI Capture).
- **User Query:** *"Order #1104 what was the order status of this order id ."*
- **Prototype Capture Output:** Displays `BB_ORDERS` / `BB_ORDER_ITEMS` status (`CONFIRMED`, `Strawberry Sweet Berry Glaze`, test account *A**** j** / `+91 ******3653 (Masked)`).
- **Submitted API / Fixture Behavior:** In `submissions/bakebox-choco-ai/data/sample_orders.json`, `#1104` uses offline fixture *Pooja Verma* (`Black Forest Classic Cherry Gateau`), protected at the backend boundary by 2FA phone verification and automatic PII masking (`P**** V****`, `+91 ******3344`).

#### `03_choco_order_status_delivered.png`
![CHOCO Order Status Delivered](03_choco_order_status_delivered.png)
- **Component:** Real-Time Order Lifecycle Updates.
- **User Query:** *"Order #1104 new status"*
- **Resolution:** Live synchronization with IBM Db2 reflects status change from `CONFIRMED` to `DELIVERED`, confirming safe hand-off to the customer's delivery address in Mathura.

---

### 1.5 Intelligent Customer Care & Policy Resolution
#### `04_choco_happiness_guarantee_support.png`
![Happiness Guarantee Support](04_choco_happiness_guarantee_support.png)
- **Component:** Damaged Order Resolution & Emotional Alignment.
- **User Query:** *"the order i got is damaged help me ."*
- **Policy Retrieval:** CHOCO AI instantly references the bakery's *Celebration Happiness Guarantee & Replacement Policy* from unstructured document embeddings in Db2 to offer 100% Free Re-bake or Instant Full Refund without human escalation.

#### `08_refund_replacement_resolution.png`
![Refund & Replacement Resolution](08_refund_replacement_resolution.png)
- **Component:** Refund Procedure Guidance.
- **User Query:** *"i got previous was damaged how i raise refund ."*
- **Resolution:** Step-by-step instructions (photo verification within 2 hours via Store Support Helpline `+91 ******1210`) with priority re-baking dispatch within 60-90 minutes; backend refund claims enforce 2FA phone matching and HMAC-SHA256 `BB_AUDIT_LOG` entries.

---

### 1.6 Role-Based Access Control & Operations Management
#### `05_bakebox_auth_role_modal.png`
![BAKEBOX Authentication Role Modal](05_bakebox_auth_role_modal.png)
- **Component:** Multi-Role Authentication Modal.
- **Roles:** Demonstrates role-based access control with one-click demo credentials for **Customer Demo**, **Super Admin**, and **Store Operator**.

#### `06_operator_login.png`
![Store Operator Login](06_operator_login.png)
- **Component:** Store Operator Authentication.
- **Role:** Authenticates operator account (`operator@bakebox.in`) to manage kitchen workflows, live baking queues, and branch dispatch synchronization.

---

## 2. Terminal Verification: Db2 Vector & Relational Ingestion
```text
==================================================================
BAKEBOX CHOCO AI — IBM Db2 DATA INGESTION PIPELINE
==================================================================
Step 1: Setting up IBM Db2 Relational Schema, Indexes, Views & Stored Procedure...
  -> Table BB_ORDERS created successfully.
  -> Table BB_ORDER_ITEMS created successfully.
  -> Table BB_CAKES created successfully.
  -> Table BB_INVENTORY created successfully.
  -> Table BB_RECIPES created successfully.
  -> Table BB_INGREDIENT_COMPONENTS created successfully.
  -> Table BB_AUDIT_LOG created successfully.
  -> Table BB_USER_CONVERSATION_BUFFER created successfully.
  -> View V_ACTIVE_BAKERY_ORDERS created successfully.
  -> View V_MASKED_BAKERY_ORDERS created successfully.
  -> Index IDX_BB_ORDER_PHONE created successfully.
  -> Index IDX_BB_ITEM_ORDER created successfully.
  -> Index IDX_BB_CAKE_SKU created successfully.
  -> Index IDX_BB_AUDIT_PREV created successfully.
  -> Index IDX_BB_AUDIT_CURR created successfully.
  -> Index IDX_BB_RECIPE_CAKE created successfully.
  -> Index IDX_BB_COMP_PARENT created successfully.
  -> Index IDX_BB_BUF_SESSION created successfully.
  -> Sequence SEQ_BB_ORDER_ID created successfully.
  -> Stored Procedure SP_RESERVE_CAKE_STOCK created successfully.

Step 2: Loading embedding engine 'BAAI/bge-small-en-v1.5'...

Step 3: Generating 384-dimensional dense vectors for knowledge corpus...
  -> Generated embeddings for 25 knowledge nodes.

Step 4: Idempotently syncing vectors into 'BB_CHUNKS_VECTOR'...
  -> Ingestion complete!
```

---

## 3. Terminal Verification: Agentic Query Engine & 2FA Privacy Flow
```text
=== SESSION 1: Recommendation ===
INTENT: CAKE_RECOMMENDATION | CARDS: 3
Radhe Radhe ji! Shri Ram Baker's BAKEBOX mein aapka swagat hai!

Aapki celebration ke liye hamare paas 3 fresh live options available hain:
• Red Velvet Berry Fantasy (₹649.0, 1.0kg)
• Red Velvet Heart Love Affair (₹649.0, 1.0kg)
• Red Velvet Crimson Crumb Crown (₹649.0, 1.0kg)

Hamare paas 100% Pure Veg (Khoaa Eggless) aur Egg-based dono base options available hain. Aap apni dietary preference ke mutabiq order customize kar sakte hain (fresh baking wait time: 3-4 ghante)!

=== SESSION 2: Order Challenge ===
INTENT: ORDER_AUTH_REQUIRED | CARDS: 0
Radhe Radhe ji! Customer data privacy & security policy ke mutabiq, Order #1002 ka live status access karne ke liye kripya apna registered 10-digit mobile number sath mein provide karein.

=== SESSION 2: Authenticated Tracking ===
INTENT: ORDER_TRACKING | CARDS: 0
Radhe Radhe ji! Shri Ram Baker's BAKEBOX mein aapka swagat hai!

Humne aapke order ki live details IBM Db2 se verify kar li hain:
• Order ID: #1002 (Customer: R**** S*****)
• Status: BAKING
• Items: 1x Red Velvet Heart Love Affair (1.0kg, Khoaa (Eggless))
• Delivery Destination: ***, Mathura, UP (Confidential)

Shri Ram Baker par har cake order par live fresh bake hota hai (standard 3-4 ghante wait time) to ensure 100% purity and taste!
```

---

## 4. Automated Test Suite Execution
```bash
python -m unittest discover -s submissions/bakebox-choco-ai/tests -v
```
- **Total Suites Executed:** 7 test modules (`test_audit_chain.py`, `test_guardrails_and_api.py`, `test_live_db2_smoke.py`, `test_order_concurrency.py`, `test_retrieval.py`, `test_rrf_fusion.py`, `test_session_memory.py`).
- **Result:** `Ran 79 tests in ~46s — OK (skipped=1)` — `78` automated tests passed offline (`0` failures, `0` errors) + `1` opt-in live-Db2 smoke test (`test_live_db2_smoke.py`, auto-executed when `.env` configures live IBM Db2) covering ACID row locks, quantity-scaled BOM CTEs, `SEQ_BB_ORDER_ID`, single-UOW rollback integrity, keyed HMAC-SHA256 audit tampering & concurrency, Gemini 1.5 Flash 5-tool schemas & isolation, 3-Way RRF, Hinglish CRAG, Db2 session hydration, Self-RAG, FastAPI `TestClient` routes (`X-Operator-Key` & HTTP 400 validation), IP+order brute-force 2FA lockout, and prompt-injection defense.
