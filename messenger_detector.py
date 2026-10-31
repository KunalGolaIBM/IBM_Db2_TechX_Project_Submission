from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from common import MAX_TEXT_LENGTH, make_report

router = APIRouter()

class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)

RULES = [
    (["otp", "one time password", "verification code"], 18, "Requests or references a one-time password / verification code."),
    (["account blocked", "account suspended", "will be closed", "deactivated today"], 18, "Account-threat or urgent suspension language."),
    (["send money", "pay now", "transfer immediately", "processing fee"], 18, "Urgent payment or money-transfer language."),
    (["remote access", "install anydesk", "anydesk", "teamviewer", "screen sharing"], 22, "Remote-access or screen-sharing request."),
    (["digital arrest", "police case", "arrest warrant", "customs parcel"], 25, "Possible impersonation, intimidation, or 'digital arrest' scam language."),
    (["you won", "claim your prize", "lottery winner", "free gift"], 15, "Prize or giveaway claim language."),
    (["click this link", "verify now", "update kyc", "kyc expired"], 15, "Link-clicking or KYC-verification pressure."),
    (["bank details", "card number", "cvv", "upi pin", "pin number"], 20, "Requests sensitive financial credentials."),
    (["guaranteed profit", "double your money", "investment return"], 18, "Unrealistic investment-return claim.")
]

@router.post("/scan-message")
async def scan_message(body: MessageRequest):
    text = body.message.strip()
    if not text:
        raise HTTPException(400, "Please enter a message.")
    lower = text.lower()
    score, findings = 0, []
    for phrases, points, description in RULES:
        if any(p in lower for p in phrases):
            score += points
            findings.append(description)
    if text.count("!") >= 4:
        score += 5
        findings.append("Excessive exclamation marks may be used to create urgency.")
    if not findings:
        findings.append("No configured scam phrase was matched. Be cautious with unexpected messages.")
    return make_report("Scam Message Detector", min(score, 100), findings,
        "Rule-based text screening can miss new scams and can flag legitimate messages. Never share OTPs, PINs, or passwords.")
