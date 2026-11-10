"""
Db2 Metadata Extractor.
Extracts tables, columns, constraints, foreign keys, indexes, and views
from live IBM Db2 LUW catalogs using standard SYSCAT queries,
with seamless fallback to the realistic enterprise demonstration dataset.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

from .connection import Db2ConnectionManager
from ..core.config import get_settings
from .catalog_queries import (
    SQL_LIST_SCHEMAS,
    SQL_GET_TABLES_AND_VIEWS,
    SQL_GET_COLUMNS_BY_SCHEMA,
    SQL_GET_PRIMARY_KEYS,
    SQL_GET_FOREIGN_KEYS,
    SQL_GET_INDEXES,
    SQL_GET_CONSTRAINTS,
    SQL_GET_VIEW_DEFINITIONS,
)
from .sample_catalog import get_sample_enterprise_metadata
from ..models.schema import (
    DbColumn,
    DbConstraint,
    DbIndex,
    DbTable,
    DbSchemaMetadata,
    ForeignKeyRef,
)

logger = logging.getLogger("CatalogLens.MetadataExtractor")


class MetadataExtractor:
    def __init__(self, connection_manager: Optional[Db2ConnectionManager] = None):
        if connection_manager is not None:
            self.conn_mgr = connection_manager
        else:
            settings = get_settings()
            if settings.has_db2_credentials():
                self.conn_mgr = Db2ConnectionManager(
                    host=settings.db2_host,
                    port=settings.db2_port,
                    database=settings.db2_database,
                    username=settings.db2_username,
                    password=settings.db2_password,
                    security=settings.db2_security,
                    timeout=settings.db2_timeout,
                )
            else:
                self.conn_mgr = None

    def list_schemas(self, use_demo: bool = False) -> List[str]:
        """Lists available non-system schemas from Db2, or demo schemas."""
        if use_demo or not self.conn_mgr or not Db2ConnectionManager.is_driver_available():
            return ["ENTERPRISE", "SALES_ARCHIVE", "FIN_AUDIT"]

        try:
            rows = self.conn_mgr.execute_query(SQL_LIST_SCHEMAS)
            schemas = [r.get("SCHEMANAME", "") for r in rows if r.get("SCHEMANAME")]
            return schemas if schemas else ["ENTERPRISE"]
        except Exception as e:
            logger.warning("Could not query live schemas, falling back to demo list: %s", str(e))
            return ["ENTERPRISE", "SALES_ARCHIVE", "FIN_AUDIT"]

    def extract_schema_metadata(
        self,
        schema_name: str = "ENTERPRISE",
        use_demo: bool = False,
    ) -> DbSchemaMetadata:
        """
        Extracts and normalizes metadata for the given schema.
        Uses live Db2 connection if available and not in demo mode.
        """
        norm_schema = schema_name.strip().upper()

        if use_demo or not self.conn_mgr or not Db2ConnectionManager.is_driver_available():
            logger.info("Using Enterprise Demo Metadata for schema '%s'", norm_schema)
            metadata = get_sample_enterprise_metadata()
            metadata.schema_name = norm_schema
            return metadata

        try:
            return self._extract_live_metadata(norm_schema)
        except Exception as e:
            logger.error("Live extraction failed for schema '%s': %s. Falling back to demo data.", norm_schema, str(e))
            metadata = get_sample_enterprise_metadata()
            metadata.schema_name = norm_schema
            return metadata

    def _extract_live_metadata(self, schema_name: str) -> DbSchemaMetadata:
        """Queries live Db2 catalog tables and normalizes into typed models."""
        tables_dict: Dict[str, DbTable] = {}
        views_dict: Dict[str, DbTable] = {}

        # 1. Fetch tables and views
        table_rows = self.conn_mgr.execute_query(SQL_GET_TABLES_AND_VIEWS, (schema_name,))
        for row in table_rows:
            tabname = row.get("TABNAME", "").strip()
            table_type = row.get("TYPE", "T").strip()
            remarks = row.get("REMARKS", "")
            card = int(row.get("CARD", -1) or -1)
            colcount = int(row.get("COLCOUNT", 0) or 0)

            t_obj = DbTable(
                tabname=tabname,
                tabschema=schema_name,
                table_type=table_type,
                remarks=remarks,
                card=card,
                colcount=colcount,
                columns=[],
                primary_keys=[],
                foreign_keys=[],
                indexes=[],
                constraints=[],
            )
            if table_type == "V":
                views_dict[tabname] = t_obj
            else:
                tables_dict[tabname] = t_obj

        # 2. Fetch all columns
        col_rows = self.conn_mgr.execute_query(SQL_GET_COLUMNS_BY_SCHEMA, (schema_name,))
        for r in col_rows:
            tabname = r.get("TABNAME", "").strip()
            target_obj = tables_dict.get(tabname) or views_dict.get(tabname)
            if not target_obj:
                continue

            colname = r.get("COLNAME", "").strip()
            typename = r.get("TYPENAME", "").strip()
            length = int(r.get("LENGTH", 0) or 0)
            scale = int(r.get("SCALE", 0) or 0)
            nulls = r.get("NULLS", "Y").strip()
            default_val = r.get("DEFAULT_VAL")
            colno = int(r.get("COLNO", 0) or 0)
            remarks = r.get("REMARKS", "")
            keyseq = r.get("KEYSEQ")
            is_pk = (keyseq is not None and int(keyseq) > 0)

            col = DbColumn(
                colname=colname,
                typename=typename,
                length=length,
                scale=scale,
                nulls=nulls,
                default_val=str(default_val) if default_val else None,
                colno=colno,
                remarks=remarks if remarks else None,
                is_primary_key=is_pk,
                primary_key_seq=int(keyseq) if is_pk else None,
            )
            target_obj.columns.append(col)

        # 3. Fetch primary keys
        pk_rows = self.conn_mgr.execute_query(SQL_GET_PRIMARY_KEYS, (schema_name,))
        for r in pk_rows:
            tabname = r.get("TABNAME", "").strip()
            colname = r.get("COLNAME", "").strip()
            constname = r.get("CONSTNAME", "").strip()
            target_obj = tables_dict.get(tabname)
            if target_obj:
                if colname not in target_obj.primary_keys:
                    target_obj.primary_keys.append(colname)
                # Mark column as PK
                col = target_obj.get_column(colname)
                if col:
                    col.is_primary_key = True

                # Check constraint list
                existing = next((c for c in target_obj.constraints if c.constname == constname), None)
                if existing:
                    existing.columns.append(colname)
                else:
                    target_obj.constraints.append(
                        DbConstraint(constname=constname, tabname=tabname, const_type="P", columns=[colname])
                    )

        # 4. Fetch foreign keys
        fk_rows = self.conn_mgr.execute_query(SQL_GET_FOREIGN_KEYS, (schema_name,))
        for r in fk_rows:
            source_table = r.get("SOURCE_TABLE", "").strip()
            target_table = r.get("TARGET_TABLE", "").strip()
            constname = r.get("CONSTNAME", "").strip()
            source_col = r.get("SOURCE_COL", "").strip()
            del_rule = r.get("DELETE_RULE", "NO ACTION").strip()
            upd_rule = r.get("UPDATE_RULE", "NO ACTION").strip()

            target_obj = tables_dict.get(source_table)
            if target_obj:
                # Find matching primary key column on target table if available
                target_table_obj = tables_dict.get(target_table)
                target_col = source_col  # Default heuristic
                if target_table_obj and target_table_obj.primary_keys:
                    target_col = target_table_obj.primary_keys[0]

                fk_ref = ForeignKeyRef(
                    constraint_name=constname,
                    source_table=source_table,
                    source_column=source_col,
                    target_table=target_table,
                    target_column=target_col,
                    delete_rule=del_rule,
                    update_rule=upd_rule,
                )
                target_obj.foreign_keys.append(fk_ref)

                col = target_obj.get_column(source_col)
                if col:
                    col.is_foreign_key = True
                    col.foreign_key_target = f"{target_table}.{target_col}"

        # 5. Fetch indexes
        idx_rows = self.conn_mgr.execute_query(SQL_GET_INDEXES, (schema_name,))
        for r in idx_rows:
            tabname = r.get("TABNAME", "").strip()
            target_obj = tables_dict.get(tabname)
            if target_obj:
                target_obj.indexes.append(
                    DbIndex(
                        indname=r.get("INDNAME", "").strip(),
                        tabname=tabname,
                        uniquerule=r.get("UNIQUERULE", "D").strip(),
                        colnames=r.get("COLNAMES", "").strip(),
                    )
                )

        # 6. Fetch check & unique constraints
        try:
            ck_rows = self.conn_mgr.execute_query(SQL_GET_CONSTRAINTS, (schema_name,))
            for r in ck_rows:
                tabname = r.get("TABNAME", "").strip()
                target_obj = tables_dict.get(tabname)
                if target_obj:
                    target_obj.constraints.append(
                        DbConstraint(
                            constname=r.get("CONSTNAME", "").strip(),
                            tabname=tabname,
                            const_type=r.get("TYPE", "K").strip(),
                            columns=[],
                        )
                    )
        except Exception:
            pass

        # 7. Fetch view definitions
        try:
            view_rows = self.conn_mgr.execute_query(SQL_GET_VIEW_DEFINITIONS, (schema_name,))
            for r in view_rows:
                vname = r.get("VIEWNAME", "").strip()
                vobj = views_dict.get(vname)
                if vobj:
                    vobj.view_definition = r.get("VIEW_DEFINITION", "")
        except Exception:
            pass

        total_cols = sum(len(t.columns) for t in tables_dict.values()) + sum(len(v.columns) for v in views_dict.values())
        total_fk = sum(len(t.foreign_keys) for t in tables_dict.values())

        return DbSchemaMetadata(
            schema_name=schema_name,
            tables=tables_dict,
            views=views_dict,
            total_tables=len(tables_dict),
            total_views=len(views_dict),
            total_columns=total_cols,
            declared_relationships_count=total_fk,
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )
