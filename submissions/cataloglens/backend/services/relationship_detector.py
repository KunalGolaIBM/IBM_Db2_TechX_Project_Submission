"""
Intelligent Relationship Discovery Service.
Extracts declared foreign keys as verified facts and detects
candidate inferred relationships through deterministic heuristic analysis:
- Exact primary key column name matches
- Prefix/Suffix enterprise conventions (e.g., CUST_ID, CUST_REF_NO)
- Compatible data types validation
- Verification status and confidence scoring
"""
from typing import Dict, List, Set, Tuple
import logging

from ..models.schema import DbSchemaMetadata, DbTable, DbColumn
from ..models.relationship import (
    RelationshipEdge,
    RelationshipType,
    VerificationStatus,
)

logger = logging.getLogger("CatalogLens.RelationshipDetector")


class RelationshipDetector:
    """Discovers declared and inferred foreign key relationships."""

    # Data type compatibility groups
    INTEGER_TYPES = {"BIGINT", "INTEGER", "SMALLINT", "INT"}
    TEXT_TYPES = {"VARCHAR", "CHAR", "CLOB", "CHARACTER"}
    DECIMAL_TYPES = {"DECIMAL", "NUMERIC", "FLOAT", "DOUBLE"}

    @classmethod
    def are_types_compatible(cls, type1: str, type2: str) -> bool:
        t1, t2 = type1.strip().upper(), type2.strip().upper()
        if t1 == t2:
            return True
        if t1 in cls.INTEGER_TYPES and t2 in cls.INTEGER_TYPES:
            return True
        if t1 in cls.TEXT_TYPES and t2 in cls.TEXT_TYPES:
            return True
        if t1 in cls.DECIMAL_TYPES and t2 in cls.DECIMAL_TYPES:
            return True
        return False

    def discover_relationships(self, metadata: DbSchemaMetadata) -> List[RelationshipEdge]:
        """Discovers both declared and inferred relationships across the schema."""
        edges: List[RelationshipEdge] = []
        declared_pairs: Set[Tuple[str, str, str, str]] = set()

        # 1. Collect Declared Relationships (from SYSCAT.REFERENCES)
        for tabname, table in metadata.tables.items():
            for fk in table.foreign_keys:
                edge_id = f"decl_{fk.source_table}_{fk.source_column}_to_{fk.target_table}_{fk.target_column}"
                edge = RelationshipEdge(
                    id=edge_id,
                    source_table=fk.source_table,
                    source_column=fk.source_column,
                    target_table=fk.target_table,
                    target_column=fk.target_column,
                    relationship_type=RelationshipType.DECLARED,
                    confidence=1.0,
                    reason=f"Db2 catalog foreign key constraint: {fk.constraint_name}",
                    evidence_notes=[
                        f"Constraint '{fk.constraint_name}' recorded in SYSCAT.REFERENCES",
                        f"Delete rule: {fk.delete_rule}, Update rule: {fk.update_rule}",
                        f"Target table primary key column: {fk.target_column}",
                    ],
                    constraint_name=fk.constraint_name,
                    verification_status=VerificationStatus.VERIFIED_FACT,
                )
                edges.append(edge)
                declared_pairs.add((
                    fk.source_table.upper(),
                    fk.source_column.upper(),
                    fk.target_table.upper(),
                    fk.target_column.upper(),
                ))

        # 2. Inferred Relationships
        # Build index of primary key columns per table
        pk_index: Dict[str, List[Tuple[str, DbColumn]]] = {}  # {col_name: [(table_name, col_obj)]}
        for tabname, table in metadata.tables.items():
            for pk_col_name in table.primary_keys:
                col_obj = table.get_column(pk_col_name)
                if col_obj:
                    pk_index.setdefault(pk_col_name.upper(), []).append((tabname, col_obj))

        # Scan each table's columns for candidate relationships
        for tabname, table in metadata.tables.items():
            for col in table.columns:
                col_name_upper = col.colname.upper()

                # Skip if column is primary key of the same table
                if col_name_upper in [pk.upper() for pk in table.primary_keys]:
                    continue

                # Heuristic A: Exact column name matches another table's primary key
                if col_name_upper in pk_index:
                    for target_table, target_pk_col in pk_index[col_name_upper]:
                        if target_table.upper() == tabname.upper():
                            continue

                        pair = (tabname.upper(), col_name_upper, target_table.upper(), target_pk_col.colname.upper())
                        if pair in declared_pairs:
                            continue

                        # Check data type compatibility
                        compatible = self.are_types_compatible(col.typename, target_pk_col.typename)
                        if not compatible:
                            continue

                        conf = 0.92
                        edge_id = f"inf_{tabname}_{col.colname}_to_{target_table}_{target_pk_col.colname}"
                        edge = RelationshipEdge(
                            id=edge_id,
                            source_table=tabname,
                            source_column=col.colname,
                            target_table=target_table,
                            target_column=target_pk_col.colname,
                            relationship_type=RelationshipType.INFERRED,
                            confidence=conf,
                            reason=f"Column '{col.colname}' identically matches primary key of '{target_table}' with compatible type ({col.typename} ~ {target_pk_col.typename})",
                            evidence_notes=[
                                f"Source column '{tabname}.{col.colname}' ({col.typename}) matches '{target_table}.{target_pk_col.colname}'",
                                f"No explicit foreign key constraint declared in SYSCAT.REFERENCES (Undocumented enterprise linkage)",
                                f"High confidence ({conf*100:.0f}%) based on exact structural identity",
                            ],
                            constraint_name=None,
                            verification_status=VerificationStatus.METADATA_SUPPORTED,
                        )
                        edges.append(edge)
                        declared_pairs.add(pair)

                # Heuristic B: Prefix/Suffix semantic patterns (e.g. CUST_REF_NO -> CUST_ID)
                for pk_col_name, pk_targets in pk_index.items():
                    for target_table, target_pk_col in pk_targets:
                        if target_table.upper() == tabname.upper():
                            continue

                        pair = (tabname.upper(), col_name_upper, target_table.upper(), target_pk_col.colname.upper())
                        if pair in declared_pairs:
                            continue

                        # Only consider columns whose names indicate a reference.
                        # This prevents quantity/status fields such as ORDER_QTY
                        # from being mistaken for foreign-key candidates.
                        is_reference_like = col_name_upper.endswith(
                            ("_ID", "_REF", "_REF_NO")
                        )
                        is_prefix_match = False
                        matched_token = ""

                        if is_reference_like:
                            for token in ["CUST", "ORDER", "PROD", "WH", "SUPP", "PM", "SHIP"]:
                                if col_name_upper.startswith(token) and target_pk_col.colname.upper().startswith(token):
                                    is_prefix_match = True
                                    matched_token = token
                                    break

                        if is_prefix_match and self.are_types_compatible(col.typename, target_pk_col.typename):
                            conf = 0.78
                            edge_id = f"inf_{tabname}_{col.colname}_to_{target_table}_{target_pk_col.colname}"
                            edge = RelationshipEdge(
                                id=edge_id,
                                source_table=tabname,
                                source_column=col.colname,
                                target_table=target_table,
                                target_column=target_pk_col.colname,
                                relationship_type=RelationshipType.INFERRED,
                                confidence=conf,
                                reason=f"Column '{col.colname}' shares entity prefix '{matched_token}' with '{target_table}.{target_pk_col.colname}' and compatible type",
                                evidence_notes=[
                                    f"Detected prefix pattern '{matched_token}_*' in undocumented column '{tabname}.{col.colname}'",
                                    f"Compatible types: {col.typename} and {target_pk_col.typename}",
                                    f"Likely legacy or denormalized reference to {target_table}",
                                ],
                                constraint_name=None,
                                verification_status=VerificationStatus.HYPOTHESIS_UNVERIFIED,
                            )
                            edges.append(edge)
                            declared_pairs.add(pair)

        return edges
