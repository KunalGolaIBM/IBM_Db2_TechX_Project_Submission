# README "AI / LLM Architecture" snippet, run against the live Db2 (2026-11-10 07:26:40 UTC)
# Host: Windows, needle/.venv (Python 3.13.2, ibm_db 3.3.0, langchain-core 1.7.6, haystack-ai 3.4.1).
# Db2 12.1.5.0 in the Codespace through the tunnel on localhost:50000; Ollama local (nomic-embed-text, qwen3:14b).
# Identity: NDL_JUNIOR. Passwords come from needle/.env through connect_as() / password_for(); none is printed.
# The service fleet is synthetic. The memo text differs between runs (random prompt nonce); the SQL rows do not.
$ cd needle; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe readme_snippet.py
# exit code 0, 30.1 s wall clock (embedding, TRIAGE, exposure join, memo, Haystack pipeline)

## readme_snippet.py (identical to the README code block)
import ibm_db
from haystack import Pipeline
from needle.haystack_component import NeedleTriageComponent
from needle.llm_summary import evidence_for, generate_memo
from needle.retriever import Db2HybridRetriever
from needle.sbom import connect_as, fetch_exposure, password_for
from needle.triage import connect
from needle.verify import verify_memo

q = "the yaml loader everyone uses runs python code from a crafted file"
conn = connect_as("NDL_JUNIOR")                                   # password from .env; RCAC applies to this user
docs = Db2HybridRetriever(conn=conn, authid="NDL_JUNIOR", k=8).invoke(q)  # NEEDLE.TRIAGE; the router picks the depth
rows = fetch_exposure(conn, [d.metadata["adv_id"] for d in docs])       # exact SBOM join on the same connection
memo = generate_memo(docs, rows)                                  # ChatOllama(LLM_MODEL) writes the memo
checked = verify_memo(memo.raw, evidence_for(docs, rows))         # deterministic check (generate_memo also runs it)
print(memo.model, [d.metadata["adv_id"] for d in docs], len(rows), checked.kept, checked.removed, checked.text, sep="\n")
ibm_db.close(conn)

p = Pipeline(); p.add_component("triage", NeedleTriageComponent(lambda: connect("NDL_JUNIOR", password_for("NDL_JUNIOR")), top_k=5))
print([d.meta["adv_id"] for d in p.run({"triage": {"query": q}})["triage"]["documents"]])

## Output (verbatim). Lines: model; retrieved ADV_IDs (k = 8); exposure rows; sentences kept; sentences removed with reasons; verified memo; Haystack top 5.
﻿qwen3:14b
['GHSA-v5f6-hjmf-9mc5', 'PYSEC-2023-223', 'GHSA-rpj2-4hq8-938g', 'PYSEC-2020-96', 'GHSA-8278-88vv-x98r', 'GHSA-fm6c-f59h-7mmg', 'PYSEC-2021-142', 'PYSEC-2026-1683']
18
4
[Removed(text='NOT_CONFIRMED services (ci-artifact-scanner, docs-renderer, etc.) use pyyaml 5.4.1 or 6.0.1, potentially exposed to [PYSEC-2020-96] and [PYSEC-2021-142], which permit arbitrary code execution through unsafe YAML processing.', reasons=['says ci-artifact-scanner is AFFECTED but its SQL status is NOT_CONFIRMED/PREVIOUSLY_AFFECTED', 'says docs-renderer is AFFECTED but its SQL status is NOT_CONFIRMED/PREVIOUSLY_AFFECTED']), Removed(text='PREVIOUSLY_AFFECTED services (ci-artifact-scanner, docs-renderer, etc.) had pyyaml versions exposed for up to 919 days to [PYSEC-2020-96] and [PYSEC-2021-142], allowing arbitrary code execution via unsafe YAML deserialization.', reasons=['says ci-artifact-scanner is AFFECTED but its SQL status is NOT_CONFIRMED/PREVIOUSLY_AFFECTED', 'says docs-renderer is AFFECTED but its SQL status is NOT_CONFIRMED/PREVIOUSLY_AFFECTED', 'states 919 days but the SQL day count is 179 days, 383 days'])]
- AFFECTED legacy-reporting (pyyaml 5.1) has been exposed for 2448 days to vulnerabilities [PYSEC-2020-96] and [PYSEC-2021-142], allowing arbitrary code execution via unsafe YAML deserialization.
- Vulnerabilities [PYSEC-2020-96] and [PYSEC-2021-142] involve arbitrary code execution through unsafe YAML deserialization in pyyaml versions before 5.3.1 and 5.4, respectively.
- Advisory [PYSEC-2023-223] affects transmute-core before 1.13.5, allowing arbitrary Python code execution via unsafe YAML deserialization.
- Advisory [GHSA-rpj2-4hq8-938g] affects vcrpy, enabling arbitrary code execution via unsafe YAML deserialization of cassette files.
['GHSA-v5f6-hjmf-9mc5', 'PYSEC-2023-223', 'GHSA-rpj2-4hq8-938g', 'PYSEC-2020-96', 'GHSA-8278-88vv-x98r']
