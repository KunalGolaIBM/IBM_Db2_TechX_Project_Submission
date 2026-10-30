# BAKEBOX-AI: AUTONOMOUS AI Bakery Management AND CUSTOMER SUPPORT

> **One-Line Pitch:** An enterprise autonomous AI bakery management system and intelligent customer support platform powered by **CHOCO AI** — leveraging IBM Db2 hybrid database (relational + native vector search via `DB2LlamaVS`), LlamaIndex Advanced RAG with Reciprocal Rank Fusion (RRF), and real-time agentic tool calling for 24/7 intelligent customer engagement.

---

## Table of Contents
- [BAKEBOX - CHOCO AI: Dual-Perspective Overview](#bakebox---choco-ai-dual-perspective-overview-users--management)
- [1. The Core Problem Statement: Dual-Perspective Challenges](#1-the-core-problem-statement-dual-perspective-challenges)
- [2. How CHOCO AI Solves Both Perspectives](#2-how-choco-ai-solves-both-perspectives)
- [3. Technical Architecture & Tech Stack](#3-technical-architecture--tech-stack)
- [4. Key Architectural Highlights](#4-key-architectural-highlights)
- [IBM Db2 Integration](#ibm-db2-integration)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Demo & Links](#demo--links)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)
- [License](#license)

---

## BAKEBOX - CHOCO AI: Dual-Perspective Overview (Users & Management)

### 1. The Core Problem Statement: Dual-Perspective Challenges

Traditional bakeries and food delivery platforms struggle with significant communication and operational gaps that negatively impact both customers and business management:

#### Customer-Facing Pain Points:
- **Information Hesitation:** Customers frequently hesitate or feel awkward asking detailed questions about product specs, precise ingredients, allergen details, custom sizing, or tailored cake recommendations.
- **Operational & Discount Blind Spots:** Real-time order status tracking, delivery updates, account balances, and available discounts are often locked behind clunky interfaces or delayed support. Furthermore, customers miss out on great active coupons or ideal product suggestions simply because they aren't visible or proactively recommended.
- **Customer Care Availability Gaps:** Live customer support drops off drastically after 9 PM, leaving late-night craving inquiries, urgent modifications, and order tracking completely unaddressed.

#### Management & Business-Facing Pain Points:
- **Lost Sales & Conversion Bottlenecks:** Because human customer support agents are unavailable after hours or overwhelmed during peak times, businesses fail to capture high-intent late-night orders and inquiries.
- **Missed Upselling Opportunities:** Traditional menus and static interfaces cannot proactively recommend the right cake or apply the best available coupons based on a customer's specific preference or budget, resulting in missed revenue.
- **Operational Inefficiencies:** Managing inquiries about inventory, active coupons, and order statuses manually drains staff bandwidth and increases response latency.

---

### 2. How CHOCO AI Solves Both Perspectives

When users interact with CHOCO AI, the platform bridges the gap completely for both sides:

#### For the User (Seamless, Hesitation-Free Experience):
- **Instant 24/7 Access:** Available around the clock (even post-9 PM) for late-night queries, live order tracking, and account balance checks.
- **Personalized Product & Coupon Discovery:** Users can ask about any cake, ingredient, or custom requirement without hesitation. CHOCO AI actively suggests the best-fit cakes and ensures they never miss out on active coupons or discounts.
- **Rich, Interactive Responses:** Through agentic tools that render structured JSON, users receive interactive product cards and recommendations rather than plain text, making the buying experience smooth and engaging (supporting both Hindi and English).

#### For the Management (Automated Operations & Scalability):
- **Autonomous 24/7 Conversion Engine:** Acts as an around-the-clock sales and support agent, capturing leads and answering inquiries even when physical shop operations or human support teams are offline.
- **Intelligent Data Retrieval:** Automatically queries the hybrid database (relational tables and PDFs via IBM DB2) to fetch exact product data, inventory status, and user records instantly.
- **Zero Data Compromise:** Built with strict session isolation and dedicated buffer memory to ensure user safety, data privacy, and secure business operations at all times.

---

### 3. Technical Architecture & Tech Stack

The architecture is built for high performance, precision retrieval, and zero-cost local embedding generation to handle real-time inventory updates without latency.

- **Database & Storage:** IBM DB2 (managed via the VS Code extension), utilizing a hybrid database structure that unifies both unstructured documents (PDFs) and structured relational tables.
- **Backend Framework:** FastAPI microservices architecture delivering high-throughput, asynchronous API endpoints.
- **Frontend:** React 18 + Vite providing a highly responsive, clean, and interactive user interface optimized for fast interaction.
- **AI & RAG Pipeline:**
  - **Orchestration Framework:** LlamaIndex configured to build robust, end-to-end ingestion and query pipelines.
  - **Retrieval Strategy:** Advanced RAG utilizing Reciprocal Rank Fusion (RRF) combined with fixed-size chunking (where individual nodes represent precise table rows or document sections) to guarantee pin-point retrieval accuracy across dynamic product inventories.
  - **Embeddings:** Hugging Face (BAAI/bge-large) model running locally/freely for rapid embedding generation. This bypasses external API rate limits and costs, ensuring newly added cakes or products are embedded and searchable instantly.
  - **LLM Engine:** Gemini 3.8 Flash powering fast, cost-effective, and intelligent text generation and reasoning.
  - **Vector Operations:** IBM DB2 Vector Store integration via `DB2LlamaVS` for efficient similarity search across the hybrid database.

---

### 4. Key Architectural Highlights

- **Hybrid Data Handling:** Seamlessly queries across structured relational tables (inventory, balances, order statuses) and unstructured documents (manuals, policy PDFs) using IBM DB2.
- **Zero-Latency Ingestion:** Local free embedding generation allows instant indexing of newly added bakery products without depending on external embedding services.
- **Rich UI Rendering:** Agentic tool responses output structured JSON, allowing the React + Vite frontend to render visually engaging product cards and suggestions instantly.
- **Bilingual Capability:** Native support for both Hindi and English interactions to match local customer demographics seamlessly.

---

## IBM Db2 Integration

- **Db2 Edition & Environment:** IBM Db2 Community Edition (Docker / VS Code Extension Instance `IBMDB201` on Port 50000).
- **Connector / Driver Used:** Official Python drivers `ibm_db` and `ibm_db_dbi`, and official LlamaIndex vector store connector `llama-index-vector-stores-db2` (`DB2LlamaVS`).
- **Database Schema / Data Models:**
  - `BB_CHUNKS_VECTOR`: Native vector table created via `DB2LlamaVS` for storing dense embeddings with schema `(id VARCHAR(64) PRIMARY KEY, doc_id VARCHAR(64), embedding vector, node_info BLOB, metadata BLOB, text CLOB)`.
  - `BB_ORDERS`: Relational order table `(order_id INT PRIMARY KEY, user_id INT, customer_name, customer_phone, order_type, order_status, total_amount, delivery_address, special_notes)`.
  - `BB_ORDER_ITEMS`: Relational line items `(item_id INT IDENTITY, order_id INT, sku_id, item_name, quantity, unit_price, cake_base, cake_weight, custom_message)`.
- **Key Queries & Operations:**
  - In-engine Cosine distance similarity search via `DB2LlamaVS.query()`.
  - Transactional relational order retrieval joining `BB_ORDERS` and `BB_ORDER_ITEMS`.

---

## Prerequisites
- Python >= 3.10
- Running local IBM Db2 instance (e.g. `localhost:50000`, database `IBMDB201`)
- Node.js >= 18 (for running the frontend)

---

## Setup & Installation

```bash
# 1. Navigate to submission directory
cd submissions/bakebox-choco-ai

# 2. Install required dependencies
pip install llama-index-core llama-index-vector-stores-db2 ibm-db fastembed scikit-learn
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your Db2 credentials:

```bash
cp .env.example .env
```

```env
DB2_HOST=127.0.0.1
DB2_PORT=50000
DB2_DATABASE=IBMDB201
DB2_USER=your_db2_user
DB2_PASSWORD=your_db2_password
GEMINI_API_KEY=your_gemini_api_key
```

> **Security Warning:** Never commit `.env` or any real API keys or database passwords to Git!

---

## Running the Project

### 1. Ingest Data & Initialize Db2 Native Vector Store
```bash
python submissions/bakebox-choco-ai/src/ingest.py
```
*Creates relational tables `BB_ORDERS`, `BB_ORDER_ITEMS` and ingests dense vectors into `BB_CHUNKS_VECTOR` via `DB2LlamaVS`.*

### 2. Execute Interactive Query Engine
```bash
python submissions/bakebox-choco-ai/src/query_engine.py
```

---

## Testing & Verification

Reviewers can verify the submission folder structure and metadata:

```bash
# Run official hackathon validator
python scripts/validate_submission.py submissions/bakebox-choco-ai
```

**Expected Output:**
```text
Validating 1 submission folder(s)...
Checking: submissions/bakebox-choco-ai
  ✅ PASSED all validation checks.
==================================================
ALL VALIDATION CHECKS PASSED.
```

---

## Demo & Links

- **Demo Video (YouTube):** [https://youtu.be/MvH82OEsDUA?si=nVuy2awvxKJAaZkV](https://youtu.be/MvH82OEsDUA?si=nVuy2awvxKJAaZkV)
- **LinkedIn Post:** [https://lnkd.in/p/gtXgu6wq](https://lnkd.in/p/gtXgu6wq)
- **Source Repository:** [https://github.com/AYUSHDHANGAR/IBM_Db2_TechX_Project_Submission](https://github.com/AYUSHDHANGAR/IBM_Db2_TechX_Project_Submission)

---

## Known Limitations & Future Roadmap
- **Current Limitations:** Vector embeddings currently run on CPU; GPU acceleration can further reduce batch embedding latency.
- **Future Roadmap:**
  - **Inbuilt Payment & Checkout:** Direct UPI/Card gateway integration with instant digital invoices and live order status updates in IBM Db2 (`BB_ORDERS`).
  - **Ultra-Fast Query Engine:** Multi-tier caching on top of IBM Db2 native vector retrieval for sub-100ms catalog and product query responses.
  - **Multi-Branch Kitchen Balancing:** Real-time order routing and kitchen workload balancing across Mathura, Vrindavan, and Govardhan branches based on oven capacity.
  - **Predictive Inventory Forecasting:** AI-driven demand forecasting on historical Db2 order data to optimize daily fresh baking and reduce ingredient waste.

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Ayush Dhangar | [@AYUSHDHANGAR](https://github.com/AYUSHDHANGAR) | BTech CSE-AIML, 4th Year · Ex-Intern Pantech Prolab Pvt Ltd · Full-Stack Architect, IBM Db2 Integration, Hybrid RAG Pipeline |

---

## License

Distributed under the MIT License. Built for the IBM Db2 TechX Summit 2026.
