from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


METRICS = [
    "Bounce Back to Par",
    "Bogey Following Bogey",
    "Bounce Back to Birdie",
    "Reverse Bounce Back",
]

METRIC_DEFINITIONS = {
    "Bounce Back to Par": "Bogey or worse -> Par",
    "Bogey Following Bogey": "Bogey or worse -> Bogey or worse",
    "Bounce Back to Birdie": "Bogey or worse -> Birdie or better",
    "Reverse Bounce Back": "Birdie or better -> Bogey or worse",
}

SOURCE_COLUMN_MAP = {
    "Name": "Player",
    "Game Type": "Game Type",
    "Bounce Back To Par": "Bounce Back to Par",
    "Bounce Back to Par": "Bounce Back to Par",
    "Bogie Following Bogie": "Bogey Following Bogey",
    "Bogey Following Bogey": "Bogey Following Bogey",
    "Bounce Back To Bridie": "Bounce Back to Birdie",
    "Bounce Back To Birdie": "Bounce Back to Birdie",
    "Bounce Back to Birdie": "Bounce Back to Birdie",
    "Reverse Bounce Back": "Reverse Bounce Back",
}

GAME_TYPE_LABELS = {
    "Tournament": "Tournament Only",
    "Tournament + Qualifying": "Tournament + Qualifying",
}

LABEL_TO_GAME_TYPE = {v: k for k, v in GAME_TYPE_LABELS.items()}


@dataclass(frozen=True)
class ProcessedData:
    raw_wide: pd.DataFrame
    tidy: pd.DataFrame
    wide_valid: pd.DataFrame
    team_benchmark: pd.DataFrame
    relative: pd.DataFrame
    yoy: pd.DataFrame
    validation_notes: pd.DataFrame
    comparison_table: pd.DataFrame


def extract_year(sheet_name: str) -> int | None:
    match = re.search(r"(20\d{2})", str(sheet_name))
    return int(match.group(1)) if match else None


def clean_source_columns(columns: list[str]) -> list[str]:
    return [SOURCE_COLUMN_MAP.get(str(col).strip(), str(col).strip()) for col in columns]


def validate_value(raw_value: object) -> tuple[float | None, str, str]:
    if pd.isna(raw_value):
        return np.nan, "missing", "NA - no observation was provided for this athlete/year/context."

    value = pd.to_numeric(raw_value, errors="coerce")
    if pd.isna(value):
        return np.nan, "invalid_nonnumeric", "NA - source value is nonnumeric and was excluded from derived comparisons."
    if value < 0:
        return np.nan, "invalid_negative", "NA - source value is negative and was excluded from derived comparisons."
    if value > 1:
        return np.nan, "invalid_over_range", "NA - source value is above 1 and was excluded from derived comparisons."

    return float(value), "valid", "Valid supplied rate."


