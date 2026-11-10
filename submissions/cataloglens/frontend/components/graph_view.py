"""
Plotly Relationship Graph Visualizer.
Renders an interactive force-directed graph distinguishing
Declared (verified facts) from Inferred (hypotheses) relationships.
"""
from typing import Any, Dict, List
import networkx as nx
import plotly.graph_objects as go


def render_relationship_graph(
    tables: Dict[str, Any],
    views: Dict[str, Any],
    relationships: List[Dict[str, Any]],
    filter_mode: str = "ALL",  # "ALL", "DECLARED_ONLY", "INFERRED_ONLY"
    highlight_table: str = None,
) -> go.Figure:
    """Builds an interactive Plotly figure representing the database topology."""
    G = nx.DiGraph()

    # 1. Add table and view nodes
    for tname, tobj in tables.items():
        card = tobj.get("card", 0)
        col_count = len(tobj.get("columns", []))
        pks = tobj.get("primary_keys", [])
        node_role = "Master Dimension" if tname.endswith("_MST") else ("Header" if tname.endswith("_HDR") else "Table")
        G.add_node(
            tname,
            type="TABLE",
            role=node_role,
            card=card,
            col_count=col_count,
            pks=", ".join(pks),
        )

    for vname, vobj in views.items():
        col_count = len(vobj.get("columns", []))
        G.add_node(
            vname,
            type="VIEW",
            role="Reporting View",
            card=vobj.get("card", 0),
            col_count=col_count,
            pks="None (View)",
        )

    # 2. Add edges with filtering
    for r in relationships:
        r_type = r.get("relationship_type", "DECLARED")
        if filter_mode == "DECLARED_ONLY" and r_type != "DECLARED":
            continue
        if filter_mode == "INFERRED_ONLY" and r_type != "INFERRED":
            continue

        src = r.get("source_table")
        tgt = r.get("target_table")
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(
                src,
                tgt,
                rel_type=r_type,
                confidence=r.get("confidence", 1.0),
                src_col=r.get("source_column"),
                tgt_col=r.get("target_column"),
                reason=r.get("reason", ""),
            )

    # 3. Compute layout coordinates
    pos = nx.spring_layout(G, k=1.8, iterations=70, seed=42)

    # 4. Construct edge traces (Separate for Declared vs Inferred)
    declared_x, declared_y = [], []
    inferred_x, inferred_y = [], []

    edge_trace_declared = go.Scatter(
        x=[],
        y=[],
        line=dict(width=2.2, color="#0062FF"),  # IBM Tech Blue
        hoverinfo="text",
        text=[],
        mode="lines",
        name="Declared (SYSCAT.REFERENCES)",
    )

    edge_trace_inferred = go.Scatter(
        x=[],
        y=[],
        line=dict(width=2.0, color="#FF832B", dash="dot"),  # Orange dotted
        hoverinfo="text",
        text=[],
        mode="lines",
        name="Inferred (Candidate Hypothesis)",
    )

    decl_hover_text = []
    inf_hover_text = []

    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        r_type = data.get("rel_type")
        conf = data.get("confidence", 1.0)
        src_c = data.get("src_col")
        tgt_c = data.get("tgt_col")
        lbl = f"<b>{u}.{src_c}</b> &rarr; <b>{v}.{tgt_c}</b><br>Type: {r_type} ({conf*100:.0f}%)<br>{data.get('reason', '')}"

        if r_type == "DECLARED":
            declared_x.extend([x0, x1, None])
            declared_y.extend([y0, y1, None])
            decl_hover_text.extend([lbl, lbl, ""])
        else:
            inferred_x.extend([x0, x1, None])
            inferred_y.extend([y0, y1, None])
            inf_hover_text.extend([lbl, lbl, ""])

    edge_trace_declared.x = declared_x
    edge_trace_declared.y = declared_y
    edge_trace_declared.text = decl_hover_text

    edge_trace_inferred.x = inferred_x
    edge_trace_inferred.y = inferred_y
    edge_trace_inferred.text = inf_hover_text

    # 5. Construct node traces
    node_x, node_y, node_colors, node_sizes, node_text, node_labels = [], [], [], [], [], []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_data = G.nodes[node]
        node_type = node_data.get("type", "TABLE")
        role = node_data.get("role", "Table")
        deg = G.degree(node)

        # Color coding
        if highlight_table and node == highlight_table:
            color = "#F1C21B"  # Yellow highlight
            size = 32
        elif node_type == "VIEW":
            color = "#8A3FFC"  # IBM Purple
            size = 20
        elif role == "Master Dimension":
            color = "#198038"  # Green
            size = 22 + (deg * 2)
        elif role == "Header":
            color = "#0F62FE"  # Primary Blue
            size = 24 + (deg * 2)
        else:
            color = "#0043CE"  # Slate Blue
            size = 18 + (deg * 2)

        node_colors.append(color)
        node_sizes.append(size)
        node_labels.append(node)

        hover_info = (
            f"<b>{node}</b> ({node_type})<br>"
            f"Role: {role}<br>"
            f"Columns: {node_data.get('col_count')}<br>"
            f"Primary Key: {node_data.get('pks')}<br>"
            f"Approx Rows (CARD): {node_data.get('card'):,}<br>"
            f"Connections: {deg}"
        )
        node_text.append(hover_info)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=node_labels,
        textposition="top center",
        hovertext=node_text,
        marker=dict(
            showscale=False,
            color=node_colors,
            size=node_sizes,
            line=dict(width=2, color="#FFFFFF"),
        ),
        name="Entities",
    )

    fig = go.Figure(
        data=[edge_trace_declared, edge_trace_inferred, node_trace],
        layout=go.Layout(
            showlegend=True,
            hovermode="closest",
            margin=dict(b=20, l=20, r=20, t=30),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            height=580,
        ),
    )
    return fig
