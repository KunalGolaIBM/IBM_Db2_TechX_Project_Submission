"""AI part of Khata AI (LangChain + Gemini).

The AI is used for two things only:
  1. understanding a Hindi/Hinglish sentence and turning it into a structured entry
  2. writing a polite reminder message
If no API key is set (or the AI call fails), a simple offline fallback is used,
so the app never completely stops working.
"""
import os
import re
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class LedgerEntry(BaseModel):
    name: str = Field(description="Customer name exactly as written, e.g. 'Sharma ji'")
    amount: float = Field(description="Amount in rupees as a number")
    entry_type: Literal["UDHAAR", "PAYMENT"] = Field(
        description="UDHAAR if the customer took goods/money on credit, "
        "PAYMENT if the customer paid money back"
    )
    note: Optional[str] = Field(default=None, description="Items or reason, short, or null")


def _get_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        temperature=0,
    )


def ai_available():
    return bool(os.getenv("GOOGLE_API_KEY"))


# ---------------------------------------------------------------- offline fallback
PAYMENT_WORDS = (
    "wapas", "vapas", "lauta", "chukaya", "chuka", "jama", "paid",
    "payment", "repaid", "returned", "clear",
)


def _fallback_parse(text):
    t = text.strip()
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", t)
    if not m:
        raise ValueError("Amount nahi mila. Example: 'Sharma ji ne 200 ka udhaar liya'")
    amount = float(m.group(1).replace(",", ""))

    name_match = re.match(r"^(?:maine\s+)?(.+?)\s+(?:ne|ko)\s+", t, flags=re.IGNORECASE)
    name = name_match.group(1) if name_match else t[: m.start()].strip(" ,")
    if not name:
        raise ValueError("Naam nahi mila. Example: 'Sharma ji ne 200 ka udhaar liya'")

    lower = t.lower()
    entry_type = "PAYMENT" if any(w in lower for w in PAYMENT_WORDS) else "UDHAAR"

    parts = re.split(r",(?!\d)", t, maxsplit=1)  # ignore commas inside numbers like 1,200
    note = parts[1].strip() if len(parts) > 1 else None
    return LedgerEntry(name=name, amount=amount, entry_type=entry_type, note=note or None)


# ---------------------------------------------------------------- public functions
def parse_entry(text):
    """Return (LedgerEntry, source_label)."""
    if ai_available():
        try:
            from langchain_core.prompts import ChatPromptTemplate

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You read entries written by an Indian shopkeeper in Hindi, Hinglish "
                        "or English for a credit ledger (khata). Extract the customer name, "
                        "the amount in rupees, whether it is UDHAAR (customer took goods or "
                        "money on credit) or PAYMENT (customer paid money back), and a short "
                        "note about the items. If the sentence mentions repaying / wapas / "
                        "chukaya / jama, it is PAYMENT.",
                    ),
                    ("human", "{text}"),
                ]
            )
            chain = prompt | _get_llm().with_structured_output(LedgerEntry)
            result = chain.invoke({"text": text})
            if result is not None and result.amount > 0 and result.name.strip():
                return result, "AI (Gemini via LangChain)"
        except Exception as err:  # noqa: BLE001 - we want to fall back on any AI error
            print(f"[AI error, using offline parser instead: {err}]")
    return _fallback_parse(text), "offline parser"


def write_reminder(name, balance, days_old):
    """Polite Hinglish WhatsApp reminder."""
    default = (
        f"Namaste {name} ji, aapka Rs {balance:.0f} ka khata baaki hai "
        f"(lagbhag {days_old} din purana). Jab suvidha ho, kripya chuka dein. Dhanyavaad! 🙏"
    )
    if not ai_available():
        return default
    try:
        prompt = (
            f"Write a short, polite, friendly WhatsApp reminder in Hinglish from a shopkeeper "
            f"to customer '{name}' whose Rs {balance:.0f} credit has been pending for "
            f"{days_old} days. Under 40 words, no pressure or threats, end with thanks. "
            f"Return only the message."
        )
        content = _get_llm().invoke(prompt).content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return content.strip() or default
    except Exception as err:  # noqa: BLE001
        print(f"[AI error, using template reminder instead: {err}]")
        return default
