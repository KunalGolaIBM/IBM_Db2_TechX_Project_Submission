# ADR 002: AI can only raise risk

Status: accepted.

Seller messages are untrusted and can contain prompt injections. Compute deterministic
and Db2 evidence first. Clamp AI additions to 0..20 in both investigation and orchestration;
ignore model-proposed verdict replacements and negative risk. Hard risk floors survive
trusted contacts, benign retrieval and AI explanations.

This limits the model's ability to cause a false negative. It cannot correct deterministic
false positives by lowering scores; those require an audited rules/data change. Invalid
or unavailable AI returns the rules explanation, and configured-model failures mark the
response degraded. Tests exercise injected ALLOW instructions and negative/oversized risk.
