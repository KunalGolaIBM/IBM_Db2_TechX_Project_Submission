"""
Anthropic Claude Reasoning Engine Integration.
Provides structured semantic interpretation of enterprise database metadata.
Includes token-efficient context trimming, memory caching, and graceful
fallback to deterministic heuristic reasoning when API key is unavailable.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Dict, List, Optional
import os

from ..core.config import get_settings
from ..models.schema import DbTable
from ..models.relationship import RelationshipEdge
from ..models.analysis import TableUnderstanding, ColumnRole
from ..models.evidence import EvidenceClaim, EvidenceItem

logger = logging.getLogger("CatalogLens.ClaudeClient")

try:
    import anthropic
    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_SDK_AVAILABLE = False


class ClaudeClient:
    """Orchestrates Claude API interactions with structured output parsing and caching."""

    def __init__(self):
        self.settings = get_settings()
        self._cache: Dict[str, TableUnderstanding] = {}
        self._client = None
        if ANTHROPIC_SDK_AVAILABLE and self.settings.has_anthropic_key():
            try:
                self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
            except Exception as e:
                logger.warning("Could not initialize Anthropic client: %s", str(e))

    def is_available(self) -> bool:
        """Returns True if the Claude API client is initialized and configured."""
        return self._client is not None

    def explain_table(
        self,
        table: DbTable,
        relationships: List[RelationshipEdge],
        schema_name: str = "ENTERPRISE",
        force_refresh: bool = False,
    ) -> TableUnderstanding:
        """
        Explains the likely business purpose, column significance, workflow role,
        and evidence for a table using Claude (or deterministic fallback).
        """
        cache_key = f"{schema_name}.{table.tabname}"
        if not force_refresh and cache_key in self._cache:
            logger.info("Returning cached understanding for %s", cache_key)
            return self._cache[cache_key]

        if not self.is_available():
            logger.info("Anthropic API key not configured; using deterministic heuristic explanation for %s", table.tabname)
            result = self._deterministic_explain_table(table, relationships, schema_name)
            self._cache[cache_key] = result
            return result

        # Call live Anthropic Claude API
        try:
            result = self._call_claude_explain(table, relationships, schema_name)
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logger.error("Claude API call failed (%s). Falling back to deterministic engine.", str(e))
            result = self._deterministic_explain_table(table, relationships, schema_name)
            result.uncertainties.append(f"AI live reasoning call encountered error: {str(e)}. Evaluated via deterministic fallback.")
            self._cache[cache_key] = result
            return result

    def _call_claude_explain(
        self,
        table: DbTable,
        relationships: List[RelationshipEdge],
        schema_name: str,
    ) -> TableUnderstanding:
        """Sends metadata context to Claude with strict JSON schema instructions."""
        # 1. Build token-efficient context limited strictly to this table and direct relationships
        cols_summary = [
            {
                "name": c.colname,
                "type": c.typename,
                "nullable": c.nulls == "Y",
                "is_pk": c.is_primary_key,
                "remarks": c.remarks or "",
            }
            for c in table.columns
        ]

        relevant_rels = [
            {
                "source": f"{r.source_table}.{r.source_column}",
                "target": f"{r.target_table}.{r.target_column}",
                "type": r.relationship_type.value,
                "confidence": r.confidence,
                "reason": r.reason,
            }
            for r in relationships
            if r.source_table == table.tabname or r.target_table == table.tabname
        ]

        prompt_payload = {
            "table_name": table.tabname,
            "schema_name": schema_name,
            "catalog_remarks": table.remarks or "None recorded in SYSCAT.TABLES",
            "columns": cols_summary,
            "relationships": relevant_rels,
        }

        system_prompt = """You are CatalogLens AI, an expert enterprise database analyst specializing in IBM Db2 LUW catalogs.
Your task is to analyze the provided table metadata and return a structured JSON object explaining its business context.

