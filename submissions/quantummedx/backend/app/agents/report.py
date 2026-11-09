"""Report = deterministic sections built from Db2 + a clearly labelled narrative section."""
from app.agents.verify import allowed_numbers, unverified_numbers

LIMITATIONS = (
    "- Research and educational prototype; not a clinically validated diagnostic system and not medical advice.\n"
    "- The quantum classifier runs on a local simulator with few qubits and a small training subset; it is not real quantum hardware.\n"
    "- A single train/test split on one public dataset does not establish that any model, quantum or classical, is better in general.\n"
    "- Feature correlations are descriptive, not causal."
)


def build_report(dataset: dict, quality: dict, patterns: dict, results: list, narrative: str, narrative_source: str) -> tuple:
    ok = allowed_numbers(results, {**{k: v for k, v in quality.items() if isinstance(v, (int, float))}})
    for v in patterns["top_features_by_abs_correlation_with_target"].values():
        ok |= {round(v, 2), round(v, 3)}
    for v in (quality.get("class_distribution") or {}).values():
        ok.add(float(v))
    bad = unverified_numbers(narrative, ok)
    lines = [f"# Research report: {dataset['name']}", "", "## Data quality (computed from the uploaded file)",
             f"- Rows: {quality['rows']}, columns: {quality['columns']}",
             f"- Missing values: {quality['missing_total']}; duplicate rows: {quality['duplicate_rows']}",
             f"- Class distribution: {quality['class_distribution']}", "",
             "## Strongest feature associations with the target (descriptive)"]
    lines += [f"- {k}: |r| = {v}" for k, v in patterns["top_features_by_abs_correlation_with_target"].items()]
    lines += ["", "## Stored experiment results (read from IBM Db2)",
              "| Experiment | Family | Algorithm | Accuracy | Precision | Recall | F1 | ROC-AUC |", "|---|---|---|---|---|---|---|---|"]
    fmt = lambda x: "n/a" if x is None else f"{x:.4f}"
    for r in results:
        lines.append(f"| {r['experiment_id']} | {r['model_family']} | {r['algorithm']} | {fmt(r['accuracy'])} | {fmt(r['precision_score'])} | {fmt(r['recall'])} | {fmt(r['f1_score'])} | {fmt(r['roc_auc'])} |")
    lines += ["", f"## Analysis narrative ({narrative_source})", narrative, "", "## Verification"]
    lines.append("All numbers in the narrative match stored results." if not bad else
                 f"WARNING: these numbers in the narrative could not be matched to stored data and should not be trusted: {', '.join(bad)}")
    lines += ["", "## Limitations", LIMITATIONS]
    return "\n".join(lines), bad


def template_narrative(quality: dict, patterns: dict, results: list) -> str:
    if not results:
        return "No completed experiments were available."
    best = max(results, key=lambda r: r["f1_score"] or 0)
    top = next(iter(patterns["top_features_by_abs_correlation_with_target"]))
    fam = {r["model_family"] for r in results}
    text = (f"The dataset has {quality['rows']} rows and {quality['missing_total']} missing values. "
            f"The feature most associated with the target was {top}. "
            f"By F1 score, the best stored result was {best['algorithm']} ({best['model_family'].lower()}) with F1 {best['f1_score']:.4f}.")
    if fam == {"CLASSICAL", "QUANTUM"}:
        q = [r for r in results if r["model_family"] == "QUANTUM"][0]
        c = max((r for r in results if r["model_family"] == "CLASSICAL"), key=lambda r: r["f1_score"] or 0)
        text += (f" The quantum simulator run scored F1 {q['f1_score']:.4f} versus {c['f1_score']:.4f} for the best classical baseline; "
                 "this single small experiment does not show quantum advantage.")
    return text
