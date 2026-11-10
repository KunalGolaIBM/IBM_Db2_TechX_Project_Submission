# IBM Db2 Enterprise Demonstration Database

This directory contains the synthetic enterprise database representing an Order-Management System for IBM Db2 LUW (Linux, Unix, Windows).

---

## 📁 Files

- `schema.sql`: Full DDL script creating schema `ENTERPRISE`, 13 tables, primary keys, declared foreign keys, check constraints, unique indexes, and 2 reporting views.
- `seed.sql`: Synthetic transactional dataset with realistic business entities and relationships.

---

## 🏛️ Database Architecture & Entities

The synthetic database models an enterprise order fulfillment lifecycle:

| Table | Db2 Type | Purpose | Key Columns |
|---|---|---|---|
| `CUSTOMER_MST` | Table | Client registry | `CUST_ID` (PK), `CUST_NAME`, `STATUS_CD` |
| `PRODUCT_MST` | Table | Merchandise catalog | `PROD_ID` (PK), `SKU_CODE`, `BASE_PRICE` |
| `SUPPLIER_MST` | Table | Wholesale vendors | `SUPP_ID` (PK), `SUPP_NAME`, `COUNTRY_CD` |
| `WAREHOUSE_MST` | Table | Regional storage hubs | `WH_ID` (PK), `WH_CODE`, `REGION_CD` |
| `ORD_HDR` | Table | Order contract header | `ORDER_ID` (PK), `CUST_ID` (FK), `TOTAL_AMT` |
| `ORD_LINE` | Table | Line-item SKU details | `LINE_ID` (PK), `ORDER_ID` (FK), `PROD_ID` (FK) |
| `INVENTORY` | Table | Physical stock balances | `INV_ID` (PK), `PROD_ID` (FK), `WH_ID` (FK) |
| `INVENTORY_RESERVATION` | Table | Pre-fulfillment holds | `RESV_ID` (PK), `ORDER_ID` (FK), `PROD_ID` (FK) |
| `PAYMENT_METHOD` | Table | Tokenized billing vault | `PM_ID` (PK), `CUST_ID` (FK), `TOKENIZED_ACCT` |
| `PAYMENT_TXN` | Table | Gateway authorizations | `TXN_ID` (PK), `ORDER_ID` (FK), `PM_ID` (FK) |
| `SHIPMENT_HDR` | Table | Dispatch manifests | `SHIPMENT_ID` (PK), `ORDER_ID` (FK), `WH_ID` (FK) |
| `SHIPMENT_ITEM` | Table | Packed carton units | `SHIP_ITEM_ID` (PK), `SHIPMENT_ID` (FK), `LINE_ID` (FK) |
| `RETURN_HDR` | Table | RMA return filings | `RET_ID` (PK), `ORDER_ID` (Inferred link), `CUST_REF_NO` (Inferred link) |
| `V_ACTIVE_ORDERS` | View | Operational summary | Joins `ORD_HDR`, `CUSTOMER_MST`, `PAYMENT_TXN` |
| `V_INVENTORY_VALUATION` | View | Asset value calculation | Joins `INVENTORY`, `PRODUCT_MST`, `WAREHOUSE_MST` |

### 🎯 Intentional Enterprise Ambiguities
Enterprise databases often have legacy tables where foreign keys were never formally added to the catalog:
1. **`RETURN_HDR.ORDER_ID`**: Has no explicit foreign key constraint to `ORD_HDR.ORDER_ID` in `SYSCAT.REFERENCES`. CatalogLens detects this link through heuristic inference (Exact primary key name match and type compatibility)!
2. **`RETURN_HDR.CUST_REF_NO`**: Uses an ambiguous legacy name referencing `CUSTOMER_MST.CUST_ID`. CatalogLens detects this via prefix convention matching!

---

## 🚀 Deployment Instructions

### Deploying to an IBM Db2 LUW Instance

1. Connect to your Db2 database using the Db2 CLI or CLPPlus:
   ```bash
   db2 connect to SAMPLE user db2inst1 using your_password
   ```

2. Execute the schema script:
   ```bash
   db2 -tvf database/schema.sql
   ```

3. Execute the seed script:
   ```bash
   db2 -tvf database/seed.sql
   ```

4. Verify creation:
   ```sql
   SELECT TABNAME, CARD FROM SYSCAT.TABLES WHERE TABSCHEMA = 'ENTERPRISE';
   ```

---

## 🛠️ Inspecting with IBM Db2 Developer Extension for VS Code

1. Open VS Code.
2. Ensure the **IBM Db2 Developer Extension** is installed.
3. Add a new connection profile with your host, port, database, user, and password.
4. Expand the **Database Connection** panel in VS Code.
5. Expand schema `ENTERPRISE` to view tables, views, and columns.
6. Open an SQL file and execute:
   ```sql
   SELECT * FROM ENTERPRISE.V_ACTIVE_ORDERS;
   ```
7. Launch **CatalogLens** to analyze the business workflows, dependency risks, and inferred relationships across the same database!
