# Three-minute demo script

Target: **3:00**. Record at 1280×720 or larger. Everything shown is real except
where a line says *offline*.

---

## 0:00–0:20 — Framing

> "India has thousands of welfare schemes. Eligibility is prose inside PDFs.
> People don't know what they qualify for, and the staff who help them can't
> show *why* they said yes.
>
> YojanaLens fixes that by splitting the job: **Db2 decides eligibility, the
> language model only explains it.** Every verdict is stored and replayable."

Show the landing page with the live corpus counters in the header
(`15 schemes · 44 rules · 39 clauses` — read from Db2 at page load).

---

## 0:20–0:35 — The claim, stated as a constraint

> "This is the whole architecture in one sentence: the model never produces a
> verdict. It is handed verdicts that Db2 already computed, and it writes prose
> around them."

Show `architecture.md` → the LangGraph diagram, or the node list in the UI's
"how it works" panel.

---

## 0:35–1:15 — Run the demo household

Click **"Widow, rural UP"** to fill the sample text, then **Check eligibility**.

> "A 34-year-old widow in rural Uttar Pradesh. OBC household, two acres of
> land, kutcha house, ₹1.8 lakh a year, a daughter in class 12, a bank account."

While it runs, point at the pipeline strip: `normalize → persist → retrieve →
Db2 rule matrix → explain → audit`.

When results appear:

> "Six eligible, three **near misses**, one needs information, four not
> eligible, and one Madhya Pradesh scheme filtered out by residency before it
> was ever scored."

Scroll the eligible cards briefly. Do not read them all.

---

## 1:15–1:50 — Open one rule trace (the core of the demo)

Expand **NFSA priority ration card** (a near miss).

> "Here is the difference between an answer and an explanation. Household
> income is ₹1.8 lakh; the priority card threshold is ₹1.5 lakh. One mandatory
> criterion failed, and it is numeric — so this is a *near miss*, not a
> rejection. The system says which door is closed and by how much."

Expand **Post-matric SC/ST scholarship** next.

> "Same shape of failure, different verdict. The category mismatch is
> categorical, so it is *not eligible* — there is nothing to move towards.
> That policy is a small pure function with unit tests, not a vibe."

Point at the clause reference and the quoted source paragraph under the rule
rows.

> "Every criterion carries the clause it came from. The paragraph was fetched
> from the `scheme_chunks` table by `VECTOR_DISTANCE(…, COSINE)` inside Db2."

---

## 1:50–2:20 — The audit record (the part judges should remember)

Open the **audit drawer** for the run.

> "Every criterion of every active scheme — 44 evaluations — was written to
> `decision_trace` by one stored procedure call, inside the same transaction
> as the run. This drawer is reading those rows back: model, prompt version,
> latency, and the event log."

If time allows, show the SQL in `sql/04_procedure.sql`:

> "The comparison is a `CASE` expression in SQL. Python passes a run id and a
> profile id. It never sees a comparison it could get wrong."

---

## 2:20–2:45 — Degradation and honesty

> "Two things that make this demoable anywhere: embeddings run offline in the
> container, and with no API key the narrator is templated from the same rule
> trace. Same verdicts, same citations, zero external calls."

Optionally stop the container and show `GET /api/health` reporting `degraded`
with an actionable message — then restart.

> "And the limitations are written down, not hidden: brute-force vector scan at
> this corpus size, a curated corpus, English-only embeddings."

---

## 2:45–3:00 — Close

> "The vector store finds the paragraph. Only Db2 verifies the rule. The model
> explains, and the trace is the evidence.
>
> YojanaLens — Db2 decides, the model explains."

---

## Pre-record checklist

- [ ] `docker compose up --build` finished; `/api/health` is `ok`
- [ ] corpus counters visible in the header (15 / 44 / 39)
- [ ] sample text loaded, one run already done (warm cache)
- [ ] browser zoom ≥ 110%, no bookmarks bar
- [ ] `docker compose exec app python -m src.cli stats` output ready in a second terminal
- [ ] notifications off; terminal font ≥ 16 pt
- [ ] record the fallback take in mock mode as well, in case the LLM quota is exhausted

## If the live stack is unavailable

Run `python -m pytest tests -q` (54 tests, no database) and show
`test_agent_flow.py` executing the graph end to end with the Db2 layer stubbed.
Say plainly that the container is not running and why. Never narrate a
container that is not there.
