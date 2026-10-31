import re
from faster_whisper import WhisperModel

_model = None

def get_model():
    global _model
    if _model is None:
        # "base" is fast; use "small" for better Hindi accuracy
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model

def transcribe_media(path: str) -> dict:
    try:
        segments, info = get_model().transcribe(path, beam_size=5, vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
        return {"ok": True, "text": text, "language": info.language}
    except Exception as e:
        return {"ok": False, "text": "", "language": None, "error": str(e)}

RULES = [
    (r"\b(digital arrest|cbi|customs|narcotics|police|parcel)\b", 30, "Impersonates authorities / digital arrest"),
    (r"\b(otp|cvv|pin|password)\b", 25, "Asks for OTP or sensitive codes"),
    (r"\b(kyc|account.{0,20}(blocked|suspended))\b", 20, "Fake KYC / account block threat"),
    (r"\b(lottery|kbc|prize|jackpot|you won)\b", 20, "Lottery or prize bait"),
    (r"\b(processing fee|registration fee|transfer|send money)\b", 20, "Demands money"),
    (r"\b(urgent|immediately|right now|last chance|stay on the (call|line))\b", 15, "Pressure and urgency"),
    (r"\b(anydesk|teamviewer|screen share)\b", 25, "Asks for remote access"),
    (r"\b(don'?t tell|keep (this )?secret)\b", 20, "Asks for secrecy"),
    (r"(डिजिटल अरेस्ट|गिरफ्तार|ओटीपी|केवाईसी|लॉटरी)", 30, "Scam keywords in Hindi"),
]

def analyze_transcript(text: str) -> dict:
    t = text.lower()
    score, reasons = 0, []
    for pattern, points, reason in RULES:
        if re.search(pattern, t):
            score += points
            reasons.append(reason)
    links = re.findall(r"https?://\S+", text)
    phones = re.findall(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b", text)
    if links:
        score += 10
        reasons.append("Mentions links")
    if phones:
        score += 5
        reasons.append("Mentions phone numbers")
    return {"score": min(score, 100), "reasons": reasons, "links": links, "phones": phones}