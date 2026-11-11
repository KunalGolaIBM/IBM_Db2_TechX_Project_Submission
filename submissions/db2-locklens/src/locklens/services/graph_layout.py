"""Pure layout for the blocking-relationship graph (no plotting library involved).

Each lock wait becomes ``holder --holds--> resource --requested by--> waiter``. Applications
are placed in columns by chain depth, so a root blocker sits left of the sessions it blocks
and a chain (A blocks B blocks C) reads left to right. Unknown holders are drawn as an
explicit grey "unknown holder" node instead of being guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import LockAnalysis, SessionInfo, Snapshot


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    label: str
    kind: str          # app | resource | unknown
    x: float
    y: float
    hover: str = ""


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    label: str
    kind: str          # holds | waits | uncertain
    emphasis: str = "normal"   # normal | long | cycle


@dataclass
class GraphModel:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


def _app_label(handle: int, sessions: dict[int, SessionInfo]) -> tuple[str, str]:
    info = sessions.get(handle)
    if not info:
        return f"App {handle}", f"Application handle {handle}"
    bits = [b for b in (info.application_name, info.system_auth_id) if b]
    label = f"App {handle}" + (f"<br>{' / '.join(bits)}" if bits else "")
    hover = "<br>".join(x for x in (
        f"Application handle: {handle}",
        f"Application: {info.application_name}" if info.application_name else "",
        f"User: {info.system_auth_id}" if info.system_auth_id else "",
        f"Client host: {info.client_hostname}" if info.client_hostname else "",
        f"State: {info.workload_state}" if info.workload_state else "") if x)
    return label, hover


def build_graph(analysis: LockAnalysis, snapshot: Snapshot, warn_seconds: int = 10) -> GraphModel:
    model = GraphModel()
    if not analysis.edges:
        return model

    rows: dict[float, int] = {}

    def place(column: float) -> float:
        n = rows.get(column, 0)
        rows[column] = n + 1
        return float(-n)

    added: set[str] = set()

    def add_node(node_id: str, label: str, kind: str, column: float, hover: str = "") -> None:
        if node_id in added:
            return
        added.add(node_id)
        model.nodes.append(GraphNode(node_id, label, kind, column * 2.0, place(column), hover))

    resource_ids: dict[tuple, str] = {}
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(edge: GraphEdge) -> None:
        key = (edge.source, edge.target, edge.kind)
        if key not in seen_edges:
            seen_edges.add(key)
            model.edges.append(edge)

    for edge in analysis.edges:
        waiter_depth = analysis.depth.get(edge.waiter, 1) if edge.waiter is not None else 1
        holder_depth = analysis.depth.get(edge.holder, 0) if edge.holder is not None else max(waiter_depth - 1, 0)

        if edge.holder is not None:
            holder_id = f"app:{edge.holder}"
            label, hover = _app_label(edge.holder, snapshot.sessions)
            add_node(holder_id, label, "app", holder_depth, hover)
            holder_kind = "holds"
        else:
            holder_id = f"unknown:{edge.lock_name_hex or id(edge)}"
            hover = {"holder_gone": "Db2 reports the holder no longer exists (rollback or in-doubt).",
                     "ambiguous": "Several applications hold this lock name: "
                                  + ", ".join(map(str, edge.holder_candidates)),
                     }.get(edge.provenance, "Db2 did not report which application holds this lock.")
            add_node(holder_id, "Holder unknown", "unknown", holder_depth, hover)
            holder_kind = "uncertain"

        res_key = (edge.lock_name_hex, edge.holder, edge.resource_label)
        res_id = resource_ids.setdefault(res_key, f"res:{len(resource_ids)}")
        mode = f"<br>held {edge.lock_mode_held}" if edge.lock_mode_held else ""
        add_node(res_id, f"{edge.resource_label}{mode}", "resource", holder_depth + 0.5,
                 f"Lock name: {edge.lock_name_hex or 'n/a'}")

        if edge.waiter is not None:
            waiter_id = f"app:{edge.waiter}"
            label, hover = _app_label(edge.waiter, snapshot.sessions)
            add_node(waiter_id, label, "app", max(waiter_depth, holder_depth + 1), hover)
            wait_txt = f"waits {edge.wait_seconds}s" if edge.wait_seconds is not None else "waiting"
            if edge.lock_mode_requested:
                wait_txt += f" ({edge.lock_mode_requested})"
            emphasis = "cycle" if edge.on_cycle else (
                "long" if (edge.wait_seconds or 0) >= warn_seconds else "normal")
            add_edge(GraphEdge(holder_id, res_id,
                                         "holds" if holder_kind == "holds" else "holder unknown",
                                         holder_kind, "cycle" if edge.on_cycle else "normal"))
            add_edge(GraphEdge(res_id, waiter_id, wait_txt, "waits", emphasis))
    return model
