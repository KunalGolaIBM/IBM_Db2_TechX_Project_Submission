"""Plotly visualizations for retrieved Db2 result sets."""
def show_dataframe_chart(df, x: str, y: str, kind: str = "Bar"):
    import plotly.express as px
    kind = kind.lower()
    if kind == "line": fig = px.line(df, x=x, y=y, markers=True)
    elif kind == "area": fig = px.area(df, x=x, y=y)
    elif kind == "pie": fig = px.pie(df, names=x, values=y, hole=0.4)
    else: fig = px.bar(df, x=x, y=y, color=x)
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=12,r=12,t=32,b=12))
    return fig
