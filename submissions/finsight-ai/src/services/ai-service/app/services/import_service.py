import csv
import io
import re
import json
import logging
from uuid import uuid4
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from app.db import db_manager
from app.services.vector_store import vector_store_service as vector_store

logger = logging.getLogger("finsight.imports")

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 2000
ALLOWED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}
ALLOWED_STATUSES = {"POSTED", "PENDING"}
ALLOWED_TYPES = {"DEBIT", "CREDIT"}

# Standard Category Aliases Mapping to seed category_id
CATEGORY_KEYWORD_MAP = {
    "cat_salary": ["salary", "payroll", "wages", "stipend"],
    "cat_freelance": ["consulting", "freelance", "contract", "client fee", "invoice"],
    "cat_investment": ["investment", "dividend", "interest", "capital gain", "mutual fund", "stock"],
    "cat_groceries": ["groceries", "supermarket", "grocery", "provisions", "food store", "bigbasket", "blinkit", "zepto", "dmart"],
    "cat_dining": ["dining", "takeout", "restaurant", "cafe", "food delivery", "swiggy", "zomato", "starbucks", "mcdonalds"],
    "cat_utilities": ["utilities", "utility", "electricity", "water", "broadband", "wifi", "internet", "phone", "gas", "airtel", "jio"],
    "cat_rent": ["rent", "housing", "mortgage", "maintenance", "landlord", "apartment"],
    "cat_subscriptions": ["software", "subscriptions", "subscription", "saas", "aws", "cloud", "netflix", "spotify", "github", "google one"],
    "cat_travel": ["travel", "commute", "cab", "taxi", "uber", "ola", "metro", "flight", "railway", "irctc", "fuel", "petrol"],
    "cat_shopping": ["shopping", "electronics", "retail", "amazon", "flipkart", "clothing", "apparel", "gadgets"],
    "cat_healthcare": ["healthcare", "pharmacy", "medical", "hospital", "doctor", "clinic", "medicine", "apollo"],
    "cat_transfer": ["transfer", "internal transfer", "self transfer", "account transfer"]
}

SUPPORTED_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
]

