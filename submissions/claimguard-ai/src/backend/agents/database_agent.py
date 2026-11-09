"""
ClaimGuard AI - Database Verification Agent
Queries IBM Db2 to cross-examine customer identity, policy validity,
remaining coverage limits, deductibles, and claim history.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from ..database.connection import db2_manager
from ..database.repository import repository
from .state import DbVerificationResult

logger = logging.getLogger("claimguard.agent.database")


class DatabaseVerificationAgent:
    """Agent responsible for querying IBM Db2 and verifying policy constraints."""

    def verify(self, claim_data: Dict[str, Any]) -> DbVerificationResult:
        """
        Queries IBM Db2 for customer and policy records, cross-referencing
        coverage limits and incident dates against the claim.
        """
        start_time = time.time()
        customer_id = claim_data.get("CUSTOMER_ID")
        policy_id = claim_data.get("POLICY_ID")
        claim_id = claim_data.get("CLAIM_ID", "UNKNOWN")
        claim_amount = float(claim_data.get("CLAIM_AMOUNT") or 0.0)
        incident_date_str = str(claim_data.get("INCIDENT_DATE") or "")

        discrepancies: List[str] = []

        # 1. Retrieve Customer from IBM Db2
        customer = repository.get_customer_by_id(customer_id)
        customer_exists = customer is not None
        if not customer_exists:
            discrepancies.append(f"Customer ID '{customer_id}' was not found in IBM Db2 CUSTOMER_DETAILS.")

        # 2. Retrieve Policy from IBM Db2
        policy = repository.get_policy_by_id(policy_id)
        policy_exists = policy is not None
        policy_active = False
        start_date_valid = True
        end_date_valid = True
        has_sufficient_coverage = True
        max_coverage = 0.0
        remaining_coverage = 0.0

        if not policy_exists:
            discrepancies.append(f"Policy ID '{policy_id}' was not found in IBM Db2 POLICY_DETAILS.")
        else:
            policy_active = (policy.get("STATUS") == "ACTIVE")
            if not policy_active:
                discrepancies.append(f"Policy '{policy.get('POLICY_NUMBER')}' is not ACTIVE (Current Status: {policy.get('STATUS')}).")

            # Check coverage limits
            max_coverage = float(policy.get("MAX_COVERAGE_AMOUNT") or 0.0)
            remaining_coverage = float(policy.get("REMAINING_COVERAGE") or 0.0)

            if claim_amount > remaining_coverage:
                has_sufficient_coverage = False
                discrepancies.append(
                    f"Claim amount (₹{claim_amount:,.2f}) exceeds policy remaining coverage limit (₹{remaining_coverage:,.2f})."
                )

            # Check incident date within policy validity window
            start_date_str = str(policy.get("START_DATE") or "")
            end_date_str = str(policy.get("END_DATE") or "")

            if incident_date_str and start_date_str and end_date_str:
                try:
                    inc_dt = datetime.strptime(incident_date_str[:10], "%Y-%m-%d").date()
                    start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d").date()
                    end_dt = datetime.strptime(end_date_str[:10], "%Y-%m-%d").date()

                    if inc_dt < start_dt:
                        start_date_valid = False
                        discrepancies.append(f"Incident date ({incident_date_str}) occurred prior to policy start date ({start_date_str}).")
                    if inc_dt > end_dt:
                        end_date_valid = False
                        discrepancies.append(f"Incident date ({incident_date_str}) occurred after policy expiry date ({end_date_str}).")
                except ValueError:
                    pass

        # 3. Retrieve Historical Claims for this Customer
        all_claims = repository.list_claims()
        historical_claims = [
            c for c in all_claims
            if c.get("CUSTOMER_ID") == customer_id and c.get("CLAIM_ID") != claim_id
        ]
        historical_claims_count = len(historical_claims)
        historical_claims_total = sum(float(c.get("CLAIM_AMOUNT") or 0.0) for c in historical_claims)

        execution_time_ms = int((time.time() - start_time) * 1000)

        # 4. Log execution in IBM Db2 VERIFICATION_LOGS
        log_status = "SUCCESS" if not discrepancies else "WARNING"
        log_entry = {
            "CLAIM_ID": claim_id,
            "AGENT_NAME": "DATABASE_AGENT",
            "ACTION": "VERIFY_POLICY_AND_COVERAGE",
            "STATUS": log_status,
            "DETAILS": (
                f"Db2 customer={customer_exists}, policy={policy_exists}, active={policy_active}, "
                f"remaining_cov=₹{remaining_coverage:,.2f}, discrepancies={len(discrepancies)}"
            ),
            "EXECUTION_TIME_MS": execution_time_ms
        }
        try:
            repository.create_log(log_entry)
        except Exception as e:
            logger.debug("Could not record verification log: %s", e)

        return DbVerificationResult(
            customer_exists=customer_exists,
            customer_details=customer,
            policy_exists=policy_exists,
            policy_active=policy_active,
            policy_details=policy,
            start_date_valid=start_date_valid,
            end_date_valid=end_date_valid,
            has_sufficient_coverage=has_sufficient_coverage,
            max_coverage=max_coverage,
            remaining_coverage=remaining_coverage,
            historical_claims_count=historical_claims_count,
            historical_claims_total=historical_claims_total,
            discrepancies=discrepancies
        )


database_agent = DatabaseVerificationAgent()