def load_workbook(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = Path(path)
    workbook_source = path
    if not path.exists():
        b64_path = Path(str(path) + ".b64")
        if not b64_path.exists():
            raise FileNotFoundError(f"Could not find {path} or {b64_path}")
        workbook_source = io.BytesIO(base64.b64decode(b64_path.read_text().strip()))

    excel = pd.ExcelFile(workbook_source)
    frames = []
    sheet_inventory = []

    for sheet_name in excel.sheet_names:
        sheet = pd.read_excel(workbook_source, sheet_name=sheet_name)
        sheet_inventory.append(
            {
                "sheet_name": sheet_name,
                "shape": sheet.shape,
                "columns": list(sheet.columns),
                "dtypes": {col: str(dtype) for col, dtype in sheet.dtypes.items()},
            }
        )
        sheet.columns = clean_source_columns(list(sheet.columns))
        sheet["Year"] = extract_year(sheet_name)
        sheet["Source Sheet"] = sheet_name
        frames.append(sheet)

    raw_wide = pd.concat(frames, ignore_index=True)
    return raw_wide, pd.DataFrame(sheet_inventory)


def build_tidy(raw_wide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw_wide.copy()
    df["Player"] = df["Player"].astype(str).str.strip()
    df["Game Type"] = df["Game Type"].where(df["Game Type"].notna(), np.nan)
    df.loc[df["Game Type"].notna(), "Game Type"] = (
        df.loc[df["Game Type"].notna(), "Game Type"].astype(str).str.strip()
    )

    athlete_wide = df[(df["Player"] != "Team Averages") & df["Game Type"].notna()].copy()
    metric_cols = [metric for metric in METRICS if metric in athlete_wide.columns]

    tidy = athlete_wide.melt(
        id_vars=["Player", "Year", "Game Type", "Source Sheet"],
        value_vars=metric_cols,
        var_name="Metric",
        value_name="raw_value",
    )

    validated = tidy["raw_value"].apply(validate_value)
    tidy[["clean_value", "data_status", "data_explanation"]] = pd.DataFrame(
        validated.tolist(), index=tidy.index
    )
    tidy["Metric"] = pd.Categorical(tidy["Metric"], categories=METRICS, ordered=True)

    validation_notes = tidy[tidy["data_status"] != "valid"].copy()
    return tidy, validation_notes


def build_wide_valid(tidy: pd.DataFrame) -> pd.DataFrame:
    wide = tidy.pivot_table(
        index=["Player", "Year", "Game Type"],
        columns="Metric",
        values="clean_value",
        aggfunc="first",
        observed=False,
    ).reset_index()
    wide.columns.name = None
    return wide


def build_team_benchmark(tidy: pd.DataFrame) -> pd.DataFrame:
    valid = tidy[tidy["data_status"] == "valid"].copy()
    bench = (
        valid.groupby(["Year", "Game Type", "Metric"], observed=False)
        .agg(
            team_benchmark=("clean_value", "mean"),
            median=("clean_value", "median"),
            minimum=("clean_value", "min"),
            maximum=("clean_value", "max"),
            q1=("clean_value", lambda x: x.quantile(0.25)),
            q3=("clean_value", lambda x: x.quantile(0.75)),
            std_dev=("clean_value", "std"),
            valid_athletes=("Player", "nunique"),
        )
        .reset_index()
    )
    bench["benchmark_label"] = "Average Athlete Rate"
    return bench


def build_relative(tidy: pd.DataFrame, team_benchmark: pd.DataFrame) -> pd.DataFrame:
    rel = tidy.merge(
        team_benchmark[["Year", "Game Type", "Metric", "team_benchmark"]],
        on=["Year", "Game Type", "Metric"],
        how="left",
    )
    rel["relative_to_team_pp"] = rel["clean_value"] - rel["team_benchmark"]
    return rel


def build_yoy(relative: pd.DataFrame) -> pd.DataFrame:
    pivot = relative.pivot_table(
        index=["Player", "Game Type", "Metric"],
        columns="Year",
        values=["clean_value", "relative_to_team_pp"],
        aggfunc="first",
        observed=False,
    )
    pivot.columns = [f"{measure}_{year}" for measure, year in pivot.columns]
    pivot = pivot.reset_index()

    for col in [
        "clean_value_2024",
        "clean_value_2025",
        "relative_to_team_pp_2024",
        "relative_to_team_pp_2025",
    ]:
        if col not in pivot.columns:
            pivot[col] = np.nan

    pivot["yoy_change_pp"] = pivot["clean_value_2025"] - pivot["clean_value_2024"]
    pivot["relative_position_change_pp"] = (
        pivot["relative_to_team_pp_2025"] - pivot["relative_to_team_pp_2024"]
    )
    return pivot


def build_comparison_table(relative: pd.DataFrame, yoy: pd.DataFrame) -> pd.DataFrame:
    out = relative.merge(
        yoy[
            [
                "Player",
                "Game Type",
                "Metric",
                "yoy_change_pp",
                "relative_position_change_pp",
            ]
        ],
        on=["Player", "Game Type", "Metric"],
        how="left",
    )
    return out


def process_workbook(path: str | Path) -> ProcessedData:
    raw_wide, _sheet_inventory = load_workbook(path)
    tidy, validation_notes = build_tidy(raw_wide)
    wide_valid = build_wide_valid(tidy)
    team_benchmark = build_team_benchmark(tidy)
    relative = build_relative(tidy, team_benchmark)
    yoy = build_yoy(relative)
    comparison_table = build_comparison_table(relative, yoy)
    return ProcessedData(
        raw_wide=raw_wide,
        tidy=tidy,
        wide_valid=wide_valid,
        team_benchmark=team_benchmark,
        relative=relative,
        yoy=yoy,
        validation_notes=validation_notes,
        comparison_table=comparison_table,
    )


def pct(value: float | None) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value * 100:.1f}%"


def pp(value: float | None) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value * 100:+.1f} pp"


def pp_neutral(value: float | None) -> str:
    if pd.isna(value):
        return "NA"
    direction = "above" if value > 0 else "below" if value < 0 else "at"
    return f"{abs(value) * 100:.1f} pp {direction} team benchmark"
