"""Aggregates every v1 route (single place to see the public surface)."""

from fastapi import APIRouter

from app.api.v1 import approvals, audit, chat, config, dba, health, knowledge, sql, status

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(status.router)
api_router.include_router(config.router)
api_router.include_router(chat.router)
api_router.include_router(sql.router)
api_router.include_router(dba.router)
api_router.include_router(audit.router)
api_router.include_router(approvals.router)
api_router.include_router(knowledge.router)

__all__ = ["api_router"]
