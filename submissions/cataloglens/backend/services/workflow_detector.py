"""
Business Workflow Discovery Service.
Identifies logical business processes from clusters of connected Db2 tables,
analyzing sequence paths, supporting declared/inferred relationships,
and expressing realistic enterprise uncertainties.
"""
from typing import Dict, List, Set
import logging

from ..models.schema import DbSchemaMetadata
from ..models.relationship import RelationshipEdge
from ..models.analysis import WorkflowGroup

logger = logging.getLogger("CatalogLens.WorkflowDetector")


class WorkflowDetector:
    """Discovers likely business workflows across connected database entities."""

    WORKFLOW_TEMPLATES = [
        {
            "id": "WF_ORDER_TO_CASH",
            "name": "Order-to-Cash (O2C) Fulfillment Flow",
            "description": "Core commercial lifecycle governing customer acquisition, purchase order booking, line item reservation, payment processing, and carrier dispatch.",
            "expected_tables": ["CUSTOMER_MST", "ORD_HDR", "ORD_LINE", "PAYMENT_TXN", "SHIPMENT_HDR", "SHIPMENT_ITEM"],
            "sequence": [
                "1. Customer Profile verification (CUSTOMER_MST)",
                "2. Purchase Order header creation (ORD_HDR)",
                "3. Line item SKU pricing and discounts (ORD_LINE)",
                "4. Payment authorization & settlement (PAYMENT_TXN)",
                "5. Warehouse parcel dispatch manifest (SHIPMENT_HDR)",
                "6. Physical carton packing & QA inspection (SHIPMENT_ITEM)",
            ],
            "uncertainties": [
                "Payment transaction settlement occurs asynchronously from order creation; exact lock-in status depends on PAYMENT_TXN.TXN_STATUS_CD.",
                "Partial shipments may produce multiple SHIPMENT_HDR records for a single ORD_HDR.",
            ],
        },
        {
            "id": "WF_INVENTORY_ALLOCATION",
            "name": "Inventory Reservation & Replenishment",
            "description": "Stock management lifecycle coordinating warehouse on-hand balances, pre-fulfillment reservation holds, and supplier replenishment thresholds.",
            "expected_tables": ["PRODUCT_MST", "INVENTORY", "INVENTORY_RESERVATION", "WAREHOUSE_MST", "SUPPLIER_MST"],
            "sequence": [
                "1. Master SKU catalog definition (PRODUCT_MST)",
                "2. Multi-warehouse physical stock audit (INVENTORY, WAREHOUSE_MST)",
                "3. Real-time temporary hold upon checkout (INVENTORY_RESERVATION)",
                "4. Supplier purchase reorder triggered at reorder threshold (SUPPLIER_MST)",
            ],
            "uncertainties": [
                "SUPPLIER_MST relationship to INVENTORY is maintained through procurement purchase orders which may be managed in an external ERP.",
                "Reservation expiration requires scheduled cleanup jobs checking INVENTORY_RESERVATION.EXPIRE_TS.",
            ],
        },
        {
            "id": "WF_CUSTOMER_BILLING_VAULT",
            "name": "Customer Payment Instrument & Billing Vault",
            "description": "PCI-DSS tokenized instrument management linking customer accounts to reusable tokens and settlement logs.",
            "expected_tables": ["CUSTOMER_MST", "PAYMENT_METHOD", "PAYMENT_TXN"],
            "sequence": [
                "1. Customer registration (CUSTOMER_MST)",
                "2. Tokenized payment method registration (PAYMENT_METHOD)",
                "3. Payment transaction authorization & charge (PAYMENT_TXN)",
            ],
            "uncertainties": [
                "Direct relationship between PAYMENT_METHOD and CUSTOMER_MST is declared; however, fallback guest checkouts might bypass stored tokens.",
            ],
        },
        {
            "id": "WF_REVERSE_LOGISTICS",
            "name": "Reverse Logistics & RMA Restitution",
            "description": "Customer merchandise return processing, inspection verification, and credit refund reimbursement.",
            "expected_tables": ["ORD_HDR", "RETURN_HDR", "CUSTOMER_MST"],
            "sequence": [
                "1. Original order placement (ORD_HDR)",
                "2. RMA return authorization filing (RETURN_HDR)",
                "3. Customer ledger refund disbursement (CUSTOMER_MST)",
            ],
            "uncertainties": [
                "RETURN_HDR lacks an explicit catalog foreign key constraint to ORD_HDR (inferred connection based on ORDER_ID column name).",
                "Customer link is identified through ambiguous column 'CUST_REF_NO', requiring developer business verification.",
            ],
        },
    ]

    def discover_workflows(
        self,
        metadata: DbSchemaMetadata,
        relationships: List[RelationshipEdge],
    ) -> List[WorkflowGroup]:
        """Detects matching workflows based on schema topology and table presence."""
        available_tables = {t.upper() for t in metadata.tables.keys()}
        workflows: List[WorkflowGroup] = []

        for template in self.WORKFLOW_TEMPLATES:
            expected = template["expected_tables"]
            matched_tables = [t for t in expected if t.upper() in available_tables]

            if len(matched_tables) >= 2:  # Significant overlap
                ratio = len(matched_tables) / len(expected)
                confidence = round(0.70 + (0.25 * ratio), 2)

                # Filter supporting relationships between these tables
                matched_set = set(matched_tables)
                supporting_rels = [
                    r for r in relationships
                    if r.source_table in matched_set and r.target_table in matched_set
                ]

                # Adjust confidence if inferred relationships are present
                has_inferred = any(r.relationship_type.value == "INFERRED" for r in supporting_rels)
                if has_inferred:
                    confidence = min(confidence, 0.85)

                wf = WorkflowGroup(
                    workflow_id=template["id"],
                    name=template["name"],
                    description=template["description"],
                    tables=matched_tables,
                    sequence_steps=template["sequence"],
                    supporting_relationships=supporting_rels,
                    confidence=confidence,
                    uncertainties=template["uncertainties"],
                )
                workflows.append(wf)

        return workflows
