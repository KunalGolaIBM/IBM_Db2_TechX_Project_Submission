# Voice RAG in Hindi and English: Multilingual Audio Search with Db2 Vectors

Ask a question in Hindi or English about a spoken talk. Db2 returns the matching transcript chunks, and each result shows the audio file and the time range it came from.

## How Db2 is used
- `VECTOR(768, FLOAT32)` column and `VECTOR_DISTANCE(..., COSINE)` (Db2 12.1.2+).
- One table holds Hindi and English chunks in the same vector space, with `language`, `source`, `start` and `end` stored as JSON metadata.
- Connector: `ibm-db-haystack` (`IBMDb2DocumentStore`, `IBMDb2EmbeddingRetriever`) over `ibm_db`.

## Prerequisites
- Python 3.10+
- IBM Db2 12.1.2 or later, reachable over TCP/IP, with a user that can create tables
- Ollama with `qwen2.5:7b` (not needed with `--no-llm`)

## Setup
```bash
cd submissions/db2-multilingual-voice-rag
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r src/requirements.txt
cp .env.example .env     # set DB2_HOST, DB2_PORT, DB2_DB, DB2_USERNAME, DB2_PASSWORD
```

## Run
```bash
cd src
python index.py                                                     # writes 16 chunks to table voice_kb
python query.py "Which distance metrics does Db2 support?"
python query.py "Db2 में कौन से डिस्टेंस मीट्रिक उपलब्ध हैं?"
python query.py --no-llm "फ़िल्टर कहाँ चलता है, डेटाबेस के अंदर या बाहर?"   # retrieval only
```
Each result line shows the score, audio file, start and end seconds, and language.

## Data
- `src/audio/talk_en.mp3` and `src/audio/talk_hi.mp3`: a short talk on Db2 vector search in each language (text in `src/scripts/`).
- `src/transcripts/*.json`: Whisper `medium` transcripts with timestamps, used by `index.py`.

To regenerate the transcripts from the audio (needs `ffmpeg` on `PATH`):
```bash
pip install -r src/requirements-transcribe.txt
cd src && python transcribe.py medium
```

## Check the data in Db2
```sql
SELECT id, JSON_VALUE(SYSTOOLS.BSON2JSON(meta), '$.source' RETURNING VARCHAR(100)) AS source,
       JSON_VALUE(SYSTOOLS.BSON2JSON(meta), '$.start' RETURNING VARCHAR(20)) AS start_s
FROM voice_kb ORDER BY id;
```

## Tests
```bash
pip install pytest && python -m pytest tests -q
```
`tests/test_retrieval.py` checks that chunks keep their audio file and time range, and that Hindi and English questions rank the matching transcript chunk in the top 3. It does not need a database.

## Dependency licenses
| Package / model | License |
|---|---|
| haystack-ai, ibm-db-haystack, ibm_db, sentence-transformers | Apache-2.0 |
| openai-whisper | MIT |
| intfloat/multilingual-e5-base | MIT |
