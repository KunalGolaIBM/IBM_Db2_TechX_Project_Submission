from fastapi import APIRouter, HTTPException, Depends, Response, Query
from typing import Any
from app.services import db2_service
from app.services.pdf_report_service import generate_recall_dossier, get_dossier_preview
from app.schemas.models import (
    IncidentResponse,
    TraceResponse,
    ExposureResponse,
    ShipmentItem,
    ActionItem,
    ActionDecisionRequest,
    AuditLogItem,
    CommStatusUpdateRequest,
    InterventionStatusUpdateRequest,
    RecordRecoveryRequest,
    ProposeDispositionRequest,
    ApproveDispositionRequest,
    ExecuteDispositionRequest,
    RegulatoryStageUpdateRequest,
    CloseRecallRequest,
)
from app.agents.workflow import run_lotline_workflow

router = APIRouter(prefix="/api", tags=["LOTLINE"])


@router.get("/health")
def api_health() -> dict[str, str]:
    return {"status": "ok", "service": "LOTLINE Recall Intelligence API", "version": "1.0.0"}


@router.get("/db/health")
def db_health() -> dict[str, Any]:
    try:
        incidents = db2_service.get_all_incidents()
        return {
            "status": "connected",
            "database": "LOTLINE",
            "schema": "LOTLINE_APP",
            "host": "127.0.0.1:50000",
            "incidents_count": len(incidents)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Db2 Connection Failed: {str(e)}")


@router.get("/incidents")
def list_incidents() -> list[dict[str, Any]]:
    try:
        return db2_service.get_all_incidents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}")
def get_incident_detail(incident_id: str) -> dict[str, Any]:
    inc = db2_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc


@router.get("/incidents/{incident_id}/trace")
def get_incident_trace(incident_id: str) -> dict[str, Any]:
    inc = db2_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    source_lot = inc["source_lot_id"]
    trace = db2_service.trace_downstream_lots(source_lot)
    trace["incident_id"] = incident_id
    return trace


@router.get("/incidents/{incident_id}/exposure")
def get_incident_exposure(incident_id: str) -> dict[str, Any]:
    inc = db2_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    source_lot = inc["source_lot_id"]
    exp = db2_service.calculate_exposure(source_lot)
    exp["incident_id"] = incident_id
    return exp


@router.get("/incidents/{incident_id}/shipments")
def get_incident_shipments(incident_id: str) -> list[dict[str, Any]]:
    inc = db2_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    source_lot = inc["source_lot_id"]
    return db2_service.get_shipments_for_incident(source_lot)


@router.get("/incidents/{incident_id}/actions")
def get_incident_actions(incident_id: str) -> list[dict[str, Any]]:
    return db2_service.get_actions_for_incident(incident_id)


