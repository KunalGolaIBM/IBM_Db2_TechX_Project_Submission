"""Explain one audit verdict in plain language. "AI explains, code computes and verifies":
- the verdict and evidence come from Db2 (COMPUTE_AQI_AUDITED); the LLM never changes them;
- the rule paragraphs come from Db2 vector search, cross-checked against the rule the procedure cited;
- every number in the LLM text must appear in the evidence, otherwise a template explanation is stored."""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from db import connect, rows
from llm import generate, MODEL
from rules import nearest_rules

SYSTEM = ("You explain air-quality audit results to ordinary Delhi residents. Use only the facts given. "
          "Write exactly 2 short sentences: first the verdict and the main reason, then how it compares with the naive dashboard number. "
          "Never invent numbers, never predict air quality, never give health or safety advice.")
# Words that signal advice, prediction or judgement the audit cannot support.
BANNED = re.compile(r"\b(should|advise|advice|safe|unsafe|danger\w*|health\w*|symptom\w*|discomfort|mask|stay indoors|will be|tomorrow|forecast|fraud|manipulat\w*)\b", re.I)

def category(aqi):
    if aqi is None: return "none"
    for hi, name in ((50, "Good"), (100, "Satisfactory"), (200, "Moderate"), (300, "Poor"), (400, "Very Poor")):
        if aqi <= hi: return name
    return "Severe"

def facts_for(conn, run_id):
    v = rows(conn, """SELECT V.STATION_ID, S.NAME, V.DAY, V.STATUS, V.AQI, V.NAIVE_AQI, V.PROMINENT, V.REASON
                        FROM AQ.VERDICT V JOIN AQ.STATION S ON S.STATION_ID = V.STATION_ID WHERE V.RUN_ID = ?""", (run_id,))[0]
    ev = rows(conn, """SELECT PARAM, CHECK_CODE, OBSERVED, RULE_REF FROM AQ.EVIDENCE
                        WHERE RUN_ID = ? AND PASSED = 0 ORDER BY CHECK_CODE, PARAM""", (run_id,))
    return v, ev

def numbers(text):
    return {n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", text)}

def template(v, ev):
    sid, name, day, status, aqi, naive, prom, reason = v
    if status == "NOT_COMPUTABLE":
        s = f"No AQI can be calculated for {name} on {day}: {reason}."
        if naive is not None: s += f" A dashboard that averages whatever arrived would still show {naive}."
    else:
        s = f"The audited AQI for {name} on {day} is {aqi} (driven by {prom})."
        if naive is not None and naive != aqi: s += f" A plain average of all values gives {naive}."
    return s

def explain(conn, run_id, use_llm=True, store=True):
    v, ev = facts_for(conn, run_id)
    sid, name, day, status, aqi, naive, prom, reason = v
    cited = sorted({e[3] for e in ev}) or ["CPCB-BREAKPOINTS"]
    # Vector search over rule texts, run inside Db2, must agree with what the procedure cited.
    query = reason + " " + " ".join(e[2] for e in ev[:4])
    near = nearest_rules(conn, query, k=3)
    agrees = int(any(r[0] in cited for r in near))
    rule_text = "\n".join(f"[{r[0]}] {r[1]}" for r in near if r[0] in cited) or \
                "\n".join(f"[{r[0]}] {r[1]}" for r in rows(conn, "SELECT RULE_REF, BODY FROM AQ.RULE_TEXT WHERE RULE_REF = ?", (cited[0],)))
    facts = (f"Station: {name}\nDay: {day:%d %B %Y} ({day})\nVerdict: {status}\nAudited AQI: {aqi if aqi is not None else 'none'}\n"
             f"CPCB category of audited AQI: {category(aqi)}\nNaive dashboard AQI: {naive if naive is not None else 'none'} ({category(naive)})\nReason: {reason}\n"
             "Failed checks:\n" + "\n".join(f"- {e[0]} {e[1]}: {e[2]}" for e in ev[:12]) + f"\nRules:\n{rule_text}")
    text, grounded, model = template(v, ev), 1, "template"
    if use_llm:
        out = generate(f"FACTS:\n{facts}\n\nExplain this verdict.", system=SYSTEM)
        allowed = numbers(facts) | {"2.5", "24", "8", "16", "3"}
        bad_words = BANNED.findall(out or "")
        wrong_cat = [c for c in ("Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe")
                     if re.search(rf"\b{c}\b", out or "") and c not in (category(aqi), category(naive)) and not (c == "Poor" and "Very Poor" in (category(aqi), category(naive)))]
        if out and numbers(out) <= allowed and not bad_words and not wrong_cat:
            text, grounded, model = out, 1, MODEL
        else:
            model = f"template (LLM rejected: {sorted(numbers(out) - allowed)[:3]}{bad_words[:2]}{wrong_cat[:2]})"
            print("REJECTED LLM TEXT:", out, file=sys.stderr)
    if not store:   # a stand-in shown while the model is busy; not written to the ledger
        return dict(run_id=run_id, text=text, model=model, cited=cited, vector_top=[r[0] for r in near], vector_agrees=bool(agrees))
    cur = conn.cursor()
    cur.execute("INSERT INTO AQ.EXPLANATION (RUN_ID, MODEL, TEXT, GROUNDED, RULE_REFS, VECTOR_AGREES) VALUES (?,?,?,?,?,?)",
                (run_id, model[:60], text[:2000], grounded, ",".join(cited)[:200], agrees))
    conn.commit()
    return dict(run_id=run_id, text=text, model=model, cited=cited, vector_top=[r[0] for r in near], vector_agrees=bool(agrees))

if __name__ == "__main__":
    c = connect()
    for rid in sys.argv[1:]:
        print(explain(c, int(rid)))
