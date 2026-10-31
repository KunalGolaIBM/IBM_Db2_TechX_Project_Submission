from fastapi import APIRouter
router = APIRouter()

PORTALS = [
    {
        "name": "National Cyber Crime Reporting Portal",
        "url": "https://cybercrime.gov.in/",
        "when_to_use": "Report online financial fraud, phishing, social-media abuse, and other cybercrime.",
        "steps": ["Open the official portal and choose the relevant complaint category.",
                  "Read the instructions and provide accurate incident details.",
                  "Keep transaction IDs, phone numbers, URLs, screenshots, and other evidence.",
                  "Save the acknowledgement/reference number after submission."]
    },
    {
        "name": "Cyber financial fraud helpline (India)",
        "url": "https://www.cybercrime.gov.in/",
        "when_to_use": "For urgent suspected online financial fraud, contact India's 1930 helpline as soon as possible and also file the online report.",
        "steps": ["Call 1930 promptly if money has been lost to online financial fraud.",
                  "Keep bank/wallet name, transaction reference, amount, time, and registered mobile ready.",
                  "Follow the instructions provided by the official helpline.",
                  "Complete the related online complaint and save the acknowledgement."]
    },
    {
        "name": "Reserve Bank of India",
        "url": "https://www.rbi.org.in/",
        "when_to_use": "For official banking guidance and escalation information; first raise a complaint with your bank.",
        "steps": ["Contact your bank using the number on its official website or card.",
                  "Report unauthorized transactions and request the bank's complaint reference.",
                  "If the issue remains unresolved, review the RBI's official complaint/escalation process."]
    },
    {
        "name": "National Consumer Helpline",
        "url": "https://consumerhelpline.gov.in/",
        "when_to_use": "Consumer disputes involving goods or services.",
        "steps": ["Open the official consumer helpline website.",
                  "Register with accurate contact and purchase details.",
                  "Attach receipts, order details, messages, and the seller's information.",
                  "Save the complaint number for follow-up."]
    }
]

@router.get("/resources")
async def resources():
    return {"title": "Scam Recovery Assistant", "notice": "Use only official portals. Never pay an agent promising guaranteed recovery, and never share OTP, PIN, password, or remote-access codes.", "resources": PORTALS}

@router.get("/guide/{portal_key}")
async def guide(portal_key: str):
    mapping = {
        "cybercrime": PORTALS[0],
        "financial-fraud": PORTALS[1],
        "rbi": PORTALS[2],
        "consumer": PORTALS[3]
    }
    item = mapping.get(portal_key)
    if not item:
        return {"error": "Unknown guide", "available": list(mapping)}
    return item
