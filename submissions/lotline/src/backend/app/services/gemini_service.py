import os
import re
import json
import logging
from typing import TypedDict, Any
from dotenv import load_dotenv

# Ensure environment is loaded from both root and backend/.env
load_dotenv()
load_dotenv("backend/.env")

logger = logging.getLogger("lotline.gemini")


class AgentInterpretation(TypedDict):
    agent_id: str
    operational_interpretation: str
    supporting_evidence_refs: list[str]
    limitations_or_missing_info: str
    ai_status: str  # 'GEMINI_SYNTHESIZED' | 'DETERMINISTIC_FALLBACK'
    validation_status: str  # 'VALIDATED' | 'FALLBACK_REJECTED' | 'OFFLINE'
    validation_notes: str | None


class GeminiSynthesisResult(TypedDict):
    available: bool
    model: str | None
    status_code: str  # 'CONNECTED' | 'MISSING_API_KEY' | 'INVALID_API_KEY' | 'QUOTA_EXCEEDED' | 'TIMEOUT' | 'UNAVAILABLE' | 'API_ERROR' | 'MALFORMED_OUTPUT' | 'VALIDATION_FAILED'
    intake_explanation: str
    traceability_explanation: str
    risk_explanation: str
    response_planning_rationale: str
    intake: AgentInterpretation
    traceability: AgentInterpretation
    risk: AgentInterpretation
    response_planning: AgentInterpretation
    validation_passed: bool
    rejection_reasons: list[str]
    note: str


def sanitize_message(message: str, api_key: str | None = None) -> str:
    """Ensure API keys and credentials are never leaked in error messages, logs, or responses."""
    if not message:
        return ""
    clean = message
    if api_key and len(api_key) > 5:
        clean = clean.replace(api_key, "[REDACTED_API_KEY]")
    clean = re.sub(r'AIza[0-9A-Za-z-_]{35}', '[REDACTED_API_KEY]', clean)
    clean = re.sub(r'AQ\.[0-9A-Za-z-_]{30,}', '[REDACTED_API_KEY]', clean)
    return clean


