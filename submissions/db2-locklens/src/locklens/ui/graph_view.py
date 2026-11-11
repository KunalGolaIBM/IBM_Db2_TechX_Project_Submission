"""Plotly rendering of the blocking-relationship graph (layout comes from services.graph_layout)."""

from __future__ import annotations

import plotly.graph_objects as go

from ..services.graph_layout import GraphModel

_NODE_COLOR = {"app": "#0f62fe", "resource": "#8a3ffc", "unknown": "#6f6f6f"}
_EDGE_COLOR = {"cycle": "#da1e28", "long": "#ff832b", "normal": "#8d8d8d"}


def build_figure(model: GraphModel) -> go.Figure:
    fig = go.Figure()
    pos = {n.node_id: (n.x, n.y) for n in model.nodes}
    for e in model.edges:
        if e.source not in pos or e.target not in pos:
            continue
        (x0, y0), (x1, y1) = pos[e.source], pos[e.target]
        color = _EDGE_COLOR.get(e.emphasis, _EDGE_COLOR["normal"])
        if e.kind == "uncertain":
            color = _EDGE_COLOR["normal"]
        fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=3, arrowsize=1.2, arrowwidth=2.2,
                           arrowcolor=color, standoff=22, startstandoff=22, text="")
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2 + 0.22, text=e.label, showarrow=False,
                           font=dict(size=11, color=color))
    for kind, name in (("app", "Application"), ("resource", "Locked resource"),
                       ("unknown", "Holder unknown")):
        nodes = [n for n in model.nodes if n.kind == kind]
        if not nodes:
            continue
        fig.add_trace(go.Scatter(
            x=[n.x for n in nodes], y=[n.y for n in nodes], mode="markers+text", name=name,
            text=[n.label for n in nodes], textposition="bottom center",
            hovertext=[n.hover or n.label for n in nodes], hoverinfo="text",
            marker=dict(size=34, color=_NODE_COLOR[kind],
                        symbol="square" if kind == "resource" else "circle",
                        line=dict(width=2, color="white"))))
    rows = max(1, len({n.y for n in model.nodes}))
    fig.update_xaxes(visible=False, fixedrange=True, range=[-1, max([n.x for n in model.nodes] or [2]) + 1])
    fig.update_yaxes(visible=False, fixedrange=True,
                     range=[min([n.y for n in model.nodes] or [0]) - 1.2, 1.0])
    fig.update_layout(height=max(320, 140 * rows + 120), margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=-0.05), showlegend=True)
    return fig
