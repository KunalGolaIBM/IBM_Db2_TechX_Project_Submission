"""
Synthetic Db2 Catalog snapshot representing a realistic enterprise Order-Management System.
This is used for offline testing, local demonstrations, and unit tests.
Matches exact Db2 LUW catalog data structures.
"""
from typing import Dict, List
from ..models.schema import (
    DbColumn,
    DbConstraint,
    DbIndex,
    DbTable,
    DbSchemaMetadata,
    ForeignKeyRef,
)


def get_sample_enterprise_metadata() -> DbSchemaMetadata:
    """Builds and returns a complete synthetic DbSchemaMetadata object for the ENTERPRISE schema."""
    tables: Dict[str, DbTable] = {}
    views: Dict[str, DbTable] = {}

    # 1. CUSTOMER_MST
    tables["CUSTOMER_MST"] = DbTable(
        tabname="CUSTOMER_MST",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Master record of registered commercial and retail clients.",
        card=18500,
        colcount=7,
        columns=[
            DbColumn(colname="CUST_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Surrogate primary key for customer", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="CUST_NAME", typename="VARCHAR", length=120, scale=0, nulls="N", colno=2, remarks="Legal or personal business entity name"),
            DbColumn(colname="CUST_TYPE_CD", typename="CHAR", length=3, scale=0, nulls="N", default_val="'RET'", colno=3, remarks="Customer classification: B2B or RET"),
            DbColumn(colname="CUST_EMAIL", typename="VARCHAR", length=255, scale=0, nulls="N", colno=4, remarks="Primary contact electronic address"),
            DbColumn(colname="TAX_ID", typename="VARCHAR", length=32, scale=0, nulls="Y", colno=5, remarks="Government tax identification number"),
            DbColumn(colname="STATUS_CD", typename="CHAR", length=2, scale=0, nulls="N", default_val="'AC'", colno=6, remarks="Account lifecycle status: AC=Active, SU=Suspended, CL=Closed"),
            DbColumn(colname="CREATED_TS", typename="TIMESTAMP", length=10, scale=6, nulls="N", colno=7, remarks="Timestamp when customer record was created"),
        ],
        primary_keys=["CUST_ID"],
        foreign_keys=[],
        indexes=[
            DbIndex(indname="PK_CUSTOMER_MST", tabname="CUSTOMER_MST", uniquerule="P", colnames="+CUST_ID"),
            DbIndex(indname="IX_CUST_EMAIL", tabname="CUSTOMER_MST", uniquerule="U", colnames="+CUST_EMAIL"),
        ],
        constraints=[
            DbConstraint(constname="PK_CUSTOMER_MST", tabname="CUSTOMER_MST", const_type="P", columns=["CUST_ID"]),
            DbConstraint(constname="CK_CUST_STATUS", tabname="CUSTOMER_MST", const_type="K", columns=["STATUS_CD"]),
        ],
    )

    # 2. PRODUCT_MST
    tables["PRODUCT_MST"] = DbTable(
        tabname="PRODUCT_MST",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Global catalog of salable merchandise and SKU specifications.",
        card=6200,
        colcount=7,
        columns=[
            DbColumn(colname="PROD_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Primary surrogate identifier for product", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="SKU_CODE", typename="VARCHAR", length=32, scale=0, nulls="N", colno=2, remarks="Standard warehouse stock-keeping unit string"),
            DbColumn(colname="PROD_NAME", typename="VARCHAR", length=160, scale=0, nulls="N", colno=3, remarks="Commercial catalog product title"),
            DbColumn(colname="CATEGORY_ID", typename="INTEGER", length=4, scale=0, nulls="Y", colno=4, remarks="Legacy category classification number (undocumented master)"),
            DbColumn(colname="BASE_PRICE", typename="DECIMAL", length=10, scale=2, nulls="N", colno=5, remarks="List price in standard currency"),
            DbColumn(colname="WEIGHT_KG", typename="DECIMAL", length=7, scale=3, nulls="Y", colno=6, remarks="Unit shipping mass in kilograms"),
            DbColumn(colname="IS_ACTIVE", typename="CHAR", length=1, scale=0, nulls="N", default_val="'Y'", colno=7, remarks="Active sales flag: Y/N"),
        ],
        primary_keys=["PROD_ID"],
        foreign_keys=[],
        indexes=[
            DbIndex(indname="PK_PRODUCT_MST", tabname="PRODUCT_MST", uniquerule="P", colnames="+PROD_ID"),
            DbIndex(indname="IX_PROD_SKU", tabname="PRODUCT_MST", uniquerule="U", colnames="+SKU_CODE"),
        ],
        constraints=[
            DbConstraint(constname="PK_PRODUCT_MST", tabname="PRODUCT_MST", const_type="P", columns=["PROD_ID"]),
        ],
    )

    # 3. SUPPLIER_MST
    tables["SUPPLIER_MST"] = DbTable(
        tabname="SUPPLIER_MST",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Vendor and wholesale supplier registry.",
        card=450,
        colcount=6,
        columns=[
            DbColumn(colname="SUPP_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Supplier surrogate key", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="SUPP_NAME", typename="VARCHAR", length=120, scale=0, nulls="N", colno=2, remarks="Corporate supplier trading entity name"),
            DbColumn(colname="CONTACT_EMAIL", typename="VARCHAR", length=255, scale=0, nulls="N", colno=3, remarks="Procurement inquiry email"),
            DbColumn(colname="COUNTRY_CD", typename="CHAR", length=3, scale=0, nulls="N", colno=4, remarks="ISO 3166-1 alpha-3 country identifier"),
            DbColumn(colname="RATING_SCORE", typename="DECIMAL", length=3, scale=2, nulls="Y", colno=5, remarks="Vendor SLA performance score (0.00 to 5.00)"),
            DbColumn(colname="ACTIVE_IND", typename="CHAR", length=1, scale=0, nulls="N", default_val="'Y'", colno=6, remarks="Supplier authorization flag"),
        ],
        primary_keys=["SUPP_ID"],
        foreign_keys=[],
        indexes=[
            DbIndex(indname="PK_SUPPLIER_MST", tabname="SUPPLIER_MST", uniquerule="P", colnames="+SUPP_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_SUPPLIER_MST", tabname="SUPPLIER_MST", const_type="P", columns=["SUPP_ID"]),
        ],
    )

    # 4. WAREHOUSE_MST
    tables["WAREHOUSE_MST"] = DbTable(
        tabname="WAREHOUSE_MST",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Physical distribution facilities and regional storage hubs.",
        card=24,
        colcount=6,
        columns=[
            DbColumn(colname="WH_ID", typename="INTEGER", length=4, scale=0, nulls="N", colno=1, remarks="Warehouse primary key identifier", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="WH_CODE", typename="VARCHAR", length=16, scale=0, nulls="N", colno=2, remarks="Short mnemonic warehouse code (e.g., WH-EAST-01)"),
            DbColumn(colname="WH_NAME", typename="VARCHAR", length=80, scale=0, nulls="N", colno=3, remarks="Full descriptive site name"),
            DbColumn(colname="REGION_CD", typename="VARCHAR", length=10, scale=0, nulls="N", colno=4, remarks="Geographical operating territory"),
            DbColumn(colname="MAX_CAPACITY", typename="INTEGER", length=4, scale=0, nulls="N", colno=5, remarks="Total pallet holding capacity"),
            DbColumn(colname="OPERATIONAL_STS", typename="VARCHAR", length=16, scale=0, nulls="N", default_val="'ONLINE'", colno=6, remarks="Operational state: ONLINE, MAINTENANCE, DECOMMISSIONED"),
        ],
        primary_keys=["WH_ID"],
        foreign_keys=[],
        indexes=[
            DbIndex(indname="PK_WAREHOUSE_MST", tabname="WAREHOUSE_MST", uniquerule="P", colnames="+WH_ID"),
            DbIndex(indname="IX_WH_CODE", tabname="WAREHOUSE_MST", uniquerule="U", colnames="+WH_CODE"),
        ],
        constraints=[
            DbConstraint(constname="PK_WAREHOUSE_MST", tabname="WAREHOUSE_MST", const_type="P", columns=["WH_ID"]),
        ],
    )

    # 5. ORD_HDR
    tables["ORD_HDR"] = DbTable(
        tabname="ORD_HDR",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Order header records containing transactional totals and customer references.",
        card=142000,
        colcount=8,
        columns=[
            DbColumn(colname="ORDER_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Unique purchase order identifier", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="CUST_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to purchasing customer", is_foreign_key=True, foreign_key_target="CUSTOMER_MST.CUST_ID"),
            DbColumn(colname="ORDER_DT", typename="DATE", length=4, scale=0, nulls="N", colno=3, remarks="Calendar date when customer placed order"),
            DbColumn(colname="ORDER_STATUS_CD", typename="CHAR", length=4, scale=0, nulls="N", default_val="'NEW'", colno=4, remarks="Order workflow status: NEW, PAID, PROC, SHIP, DELV, CANC"),
            DbColumn(colname="TOTAL_AMT", typename="DECIMAL", length=12, scale=2, nulls="N", colno=5, remarks="Gross currency total including tax and shipping"),
            DbColumn(colname="CURRENCY_CD", typename="CHAR", length=3, scale=0, nulls="N", default_val="'USD'", colno=6, remarks="ISO 4217 transaction currency code"),
            DbColumn(colname="CHANNEL_CD", typename="VARCHAR", length=12, scale=0, nulls="N", default_val="'WEB'", colno=7, remarks="Sales acquisition channel: WEB, MOBILE, B2B_EDI, POS"),
            DbColumn(colname="CREATED_TS", typename="TIMESTAMP", length=10, scale=6, nulls="N", colno=8, remarks="System audit creation timestamp"),
        ],
        primary_keys=["ORDER_ID"],
        foreign_keys=[
            ForeignKeyRef(
                constraint_name="FK_ORD_HDR_CUST",
                source_table="ORD_HDR",
                source_column="CUST_ID",
                target_table="CUSTOMER_MST",
                target_column="CUST_ID",
                delete_rule="RESTRICT",
                update_rule="RESTRICT",
            )
        ],
        indexes=[
            DbIndex(indname="PK_ORD_HDR", tabname="ORD_HDR", uniquerule="P", colnames="+ORDER_ID"),
            DbIndex(indname="IX_ORD_CUST", tabname="ORD_HDR", uniquerule="D", colnames="+CUST_ID"),
            DbIndex(indname="IX_ORD_STATUS", tabname="ORD_HDR", uniquerule="D", colnames="+ORDER_STATUS_CD+ORDER_DT"),
        ],
        constraints=[
            DbConstraint(constname="PK_ORD_HDR", tabname="ORD_HDR", const_type="P", columns=["ORDER_ID"]),
            DbConstraint(constname="FK_ORD_HDR_CUST", tabname="ORD_HDR", const_type="F", columns=["CUST_ID"], ref_table="CUSTOMER_MST"),
            DbConstraint(constname="CK_ORD_TOTAL_NONNEG", tabname="ORD_HDR", const_type="K", columns=["TOTAL_AMT"]),
        ],
    )

    # 6. ORD_LINE
    tables["ORD_LINE"] = DbTable(
        tabname="ORD_LINE",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Itemized purchase order line entries detailing SKUs and quantities.",
        card=480000,
        colcount=8,
        columns=[
            DbColumn(colname="LINE_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Surrogate primary key for line entry", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="ORDER_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to parent order header", is_foreign_key=True, foreign_key_target="ORD_HDR.ORDER_ID"),
            DbColumn(colname="PROD_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=3, remarks="Foreign key to purchased product catalog item", is_foreign_key=True, foreign_key_target="PRODUCT_MST.PROD_ID"),
            DbColumn(colname="LINE_NUM", typename="SMALLINT", length=2, scale=0, nulls="N", colno=4, remarks="Line ordinal index within the order"),
            DbColumn(colname="ORDER_QTY", typename="INTEGER", length=4, scale=0, nulls="N", colno=5, remarks="Quantity of items ordered"),
            DbColumn(colname="UNIT_PRICE", typename="DECIMAL", length=10, scale=2, nulls="N", colno=6, remarks="Sold price per unit at purchase time"),
            DbColumn(colname="DISCOUNT_AMT", typename="DECIMAL", length=10, scale=2, nulls="N", default_val="0.00", colno=7, remarks="Promotional concession amount"),
            DbColumn(colname="NET_AMT", typename="DECIMAL", length=10, scale=2, nulls="N", colno=8, remarks="Calculated payable line item total"),
        ],
        primary_keys=["LINE_ID"],
        foreign_keys=[
            ForeignKeyRef(
                constraint_name="FK_ORD_LINE_HDR",
                source_table="ORD_LINE",
                source_column="ORDER_ID",
                target_table="ORD_HDR",
                target_column="ORDER_ID",
                delete_rule="CASCADE",
                update_rule="RESTRICT",
            ),
            ForeignKeyRef(
                constraint_name="FK_ORD_LINE_PROD",
                source_table="ORD_LINE",
                source_column="PROD_ID",
                target_table="PRODUCT_MST",
                target_column="PROD_ID",
                delete_rule="RESTRICT",
                update_rule="RESTRICT",
            ),
        ],
        indexes=[
            DbIndex(indname="PK_ORD_LINE", tabname="ORD_LINE", uniquerule="P", colnames="+LINE_ID"),
            DbIndex(indname="IX_LINE_ORD_SEQ", tabname="ORD_LINE", uniquerule="U", colnames="+ORDER_ID+LINE_NUM"),
            DbIndex(indname="IX_LINE_PROD", tabname="ORD_LINE", uniquerule="D", colnames="+PROD_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_ORD_LINE", tabname="ORD_LINE", const_type="P", columns=["LINE_ID"]),
            DbConstraint(constname="FK_ORD_LINE_HDR", tabname="ORD_LINE", const_type="F", columns=["ORDER_ID"], ref_table="ORD_HDR"),
            DbConstraint(constname="FK_ORD_LINE_PROD", tabname="ORD_LINE", const_type="F", columns=["PROD_ID"], ref_table="PRODUCT_MST"),
        ],
    )

    # 7. INVENTORY
    tables["INVENTORY"] = DbTable(
        tabname="INVENTORY",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Current physical on-hand stock balances across warehouse locations.",
        card=98000,
        colcount=6,
        columns=[
            DbColumn(colname="INV_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Inventory record identifier", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="PROD_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to product catalog", is_foreign_key=True, foreign_key_target="PRODUCT_MST.PROD_ID"),
            DbColumn(colname="WH_ID", typename="INTEGER", length=4, scale=0, nulls="N", colno=3, remarks="Foreign key to warehouse facility", is_foreign_key=True, foreign_key_target="WAREHOUSE_MST.WH_ID"),
            DbColumn(colname="ON_HAND_QTY", typename="INTEGER", length=4, scale=0, nulls="N", default_val="0", colno=4, remarks="Physical unit count present in facility"),
            DbColumn(colname="REORDER_POINT", typename="INTEGER", length=4, scale=0, nulls="N", default_val="10", colno=5, remarks="Threshold for automated supplier reordering"),
            DbColumn(colname="LAST_COUNT_DT", typename="DATE", length=4, scale=0, nulls="Y", colno=6, remarks="Date of last physical cycle audit"),
        ],
        primary_keys=["INV_ID"],
        foreign_keys=[
            ForeignKeyRef(
                constraint_name="FK_INV_PROD",
                source_table="INVENTORY",
                source_column="PROD_ID",
                target_table="PRODUCT_MST",
                target_column="PROD_ID",
            ),
            ForeignKeyRef(
                constraint_name="FK_INV_WH",
                source_table="INVENTORY",
                source_column="WH_ID",
                target_table="WAREHOUSE_MST",
                target_column="WH_ID",
            ),
        ],
        indexes=[
            DbIndex(indname="PK_INVENTORY", tabname="INVENTORY", uniquerule="P", colnames="+INV_ID"),
            DbIndex(indname="IX_INV_PROD_WH", tabname="INVENTORY", uniquerule="U", colnames="+PROD_ID+WH_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_INVENTORY", tabname="INVENTORY", const_type="P", columns=["INV_ID"]),
            DbConstraint(constname="FK_INV_PROD", tabname="INVENTORY", const_type="F", columns=["PROD_ID"], ref_table="PRODUCT_MST"),
            DbConstraint(constname="FK_INV_WH", tabname="INVENTORY", const_type="F", columns=["WH_ID"], ref_table="WAREHOUSE_MST"),
        ],
    )

    # 8. INVENTORY_RESERVATION
    tables["INVENTORY_RESERVATION"] = DbTable(
        tabname="INVENTORY_RESERVATION",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Temporary stock holds allocated to unfulfilled orders to prevent double-selling.",
        card=12500,
        colcount=7,
        columns=[
            DbColumn(colname="RESV_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Reservation sequence key", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="ORDER_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to ordering contract", is_foreign_key=True, foreign_key_target="ORD_HDR.ORDER_ID"),
            DbColumn(colname="PROD_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=3, remarks="Foreign key to product being held", is_foreign_key=True, foreign_key_target="PRODUCT_MST.PROD_ID"),
            DbColumn(colname="WH_ID", typename="INTEGER", length=4, scale=0, nulls="N", colno=4, remarks="Facility where unit is sequestered", is_foreign_key=True, foreign_key_target="WAREHOUSE_MST.WH_ID"),
            DbColumn(colname="RESV_QTY", typename="INTEGER", length=4, scale=0, nulls="N", colno=5, remarks="Number of units reserved"),
            DbColumn(colname="RESV_STATUS", typename="VARCHAR", length=16, scale=0, nulls="N", default_val="'ACTIVE'", colno=6, remarks="Reservation status: ACTIVE, FULFILLED, EXPIRED"),
            DbColumn(colname="EXPIRE_TS", typename="TIMESTAMP", length=10, scale=6, nulls="N", colno=7, remarks="Timestamp when lock expires if unconfirmed"),
        ],
        primary_keys=["RESV_ID"],
        foreign_keys=[
            ForeignKeyRef(constraint_name="FK_RESV_ORD", source_table="INVENTORY_RESERVATION", source_column="ORDER_ID", target_table="ORD_HDR", target_column="ORDER_ID"),
            ForeignKeyRef(constraint_name="FK_RESV_PROD", source_table="INVENTORY_RESERVATION", source_column="PROD_ID", target_table="PRODUCT_MST", target_column="PROD_ID"),
            ForeignKeyRef(constraint_name="FK_RESV_WH", source_table="INVENTORY_RESERVATION", source_column="WH_ID", target_table="WAREHOUSE_MST", target_column="WH_ID"),
        ],
        indexes=[
            DbIndex(indname="PK_INV_RESV", tabname="INVENTORY_RESERVATION", uniquerule="P", colnames="+RESV_ID"),
            DbIndex(indname="IX_RESV_ORD", tabname="INVENTORY_RESERVATION", uniquerule="D", colnames="+ORDER_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_INV_RESV", tabname="INVENTORY_RESERVATION", const_type="P", columns=["RESV_ID"]),
        ],
    )

    # 9. PAYMENT_METHOD
    tables["PAYMENT_METHOD"] = DbTable(
        tabname="PAYMENT_METHOD",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Stored customer billing instrument tokens and wallet identifiers.",
        card=23000,
        colcount=6,
        columns=[
            DbColumn(colname="PM_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Payment method identifier", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="CUST_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to owning customer", is_foreign_key=True, foreign_key_target="CUSTOMER_MST.CUST_ID"),
            DbColumn(colname="PM_TYPE_CD", typename="VARCHAR", length=16, scale=0, nulls="N", colno=3, remarks="Instrument kind: CC, ACH, PAYPAL, APPLE_PAY"),
            DbColumn(colname="TOKENIZED_ACCT", typename="VARCHAR", length=64, scale=0, nulls="N", colno=4, remarks="PCI-DSS compliant encrypted vault token"),
            DbColumn(colname="EXPIRY_MON_YR", typename="CHAR", length=7, scale=0, nulls="Y", colno=5, remarks="Instrument expiration formatted MM/YYYY"),
            DbColumn(colname="IS_DEFAULT", typename="CHAR", length=1, scale=0, nulls="N", default_val="'N'", colno=6, remarks="Primary checkout default indicator (Y/N)"),
        ],
        primary_keys=["PM_ID"],
        foreign_keys=[
            ForeignKeyRef(constraint_name="FK_PM_CUST", source_table="PAYMENT_METHOD", source_column="CUST_ID", target_table="CUSTOMER_MST", target_column="CUST_ID"),
        ],
        indexes=[
            DbIndex(indname="PK_PAYMENT_METHOD", tabname="PAYMENT_METHOD", uniquerule="P", colnames="+PM_ID"),
            DbIndex(indname="IX_PM_CUST", tabname="PAYMENT_METHOD", uniquerule="D", colnames="+CUST_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_PAYMENT_METHOD", tabname="PAYMENT_METHOD", const_type="P", columns=["PM_ID"]),
        ],
    )

    # 10. PAYMENT_TXN
    tables["PAYMENT_TXN"] = DbTable(
        tabname="PAYMENT_TXN",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Settled and attempted gateway authorization transactions.",
        card=156000,
        colcount=8,
        columns=[
            DbColumn(colname="TXN_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Transaction surrogate key", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="ORDER_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to order being settled", is_foreign_key=True, foreign_key_target="ORD_HDR.ORDER_ID"),
            DbColumn(colname="PM_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=3, remarks="Foreign key to used payment instrument", is_foreign_key=True, foreign_key_target="PAYMENT_METHOD.PM_ID"),
            DbColumn(colname="TXN_AMT", typename="DECIMAL", length=12, scale=2, nulls="N", colno=4, remarks="Authorized payment currency amount"),
            DbColumn(colname="TXN_STATUS_CD", typename="CHAR", length=4, scale=0, nulls="N", colno=5, remarks="Transaction state: AUTH, CAPT, DECL, REFD"),
            DbColumn(colname="GATEWAY_REF_NO", typename="VARCHAR", length=64, scale=0, nulls="N", colno=6, remarks="External payment processor authorization code"),
            DbColumn(colname="AUTH_CODE", typename="VARCHAR", length=32, scale=0, nulls="Y", colno=7, remarks="Banking clearinghouse authorization approval code"),
            DbColumn(colname="TXN_TS", typename="TIMESTAMP", length=10, scale=6, nulls="N", colno=8, remarks="Timestamp of gateway transaction"),
        ],
        primary_keys=["TXN_ID"],
        foreign_keys=[
            ForeignKeyRef(constraint_name="FK_TXN_ORD", source_table="PAYMENT_TXN", source_column="ORDER_ID", target_table="ORD_HDR", target_column="ORDER_ID"),
            ForeignKeyRef(constraint_name="FK_TXN_PM", source_table="PAYMENT_TXN", source_column="PM_ID", target_table="PAYMENT_METHOD", target_column="PM_ID"),
        ],
        indexes=[
            DbIndex(indname="PK_PAYMENT_TXN", tabname="PAYMENT_TXN", uniquerule="P", colnames="+TXN_ID"),
            DbIndex(indname="IX_TXN_ORD", tabname="PAYMENT_TXN", uniquerule="D", colnames="+ORDER_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_PAYMENT_TXN", tabname="PAYMENT_TXN", const_type="P", columns=["TXN_ID"]),
        ],
    )

    # 11. SHIPMENT_HDR
    tables["SHIPMENT_HDR"] = DbTable(
        tabname="SHIPMENT_HDR",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Carrier dispatch manifests and consignment tracking records.",
        card=135000,
        colcount=7,
        columns=[
            DbColumn(colname="SHIPMENT_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Shipment primary key identifier", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="ORDER_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to fulfilled order header", is_foreign_key=True, foreign_key_target="ORD_HDR.ORDER_ID"),
            DbColumn(colname="WH_ID", typename="INTEGER", length=4, scale=0, nulls="N", colno=3, remarks="Originating distribution center", is_foreign_key=True, foreign_key_target="WAREHOUSE_MST.WH_ID"),
            DbColumn(colname="CARRIER_CD", typename="VARCHAR", length=16, scale=0, nulls="N", colno=4, remarks="Logistics courier code (FEDEX, UPS, DHL, USPS)"),
            DbColumn(colname="TRACKING_NO", typename="VARCHAR", length=64, scale=0, nulls="N", colno=5, remarks="Airway bill or courier tracking number"),
            DbColumn(colname="SHIP_DT", typename="DATE", length=4, scale=0, nulls="N", colno=6, remarks="Dispatch shipment handover date"),
            DbColumn(colname="DELIVERY_STS", typename="VARCHAR", length=16, scale=0, nulls="N", default_val="'IN_TRANSIT'", colno=7, remarks="Delivery stage: IN_TRANSIT, DELIVERED, EXCEPTION"),
        ],
        primary_keys=["SHIPMENT_ID"],
        foreign_keys=[
            ForeignKeyRef(constraint_name="FK_SHIP_ORD", source_table="SHIPMENT_HDR", source_column="ORDER_ID", target_table="ORD_HDR", target_column="ORDER_ID"),
            ForeignKeyRef(constraint_name="FK_SHIP_WH", source_table="SHIPMENT_HDR", source_column="WH_ID", target_table="WAREHOUSE_MST", target_column="WH_ID"),
        ],
        indexes=[
            DbIndex(indname="PK_SHIPMENT_HDR", tabname="SHIPMENT_HDR", uniquerule="P", colnames="+SHIPMENT_ID"),
            DbIndex(indname="IX_SHIP_TRACK", tabname="SHIPMENT_HDR", uniquerule="U", colnames="+TRACKING_NO"),
        ],
        constraints=[
            DbConstraint(constname="PK_SHIPMENT_HDR", tabname="SHIPMENT_HDR", const_type="P", columns=["SHIPMENT_ID"]),
        ],
    )

    # 12. SHIPMENT_ITEM
    tables["SHIPMENT_ITEM"] = DbTable(
        tabname="SHIPMENT_ITEM",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Line items physically packed into an outbound consignment carton.",
        card=450000,
        colcount=5,
        columns=[
            DbColumn(colname="SHIP_ITEM_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Box item surrogate key", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="SHIPMENT_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Foreign key to shipping parcel header", is_foreign_key=True, foreign_key_target="SHIPMENT_HDR.SHIPMENT_ID"),
            DbColumn(colname="LINE_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=3, remarks="Foreign key to customer order line item", is_foreign_key=True, foreign_key_target="ORD_LINE.LINE_ID"),
            DbColumn(colname="PACKED_QTY", typename="INTEGER", length=4, scale=0, nulls="N", colno=4, remarks="Quantity included in this physical carton"),
            DbColumn(colname="INSPECTION_STS", typename="VARCHAR", length=16, scale=0, nulls="N", default_val="'PASSED'", colno=5, remarks="QA warehouse inspection verdict"),
        ],
        primary_keys=["SHIP_ITEM_ID"],
        foreign_keys=[
            ForeignKeyRef(constraint_name="FK_ITEM_SHIP", source_table="SHIPMENT_ITEM", source_column="SHIPMENT_ID", target_table="SHIPMENT_HDR", target_column="SHIPMENT_ID"),
            ForeignKeyRef(constraint_name="FK_ITEM_LINE", source_table="SHIPMENT_ITEM", source_column="LINE_ID", target_table="ORD_LINE", target_column="LINE_ID"),
        ],
        indexes=[
            DbIndex(indname="PK_SHIPMENT_ITEM", tabname="SHIPMENT_ITEM", uniquerule="P", colnames="+SHIP_ITEM_ID"),
            DbIndex(indname="IX_ITEM_SHIP_LINE", tabname="SHIPMENT_ITEM", uniquerule="U", colnames="+SHIPMENT_ID+LINE_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_SHIPMENT_ITEM", tabname="SHIPMENT_ITEM", const_type="P", columns=["SHIP_ITEM_ID"]),
        ],
    )

    # 13. RETURN_HDR
    # Intentionally designed to demonstrate inferred relationship discovery:
    # Notice ORDER_ID has no declared foreign key constraint in the Db2 catalog!
    # Notice CUST_REF_NO is an undocumented column referencing CUSTOMER_MST.CUST_ID!
    tables["RETURN_HDR"] = DbTable(
        tabname="RETURN_HDR",
        tabschema="ENTERPRISE",
        table_type="T",
        remarks="Customer merchandise authorization returns and RMA restitution filings.",
        card=8400,
        colcount=7,
        columns=[
            DbColumn(colname="RET_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Return merchandise authorization RMA key", is_primary_key=True, primary_key_seq=1),
            DbColumn(colname="ORDER_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=2, remarks="Legacy order reference number without explicit foreign key constraint"),
            DbColumn(colname="CUST_REF_NO", typename="BIGINT", length=8, scale=0, nulls="N", colno=3, remarks="Customer account reference number (undocumented link to CUST_ID)"),
            DbColumn(colname="RET_REASON_CD", typename="VARCHAR", length=16, scale=0, nulls="N", colno=4, remarks="Return reason classification: DEFECTIVE, WRONG_ITEM, SIZE_MISFIT, BUYER_REMORSE"),
            DbColumn(colname="RET_STATUS_CD", typename="CHAR", length=4, scale=0, nulls="N", default_val="'INIT'", colno=5, remarks="RMA state: INIT, APRV, RECV, RFND, REJT"),
            DbColumn(colname="REFUND_AMT", typename="DECIMAL", length=10, scale=2, nulls="N", default_val="0.00", colno=6, remarks="Approved customer refund credit amount"),
            DbColumn(colname="REQUEST_DT", typename="DATE", length=4, scale=0, nulls="N", colno=7, remarks="Date customer initiated return claim"),
        ],
        primary_keys=["RET_ID"],
        foreign_keys=[],  # No declared foreign keys! Perfect target for relationship inference!
        indexes=[
            DbIndex(indname="PK_RETURN_HDR", tabname="RETURN_HDR", uniquerule="P", colnames="+RET_ID"),
            DbIndex(indname="IX_RET_ORD_ID", tabname="RETURN_HDR", uniquerule="D", colnames="+ORDER_ID"),
        ],
        constraints=[
            DbConstraint(constname="PK_RETURN_HDR", tabname="RETURN_HDR", const_type="P", columns=["RET_ID"]),
        ],
    )

    # 14. V_ACTIVE_ORDERS (View)
    views["V_ACTIVE_ORDERS"] = DbTable(
        tabname="V_ACTIVE_ORDERS",
        tabschema="ENTERPRISE",
        table_type="V",
        remarks="Operational reporting view aggregating active orders with customer name and latest payment status.",
        card=1250,
        colcount=6,
        columns=[
            DbColumn(colname="ORDER_ID", typename="BIGINT", length=8, scale=0, nulls="N", colno=1, remarks="Order identifier"),
            DbColumn(colname="CUST_NAME", typename="VARCHAR", length=120, scale=0, nulls="N", colno=2, remarks="Customer legal name"),
            DbColumn(colname="ORDER_DT", typename="DATE", length=4, scale=0, nulls="N", colno=3, remarks="Order date"),
            DbColumn(colname="ORDER_STATUS_CD", typename="CHAR", length=4, scale=0, nulls="N", colno=4, remarks="Order workflow status"),
            DbColumn(colname="TOTAL_AMT", typename="DECIMAL", length=12, scale=2, nulls="N", colno=5, remarks="Total amount"),
            DbColumn(colname="TXN_STATUS_CD", typename="CHAR", length=4, scale=0, nulls="Y", colno=6, remarks="Latest settlement transaction status"),
        ],
        view_definition="""
CREATE VIEW ENTERPRISE.V_ACTIVE_ORDERS AS
SELECT
    O.ORDER_ID,
    C.CUST_NAME,
    O.ORDER_DT,
    O.ORDER_STATUS_CD,
    O.TOTAL_AMT,
    T.TXN_STATUS_CD
FROM ENTERPRISE.ORD_HDR O
JOIN ENTERPRISE.CUSTOMER_MST C ON O.CUST_ID = C.CUST_ID
LEFT JOIN ENTERPRISE.PAYMENT_TXN T ON O.ORDER_ID = T.ORDER_ID
WHERE O.ORDER_STATUS_CD IN ('NEW', 'PAID', 'PROC')
        """.strip(),
    )

    # 15. V_INVENTORY_VALUATION (View)
    views["V_INVENTORY_VALUATION"] = DbTable(
        tabname="V_INVENTORY_VALUATION",
        tabschema="ENTERPRISE",
        table_type="V",
        remarks="Financial balance view calculating total inventory valuation across storage facilities.",
        card=4500,
        colcount=6,
        columns=[
            DbColumn(colname="WH_CODE", typename="VARCHAR", length=16, scale=0, nulls="N", colno=1, remarks="Warehouse code"),
            DbColumn(colname="SKU_CODE", typename="VARCHAR", length=32, scale=0, nulls="N", colno=2, remarks="Product SKU code"),
            DbColumn(colname="PROD_NAME", typename="VARCHAR", length=160, scale=0, nulls="N", colno=3, remarks="Product title"),
            DbColumn(colname="ON_HAND_QTY", typename="INTEGER", length=4, scale=0, nulls="N", colno=4, remarks="On-hand quantity"),
            DbColumn(colname="BASE_PRICE", typename="DECIMAL", length=10, scale=2, nulls="N", colno=5, remarks="Catalog unit base price"),
            DbColumn(colname="TOTAL_ASSET_VALUE", typename="DECIMAL", length=14, scale=2, nulls="N", colno=6, remarks="Calculated on-hand monetary value"),
        ],
        view_definition="""
CREATE VIEW ENTERPRISE.V_INVENTORY_VALUATION AS
SELECT
    W.WH_CODE,
    P.SKU_CODE,
    P.PROD_NAME,
    I.ON_HAND_QTY,
    P.BASE_PRICE,
    (I.ON_HAND_QTY * P.BASE_PRICE) AS TOTAL_ASSET_VALUE
FROM ENTERPRISE.INVENTORY I
JOIN ENTERPRISE.PRODUCT_MST P ON I.PROD_ID = P.PROD_ID
JOIN ENTERPRISE.WAREHOUSE_MST W ON I.WH_ID = W.WH_ID
        """.strip(),
    )

    total_cols = sum(len(t.columns) for t in tables.values()) + sum(len(v.columns) for v in views.values())
    total_fk = sum(len(t.foreign_keys) for t in tables.values())

    return DbSchemaMetadata(
        schema_name="ENTERPRISE",
        tables=tables,
        views=views,
        total_tables=len(tables),
        total_views=len(views),
        total_columns=total_cols,
        declared_relationships_count=total_fk,
        extracted_at="2026-11-10T14:30:00Z",
    )
