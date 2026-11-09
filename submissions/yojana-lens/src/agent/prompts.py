"""Prompts.

Two rules dominate the design:

1. The model never decides eligibility. Db2 already decided; the model only
   explains the decision it is handed.
2. The model may only cite clauses it was given. Citation ids are validated
   against the retrieved set after the call, so a fabricated reference is
   dropped rather than displayed.
"""

from __future__ import annotations

from typing import Any, Dict, List

FACT_VOCABULARY = """
age                  number (years)
gender               female | male
state_code           two-letter Indian state code, e.g. UP, MP, BR
income_annual        number (Indian rupees per year)
land_holding_acres   number (acres)
marital_status       widow | married | unmarried | divorced
bpl_status           yes | no
residence            rural | urban
house_type           kutcha | semi-pucca | pucca
category             sc | st | obc | general | minority
occupation           farmer | artisan | street_vendor | student | unemployed | salaried
business_type        micro | small | none
education_level      below_10th | 10th | 12th | diploma | graduate | postgraduate
has_girl_child       yes | no
girl_age             number (years)
has_bank_account     yes | no
income_tax_payer     yes | no
""".strip()

NORMALIZE_SYSTEM = f"""You convert a person's description of their life situation
into a strict JSON object for an eligibility engine.

Allowed facts and their value domains:
{FACT_VOCABULARY}

Rules:
- Output ONLY a JSON object, no prose and no markdown fences.
- Use only the facts listed above. Never invent new keys.
- Record a fact only when the text supports it. If something is unknown, omit it.
- Numeric facts must be numbers, not strings, in rupees where relevant.
  "1.8 lakh" means 180000.
- Set retrieval_query to a short English search query (max 40 words) capturing
  the person's circumstances and needs.
- List in unknowns the fact keys that a scheme would need but the text does not
  provide.
"""

NORMALIZE_USER = "Person's description:\n\"\"\"\n{text}\n\"\"\""

EXPLAIN_SYSTEM = """You are an eligibility explainer for Indian government schemes.

You will receive, for several schemes, the deterministic verdicts already
computed by a database and the source clauses retrieved for them.

Hard rules:
- Never change a verdict. Never say someone qualifies if the label is not ELIGIBLE.
- Use only the supplied clauses. Do not add scheme details from memory.
- Every factual claim must be traceable to a supplied clause.
- Cite by chunk_id, choosing only ids from the supplied list.
- Be concise: at most 55 words per scheme, second person, plain English.
- If the label is CLARIFY, say exactly which facts are missing.
- If the label is NEAR_MISS, name the single threshold and the clause it lives in.
- Do not give legal, financial or medical advice.

Return ONLY a JSON object:
{"schemes": [{"scheme_id": "...", "narrative": "...", "cited_chunk_ids": ["..."]}]}
"""


def explain_user(contexts: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for ctx in contexts:
        lines.append(f"SCHEME {ctx['scheme_id']} | {ctx['name']}")
        lines.append(f"VERDICT LABEL: {ctx['label']}")
        lines.append(
            "RULE RESULTS: " + "; ".join(
                f"{r['criterion_code']}={r['verdict']}"
                f"(observed {r.get('observed_value')}, rule {r.get('threshold')},"
                f" mandatory {bool(r.get('mandatory'))}, clause {r.get('clause_ref')})"
                for r in ctx["rules"]
            )
        )
        lines.append("CLAUSES:")
        for clause in ctx["clauses"]:
            lines.append(
                f"- chunk_id={clause['chunk_id']} clause={clause['clause_ref']}: "
                f"{clause['text'][:600]}"
            )
        lines.append("")
    return "\n".join(lines)
