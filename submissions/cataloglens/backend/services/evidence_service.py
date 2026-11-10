"""
Evidence Validation Service.
Enforces the core CatalogLens philosophy:
"Don't just ask AI to explain a database. Give AI the evidence needed to understand it."
Validates AI claims and referenced objects deterministically against real catalog metadata.
"""
from typing import Dict, List, Optional, Set
import logging

from ..models.schema import DbSchemaMetadata
from ..models.evidence import EvidenceClaim, EvidenceItem

logger = logging.getLogger("CatalogLens.EvidenceService")


class EvidenceService:
    """Validates claims and prevents LLM hallucinations by checking catalog facts."""

    def __init__(self, metadata: DbSchemaMetadata):
        self.metadata = metadata
        self._table_col_map: Dict[str, Set[str]] = {}
        for tname, tobj in metadata.tables.items():
            self._table_col_map[tname.upper()] = {c.colname.upper() for c in tobj.columns}
        for vname, vobj in metadata.views.items():
            self._table_col_map[vname.upper()] = {c.colname.upper() for c in vobj.columns}

    def validate_claim(self, claim: EvidenceClaim) -> EvidenceClaim:
        """
        Validates an EvidenceClaim against the loaded schema metadata.
        Verifies that every referenced table and column exists.
        Rejects unsupported references and updates status accordingly.
        """
        discrepancies: List[str] = []
        valid_tables: List[str] = []
        valid_columns: List[str] = []

        # 1. Validate referenced tables
        for t in claim.referenced_tables:
            norm_t = t.strip().upper()
            if norm_t in self._table_col_map:
                valid_tables.append(norm_t)
            else:
                discrepancies.append(f"Referenced table '{t}' does not exist in schema '{self.metadata.schema_name}'.")

        # 2. Validate referenced columns
        for c in claim.referenced_columns:
            parts = c.strip().upper().split(".")
            if len(parts) == 2:
                t_part, c_part = parts[0], parts[1]
                if t_part in self._table_col_map:
                    if c_part in self._table_col_map[t_part]:
                        valid_columns.append(f"{t_part}.{c_part}")
                    else:
                        discrepancies.append(f"Column '{c_part}' does not exist in table '{t_part}'.")
                else:
                    discrepancies.append(f"Table '{t_part}' for column '{c_part}' does not exist.")
            else:
                # Column without table prefix, check if exists in any referenced table
                found = False
                for t_name in valid_tables:
                    if c.strip().upper() in self._table_col_map.get(t_name, set()):
                        valid_columns.append(f"{t_name}.{c.strip().upper()}")
                        found = True
                        break
                if not found:
                    discrepancies.append(f"Column '{c}' could not be resolved to any active table.")

        # 3. Check declared relationship backing
        has_catalog_evidence = any(
            item.source.startswith("SYSCAT") or item.type in ("catalog_metadata", "declared_relationship")
            for item in claim.evidence
        )

        # 4. Status and confidence adjustment
        new_status = claim.status
        new_confidence = claim.confidence

        if discrepancies:
            # Hallucination or invalid reference detected!
            new_status = "unverified_assumption"
            new_confidence = min(new_confidence * 0.5, 0.40)
            claim.verified_by_engine = False
        elif has_catalog_evidence and claim.status == "verified_fact":
            new_confidence = 1.0
            claim.verified_by_engine = True
        elif not discrepancies:
            claim.verified_by_engine = True
            if new_status == "ai_hypothesis" and has_catalog_evidence:
                new_status = "metadata_supported"

        claim.status = new_status
        claim.confidence = round(new_confidence, 2)
        claim.discrepancies = discrepancies
        claim.referenced_tables = valid_tables
        claim.referenced_columns = valid_columns
        return claim

    def build_table_evidence_ledger(self, table_name: str) -> List[EvidenceClaim]:
        """Constructs an initial ground-truth evidence ledger for a given table from SYSCAT."""
        norm_name = table_name.strip().upper()
        tobj = self.metadata.get_object(norm_name)
        if not tobj:
            return []

        ledger: List[EvidenceClaim] = []

        # Claim 1: Primary Identity & Cardinality
        pk_cols = tobj.primary_keys
        if pk_cols:
            ledger.append(
                EvidenceClaim(
                    claim=f"'{norm_name}' primary key is composed of column(s): {', '.join(pk_cols)}.",
                    evidence=[
                        EvidenceItem(
                            source="SYSCAT.TABCONST",
                            observation=f"Type 'P' constraint declared on columns: {pk_cols}",
                            type="catalog_metadata",
                        ),
                        EvidenceItem(
                            source="SYSCAT.TABLES",
                            observation=f"Table contains approximately {tobj.card} records and {tobj.colcount} columns.",
                            type="catalog_metadata",
                        ),
                    ],
                    confidence=1.0,
                    status="verified_fact",
                    verified_by_engine=True,
                    referenced_tables=[norm_name],
                    referenced_columns=[f"{norm_name}.{p}" for p in pk_cols],
                )
            )

        # Claim 2: Declared Foreign Keys
        for fk in tobj.foreign_keys:
            ledger.append(
                EvidenceClaim(
                    claim=f"'{norm_name}.{fk.source_column}' formally references '{fk.target_table}.{fk.target_column}' in the Db2 catalog.",
                    evidence=[
                        EvidenceItem(
                            source="SYSCAT.REFERENCES",
                            observation=f"Constraint '{fk.constraint_name}' links {fk.source_table} -> {fk.target_table} (Delete: {fk.delete_rule}, Update: {fk.update_rule})",
                            type="declared_relationship",
                        )
                    ],
                    confidence=1.0,
                    status="verified_fact",
                    verified_by_engine=True,
                    referenced_tables=[norm_name, fk.target_table],
                    referenced_columns=[f"{norm_name}.{fk.source_column}", f"{fk.target_table}.{fk.target_column}"],
                )
            )

        # Claim 3: Semantic Remarks
        if tobj.remarks:
            ledger.append(
                EvidenceClaim(
                    claim=f"Catalog remarks define table purpose: \"{tobj.remarks}\"",
                    evidence=[
                        EvidenceItem(
                            source="SYSCAT.TABLES",
                            observation=f"REMARKS column contains: '{tobj.remarks}'",
                            type="catalog_metadata",
                        )
                    ],
                    confidence=1.0,
                    status="verified_fact",
                    verified_by_engine=True,
                    referenced_tables=[norm_name],
                    referenced_columns=[],
                )
            )

        return ledger
