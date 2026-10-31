from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from urllib.parse import urlparse
import ipaddress
import re
from common import MAX_URL_LENGTH, make_report

router = APIRouter()

class LinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=MAX_URL_LENGTH)

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "rb.gy", "shorturl.at"}
SUSPICIOUS_TERMS = {"login", "verify", "account", "password", "wallet", "claim", "prize", "urgent", "kyc", "refund", "gift"}

@router.post("/scan-link")
async def scan_link(body: LinkRequest):
    raw = body.url.strip()
    candidate = raw if "://" in raw else "https://" + raw
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "Please enter a valid URL or domain.")
    score, findings = 0, []
    if parsed.scheme != "https":
        score += 15
        findings.append("URL does not use HTTPS.")
    if parsed.username or parsed.password:
        score += 35
        findings.append("URL contains embedded username/password credentials.")
    try:
        ipaddress.ip_address(host.strip("[]"))
        score += 25
        findings.append("The hostname is an IP address rather than a normal domain.")
    except ValueError:
        pass
    if "xn--" in host:
        score += 25
        findings.append("Internationalized/punycode domain; verify spelling carefully.")
    if host in SHORTENERS or any(host.endswith("." + d) for d in SHORTENERS):
        score += 20
        findings.append("URL uses a known link-shortening domain, which hides the destination.")
    if len(host.split(".")) >= 5:
        score += 10
        findings.append("Unusually deep subdomain structure.")
    if re.search(r"(@|%40)", raw):
        score += 15
        findings.append("Contains an @ character or encoded equivalent that may confuse URL reading.")
    matched = sorted(t for t in SUSPICIOUS_TERMS if t in (parsed.path + "?" + parsed.query).lower())
    if matched:
        score += min(25, 5 * len(matched))
        findings.append("Urgency/account-related terms in URL path or query: " + ", ".join(matched))
    if not findings:
        findings.append("No rule-based URL warning was triggered.")
    report = make_report("Link Inspector", min(score, 100), findings,
        "This scanner checks URL patterns only; it does not browse the destination or guarantee reputation.")
    report["normalized_url"] = candidate
    report["hostname"] = host
    return report
