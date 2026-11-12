---
id: POL-TST-005
title: Automated Test and Code Quality Gate
category: tests
version: 1.0.0
---
# Automated Test and Code Quality Gate

## Rule
All automated unit and integration tests must pass with zero failures before merge.
A failing test suite blocks the pull request. Skipped checks must be reported as
skipped, never as passed.

## Code quality
Bare `except:` clauses hide `KeyboardInterrupt` and `SystemExit` and must be replaced
by specific exception types. Files with syntax errors block the release.
