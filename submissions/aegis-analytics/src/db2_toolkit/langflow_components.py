"""Langflow IBM Db2 Extension Components and Flow Exporter (lfx-ibm).

Provides reusable visual flow templates and node definitions for drag-and-drop
no-code multi-agent and RAG orchestration backed by IBM Db2 LUW.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FlowNode:
    """Represents a visual Langflow graph node."""

    id: str
    name: str
    display_name: str
    description: str
    node_type: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})


@dataclass
class FlowEdge:
    """Represents a directed link between nodes in a Langflow graph."""

    source: str
    target: str
    source_handle: str
    target_handle: str


class Db2LangflowBuilder:
    """Builds and serializes IBM Db2 visual flows into standard Langflow JSON."""

    def __init__(self, flow_name: str = "Aegis IBM Db2 Intelligence Pipeline") -> None:
        self.flow_name = flow_name
        self.nodes: List[FlowNode] = []
        self.edges: List[FlowEdge] = []
        self._build_default_pipeline()

    def _build_default_pipeline(self) -> None:
        """Constructs default multi-stage Db2 workflow."""
        # 1. Connection Node
        n1 = FlowNode(
            id="node_db2_conn",
            name="Db2Connection",
            display_name="IBM Db2 Connection",
            description="Manages native ibm_db connection pool or mock sandbox fallback.",
            node_type="Database",
            inputs={
                "database": "BLUDB",
                "hostname": "localhost",
                "port": 50000,
                "security": "NONE",
            },
            outputs=["connection_pool"],
            position={"x": 100.0, "y": 200.0},
        )
        self.nodes.append(n1)

        # 2. SQL Transpiler Node
        n2 = FlowNode(
            id="node_sql_transpiler",
            name="Db2SQLGlotTranspiler",
            display_name="SQLGlot Db2 Transpiler",
            description="Transpiles Postgres/SQLite queries to Db2 syntax (FETCH FIRST n ROWS).",
            node_type="DataProcessing",
            inputs={"source_dialect": "postgres"},
            outputs=["db2_sql"],
            position={"x": 400.0, "y": 100.0},
        )
        self.nodes.append(n2)

        # 3. Vector RAG Node
        n3 = FlowNode(
            id="node_vector_rag",
            name="Db2VectorStore",
            display_name="IBM Db2 Vector Store",
            description="Performs semantic cosine retrieval over documents stored in Db2.",
            node_type="VectorStore",
            inputs={"table_name": "DB2_VECTOR_STORE", "top_k": 3},
            outputs=["retrieved_documents"],
            position={"x": 400.0, "y": 300.0},
        )
        self.nodes.append(n3)

        # 4. Multi-Agent Risk Auditor Node
        n4 = FlowNode(
            id="node_risk_auditor",
            name="Db2CrewRiskAuditor",
            display_name="Db2 CrewAI Risk Auditor",
            description="Autonomous multi-agent crew auditing conformal residuals and market bars.",
            node_type="Agent",
            inputs={"alpha": 0.05, "symbol": "AAPL"},
            outputs=["executive_briefing", "audit_metrics"],
            position={"x": 750.0, "y": 200.0},
        )
        self.nodes.append(n4)

        # Edges
        self.edges.append(
            FlowEdge(
                source="node_db2_conn",
                target="node_sql_transpiler",
                source_handle="connection_pool",
                target_handle="connection_pool",
            )
        )
        self.edges.append(
            FlowEdge(
                source="node_db2_conn",
                target="node_vector_rag",
                source_handle="connection_pool",
                target_handle="connection_pool",
            )
        )
        self.edges.append(
            FlowEdge(
                source="node_db2_conn",
                target="node_risk_auditor",
                source_handle="connection_pool",
                target_handle="connection_pool",
            )
        )

    def export_flow_dict(self) -> Dict[str, Any]:
        """Exports graph structure as a standard Langflow dictionary."""
        return {
            "name": self.flow_name,
            "description": "Visual drag-and-drop workflow for IBM Db2 financial analytics & RAG.",
            "data": {
                "nodes": [asdict(n) for n in self.nodes],
                "edges": [asdict(e) for e in self.edges],
            },
        }

    def export_flow_json(self, indent: int = 2) -> str:
        """Serializes flow dictionary into formatted JSON string."""
        return json.dumps(self.export_flow_dict(), indent=indent)

