"""Root API router aggregating all domain sub-routers."""

from fastapi import APIRouter

from auth.router import router as auth_router
from groups.router import router as groups_router
from payments.router import router as payments_router
from cash.router import router as cash_router
from approvals.router import router as approvals_router
from expenses.router import router as expenses_router
from api.summary import router as summary_router
from settlement.router import router as settlement_router
from ai.router import router as ai_router
from audit.router import router as audit_router

api_router = APIRouter()

# Domain routes
api_router.include_router(auth_router)
api_router.include_router(groups_router)
api_router.include_router(payments_router)
api_router.include_router(cash_router)
api_router.include_router(approvals_router)
api_router.include_router(expenses_router)
api_router.include_router(summary_router)
api_router.include_router(settlement_router)
api_router.include_router(ai_router)
api_router.include_router(audit_router)

# Alias for compatibility with main.py
router = api_router
