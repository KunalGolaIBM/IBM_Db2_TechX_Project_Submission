from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query, Path
from app.models.schemas import (
    AnomalyListResponse, AnomalyItem, AnomalyExplainResponse,
    UpdateAnomalyStatusRequest, UpdateAnomalyStatusResponse,
    InsightsResponse, InsightItem,
    FinancialInsightsResponse, MonthlyReportResponse
)
from app.services.anomaly_engine import anomaly_engine
from app.services.insights_service import insights_service
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["Anomalies & Insights"])

def verify_token(x_service_token: str):
    if settings.ai_service_internal_token and x_service_token != settings.ai_service_internal_token:
        raise HTTPException(status_code=401, detail="Invalid service authorization token.")

@router.get("/anomalies", response_model=AnomalyListResponse)
def list_anomalies(
    user_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    alert_type: Optional[str] = Query(default=None),
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    verify_token(x_service_token)
    uid = user_id or settings.demo_user_id
    anomalies_data = anomaly_engine.list_anomalies(
        uid,
        status=status,
        severity=severity,
        alert_type=alert_type
    )
    items = [AnomalyItem(**a) for a in anomalies_data]

    return AnomalyListResponse(
        user_id=uid,
        total_anomalies=len(items),
        anomalies=items
    )

@router.get("/anomalies/{alert_id}", response_model=AnomalyItem)
def get_anomaly_by_id(
    alert_id: str = Path(...),
    user_id: Optional[str] = Query(default=None),
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    verify_token(x_service_token)
    uid = user_id or settings.demo_user_id
    data = anomaly_engine.get_anomaly(alert_id, uid)
    if not data:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return AnomalyItem(**data)

@router.post("/anomalies/{alert_id}/explain", response_model=AnomalyExplainResponse)
def explain_anomaly(
    alert_id: str = Path(...),
    user_id: Optional[str] = Query(default=None),
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    verify_token(x_service_token)
    uid = user_id or settings.demo_user_id
    try:
        res = anomaly_engine.explain_anomaly(alert_id, uid)
        return AnomalyExplainResponse(**res)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

@router.patch("/anomalies/{alert_id}/status", response_model=UpdateAnomalyStatusResponse)
def update_anomaly_status(
    alert_id: str = Path(...),
    req: UpdateAnomalyStatusRequest = ...,
    user_id: Optional[str] = Query(default=None),
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    verify_token(x_service_token)
    uid = user_id or settings.demo_user_id
    try:
        res = anomaly_engine.update_anomaly_status(alert_id, uid, req.status)
        return UpdateAnomalyStatusResponse(**res)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found or access denied.")

@router.get("/insights", response_model=FinancialInsightsResponse)
def get_insights(
    user_id: Optional[str] = Query(default=None),
    month: Optional[str] = Query(default=None),
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    verify_token(x_service_token)
    uid = user_id or settings.demo_user_id
    try:
        data = insights_service.get_monthly_insights(uid, month=month)
        return FinancialInsightsResponse(**data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.get("/reports/monthly", response_model=MonthlyReportResponse)
def get_monthly_report(
    user_id: Optional[str] = Query(default=None),
    month: Optional[str] = Query(default=None),
    x_service_token: str = Header(default="dev_internal_secret_token")
):
    verify_token(x_service_token)
    uid = user_id or settings.demo_user_id
    try:
        data = insights_service.get_monthly_report(uid, month=month)
        return MonthlyReportResponse(**data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
