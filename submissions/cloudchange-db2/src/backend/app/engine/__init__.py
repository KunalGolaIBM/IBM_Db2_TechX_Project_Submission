"""Core Analysis Engine for CloudChange.

Contains:
- Plan Parser: Ingests and parses Terraform JSON plans (`terraform show -json`).
- Change Normalizer: Maps raw resource diffs into internal canonical representations.
- Impact Predictor: Evaluates changes against risk and blast-radius heuristics.
"""
