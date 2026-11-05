# 🎥 Kisan Mitra (किसान मित्र) - Hackathon Demo Video Script
## IBM Db2Hack 2026 (Presentation Guide: 2 to 3 Minutes)

This script is structured to demonstrate **Kisan Mitra** to hackathon judges in an engaging, crisp 2 to 3 minute video walkthrough.

---

### ⏱️ Video Timeline Overview
- **0:00 - 0:30**: Problem Statement, Architecture & Genuine IBM Db2 Integration
- **0:30 - 1:05**: Demo Question 1 & 2 (Relational Text-to-SQL on Mandi Prices)
- **1:05 - 1:45**: Demo Question 3 & 4 (Native Db2 Vector Search & Grounded RAG)
- **1:45 - 2:30**: Demo Question 5 (Hybrid Intent Orchestration: SQL + RAG)
- **2:30 - 3:00**: Security Defense-in-Depth, Summary & Submission Wrap-up

---

### 🎬 Scene-by-Scene Walkthrough

#### 1. Introduction (0:00 - 0:30)
- **Screen**: Streamlit Dashboard (`http://localhost:8501`) showing the header, live Db2 connection badge, and sidebar metrics.
- **Narrator**:
  > *"Hello judges! Welcome to **Kisan Mitra** (किसान मित्र), our submission for **IBM Db2Hack 2026**. In India, millions of farmers struggle to obtain accurate daily mandi prices and understand complex government welfare scheme guidelines in their native languages. 
  >
  > Instead of using IBM Db2 simply as plain storage, Kisan Mitra showcases Db2's full dual capabilities:
  > 1. High-performance **relational analytics** for natural language **Text-to-SQL** over daily Agmarknet mandi data.
  > 2. Native **Db2 12.1+ vector search** using the `VECTOR(384, REAL)` data type and `VECTOR_DISTANCE` with the `COSINE` metric for grounded, hallucination-free scheme advisory."*

---

#### 2. Demo Question 1: Daily Mandi Price (Text-to-SQL) (0:30 - 0:50)
- **Action**: Click the quick prompt chip or type:
  `Mathura mandi me aaj aloo ka bhav kya hai?`
- **What to point out on screen**:
  - The instant response in friendly Hinglish/Hindi explaining the potato modal price in Mathura (₹1,520/quintal).
  - Open the **"🔍 IBM Db2 SQL Query Inspector"** expander:
    - Point out the generated SQL:
      ```sql
      SELECT market, commodity, variety, arrival_date, min_price, max_price, modal_price 
      FROM MANDI_PRICES 
      WHERE state = 'Uttar Pradesh' AND district = 'Mathura' AND commodity = 'Potato' 
      ORDER BY arrival_date DESC FETCH FIRST 5 ROWS ONLY;
      ```
    - Highlight the execution latency badge (**~3 ms**).
  - Show the **interactive Plotly chart** comparing Mathura and Kosi Kalan market prices.
- **Narrator**:
  > *"Notice how the LangChain SQL agent translated the farmer's colloquial Hinglish query into optimized IBM Db2 SQL with proper date ordering and `FETCH FIRST 5 ROWS ONLY`. The query runs in under 4 milliseconds, returning tabular data and an interactive Plotly visualization."*

---

#### 3. Demo Question 2: Complex Market Aggregation (0:50 - 1:05)
- **Action**: Click or type:
  `UP me pichhle hafte sabse mehnga kaunsa anaaj tha?`
- **What to point out on screen**:
  - Point out the generated aggregation query:
    ```sql
    SELECT commodity, MAX(modal_price) AS max_price, district, market, arrival_date 
    FROM MANDI_PRICES 
    WHERE state = 'Uttar Pradesh' AND arrival_date >= CURRENT DATE - 7 DAYS 
    GROUP BY commodity, district, market, arrival_date 
    ORDER BY max_price DESC FETCH FIRST 5 ROWS ONLY;
    ```
  - Result highlights **Gram (चना) at ₹6,480/quintal in Varanasi**, followed by Kanpur and Lucknow.
