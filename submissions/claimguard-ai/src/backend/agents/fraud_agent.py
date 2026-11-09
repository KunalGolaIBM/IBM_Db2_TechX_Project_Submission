"""
ClaimGuard AI - Fraud Detection Agent
Analyzes claims and documents for duplicate hashes, invoice collisions,
date anomalies, and abnormal billing amounts, persisting alerts to IBM Db2.
"""

import logging
import time
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from ..database.repository import repository
from .state import FraudAnalysisResult, FraudIndicator

logger = logging.getLogger("claimguard.agent.fraud")


class FraudDetectionAgent:
    """Agent responsible for identifying fraud patterns and persisting alerts to Db2."""

    def analyze(
        self,
        claim_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        extracted_docs: Optional[List[Dict[str, Any]]] = None
    ) -> FraudAnalysisResult:
        """
        Runs fraud detection rules against documents, invoices, and temporal metrics.
        Persists detected alerts into the IBM Db2 FRAUD_ALERTS table.
        """
        start_time = time.time()
        claim_id = claim_data.get("CLAIM_ID", "UNKNOWN")
        invoice_num = claim_data.get("HOSPITAL_INVOICE_NUMBER")
        claim_amount = float(claim_data.get("CLAIM_AMOUNT") or 0.0)
        adm_str = claim_data.get("ADMISSION_DATE")
        dis_str = claim_data.get("DISCHARGE_DATE")
        inc_str = claim_data.get("INCIDENT_DATE")

        indicators: List[FraudIndicator] = []
        duplicate_hash_found = False
        duplicate_invoice_found = False
        date_anomaly_found = False
        unusual_amount_found = False

        # 1. Duplicate Document Hash Detection (Db2 Lookup)
        for doc in documents:
            file_hash = doc.get("FILE_HASH")
            if not file_hash:
                continue

            # Query Db2 DOCUMENT_RECORDS for same hash on a different claim
            colliding_docs = repository.find_documents_by_hash(file_hash, exclude_claim_id=claim_id)
            if colliding_docs:
                duplicate_hash_found = True
                matched_claim = colliding_docs[0].get("CLAIM_ID", "another claim")
                indicator = FraudIndicator(
                    alert_type="DUPLICATE_DOCUMENT_HASH",
                    severity="CRITICAL",
                    description=(
                        f"Cryptographic document hash collision: Document '{doc.get('DOCUMENT_NAME')}' "
                        f"matches document previously submitted on claim '{matched_claim}'."
                    ),
                    evidence=f"File SHA-256: {file_hash}",
                    risk_weight=45
                )
                indicators.append(indicator)
                self._persist_alert(claim_id, indicator)

        # 2. Duplicate Hospital Invoice Detection (Db2 Lookup)
        if invoice_num:
            colliding_claims = repository.find_claims_by_invoice(invoice_num, exclude_claim_id=claim_id)
            if colliding_claims:
                duplicate_invoice_found = True
                matched_id = colliding_claims[0].get("CLAIM_ID")
                indicator = FraudIndicator(
                    alert_type="DUPLICATE_INVOICE",
                    severity="CRITICAL",
                    description=(
                        f"Invoice number collision: Invoice '{invoice_num}' was already used "
                        f"in existing claim '{matched_id}'."
                    ),
                    evidence=f"Hospital invoice: {invoice_num}",
                    risk_weight=40
                )
                indicators.append(indicator)
                self._persist_alert(claim_id, indicator)

        # 3. Date Anomaly Detection
        if adm_str and dis_str:
            try:
                adm_date = datetime.strptime(str(adm_str)[:10], "%Y-%m-%d").date()
                dis_date = datetime.strptime(str(dis_str)[:10], "%Y-%m-%d").date()
                today = date.today()

                if dis_date < adm_date:
                    date_anomaly_found = True
                    indicator = FraudIndicator(
                        alert_type="DATE_ANOMALY",
                        severity="HIGH",
                        description=(
                            f"Chronological impossibility: Discharge date ({dis_date}) "
                            f"occurs before admission date ({adm_date})."
                        ),
                        evidence=f"Admission: {adm_date}, Discharge: {dis_date}",
                        risk_weight=30
                    )
                    indicators.append(indicator)
                    self._persist_alert(claim_id, indicator)

                if adm_date > today:
                    date_anomaly_found = True
                    indicator = FraudIndicator(
                        alert_type="DATE_ANOMALY",
                        severity="HIGH",
                        description=f"Future admission date ({adm_date}) recorded on historical claim.",
                        evidence=f"Admission date in future: {adm_date}",
                        risk_weight=25
                    )
                    indicators.append(indicator)
                    self._persist_alert(claim_id, indicator)
            except ValueError:
                pass

        # 4. Unusual Amount Detection
        diag_code = (claim_data.get("DIAGNOSIS_CODE") or "").upper()
        # High-risk benchmark: Minor conditions (A09 gastroenteritis, J00 common cold) claiming > ₹150,000
        if diag_code in ("A09", "J00", "R51", "K29.7") and claim_amount > 150000.0:
            unusual_amount_found = True
            indicator = FraudIndicator(
                alert_type="UNUSUAL_AMOUNT",
                severity="MEDIUM",
                description=(
                    f"Claim amount of ₹{claim_amount:,.2f} is significantly elevated "
                    f"for recorded diagnosis code '{diag_code}'."
                ),
                evidence=f"Diagnosis: {diag_code}, Claimed Amount: ₹{claim_amount:,.2f}",
                risk_weight=20
            )
            indicators.append(indicator)
            self._persist_alert(claim_id, indicator)

        is_suspicious = len(indicators) > 0
        summary = (
            f"Detected {len(indicators)} potential fraud indicators requiring investigation."
            if is_suspicious
            else "No duplicate documents or anomalous billing patterns detected."
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Record audit log in Db2 VERIFICATION_LOGS
        log_status = "WARNING" if is_suspicious else "SUCCESS"
        log_entry = {
            "CLAIM_ID": claim_id,
            "AGENT_NAME": "FRAUD_AGENT",
            "ACTION": "ANALYZE_FRAUD_PATTERNS",
            "STATUS": log_status,
            "DETAILS": f"Found {len(indicators)} alerts (dup_hash={duplicate_hash_found}, dup_inv={duplicate_invoice_found})",
            "EXECUTION_TIME_MS": execution_time_ms
        }
        try:
            repository.create_log(log_entry)
        except Exception as e:
            logger.debug("Could not record verification log: %s", e)

        return FraudAnalysisResult(
            is_suspicious=is_suspicious,
            indicators=indicators,
            duplicate_hash_found=duplicate_hash_found,
            duplicate_invoice_found=duplicate_invoice_found,
            date_anomaly_found=date_anomaly_found,
            unusual_amount_found=unusual_amount_found,
            summary=summary
        )

    def _persist_alert(self, claim_id: str, indicator: FraudIndicator):
        """Persists detected alert into IBM Db2 FRAUD_ALERTS table."""
        alert_data = {
            "CLAIM_ID": claim_id,
            "ALERT_TYPE": indicator.alert_type,
            "SEVERITY": indicator.severity,
            "DESCRIPTION": indicator.description,
            "EVIDENCE_DETAILS": indicator.evidence,
            "IS_RESOLVED": 0
        }
        try:
            repository.create_fraud_alert(alert_data)
        except Exception as e:
            logger.debug("Could not record fraud alert to Db2: %s", e)


fraud_agent = FraudDetectionAgent()
