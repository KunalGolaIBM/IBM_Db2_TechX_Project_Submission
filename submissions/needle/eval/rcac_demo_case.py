"""Demo case: the same vague triage text as NDL_JUNIOR and as NDL_SENIOR (real, separate Db2 identities).

GHSA-5x8w-8jj5-q52h carries a SYNTHETIC demo embargo flag (sql/04_rcac.sql step 2b). Expected: NDL_JUNIOR never
receives it; NDL_SENIOR does. Output: docs/evidence/rcac_demo_case.txt (written by this script, nothing edited).

Run from needle/:  PYTHONPATH=src .venv\\Scripts\\python eval\\rcac_demo_case.py
"""
import datetime as dt
import io
from pathlib import Path

import ibm_db
import ibm_db_dbi

from needle.sbom import connect_as
from needle.triage import triage

ROOT = Path(__file__).resolve().parents[1]
TEXT = "heap overflow in the image library's FlashPix JPEG decoder can lead to code execution, no CVE yet"
TARGET = "GHSA-5x8w-8jj5-q52h"


def main() -> None:
    out = io.StringIO()
    out.write(f"# RCAC demo case, run {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n")
    out.write(f"# query text: {TEXT!r}\n# target: {TARGET} (synthetic demo embargo flag on a real advisory)\n\n")
    for user in ("NDL_JUNIOR", "NDL_SENIOR"):
        raw = connect_as(user, timeout_s=30)
        try:
            conn = ibm_db_dbi.Connection(raw)
            cur = conn.cursor()
            cur.execute("SELECT SESSION_USER FROM SYSIBM.SYSDUMMY1")
            su = str(cur.fetchone()[0]).strip()
            cur.execute("SELECT COUNT(*) FROM NEEDLE.ADV_DOC WHERE ADV_ID = ?", (TARGET,))
            visible = cur.fetchone()[0]
            cur.close()
            res = triage(TEXT, k=10, depth=100, mode="HYBRID", conn=conn)
            ids = [h.adv_id for h in res.hits]
            rank = ids.index(TARGET) + 1 if TARGET in ids else None
            out.write(f"== {user}  (SESSION_USER={su}; rows with ADV_ID={TARGET} visible to this user: {visible})\n")
            out.write("rank  ADV_ID                     RRF       KW_RANK  VEC_RANK  VEC_DIST\n")
            for i, h in enumerate(res.hits, 1):
                out.write(f"{i:>4}  {h.adv_id:<25}  {h.rrf:.5f}  {str(h.kw_rank):>7}  {str(h.vec_rank):>8}  "
                          f"{'' if h.vec_dist is None else f'{h.vec_dist:.4f}'}\n")
            out.write(f"-> {TARGET} rank for {user}: {rank if rank else 'NOT RETURNED'}\n\n")
        finally:
            ibm_db.close(raw)
    text = out.getvalue()
    (ROOT / "docs" / "evidence" / "rcac_demo_case.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