@router.post("/incidents/{incident_id}/actions/{action_id}/decision")
def record_action_decision(incident_id: str, action_id: str, payload: ActionDecisionRequest) -> dict[str, Any]:
    try:
        success = db2_service.update_action_decision(
            action_id=action_id,
            decision=payload.decision,
            operator_name=payload.operator_name or "Operator",
            notes=payload.notes
        )
        return {
            "success": success,
            "action_id": action_id,
            "incident_id": incident_id,
            "new_status": payload.decision.upper(),
            "operator": payload.operator_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/audit")
def get_incident_audit(incident_id: str) -> list[dict[str, Any]]:
    return db2_service.get_audit_trail(incident_id)


@router.post("/incidents/{incident_id}/actions/reset")
def reset_incident_actions(incident_id: str) -> dict[str, Any]:
    try:
        success = db2_service.reset_incident_demo_state(incident_id)
        return {
            "success": success,
            "incident_id": incident_id,
            "message": "Demo response actions restored to baseline (ACT-001 APPROVED, ACT-002..004 PROPOSED)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incidents/{incident_id}/agents/run")
def trigger_agentic_workflow(incident_id: str) -> dict[str, Any]:
    try:
        return run_lotline_workflow(incident_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/dossier/preview")
def preview_incident_dossier(incident_id: str) -> dict[str, Any]:
    """Pre-flight check and metadata preview for recall dossier generation."""
    preview = get_dossier_preview(incident_id)
    if not preview:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found in database")
    return preview


@router.get("/incidents/{incident_id}/dossier")
def download_incident_dossier(
    incident_id: str,
    include_fssai: bool = Query(True, description="Include FSSAI Schedule-I draft regulatory profile"),
    operator_name: str = Query("Chief Safety Officer", description="Name/title of operator generating dossier")
):
    """Generate and download official 5-page A4 PDF recall dossier with cryptographic integrity hash."""
    inc = db2_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found in database")
    try:
        pdf_bytes, sha256_digest, metadata = generate_recall_dossier(
            incident_id=incident_id,
            operator_name=operator_name,
            include_fssai=include_fssai
        )
        filename = f"LOTLINE-RECALL-DOSSIER-{incident_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Dossier-SHA256": sha256_digest,
                "X-Report-ID": metadata["report_id"],
                "X-Byte-Size": str(metadata["byte_size"]),
                "X-Generated-At": metadata["generated_at"],
                "Access-Control-Expose-Headers": "Content-Disposition, X-Dossier-SHA256, X-Report-ID, X-Byte-Size, X-Generated-At"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate recall dossier: {str(e)}")


# =============================================================================
# PHASE 5: CLOSED-LOOP RECALL EXECUTION CONTROL TOWER ENDPOINTS
# =============================================================================

@router.get("/incidents/{incident_id}/reconciliation/raw")
def get_raw_mass_reconciliation(incident_id: str) -> dict[str, Any]:
    """A1. Deterministic raw material mass balance reconciliation."""
    inc = db2_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    source_lot_id = inc["source_lot_id"]
    res = db2_service.get_raw_material_reconciliation(source_lot_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Source lot {source_lot_id} not found")
    return res


@router.get("/incidents/{incident_id}/communications")
def list_communications(incident_id: str) -> list[dict[str, Any]]:
    """B1. List downstream consignee communications."""
    return db2_service.get_recall_communications(incident_id)


@router.post("/incidents/{incident_id}/communications/{comm_id}/status")
def update_communication_status_endpoint(
    incident_id: str,
    comm_id: str,
    payload: CommStatusUpdateRequest
) -> dict[str, Any]:
    """B1. Update communication lifecycle state."""
    try:
        success = db2_service.update_communication_status(
            comm_id=comm_id,
            new_status=payload.new_status,
            operator_name=payload.operator_name or "Operator",
            notes=payload.notes,
            delivery_confirmation=payload.delivery_confirmation
        )
        return {"success": success, "comm_id": comm_id, "new_status": payload.new_status.upper()}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/logistics/interventions")
def list_logistics_interventions(incident_id: str) -> list[dict[str, Any]]:
    """B2. List logistics interventions for in-transit shipments."""
    return db2_service.get_logistics_interventions(incident_id)


@router.post("/incidents/{incident_id}/logistics/interventions/{intervention_id}/status")
def update_logistics_intervention_status_endpoint(
    incident_id: str,
    intervention_id: str,
    payload: InterventionStatusUpdateRequest
) -> dict[str, Any]:
    """B2. Update logistics intervention status with carrier evidence."""
    try:
        success = db2_service.update_logistics_intervention(
            intervention_id=intervention_id,
            new_status=payload.new_status,
            operator_name=payload.operator_name or "Logistics Officer",
            cargo_location=payload.cargo_location,
            interception_notes=payload.interception_notes,
            recovered_quantity=payload.recovered_quantity,
            returned_facility_id=payload.returned_facility_id
        )
        return {"success": success, "intervention_id": intervention_id, "new_status": payload.new_status.upper()}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/recoveries")
def list_product_recoveries(incident_id: str) -> list[dict[str, Any]]:
    """B3. List physical product recovery audit entries."""
    return db2_service.get_product_recoveries(incident_id)


@router.post("/incidents/{incident_id}/recoveries")
def record_product_recovery_endpoint(
    incident_id: str,
    payload: RecordRecoveryRequest
) -> dict[str, Any]:
    """B3. Record product recovery with numerical sanity enforcement."""
    try:
        rec_id = db2_service.record_product_recovery(
            incident_id=incident_id,
            lot_id=payload.lot_id,
            source_location_type=payload.source_location_type,
            source_entity_name=payload.source_entity_name,
            quantity_recovered=payload.quantity_recovered,
            unit_of_measure=payload.unit_of_measure or "UNIT",
            storage_facility_id=payload.storage_facility_id or "FAC-PUN",
            verification_method=payload.verification_method or "PHYSICAL_AUDIT",
            operator_name=payload.operator_name or "Quality Control Officer",
            notes=payload.notes
        )
        return {"success": True, "recovery_id": rec_id, "lot_id": payload.lot_id, "quantity_recovered": payload.quantity_recovered}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/recoveries/reconciliation")
def get_recovery_reconciliation(incident_id: str) -> dict[str, Any]:
    """B3. Aggregate recovery reconciliation summary across all finished batches."""
    return db2_service.get_recovery_reconciliation_summary(incident_id)


@router.get("/incidents/{incident_id}/dispositions")
def list_product_dispositions(incident_id: str) -> list[dict[str, Any]]:
    """B4. List product dispositions."""
    return db2_service.get_product_dispositions(incident_id)


@router.post("/incidents/{incident_id}/dispositions")
def propose_product_disposition_endpoint(
    incident_id: str,
    payload: ProposeDispositionRequest
) -> dict[str, Any]:
    """B4. Propose product disposition (human approval required)."""
    try:
        disp_id = db2_service.create_product_disposition(
            incident_id=incident_id,
            lot_id=payload.lot_id,
            lot_type=payload.lot_type,
            quantity=payload.quantity,
            unit_of_measure=payload.unit_of_measure,
            disposition_type=payload.disposition_type,
            reason=payload.reason,
            proposed_method=payload.proposed_method,
            authority_permission_ref=payload.authority_permission_ref,
            operator_name=payload.operator_name or "Operator",
            evidence_attachment=payload.evidence_attachment
        )
        return {"success": True, "disposition_id": disp_id, "status": "PROPOSED"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incidents/{incident_id}/dispositions/{disposition_id}/approve")
def approve_product_disposition_endpoint(
    incident_id: str,
    disposition_id: str,
    payload: ApproveDispositionRequest
) -> dict[str, Any]:
    """B4. Human operator approval for product disposition."""
    try:
        success = db2_service.approve_product_disposition(
            disposition_id=disposition_id,
            operator_name=payload.operator_name or "Lead Product Safety Officer",
            notes=payload.notes
        )
        return {"success": success, "disposition_id": disposition_id, "status": "APPROVED"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incidents/{incident_id}/dispositions/{disposition_id}/execute")
def execute_product_disposition_endpoint(
    incident_id: str,
    disposition_id: str,
    payload: ExecuteDispositionRequest
) -> dict[str, Any]:
    """B4. Record execution of an approved disposition with evidence."""
    try:
        success = db2_service.execute_product_disposition(
            disposition_id=disposition_id,
            operator_name=payload.operator_name or "Plant Operations Lead",
            evidence_attachment=payload.evidence_attachment
        )
        return {"success": success, "disposition_id": disposition_id, "status": "EXECUTED"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/fssai/checklist")
def get_fssai_checklist_endpoint(incident_id: str) -> dict[str, Any]:
    """A3 / C. Full 14-item FSSAI Schedule-I checklist and 24-hour deadline status."""
    res = db2_service.get_fssai_schedule1_checklist(incident_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return res


@router.get("/incidents/{incident_id}/fssai/submissions")
def list_regulatory_submissions(incident_id: str) -> list[dict[str, Any]]:
    """C. List FoSCoS regulatory submission records."""
    return db2_service.get_regulatory_submissions(incident_id)


@router.post("/incidents/{incident_id}/fssai/submissions/{submission_id}/stage")
def update_regulatory_submission_stage_endpoint(
    incident_id: str,
    submission_id: str,
    payload: RegulatoryStageUpdateRequest
) -> dict[str, Any]:
    """C. Update FoSCoS regulatory submission stage."""
    try:
        success = db2_service.update_regulatory_submission_stage(
            submission_id=submission_id,
            new_stage=payload.new_stage,
            operator_name=payload.operator_name or "Regulatory Compliance Officer",
            foscos_recall_ref=payload.foscos_recall_ref,
            authority_feedback=payload.authority_feedback,
            pending_corrections=payload.pending_corrections
        )
        return {"success": success, "submission_id": submission_id, "new_stage": payload.new_stage.upper()}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}/effectiveness")
def get_recall_effectiveness_endpoint(incident_id: str) -> dict[str, Any]:
    """D. Post-recall effectiveness metrics and closure evaluation."""
    return db2_service.calculate_recall_effectiveness(incident_id)


@router.post("/incidents/{incident_id}/close")
def close_recall_endpoint(incident_id: str, payload: CloseRecallRequest) -> dict[str, Any]:
    """D. Attempt recall closure with regulatory prerequisite verification."""
    try:
        success = db2_service.attempt_close_recall(
            incident_id=incident_id,
            operator_name=payload.operator_name,
            justification=payload.justification
        )
        return {"success": success, "incident_id": incident_id, "status": "CLOSED"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


