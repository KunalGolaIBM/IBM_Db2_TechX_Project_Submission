# KisanRakshak AI

This project is a small, self-contained Python prototype showing how IBM Db2 can power an AI-based crop advisory system.

## Setup

```bash
cd submissions/kisanrakshak-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/main.py
```

## Features

- Reads field and crop conditions from IBM Db2.
- Produces advisory recommendations based on crop risk patterns.
- Uses an LLM-style reasoning flow for contextual suggestions.
- Can be extended into a Streamlit dashboard or FastAPI API.

## Notes

This project is designed for hackathon submission and demonstration. Replace the sample placeholders with real IBM Db2 credentials and tune the prompts for actual field data.
