"""Db2 Ops Copilot agent: a graph-based DBA diagnosis workflow plus
human-approved maintenance actions.

    question -> analyze_intent -> plan_tools -> collect_evidence <-> reflect
             -> analyze_evidence -> recommend -> propose_actions -> finalize

The diagnosis graph only ever runs READ-ONLY, fixed DBA tools and EXPLAIN.
Anything that changes the database is a *proposal* that waits for an explicit
human decision (``app.services.approval_service``); the agent has no code path
that approves or executes an action.
"""
