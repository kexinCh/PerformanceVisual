from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

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
REQUIRED_SOURCE_COLUMNS = ["Player", "Game Type", *METRICS]
VALID_GAME_TYPES = set(GAME_TYPE_LABELS)


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


@dataclass(frozen=True)
class UploadValidation:
    raw_wide: pd.DataFrame
    errors: list[str]
    warnings: list[str]
    filename_year: int | None = None
    sheet_years: list[int] = field(default_factory=list)
    year_conflicts: list[str] = field(default_factory=list)
    needs_manual_year: bool = False

    @property
    def is_valid(self) -> bool:
        return not self.errors


def extract_year(sheet_name: str) -> int | None:
    match = re.search(r"(20\d{2})", str(sheet_name))
    return int(match.group(1)) if match else None


def clean_source_columns(columns: list[str]) -> list[str]:
    return [SOURCE_COLUMN_MAP.get(str(col).strip(), str(col).strip()) for col in columns]


def available_years(raw_wide: pd.DataFrame) -> list[int]:
    if "Year" not in raw_wide.columns:
        return []
    years = pd.to_numeric(raw_wide["Year"], errors="coerce").dropna().astype(int)
    return sorted(years.unique().tolist())


def infer_year_from_name(name: str) -> int | None:
    return extract_year(name)


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


def _clean_frame(frame: pd.DataFrame, source_name: str, year: int | None) -> pd.DataFrame:
    cleaned = frame.copy()
    cleaned.columns = clean_source_columns(list(cleaned.columns))
    if year is not None:
        cleaned["Year"] = year
    elif "Year" not in cleaned.columns:
        cleaned["Year"] = year
    cleaned["Source Sheet"] = source_name
    return cleaned


def _year_resolution_for_sheet(
    filename_year: int | None,
    sheet_name: str,
    selected_year: int | None,
) -> tuple[int | None, int | None, str | None]:
    sheet_year = extract_year(sheet_name) if filename_year is None else None
    if filename_year is not None:
        actual_sheet_year = extract_year(sheet_name)
        conflict = (
            f"{sheet_name}: filename {filename_year}, sheet {actual_sheet_year}"
            if actual_sheet_year is not None and actual_sheet_year != filename_year
            else None
        )
        return selected_year if selected_year is not None else filename_year, actual_sheet_year, conflict
    return selected_year if selected_year is not None else sheet_year, sheet_year, None


def _frame_has_relevant_columns(frame: pd.DataFrame) -> bool:
    cleaned_cols = set(clean_source_columns(list(frame.columns)))
    return bool(cleaned_cols & set(REQUIRED_SOURCE_COLUMNS))


def load_uploaded_dataset(
    uploaded_file: BinaryIO,
    filename: str,
    selected_year: int | None = None,
) -> tuple[pd.DataFrame, int | None, list[int], list[str], bool]:
    suffix = Path(filename).suffix.lower()
    filename_year = infer_year_from_name(filename)
    sheet_years: list[int] = []
    year_conflicts: list[str] = []
    needs_manual_year = False

    if suffix == ".csv":
        frame = pd.read_csv(uploaded_file)
        year = selected_year if selected_year is not None else filename_year
        if year is None and "Year" in clean_source_columns(list(frame.columns)):
            cleaned_for_year = frame.copy()
            cleaned_for_year.columns = clean_source_columns(list(cleaned_for_year.columns))
            years = available_years(cleaned_for_year)
            if len(years) == 1:
                year = years[0]
        needs_manual_year = bool(year is None)
        return _clean_frame(frame, filename, year), filename_year, sheet_years, year_conflicts, needs_manual_year

    if suffix in {".xlsx", ".xlsm", ".xls"}:
        excel = pd.ExcelFile(uploaded_file)
        frames = []
        for sheet_name in excel.sheet_names:
            sheet = pd.read_excel(excel, sheet_name=sheet_name)
            if not _frame_has_relevant_columns(sheet):
                continue
            year, sheet_year, conflict = _year_resolution_for_sheet(filename_year, sheet_name, selected_year)
            if sheet_year is not None:
                sheet_years.append(sheet_year)
            if conflict is not None:
                year_conflicts.append(conflict)
            frames.append(_clean_frame(sheet, sheet_name, year))
        if not frames:
            return pd.DataFrame(), filename_year, sorted(set(sheet_years)), year_conflicts, False
        raw_wide = pd.concat(frames, ignore_index=True)
        needs_manual_year = bool(raw_wide["Year"].isna().any())
        return raw_wide, filename_year, sorted(set(sheet_years)), year_conflicts, needs_manual_year

    raise ValueError("Upload must be a .xlsx or .csv file.")


