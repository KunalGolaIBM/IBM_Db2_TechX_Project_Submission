"""
CatalogLens API Client.
Provides typed access to FastAPI backend endpoints with graceful direct fallback
when running Streamlit standalone.
"""
from typing import Any, Dict, List, Optional
import os
import requests

from backend.core.config import get_settings
from backend.db.metadata_extractor import MetadataExtractor
from backend.db.connection import Db2ConnectionManager
from backend.services.relationship_detector import RelationshipDetector
from backend.services.dependency_analyzer import DependencyAnalyzer
from backend.services.workflow_detector import WorkflowDetector
from backend.graph.investigation_graph import create_investigation_graph

settings = get_settings()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8001")


class CatalogLensAPIClient:
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            resp = requests.get(f"{self.base_url}{path}", params=params, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _post(self, path: str, json_data: Dict[str, Any]) -> Any:
        try:
            resp = requests.post(f"{self.base_url}{path}", json=json_data, timeout=30)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_health(self) -> Dict[str, Any]:
        data = self._get("/api/health")
        if data:
            return data
        return {
            "status": "online (direct)",
            "version": settings.app_version,
            "ibm_db_driver_installed": Db2ConnectionManager.is_driver_available(),
            "anthropic_configured": settings.has_anthropic_key(),
            "anthropic_model": settings.anthropic_model,
            "demo_mode": settings.demo_mode,
        }

    def test_connection(self, host, port, database, username, password, security) -> Dict[str, Any]:
        payload = {
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
            "security": security,
        }
        res = self._post("/api/connection/test", payload)
        if res:
            return res
        # Direct fallback
        mgr = Db2ConnectionManager(host, port, database, username, password, security)
        return mgr.test_connection()

    def get_schemas(self, use_demo: bool = True) -> List[str]:
        data = self._get("/api/schemas", {"use_demo": use_demo})
        if data is not None:
            return data
        extractor = MetadataExtractor()
        return extractor.list_schemas(use_demo=use_demo)

    def get_metadata(self, schema_name: str = "ENTERPRISE", use_demo: bool = True) -> Dict[str, Any]:
        data = self._get("/api/metadata", {"schema_name": schema_name, "use_demo": use_demo})
        if data is not None:
            return data
        extractor = MetadataExtractor()
        meta = extractor.extract_schema_metadata(schema_name, use_demo=use_demo)
        return meta.model_dump() if hasattr(meta, "model_dump") else meta.dict()

    def get_relationships(self, schema_name: str = "ENTERPRISE", use_demo: bool = True) -> List[Dict[str, Any]]:
        data = self._get("/api/relationships", {"schema_name": schema_name, "use_demo": use_demo})
        if data is not None:
            return data
        extractor = MetadataExtractor()
        meta = extractor.extract_schema_metadata(schema_name, use_demo=use_demo)
        detector = RelationshipDetector()
        rels = detector.discover_relationships(meta)
        return [(r.model_dump() if hasattr(r, "model_dump") else r.dict()) for r in rels]

    def analyze_table(self, table_name: str, schema_name: str = "ENTERPRISE", question: Optional[str] = None, use_demo: bool = True) -> Dict[str, Any]:
        payload = {
            "table_name": table_name,
            "schema_name": schema_name,
            "question": question,
            "use_demo": use_demo,
        }
        res = self._post("/api/analyze/table", payload)
        if res:
            return res
        # Direct fallback via LangGraph
        graph = create_investigation_graph()
        initial_state = {
            "schema_name": schema_name,
            "selected_table": table_name,
            "investigation_question": question,
            "use_demo": use_demo,
            "metadata": None,
            "declared_relationships": [],
            "inferred_relationships": [],
            "table_evidence_ledger": [],
            "ai_understanding": None,
            "validated_evidence": [],
            "discrepancies": [],
            "final_report": None,
            "errors": [],
        }
        final_state = graph.invoke(initial_state)
        return final_state.get("final_report", {})

    def analyze_workflows(self, schema_name: str = "ENTERPRISE", use_demo: bool = True) -> List[Dict[str, Any]]:
        payload = {"schema_name": schema_name, "use_demo": use_demo}
        res = self._post("/api/analyze/workflow", payload)
        if res:
            return res
        extractor = MetadataExtractor()
        meta = extractor.extract_schema_metadata(schema_name, use_demo=use_demo)
        detector = RelationshipDetector()
        rels = detector.discover_relationships(meta)
        wf_detector = WorkflowDetector()
        wfs = wf_detector.discover_workflows(meta, rels)
        return [w.dict() for w in wfs]

    def investigate_dependencies(self, target_object: str, schema_name: str = "ENTERPRISE", use_demo: bool = True) -> Dict[str, Any]:
        payload = {"target_object": target_object, "schema_name": schema_name, "use_demo": use_demo}
        res = self._post("/api/investigate/dependencies", payload)
        if res:
            return res
        extractor = MetadataExtractor()
        meta = extractor.extract_schema_metadata(schema_name, use_demo=use_demo)
        detector = RelationshipDetector()
        rels = detector.discover_relationships(meta)
        analyzer = DependencyAnalyzer(meta, rels)
        result = analyzer.investigate(target_object)
        return result.dict()
