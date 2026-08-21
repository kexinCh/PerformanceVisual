from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from data_processing import (
    GAME_TYPE_LABELS,
    LABEL_TO_GAME_TYPE,
    METRIC_DEFINITIONS,
    METRICS,
    pp,
    pp_neutral,
    pct,
    process_workbook,
)


APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR / "data" / "Golfer Resilience Data Set.xlsx"

BERKELEY_BLUE = "#003262"
CAL_GOLD = "#FDB515"
INK = "#1F2937"
MUTED = "#6B7280"
LINE = "#D8DEE9"
TEAL = "#2A9D8F"
ROSE = "#B56576"
LIGHT_BG = "#F7F9FC"

PRIMARY_CONTEXT_LABEL = "Tournament + Qualifying"
PRIMARY_YEAR_MODE = "Compare 2024 vs 2025"


st.set_page_config(
    page_title="Golf Mental-Performance Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #F6F8FB 0%, #FFFFFF 260px);
    }
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2.5rem;
        max-width: 1380px;
    }
    h1, h2, h3 {
        color: #1F2937;
        letter-spacing: 0;
    }
    .dashboard-hero {
        background: #FFFFFF;
        border: 1px solid #D8DEE9;
        border-top: 7px solid #003262;
        border-radius: 14px;
        padding: 22px 26px 18px 26px;
        margin-bottom: 18px;
        box-shadow: 0 10px 30px rgba(0, 50, 98, 0.07);
    }
    .hero-kicker {
        color: #8A6D00;
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .hero-title {
        color: #172033;
        font-size: 2.25rem;
        font-weight: 800;
        line-height: 1.08;
        margin: 0;
    }
    .hero-copy {
        color: #5E6878;
        font-size: 1.02rem;
        margin-top: 8px;
        max-width: 920px;
    }
    .section-title {
        color: #172033;
        font-size: 1.35rem;
        font-weight: 800;
        margin: 22px 0 2px 0;
    }
    .section-subtitle {
        color: #6B7280;
        font-size: 0.96rem;
        line-height: 1.4;
        margin-bottom: 12px;
    }
    div[data-baseweb="tab-list"] {
        gap: 10px;
        border-bottom: 1px solid #D8DEE9;
        margin-top: 8px;
    }
    button[data-baseweb="tab"] {
        background: #FFFFFF;
        border: 1px solid #D8DEE9;
        border-bottom: 0;
        border-radius: 10px 10px 0 0;
        padding: 10px 18px;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #003262;
        color: #FFFFFF;
    }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #D8DEE9;
        border-left: 5px solid #FDB515;
        border-radius: 12px;
        padding: 17px 18px;
        box-shadow: 0 8px 22px rgba(0, 50, 98, 0.055);
    }
    div[data-testid="stMetric"] label {
        color: #1F2937;
        font-weight: 700;
    }
    div[data-testid="stMetricValue"] {
        color: #003262;
        font-size: 2.05rem;
        line-height: 1.1;
    }
    div[data-testid="stMetricDelta"] {
        color: #1F2937;
    }
    .small-note {
        color: #6B7280;
        font-size: 0.92rem;
        line-height: 1.35;
    }
    .callout {
        background: #FFF8E6;
        border: 1px solid #F4D27A;
        border-radius: 10px;
        padding: 12px 14px;
        color: #3F2D00;
    }
    .section-card {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 18px;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        overflow: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def get_data(path: str, cache_key: float):
    return process_workbook(Path(path))


def workbook_cache_key(path: Path) -> float:
    candidates = [path, Path(str(path) + ".b64")]
    mtimes = [candidate.stat().st_mtime for candidate in candidates if candidate.exists()]
    return max(mtimes) if mtimes else 0.0


data = get_data(str(DATA_PATH), workbook_cache_key(DATA_PATH))


def make_template(height: int = 430, top: int = 92, bottom: int = 54):
    return dict(
        template="plotly_white",
        height=height,
        margin=dict(l=26, r=28, t=top, b=bottom),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", size=14, color=INK),
        title_font=dict(size=20, color=INK),
        title_x=0.0,
        legend=dict(orientation="h", yanchor="bottom", y=-0.20, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=LINE, font=dict(color=INK, size=13)),
    )


def safe_rate_axis_max(values, minimum: float = 0.5, padding: float = 0.1) -> float:
    valid = pd.Series(values).dropna()
    if valid.empty:
        return minimum
    return max(minimum, float(valid.max()) + padding)


def metric_definition(metric: str) -> str:
    return METRIC_DEFINITIONS.get(metric, "")


def selected_context_controls(presentation_mode: bool):
    col1, col2, col3 = st.columns([1.2, 1.2, 1.0])
    with col1:
        context_label = st.selectbox(
            "Competition Context",
            ["Tournament + Qualifying", "Tournament Only"],
            index=0,
            help="Tournament + Qualifying is the default interview view. Tournament Only is analyzed separately.",
        )
    with col2:
        year_mode = st.selectbox(
            "Year View",
            ["Compare 2024 vs 2025", "2025", "2024"],
            index=0,
            help="Compare mode emphasizes year-over-year movement.",
        )
    with col3:
        if presentation_mode:
            st.markdown("<div class='small-note'>Presentation Mode is on: technical detail is minimized.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='small-note'>Use the tabs below to move from team patterns to a player-specific view.</div>", unsafe_allow_html=True)
    return LABEL_TO_GAME_TYPE[context_label], year_mode


def year_from_mode(year_mode: str) -> int:
    return 2024 if year_mode == "2024" else 2025


def is_compare_mode(year_mode: str) -> bool:
    return year_mode == "Compare 2024 vs 2025"


def metric_delta_color(metric: str) -> str:
    return "inverse" if metric == "Reverse Bounce Back" else "normal"


@st.cache_data(show_spinner=False)
def context_benchmark(context: str) -> pd.DataFrame:
    return data.team_benchmark[data.team_benchmark["Game Type"] == context].copy()


@st.cache_data(show_spinner=False)
def get_benchmark(context: str, year: int, metric: str) -> float:
    row = data.team_benchmark[
        (data.team_benchmark["Game Type"] == context)
        & (data.team_benchmark["Year"] == year)
        & (data.team_benchmark["Metric"].astype(str) == metric)
    ]
    if row.empty:
        return np.nan
    return float(row.iloc[0]["team_benchmark"])


@st.cache_data(show_spinner=False)
def player_metric_row(player: str, context: str, year: int, metric: str) -> pd.Series | None:
    rows = data.relative[
        (data.relative["Player"] == player)
        & (data.relative["Game Type"] == context)
        & (data.relative["Year"] == year)
        & (data.relative["Metric"].astype(str) == metric)
    ]
    if rows.empty:
        return None
    return rows.iloc[0]


@st.cache_data(show_spinner=False)
def player_yoy_row(player: str, context: str, metric: str) -> pd.Series | None:
    rows = data.yoy[
        (data.yoy["Player"] == player)
        & (data.yoy["Game Type"] == context)
        & (data.yoy["Metric"].astype(str) == metric)
    ]
    if rows.empty:
        return None
    return rows.iloc[0]


def section_intro(title: str, subtitle: str):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='section-subtitle'>{subtitle}</div>", unsafe_allow_html=True)


def render_glossary(presentation_mode: bool):
    with st.expander("Metric Definitions", expanded=False):
        for metric, definition in METRIC_DEFINITIONS.items():
            st.markdown(f"**{metric}**: `{definition}`")
        st.markdown(
            """
            These are supplied behavioral transition indicators. They are not direct measurements of
            mental toughness, resilience, confidence, or focus.
            """
        )
    if not presentation_mode:
        with st.expander("Data & Interpretation Notes", expanded=False):
            st.markdown(
                """
                - Underlying event/opportunity counts are unavailable.
                - Team benchmarks are unweighted averages of available athlete rates.
                - Statistical significance cannot be evaluated from the supplied data.
                - Tournament + Qualifying cannot be decomposed into qualifying-only performance without underlying counts.
                - Metric denominator details should be confirmed.
                - Supplied transition metrics are descriptive behavioral indicators, not direct measures of psychological state.
                """
            )


def render_kpi_cards(context: str, year_mode: str):
    cols = st.columns(4)
    for i, metric in enumerate(METRICS):
        if is_compare_mode(year_mode):
            year = 2025
            b24 = get_benchmark(context, 2024, metric)
            b25 = get_benchmark(context, 2025, metric)
            value = pct(b25)
            delta = f"{pp(b25 - b24)} vs 2024" if pd.notna(b24) and pd.notna(b25) else None
        else:
            year = year_from_mode(year_mode)
            value = pct(get_benchmark(context, year, metric))
            delta = None
        with cols[i]:
            st.metric(
                metric,
                value,
                delta,
                delta_color=metric_delta_color(metric),
                help=f"{metric_definition(metric)}\n\nAverage Athlete Rate for {year}.",
            )


@st.cache_data(show_spinner=False)
def team_dumbbell(context: str) -> go.Figure:
    bench = context_benchmark(context)
    rows = []
    for metric in METRICS:
        b24 = get_benchmark(context, 2024, metric)
        b25 = get_benchmark(context, 2025, metric)
        rows.append({"Metric": metric, "2024": b24, "2025": b25, "Change": b25 - b24})
    chart = pd.DataFrame(rows).iloc[::-1]

    fig = go.Figure()
    for _, row in chart.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["2024"], row["2025"]],
                y=[row["Metric"], row["Metric"]],
                mode="lines",
                line=dict(color=LINE, width=8),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=chart["2024"],
            y=chart["Metric"],
            mode="markers+text",
            marker=dict(size=18, color=BERKELEY_BLUE),
            text=chart["2024"].map(pct),
            textposition="middle left",
            name="2024",
            hovertemplate="<b>%{y}</b><br>2024 benchmark: %{x:.1%}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=chart["2025"],
            y=chart["Metric"],
            mode="markers+text",
            marker=dict(size=18, color=CAL_GOLD, line=dict(color="#8A6D00", width=1)),
            text=chart["2025"].map(pct),
            textposition="middle right",
            name="2025",
            hovertemplate="<b>%{y}</b><br>2025 benchmark: %{x:.1%}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=chart[["2024", "2025"]].max(axis=1) + 0.085,
            y=chart["Metric"],
            mode="text",
            text=chart["Change"].map(pp),
            textfont=dict(size=17, color=INK),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        **make_template(470, top=94, bottom=62),
        title=f"How Did the Team Change?<br><sup>{GAME_TYPE_LABELS[context]} • average athlete rate</sup>",
        xaxis=dict(tickformat=".0%", title="Team Benchmark", range=[0, max(chart[["2024", "2025"]].max()) + 0.18]),
        yaxis=dict(title=None),
    )
    return fig


