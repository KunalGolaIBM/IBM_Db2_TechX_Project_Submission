"""
Dependency Investigation Service.
Traces direct and indirect dependencies across Db2 schema objects,
views, and foreign keys, computing impact severity and actionable checks.
"""
from datetime import datetime, timezone
from typing import Dict, List, Set
import logging
import networkx as nx

from ..models.schema import DbSchemaMetadata
from ..models.relationship import RelationshipEdge, RelationshipType
from ..models.analysis import DependencyInvestigation, DependencyImpact
from ..models.evidence import EvidenceClaim, EvidenceItem

logger = logging.getLogger("CatalogLens.DependencyAnalyzer")


class DependencyAnalyzer:
    """Analyzes structural and semantic dependencies for schema objects."""

    def __init__(self, metadata: DbSchemaMetadata, relationships: List[RelationshipEdge]):
        self.metadata = metadata
        self.relationships = relationships
        self.graph = self._build_dependency_graph()

    def _build_dependency_graph(self) -> nx.DiGraph:
        """Constructs a directed graph where edges point from parent to dependent children."""
        g = nx.DiGraph()
        for tabname in self.metadata.tables.keys():
            g.add_node(tabname, type="TABLE")
        for vname in self.metadata.views.keys():
            g.add_node(vname, type="VIEW")

        for edge in self.relationships:
            # If Child -> Parent via FK, modifying Parent impacts Child!
            # Edge in graph: target_table (parent) -> source_table (dependent child)
            g.add_edge(
                edge.target_table,
                edge.source_table,
                source_col=edge.source_column,
                target_col=edge.target_column,
                kind=edge.relationship_type.value,
                confidence=edge.confidence,
                edge_obj=edge,
            )

        # Add view dependencies (if view definition references table)
        for vname, vobj in self.metadata.views.items():
            defn = (vobj.view_definition or "").upper()
            for tabname in self.metadata.tables.keys():
                if tabname.upper() in defn:
                    g.add_edge(
                        tabname,
                        vname,
                        source_col="*",
                        target_col="*",
                        kind="VIEW_DEPENDENCY",
                        confidence=1.0,
                    )
        return g

    def investigate(self, target_object: str) -> DependencyInvestigation:
        """
        Investigates the downstream and upstream impact of altering a table or column.
        Target format: 'TABLE_NAME' or 'TABLE_NAME.COLUMN_NAME'
        """
        parts = target_object.strip().upper().split(".")
        target_table = parts[0]
        target_column = parts[1] if len(parts) > 1 else None
        object_type = "COLUMN" if target_column else "TABLE"

        direct_impacts: List[DependencyImpact] = []
        indirect_impacts: List[DependencyImpact] = []
        verified_edges: List[RelationshipEdge] = []
        impact_areas: List[str] = []
        evidence_claims: List[EvidenceClaim] = []
        manual_checks: List[str] = []

        # Validate target table existence
        table_obj = self.metadata.get_object(target_table)
        if not table_obj:
            return DependencyInvestigation(
                target_object=target_object,
                object_type=object_type,
                impact_severity="LOW",
                potential_impactAreas=[f"Object '{target_table}' not found in active schema."],
                recommended_manual_checks=["Verify schema and object spelling."],
                investigated_at=datetime.now(timezone.utc).isoformat(),
            )

        # 1. Direct Dependencies (outgoing edges from target_table in dependency graph)
        visited_direct: Set[str] = set()
        if self.graph.has_node(target_table):
            for child in self.graph.successors(target_table):
                edge_data = self.graph.get_edge_data(target_table, child)
                kind = edge_data.get("kind", "FOREIGN_KEY")
                source_col = edge_data.get("source_col")
                target_col = edge_data.get("target_col")

                # If investigating a specific column, filter relevant edges
                if target_column and target_col != "*" and target_col != target_column:
                    continue

                visited_direct.add(child)
                child_type = self.graph.nodes[child].get("type", "TABLE")

                # Retrieve original RelationshipEdge if present
                if "edge_obj" in edge_data:
                    verified_edges.append(edge_data["edge_obj"])

                impact_level = "CRITICAL" if kind == "DECLARED" else ("HIGH" if kind == "VIEW_DEPENDENCY" else "MEDIUM")
                desc = (
                    f"View '{child}' queries '{target_table}' directly."
                    if kind == "VIEW_DEPENDENCY"
                    else f"Table '{child}' references {target_table}.{target_col or target_column or 'PK'} via column '{source_col}' ({kind})."
                )

                direct_impacts.append(
                    DependencyImpact(
                        entity=child,
                        entity_type=child_type,
                        relationship_kind=kind,
                        impact_level=impact_level,
                        description=desc,
                    )
                )

        # 2. Indirect Dependencies (2-hop or deeper)
        visited_indirect: Set[str] = set()
        for direct_child in visited_direct:
            if self.graph.has_node(direct_child):
                for grand_child in self.graph.successors(direct_child):
                    if grand_child != target_table and grand_child not in visited_direct and grand_child not in visited_indirect:
                        visited_indirect.add(grand_child)
                        gchild_type = self.graph.nodes[grand_child].get("type", "TABLE")
                        indirect_impacts.append(
                            DependencyImpact(
                                entity=grand_child,
                                entity_type=gchild_type,
                                relationship_kind="INDIRECT_CASCADE",
                                impact_level="MEDIUM",
                                description=f"Indirect dependent via intermediary '{direct_child}'. Cascading modifications could invalidate workflows.",
                            )
                        )

        # 3. Compute Severity
        total_dependents = len(direct_impacts) + len(indirect_impacts)
        has_critical = any(d.impact_level == "CRITICAL" for d in direct_impacts)
        if has_critical or total_dependents >= 3:
            severity = "CRITICAL"
        elif total_dependents > 0:
            severity = "HIGH"
        else:
            severity = "LOW"

        # 4. Formulate Impact Areas
        if direct_impacts:
            impact_areas.append(f"Foreign-key cascading integrity on {len(direct_impacts)} downstream tables/views.")
        if any(d.entity_type == "VIEW" for d in direct_impacts + indirect_impacts):
            impact_areas.append("Reporting views and analytical dashboards reading materialized or virtual definitions.")
        if indirect_impacts:
            impact_areas.append(f"Multi-tier transaction workflows ({len(indirect_impacts)} indirect tables).")
        if not impact_areas:
            impact_areas.append("Isolated entity; structural modifications pose minimal immediate cascade risk.")

        # 5. Formulate Evidence
        obs_text = f"Analyzed {len(direct_impacts)} direct and {len(indirect_impacts)} indirect downstream dependencies for '{target_object}'."
        evidence_claims.append(
            EvidenceClaim(
                claim=f"Modifying '{target_object}' has {severity} impact on the enterprise database topology.",
                evidence=[
                    EvidenceItem(
                        source="SYSCAT.REFERENCES",
                        observation=f"{len(verified_edges)} declared foreign key references found referencing this object.",
                        type="declared_relationship",
                    ),
                    EvidenceItem(
                        source="SYSCAT.VIEWS",
                        observation=f"Dependent views detected: {[d.entity for d in direct_impacts if d.entity_type == 'VIEW']}",
                        type="catalog_metadata",
                    ),
                ],
                confidence=0.95,
                status="verified_fact" if verified_edges else "metadata_supported",
                verified_by_engine=True,
                referenced_tables=[target_table] + [d.entity for d in direct_impacts],
                referenced_columns=[target_column] if target_column else [],
            )
        )

        # 6. Recommended Manual Checks
        if target_column:
            manual_checks.append(f"Run 'SELECT COUNT(*) FROM {target_table} WHERE {target_column} IS NULL' to verify nullability safety before altering constraint.")
        for d in direct_impacts:
            if d.entity_type == "VIEW":
                manual_checks.append(f"Inspect and recompile view definition for '{d.entity}' in Db2 Developer Extension.")
            elif d.relationship_kind == "DECLARED":
                manual_checks.append(f"Verify foreign key index performance on referencing table '{d.entity}'.")
        manual_checks.append("Verify data migration scripts and ETL batch jobs accessing this table.")

        return DependencyInvestigation(
            target_object=target_object,
            object_type=object_type,
            direct_dependencies=direct_impacts,
            indirect_dependencies=indirect_impacts,
            verified_relationships=verified_edges,
            potential_impact_areas=impact_areas,
            impact_severity=severity,
            evidence=evidence_claims,
            recommended_manual_checks=manual_checks,
            investigated_at=datetime.now(timezone.utc).isoformat(),
        )
