from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class IncidentResponse(BaseModel):
    incident_id: str
    source_lot_id: str
    incident_type: str
    severity: str
    description: str
    reported_by: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source_lot_details: Optional[dict[str, Any]] = None


class TraceNode(BaseModel):
    lot_id: str
    item_name: str
    lot_type: str
    status: str
    facility_id: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None


class TraceLink(BaseModel):
    parent_lot_id: str
    child_lot_id: str
    depth: int
    quantity_consumed: Optional[float] = None
    unit: Optional[str] = None


class TraceResponse(BaseModel):
    incident_id: str
    source_lot_id: str
    total_downstream_lots: int
    total_production_levels: int
    finished_lots_count: int
    nodes: list[dict[str, Any]]
    links: list[TraceLink]


class ExposureCategory(BaseModel):
    label: str
    quantity: float
    percentage: float


class ExposureResponse(BaseModel):
    incident_id: str
    total_affected_units: float
    warehouse_units: float
    retailer_delivered_units: float
    in_transit_units: float
    finished_product_lots_count: int
    total_downstream_lots_count: int
    categories: list[ExposureCategory]
    affected_batches: list[dict[str, Any]]


class ShipmentItem(BaseModel):
    shipment_id: str
    lot_id: str
    product_name: Optional[str] = None
    retailer: str
    quantity: float
    status: str
    delivery_date: Optional[str] = None
    source_facility: Optional[str] = None


class ActionItem(BaseModel):
    action_id: str
    incident_id: str
    action_type: str
    target_type: str
    target_id: str
    action_description: str
    status: str
    proposed_by: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: Optional[str] = None
    approved_at: Optional[str] = None


class ActionDecisionRequest(BaseModel):
    decision: str  # 'APPROVED' or 'REJECTED'
    operator_name: Optional[str] = "Operator"
    notes: Optional[str] = None


class AuditLogItem(BaseModel):
    log_id: int
    incident_id: Optional[str] = None
    action_id: Optional[str] = None
    event_type: str
    performed_by: str
    details: Optional[str] = None
    created_at: Optional[str] = None


class CommStatusUpdateRequest(BaseModel):
    new_status: str
    operator_name: Optional[str] = "Lead Product Safety Officer"
    notes: Optional[str] = None
    delivery_confirmation: Optional[str] = None


class InterventionStatusUpdateRequest(BaseModel):
    new_status: str
    operator_name: Optional[str] = "Logistics Intervention Officer"
    cargo_location: Optional[str] = None
    interception_notes: Optional[str] = None
    recovered_quantity: Optional[float] = None
    returned_facility_id: Optional[str] = None


class RecordRecoveryRequest(BaseModel):
    lot_id: str
    source_location_type: str
    source_entity_name: str
    quantity_recovered: float
    unit_of_measure: Optional[str] = "UNIT"
    storage_facility_id: Optional[str] = "FAC-PUN"
    verification_method: Optional[str] = "PHYSICAL_AUDIT"
    operator_name: Optional[str] = "Quality Control Officer"
    notes: Optional[str] = None


class ProposeDispositionRequest(BaseModel):
    lot_id: str
    lot_type: str
    quantity: float
    unit_of_measure: str
    disposition_type: str
    reason: str
    proposed_method: Optional[str] = None
    authority_permission_ref: Optional[str] = None
    operator_name: Optional[str] = "Response Planning Agent"
    evidence_attachment: Optional[str] = None


class ApproveDispositionRequest(BaseModel):
    operator_name: Optional[str] = "Lead Product Safety Officer"
    notes: Optional[str] = None


class ExecuteDispositionRequest(BaseModel):
    operator_name: Optional[str] = "Plant Operations Lead"
    evidence_attachment: Optional[str] = None


class RegulatoryStageUpdateRequest(BaseModel):
    new_stage: str
    operator_name: Optional[str] = "Regulatory Compliance Officer"
    foscos_recall_ref: Optional[str] = None
    authority_feedback: Optional[str] = None
    pending_corrections: Optional[str] = None


class CloseRecallRequest(BaseModel):
    operator_name: str
    justification: str

