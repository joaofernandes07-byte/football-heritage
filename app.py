import dash
from dash import html, dcc
from dash.dependencies import Input, Output
from dash import dash_table
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# -------------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------------
df = pd.read_csv("ballon_dor_complete.csv")
df.columns = df.columns.str.strip()
df["year"] = df["year"].astype(int)

# Filter only awarded editions (excludes 2020)
df_valid = df[df["awarded"] == True].copy()
countries = sorted(df_valid["modern_country"].dropna().unique())
positions = sorted(df_valid["general_position"].dropna().unique())

# -------------------------------------------------------------
# CREATE DASH APP (COMPATIBLE WITH gunicorn app:app ON RENDER)
# -------------------------------------------------------------
dash_app = dash.Dash(__name__, suppress_callback_exceptions=True)
app = dash_app.server

# -------------------------------------------------------------
# LAYOUT
# -------------------------------------------------------------
dash_app.layout = html.Div([
    html.H1("Ballon d'Or Historical Dashboard (1956–2024)", style={"textAlign": "center"}),

    dcc.Tabs(id="mainTabs", value="overviewTab", children=[
        dcc.Tab(label="Overview", value="overviewTab"),
        dcc.Tab(label="Graphics (Nested Tabs)", value="graphicsTab"),
        dcc.Tab(label="Data Table", value="tableTab"),
        dcc.Tab(label="Summary Statistics", value="summaryTab"),
    ]),

    html.Hr(),

    # ------------------- FILTERS -------------------
    html.Div([
        html.Div([
            html.Label("Select Country:"),
            dcc.Dropdown(
                id="countryFilter",
                options=[{"label": "All", "value": "All"}] + [{"label": c, "value": c} for c in countries],
                value=["All"],
                multi=True,
                style={"width": "95%"}
            )
        ], style={"width": "24%", "display": "inline-block", "verticalAlign": "top"}),

        html.Div([
            html.Label("Select Position:"),
            dcc.Dropdown(
                id="positionFilter",
                options=[{"label": "All", "value": "All"}] + [{"label": p, "value": p} for p in positions],
                value=["All"],
                multi=True,
                style={"width": "95%"}
            )
        ], style={"width": "22%", "display": "inline-block", "verticalAlign": "top"}),

        html.Div([
            html.Label("Select Year Range:"),
            dcc.RangeSlider(
                id="yearFilter",
                min=int(df_valid["year"].min()),
                max=int(df_valid["year"].max()),
                value=[int(df_valid["year"].min()), int(df_valid["year"].max())],
                marks={y: str(y) for y in range(int(df_valid["year"].min()), int(df_valid["year"].max()) + 1, 8)},
                tooltip={"placement": "bottom", "always_visible": True}
            )
        ], style={"width": "52%", "display": "inline-block", "paddingLeft": "2%", "verticalAlign": "top"})
    ], style={"padding": "15px"}),

    html.Hr(),

    html.Div(id="tabContent"),
    dcc.Store(id="filteredData")
])

# -------------------------------------------------------------
# CALLBACK -> FILTER DATA
# -------------------------------------------------------------
@dash_app.callback(
    Output("filteredData", "data"),
    [Input("countryFilter", "value"),
     Input("positionFilter", "value"),
     Input("yearFilter", "value")]
)
def filter_data(country_sel, pos_sel, year_range):
    low, high = year_range
    dff = df_valid.copy()

    if country_sel and "All" not in country_sel:
        dff = dff[dff["modern_country"].isin(country_sel)]

    if pos_sel and "All" not in pos_sel:
        dff = dff[dff["general_position"].isin(pos_sel)]

    dff = dff[(dff["year"] >= low) & (dff["year"] <= high)]
    return dff.to_dict("records")

# -------------------------------------------------------------
# CALLBACK -> MAIN TABS
# -------------------------------------------------------------
@dash_app.callback(
    Output("tabContent", "children"),
    [Input("mainTabs", "value"),
     Input("filteredData", "data")]
)
def render_tabs(tab, data):
    if not data:
        return html.Div("No data available for the selected filters.", style={"padding": "20px"})

    dff = pd.DataFrame(data)

    if tab == "overviewTab":
        dff_sorted = dff.sort_values("year").copy()
        dff_sorted["cumulative_awards"] = dff_sorted.groupby("modern_country").cumcount() + 1

        fig = go.Figure()
        for country in sorted(dff_sorted["modern_country"].unique()):
            df_c = dff_sorted[dff_sorted["modern_country"] == country]
            fig.add_trace(go.Scatter(
                x=df_c["year"],
                y=df_c["cumulative_awards"],
                mode="lines+markers",
                name=country,
                text=df_c["player"] + " (" + df_c["club"] + " | " + df_c["season_goals"].astype(int).astype(str) + "G, " + df_c["season_assists"].astype(int).astype(str) + "A)",
                hovertemplate="<b>%{fullData.name}</b><br>Year: %{x}<br>Cumulative Awards: %{y}<br>Winner: %{text}<extra></extra>"
            ))

        fig.update_layout(
            title="Cumulative Ballon d'Or Wins by Country",
            xaxis_title="Year",
            yaxis_title="Cumulative Awards"
        )

        return html.Div([
            html.H3("Overview"),
            dcc.Graph(figure=fig)
        ])

    if tab == "graphicsTab":
        return html.Div([
            dcc.Tabs(id="nestedTabs", value="barCountry", children=[
                dcc.Tab(label="Wins by Country", value="barCountry"),
                dcc.Tab(label="Wins by Club", value="barClub"),
                dcc.Tab(label="Goals & Assists Trend", value="goalsLine"),
                dcc.Tab(label="Age vs. Year (Scatter)", value="ageScatter"),
                dcc.Tab(label="Cumulative Trendline", value="trend")
            ]),
            html.Div(id="nestedContent", style={"paddingTop": "20px"})
        ])

    if tab == "tableTab":
        cols_display = [
            "year", "player", "modern_country", "club", "club_league",
            "general_position", "age_at_win", "season_goals", "season_assists",
            "goal_contributions", "winner_points", "runner_up", "third_place", "key_achievement"
        ]
        return html.Div([
            html.H3("Filtered Ballon d'Or Data Table"),
            dash_table.DataTable(
                columns=[{"name": col.replace("_", " ").title(), "id": col} for col in cols_display],
                data=dff[cols_display].to_dict("records"),
                page_size=15,
                sort_action="native",
                filter_action="native",
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center", "padding": "6px", "fontSize": "13px"}
            )
        ])

    if tab == "summaryTab":
        country_summary = (
            dff.groupby("modern_country")
            .agg(
                Total_Awards=("year", "count"),
                Unique_Winners=("player", "nunique"),
                Avg_Age=("age_at_win", "mean"),
                Avg_Goals=("season_goals", "mean"),
                Avg_Assists=("season_assists", "mean"),
                First_Win=("year", "min"),
                Last_Win=("year", "max")
            )
            .round(1)
            .sort_values(by="Total_Awards", ascending=False)
        )
        return html.Div([
            html.H3("Summary Statistics by Country"),
            html.Pre(country_summary.to_string(), style={"fontSize": "14px"})
        ])

