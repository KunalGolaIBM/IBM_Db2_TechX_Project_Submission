"""
ClaimGuard AI - Decision Support Agent
Synthesizes multi-agent signals into a transparent 0-100 risk score,
formulates explainable adjudication recommendations, and updates IBM Db2.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from ..database.repository import repository
from .state import DbVerificationResult, DecisionResult, FraudAnalysisResult

logger = logging.getLogger("claimguard.agent.decision")


class DecisionSupportAgent:
    """Agent that aggregates evidence, calculates risk score, and recommends adjudication."""

    def evaluate(
        self,
        claim_data: Dict[str, Any],
        db_result: DbVerificationResult,
        fraud_result: FraudAnalysisResult,
        extracted_docs: Optional[List[Dict[str, Any]]] = None
    ) -> DecisionResult:
        """
        Combines verification outputs, calculates weighted risk score,
        generates transparent explanation, and updates Db2 CLAIM_RECORDS.
        """
        start_time = time.time()
        claim_id = claim_data.get("CLAIM_ID", "UNKNOWN")
        claim_amount = float(claim_data.get("CLAIM_AMOUNT") or 0.0)

        risk_score = 5.0  # Baseline nominal risk
        key_factors: List[str] = []

        # 1. Evaluate Database Verification Discrepancies
        if not db_result.customer_exists:
            risk_score += 40.0
            key_factors.append("Claimant identity could not be verified in IBM Db2 CUSTOMER_DETAILS.")

        if not db_result.policy_exists:
            risk_score += 40.0
            key_factors.append("Policy ID does not match any valid record in IBM Db2 POLICY_DETAILS.")
        elif not db_result.policy_active:
            risk_score += 35.0
            key_factors.append(f"Policy status is not active (reported as {db_result.policy_details.get('STATUS') if db_result.policy_details else 'UNKNOWN'}).")

        if not db_result.has_sufficient_coverage:
            risk_score += 25.0
            key_factors.append(
                f"Claim amount (₹{claim_amount:,.2f}) exceeds remaining policy limit (₹{db_result.remaining_coverage:,.2f})."
            )

        if not db_result.start_date_valid or not db_result.end_date_valid:
            risk_score += 20.0
            key_factors.append("Incident date falls outside active policy coverage window.")

        # 2. Evaluate Fraud Detection Indicators
        for indicator in fraud_result.indicators:
            risk_score += float(indicator.risk_weight)
            key_factors.append(f"[{indicator.severity}] {indicator.alert_type}: {indicator.description}")

        # Clamp risk score between 0.0 and 100.0
        risk_score = min(100.0, max(0.0, round(risk_score, 2)))

        # Determine Risk Level
        if risk_score <= 25.0:
            risk_level = "LOW"
        elif risk_score <= 60.0:
            risk_level = "MEDIUM"
        elif risk_score <= 85.0:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        # Determine Recommendation (Advisory Only)
        if risk_score <= 25.0 and db_result.policy_active and db_result.has_sufficient_coverage:
            recommendation = "APPROVE"
            executive_summary = (
                f"Low risk assessment ({risk_score}/100). Policy active, coverage confirmed, "
                f"and zero critical fraud flags detected. Recommended for standard approval."
            )
            # Apply deductible if defined
            deductible = float(db_result.policy_details.get("DEDUCTIBLE") or 0.0) if db_result.policy_details else 0.0
            recommended_approved_amount = max(0.0, claim_amount - deductible)
        elif risk_score >= 70.0 or fraud_result.duplicate_hash_found or fraud_result.duplicate_invoice_found:
            recommendation = "REJECT"
            executive_summary = (
                f"High fraud risk ({risk_score}/100). Critical inconsistencies or duplicate billing "
                f"evidence identified. Recommend rejection pending formal investigation."
            )
            recommended_approved_amount = 0.0
        else:
            recommendation = "INVESTIGATE"
            executive_summary = (
                f"Elevated risk assessment ({risk_score}/100). Moderate discrepancies or coverage limit "
                f"mismatches detected. Route to Senior Claims Examiner for manual review."
            )
            recommended_approved_amount = None

        if not key_factors:
            key_factors.append("All automated policy and cryptographic fraud checks completed without negative findings.")

        # 3. Update IBM Db2 CLAIM_RECORDS with updated risk score and risk level
        try:
            repository.update_claim_risk(claim_id, risk_score, risk_level)
            logger.info("Updated risk score %s (%s) for claim %s in IBM Db2", risk_score, risk_level, claim_id)
        except Exception as e:
            logger.debug("Could not update claim risk in Db2: %s", e)

        execution_time_ms = int((time.time() - start_time) * 1000)

        # 4. Record audit log in Db2 VERIFICATION_LOGS
        log_entry = {
            "CLAIM_ID": claim_id,
            "AGENT_NAME": "DECISION_AGENT",
            "ACTION": "EVALUATE_RECOMMENDATION",
            "STATUS": "SUCCESS",
            "DETAILS": f"RiskScore={risk_score}, Recommendation={recommendation}, Factors={len(key_factors)}",
            "EXECUTION_TIME_MS": execution_time_ms
        }
        try:
            repository.create_log(log_entry)
        except Exception as e:
            logger.debug("Could not record verification log: %s", e)

        return DecisionResult(
            risk_score=risk_score,
            risk_level=risk_level,
            recommendation=recommendation,
            executive_summary=executive_summary,
            key_factors=key_factors,
            recommended_approved_amount=recommended_approved_amount,
            human_review_required=True
        )


decision_agent = DecisionSupportAgent()