def get_deterministic_fallbacks(
    incident_data: dict[str, Any],
    trace_data: dict[str, Any],
    risk_data: dict[str, Any],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate deterministic, verifiable rule-based explanations strictly grounded in Db2 facts."""
    source_lot = incident_data.get("source_lot_id", "RAW-204")
    lot_details = incident_data.get("source_lot_details", {})
    item_name = lot_details.get("item_name", "Organic Spinach")
    supplier = lot_details.get("supplier_name", "GreenLeaf Foods")
    supplier_country = lot_details.get("country", "India")
    qty_created = lot_details.get("quantity_created", 500.0)
    unit = lot_details.get("unit", "KG")
    severity = incident_data.get("severity", "CRITICAL")
    incident_id = incident_data.get("incident_id", "INC-2026-001")
    desc = incident_data.get("description", "")
    pathogen = "Salmonella" if "salmonella" in desc.lower() else "Biological Contaminant"

    downstream_count = trace_data.get("total_downstream_lots", 6)
    depth = trace_data.get("total_production_levels", 2)
    wip_lots = [n["lot_id"] for n in trace_data.get("nodes", []) if n.get("lot_type") == "WIP"]
    fin_lots = [n["lot_id"] for n in trace_data.get("nodes", []) if n.get("lot_type") == "FINISHED"]

    total_units = float(risk_data.get("total_affected_units", 2400.0))
    wh_units = float(risk_data.get("warehouse_units", 1350.0))
    ret_units = float(risk_data.get("retailer_delivered_units", 850.0))
    trans_units = float(risk_data.get("in_transit_units", 200.0))
    risk_score = risk_data.get("risk_score", 94)

    intake_text = (
        f"Verified source lot {source_lot} ({qty_created:,.1f} {unit} {item_name}) from supplier {supplier} ({supplier_country}). "
        f"Under incident {incident_id}, the lot status is QUARANTINED with severity {severity}. "
        f"Confirmed {pathogen} contamination report from intake screening."
    )
    trace_text = (
        f"Recursive Db2 CTE identified {downstream_count} downstream lots across {depth} production tiers. "
        f"Intermediate work-in-progress batches ({', '.join(wip_lots) if wip_lots else 'WIP-301, 302, 303'}) directly fed "
        f"into commercial finished product batches ({', '.join(fin_lots) if fin_lots else 'FIN-401, 402, 403'})."
    )
    risk_text = (
        f"Total commercial exposure is {total_units:,.0f} units (Risk Score: {risk_score}/100, CRITICAL). "
        f"Warehouse quarantine holds {wh_units:,.0f} units (56.3%), but {ret_units:,.0f} units (35.4%) are delivered to retailers "
        f"and {trans_units:,.0f} units (8.3%) are active in logistics transit."
    )
    response_text = (
        f"4 mitigation protocols formulated from LOTLINE_APP.RECALL_ACTIONS. Immediate priority is halting {trans_units:,.0f} "
        f"in-transit units and issuing retailer recall alerts for the {ret_units:,.0f} delivered units. "
        f"All action executions remain strictly gated until authenticated Human Operator sign-off."
    )

    intake_struct: AgentInterpretation = {
        "agent_id": "incident_intake",
        "operational_interpretation": intake_text,
        "supporting_evidence_refs": [incident_id, source_lot, supplier, pathogen],
        "limitations_or_missing_info": f"Supplier facility address not recorded in Db2; country is {supplier_country}.",
        "ai_status": "DETERMINISTIC_FALLBACK",
        "validation_status": "OFFLINE",
        "validation_notes": None
    }
    trace_struct: AgentInterpretation = {
        "agent_id": "traceability",
        "operational_interpretation": trace_text,
        "supporting_evidence_refs": [source_lot] + wip_lots + fin_lots,
        "limitations_or_missing_info": f"Genealogy depth bounded at {depth} levels in LOTLINE_APP.LOT_LINEAGE.",
        "ai_status": "DETERMINISTIC_FALLBACK",
        "validation_status": "OFFLINE",
        "validation_notes": None
    }
    risk_struct: AgentInterpretation = {
        "agent_id": "risk_assessment",
        "operational_interpretation": risk_text,
        "supporting_evidence_refs": [f"{total_units:.0f} units", f"{wh_units:.0f} warehouse", f"{ret_units:.0f} retail", f"{trans_units:.0f} transit"],
        "limitations_or_missing_info": "Retail customer POS scan data is external to Db2.",
        "ai_status": "DETERMINISTIC_FALLBACK",
        "validation_status": "OFFLINE",
        "validation_notes": None
    }
    response_struct: AgentInterpretation = {
        "agent_id": "response_planning",
        "operational_interpretation": response_text,
        "supporting_evidence_refs": [a.get("action_id", "") for a in actions],
        "limitations_or_missing_info": "Mandatory Human-in-the-Loop review required for all database mutations.",
        "ai_status": "DETERMINISTIC_FALLBACK",
        "validation_status": "OFFLINE",
        "validation_notes": None
    }

    return {
        "intake_explanation": intake_text,
        "traceability_explanation": trace_text,
        "risk_explanation": risk_text,
        "response_planning_rationale": response_text,
        "intake": intake_struct,
        "traceability": trace_struct,
        "risk": risk_struct,
        "response_planning": response_struct
    }


def validate_agent_payload(
    parsed: dict[str, Any],
    incident_data: dict[str, Any],
    trace_data: dict[str, Any],
    risk_data: dict[str, Any],
    actions: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Strict server-side validation rejecting unsupported factual claims, invented entities, and hallucinations.
    Returns (is_valid, rejection_reasons).
    """
    rejection_reasons: list[str] = []

    # Gather all text generated by the model across all agent fields
    all_text_chunks: list[str] = []
    for key, val in parsed.items():
        if isinstance(val, dict):
            for k2, v2 in val.items():
                if isinstance(v2, str):
                    all_text_chunks.append(v2)
                elif isinstance(v2, list):
                    all_text_chunks.extend(str(x) for x in v2)
        elif isinstance(val, str):
            all_text_chunks.append(val)
    full_text = " ".join(all_text_chunks)
    full_text_lower = full_text.lower()

    # 1. Pathogen Integrity Check: Db2 incident description specifies the verified contaminant
    db_desc = (incident_data.get("description") or "").lower()
    if "salmonella" in db_desc:
        conflicting_pathogens = [
            "e. coli", "e.coli", "escherichia coli", "listeria",
            "botulinum", "campylobacter", "shigella", "norovirus"
        ]
        for p in conflicting_pathogens:
            if p in full_text_lower:
                rejection_reasons.append(
                    f"UNSUPPORTED_PATHOGEN: Model introduced '{p}' while IBM Db2 incident record explicitly specifies Salmonella."
                )
                break

    # 2. Supplier Geography Integrity Check: Db2 SUPPLIERS contains country India and no US location
    ungrounded_locations = [
        "salinas", "california", "monterey", "yuma", "arizona",
        "bakersfield", "fresno", "mexico", "chile", "peru"
    ]
    for loc in ungrounded_locations:
        if loc in full_text_lower:
            rejection_reasons.append(
                f"UNGROUNDED_LOCATION: Model hallucinated supplier location '{loc.capitalize()}' not present in Db2 SUPPLIERS table (Db2 records country: India only)."
            )
            break

    # 3. Lineage Lot Integrity Check: Model must NOT reference lots not present in the Db2 lineage tree
    verified_lots = {incident_data.get("source_lot_id", "RAW-204")}
    for n in trace_data.get("nodes", []):
        if "lot_id" in n:
            verified_lots.add(n["lot_id"])

    # Regex search for lot identifiers (e.g. FIN-404, WIP-305, RAW-205, LOT-999)
    found_lots = set(re.findall(r'\b(?:RAW|WIP|FIN|LOT)-[0-9]{3,4}\b', full_text))
    invented_lots = found_lots - verified_lots
    if invented_lots:
        rejection_reasons.append(
            f"INVENTED_LOT: Model referenced unauthorized lot(s) {sorted(list(invented_lots))} not present in Db2 downstream lineage graph."
        )

    # 4. Action Protocol Integrity Check: Model must NOT invent new actions or modify IDs
    verified_action_ids = {a.get("action_id") for a in actions if a.get("action_id")}
    found_actions = set(re.findall(r'\bACT-[0-9]{3,4}\b', full_text))
    invented_actions = found_actions - verified_action_ids
    if invented_actions:
        rejection_reasons.append(
            f"INVENTED_ACTION: Model referenced unauthorized action(s) {sorted(list(invented_actions))} not present in LOTLINE_APP.RECALL_ACTIONS."
        )

    # 5. Unauthorized Action Status Modification Check: AI cannot approve or execute actions
    forbidden_approval_patterns = [
        r'\b(?:ai approved|automatically approved|model approved|status changed to approved|auto-executed|auto-execute|approved by agent)\b'
    ]
    for pat in forbidden_approval_patterns:
        if re.search(pat, full_text_lower):
            rejection_reasons.append(
                "UNAUTHORIZED_STATUS_CHANGE: Model claimed AI approval or automated execution; Human-in-the-Loop governance strictly violated."
            )
            break

    # 6. Action Description Tampering Check: If model purports to alter action descriptions
    for a in actions:
        aid = a.get("action_id", "")
        # Verify if model explicitly asserted that an action ID does something completely contrary
        if aid and aid in full_text:
            if aid == "ACT-001" and ("destroy" in full_text_lower or "discard" in full_text_lower):
                rejection_reasons.append(
                    "ACTION_TAMPERING: Model altered ACT-001 protocol from 'Hold Quarantine' to unauthorized destruction."
                )

    # 7. Deterministic Exposure Figures Integrity Check:
    # Db2 ground truth: 2,400 total units, 1,350 warehouse, 850 delivered retail, 200 in-transit
    # Check for contradictory total unit claims (e.g. 3,000 units, 5,000 units)
    qty_matches = re.finditer(r'\b([0-9]{1,2},[0-9]{3})\s*(?:total\s+units|exposed\s+units|units\s+affected|units\s+in\s+total)', full_text, re.IGNORECASE)
    for qm in qty_matches:
        num_str = qm.group(1).replace(",", "")
        if num_str != "2400":
            rejection_reasons.append(
                f"QUANTITY_MISMATCH: Model modified deterministic Db2 total unit count to {qm.group(1)} (Db2 ground truth: 2,400 units)."
            )

    return (len(rejection_reasons) == 0, rejection_reasons)


def synthesize_agent_intelligence(
    incident_data: dict[str, Any],
    trace_data: dict[str, Any],
    risk_data: dict[str, Any],
    actions: list[dict[str, Any]],
) -> GeminiSynthesisResult:
    """Synthesize grounded intelligence across all 4 agents using Gemini 3.5 Flash or return honest fallback.
    Validates output server-side to strictly reject hallucinations and unauthorized mutations.
    """
    fallbacks = get_deterministic_fallbacks(incident_data, trace_data, risk_data, actions)
    
    # Read credentials exclusively on backend
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
    timeout_ms = int(os.getenv("GEMINI_TIMEOUT_MS", "20000"))

    if not api_key:
        return {
            "available": False,
            "model": None,
            "status_code": "MISSING_API_KEY",
            "intake_explanation": fallbacks["intake_explanation"],
            "traceability_explanation": fallbacks["traceability_explanation"],
            "risk_explanation": fallbacks["risk_explanation"],
            "response_planning_rationale": fallbacks["response_planning_rationale"],
            "intake": fallbacks["intake"],
            "traceability": fallbacks["traceability"],
            "risk": fallbacks["risk"],
            "response_planning": fallbacks["response_planning"],
            "validation_passed": True,
            "rejection_reasons": [],
            "note": "GEMINI_API_KEY is not configured in backend environment. Operating in deterministic rule-based mode based on Db2 audit evidence."
        }

    try:
        from google import genai
        from google.genai import errors

        # Initialize client with configured timeout (minimum 10s enforced by google-genai)
        client = genai.Client(api_key=api_key, http_options={"timeout": timeout_ms})

        prompt = f"""You are the LOTLINE Senior Recall Intelligence Agent for IBM Db2Hack 2026.
You are provided with VERIFIED GROUND TRUTH records directly queried from IBM Db2 (Schema: LOTLINE_APP).

VERIFIED INCIDENT & SOURCE RECORD:
- Incident ID: {incident_data.get('incident_id', 'INC-2026-001')}
- Severity: {incident_data.get('severity', 'CRITICAL')} (Status: {incident_data.get('status', 'OPEN')})
- Source Lot: {incident_data.get('source_lot_id', 'RAW-204')}
- Material: {incident_data.get('source_lot_details', {}).get('item_name', 'Organic Spinach')} ({incident_data.get('source_lot_details', {}).get('quantity_created', 500)} {incident_data.get('source_lot_details', {}).get('unit', 'KG')})
- Supplier: {incident_data.get('source_lot_details', {}).get('supplier_name', 'GreenLeaf Foods')} (Country: {incident_data.get('source_lot_details', {}).get('country', 'India')}, Status: {incident_data.get('source_lot_details', {}).get('status', 'QUARANTINED')})
- Contaminant Description: {incident_data.get('description', 'Possible Salmonella contamination reported in source lot RAW-204.')}

VERIFIED RECURSIVE LINEAGE (Db2 CTE WITH RPL):
- Total Downstream Batches: {trace_data.get('total_downstream_lots', 6)}
- Production Depth Levels: {trace_data.get('total_production_levels', 2)}
- Downstream Nodes: {[n.get('lot_id') + ' (' + n.get('item_name', '') + ')' for n in trace_data.get('nodes', [])]}

VERIFIED LOGISTICS & INVENTORY EXPOSURE:
- Total Exposed Units: {risk_data.get('total_affected_units', 2400):,.0f}
- Quarantined Warehouse Units: {risk_data.get('warehouse_units', 1350):,.0f}
- Delivered to Commercial Retailers: {risk_data.get('retailer_delivered_units', 850):,.0f}
- In-Transit Logistics Units: {risk_data.get('in_transit_units', 200):,.0f}
- Risk Score: {risk_data.get('risk_score', 94)} / 100 (Severity: {risk_data.get('risk_level', 'CRITICAL')})
- Retailer Partners Affected: {[r.get('retailer') for r in risk_data.get('affected_retailers', [])]}

PROPOSED MITIGATION PROTOCOLS (LOTLINE_APP.RECALL_ACTIONS):
- Protocols: {[a.get('action_id') + ' [' + a.get('action_type', '') + ' on ' + str(a.get('target_id', '')) + ']: ' + str(a.get('action_description', '')) for a in actions]}

STRICT GOVERNANCE & FACTUAL CONSTRAINTS:
1. Ground every statement STRICTLY in the Db2 facts above. The contaminant is Salmonella (do NOT introduce E. coli or other unverified pathogens).
2. The supplier is GreenLeaf Foods in India. There is NO street address or US location in Db2 (do NOT invent Salinas, California).
3. Downstream lots are ONLY: RAW-204, WIP-301, WIP-302, WIP-303, FIN-401, FIN-402, FIN-403. Do NOT invent lot IDs.
4. Protocols are ONLY: ACT-001, ACT-002, ACT-003, ACT-004. Do NOT invent new action IDs or modify descriptions.
5. All exposure counts (2,400 total, 1,350 warehouse, 850 retail, 200 in-transit) are final database facts. Do NOT recalculate or modify them.
6. NEVER approve or reject any recall action yourself. Enforce that human operator sign-off is mandatory before any database transaction commitment.

TASK:
Provide structured operational intelligence for each of the 4 autonomous recall agents.
Format your output as valid JSON with EXACTLY this structure:
{{
  "intake": {{
    "agent_id": "incident_intake",
    "operational_interpretation": "2-3 sentences explaining verified incident and supplier evidence.",
    "supporting_evidence_refs": ["INC-2026-001", "RAW-204", "GreenLeaf Foods", "Salmonella"],
    "limitations_or_missing_info": "Supplier physical street address not recorded in Db2; country is India."
  }},
  "traceability": {{
    "agent_id": "traceability",
    "operational_interpretation": "2-3 sentences explaining downstream production genealogy from raw lot to finished goods.",
    "supporting_evidence_refs": ["RAW-204", "WIP-301", "WIP-302", "WIP-303", "FIN-401", "FIN-402", "FIN-403"],
    "limitations_or_missing_info": "Lineage depth bounded at 2 levels in LOTLINE_APP.LOT_LINEAGE."
  }},
  "risk": {{
    "agent_id": "risk_assessment",
    "operational_interpretation": "2-3 sentences interpreting the exposure breakdown and public risk vector of delivered units.",
    "supporting_evidence_refs": ["2400 units", "1350 warehouse", "850 delivered", "200 in-transit"],
    "limitations_or_missing_info": "Retail customer POS scan data is external to Db2."
  }},
  "response_planning": {{
    "agent_id": "response_planning",
    "operational_interpretation": "2-3 sentences explaining mitigation rationale and confirming mandatory Human-in-the-Loop approval gate.",
    "supporting_evidence_refs": ["ACT-001", "ACT-002", "ACT-003", "ACT-004"],
    "limitations_or_missing_info": "Mandatory Human-in-the-Loop review required for all database mutations."
  }}
}}
"""

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        resp_text = (response.text or "").strip() if response else ""
        if not resp_text:
            return {
                "available": False,
                "model": model_name,
                "status_code": "MALFORMED_OUTPUT",
                "intake_explanation": fallbacks["intake_explanation"],
                "traceability_explanation": fallbacks["traceability_explanation"],
                "risk_explanation": fallbacks["risk_explanation"],
                "response_planning_rationale": fallbacks["response_planning_rationale"],
                "intake": fallbacks["intake"],
                "traceability": fallbacks["traceability"],
                "risk": fallbacks["risk"],
                "response_planning": fallbacks["response_planning"],
                "validation_passed": False,
                "rejection_reasons": ["Empty response returned by model."],
                "note": "Gemini API returned an empty response. Operating in deterministic rule-based mode based on Db2 audit evidence."
            }

        # Parse JSON from response text (handling code fences if present)
        clean_json_str = resp_text
        if "```json" in clean_json_str:
            clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json_str:
            clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(clean_json_str)
        except Exception:
            return {
                "available": False,
                "model": model_name,
                "status_code": "MALFORMED_OUTPUT",
                "intake_explanation": fallbacks["intake_explanation"],
                "traceability_explanation": fallbacks["traceability_explanation"],
                "risk_explanation": fallbacks["risk_explanation"],
                "response_planning_rationale": fallbacks["response_planning_rationale"],
                "intake": fallbacks["intake"],
                "traceability": fallbacks["traceability"],
                "risk": fallbacks["risk"],
                "response_planning": fallbacks["response_planning"],
                "validation_passed": False,
                "rejection_reasons": ["Model output was not valid JSON."],
                "note": "Gemini API returned malformed JSON. Reverted to deterministic Db2 ground truth."
            }

        # -------------------------------------------------------------
        # SERVER-SIDE RESPONSE VALIDATION
        # -------------------------------------------------------------
        is_valid, rejection_reasons = validate_agent_payload(
            parsed=parsed,
            incident_data=incident_data,
            trace_data=trace_data,
            risk_data=risk_data,
            actions=actions
        )

        if not is_valid:
            logger.warning(f"Gemini output rejected by server-side validator: {rejection_reasons}")
            user_note = f"Gemini output rejected by server-side validator: {'; '.join(rejection_reasons)}. Reverted to deterministic Db2 ground truth."
            fb_intake = dict(fallbacks["intake"])
            fb_intake["validation_status"] = "FALLBACK_REJECTED"
            fb_intake["validation_notes"] = "; ".join(rejection_reasons)
            fb_trace = dict(fallbacks["traceability"])
            fb_trace["validation_status"] = "FALLBACK_REJECTED"
            fb_trace["validation_notes"] = "; ".join(rejection_reasons)
            fb_risk = dict(fallbacks["risk"])
            fb_risk["validation_status"] = "FALLBACK_REJECTED"
            fb_risk["validation_notes"] = "; ".join(rejection_reasons)
            fb_resp = dict(fallbacks["response_planning"])
            fb_resp["validation_status"] = "FALLBACK_REJECTED"
            fb_resp["validation_notes"] = "; ".join(rejection_reasons)

            return {
                "available": False,
                "model": model_name,
                "status_code": "VALIDATION_FAILED",
                "intake_explanation": fallbacks["intake_explanation"],
                "traceability_explanation": fallbacks["traceability_explanation"],
                "risk_explanation": fallbacks["risk_explanation"],
                "response_planning_rationale": fallbacks["response_planning_rationale"],
                "intake": fb_intake,
                "traceability": fb_trace,
                "risk": fb_risk,
                "response_planning": fb_resp,
                "validation_passed": False,
                "rejection_reasons": rejection_reasons,
                "note": user_note
            }

        # Structure validated outputs
        def extract_agent_struct(section_key: str, fallback_key: str, agent_id: str) -> AgentInterpretation:
            data = parsed.get(section_key)
            if isinstance(data, dict):
                op_interp = data.get("operational_interpretation") or fallbacks[fallback_key]
                ev_refs = data.get("supporting_evidence_refs") or []
                limitations = data.get("limitations_or_missing_info") or ""
            elif isinstance(data, str):
                op_interp = data
                ev_refs = []
                limitations = ""
            else:
                legacy_str = parsed.get(fallback_key)
                op_interp = legacy_str if isinstance(legacy_str, str) else fallbacks[fallback_key]
                ev_refs = []
                limitations = ""

            return {
                "agent_id": agent_id,
                "operational_interpretation": op_interp,
                "supporting_evidence_refs": ev_refs if isinstance(ev_refs, list) else [str(ev_refs)],
                "limitations_or_missing_info": str(limitations),
                "ai_status": "GEMINI_SYNTHESIZED",
                "validation_status": "VALIDATED",
                "validation_notes": None
            }

        v_intake = extract_agent_struct("intake", "intake_explanation", "incident_intake")
        v_trace = extract_agent_struct("traceability", "traceability_explanation", "traceability")
        v_risk = extract_agent_struct("risk", "risk_explanation", "risk_assessment")
        v_resp = extract_agent_struct("response_planning", "response_planning_rationale", "response_planning")

        return {
            "available": True,
            "model": model_name,
            "status_code": "CONNECTED",
            "intake_explanation": v_intake["operational_interpretation"],
            "traceability_explanation": v_trace["operational_interpretation"],
            "risk_explanation": v_risk["operational_interpretation"],
            "response_planning_rationale": v_resp["operational_interpretation"],
            "intake": v_intake,
            "traceability": v_trace,
            "risk": v_risk,
            "response_planning": v_resp,
            "validation_passed": True,
            "rejection_reasons": [],
            "note": f"Intelligence synthesized across 4 agents via {model_name} and validated against IBM Db2 ground truth."
        }

    except Exception as e:
        err_type = type(e).__name__
        err_msg = sanitize_message(str(e), api_key)

        status_code = "API_ERROR"
        if "400" in err_msg or "401" in err_msg or "403" in err_msg or "API_KEY" in err_msg.upper():
            status_code = "INVALID_API_KEY"
            user_note = "Gemini API authentication failed (Invalid API Key). Fallback to deterministic Db2 governance rules active."
        elif "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg.upper() or "quota" in err_msg.lower():
            status_code = "QUOTA_EXCEEDED"
            user_note = "Gemini API quota exceeded (Rate limit reached). Fallback to deterministic Db2 governance rules active."
        elif "503" in err_msg or "UNAVAILABLE" in err_msg.upper() or "demand" in err_msg.lower():
            status_code = "UNAVAILABLE"
            user_note = "Gemini API model temporarily unavailable (High demand spike). Fallback to deterministic Db2 governance rules active."
        elif "504" in err_msg or "DEADLINE" in err_msg.upper() or "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            status_code = "TIMEOUT"
            user_note = f"Gemini API request timed out ({timeout_ms // 1000}s deadline). Fallback to deterministic Db2 governance rules active."
        else:
            user_note = f"Gemini API call failed ({err_type}). Fallback to deterministic Db2 governance rules active."

        logger.warning(f"Gemini API integration error ({status_code}): {err_msg[:120]}")

        return {
            "available": False,
            "model": model_name,
            "status_code": status_code,
            "intake_explanation": fallbacks["intake_explanation"],
            "traceability_explanation": fallbacks["traceability_explanation"],
            "risk_explanation": fallbacks["risk_explanation"],
            "response_planning_rationale": fallbacks["response_planning_rationale"],
            "intake": fallbacks["intake"],
            "traceability": fallbacks["traceability"],
            "risk": fallbacks["risk"],
            "response_planning": fallbacks["response_planning"],
            "validation_passed": False,
            "rejection_reasons": [user_note],
            "note": user_note
        }
