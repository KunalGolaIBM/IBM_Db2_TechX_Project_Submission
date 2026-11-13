# Khata AI — Smart Udhaar Ledger for Small Shops

> Type a sentence like *"Sharma ji ne 200 ka udhaar liya, doodh aur bread"* and Khata AI turns it into a structured ledger entry stored in **IBM Db2**, tracks who owes what, and writes polite reminders.

## Problem

Millions of small kirana and neighbourhood shops in India still run on *udhaar* (credit), recorded on paper or in memory. Entries get lost, balances go wrong, and asking for old dues feels awkward. Existing apps need forms and menus that shopkeepers rarely use, while everyone is comfortable typing or speaking one natural sentence in Hindi/Hinglish.

## Solution

Khata AI lets the shopkeeper write entries in plain Hinglish. An LLM (via **LangChain** + Google Gemini) extracts the customer, amount, type (udhaar or payment) and note. Entries are stored in **IBM Db2**. All balances and ageing are computed by **SQL inside Db2** (never by the LLM), so the money is always exact. The AI also drafts a short, polite Hinglish WhatsApp reminder for every customer with pending dues.

## IBM Db2 integration

- Db2 Community Edition (Docker image `icr.io/db2_community/db2`) is the system of record.
- Python driver: `ibm_db` / `ibm_db_dbi`.
- Tables `customers` and `entries` are created automatically on first run.
- The pending-dues report is a single Db2 SQL query using `SUM(CASE ...)`, `GROUP BY`, `HAVING` and Db2 date arithmetic (`DAYS(CURRENT DATE) - DAYS(MIN(entry_date))`).
- See [architecture.md](architecture.md) for the schema and queries.

## AI integration

- **LangChain** (`langchain-core`, `langchain-google-genai`) with Gemini.
- `with_structured_output(...)` and a Pydantic model force the LLM to return a validated `{name, amount, entry_type, note}` object.
- If no `GOOGLE_API_KEY` is set (or the API call fails), a rule-based offline parser is used, so the app keeps working.

## Prerequisites

- Docker Desktop
- Python 3.12
- (Optional) a free Gemini API key from https://aistudio.google.com/apikey

## Setup

### 1. Start Db2

```bash
docker run -itd --name db2server --privileged=true -p 50000:50000 \
  -e LICENSE=accept -e DB2INSTANCE=db2inst1 \
  -e DB2INST1_PASSWORD=<choose-a-password> -e DBNAME=testdb \
  icr.io/db2_community/db2
```

First start takes several minutes. Wait until this prints a result:

```bash
docker logs db2server 2>&1 | grep "Setup has completed"
```

### 2. Configure

```bash
cd submissions/khata-ai
cp .env.example .env      # Windows: copy .env.example .env
```

Edit `.env` with the same password you chose, and (optionally) your Gemini key. Never commit `.env`.

### 3. Run

**Option A — Docker (most reliable, works on any OS):**

```bash
docker run -it --rm -v "$(pwd):/app" -w /app -e DB2_HOST=host.docker.internal python:3.12 bash
pip install -r src/requirements.txt
python src/app.py
```

**Option B — Local Python:**

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r src/requirements.txt
python src/app.py
```

> Troubleshooting: on one Windows 11 machine, `ibm_db` installed fine but could not open a connection natively (it returned NULL without an error). Running the app inside the Python Docker container (Option A) fixed it.

Optional web UI: `pip install streamlit pandas` then `streamlit run src/ui.py`.

## Demo

1. Menu `5` — load demo data (7 sample entries).
2. Menu `2` — pending report:

   | Customer | Balance (Rs) | Days old |
   |---|---|---|
   | Mehta ji | cleared, not listed | — |
   | Sharma ji | 100 | 45 |
   | Gupta aunty | 450 | 20 |
   | Rahul bhaiya | 80 | 7 |
   | Pooja didi | 150 | 3 |

3. Menu `1` — try: `Gupta aunty ne aaj 100 rupaye wapas kiye` (recognised as a PAYMENT).
4. Menu `4` — generate Hinglish reminders.

Screenshots are in `docs/screenshots/`.

## Project structure

```
src/
  app.py            command-line app
  db.py             Db2 connection, schema, queries
  llm.py            LangChain + Gemini (entry parsing, reminders)
  ui.py             optional Streamlit UI
  requirements.txt
```

## Limitations and future work

- Two customers with the same name are treated as one.
- Voice input (speech-to-text) for shopkeepers who prefer speaking.
- A per-customer payment-trust score from Db2 history.
- Actually sending reminders through WhatsApp.

## Team

- <Shiva Yadav> — <GL Bajaj group of institutions, 2 year>
