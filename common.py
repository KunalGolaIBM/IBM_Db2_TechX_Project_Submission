import hashlib
import re
from pathlib import Path

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_MEDIA_SIZE = 10 * 1024 * 1024
MAX_TEXT_LENGTH = 10000
MAX_URL_LENGTH = 2048

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def clamp_score(score: int) -> int:
    return max(0, min(100, int(score)))

def verdict_for(score: int) -> str:
    if score >= 70:
        return "High Risk"
    if score >= 35:
        return "Suspicious"
    return "Low Risk"

def make_report(module: str, score: int, findings: list[str], message: str = "") -> dict:
    score = clamp_score(score)
    return {
        "module": module,
        "status": "completed",
        "risk_score": score,
        "verdict": verdict_for(score),
        "findings": findings or ["No rule-based warning was triggered."],
        "message": message or "This is an automated risk assessment, not a guarantee of safety."
    }

def safe_filename(name: str) -> str:
    name = Path(name or "upload.bin").name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:160] or "upload.bin"
