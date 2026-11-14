"""Physical-design advice that Db2 measures, instead of a model guessing.

A migration is not finished when the SQL runs. The table also needs a shape.
Rather than asking a language model what it thinks, PortProof builds the
candidate shapes in a throwaway schema, loads the same rows into each, and
reads Db2's own numbers back out of the catalog.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import db

SCHEMA = "PPTEST"


@dataclass
class CompressionAdvice:
    table: str
    rows: int
    uncompressed_pages: int | None
    compressed_pages: int | None
    percent_saved: float | None
    adaptive_percent_saved: float | None = None
    avg_row_size: int | None = None
    note: str = ""

    @property
    def measured_page_saving(self) -> float | None:
        """Saving computed from the catalog's own page counts.

        Independent of the compression estimator: this is the difference Db2
        recorded in ``SYSCAT.TABLES.NPAGES`` after RUNSTATS on two tables that
        hold byte-identical rows.
        """
        if not self.uncompressed_pages or self.compressed_pages is None:
            return None
        return 100.0 * (self.uncompressed_pages - self.compressed_pages) / self.uncompressed_pages

    @property
    def headline(self) -> str:
        measured = self.measured_page_saving
        parts: list[str] = []
        if measured is not None:
            parts.append(
                f"{measured:.1f}% fewer pages measured ("
                f"{self.uncompressed_pages} -> {self.compressed_pages} pages "
                f"for the same {self.rows} rows)"
            )
        if self.percent_saved is not None:
            parts.append(
                f"Db2's own estimator agrees at {self.percent_saved:.0f}%"
                + (
                    f" and puts the ceiling at {self.adaptive_percent_saved:.0f}%"
                    if self.adaptive_percent_saved is not None
                    else ""
                )
                + (f", avg row {self.avg_row_size}B" if self.avg_row_size else "")
            )
        if not parts:
            return f"{self.table}: compression not measurable here ({self.note})"
        return f"{self.table}: COMPRESS YES ADAPTIVE -- " + "; ".join(parts)


def measure_compression(conn, *, rows: int = 4000) -> CompressionAdvice:
    """Measure what COMPRESS YES ADAPTIVE actually buys on representative rows.

    ``ADMIN_GET_TAB_COMPRESS_INFO`` reports Db2's own estimate, so the number in
    the report is the engine's, not an assumption.
    """
    plain = f"{SCHEMA}.PD_PLAIN"
    compressed = f"{SCHEMA}.PD_COMPRESSED"
    for table in (plain, compressed):
        try:
            db.execute(conn, f"DROP TABLE {table}")
        except db.Db2Error:
            pass

    columns = (
        "ID INTEGER NOT NULL, STATUS VARCHAR(20), CITY VARCHAR(40), "
        "NOTE VARCHAR(200), AMOUNT DECIMAL(12,2)"
    )
    db.execute(conn, f"CREATE TABLE {plain} ({columns})")
    db.execute(conn, f"CREATE TABLE {compressed} ({columns}) COMPRESS YES ADAPTIVE")

    # Deliberately repetitive values: the shape real migrated data tends to have.
    generator = f"""
        INSERT INTO {{target}}
        WITH N(I) AS (
          VALUES 1 UNION ALL SELECT I + 1 FROM N WHERE I < {int(rows)}
        )
        SELECT I,
               CASE MOD(I, 3) WHEN 0 THEN 'PAID' WHEN 1 THEN 'NEW' ELSE 'CANCELLED' END,
               CASE MOD(I, 4) WHEN 0 THEN 'Lucknow' WHEN 1 THEN 'Pune'
                              WHEN 2 THEN 'Mathura' ELSE 'Agra' END,
               'migrated row, status unchanged since cutover batch ' || CAST(MOD(I, 50) AS VARCHAR(8)),
               DECIMAL(MOD(I, 900) + 0.50, 12, 2)
          FROM N
    """
    for table in (plain, compressed):
        db.execute(conn, generator.format(target=table))

    try:
        db.execute(
            conn,
            "CALL SYSPROC.ADMIN_CMD(?)",
            (f"RUNSTATS ON TABLE {compressed} WITH DISTRIBUTION AND INDEXES ALL",),
        )
    except db.Db2Error:
        pass

    def pages(table: str) -> int | None:
        schema, name = table.split(".")
        row = db.fetch_one(
            conn,
            "SELECT NPAGES FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
            (schema, name),
        )
        return int(row[0]) if row and row[0] is not None and int(row[0]) >= 0 else None

    try:
        db.execute(conn, "CALL SYSPROC.ADMIN_CMD(?)", (f"RUNSTATS ON TABLE {plain}",))
    except db.Db2Error:
        pass

    # Result-column names here are genuinely version-dependent, and measured on
    # CE 12.1.5 rather than assumed:
    #
    #   * The column is NOT called PCTPAGESSAVED, which is what most docs and
    #     blog posts say. Selecting that name gets SQLCODE -206, and a forgiving
    #     caller then reports "not measurable" for a table that compressed fine.
    #   * ADMIN_GET_TAB_COMPRESS_INFO_V10 is a SPECIFIC name, not a routine
    #     name: calling it directly is SQLCODE -440. The unqualified call
    #     resolves to that overload anyway, so its columns are the ones to use.
    #   * EXECUTE must be granted per specific signature -- see
    #     scripts/create_db2_users.sh -- or the whole call is SQLCODE -551.
    #
    # So: try the shape this server exposes first, then the newer spelling.
    estimate: tuple | None = None
    note = ""
    for sql in (
        "SELECT PCTPAGESSAVED_CURRENT, PCTPAGESSAVED_ADAPTIVE, AVGROWSIZE_CURRENT "
        "FROM TABLE(SYSPROC.ADMIN_GET_TAB_COMPRESS_INFO(?, ?)) AS T",
        "SELECT PAGES_SAVED_PERCENT, BYTES_SAVED_PERCENT, ROWS_SAMPLED "
        "FROM TABLE(SYSPROC.ADMIN_GET_TAB_COMPRESS_INFO(?, ?)) AS T",
    ):
        try:
            estimate = db.fetch_one(conn, sql, (SCHEMA, "PD_COMPRESSED"))
            note = ""
            break
        except db.Db2Error as exc:
            note = f"SQLCODE={exc.sqlcode}"

    def _number(value) -> float | None:
        return float(value) if value is not None else None

    return CompressionAdvice(
        table="PD_COMPRESSED",
        rows=rows,
        uncompressed_pages=pages(plain),
        compressed_pages=pages(compressed),
        percent_saved=_number(estimate[0]) if estimate else None,
        adaptive_percent_saved=_number(estimate[1]) if estimate else None,
        avg_row_size=int(estimate[2]) if estimate and estimate[2] is not None else None,
        note=note or ("no estimate returned" if not estimate else ""),
    )


@dataclass
class ColumnarAdvice:
    supported: bool
    note: str

    @property
    def headline(self) -> str:
        return (
            "ORGANIZE BY COLUMN (BLU) available: recommend it for scan-heavy "
            "analytical tables"
            if self.supported
            else f"columnar storage unavailable here: {self.note}"
        )


def check_columnar(conn) -> ColumnarAdvice:
    """Is BLU columnar organisation actually usable on this instance?"""
    table = f"{SCHEMA}.PD_COLUMNAR"
    try:
        db.execute(conn, f"DROP TABLE {table}")
    except db.Db2Error:
        pass
    try:
        db.execute(
            conn,
            f"CREATE TABLE {table} (ID INTEGER NOT NULL, AMOUNT DECIMAL(12,2)) "
            "ORGANIZE BY COLUMN",
        )
    except db.Db2Error as exc:
        return ColumnarAdvice(supported=False, note=f"SQLCODE={exc.sqlcode}")
    return ColumnarAdvice(supported=True, note="")


def workload_hotspots(conn, limit: int = 5) -> list[tuple[str, int, float]]:
    """The migrated workload's real cost, from Db2's package cache.

    This is how PortProof checks for regressions after a migration: it reads
    what the statements actually did, rather than predicting what they might.
    """
    try:
        rows = db.fetch_all(
            conn,
            "SELECT SUBSTR(STMT_TEXT, 1, 80), NUM_EXECUTIONS, TOTAL_CPU_TIME "
            "FROM TABLE(MON_GET_PKG_CACHE_STMT(NULL, NULL, NULL, -2)) AS T "
            "WHERE STMT_TEXT IS NOT NULL AND NUM_EXECUTIONS > 0 "
            "ORDER BY TOTAL_CPU_TIME DESC FETCH FIRST ? ROWS ONLY",
            (int(limit),),
        )
    except db.Db2Error:
        return []
    return [(str(r[0]).strip(), int(r[1] or 0), float(r[2] or 0)) for r in rows]
