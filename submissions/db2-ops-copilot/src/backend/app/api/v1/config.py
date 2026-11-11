"""GET /api/v1/config — effective non-secret configuration for the UI.

Secrets (``DB2_RO_PASSWORD``, instance passwords, tokens) are never included:
the schema has no field for them and settings hold them as ``SecretStr``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.security.sql_policy import DEFAULT_POLICY
from app.schemas.status import (
    ConfigResponse,
    DatabaseConfigView,
    ModelsConfigView,
    SecurityConfigView,
    SqlPolicyView,
)

router = APIRouter(tags=["config"])


@router.get("/config", response_model=ConfigResponse)
def get_config(settings: Settings = Depends(get_app_settings)) -> ConfigResponse:
    return ConfigResponse(
        environment=settings.environment,
        debug=settings.debug,
        adapter_mode=settings.adapter_mode,
        api_base=settings.api_v1_prefix,
        cors_origins=settings.cors_origins_list,
        serve_frontend=settings.serve_frontend,
        database=DatabaseConfigView(
            host=settings.db2_host,
            port=settings.db2_port,
            name=settings.db2_dbname,
            read_only_user=settings.db2_ro_user,
        ),
        models=ModelsConfigView(
            llm=settings.ollama_llm_model,
            embeddings=settings.ollama_embed_model,
            ollama_base_url=settings.ollama_base_url,
        ),
        sql_policy=SqlPolicyView(
            allowed_statements=list(DEFAULT_POLICY.allowed_statements),
            max_sql_length=settings.sql_max_length,
            max_ast_nodes=settings.sql_max_ast_nodes,
            max_rows=settings.sql_max_rows,
            query_timeout_ms=settings.sql_query_timeout_ms,
            denied_schemas=settings.denied_schemas_list,
            enforce_row_limit=settings.sql_enforce_row_limit,
        ),
        security=SecurityConfigView(
            injection_mode=settings.injection_mode,
            max_message_length=settings.security_max_message_length,
        ),
    )
