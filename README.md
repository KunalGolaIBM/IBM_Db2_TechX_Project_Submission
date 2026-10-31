# Digital Suraksha / Digital Rakshak

A local FastAPI starter application with:
1. File Inspector
2. Link Inspector
3. Scam Message Detector
4. Media Scam Detector (basic media/container checks; not a deepfake classifier)
5. Login and Registration with profile photo upload
6. Scam Recovery Assistant with official India complaint links and step-by-step guidance

## Run locally
Use Python 3.10+ (Python 3.11 or 3.12 is recommended).

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs

## Important limitations and safety
- Risk scores are heuristic indicators, not a guarantee that content is safe or malicious.
- The Media Scam Detector in this starter only checks file/container characteristics. It does NOT determine whether a voice/video is AI-generated. A real deepfake detector requires a separately evaluated model and dataset.
- Phone OTP verification is not active. Configure an SMS provider and server-side verification before production.
- The app is a local prototype. Before public deployment, add HTTPS, CSRF protections where applicable, rate limits, email verification, secure session cookies, account recovery, audit logging, file-type/content validation, malware scanning, and production database migrations.
- Never store real secrets in source code. Do not upload sensitive files unless you understand how the app handles them.
- Scam recovery links point to official Indian portals; confirm the domain before entering personal information. For urgent online financial fraud in India, call 1930 promptly.
