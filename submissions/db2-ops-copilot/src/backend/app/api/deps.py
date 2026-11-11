"""Dependency injection wiring.

Adapters live on ``app.state.registry`` (built once during startup lifespan);
services are constructed per request so tests can swap settings/registry
cleanly via ``app.dependency_overrides``.
"""

from __future__ import annotations

from fastapi import Request

from app.adapters.registry import AdapterRegistry
from app.core.config import Settings, get_settings
from app.services.approval_service import ApprovalService
from app.services.chat_service import ChatService
from app.services.dba_service import DbaService
from app.services.explain_service import ExplainService
from app.services.health_service import HealthService
from app.services.sql_execution_service import SqlExecutionService
from app.services.sql_guard_service import SqlGuardService
from app.services.status_service import StatusService


def get_app_settings() -> Settings:
    return get_settings()


def get_registry(request: Request) -> AdapterRegistry:
    return request.app.state.registry


def get_started_at(request: Request) -> float:
    return request.app.state.started_at


def build_approval_service(request: Request) -> ApprovalService:
    return ApprovalService(
        get_settings(), get_registry(request), request.app.state.approval_store
    )


def build_health_service(request: Request) -> HealthService:
    return HealthService(get_settings(), get_registry(request))


def build_status_service(request: Request) -> StatusService:
    return StatusService(get_settings(), get_registry(request))


def build_chat_service(request: Request) -> ChatService:
    return ChatService(get_settings(), get_registry(request))


def build_sql_guard(request: Request) -> SqlGuardService:
    return SqlGuardService(get_registry(request).validator)


def build_dba_service(request: Request) -> DbaService:
    return DbaService(get_settings(), get_registry(request))


def build_explain_service(request: Request) -> ExplainService:
    registry = get_registry(request)
    return ExplainService(
        get_settings(), registry, SqlGuardService(registry.validator)
    )


def build_sql_execution(request: Request) -> SqlExecutionService:
    registry = get_registry(request)
    return SqlExecutionService(
        get_settings(), registry, SqlGuardService(registry.validator)
    )
