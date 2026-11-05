"""
Gramin Mitra (ग्रामीण मित्र) - Rural Conversational AI Agent for Kisan Mitra
Specially designed for illiterate and neo-literate farmers.
Features:
- Translates bureaucratic guidelines and SQL market numbers into simple, conversational village Hindi (ग्राम चौपाल शैली).
- Uses everyday analogies, avoids complex English/administrative jargon.
- Formats answers into short, memorable voice-ready bullet points.
- Prepares clean text for Web Speech API text-to-speech narration (ध्वनि उच्चारण).
"""

import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.llm import get_llm

RURAL_SIMPLIFIER_PROMPT = """आप 'ग्रामीण मित्र' (Gramin Mitra) हैं - एक बहुत ही सरल, आत्मीय और मददगार गांव के साथी।
आपका काम है कि किसान भाइयों को, जो शायद ज्यादा पढ़े-लिखे नहीं हैं, बिल्कुल अपनी देसी बोलचाल की भाषा में बात समझाएं।

नियम (Rules for Rural Explanations):
1. **भाषा**: सरल, व्यावहारिक हिंदी और बोलचाल की भाषा (देहाती/ग्रामीण टच)।
2. **कठिन शब्दों से बचें**:
   - 'अपात्रता' की जगह बोलें: 'किन भाइयों को पैसा नहीं मिलेगा'
   - 'संवितरण / DBT' की जगह बोलें: 'सीधे आपके बैंक खाते में'
   - 'दिशानिर्देश' की जगह बोलें: 'सरकारी नियम'
   - 'अधिसूचित' की जगह बोलें: 'सरकारी लिस्ट में शामिल'
   - 'दावा / Intimation' की जगह बोलें: 'नुकसान की सूचना'
   - 'संस्थागत भूमिधारक' की जगह बोलें: 'कंपनी, ट्रस्ट या स्कूल की जमीन'
3. **कम शब्दों में मुख्य बात**: केवल 2 या 3 मुख्य बातें बताएं, ताकि किसान भाई सुनकर आसानी से याद रख सकें।
4. **स्पष्ट रुपए और समय**: रुपए (उदा. ₹6,000, ₹2,000, 4% ब्याज) और समय सीमा (उदा. 72 घंटे यानी 3 दिन) बहुत साफ-साफ बताएं।
5. **आगे क्या करना है (Actionable Advice)**: अंत में एक लाइन में बताएं कि किसान भाई को अब क्या करना चाहिए (उदा. 'अपने लेखपाल या बैंक शाखा में मिलें' या '14447 पर फोन मिलाएं')।
"""

# Common colloquial rural expressions mapped to standard intents
COLLOQUIAL_MAPPINGS = {
    "khet me paani": "fasal bima inundation claim",
    "paani bhar gya": "fasal bima flood damage",
    "ola gira": "fasal bima hailstorm damage",
    "fasal mar gayi": "fasal bima claim process",
    "barish se nuksan": "fasal bima weather loss 72 hours",
    "6000 wali kist": "pm-kisan installment rules",
    "chhe hazar kab": "pm-kisan status",
    "karza chahiye": "kcc loan application",
    "byaj kitna": "kcc interest rate 4%",
    "bina jameen loan": "kcc collateral free limit",
    "gay bhains loan": "kcc animal husbandry dairy limit",
    "aaj ka bhav": "mandi price today",
    "kitne me bik rha": "mandi modal price",
}

