"""
Database schema representations matching IBM Db2 LUW catalog constructs.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ForeignKeyRef(BaseModel):
    constraint_name: str
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    delete_rule: str = "NO ACTION"
    update_rule: str = "NO ACTION"


class DbColumn(BaseModel):
    colname: str
    typename: str
    length: int = 0
    scale: int = 0
    nulls: str = "Y"  # 'Y' or 'N'
    default_val: Optional[str] = None
    colno: int = 0
    remarks: Optional[str] = None
    is_primary_key: bool = False
    primary_key_seq: Optional[int] = None
    is_foreign_key: bool = False
    foreign_key_target: Optional[str] = None  # e.g. "CUSTOMER_MST.CUST_ID"


class DbConstraint(BaseModel):
    constname: str
    tabname: str
    const_type: str  # P=PK, F=FK, U=Unique, K=Check
    columns: List[str] = Field(default_factory=list)
    ref_table: Optional[str] = None


class DbIndex(BaseModel):
    indname: str
    tabname: str
    uniquerule: str = "D"  # 'U'=Unique, 'P'=Primary, 'D'=Duplicates allowed
    colnames: str = ""  # "+COL1+COL2" formatted in Db2 catalog


class DbTable(BaseModel):
    tabname: str
    tabschema: str
    table_type: str = "T"  # 'T'=Table, 'V'=View, etc.
    remarks: Optional[str] = None
    card: int = -1  # Cardinality (number of rows in Db2 stats)
    colcount: int = 0
    columns: List[DbColumn] = Field(default_factory=list)
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[ForeignKeyRef] = Field(default_factory=list)
    indexes: List[DbIndex] = Field(default_factory=list)
    constraints: List[DbConstraint] = Field(default_factory=list)
    view_definition: Optional[str] = None

    def get_column(self, colname: str) -> Optional[DbColumn]:
        norm = colname.strip().upper()
        for col in self.columns:
            if col.colname.upper() == norm:
                return col
        return None


class DbSchemaMetadata(BaseModel):
    schema_name: str
    tables: Dict[str, DbTable] = Field(default_factory=dict)
    views: Dict[str, DbTable] = Field(default_factory=dict)
    total_tables: int = 0
    total_views: int = 0
    total_columns: int = 0
    declared_relationships_count: int = 0
    extracted_at: str = ""

    def get_object(self, name: str) -> Optional[DbTable]:
        norm = name.strip().upper()
        if norm in self.tables:
            return self.tables[norm]
        if norm in self.views:
            return self.views[norm]
        return None
