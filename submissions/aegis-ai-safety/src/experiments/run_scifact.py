#!/usr/bin/env python3
"""Canonical SciFact runner alias.

Delegates to the resumable evaluation runner. See experiments/README.md.
"""

from __future__ import annotations

from experiments.run_scifact_eval import main

if __name__ == "__main__":
    raise SystemExit(main())
