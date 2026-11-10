"""
Schema discovery using Db2 catalog views.

Safety assumptions:
- Schema name comes from configuration, not user input
- All identifiers retrieved from SYSCAT views are trusted
- Foreign key graph may contain cycles; we detect and fail closed
"""
from typing import Any

import networkx as nx

from app.config import settings
from app.db import query


def columns(schema: str) -> list[tuple[Any, ...]]:
    """
    Retrieve all columns for a schema from SYSCAT.COLUMNS.
    
    Args:
        schema: Schema name (e.g., 'DB2INST1')
        
    Returns:
        List of tuples: (TABNAME, COLNAME, TYPENAME, LENGTH, NULLS)
    """
    sql = """
        SELECT TABNAME, COLNAME, TYPENAME, LENGTH, NULLS
        FROM SYSCAT.COLUMNS 
        WHERE TABSCHEMA = ?
        ORDER BY TABNAME, COLNO
    """
    result = query(sql, (schema.upper(),))
    return result if result else []


def tables(schema: str) -> list[tuple[Any, ...]]:
    """
    Retrieve all tables for a schema from SYSCAT.TABLES.
    
    Args:
        schema: Schema name
        
    Returns:
        List of tuples: (TABNAME, TYPE)
    """
    sql = """
        SELECT TABNAME, TYPE
        FROM SYSCAT.TABLES 
        WHERE TABSCHEMA = ? AND TYPE = 'T'
        ORDER BY TABNAME
    """
    result = query(sql, (schema.upper(),))
    return result if result else []


def fk_edges(schema: str) -> list[tuple[Any, ...]]:
    """
    Retrieve foreign key relationships from SYSCAT.REFERENCES.
    
    Args:
        schema: Schema name
        
    Returns:
        List of tuples: (child_table, parent_table, fk_colnames, pk_colnames)
    """
    sql = """
        SELECT 
            R.TABNAME as CHILD_TABLE,
            R.REFTABNAME as PARENT_TABLE,
            R.FK_COLNAMES,
            R.PK_COLNAMES
        FROM SYSCAT.REFERENCES R
        WHERE R.TABSCHEMA = ?
        ORDER BY R.TABNAME, R.REFTABNAME
    """
    result = query(sql, (schema.upper(),))
    return result if result else []


def delete_order(schema: str, root: str) -> list[str]:
    """
    Compute safe deletion order for tables, respecting foreign keys.
    
    Children must be deleted before parents to avoid FK violations.
    
    Args:
        schema: Schema name
        root: Root table name (e.g., 'PATIENT')
        
    Returns:
        List of table names in deletion order (children first)
        
    Raises:
        ValueError: If FK graph contains cycles
        KeyError: If root table is not found
    """
    known_tables = {row[0].strip().upper() for row in tables(schema) if row}
    if root.upper() not in known_tables:
        raise KeyError(f"Root table {schema}.{root} not found")

    # Build directed graph: parent -> child
    g = nx.DiGraph()
    
    edges = fk_edges(schema)
    for child, parent, fk_cols, pk_cols in edges:
        child = child.strip()
        parent = parent.strip()
        g.add_edge(parent, child)
    
    # Check for cycles
    try:
        cycles = list(nx.find_cycle(g, orientation="original"))
        if cycles:
            cycle_desc = " -> ".join([f"{u}" for u, v, d in cycles])
            raise ValueError(f"Foreign key cycle detected: {cycle_desc}")
    except nx.NetworkXNoCycle:
        pass  # Good - no cycles
    
    # Get all tables reachable from root
    g.add_node(root.upper())

    reachable = nx.descendants(g, root.upper()) | {root.upper()}
    subgraph = g.subgraph(reachable)
    
    # Topological sort, then reverse (children first)
    try:
        topo_order = list(nx.topological_sort(subgraph))
        return list(reversed(topo_order))
    except nx.NetworkXError as e:
        raise ValueError(f"Could not compute deletion order: {e}")


def fk_column_to_root(schema: str, table: str, root: str) -> str | None:
    """
    Find the foreign key column in 'table' that references 'root'.
    
    Args:
        schema: Schema name
        table: Child table
        root: Root table (parent)
        
    Returns:
        Foreign key column name, or None if no direct relationship
    """
    if table.upper() == root.upper():
        # For the root table itself, use the primary key
        sql = """
            SELECT COLNAME FROM SYSCAT.KEYCOLUSE
            WHERE TABSCHEMA = ? AND TABNAME = ? AND CONSTNAME LIKE 'PK%'
            ORDER BY COLSEQ
            FETCH FIRST 1 ROW ONLY
        """
        result = query(sql, (schema.upper(), root.upper()))
        return result[0][0].strip() if result else "ID"
    
    # Find FK from table to root
    sql = """
        SELECT FK_COLNAMES
        FROM SYSCAT.REFERENCES
        WHERE TABSCHEMA = ? AND TABNAME = ? AND REFTABNAME = ?
    """
    result = query(sql, (schema.upper(), table.upper(), root.upper()))
    if result:
        # FK_COLNAMES might be space-delimited if composite
        fk_cols = result[0][0].strip()
        # Return the first column if composite
        return fk_cols.split()[0] if fk_cols else None
    
    # Check transitive relationship through FK chain
    # For now, return None - Phase 4 will need more sophisticated handling
    return None


def summary(schema: str) -> dict[str, Any]:
    """
    Generate a summary of the schema for agent consumption.
    
    Returns metadata only - no actual data values.
    
    Args:
        schema: Schema name
        
    Returns:
        Dictionary with tables, columns, foreign_keys, and graph info
    """
    tabs = tables(schema)
    cols = columns(schema)
    fks = fk_edges(schema)
    
    # Group columns by table
    columns_by_table: dict[str, list[dict[str, Any]]] = {}
    for tabname, colname, typename, length, nulls in cols:
        tabname = tabname.strip()
        if tabname not in columns_by_table:
            columns_by_table[tabname] = []
        columns_by_table[tabname].append({
            "name": colname.strip(),
            "type": typename.strip(),
            "length": length,
            "nullable": nulls.strip() == "Y"
        })
    
    # Format FK relationships
    fk_list = []
    for child, parent, fk_cols, pk_cols in fks:
        fk_list.append({
            "child": child.strip(),
            "parent": parent.strip(),
            "fk_columns": fk_cols.strip(),
            "pk_columns": pk_cols.strip()
        })
    
    return {
        "schema": schema,
        "tables": [t[0].strip() for t in tabs],
        "column_count": len(cols),
        "columns_by_table": columns_by_table,
        "foreign_keys": fk_list,
        "fk_count": len(fk_list)
    }


if __name__ == "__main__":
    """Quick test of discovery functions."""
    import json
    
    schema = settings.db2_schema
    print(f"Discovering schema: {schema}\n")
    
    print("=" * 60)
    print("Tables")
    print("=" * 60)
    for table in tables(schema):
        print(f"  {table[0]}")
    
    print(f"\n{'=' * 60}")
    print("Foreign Keys")
    print("=" * 60)
    for fk in fk_edges(schema):
        print(f"  {fk[0]} -> {fk[1]} ({fk[2]})")
    
    print(f"\n{'=' * 60}")
    print("Delete Order (from PATIENT)")
    print("=" * 60)
    try:
        order = delete_order(schema, "PATIENT")
        for i, table in enumerate(order, 1):
            print(f"  {i}. {table}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print(f"\n{'=' * 60}")
    print("Summary (JSON)")
    print("=" * 60)
    summ = summary(schema)
    print(json.dumps(summ, indent=2))
