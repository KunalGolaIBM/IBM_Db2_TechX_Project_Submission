"""DBA tools: fixed, parameterized catalog (SYSCAT) and monitoring (MON_GET_*) queries.

- ``GET  /api/v1/dba/tools``               — list tools and their parameters.
- ``POST /api/v1/dba/tools/{id}/run``      — run one tool (validated params).

Tools accept identifiers and a row limit only — never SQL.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import build_dba_service
from app.schemas.dba import DbaRunRequest, DbaRunResponse, DbaToolsResponse

router = APIRouter(tags=["dba"])


@router.get("/dba/tools", response_model=DbaToolsResponse)
def list_dba_tools(request: Request) -> DbaToolsResponse:
    return build_dba_service(request).list_tools()


@router.post("/dba/tools/{tool_id}/run", response_model=DbaRunResponse)
def run_dba_tool(
    tool_id: str, payload: DbaRunRequest, request: Request
) -> DbaRunResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
    return build_dba_service(request).run(
        tool_id,
        payload.params,
        request_id=request_id,
        session_id=payload.session_id,
    )
