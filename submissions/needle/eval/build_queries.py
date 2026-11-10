"""Build the three FROZEN NEEDLE evaluation query slices from data/docs.jsonl.

Run from the needle/ folder:
    .venv\\Scripts\\python eval\\build_queries.py --slices named,masked,paraphrase
    .venv\\Scripts\\python eval\\build_queries.py --verify          (check the .sha256 files)

Slices (one JSON object per line in eval/queries/<slice>.jsonl, plus <slice>.sha256 and
<slice>.manifest.json):
  named       The advisory summary exactly as written. Kept only when the summary contains an
              affected package name (or an obvious variant, see package_variants()).
  masked      Summary + the first part of the cleaned details, with every affected package
              name and its obvious variants replaced by "a popular library", and all
              CVE/GHSA/PYSEC/OSV/MAL ids and URLs removed.
  paraphrase  SYNTHETIC. A vague chat-style rewrite of the masked text, generated locally by
              Ollama qwen3:4b-instruct-2507-q4_K_M (temperature 0, fixed seed). Dropped when it
              names a package/variant, contains an advisory id, or shares a run of >= 6
              consecutive words with the source advisory text (leak_reason()).

Sampling: candidate vulnerabilities = canon_id groups of NON-withdrawn records that contain at
least one non-withdrawn PYSEC or GHSA record (MAL records stay in the corpus as distractors but
never seed a query). The sorted canon_id list is shuffled once with SEED; every slice walks the
same shuffled order and takes the first PER_SLICE eligible groups, so slices overlap heavily but
not completely. Within a group the source record is the first eligible one in the order
GHSA before PYSEC, then adv_id.

Ground truth (gt): every NON-withdrawn adv_id with the query's canon_id (withdrawn records are
not loaded into NEEDLE.ADV_DOC). PYSEC and GHSA duplicates of one vulnerability are all correct.
Known leakage: the source record itself is in the corpus, so named/masked queries are text
copied from a relevant document (named = verbatim summary, masked = verbatim minus names/ids).
Only the paraphrase slice is free of verbatim overlap (enforced by the 6-word-run filter).

Freezing: an existing <slice>.jsonl is NEVER overwritten unless --force is given, and --force
prints the old and new sha256. run_eval.py refuses to run when a file does not match its .sha256.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # needle/
DOCS = ROOT / "data" / "docs.jsonl"
QDIR = ROOT / "eval" / "queries"

SEED = 20261109
PER_SLICE = 150
MASK = "a popular library"
QUERY_KINDS = ("GHSA", "PYSEC")  # preference order for the source record
DETAILS_MAX_CHARS = 500
PARAPHRASE_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
PARAPHRASE_MAX_ATTEMPTS = 400
LEAK_RUN = 6  # a paraphrase sharing >= this many consecutive words with the source is dropped

ID_RE = re.compile(
    r"\b(?:CVE-\d{4}-\d{3,}|GHSA(?:-[0-9a-z]{4}){3}|PYSEC-\d{4}-\d+|OSV-\d{4}-\d+|MAL-\d{4}-\d+)\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MDLINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
FENCE_RE = re.compile(r"```.*?(?:```|$)", re.DOTALL)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
WORD_RE = re.compile(r"[a-z0-9]+")
_SEP = r"[\s._\-]?"  # optional single separator allowed between characters of a name


# ----------------------------------------------------------------------------------------------
# Package-name variants and masking (pure functions, unit-tested in tests/test_eval_queries.py)
# ----------------------------------------------------------------------------------------------
def _parts(name: str) -> list[str]:
    return [p for p in re.split(r"[^a-z0-9]+", name.lower()) if p]


def package_variants(pkg: str) -> list[str]:
    """Obvious textual variants of a PyPI package name, as lowercase alnum strings.

    full name (separators removed); multi-part prefixes with >= 2 parts (apache-airflow from
    apache-airflow-providers-x); python-/py- prefix and -python/-py suffix stripped; a bare
    'py' prefix stripped when >= 4 characters remain (pyyaml -> yaml); a trailing version digit
    stripped when >= 4 letters remain (jinja2 -> jinja). Matching is case-insensitive and
    tolerates one separator (space . _ -) between any two characters, so 'open-webui' also
    masks 'Open WebUI' and 'open_webui'. Variants shorter than 3 characters are dropped,
    except the full name itself (>= 2 characters).
    """
    parts = _parts(pkg)
    if not parts:
        return []
    full = "".join(parts)
    out: set[str] = {full}
    for i in range(2, len(parts)):
        out.add("".join(parts[:i]))
    if len(parts) >= 2 and parts[0] in ("python", "py", "python3"):
        out.add("".join(parts[1:]))
    if len(parts) >= 2 and parts[-1] in ("python", "py", "python3", "py3"):
        out.add("".join(parts[:-1]))
    if len(parts) == 1 and parts[0].startswith("py") and len(parts[0]) - 2 >= 4:
        out.add(parts[0][2:])
    m = re.match(r"^(.*[a-z])\d+$", full)
    if m and len(m.group(1)) >= 4:
        out.add(m.group(1))
    return sorted(v for v in out if len(v) >= 3 or (v == full and len(v) >= 2))


def name_regex(packages: list[str]) -> re.Pattern | None:
    """One case-insensitive regex matching any variant of any package, longest first."""
    variants: set[str] = set()
    for p in packages or []:
        variants.update(package_variants(p))
    if not variants:
        return None
    alts = [_SEP.join(re.escape(ch) for ch in v) for v in sorted(variants, key=lambda s: (-len(s), s))]
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])", re.IGNORECASE)


def contains_package(text: str, packages: list[str]) -> bool:
    rx = name_regex(packages)
    return bool(text and rx and rx.search(text))


def clean_text(text: str | None) -> str:
    """Drop fenced code, markdown link targets, URLs and heading markers; collapse whitespace."""
    if not text:
        return ""
    t = FENCE_RE.sub(" ", text)
    t = MDLINK_RE.sub(r"\1", t)
    t = URL_RE.sub(" ", t)
    t = HEADING_RE.sub("", t)
    t = t.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", t).strip()


def first_part(text: str, max_chars: int = DETAILS_MAX_CHARS) -> str:
    """First max_chars of text, cut back to a sentence end (or a word end)."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(". "), cut.rfind(".\n"))
    if end >= max_chars // 3:
        return cut[: end + 1]
    sp = cut.rfind(" ")
    return cut[: sp if sp > 0 else max_chars]


