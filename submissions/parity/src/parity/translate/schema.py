"""Column types for type aware translation.

Some Db2 differences can only be fixed when the column
type is known. `SUM` of an integer column overflows on
Db2 and needs a cast to a bigint. A decimal column must
not be cast, because that would change the value.

The context is built from the source schema and passed to
the translator. A rule that needs it does nothing when no
context is given.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from parity.config import DatabaseSettings
from parity.sync.schema import TableDef

INTEGER_TYPES = ("INTEGER", "SMALLINT", "BIGINT")


@dataclass(frozen=True)
class SchemaContext:
    """The column types of the tables of a workload."""

    tables: Mapping[str, Mapping[str, str]]

    @classmethod
    def from_tables(cls, tables: tuple[TableDef, ...]) -> SchemaContext:
        """Build a context from introspected tables."""
        mapping: dict[str, dict[str, str]] = {}
        for table in tables:
            columns = {
                column.name.lower(): column.db2_type.upper()
                for column in table.columns
            }
            mapping[table.name.lower()] = columns
        return cls(tables=mapping)

    def column_type(self, table: str, column: str) -> str | None:
        """Return the Db2 type of one column, or None."""
        columns = self.tables.get(table.lower())
        if columns is None:
            return None
        return columns.get(column.lower())

    def resolve_type(
        self, table_names: tuple[str, ...], column: str
    ) -> str | None:
        """Return the type of a column found in the given tables.

        The column must exist in exactly one table, or in
        several tables with the same type. Anything else is
        unknown and no rule fires.
        """
        found = {
            self.column_type(table, column)
            for table in table_names
            if self.column_type(table, column) is not None
        }
        if len(found) == 1:
            return found.pop()
        return None

    def is_integer(self, table_names: tuple[str, ...], column: str) -> bool:
        """True when the column holds a whole number."""
        column_type = self.resolve_type(table_names, column)
        if column_type is None:
            return False
        return column_type.split("(")[0].strip() in INTEGER_TYPES


def schema_from_postgres(settings: DatabaseSettings) -> SchemaContext:
    """Read the schema of the source database."""
    from parity.sync.schema import introspect_postgres

    return SchemaContext.from_tables(introspect_postgres(settings))