# -------------------------------------------------------------
# CALLBACK -> NESTED GRAPH TABS
# -------------------------------------------------------------
@dash_app.callback(
    Output("nestedContent", "children"),
    [Input("nestedTabs", "value"),
     Input("filteredData", "data")]
)
def nested_graphs(nested_tab, data):
    if not data:
        return html.Div("Waiting for data...")

    dff = pd.DataFrame(data)
    dff_sorted = dff.sort_values("year").copy()
    dff_sorted["cumulative_awards"] = dff_sorted.groupby("modern_country").cumcount() + 1

    if nested_tab == "barCountry":
        sums = dff.groupby("modern_country").size().reset_index(name="total_awards")
        sums = sums.sort_values("total_awards", ascending=False)
        fig = go.Figure(go.Bar(
            x=sums["modern_country"],
            y=sums["total_awards"],
            text=sums["total_awards"],
            textposition="auto"
        ))
        fig.update_layout(
            title="Total Ballon d'Or Awards by Country",
            xaxis_title="Country",
            yaxis_title="Number of Awards"
        )
        return dcc.Graph(figure=fig)

    if nested_tab == "barClub":
        club_sums = dff.groupby("club").size().reset_index(name="total_awards")
        club_sums = club_sums.sort_values("total_awards", ascending=False)
        fig = go.Figure(go.Bar(
            x=club_sums["club"],
            y=club_sums["total_awards"],
            text=club_sums["total_awards"],
            textposition="auto"
        ))
        fig.update_layout(
            title="Total Ballon d'Or Awards by Club",
            xaxis_title="Club",
            yaxis_title="Number of Awards"
        )
        return dcc.Graph(figure=fig)

    if nested_tab == "goalsLine":
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dff_sorted["year"],
            y=dff_sorted["season_goals"],
            mode="lines+markers",
            name="Season Goals",
            text=dff_sorted["player"],
            hovertemplate="<b>%{text}</b> (%{x})<br>Goals: %{y}<extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=dff_sorted["year"],
            y=dff_sorted["season_assists"],
            mode="lines+markers",
            name="Season Assists",
            text=dff_sorted["player"],
            hovertemplate="<b>%{text}</b> (%{x})<br>Assists: %{y}<extra></extra>"
        ))
        fig.update_layout(
            title="Winner Season Goals & Assists Over Time",
            xaxis_title="Year",
            yaxis_title="Count"
        )
        return dcc.Graph(figure=fig)

    if nested_tab == "ageScatter":
        fig = go.Figure()
        for pos in sorted(dff["general_position"].dropna().unique()):
            df_p = dff[dff["general_position"] == pos]
            fig.add_trace(go.Scatter(
                x=df_p["year"],
                y=df_p["age_at_win"],
                mode="markers",
                marker=dict(size=10),
                name=pos,
                text=df_p["player"] + " (" + df_p["modern_country"] + ")",
                hovertemplate="<b>%{text}</b><br>Year: %{x}<br>Age: %{y}<extra></extra>"
            ))
        fig.update_layout(
            title="Winner Age at Victory by Position",
            xaxis_title="Year",
            yaxis_title="Age at Win"
        )
        return dcc.Graph(figure=fig)

    if nested_tab == "trend":
        fig = go.Figure()
        for country in sorted(dff_sorted["modern_country"].unique()):
            df_c = dff_sorted[dff_sorted["modern_country"] == country]
            fig.add_trace(go.Scatter(
                x=df_c["year"],
                y=df_c["cumulative_awards"],
                mode="markers",
                name=country
            ))
            if len(df_c) > 1:
                m, b = np.polyfit(df_c["year"], df_c["cumulative_awards"], 1)
                fig.add_trace(go.Scatter(
                    x=df_c["year"],
                    y=m * df_c["year"] + b,
                    mode="lines",
                    name=f"{country} trend"
                ))
        fig.update_layout(
            title="Cumulative Wins Linear Trend by Country",
            xaxis_title="Year",
            yaxis_title="Cumulative Awards"
        )
        return dcc.Graph(figure=fig)

# -------------------------------------------------------------
# RUN APP
# -------------------------------------------------------------
if __name__ == "__main__":
    dash_app.run(debug=True)