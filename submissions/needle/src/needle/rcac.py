"""Per-user vector-search router for Db2 tables under row and column access control (RCAC).

Why this exists (measured on Db2 12.1.5.0, docs/evidence/rcac_real.md): for `FETCH APPROX FIRST n ROWS ONLY`
the optimizer sizes the DiskANN index scan at n / FF candidates, where FF is the compile-time filter factor of the
other predicates, and applies those predicates to the candidates at FETCH (over-fetch by 1/FF; section actuals:
21 rows out of the vector IXSCAN for n = 10). A row permission compares ROW_BUCKET with a per-user value from a
subquery on SESSION_USER, so every user shares one plan with the constant observed estimate FF = 0.495. Users who
see less than about half the table get fewer than k rows (NDL_P10: 2.05 of 10, recall 0.205). SEARCH_LIST_SIZE does
not change the candidate count; only n does. On ADV_DOC, Db2 keeps the vector index up to 134 estimated candidates
(n / FF) and switches to an exact table scan at about 200 or more.

The router looks up, once per (session user, table, k), how many rows that user can see (COUNT(*) under RCAC) and
the table cardinality (SYSCAT.TABLES.CARD), and picks one of a few fixed statement texts:
  * EXACT  FETCH EXACT FIRST k when visible rows <= T, or when the needed depth exceeds the largest fixed depth;
  * APPROX FETCH APPROX FIRST d, d = the smallest of DEPTHS >= ceil(k / fraction * m), with the inline guideline
    SEARCH_LIST_SIZE = max(50, 3 d), keeping the k nearest returned rows;
  * EXACT fallback when APPROX returns fewer than k rows or raises SQL0901N.
T = 7000 and m = 3.0 were fitted on the dev split (eval/rcac_router_fit.py) and evaluated on held-out queries.
Only integers validated with int() are interpolated into SQL (FETCH ... FIRST n must be a literal for Db2 to use the
vector index). The query vector is always a bound parameter.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass, field

_IDENT = re.compile(r"[A-Z][A-Z0-9_]{0,127}")


def _ident(name: str) -> str:
    """Validate an SQL identifier (schema, table or column). Raises ValueError if unsafe."""
    up = name.upper()
    if not _IDENT.fullmatch(up):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return up


DEPTHS = (10, 25, 50, 100, 200)  # the only APPROX statement texts the router issues (clean package cache)


@dataclass(frozen=True)
class RouterConfig:
    exact_max_rows: int = 7000         # T: visible set at or below this size -> EXACT (fitted on dev split)
    overfetch: float = 3.0             # m: depth needed = ceil(k / fraction * m), rounded up to DEPTHS (fitted)
    depths: tuple = DEPTHS
    use_guideline: bool = True         # add IXSCAN SEARCH_LIST_SIZE = max(min_sls, sls_factor * depth)
    min_sls: int = 50
    sls_factor: int = 3
    fallback_exact: bool = True        # APPROX returned < k rows -> rerun as EXACT


@dataclass(frozen=True)
class Strategy:
    mode: str            # "EXACT" or "APPROX"
    depth: int           # n in FETCH <mode> FIRST n ROWS ONLY
    k: int
    visible_rows: int
    total_rows: int
    search_list_size: int | None = None  # DiskANN L via inline optimization guideline (APPROX only)

    @property
    def fraction(self) -> float:
        return self.visible_rows / self.total_rows if self.total_rows > 0 else 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["fraction"] = round(self.fraction, 4)
        return d


def choose_strategy(visible_rows: int, total_rows: int, k: int, cfg: RouterConfig = RouterConfig()) -> Strategy:
    """Pure decision function (unit-tested without a database)."""
    k = int(k)
    visible_rows = int(visible_rows)
    total_rows = int(total_rows)
    if k < 1:
        raise ValueError("k must be >= 1")
    if total_rows <= 0 or visible_rows <= 0:
        # No statistics or nothing visible: exact search is always correct.
        return Strategy("EXACT", k, k, max(visible_rows, 0), max(total_rows, 0))
    total_rows = max(total_rows, visible_rows)  # stale statistics can undercount
    frac = visible_rows / total_rows
    if visible_rows <= cfg.exact_max_rows:
        return Strategy("EXACT", k, k, visible_rows, total_rows)
    need = math.ceil(k / frac * cfg.overfetch)
    fitting = [d for d in sorted(cfg.depths) if d >= max(need, k)]
    if not fitting:  # would need more depth than any fixed statement offers -> exact is the safe choice
        return Strategy("EXACT", k, k, visible_rows, total_rows)
    depth = int(fitting[0])
    sls = max(cfg.min_sls, cfg.sls_factor * depth) if cfg.use_guideline else None
    return Strategy("APPROX", depth, k, visible_rows, total_rows, sls)


def knn_sql(table: str, n: int, approx: bool, id_col: str = "ID", emb_col: str = "EMB",
            dim: int = 768, extra_cols: tuple[str, ...] = (), max_bucket: int | None = None,
            search_list_size: int | None = None) -> str:
    """k-NN statement with two bound parameters (the query vector, as text, twice).

    The table gets the correlation name T; `search_list_size` appends the inline optimization guideline
    <IXSCAN TABLE='T' SEARCH_LIST_SIZE='L'/> (DiskANN search list size; verified applied in db2exfmt SRCHLSIZ).
    `max_bucket` (optional, validated integer 0..100) adds the only supported filter, `WHERE ROW_BUCKET < max_bucket`
    (a literal the optimizer can size, used for experiments; RCAC still applies on top of it).
    """
    if max_bucket is not None:
        mb = int(max_bucket)
        if not 0 <= mb <= 100 or mb != max_bucket:
            raise ValueError("max_bucket must be an integer 0..100")
        where = f"ROW_BUCKET < {mb}"
    else:
        where = ""
    schema, _, name = table.partition(".")
    tbl = f"{_ident(schema)}.{_ident(name)}" if name else _ident(schema)
    idc, emb = _ident(id_col), _ident(emb_col)
    cols = "".join(f", {_ident(c)}" for c in extra_cols)
    n, dim = int(n), int(dim)
    if n < 1:
        raise ValueError("n must be >= 1")
    qv = f"VECTOR(CAST(? AS CLOB(100K)), {dim}, FLOAT32)"
    w = f"WHERE {where} " if where else ""
    g = ""
    if search_list_size and approx:
        g = (f" /* <OPTGUIDELINES><IXSCAN TABLE='T' SEARCH_LIST_SIZE='{int(search_list_size)}'/>"
             f"</OPTGUIDELINES> */")
    return (f"SELECT {idc}, VECTOR_DISTANCE({emb}, {qv}, COSINE) AS DIST{cols} FROM {tbl} T {w}"
            f"ORDER BY VECTOR_DISTANCE({emb}, {qv}, COSINE) "
            f"FETCH {'APPROX' if approx else 'EXACT'} FIRST {n} ROWS ONLY{g}")


def _fetch_all(stmt) -> list[tuple]:
    import ibm_db

    out = []
    r = ibm_db.fetch_tuple(stmt)
    while r:
        out.append(r)
        r = ibm_db.fetch_tuple(stmt)
    return out


def visible_and_total(conn, table: str) -> tuple[int, int]:
    """Rows the CURRENT session user may see (RCAC applies) and catalog cardinality (-1 if no stats)."""
    import ibm_db

    schema, _, name = table.partition(".")
    schema, name = _ident(schema), _ident(name)
    st = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {schema}.{name}")
    visible = int(ibm_db.fetch_tuple(st)[0])
    ibm_db.free_stmt(st)
    st = ibm_db.prepare(conn, "SELECT CARD FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?")
    ibm_db.execute(st, (schema, name))
    r = ibm_db.fetch_tuple(st)
    ibm_db.free_stmt(st)
    total = int(r[0]) if r and r[0] is not None else -1
    return visible, total


@dataclass
class Router:
    """Caches one Strategy per (session user, table, k)."""
    table: str
    id_col: str = "ID"
    emb_col: str = "EMB"
    dim: int = 768
    cfg: RouterConfig = field(default_factory=RouterConfig)
    _cache: dict = field(default_factory=dict)

    def strategy(self, conn, k: int) -> Strategy:
        import ibm_db

        st = ibm_db.exec_immediate(conn, "SELECT SESSION_USER FROM SYSIBM.SYSDUMMY1")
        user = ibm_db.fetch_tuple(st)[0].strip()
        ibm_db.free_stmt(st)
        key = (user, self.table.upper(), int(k))
        if key not in self._cache:
            visible, total = visible_and_total(conn, self.table)
            self._cache[key] = choose_strategy(visible, total, k, self.cfg)
        return self._cache[key]

    def sql_for(self, s: Strategy) -> str:
        return knn_sql(self.table, s.depth, s.mode == "APPROX", self.id_col, self.emb_col, self.dim,
                       search_list_size=s.search_list_size)

    def _run(self, conn, sql: str, qvec_text: str) -> list[tuple]:
        import ibm_db

        stmt = ibm_db.prepare(conn, sql)
        try:
            ibm_db.execute(stmt, (qvec_text, qvec_text))
            return _fetch_all(stmt)
        finally:
            ibm_db.free_stmt(stmt)

    def search(self, conn, qvec_text: str, k: int, strategy: Strategy | None = None) -> dict:
        """k nearest rows the session user may see.

        Returns {"rows": [(id, dist)...] (<= k, sorted by (dist, id)), "strategy": Strategy, "fallback": bool,
        "returned_by_approx": int | None, "ms": elapsed SQL ms including a fallback}.
        """
        s = strategy or self.strategy(conn, k)
        t0 = time.perf_counter()
        fallback, n_approx, error = False, None, None
        try:
            res = self._run(conn, self.sql_for(s), qvec_text)
        except Exception as e:  # noqa: BLE001
            # Observed Db2 12.1.5 defect: FETCH APPROX FIRST 99/100 can raise SQL0901N ("Fetched nodes unexpectedly
            # unsorted") for some query vectors. Only that error is retried, and only as EXACT (always correct).
            if s.mode != "APPROX" or "SQL0901N" not in str(e):
                raise
            res, error = [], "SQL0901N"
        if s.mode == "APPROX":
            n_approx = len(res)
            if (n_approx < int(k) and self.cfg.fallback_exact) or error:
                fallback = True
                res = self._run(conn, knn_sql(self.table, int(k), False, self.id_col, self.emb_col, self.dim),
                                qvec_text)
        ms = (time.perf_counter() - t0) * 1000.0
        res.sort(key=lambda r: (r[1], str(r[0])))
        return {"rows": res[: int(k)], "strategy": s, "fallback": fallback, "returned_by_approx": n_approx,
                "error": error, "ms": ms}
