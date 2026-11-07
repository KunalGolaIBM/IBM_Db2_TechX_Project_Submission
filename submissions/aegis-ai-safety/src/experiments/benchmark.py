#!/usr/bin/env python3
"""SciFact benchmark entry point.

This is the canonical benchmark command; `evaluate.py` remains available as an
alias. It computes metrics only from files supplied at runtime and never invents
scores.
"""

from __future__ import annotations

from experiments.evaluate import main

if __name__ == "__main__":
    raise SystemExit(main())