class ImportService:
    def __init__(self):
        self._categories_cache: Optional[List[Dict[str, Any]]] = None

    def _get_categories(self) -> List[Dict[str, Any]]:
        if self._categories_cache is None:
            sql = "SELECT category_id, category_name, category_type FROM FINSIGHT.CATEGORIES"
            try:
                self._categories_cache = db_manager.execute_query(sql, ())
            except Exception as e:
                logger.error("Failed to load categories: %s", e)
                return []
        return self._categories_cache

    def match_category(self, raw_cat: Optional[str]) -> Tuple[Optional[str], str]:
        if not raw_cat or not raw_cat.strip():
            return None, "Uncategorized"
        
        cleaned = raw_cat.strip().lower()
        categories = self._get_categories()

        # 1. Exact match against category_name
        for cat in categories:
            if cat["category_name"].lower() == cleaned:
                return cat["category_id"], cat["category_name"]

        # 2. Keyword heuristic mapping
        for cat_id, keywords in CATEGORY_KEYWORD_MAP.items():
            for kw in keywords:
                if kw in cleaned:
                    matched_name = next((c["category_name"] for c in categories if c["category_id"] == cat_id), raw_cat.strip())
                    return cat_id, matched_name

        return None, "Uncategorized"

    def detect_column_mappings(self, headers: List[str]) -> Dict[str, Optional[str]]:
        """Automatically infers column mapping from CSV headers based on standard fintech patterns."""
        mapping: Dict[str, Optional[str]] = {
            "date": None,
            "merchant": None,
            "amount": None,
            "transaction_type": None,
            "category": None,
            "currency": None,
            "status": None,
            "debit_amount": None,
            "credit_amount": None,
            "external_id": None
        }

        header_clean = {h: re.sub(r'[^a-zA-Z0-9_]', '', h.lower().replace(' ', '_')) for h in headers}

        for orig_h, h in header_clean.items():
            if not mapping["date"] and any(k in h for k in ["txn_date", "transaction_date", "trans_date", "posting_date", "value_date", "date"]):
                mapping["date"] = orig_h
            elif not mapping["merchant"] and any(k in h for k in ["merchant", "description", "narration", "particulars", "payee", "details", "remarks"]):
                mapping["merchant"] = orig_h
            elif not mapping["debit_amount"] and any(k in h for k in ["debit_amount", "debit", "withdrawal", "withdrawals", "dr_amount", "dr"]):
                mapping["debit_amount"] = orig_h
            elif not mapping["credit_amount"] and any(k in h for k in ["credit_amount", "credit", "deposit", "deposits", "cr_amount", "cr"]):
                mapping["credit_amount"] = orig_h
            elif not mapping["amount"] and any(k in h for k in ["net_amount", "txn_amount", "amount", "total"]):
                mapping["amount"] = orig_h
            elif not mapping["transaction_type"] and any(k in h for k in ["transaction_type", "txn_type", "type", "cr_dr", "dr_cr", "mode"]):
                mapping["transaction_type"] = orig_h
            elif not mapping["category"] and any(k in h for k in ["transaction_category", "expense_category", "category"]):
                mapping["category"] = orig_h
            elif not mapping["currency"] and any(k in h for k in ["currency", "curr", "ccy"]):
                mapping["currency"] = orig_h
            elif not mapping["status"] and any(k in h for k in ["transaction_status", "status"]):
                mapping["status"] = orig_h
            elif not mapping["external_id"] and any(k in h for k in ["ref_no", "reference", "txn_id", "transaction_id", "chq_no"]):
                mapping["external_id"] = orig_h

        # Fallback for merchant if still None and there are headers left
        if not mapping["merchant"]:
            for orig_h in headers:
                if orig_h not in mapping.values():
                    mapping["merchant"] = orig_h
                    break

        return mapping

    def parse_date(self, raw_date: str) -> Optional[str]:
        if not raw_date or not raw_date.strip():
            return None
        cleaned = raw_date.strip()
        for fmt in SUPPORTED_DATE_FORMATS:
            try:
                dt = datetime.strptime(cleaned, fmt)
                if 2000 <= dt.year <= 2050:
                    return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def clean_amount(self, raw_val: str) -> Tuple[Optional[Decimal], Optional[str]]:
        """Parses a raw financial string into an exact Decimal amount and optional signed type indicator."""
        if not raw_val or not raw_val.strip():
            return None, None
        
        cleaned = raw_val.strip()
        # Remove currency symbols and currency codes, but preserve decimal point and signs
        cleaned = re.sub(r'(?i)\b(?:INR|USD|EUR|GBP|Rs)\b\.?', '', cleaned)
        cleaned = re.sub(r'[₹$€£\s]', '', cleaned)
        cleaned = cleaned.replace(',', '')

        is_negative = False
        if cleaned.startswith('(') and cleaned.endswith(')'):
            is_negative = True
            cleaned = cleaned[1:-1].strip()
        elif cleaned.startswith('-'):
            is_negative = True
            cleaned = cleaned[1:].strip()
        elif cleaned.startswith('+'):
            cleaned = cleaned[1:].strip()

        try:
            val = Decimal(cleaned)
            if val < Decimal('0.00'):
                is_negative = True
                val = abs(val)
            inferred_type = "DEBIT" if is_negative else None
            return val.quantize(Decimal('0.01')), inferred_type
        except (InvalidOperation, ValueError):
            return None, None

    def normalize_type(self, raw_type: Optional[str]) -> Optional[str]:
        if not raw_type or not raw_type.strip():
            return None
        cleaned = raw_type.strip().upper()
        if cleaned in {"DEBIT", "DR", "EXPENSE", "OUTFLOW", "WITHDRAWAL", "PAYMENT"}:
            return "DEBIT"
        if cleaned in {"CREDIT", "CR", "INCOME", "INFLOW", "DEPOSIT", "REFUND"}:
            return "CREDIT"
        return None

    def get_existing_transactions(self, user_id: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT transaction_id, merchant, amount, currency, transaction_type, transaction_date, external_transaction_id
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
        """
        return db_manager.execute_query(sql, (user_id,))

    def parse_csv_rows(
        self,
        csv_content: str,
        user_id: str,
        custom_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Parses, validates, normalizes and identifies duplicates across CSV rows.
        Returns full preview payload.
        """
        if len(csv_content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"CSV file size exceeds maximum limit of {MAX_FILE_BYTES // (1024*1024)} MB.")

        # Read CSV with standard Python csv reader
        try:
            stream = io.StringIO(csv_content.strip())
            reader = csv.reader(stream)
            all_rows = [row for row in reader if any(cell.strip() for cell in row)]
        except Exception as e:
            raise ValueError(f"Malformed CSV content: {e}")

        if not all_rows:
            raise ValueError("CSV file is empty or contains no readable transaction data.")

        headers = [h.strip() for h in all_rows[0]]
        if not headers:
            raise ValueError("CSV file header row is empty.")

        data_rows = all_rows[1:]
        if not data_rows:
            raise ValueError("CSV file contains headers but zero transaction rows.")

        if len(data_rows) > MAX_ROWS:
            raise ValueError(f"CSV contains {len(data_rows)} rows, exceeding maximum limit of {MAX_ROWS} rows.")

        # Resolve column mappings
        auto_mapping = self.detect_column_mappings(headers)
        mapping = dict(auto_mapping)
        if custom_mapping:
            mapping.update(custom_mapping)

        # Check required columns
        has_amount_col = bool(mapping.get("amount") or (mapping.get("debit_amount") and mapping.get("credit_amount")) or mapping.get("debit_amount") or mapping.get("credit_amount"))
        if not mapping.get("date") or not mapping.get("merchant") or not has_amount_col:
            missing = []
            if not mapping.get("date"): missing.append("Date")
            if not mapping.get("merchant"): missing.append("Merchant / Description")
            if not has_amount_col: missing.append("Amount (or Debit/Credit)")
            raise ValueError(f"Missing required column mappings: {', '.join(missing)}. Available headers: {headers}")

        date_idx = headers.index(mapping["date"]) if mapping.get("date") in headers else -1
        merchant_idx = headers.index(mapping["merchant"]) if mapping.get("merchant") in headers else -1
        amount_idx = headers.index(mapping["amount"]) if mapping.get("amount") in headers else -1
        debit_idx = headers.index(mapping["debit_amount"]) if mapping.get("debit_amount") in headers else -1
        credit_idx = headers.index(mapping["credit_amount"]) if mapping.get("credit_amount") in headers else -1
        type_idx = headers.index(mapping["transaction_type"]) if mapping.get("transaction_type") in headers else -1
        cat_idx = headers.index(mapping["category"]) if mapping.get("category") in headers else -1
        curr_idx = headers.index(mapping["currency"]) if mapping.get("currency") in headers else -1
        status_idx = headers.index(mapping["status"]) if mapping.get("status") in headers else -1
        ext_idx = headers.index(mapping["external_id"]) if mapping.get("external_id") in headers else -1

        existing_txs = self.get_existing_transactions(user_id)

        parsed_rows: List[Dict[str, Any]] = []
        validation_errors: List[Dict[str, Any]] = []
        duplicate_candidates: List[Dict[str, Any]] = []

        total_credits = Decimal('0.00')
        total_debits = Decimal('0.00')
        seen_in_batch: Dict[Tuple[str, str, Decimal, str], int] = {}

        for row_num, raw_row in enumerate(data_rows, start=2):
            raw_dict = {headers[i]: raw_row[i].strip() for i in range(min(len(headers), len(raw_row)))}
            row_errors: List[str] = []

            # 1. Date Validation
            raw_date_val = raw_row[date_idx].strip() if date_idx >= 0 and date_idx < len(raw_row) else ""
            parsed_date = self.parse_date(raw_date_val)
            if not parsed_date:
                row_errors.append(f"Invalid or ambiguous date format '{raw_date_val}'. Supported formats include YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY.")

            # 2. Merchant / Description Validation
            raw_merchant_val = raw_row[merchant_idx].strip() if merchant_idx >= 0 and merchant_idx < len(raw_row) else ""
            if not raw_merchant_val:
                row_errors.append("Merchant / Description cannot be blank.")
            merchant_clean = raw_merchant_val[:150]
            description_clean = raw_merchant_val[:500]

            # 3. Amount & Type Validation
            parsed_amount: Optional[Decimal] = None
            parsed_type: Optional[str] = None

            # Handle separate Debit / Credit columns
            if debit_idx >= 0 or credit_idx >= 0:
                raw_deb = raw_row[debit_idx].strip() if debit_idx >= 0 and debit_idx < len(raw_row) else ""
                raw_cred = raw_row[credit_idx].strip() if credit_idx >= 0 and credit_idx < len(raw_row) else ""
                deb_val, _ = self.clean_amount(raw_deb) if raw_deb else (None, None)
                cred_val, _ = self.clean_amount(raw_cred) if raw_cred else (None, None)

                if deb_val and deb_val > Decimal('0.00') and cred_val and cred_val > Decimal('0.00'):
                    row_errors.append(f"Both Debit ({deb_val}) and Credit ({cred_val}) columns are populated. Conflicting transaction direction.")
                elif deb_val and deb_val > Decimal('0.00'):
                    parsed_amount = deb_val
                    parsed_type = "DEBIT"
                elif cred_val and cred_val > Decimal('0.00'):
                    parsed_amount = cred_val
                    parsed_type = "CREDIT"
                elif amount_idx >= 0 and amount_idx < len(raw_row):
                    # Fallback to amount column if both debit & credit empty
                    raw_amt = raw_row[amount_idx].strip()
                    amt_val, inf_type = self.clean_amount(raw_amt)
                    parsed_amount = amt_val
                    parsed_type = inf_type
                else:
                    row_errors.append("Transaction amount is zero or missing in Debit and Credit columns.")

            elif amount_idx >= 0 and amount_idx < len(raw_row):
                raw_amt = raw_row[amount_idx].strip()
                amt_val, inf_type = self.clean_amount(raw_amt)
                if amt_val is None or amt_val <= Decimal('0.00'):
                    row_errors.append(f"Invalid monetary amount '{raw_amt}'. Must be a positive decimal.")
                else:
                    parsed_amount = amt_val
                    parsed_type = inf_type

            # If explicit Type column mapped, check it
            if type_idx >= 0 and type_idx < len(raw_row):
                raw_type = raw_row[type_idx].strip()
                norm_type = self.normalize_type(raw_type)
                if norm_type:
                    parsed_type = norm_type
                elif raw_type:
                    row_errors.append(f"Unrecognized transaction type '{raw_type}'. Expected DEBIT or CREDIT.")

            # Default transaction type if still undefined: assume DEBIT for expense transactions
            if not parsed_type:
                parsed_type = "DEBIT"

            # 4. Currency Validation
            parsed_curr = "INR"
            if curr_idx >= 0 and curr_idx < len(raw_row):
                raw_curr = raw_row[curr_idx].strip().upper()
                if raw_curr in ALLOWED_CURRENCIES:
                    parsed_curr = raw_curr
                elif raw_curr:
                    row_errors.append(f"Unsupported currency '{raw_curr}'. Allowed currencies: {sorted(list(ALLOWED_CURRENCIES))}.")

            # 5. Status Validation
            parsed_status = "POSTED"
            if status_idx >= 0 and status_idx < len(raw_row):
                raw_st = raw_row[status_idx].strip().upper()
                if raw_st in ALLOWED_STATUSES:
                    parsed_status = raw_st
                elif raw_st:
                    parsed_status = "POSTED"  # Safe default with explanation

            # 6. Category Mapping
            raw_cat = raw_row[cat_idx].strip() if cat_idx >= 0 and cat_idx < len(raw_row) else None
            cat_id, cat_name = self.match_category(raw_cat)

            # 7. External Reference ID
            external_id = raw_row[ext_idx].strip()[:100] if ext_idx >= 0 and ext_idx < len(raw_row) and raw_row[ext_idx].strip() else None

            is_valid = len(row_errors) == 0
            is_duplicate = False
            duplicate_info = None

            if is_valid and parsed_amount is not None and parsed_date is not None:
                # Accumulate financial sums for valid rows
                if parsed_type == "CREDIT":
                    total_credits += parsed_amount
                else:
                    total_debits += parsed_amount

                # Check duplicate against existing Db2 transactions
                clean_m = re.sub(r'[^a-zA-Z0-9]', '', merchant_clean.lower())
                for tx in existing_txs:
                    tx_date = str(tx["transaction_date"])
                    tx_amt = Decimal(str(tx["amount"])).quantize(Decimal('0.01'))
                    tx_type = tx["transaction_type"].upper()
                    tx_m = re.sub(r'[^a-zA-Z0-9]', '', tx["merchant"].lower())

                    # Check exact duplicate: same date, exact amount, same type, matching merchant
                    if tx_date == parsed_date and tx_amt == parsed_amount and tx_type == parsed_type and (tx_m == clean_m or clean_m in tx_m or tx_m in clean_m):
                        is_duplicate = True
                        duplicate_info = {
                            "row_number": row_num,
                            "merchant": merchant_clean,
                            "amount": float(parsed_amount),
                            "date": parsed_date,
                            "transaction_type": parsed_type,
                            "duplicate_type": "EXACT",
                            "matched_transaction_id": tx["transaction_id"],
                            "reason": f"Exact match found in ledger on {tx_date} for INR {parsed_amount:.2f} ({tx['merchant']})."
                        }
                        duplicate_candidates.append(duplicate_info)
                        break
                    # Check external transaction ID duplicate
                    elif external_id and tx.get("external_transaction_id") and tx["external_transaction_id"].strip() == external_id:
                        is_duplicate = True
                        duplicate_info = {
                            "row_number": row_num,
                            "merchant": merchant_clean,
                            "amount": float(parsed_amount),
                            "date": parsed_date,
                            "transaction_type": parsed_type,
                            "duplicate_type": "EXACT",
                            "matched_transaction_id": tx["transaction_id"],
                            "reason": f"Existing transaction matches external reference ID '{external_id}'."
                        }
                        duplicate_candidates.append(duplicate_info)
                        break

                # Also check intra-batch duplicate
                batch_key = (parsed_date, clean_m, parsed_amount, parsed_type)
                if not is_duplicate and batch_key in seen_in_batch:
                    is_duplicate = True
                    prev_row = seen_in_batch[batch_key]
                    duplicate_info = {
                        "row_number": row_num,
                        "merchant": merchant_clean,
                        "amount": float(parsed_amount),
                        "date": parsed_date,
                        "transaction_type": parsed_type,
                        "duplicate_type": "BATCH_DUPLICATE",
                        "matched_transaction_id": f"Row {prev_row}",
                        "reason": f"Identical transaction appears earlier in this CSV at row {prev_row}."
                    }
                    duplicate_candidates.append(duplicate_info)
                elif not is_duplicate:
                    seen_in_batch[batch_key] = row_num

            if not is_valid:
                for err in row_errors:
                    validation_errors.append({
                        "row_number": row_num,
                        "raw_data": raw_dict,
                        "message": err
                    })

            parsed_rows.append({
                "row_number": row_num,
                "date": parsed_date,
                "merchant": merchant_clean,
                "description": description_clean,
                "amount": float(parsed_amount) if parsed_amount is not None else None,
                "currency": parsed_curr,
                "transaction_type": parsed_type,
                "category": cat_name,
                "category_id": cat_id,
                "transaction_status": parsed_status,
                "external_transaction_id": external_id,
                "is_valid": is_valid,
                "is_duplicate": is_duplicate,
                "duplicate_info": duplicate_info,
                "validation_errors": row_errors
            })

        valid_count = sum(1 for r in parsed_rows if r["is_valid"])
        invalid_count = len(parsed_rows) - valid_count
        duplicate_count = len(duplicate_candidates)

        return {
            "headers": headers,
            "detected_mapping": mapping,
            "summary": {
                "total_rows": len(parsed_rows),
                "valid_rows": valid_count,
                "invalid_rows": invalid_count,
                "duplicate_rows": duplicate_count,
                "total_credits": float(total_credits),
                "total_debits": float(total_debits),
                "net_value": float(total_credits - total_debits),
                "currency": "INR"
            },
            "validation_errors": validation_errors,
            "duplicate_candidates": duplicate_candidates,
            "preview_rows": parsed_rows[:50]  # First 50 rows for frontend display
        }

    def preview_import(
        self,
        user_id: str,
        filename: str,
        csv_content: str,
        custom_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Validates CSV and stores a pending import job in Db2."""
        parse_result = self.parse_csv_rows(csv_content, user_id, custom_mapping)
        import_id = f"imp_{uuid4().hex[:16]}"

        insert_job_sql = """
        INSERT INTO FINSIGHT.IMPORT_JOBS 
            (import_job_id, user_id, filename, status, total_rows, successful_rows, rejected_rows, duplicate_rows, error_summary, created_at)
        VALUES (?, ?, ?, 'PENDING', ?, 0, ?, ?, ?, CURRENT TIMESTAMP)
        """
        error_summary = json.dumps({
            "mapping": parse_result["detected_mapping"],
            "errors_count": len(parse_result["validation_errors"]),
            "duplicates_count": len(parse_result["duplicate_candidates"])
        })
        try:
            db_manager.execute_statement(insert_job_sql, (
                import_id,
                user_id,
                filename[:255],
                parse_result["summary"]["total_rows"],
                parse_result["summary"]["invalid_rows"],
                parse_result["summary"]["duplicate_rows"],
                error_summary
            ))
        except Exception as e:
            logger.error("Failed to create pending import job record: %s", e)

        return {
            "import_id": import_id,
            "filename": filename,
            **parse_result
        }

    def commit_import(
        self,
        user_id: str,
        import_id: str,
        filename: str,
        csv_content: str,
        custom_mapping: Optional[Dict[str, str]] = None,
        skip_duplicates: bool = True,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Atomically commits approved CSV transactions into Db2.
        Guarantees idempotency via persistent import_job_id check.
        """
        # 1. Idempotency Check
        check_sql = "SELECT import_job_id, status, successful_rows, rejected_rows, duplicate_rows, error_summary, completed_at FROM FINSIGHT.IMPORT_JOBS WHERE import_job_id = ? AND user_id = ?"
        jobs = db_manager.execute_query(check_sql, (import_id, user_id))
        if jobs:
            existing_job = jobs[0]
            if existing_job["status"] == "COMPLETED":
                logger.info("Import job %s already completed. Returning cached result (Idempotent).", import_id)
                meta = {}
                try:
                    if existing_job.get("error_summary"):
                        meta = json.loads(existing_job["error_summary"])
                except Exception:
                    pass
                return {
                    "import_id": import_id,
                    "status": "COMPLETED",
                    "total_rows": existing_job.get("successful_rows", 0) + existing_job.get("rejected_rows", 0) + existing_job.get("duplicate_rows", 0),
                    "successful_rows": existing_job.get("successful_rows", 0),
                    "skipped_duplicates": existing_job.get("duplicate_rows", 0),
                    "rejected_rows": existing_job.get("rejected_rows", 0),
                    "imported_transaction_ids": meta.get("imported_ids", []),
                    "completed_at": str(existing_job.get("completed_at")),
                    "indexing_status": meta.get("indexing_status", {"status": "COMPLETED", "indexed_count": existing_job.get("successful_rows", 0)})
                }
            elif existing_job["status"] == "PROCESSING":
                raise RuntimeError("Import job is currently processing. Concurrent duplicate execution prevented.")

        # Update job to PROCESSING or create job if not yet created
        if jobs:
            upd_sql = "UPDATE FINSIGHT.IMPORT_JOBS SET status = 'PROCESSING' WHERE import_job_id = ? AND user_id = ?"
            db_manager.execute_statement(upd_sql, (import_id, user_id))
        else:
            ins_sql = "INSERT INTO FINSIGHT.IMPORT_JOBS (import_job_id, user_id, filename, status, created_at) VALUES (?, ?, ?, 'PROCESSING', CURRENT TIMESTAMP)"
            db_manager.execute_statement(ins_sql, (import_id, user_id, filename[:255]))

        # 2. Determine target account_id for user
        if not account_id:
            acc_sql = "SELECT account_id FROM FINSIGHT.ACCOUNTS WHERE user_id = ? ORDER BY created_at ASC"
            acc_rows = db_manager.execute_query(acc_sql, (user_id,))
            if acc_rows:
                account_id = acc_rows[0]["account_id"].strip()
            else:
                # Auto-create primary checking account for user
                account_id = f"acc_{user_id[-12:]}_chk"
                new_acc_sql = """
                INSERT INTO FINSIGHT.ACCOUNTS 
                    (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance, created_at)
                VALUES (?, ?, 'Primary Checking', 'CHECKING', 'FinSight Bank', 'INR', 10000.00, CURRENT TIMESTAMP)
                """
                try:
                    db_manager.execute_statement(new_acc_sql, (account_id, user_id))
                except Exception as e:
                    logger.error("Failed to auto-create checking account: %s", e)

        # 3. Parse and filter rows
        parse_result = self.parse_csv_rows(csv_content, user_id, custom_mapping)
        rows_to_insert = []
        skipped_dup_count = 0
        rejected_count = len(parse_result["validation_errors"])

        for r in parse_result["preview_rows"]:
            if not r["is_valid"]:
                continue
            if r["is_duplicate"] and skip_duplicates:
                skipped_dup_count += 1
                continue
            rows_to_insert.append(r)

        # 4. Atomic Database Batch Insert
        tx_insert_sql = """
        INSERT INTO FINSIGHT.TRANSACTIONS 
            (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS DATE), ?, 'CSV_IMPORT', CURRENT TIMESTAMP)
        """

        operations: List[Tuple[str, Tuple[Any, ...]]] = []
        imported_ids: List[str] = []

        for r in rows_to_insert:
            tx_id = f"tx_imp_{uuid4().hex[:12]}"
            imported_ids.append(tx_id)
            operations.append((
                tx_insert_sql,
                (
                    tx_id,
                    user_id,
                    account_id,
                    r["category_id"],
                    r["external_transaction_id"],
                    r["merchant"],
                    r["description"],
                    r["amount"],
                    r["currency"],
                    r["transaction_type"],
                    r["date"],
                    r["transaction_status"]
                )
            ))

        try:
            if operations:
                db_manager.execute_transaction_batch(operations)
                logger.info("Successfully committed %d transactions for user %s inside Db2 transaction.", len(operations), user_id)
        except Exception as e:
            logger.error("Db2 batch insert failed, rolled back: %s", e)
            fail_sql = "UPDATE FINSIGHT.IMPORT_JOBS SET status = 'FAILED', error_summary = ? WHERE import_job_id = ? AND user_id = ?"
            db_manager.execute_statement(fail_sql, (f"Database batch transaction rolled back: {e}", import_id, user_id))
            raise RuntimeError(f"Database insertion failed: {e}")

        # 5. Vector Store Embedding Generation (Post-Commit Resilient Indexing)
        indexing_status = {
            "status": "COMPLETED",
            "indexed_count": 0,
            "message": "Zero records required embedding."
        }
        if imported_ids:
            try:
                idx_res = vector_store.index_specific_transactions(user_id, imported_ids)
                indexing_status = {
                    "status": idx_res.get("status", "COMPLETED"),
                    "indexed_count": idx_res.get("indexed_count", 0),
                    "message": f"Successfully indexed {idx_res.get('indexed_count', 0)} of {len(imported_ids)} transactions into Db2 vector store."
                }
            except Exception as e:
                logger.error("Vector embedding generation failed post-commit: %s", e)
                indexing_status = {
                    "status": "FAILED",
                    "indexed_count": 0,
                    "message": f"Embedding generation failed: {e}. You can retry indexing at any time."
                }

        # 6. Update Import Job to COMPLETED
        now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        job_meta = json.dumps({
            "imported_ids": imported_ids,
            "indexing_status": indexing_status,
            "completed_at": now_str
        })
        comp_sql = """
        UPDATE FINSIGHT.IMPORT_JOBS 
        SET status = 'COMPLETED',
            total_rows = ?,
            successful_rows = ?,
            rejected_rows = ?,
            duplicate_rows = ?,
            error_summary = ?,
            completed_at = CURRENT TIMESTAMP
        WHERE import_job_id = ? AND user_id = ?
        """
        db_manager.execute_statement(comp_sql, (
            parse_result["summary"]["total_rows"],
            len(imported_ids),
            rejected_count,
            skipped_dup_count,
            job_meta,
            import_id,
            user_id
        ))

        return {
            "import_id": import_id,
            "status": "COMPLETED",
            "total_rows": parse_result["summary"]["total_rows"],
            "successful_rows": len(imported_ids),
            "skipped_duplicates": skipped_dup_count,
            "rejected_rows": rejected_count,
            "imported_transaction_ids": imported_ids,
            "completed_at": now_str,
            "indexing_status": indexing_status
        }

    def get_import(self, user_id: str, import_id: str) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT import_job_id, user_id, filename, status, total_rows, successful_rows, rejected_rows, duplicate_rows, error_summary, created_at, completed_at
        FROM FINSIGHT.IMPORT_JOBS
        WHERE import_job_id = ? AND user_id = ?
        """
        rows = db_manager.execute_query(sql, (import_id, user_id))
        if not rows:
            return None
        r = rows[0]
        meta = {}
        try:
            if r.get("error_summary"):
                meta = json.loads(r["error_summary"])
        except Exception:
            pass

        return {
            "import_id": r["import_job_id"],
            "filename": r["filename"],
            "status": r["status"],
            "total_rows": r["total_rows"],
            "successful_rows": r["successful_rows"],
            "rejected_rows": r["rejected_rows"],
            "duplicate_rows": r["duplicate_rows"],
            "created_at": str(r["created_at"]),
            "completed_at": str(r["completed_at"]) if r.get("completed_at") else None,
            "indexing_status": meta.get("indexing_status"),
            "imported_transaction_ids": meta.get("imported_ids", [])
        }

    def list_imports(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        sql = """
        SELECT import_job_id, user_id, filename, status, total_rows, successful_rows, rejected_rows, duplicate_rows, error_summary, created_at, completed_at
        FROM FINSIGHT.IMPORT_JOBS
        WHERE user_id = ?
        ORDER BY created_at DESC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (user_id, limit))
        results = []
        for r in rows:
            meta = {}
            try:
                if r.get("error_summary"):
                    meta = json.loads(r["error_summary"])
            except Exception:
                pass
            results.append({
                "import_id": r["import_job_id"],
                "filename": r["filename"],
                "status": r["status"],
                "total_rows": r["total_rows"],
                "successful_rows": r["successful_rows"],
                "rejected_rows": r["rejected_rows"],
                "duplicate_rows": r["duplicate_rows"],
                "created_at": str(r["created_at"]),
                "completed_at": str(r["completed_at"]) if r.get("completed_at") else None,
                "indexing_status": meta.get("indexing_status")
            })
        return results

    def retry_indexing(self, user_id: str, import_id: str) -> Dict[str, Any]:
        """Retries indexing for transactions imported in a specific job."""
        job = self.get_import(user_id, import_id)
        if not job:
            raise KeyError(f"Import job {import_id} not found.")

        tx_ids = job.get("imported_transaction_ids", [])
        if not tx_ids:
            # Query recent CSV_IMPORT transactions for this user
            sql = "SELECT transaction_id FROM FINSIGHT.TRANSACTIONS WHERE user_id = ? AND source = 'CSV_IMPORT'"
            rows = db_manager.execute_query(sql, (user_id,))
            tx_ids = [r["transaction_id"] for r in rows]

        if not tx_ids:
            return {"status": "COMPLETED", "indexed_count": 0, "message": "No transactions found to index."}

        idx_res = vector_store.index_specific_transactions(user_id, tx_ids)
        
        # Update job error_summary with new status
        job_meta = json.dumps({
            "imported_ids": tx_ids,
            "indexing_status": idx_res,
            "completed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        })
        upd_sql = "UPDATE FINSIGHT.IMPORT_JOBS SET error_summary = ? WHERE import_job_id = ? AND user_id = ?"
        db_manager.execute_statement(upd_sql, (job_meta, import_id, user_id))

        return idx_res

import_service = ImportService()