class RuralConversationalAgent:
    """Agent that adapts responses for simple audio narration and rural farmers."""

    def __init__(self):
        self.llm = get_llm(temperature=0.2)

    def normalize_rural_query(self, query: str) -> str:
        """
        Normalizes colloquial rural phrases (e.g. 'khet me paani bhar gaya')
        into search-friendly queries while preserving intent.
        """
        q_clean = query.strip()
        q_lower = q_clean.lower()
        for phrase, mapped in COLLOQUIAL_MAPPINGS.items():
            if phrase in q_lower:
                return f"{q_clean} ({mapped})"
        return q_clean

    def simplify_for_farmer(self, question: str, technical_answer: str, context_type: str = "general") -> str:
        """
        Takes technical/bureaucratic answer and transforms it into warm,
        plain-language village Hindi suitable for reading aloud or audio playback.
        """
        messages = [
            SystemMessage(content=RURAL_SIMPLIFIER_PROMPT),
            HumanMessage(content=(
                f"किसान भाई का प्रश्न: {question}\n"
                f"तकनीकी जानकारी: {technical_answer}\n\n"
                f"इसे किसान भाई के लिए 2-3 बहुत ही सरल और स्पष्ट बुलेट बिंदुओं में समझाइए:"
            ))
        ]

        try:
            res = self.llm.invoke(messages)
            simple_text = res.content.strip()
            # If model returned empty or error-like string
            if not simple_text or len(simple_text) < 10:
                simple_text = self._fallback_rural_simplify(question, technical_answer)
        except Exception:
            simple_text = self._fallback_rural_simplify(question, technical_answer)

        return simple_text

    def to_speech_text(self, markdown_text: str) -> str:
        """
        Strips markdown asterisks, bullet markers, brackets, and emojis
        so that Web Speech API (speechSynthesis) speaks smoothly and naturally in Hindi.
        """
        text = markdown_text
        # Remove markdown bold/italics
        text = re.sub(r'[*_#`]', '', text)
        # Replace bullet points with pause/comma
        text = re.sub(r'^\s*[-•]\s*', '। ', text, flags=re.MULTILINE)
        # Clean multiple spaces or newlines
        text = re.sub(r'\n+', '। ', text)
        # Remove markdown link syntax [text](url) -> text
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
        # Remove remaining symbols and normalize currency
        text = text.replace('₹', 'रुपये ')
        text = text.replace('%', ' प्रतिशत ')
        # Clean repetitive punctuation
        text = re.sub(r'[।\s]{2,}', '। ', text)
        return text.strip()

    def _fallback_rural_simplify(self, question: str, raw_answer: str) -> str:
        """Heuristic rural simplifier when offline or LLM unavailable."""
        q_lower = question.lower()
        
        if any(w in q_lower for w in ["pm-kisan", "pmkisan", "6000", "सम्मान निधि", "किस्त", "पैसा"]):
            return (
                "राम-राम किसान भाई! 🙏\n\n"
                "• **पैसा कितना मिलेगा**: हर साल **₹6,000** मिलेंगे, जो ₹2,000-₹2,000 की तीन किस्तों में सीधे आपके बैंक खाते में आएंगे।\n"
                "• **किसे नहीं मिलेगा**: जिनके परिवार में कोई सरकारी नौकरी में है, या जो इनकम टैक्स भरते हैं, उन्हें यह लाभ नहीं मिलेगा।\n"
                "• **क्या करें**: अपना आधार कार्ड बैंक खाते से लिंक (e-KYC) जरूर करवा लें।"
            )
        elif any(w in q_lower for w in ["bima", "pmfby", "nuksan", "kharab", "paani", "ola", "72", "डूबा", "ओला", "नुकसान"]):
            return (
                "किसान भाई, परेशान न हों! 🙏\n\n"
                "• **सबसे जरूरी बात**: अगर बारिश या ओले से फसल खराब हुई है, तो **3 दिन (72 घंटे) के भीतर** सूचना देना जरूरी है।\n"
                "• **कहाँ फोन करें**: तुरंत फ्री नंबर **14447** पर फोन मिलाएं या अपने कृषि अधिकारी / बैंक को बताएं।\n"
                "• **मुआवजा**: जांच के बाद नुकसान का पैसा सीधे आपके बैंक खाते में डाल दिया जाएगा।"
            )
        elif any(w in q_lower for w in ["kcc", "karza", "loan", "byaj", "credit card", "ऋण", "कर्ज", "ब्याज"]):
            return (
                "किसान भाई, KCC कार्ड की मुख्य बातें: 🙏\n\n"
                "• **ब्याज कितना लगेगा**: समय पर पैसा चुकाने पर ब्याज केवल **4% सालाना** लगेगा (बहुत ही सस्ता)।\n"
                "• **बिना गारंटी लोन**: **₹1,60,000 (1.60 लाख)** तक के लोन के लिए कोई जमीन या गारंटी नहीं लगती।\n"
                "• **पशुपालन**: गाय, भैंस या मछली पालन के लिए भी ₹2 लाख तक का कार्ड बनता है।"
            )
        elif any(w in q_lower for w in ["bhav", "price", "rate", "mandi", "aloo", "gehun", "sarson", "भाव", "मंडी", "दाम", "बिका"]):
            # Extract basic numbers if present
            return (
                "मंडी भाव की सीधी जानकारी: 🌾\n\n"
                f"{raw_answer}\n\n"
                "• **सलाह**: माल मंडी ले जाने से पहले भाव की जांच जरूर कर लें ताकि सही और पूरा दाम मिले।"
            )
        else:
            return (
                "राम-राम किसान भाई! 🙏\n\n"
                "मैं आपकी अपनी भाषा में खेती, मंडी भाव और सरकारी योजनाओं की जानकारी देने के लिए बना हूँ।\n"
                "आप सीधे बोलकर या लिखकर अपनी परेशानी बता सकते हैं।"
            )


def get_rural_agent() -> RuralConversationalAgent:
    """Factory helper for RuralConversationalAgent."""
    return RuralConversationalAgent()