STRICT ACCURACY RULES:
1. ONLY reference tables and columns that appear in the provided context. Never invent tables or columns.
2. Differentiate between verified facts (catalog foreign keys/PKs) and inferences.
3. If information is ambiguous, explicitly state it in 'uncertainties'.
4. Respond with VALID JSON ONLY matching the requested structure. Do not surround with markdown code blocks if possible.

JSON Response Structure:
{
  "likely_business_purpose": "Clear 2-3 sentence explanation of the business domain and role",
  "important_columns": [
    {
      "column_name": "EXACT_COL_NAME",
      "role_description": "Explanation of its business meaning",
      "significance": "PRIMARY_IDENTIFIER|FOREIGN_LINK|BUSINESS_METRIC|STATUS_CODE|AUDIT"
    }
  ],
  "relationships_summary": ["Human readable description of relationships"],
  "likely_business_workflow": "Name and explanation of the primary business workflow",
  "evidence": [
    {
      "claim": "Statement about the table",
      "source": "SYSCAT.COLUMNS or SYSCAT.REFERENCES",
      "observation": "Exact observation from metadata",
      "confidence": 0.95,
      "status": "verified_fact|metadata_supported|ai_hypothesis",
      "referenced_tables": ["TABLE1"],
      "referenced_columns": ["COL1"]
    }
  ],
  "uncertainties": ["Things that cannot be determined with certainty from catalog alone"],
  "verification_questions": ["Questions to ask the lead database architect"]
}
"""

        message = self._client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this Db2 table metadata:\n\n{json.dumps(prompt_payload, indent=2)}",
                }
            ],
        )

        raw_response = message.content[0].text.strip()
        # Clean any accidental markdown backticks
        if raw_response.startswith("```json"):
            raw_response = raw_response[7:]
        if raw_response.startswith("```"):
            raw_response = raw_response[3:]
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3]

        parsed = json.loads(raw_response.strip())

        # Construct typed Pydantic TableUnderstanding
        col_roles = [
            ColumnRole(
                column_name=c.get("column_name", ""),
                role_description=c.get("role_description", ""),
                significance=c.get("significance", "BUSINESS_METRIC"),
            )
            for c in parsed.get("important_columns", [])
        ]

        evidence_list = []
        for e in parsed.get("evidence", []):
            item = EvidenceItem(
                source=e.get("source", "SYSCAT.COLUMNS"),
                observation=e.get("observation", ""),
                type="catalog_metadata" if "SYSCAT" in e.get("source", "") else "structural_constraint",
            )
            evidence_list.append(
                EvidenceClaim(
                    claim=e.get("claim", ""),
                    evidence=[item],
                    confidence=float(e.get("confidence", 0.85)),
                    status=e.get("status", "ai_hypothesis"),
                    verified_by_engine=False,
                    referenced_tables=e.get("referenced_tables", [table.tabname]),
                    referenced_columns=e.get("referenced_columns", []),
                )
            )

        return TableUnderstanding(
            table_name=table.tabname,
            likely_business_purpose=parsed.get("likely_business_purpose", ""),
            important_columns=col_roles,
            relationships_summary=parsed.get("relationships_summary", []),
            likely_business_workflow=parsed.get("likely_business_workflow", ""),
            evidence=evidence_list,
            uncertainties=parsed.get("uncertainties", []),
            verification_questions=parsed.get("verification_questions", []),
            is_ai_generated=True,
            model_used=self.settings.anthropic_model,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _deterministic_explain_table(
        self,
        table: DbTable,
        relationships: List[RelationshipEdge],
        schema_name: str,
    ) -> TableUnderstanding:
        """Deterministic heuristic fallback when Anthropic API key is not supplied."""
        # 1. Analyze column roles
        col_roles: List[ColumnRole] = []
        for col in table.columns:
            sig = "BUSINESS_METRIC"
            role = f"Column of type {col.typename}"
            if col.is_primary_key:
                sig = "PRIMARY_IDENTIFIER"
                role = "Unique primary record identifier in Db2 catalog (SYSCAT.TABCONST)"
            elif col.is_foreign_key or any(r.source_column == col.colname for r in relationships):
                sig = "FOREIGN_LINK"
                target = col.foreign_key_target or "target table"
                role = f"Foreign reference to {target}"
            elif "STS" in col.colname or "STATUS" in col.colname or "CD" in col.colname:
                sig = "STATUS_CODE"
                role = "Discrete business lifecycle state or classification code"
            elif "AMT" in col.colname or "PRICE" in col.colname or "QTY" in col.colname:
                sig = "BUSINESS_METRIC"
                role = "Quantitative financial or volume metric"
            elif "DT" in col.colname or "TS" in col.colname or "TIME" in col.colname:
                sig = "AUDIT"
                role = "Temporal timestamp or chronological tracking date"

            if col.remarks:
                role += f": {col.remarks}"

            col_roles.append(ColumnRole(column_name=col.colname, role_description=role, significance=sig))

        # 2. Summarize relationships
        rel_summary: List[str] = []
        for r in relationships:
            if r.source_table == table.tabname:
                rel_summary.append(f"Outgoing reference: {r.source_column} -> {r.target_table}.{r.target_column} ({r.relationship_type.value}, {r.confidence*100:.0f}%)")
            elif r.target_table == table.tabname:
                rel_summary.append(f"Incoming dependent: {r.source_table}.{r.source_column} references this table ({r.relationship_type.value}, {r.confidence*100:.0f}%)")

        # 3. Formulate Purpose
        purpose = table.remarks or f"Core entity '{table.tabname}' managing transactions or master records."
        if table.tabname.endswith("_MST"):
            purpose = f"Master dimension entity storing persistent reference data for {table.tabname.replace('_MST', '').title()}."
        elif table.tabname.endswith("_HDR"):
            purpose = f"Transactional parent header entity orchestrating high-level order or dispatch cycles for {table.tabname.replace('_HDR', '').title()}."
        elif table.tabname.endswith("_LINE") or table.tabname.endswith("_ITEM"):
            purpose = f"Granular line-item breakdown detailing individual catalog products associated with parent contracts."

        # 4. Formulate Evidence
        evidence = [
            EvidenceClaim(
                claim=f"'{table.tabname}' is a verified table containing {len(table.columns)} columns in schema '{schema_name}'.",
                evidence=[
                    EvidenceItem(source="SYSCAT.TABLES", observation=f"Object registered with CARD={table.card}", type="catalog_metadata"),
                    EvidenceItem(source="SYSCAT.COLUMNS", observation=f"{len(table.columns)} columns extracted", type="catalog_metadata"),
                ],
                confidence=1.0,
                status="verified_fact",
                verified_by_engine=True,
                referenced_tables=[table.tabname],
                referenced_columns=[f"{table.tabname}.{c.colname}" for c in table.columns[:3]],
            )
        ]

        # 5. Formulate Uncertainties
        uncertainties = [
            "Table has not yet been audited by an enterprise subject matter expert.",
        ]
        if any(r.relationship_type.value == "INFERRED" for r in relationships if r.source_table == table.tabname):
            uncertainties.append("Contains undocumented foreign linkages inferred from column naming patterns without catalog constraints.")

        # 6. Verification Questions
        questions = [
            f"What upstream ETL or microservice is the primary producer of rows into {table.tabname}?",
            f"Are there data retention or archiving policies applied to historical records in {table.tabname}?",
        ]

        return TableUnderstanding(
            table_name=table.tabname,
            likely_business_purpose=purpose,
            important_columns=col_roles,
            relationships_summary=rel_summary if rel_summary else ["No direct catalog relationships found."],
            likely_business_workflow="Enterprise Commercial & Order Fulfillment System",
            evidence=evidence,
            uncertainties=uncertainties,
            verification_questions=questions,
            is_ai_generated=False,
            model_used="Deterministic Heuristic Engine (Claude API Not Configured)",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