@st.cache_data(show_spinner=False)
def player_metric_trend_lines(context: str) -> go.Figure:
    trend = data.relative[
        (data.relative["Game Type"] == context)
        & (data.relative["data_status"] == "valid")
    ].copy()
    trend["Metric"] = pd.Categorical(trend["Metric"], categories=METRICS, ordered=True)
    trend = trend.sort_values(["Metric", "Player", "Year"])

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=METRICS,
        horizontal_spacing=0.10,
        vertical_spacing=0.18,
    )
    players = sorted(trend["Player"].unique())
    palette = [
        BERKELEY_BLUE,
        CAL_GOLD,
        TEAL,
        ROSE,
        "#6C5CE7",
        "#E76F51",
        "#457B9D",
        "#7A7A7A",
    ]

    for metric_idx, metric in enumerate(METRICS):
        metric_data = trend[trend["Metric"].astype(str) == metric]
        for player_idx, player in enumerate(players):
            player_data = metric_data[metric_data["Player"] == player]
            if player_data.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=player_data["Year"],
                    y=player_data["clean_value"],
                    mode="lines+markers",
                    name=player,
                    legendgroup=player,
                    showlegend=metric_idx == 0,
                    marker=dict(size=9),
                    line=dict(width=2.5, color=palette[player_idx % len(palette)]),
                    customdata=np.stack(
                        [
                            player_data["Metric"].astype(str),
                            player_data["relative_to_team_pp"].map(pp),
                        ],
                        axis=-1,
                    ),
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "%{customdata[0]}<br>"
                        "Year: %{x}<br>"
                        "Rate: %{y:.1%}<br>"
                        "vs Team: %{customdata[1]}<extra></extra>"
                    ),
                ),
                row=(metric_idx // 2) + 1,
                col=(metric_idx % 2) + 1,
            )

    fig.update_layout(
        **make_template(730, top=126, bottom=96),
        title=f"Player Trends by Metric<br><sup>{GAME_TYPE_LABELS[context]} • year on x-axis, rate on y-axis</sup>",
    )
    fig.update_layout(legend=dict(title="Player", orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5))
    fig.update_annotations(font=dict(size=14, color=INK))
    for idx, metric in enumerate(METRICS, start=1):
        fig.update_xaxes(
            title="Year",
            tickmode="array",
            tickvals=[2024, 2025],
            range=[2023.85, 2025.15],
            row=((idx - 1) // 2) + 1,
            col=((idx - 1) % 2) + 1,
        )
        fig.update_yaxes(
            title="Rate",
            tickformat=".0%",
            range=[0, safe_rate_axis_max(trend[trend["Metric"].astype(str) == metric]["clean_value"], minimum=0.35, padding=0.08)],
            row=((idx - 1) // 2) + 1,
            col=((idx - 1) % 2) + 1,
        )
    return fig


@st.cache_data(show_spinner=False)
def distribution_chart(context: str, year: int, metric: str) -> go.Figure:
    rel = data.relative[
        (data.relative["Game Type"] == context)
        & (data.relative["Year"] == year)
        & (data.relative["Metric"].astype(str) == metric)
        & (data.relative["data_status"] == "valid")
    ].copy()
    yoy = data.yoy[(data.yoy["Game Type"] == context) & (data.yoy["Metric"].astype(str) == metric)][
        ["Player", "yoy_change_pp"]
    ]
    rel = rel.merge(yoy, on="Player", how="left")

    fig = go.Figure()
    fig.add_trace(
        go.Box(
            x=rel["clean_value"],
            name=metric,
            boxpoints=False,
            marker_color=BERKELEY_BLUE,
            line=dict(color=BERKELEY_BLUE),
            fillcolor="rgba(0, 50, 98, 0.14)",
            hovertemplate="Distribution<br>Median/IQR context<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=rel["clean_value"],
            y=[metric] * len(rel),
            mode="markers",
            marker=dict(size=15, color=CAL_GOLD, line=dict(color=BERKELEY_BLUE, width=1.5)),
            text=rel["Player"],
            customdata=np.stack(
                [
                    rel["relative_to_team_pp"].map(pp),
                    rel["yoy_change_pp"].map(pp),
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Rate: %{x:.1%}<br>"
                "vs Team: %{customdata[0]}<br>"
                "YoY: %{customdata[1]}<extra></extra>"
            ),
            name="Athletes",
        )
    )
    fig.update_layout(
        **make_template(340, top=88, bottom=48),
        title=f"{metric}<br><sup>{year} • {GAME_TYPE_LABELS[context]}</sup>",
        xaxis=dict(tickformat=".0%", title="Supplied Rate"),
        yaxis=dict(showticklabels=False, title=None),
        showlegend=False,
    )
    return fig


def render_all_metric_distributions(context: str, year: int):
    rows = [st.columns(2), st.columns(2)]
    for idx, metric in enumerate(METRICS):
        with rows[idx // 2][idx % 2]:
            st.plotly_chart(distribution_chart(context, year, metric), width="stretch")


@st.cache_data(show_spinner=False)
def notable_changes(context: str) -> pd.DataFrame:
    rows = data.yoy[(data.yoy["Game Type"] == context) & data.yoy["yoy_change_pp"].notna()].copy()
    out = []
    for metric in METRICS:
        metric_rows = rows[rows["Metric"].astype(str) == metric]
        if metric_rows.empty:
            continue
        inc = metric_rows.loc[metric_rows["yoy_change_pp"].idxmax()]
        dec = metric_rows.loc[metric_rows["yoy_change_pp"].idxmin()]
        out.append(
            {
                "Label": "Largest increase",
                "Player": inc["Player"],
                "Metric": metric,
                "Change": pp(inc["yoy_change_pp"]),
                "Coach-facing note": f"{inc['Player']} - {metric} increased {pp(inc['yoy_change_pp'])}.",
            }
        )
        out.append(
            {
                "Label": "Largest decrease",
                "Player": dec["Player"],
                "Metric": metric,
                "Change": pp(dec["yoy_change_pp"]),
                "Coach-facing note": f"{dec['Player']} - {metric} changed {pp(dec['yoy_change_pp'])}.",
            }
        )
    return pd.DataFrame(out)


@st.cache_data(show_spinner=False)
def table_for_year_mode(context: str, year_mode: str) -> pd.DataFrame:
    players = sorted(data.relative[data.relative["Game Type"] == context]["Player"].unique())
    rows = []
    for player in players:
        row = {"Player": player}
        for metric in METRICS:
            if year_mode == "2024":
                r = player_metric_row(player, context, 2024, metric)
                row[f"{metric} Rate"] = pct(r["clean_value"]) if r is not None else "NA"
                row[f"{metric} vs Team"] = pp(r["relative_to_team_pp"]) if r is not None else "NA"
            elif year_mode == "2025":
                r = player_metric_row(player, context, 2025, metric)
                row[f"{metric} Rate"] = pct(r["clean_value"]) if r is not None else "NA"
                row[f"{metric} vs Team"] = pp(r["relative_to_team_pp"]) if r is not None else "NA"
            else:
                y = player_yoy_row(player, context, metric)
                row[f"{metric} Rate"] = pct(y["clean_value_2025"]) if y is not None else "NA"
                row[f"{metric} vs Team"] = pp(y["relative_to_team_pp_2025"]) if y is not None else "NA"
                row[f"{metric} YoY"] = pp(y["yoy_change_pp"]) if y is not None else "NA"
        rows.append(row)
    return pd.DataFrame(rows)


def player_snapshot(player: str, context: str, year_mode: str):
    cols = st.columns(4)
    selected_year = year_from_mode(year_mode)
    for i, metric in enumerate(METRICS):
        year = 2025 if is_compare_mode(year_mode) else selected_year
        r25 = player_metric_row(player, context, year, metric)
        y = player_yoy_row(player, context, metric)
        if r25 is None or r25["data_status"] != "valid":
            value = "NA"
            delta = r25["data_explanation"] if r25 is not None else "No row available."
            help_text = delta
        else:
            value = pct(r25["clean_value"])
            team_text = pp(r25["relative_to_team_pp"])
            if is_compare_mode(year_mode):
                yoy_text = pp(y["yoy_change_pp"]) if y is not None else "NA"
                delta = f"{yoy_text} vs 2024 | {team_text} vs team"
            else:
                delta = f"{team_text} vs team"
            help_text = metric_definition(metric)
        with cols[i]:
            st.metric(metric, value, delta, delta_color=metric_delta_color(metric), help=help_text)


@st.cache_data(show_spinner=False)
def player_profile_chart(player: str, context: str) -> go.Figure:
    rows = []
    for metric in METRICS:
        y = player_yoy_row(player, context, metric)
        if y is None:
            continue
        rows.append(
            {
                "Metric": metric,
                "2024": y["clean_value_2024"],
                "2025": y["clean_value_2025"],
                "Change": y["yoy_change_pp"],
            }
        )
    chart = pd.DataFrame(rows).iloc[::-1]
    fig = go.Figure()
    for _, row in chart.iterrows():
        if pd.notna(row["2024"]) and pd.notna(row["2025"]):
            fig.add_trace(
                go.Scatter(
                    x=[row["2024"], row["2025"]],
                    y=[row["Metric"], row["Metric"]],
                    mode="lines",
                    line=dict(color=LINE, width=7),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
    fig.add_trace(
        go.Scatter(
            x=chart["2024"],
            y=chart["Metric"],
            mode="markers+text",
            text=chart["2024"].map(pct),
            textposition="middle left",
            marker=dict(size=17, color=BERKELEY_BLUE),
            name="2024",
            hovertemplate="<b>%{y}</b><br>2024: %{x:.1%}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=chart["2025"],
            y=chart["Metric"],
            mode="markers+text",
            text=chart["2025"].map(pct),
            textposition="middle right",
            marker=dict(size=17, color=CAL_GOLD, line=dict(color="#8A6D00", width=1)),
            name="2025",
            hovertemplate="<b>%{y}</b><br>2025: %{x:.1%}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=chart[["2024", "2025"]].max(axis=1) + 0.09,
            y=chart["Metric"],
            mode="text",
            text=chart["Change"].map(pp),
            textfont=dict(size=16, color=INK),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    max_x = np.nanmax(chart[["2024", "2025"]].values)
    fig.update_layout(
        **make_template(470, top=98, bottom=66),
        title=f"How Has {player} Changed?<br><sup>{GAME_TYPE_LABELS[context]} • supplied rates shown directly</sup>",
        xaxis=dict(tickformat=".0%", title="Rate", range=[0, min(1, max_x + 0.22)]),
        yaxis=dict(title=None),
    )
    return fig


@st.cache_data(show_spinner=False)
def bad_hole_chart(player: str, context: str) -> go.Figure:
    bad_metrics = ["Bounce Back to Birdie", "Bounce Back to Par", "Bogey Following Bogey"]
    rows = []
    for metric in bad_metrics:
        for year in [2024, 2025]:
            r = player_metric_row(player, context, year, metric)
            rows.append({"Metric": metric, "Year": str(year), "Rate": r["clean_value"] if r is not None else np.nan})
    chart = pd.DataFrame(rows)
    fig = go.Figure()
    for year, color in [("2024", BERKELEY_BLUE), ("2025", CAL_GOLD)]:
        part = chart[chart["Year"] == year]
        fig.add_trace(
            go.Bar(
                y=part["Metric"],
                x=part["Rate"],
                orientation="h",
                name=year,
                marker_color=color,
                text=part["Rate"].map(pct),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>%{x:.1%}<extra></extra>",
            )
        )
    fig.update_layout(
        **make_template(410),
        title=f"What Happens After a Bogey or Worse?<br><sup>{player} • supplied transition rates displayed directly</sup>",
        xaxis=dict(tickformat=".0%", title="Supplied Rate", range=[0, safe_rate_axis_max(chart["Rate"])]),
        yaxis=dict(title=None, autorange="reversed"),
        barmode="group",
    )
    return fig


@st.cache_data(show_spinner=False)
def bad_hole_chart_for_year(player: str, context: str, year: int) -> go.Figure:
    bad_metrics = ["Bounce Back to Birdie", "Bounce Back to Par", "Bogey Following Bogey"]
    rows = []
    for metric in bad_metrics:
        r = player_metric_row(player, context, year, metric)
        rows.append({"Metric": metric, "Rate": r["clean_value"] if r is not None else np.nan})
    chart = pd.DataFrame(rows)
    fig = go.Figure(
        go.Bar(
            y=chart["Metric"],
            x=chart["Rate"],
            orientation="h",
            marker_color=BERKELEY_BLUE,
            text=chart["Rate"].map(pct),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x:.1%}<extra></extra>",
        )
    )
    fig.update_layout(
        **make_template(360),
        title=f"What Happens After a Bogey or Worse?<br><sup>{player} • {year} • supplied transition rates displayed directly</sup>",
        xaxis=dict(tickformat=".0%", title="Supplied Rate", range=[0, safe_rate_axis_max(chart["Rate"])]),
        yaxis=dict(title=None, autorange="reversed"),
        showlegend=False,
    )
    return fig


@st.cache_data(show_spinner=False)
def bad_hole_normalized_pie(player: str, context: str, year: int) -> go.Figure:
    pie_metrics = ["Bounce Back to Birdie", "Bounce Back to Par", "Bogey Following Bogey"]
    labels = [
        "Bogey+ -> Birdie+",
        "Bogey+ -> Par",
        "Bogey+ -> Bogey+",
    ]
    values = []
    for metric in pie_metrics:
        row = player_metric_row(player, context, year, metric)
        values.append(row["clean_value"] if row is not None and row["data_status"] == "valid" else np.nan)
    total = np.nansum(values)
    if not total or pd.isna(total):
        fig = go.Figure()
        fig.add_annotation(
            text="NA<br><sup>No valid bad-hole rates available for this year/context.</sup>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=22, color=INK),
        )
        fig.update_layout(
            **make_template(300),
            title=(
                "Exploratory Normalized Bad-Hole Mix"
                f"<br><sup>{player} • {year} • denominator = sum of the three supplied bad-hole rates</sup>"
            ),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        return fig
    norm_values = [v / total if pd.notna(v) and total > 0 else np.nan for v in values]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=norm_values,
            hole=0.45,
            marker=dict(colors=[TEAL, CAL_GOLD, BERKELEY_BLUE], line=dict(color="white", width=2)),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Normalized share: %{percent}<extra></extra>",
        )
    )
    fig.update_layout(
        **make_template(390),
        title=(
            "Exploratory Normalized Bad-Hole Mix"
            f"<br><sup>{player} • {year} • denominator = sum of the three supplied bad-hole rates</sup>"
        ),
        showlegend=False,
    )
    return fig


@st.cache_data(show_spinner=False)
def bad_hole_context_comparison_chart(player: str, year: int) -> go.Figure:
    bad_metrics = ["Bounce Back to Birdie", "Bounce Back to Par", "Bogey Following Bogey"]
    contexts = [("Tournament", "Tournament Only", BERKELEY_BLUE), ("Tournament + Qualifying", "Tournament + Qualifying", CAL_GOLD)]
    rows = []
    for metric in bad_metrics:
        for context_value, context_label, color in contexts:
            r = player_metric_row(player, context_value, year, metric)
            rows.append(
                {
                    "Metric": metric,
                    "Context": context_label,
                    "Rate": r["clean_value"] if r is not None else np.nan,
                    "Color": color,
                }
            )
    chart = pd.DataFrame(rows)
    fig = go.Figure()
    for context_label, color in [("Tournament Only", BERKELEY_BLUE), ("Tournament + Qualifying", CAL_GOLD)]:
        part = chart[chart["Context"] == context_label]
        fig.add_trace(
            go.Bar(
                y=part["Metric"],
                x=part["Rate"],
                orientation="h",
                name=context_label,
                marker_color=color,
                text=part["Rate"].map(pct),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>%{fullData.name}<br>%{x:.1%}<extra></extra>",
            )
        )
    fig.update_layout(
        **make_template(430, top=104, bottom=68),
        title=f"After a Bogey or Worse<br><sup>{player} • {year} • Tournament Only vs Tournament + Qualifying</sup>",
        xaxis=dict(tickformat=".0%", title="Supplied Rate", range=[0, safe_rate_axis_max(chart["Rate"])]),
        yaxis=dict(title=None, autorange="reversed"),
        barmode="group",
    )
    return fig


@st.cache_data(show_spinner=False)
def bad_hole_context_normalized_pie(player: str, year: int) -> go.Figure:
    pie_metrics = ["Bounce Back to Birdie", "Bounce Back to Par", "Bogey Following Bogey"]
    labels = ["Bogey+ -> Birdie+", "Bogey+ -> Par", "Bogey+ -> Bogey+"]
    fig = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}]],
        subplot_titles=["Tournament Only", "Tournament + Qualifying"],
    )
    for col, context_value in enumerate(["Tournament", "Tournament + Qualifying"], start=1):
        values = []
        for metric in pie_metrics:
            row = player_metric_row(player, context_value, year, metric)
            values.append(row["clean_value"] if row is not None and row["data_status"] == "valid" else np.nan)
        total = np.nansum(values)
        norm_values = [v / total if pd.notna(v) and total > 0 else 0 for v in values]
        fig.add_trace(
            go.Pie(
                labels=labels,
                values=norm_values,
                hole=0.45,
                marker=dict(colors=[TEAL, CAL_GOLD, BERKELEY_BLUE], line=dict(color="white", width=2)),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>Normalized share: %{percent}<extra></extra>",
                showlegend=col == 1,
            ),
            row=1,
            col=col,
        )
    fig.update_layout(
        **make_template(430, top=124, bottom=86),
        title=(
            "Normalized Bad-Hole Mix"
            f"<br><sup>{player} • {year} • exploratory denominator = three supplied bad-hole rates</sup>"
        ),
    )
    fig.update_annotations(font=dict(size=13, color=INK))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5))
    return fig