- **Narrator**:
  > *"Here, Db2 executes multi-column grouping, dynamic date arithmetic (`CURRENT DATE - 7 DAYS`), and price aggregation across all Uttar Pradesh markets, demonstrating genuine relational query capabilities."*

---

#### 4. Demo Question 3: Scheme Eligibility & Exclusion (Db2 Native Vector RAG) (1:05 - 1:25)
- **Action**: Click or type:
  `PM-KISAN me kon aavedan nahi kar sakta?`
- **What to point out on screen**:
  - The answer listing the exact exclusion criteria: constitutional post holders, income tax payers, serving/retired government officers, and registered professionals (doctors, lawyers, CAs).
  - Open the **"📚 Official Government Policy Citations"** expander:
    - Show the citation card: **`PM_KISAN_Guidelines.pdf` &bull; Page 3 &bull; Cosine Distance: 0.27**.
- **Narrator**:
  > *"Now switching to policy intelligence: when asking who is ineligible for PM-KISAN, our system queries Db2's `DOC_CHUNKS` table using native `VECTOR_DISTANCE(embedding, query_vector, COSINE)`. Notice how it retrieved Page 3—the official Exclusion Criteria—with complete provenance and zero hallucination."*

---

#### 5. Demo Question 4: Localized Calamity Intimation Rule (1:25 - 1:45)
- **Action**: Click or type:
  `फसल नष्ट होने पर PMFBY में क्लेम कैसे करें?`
- **What to point out on screen**:
  - Highlight the mandatory **72-hour reporting rule**, toll-free number **14447**, and Crop Insurance App intimation.
  - Source citation: **`PMFBY_Guidelines.pdf` &bull; Page 4 &bull; Cosine Distance: 0.12**.
- **Narrator**:
  > *"For crop damage under PMFBY, the farmer is immediately alerted to the crucial 72-hour mandatory notification deadline and the 14447 helpline, directly cited from official Ministry guidelines."*

---

#### 6. Demo Question 5: Hybrid Multi-Intent Orchestration (1:45 - 2:20)
- **Action**: Click or type:
  `Agra me gehun ka kya bhav hai aur fasal kharab hone par PMFBY claim kaise karein?`
- **What to point out on screen**:
  - Show the **"Intent: HYBRID"** badge.
  - The answer cleanly synthesizes **both** sections:
    1. **🌾 Mandi Intelligence**: Agra wheat modal price (₹2,520/quintal) with SQL table & chart.
    2. **📋 Scheme Advisory**: PMFBY claim intimation steps with document citations.
- **Narrator**:
  > *"Here is the crown jewel: a composite farmer query combining both market prices and crop insurance. Our LangChain Router classifies this as HYBRID, simultaneously executing relational SQL and native vector search on IBM Db2, returning an all-in-one actionable briefing."*

---

#### 7. Gramin Mitra: Rural AI Mode & Audio Playback for Illiterate Farmers (2:20 - 2:45)
- **Action**: 
  - Point to the **"🌾 सरल ग्रामीण मोड (Farmer / Audio Mode)"** toggle in the sidebar.
  - Click on the **"▶️ चलाएं (Play)"** button next to any answer.
  - The browser reads the plain-language village bullet points aloud in Hindi.
- **Narrator**:
  > *"For millions of illiterate or neo-literate farmers who struggle with written words or administrative jargon, we created **Gramin Mitra**. It simplifies dense official guidelines into warm village language (ग्राम चौपाल शैली) and provides one-click voice narration using the Web Speech API—so farmers can simply listen and understand!"*

---

#### 8. Security & Wrap-Up (2:45 - 3:00)
- **Screen**: Sidebar Security Section & Terminal showing test pass (`35 passed`).
- **Narrator**:
  > *"Finally, security is built-in: all Text-to-SQL runs under a dedicated `kisan_ro` read-only Db2 user, strictly enforcing SELECT-only execution and blocking any DDL/DML injection. Our test suite covers 35 automated tests across Hindi, Hinglish, English, audio generation, and rural colloquial queries with a 100% pass rate.
  >
  > Kisan Mitra brings the power of **IBM Db2** directly into the hands of India's farmers. Thank you!"*