def mask_text(text: str, packages: list[str], extra_ids: list[str] | None = None) -> tuple[str, int]:
    """Return (masked text, number of package-name replacements)."""
    t = URL_RE.sub(" ", text or "")
    for a in extra_ids or []:
        if a:
            t = re.sub(re.escape(a), " ", t, flags=re.IGNORECASE)
    t = ID_RE.sub(" ", t)
    n = 0
    rx = name_regex(packages)
    if rx:
        t, n = rx.subn(MASK, t)
    t = re.sub(r"\(\s*[,;/]?\s*\)", " ", t)  # "( )" left behind by removed ids
    t = re.sub(rf"{MASK}(?:[\s,/]+(?:and\s+|or\s+)?{MASK})+", MASK, t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    return t, n


def masked_query(doc: dict) -> tuple[str, int]:
    summary = clean_text(doc.get("summary"))
    details = first_part(clean_text(doc.get("details")))
    if summary and details.lower().startswith(summary.lower()):
        details = details[len(summary):].lstrip(" .:-")
    src = summary if not details else (f"{summary}. {details}" if summary else details)
    src = re.sub(r"\.\.\s", ". ", src)
    return mask_text(src, doc.get("packages") or [], doc.get("aliases") or [])


def words(text: str) -> list[str]:
    return WORD_RE.findall((text or "").lower())


def longest_shared_run(a: str, b: str) -> int:
    """Length of the longest run of consecutive words that occurs in both a and b."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0
    # dynamic programming over word positions (texts are short: <= a few hundred words)
    best = 0
    prev = [0] * (len(wb) + 1)
    for i in range(1, len(wa) + 1):
        cur = [0] * (len(wb) + 1)
        ai = wa[i - 1]
        for j in range(1, len(wb) + 1):
            if ai == wb[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def leak_reason(paraphrase: str, packages: list[str], sources: list[str], run: int = LEAK_RUN) -> str | None:
    """Why a paraphrase must be dropped, or None when it is acceptable."""
    p = (paraphrase or "").strip()
    if len(p) < 20:
        return "too_short"
    if len(p) > 700:
        return "too_long"
    if contains_package(p, packages):
        return "names_package"
    if ID_RE.search(p):
        return "contains_advisory_id"
    if URL_RE.search(p):
        return "contains_url"
    for s in sources:
        if longest_shared_run(p, s) >= run:
            return f"shares_{run}_word_run"
    return None


# ----------------------------------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------------------------------
def load_docs(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def candidate_groups(docs: list[dict]) -> tuple[list[str], dict[str, list[str]], dict[str, list[dict]]]:
    """(shuffled canon ids, gt adv_ids per canon, source-candidate docs per canon)."""
    gt: dict[str, list[str]] = {}
    src: dict[str, list[dict]] = {}
    for d in docs:
        if d.get("withdrawn"):
            continue
        gt.setdefault(d["canon_id"], []).append(d["adv_id"])
        if d["kind"] in QUERY_KINDS:
            src.setdefault(d["canon_id"], []).append(d)
    for c in src:
        src[c].sort(key=lambda d: (QUERY_KINDS.index(d["kind"]), d["adv_id"]))
    order = sorted(src)
    random.Random(SEED).shuffle(order)
    return order, {c: sorted(v) for c, v in gt.items()}, src


def build_named(order, gt, src, n):
    out, stats = [], {"groups_scanned": 0, "no_summary": 0, "summary_lacks_package": 0}
    for c in order:
        if len(out) >= n:
            break
        stats["groups_scanned"] += 1
        chosen = None
        for d in src[c]:
            s = (d.get("summary") or "").strip()
            if len(s) < 15:
                continue
            if contains_package(s, d.get("packages") or []):
                chosen = (d, s)
                break
        if chosen is None:
            if any((d.get("summary") or "").strip() for d in src[c]):
                stats["summary_lacks_package"] += 1
            else:
                stats["no_summary"] += 1
            continue
        d, s = chosen
        out.append(_rec("named", d, s, gt, synthetic=False))
    return out, stats


def build_masked(order, gt, src, n):
    out, stats = [], {"groups_scanned": 0, "no_packages": 0, "too_short": 0, "residual_name": 0}
    for c in order:
        if len(out) >= n:
            break
        stats["groups_scanned"] += 1
        chosen = None
        for d in src[c]:
            pk = d.get("packages") or []
            if not pk:
                stats["no_packages"] += 1
                continue
            q, nrep = masked_query(d)
            if len(q) < 60:
                stats["too_short"] += 1
                continue
            if contains_package(q, pk):
                stats["residual_name"] += 1
                continue
            chosen = (d, q, nrep)
            break
        if chosen is None:
            continue
        d, q, nrep = chosen
        r = _rec("masked", d, q, gt, synthetic=False)
        r["mask_replacements"] = nrep
        out.append(r)
    return out, stats


PARA_SYSTEM = (
    "You rewrite software security advisories into short, vague chat messages, the way a "
    "developer would type them to a teammate when they are not sure what is going on."
)
PARA_USER = (
    "Rewrite the advisory below as a chat message of 1 to 3 sentences (at most 50 words) from a "
    "developer who noticed something worrying and asks whether it is a known vulnerability.\n"
    "Rules: do not name any library, package, product, project, vendor, file or function. "
    "No version numbers, no CVE or GHSA ids, no URLs, no code. Describe the behaviour or the "
    "attack in everyday words. Do not copy phrases from the advisory. Output only the message.\n\n"
    "Advisory:\n{text}"
)


def ollama_digest(url: str, model: str) -> str | None:
    import requests

    r = requests.get(f"{url}/api/tags", timeout=30)
    r.raise_for_status()
    for m in r.json().get("models", []):
        if m.get("name") == model or m.get("model") == model:
            return m.get("digest")
    return None


def generate_paraphrase(session, url: str, text: str) -> str:
    body = {
        "model": PARAPHRASE_MODEL,
        "messages": [
            {"role": "system", "content": PARA_SYSTEM},
            {"role": "user", "content": PARA_USER.format(text=text)},
        ],
        "stream": False,
        "options": {"temperature": 0, "seed": SEED, "num_predict": 160},
    }
    r = session.post(f"{url}/api/chat", json=body, timeout=300)
    r.raise_for_status()
    out = r.json()["message"]["content"]
    out = re.sub(r"<think>.*?</think>", " ", out, flags=re.DOTALL)
    return re.sub(r"\s+", " ", out).strip().strip('"').strip()


def build_paraphrase(order, gt, src, n, url):
    import requests

    out, drops = [], []
    stats = {"groups_scanned": 0, "attempts": 0, "accepted": 0, "dropped": {}}
    with requests.Session() as s:
        for c in order:
            if len(out) >= n or stats["attempts"] >= PARAPHRASE_MAX_ATTEMPTS:
                break
            stats["groups_scanned"] += 1
            d = next((x for x in src[c] if x.get("packages")), None)
            if d is None:
                continue
            masked, _ = masked_query(d)
            if len(masked) < 60 or contains_package(masked, d["packages"]):
                continue
            stats["attempts"] += 1
            para = generate_paraphrase(s, url, masked)
            sources = [(d.get("summary") or "") + "\n" + (d.get("details") or ""), masked]
            why = leak_reason(para, d["packages"], sources)
            if why:
                stats["dropped"][why] = stats["dropped"].get(why, 0) + 1
                drops.append({"source_adv_id": d["adv_id"], "reason": why, "text": para})
                continue
            r = _rec("paraphrase", d, para, gt, synthetic=True)
            r["longest_shared_run"] = max(longest_shared_run(para, x) for x in sources)
            out.append(r)
            stats["accepted"] += 1
            if stats["attempts"] % 25 == 0:
                print(f"  paraphrase attempts={stats['attempts']} accepted={len(out)}", flush=True)
    return out, stats, drops


def _rec(slice_name: str, d: dict, text: str, gt: dict, synthetic: bool) -> dict:
    return {
        "qid": f"{slice_name}:{d['adv_id']}",
        "slice": slice_name,
        "query": text,
        "source_adv_id": d["adv_id"],
        "canon_id": d["canon_id"],
        "gt": gt[d["canon_id"]],
        "packages": d.get("packages") or [],
        "row_bucket": d.get("row_bucket"),
        "synthetic": synthetic,
    }


# ----------------------------------------------------------------------------------------------
# Writing / verification
# ----------------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_slice(name: str, recs: list[dict], manifest: dict, force: bool) -> str:
    path = QDIR / f"{name}.jsonl"
    old = sha256_file(path) if path.exists() else None
    if old and not force:
        raise SystemExit(f"REFUSED: {path} exists (sha256 {old}). Frozen sets are never regenerated "
                         f"silently; pass --force to rebuild and report the change.")
    QDIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    digest = sha256_file(path)
    (QDIR / f"{name}.sha256").write_text(f"{digest}  {name}.jsonl\n", encoding="utf-8", newline="\n")
    manifest = dict(manifest, slice=name, count=len(recs), sha256=digest, replaced_sha256=old)
    (QDIR / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    if old and old != digest:
        print(f"WARNING: {name}.jsonl REPLACED: old sha256 {old} -> new {digest}")
    return digest


def verify(names: list[str]) -> int:
    bad = 0
    for name in names:
        p, s = QDIR / f"{name}.jsonl", QDIR / f"{name}.sha256"
        if not p.exists() or not s.exists():
            print(f"{name}: MISSING")
            bad += 1
            continue
        want = s.read_text(encoding="utf-8").split()[0]
        got = sha256_file(p)
        n = sum(1 for _ in open(p, encoding="utf-8"))
        print(f"{name}: {'OK' if want == got else 'MISMATCH'} n={n} sha256={got}")
        bad += want != got
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slices", default="named,masked,paraphrase")
    ap.add_argument("--n", type=int, default=PER_SLICE)
    ap.add_argument("--docs", default=str(DOCS))
    ap.add_argument("--force", action="store_true", help="overwrite an existing frozen slice (prints old/new sha256)")
    ap.add_argument("--verify", action="store_true", help="only check the .sha256 files")
    args = ap.parse_args()
    names = [s.strip() for s in args.slices.split(",") if s.strip()]
    if args.verify:
        return verify(names)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    docs_path = Path(args.docs)
    t0 = time.time()
    docs = load_docs(docs_path)
    order, gt, src = candidate_groups(docs)
    base = {
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "seed": SEED,
        "per_slice_target": args.n,
        "docs_path": docs_path.name,
        "docs_sha256": sha256_file(docs_path),
        "docs_records": len(docs),
        "candidate_groups": len(order),
        "query_kinds": list(QUERY_KINDS),
        "ground_truth": "all non-withdrawn adv_ids sharing the query's canon_id",
        "mask_token": MASK,
        "details_max_chars": DETAILS_MAX_CHARS,
    }
    print(f"docs={len(docs)} candidate canon groups={len(order)} ({time.time()-t0:.1f}s)")
    for name in names:
        if name == "named":
            recs, stats = build_named(order, gt, src, args.n)
            extra = {"stats": stats, "synthetic": False}
        elif name == "masked":
            recs, stats = build_masked(order, gt, src, args.n)
            extra = {"stats": stats, "synthetic": False}
        elif name == "paraphrase":
            if (QDIR / "paraphrase.jsonl").exists() and not args.force:
                raise SystemExit("REFUSED: paraphrase.jsonl exists; pass --force to rebuild.")
            recs, stats, drops = build_paraphrase(order, gt, src, args.n, url)
            extra = {
                "stats": stats, "synthetic": True, "model": PARAPHRASE_MODEL,
                "model_digest": ollama_digest(url, PARAPHRASE_MODEL),
                "options": {"temperature": 0, "seed": SEED, "num_predict": 160},
                "system_prompt": PARA_SYSTEM, "user_prompt": PARA_USER,
                "leak_filter": f"drop if names a package variant, contains an advisory id or URL, "
                               f"or shares >= {LEAK_RUN} consecutive words with summary+details "
                               f"or with the masked input",
            }
            with open(QDIR / "paraphrase.dropped.jsonl", "w", encoding="utf-8", newline="\n") as f:
                for x in drops:
                    f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
        else:
            raise SystemExit(f"unknown slice {name}")
        digest = write_slice(name, recs, dict(base, **extra), args.force)
        print(f"{name}: n={len(recs)} sha256={digest} stats={json.dumps(stats)}", flush=True)
    print(f"elapsed {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