@st.cache_data(show_spinner=False)
def success_context_comparison_chart(player: str, year: int) -> go.Figure:
    metric = "Reverse Bounce Back"
    rows = []
    for context_value, context_label in [("Tournament", "Tournament Only"), ("Tournament + Qualifying", "Tournament + Qualifying")]:
        value = player_metric_row(player, context_value, year, metric)
        rows.append({"Label": context_label, "Rate": value["clean_value"] if value is not None else np.nan})
    chart = pd.DataFrame(rows)
    fig = go.Figure(
        go.Bar(
            x=chart["Label"],
            y=chart["Rate"],
            marker_color=[BERKELEY_BLUE, CAL_GOLD],
            text=chart["Rate"].map(pct),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:.1%}<extra></extra>",
        )
    )
    fig.update_layout(
        **make_template(430, top=104, bottom=70),
        title=f"After a Birdie or Better<br><sup>{player} • {year} • Tournament Only vs Tournament + Qualifying</sup>",
        yaxis=dict(tickformat=".0%", title="Reverse Bounce Back", range=[0, safe_rate_axis_max(chart["Rate"])]),
        xaxis=dict(title=None),
        showlegend=False,
    )
    return fig


@st.cache_data(show_spinner=False)
def team_comparison_chart(player: str, context: str, year: int, metric: str) -> go.Figure:
    rel = data.relative[
        (data.relative["Game Type"] == context)
        & (data.relative["Year"] == year)
        & (data.relative["Metric"].astype(str) == metric)
        & (data.relative["data_status"] == "valid")
    ].sort_values("clean_value")
    colors = [CAL_GOLD if p == player else BERKELEY_BLUE for p in rel["Player"]]
    sizes = [18 if p == player else 12 for p in rel["Player"]]
    symbols = ["star" if p == player else "circle" for p in rel["Player"]]
    benchmark = get_benchmark(context, year, metric)
    fig = go.Figure()
    fig.add_vline(x=benchmark, line_width=3, line_color=TEAL, annotation_text="Team Benchmark", annotation_position="top")
    fig.add_trace(
        go.Scatter(
            x=rel["clean_value"],
            y=rel["Player"],
            mode="markers",
            marker=dict(color=colors, size=sizes, symbol=symbols, line=dict(width=1, color=INK)),
            text=rel["Player"],
            customdata=rel[["relative_to_team_pp"]].apply(lambda r: [pp_neutral(r["relative_to_team_pp"])], axis=1).tolist(),
            hovertemplate="<b>%{text}</b><br>Rate: %{x:.1%}<br>%{customdata[0]}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        **make_template(470, top=100, bottom=58),
        title=f"Where Does {player} Sit?<br><sup>{metric} • {year} • star = selected athlete</sup>",
        xaxis=dict(tickformat=".0%", title="Supplied Rate"),
        yaxis=dict(title=None, autorange="reversed"),
    )
    return fig


def player_data_notes(player: str, context: str):
    notes = data.validation_notes[
        (data.validation_notes["Player"] == player) & (data.validation_notes["Game Type"] == context)
    ].copy()
    if notes.empty:
        st.caption("No missing or invalid values are flagged for this player in the selected competition context.")
        return
    show = notes[["Year", "Metric", "raw_value", "data_status", "data_explanation"]].sort_values(["Year", "Metric"])
    st.dataframe(show, width="stretch", hide_index=True)


@st.cache_data(show_spinner=False)
def downloadable_table(context: str):
    table = data.comparison_table[data.comparison_table["Game Type"] == context].copy()
    table["Rate"] = table["clean_value"].map(pct)
    table["Team Benchmark"] = table["team_benchmark"].map(pct)
    table["vs Team"] = table["relative_to_team_pp"].map(pp)
    table["YoY"] = table["yoy_change_pp"].map(pp)
    export = table[
        ["Player", "Year", "Game Type", "Metric", "raw_value", "Rate", "data_status", "data_explanation", "Team Benchmark", "vs Team", "YoY"]
    ]
    return export


st.markdown(
    """
    <div class="dashboard-hero">
      <div class="hero-kicker">UC Berkeley Cameron Institute interview dashboard</div>
      <div class="hero-title">Golf Mental-Performance Transitions</div>
      <div class="hero-copy">
        A coach-facing view of supplied transition rates, team benchmarks, and athlete-level year-over-year patterns.
        Values are descriptive behavioral indicators, not psychological diagnoses.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

top_col1, top_col2 = st.columns([3.5, 1])
with top_col2:
    presentation_mode = st.toggle("Presentation Mode", value=True, help="Simplifies technical notes and prioritizes live-demo readability.")

context, year_mode = selected_context_controls(presentation_mode)
render_glossary(presentation_mode)

tab_team, tab_player = st.tabs(["Team Overview", "Player Explorer"])

with tab_team:
    section_intro(
        "Team Overview",
        "Start here during the interview: team movement, athlete spread, notable changes, and data-quality flags.",
    )
    render_kpi_cards(context, year_mode)

    if is_compare_mode(year_mode):
        st.plotly_chart(team_dumbbell(context), width="stretch")
        st.plotly_chart(player_metric_trend_lines(context), width="stretch")

    st.markdown("### Player Distribution")
    if is_compare_mode(year_mode):
        dist_col1, dist_col2 = st.columns([1, 3])
        with dist_col1:
            selected_year = st.radio(
                "Distribution Year",
                [2025, 2024],
                horizontal=True,
                help="Distribution uses valid supplied athlete rates only. Missing or invalid values are not treated as zero.",
            )
            dist_metric = st.selectbox("Distribution Metric", METRICS, index=0)
        with dist_col2:
            st.plotly_chart(distribution_chart(context, selected_year, dist_metric), width="stretch")
    else:
        selected_year = year_from_mode(year_mode)
        st.markdown(
            f"<div class='small-note'>Showing all four metrics for {selected_year}. Missing or invalid values are not treated as zero.</div>",
            unsafe_allow_html=True,
        )
        render_all_metric_distributions(context, selected_year)

    if is_compare_mode(year_mode):
        changes_col, notes_col = st.columns([1.45, 1])
        with changes_col:
            st.markdown("### Notable Changes")
            st.markdown("<div class='small-note'>Largest absolute movements are neutral review prompts, not athlete labels.</div>", unsafe_allow_html=True)
            st.dataframe(notable_changes(context), hide_index=True, width="stretch")
        with notes_col:
            st.markdown("### Values Needing Review")
            review = data.validation_notes[data.validation_notes["Game Type"] == context].copy()
            if review.empty:
                st.success("No missing or invalid values are flagged for this competition context.")
            else:
                st.dataframe(
                    review[["Player", "Year", "Metric", "raw_value", "data_status", "data_explanation"]],
                    hide_index=True,
                    width="stretch",
                )
    else:
        st.markdown("### Values Needing Review")
        review = data.validation_notes[
            (data.validation_notes["Game Type"] == context)
            & (data.validation_notes["Year"] == year_from_mode(year_mode))
        ].copy()
        if review.empty:
            st.success("No missing or invalid values are flagged for this year and competition context.")
        else:
            st.dataframe(
                review[["Player", "Year", "Metric", "raw_value", "data_status", "data_explanation"]],
                hide_index=True,
                width="stretch",
            )

    st.markdown("### All-Player Table")
    st.markdown(
        "<div class='small-note'>Rate, vs Team, and YoY values are formatted for coach discussion. NA values remain unavailable, not zero.</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(table_for_year_mode(context, year_mode), hide_index=True, width="stretch")

    with st.expander("Download cleaned comparison table", expanded=False):
        export = downloadable_table(context)
        st.download_button(
            "Download CSV",
            export.to_csv(index=False).encode("utf-8"),
            file_name="golf_cleaned_comparison_table.csv",
            mime="text/csv",
        )

with tab_player:
    players = sorted(data.relative[data.relative["Game Type"] == context]["Player"].unique())
    player = st.selectbox("Select Player", players, index=0)

    section_intro(
        f"{player} Snapshot",
        "Use this page to move from team-level patterns to one athlete's absolute rates, year-over-year movement, and teammate context.",
    )
    player_snapshot(player, context, year_mode)

    active_year = 2025 if is_compare_mode(year_mode) else year_from_mode(year_mode)
    if is_compare_mode(year_mode):
        st.plotly_chart(player_profile_chart(player, context), width="stretch")

    st.markdown("<div class='section-title'>Transition Detail</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-subtitle'>Blue = Tournament Only. Yellow = Tournament + Qualifying. Supplied rates are shown directly unless explicitly labeled normalized.</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(bad_hole_context_comparison_chart(player, active_year), width="stretch")

    mix_col, success_col = st.columns([1.2, 1])
    with mix_col:
        st.plotly_chart(bad_hole_context_normalized_pie(player, active_year), width="stretch")
        st.markdown(
            "<div class='small-note'>Exploratory view: denominator = Bounce Back to Birdie + Bounce Back to Par + Bogey Following Bogey.</div>",
            unsafe_allow_html=True,
        )
    with success_col:
        st.plotly_chart(success_context_comparison_chart(player, active_year), width="stretch")

    compare_col1, compare_col2 = st.columns([1, 3])
    with compare_col1:
        if is_compare_mode(year_mode):
            compare_year = st.radio("Comparison Year", [2025, 2024], horizontal=True)
        else:
            compare_year = active_year
            st.markdown(f"<div class='small-note'>Comparison year: {active_year}</div>", unsafe_allow_html=True)
        compare_metric = st.selectbox("Team Comparison Metric", METRICS, index=0)
    with compare_col2:
        st.plotly_chart(team_comparison_chart(player, context, compare_year, compare_metric), width="stretch")

    with st.expander("Data Notes for Selected Player", expanded=not presentation_mode):
        player_data_notes(player, context)

    with st.expander("Exploratory Similarity - small sample", expanded=False):
        st.markdown(
            """
            This app does not feature clustering in the main workflow. With only a small number of athletes,
            any grouping should be treated as exploratory rather than a stable player type.
            """
        )