def _validation_row_label(row: pd.Series) -> str:
    player = row.get("Player", "Unknown athlete")
    year = row.get("Year", "Unknown year")
    game_type = row.get("Game Type", "Unknown context")
    return f"{player} / {year} / {game_type}"


def validate_raw_wide(raw_wide: pd.DataFrame) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if raw_wide.empty:
        return ["No relevant dataset rows were found in the uploaded file."], warnings

    missing_columns = [column for column in REQUIRED_SOURCE_COLUMNS if column not in raw_wide.columns]
    if missing_columns:
        errors.append("Missing required columns: " + ", ".join(missing_columns) + ".")
        return errors, warnings

    df = raw_wide.copy()
    df["Player"] = df["Player"].where(df["Player"].notna(), np.nan)
    df.loc[df["Player"].notna(), "Player"] = df.loc[df["Player"].notna(), "Player"].astype(str).str.strip()
    df["Game Type"] = df["Game Type"].where(df["Game Type"].notna(), np.nan)
    df.loc[df["Game Type"].notna(), "Game Type"] = df.loc[df["Game Type"].notna(), "Game Type"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

    missing_players = df["Player"].isna() | (df["Player"] == "")
    if missing_players.any():
        errors.append(f"{int(missing_players.sum())} row(s) are missing athlete names.")

    unknown_game_types = sorted(
        game_type for game_type in df["Game Type"].dropna().unique() if game_type not in VALID_GAME_TYPES
    )
    if unknown_game_types:
        errors.append("Unknown Game Type values: " + ", ".join(map(str, unknown_game_types)) + ".")

    athlete_rows = df[(df["Player"].notna()) & (df["Player"] != "") & (df["Player"] != "Team Averages")].copy()
    duplicate_mask = athlete_rows.duplicated(["Player", "Year", "Game Type"], keep=False)
    if duplicate_mask.any():
        duplicates = athlete_rows.loc[duplicate_mask, ["Player", "Year", "Game Type"]].drop_duplicates()
        labels = [_validation_row_label(row) for _, row in duplicates.iterrows()]
        errors.append("Duplicate athlete/year/game-type records: " + "; ".join(labels) + ".")

    for metric in METRICS:
        numeric = pd.to_numeric(athlete_rows[metric], errors="coerce")
        supplied = athlete_rows[metric].notna()
        invalid_nonnumeric = supplied & numeric.isna()
        if invalid_nonnumeric.any():
            labels = [_validation_row_label(row) for _, row in athlete_rows.loc[invalid_nonnumeric].iterrows()]
            errors.append(f"{metric} has nonnumeric values for: " + "; ".join(labels) + ".")
        invalid_negative = numeric < 0
        if invalid_negative.any():
            labels = [_validation_row_label(row) for _, row in athlete_rows.loc[invalid_negative].iterrows()]
            errors.append(f"{metric} has negative rate values for: " + "; ".join(labels) + ".")
        invalid_over_range = numeric > 1
        if invalid_over_range.any():
            labels = [_validation_row_label(row) for _, row in athlete_rows.loc[invalid_over_range].iterrows()]
            errors.append(f"{metric} has rate values above 1 for: " + "; ".join(labels) + ".")

    context_counts = (
        athlete_rows[athlete_rows["Game Type"].isin(VALID_GAME_TYPES)]
        .groupby(["Player", "Year"])["Game Type"]
        .agg(lambda values: set(values))
    )
    for (player, year), contexts in context_counts.items():
        if "Tournament + Qualifying" in contexts and "Tournament" not in contexts:
            warnings.append(f"{player} has {int(year)} Tournament + Qualifying data but no Tournament-only data.")
        if "Tournament" in contexts and "Tournament + Qualifying" not in contexts:
            warnings.append(f"{player} has {int(year)} Tournament-only data but no Tournament + Qualifying data.")

    return errors, warnings


def validate_uploaded_dataset(
    uploaded_file: BinaryIO,
    filename: str,
    selected_year: int | None = None,
) -> UploadValidation:
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    raw_wide, filename_year, sheet_years, year_conflicts, needs_manual_year = load_uploaded_dataset(
        uploaded_file,
        filename,
        selected_year=selected_year,
    )
    if needs_manual_year and selected_year is None:
        return UploadValidation(
            raw_wide=raw_wide,
            errors=[],
            warnings=[],
            filename_year=filename_year,
            sheet_years=sheet_years,
            year_conflicts=year_conflicts,
            needs_manual_year=True,
        )
    errors, warnings = validate_raw_wide(raw_wide)
    return UploadValidation(
        raw_wide=raw_wide,
        errors=errors,
        warnings=warnings,
        filename_year=filename_year,
        sheet_years=sheet_years,
        year_conflicts=year_conflicts,
        needs_manual_year=bool(needs_manual_year),
    )


def build_tidy(raw_wide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw_wide.copy()
    df["Player"] = df["Player"].astype(str).str.strip()
    df["Game Type"] = df["Game Type"].where(df["Game Type"].notna(), np.nan)
    df.loc[df["Game Type"].notna(), "Game Type"] = (
        df.loc[df["Game Type"].notna(), "Game Type"].astype(str).str.strip()
    )
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")

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

    years = sorted(pd.to_numeric(relative["Year"], errors="coerce").dropna().astype(int).unique())
    pairs = [(start, end) for idx, start in enumerate(years) for end in years[idx + 1 :]]
    rows = []
    for _, row in pivot.iterrows():
        for start_year, end_year in pairs:
            start_value = row.get(f"clean_value_{start_year}", np.nan)
            end_value = row.get(f"clean_value_{end_year}", np.nan)
            start_relative = row.get(f"relative_to_team_pp_{start_year}", np.nan)
            end_relative = row.get(f"relative_to_team_pp_{end_year}", np.nan)
            rows.append(
                {
                    "Player": row["Player"],
                    "Game Type": row["Game Type"],
                    "Metric": row["Metric"],
                    "start_year": start_year,
                    "end_year": end_year,
                    "start_clean_value": start_value,
                    "end_clean_value": end_value,
                    "start_relative_to_team_pp": start_relative,
                    "end_relative_to_team_pp": end_relative,
                    "yoy_change_pp": end_value - start_value,
                    "relative_position_change_pp": end_relative - start_relative,
                }
            )
    return pd.DataFrame(rows)


def build_comparison_table(relative: pd.DataFrame, yoy: pd.DataFrame) -> pd.DataFrame:
    if yoy.empty:
        out = relative.copy()
        out["yoy_change_pp"] = np.nan
        out["relative_position_change_pp"] = np.nan
        return out
    latest_end_year = yoy["end_year"].max()
    latest = yoy[yoy["end_year"] == latest_end_year].sort_values("start_year").drop_duplicates(
        ["Player", "Game Type", "Metric"], keep="last"
    )
    out = relative.merge(
        latest[["Player", "Game Type", "Metric", "yoy_change_pp", "relative_position_change_pp"]],
        on=["Player", "Game Type", "Metric"],
        how="left",
    )
    return out


def process_raw_wide(raw_wide: pd.DataFrame) -> ProcessedData:
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


def process_workbook(path: str | Path) -> ProcessedData:
    raw_wide, _sheet_inventory = load_workbook(path)
    return process_raw_wide(raw_wide)


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
