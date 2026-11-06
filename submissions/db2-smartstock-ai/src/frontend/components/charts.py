"""
Interactive Plotly Visualizations for SmartStock AI.
Fully adaptive to both Dark and Light themes.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, List, Any

# Transparent layout letting Streamlit manage font/grid contrast dynamically
CHART_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 20, "r": 20, "t": 40, "b": 20},
    "xaxis": {"showgrid": True, "gridcolor": "rgba(148, 163, 184, 0.2)"},
    "yaxis": {"showgrid": True, "gridcolor": "rgba(148, 163, 184, 0.2)"},
}

def plot_demand_vs_stock(forecasts: List[Dict[str, Any]]):
    """Bar chart comparing Current Stock vs Predicted 7-Day Demand."""
    df = pd.DataFrame(forecasts)
    if df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['ingredient_name'],
        y=df['current_stock'],
        name='Current Stock',
        marker_color='#10b981'
    ))
    fig.add_trace(go.Bar(
        x=df['ingredient_name'],
        y=df['predicted_demand'],
        name='Predicted 7-Day Demand',
        marker_color='#3b82f6'
    ))
    fig.add_trace(go.Bar(
        x=df['ingredient_name'],
        y=df['shortage'],
        name='Projected Shortage',
        marker_color='#ef4444'
    ))

    fig.update_layout(
        barmode='group',
        title="7-Day Demand Forecast vs Current Stock (Shortage Detection)",
        **CHART_LAYOUT
    )
    return fig

def plot_feature_importance(feature_importance: Dict[str, float]):
    """Horizontal bar chart showing ML feature importance."""
    if not feature_importance:
        return go.Figure()

    df = pd.DataFrame(list(feature_importance.items()), columns=['Feature', 'Importance'])
    df = df.sort_values(by='Importance', ascending=True)

    fig = px.bar(
        df,
        x='Importance',
        y='Feature',
        orientation='h',
        title="ML Feature Importance (Factors Driving Spoilage Risk)",
        color='Importance',
        color_continuous_scale='Tealgrn'
    )
    fig.update_layout(**CHART_LAYOUT, coloraxis_showscale=False)
    return fig

def plot_waste_by_category(cat_dict: Dict[str, float]):
    """Donut chart showing monetary waste losses by category."""
    if not cat_dict:
        return go.Figure()

    labels = list(cat_dict.keys())
    values = list(cat_dict.values())

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=.45,
        marker=dict(colors=['#f59e0b', '#ef4444', '#10b981', '#3b82f6', '#8b5cf6'])
    )])
    fig.update_layout(
        title="Historical Waste Monetary Loss by Food Category (₹)",
        **CHART_LAYOUT
    )
    return fig

def plot_consumption_timeline(cons_rows: List[Dict[str, Any]]):
    """Line chart showing daily consumption trend."""
    if not cons_rows:
        return go.Figure()

    df = pd.DataFrame(cons_rows)
    fig = px.area(
        df,
        x='consumption_date',
        y='total_used',
        title="Daily Restaurant Ingredient Consumption (kg/L)",
        color_discrete_sequence=['#38bdf8']
    )
    fig.update_layout(**CHART_LAYOUT)
    return fig

def plot_what_if_comparison(items: List[Dict[str, Any]]):
    """Comparison chart for baseline vs simulated demand surge."""
    df = pd.DataFrame(items)
    if df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['ingredient_name'],
        y=df['baseline_demand'],
        name='Baseline Demand',
        marker_color='#94a3b8'
    ))
    fig.add_trace(go.Bar(
        x=df['ingredient_name'],
        y=df['simulated_demand'],
        name='Simulated Demand Surge',
        marker_color='#f59e0b'
    ))
    fig.add_trace(go.Bar(
        x=df['ingredient_name'],
        y=df['simulated_shortage'],
        name='New Projected Shortage',
        marker_color='#ef4444'
    ))

    fig.update_layout(
        barmode='group',
        title="What-If Simulation: Demand Shift & Shortage Impact",
        **CHART_LAYOUT
    )
    return fig
