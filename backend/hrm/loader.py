"""
loader.py — read an uploaded melt-curve file into a clean DataFrame
[SPEC_Phase1 §4.1, and the "unusual HRM format" risk in §9].

Ported from the existing hrm-tool project; algorithm unchanged, messages translated.

Handles the messy reality of instrument exports:
  * metadata / title rows above the real header (data start is auto-detected)
  * NaN in the temperature column  -> those rows are dropped
  * NaN in sample columns          -> linear interpolation
  * non-monotonic temperature      -> sorted ascending, duplicates averaged
  * CSV with any common separator  (, ; tab |)

The first numeric column becomes 'Temp'; every other column is a sample well.
"""

import io

import numpy as np
import pandas as pd


def load_melt_file(file_obj) -> pd.DataFrame:
    """Load .xlsx / .xls / .csv into a validated DataFrame with a 'Temp' column."""
    filename = getattr(file_obj, "filename", None) or getattr(file_obj, "name", "") or ""
    raw = _read_raw(file_obj, filename)   # no header assumption yet
    df  = _find_and_parse(raw)            # locate the header row, parse numerics
    df  = _clean(df)                      # NaN / sort / interpolate
    _validate(df)
    return df


# ── Step 1: raw bytes -> DataFrame (header not yet resolved) ────────────────

def _read_raw(file_obj, filename: str) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        return _read_csv_raw(file_obj)

    if ext != "xls":
        try:
            file_obj.seek(0)
            return pd.read_excel(file_obj, engine="openpyxl", header=None)
        except Exception:
            pass

    try:
        file_obj.seek(0)
        return pd.read_excel(file_obj, engine="xlrd", header=None)
    except Exception:
        pass

    try:
        file_obj.seek(0)
        return _read_csv_raw(file_obj)
    except Exception as exc:
        raise ValueError(
            f"Could not read the file. Supported formats: .xlsx, .xls, .csv. Details: {exc}"
        )


def _read_csv_raw(file_obj) -> pd.DataFrame:
    file_obj.seek(0)
    raw = file_obj.read()
    file_obj.seek(0)

    text = None
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = raw.decode(enc) if isinstance(raw, bytes) else raw
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Could not decode the CSV file. Re-save it with UTF-8 encoding.")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("The file is empty or contains no data.")

    # Pick the separator that occurs most often across the file, not just in line 1:
    # line 1 is usually an instrument title row ("Melt Curve Export") that may contain
    # no separator at all, or a different one than the data block.
    sep = max([",", ";", "\t", "|"], key=lambda s: sum(ln.count(s) for ln in lines))
    if sum(ln.count(sep) for ln in lines) == 0:
        sep = ","

    # Instrument exports are RAGGED: title/metadata rows carry fewer fields than the
    # data rows below them. pandas infers the column count from the first line and
    # then raises "Expected N fields, saw M" on the wider data rows. Pinning the
    # column count to the WIDEST row makes the short rows pad with NaN instead —
    # and _find_and_parse() discards them anyway once it locates the header.
    n_cols = max(ln.count(sep) for ln in lines) + 1

    return pd.read_csv(
        io.StringIO(text),
        sep=sep,
        header=None,
        names=range(n_cols),
        engine="python",   # the C parser cannot take `names` wider than the first row
    )


# ── Step 2: find the header row and the data block ─────────────────────────

def _find_and_parse(raw: pd.DataFrame) -> pd.DataFrame:
    """
    1. Find the first COLUMN holding finite numbers (skips leading empty columns).
    2. In that column, find the first ROW holding a number -> data start.
    3. The row immediately above it (if any) is the header row.
    4. Drop every column left of the temperature column (metadata / blanks).
    """
    if raw.empty:
        raise ValueError("The file is empty or contains no data.")

    temp_col_idx = None
    for col_idx in range(len(raw.columns)):
        if any(_is_number(v) for v in raw.iloc[:, col_idx]):
            temp_col_idx = col_idx
            break

    if temp_col_idx is None:
        raise ValueError(
            "No numeric data found in the file. Make sure it contains a temperature "
            "column with real numbers."
        )

    first_data_row = next(
        row_idx
        for row_idx, val in enumerate(raw.iloc[:, temp_col_idx])
        if _is_number(val)
    )

    if first_data_row > 0:
        headers = [str(v).strip() for v in raw.iloc[first_data_row - 1, temp_col_idx:]]
    else:
        headers = None

    data_block = raw.iloc[first_data_row:, temp_col_idx:].reset_index(drop=True)
    data_block.columns = range(len(data_block.columns))

    if headers is not None:
        data_block.columns = headers
    else:
        n = len(data_block.columns)
        data_block.columns = ["Temp"] + [f"Col{i}" for i in range(1, n)]

    first_col = data_block.columns[0]
    if first_col != "Temp":
        data_block = data_block.rename(columns={first_col: "Temp"})

    for col in data_block.columns:
        data_block[col] = pd.to_numeric(data_block[col], errors="coerce")

    return data_block


def _is_number(val) -> bool:
    try:
        return np.isfinite(float(val))
    except (TypeError, ValueError):
        return False


# ── Step 3: clean ──────────────────────────────────────────────────────────

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    # A NaN temperature cannot be interpolated (it IS the x-axis) — drop the row.
    before = len(df)
    df = df.dropna(subset=["Temp"]).reset_index(drop=True)
    if len(df) == 0:
        raise ValueError(
            f"After dropping {before} row(s) with a missing temperature, no valid data "
            "remained. Check the file structure."
        )

    if not df["Temp"].is_monotonic_increasing:
        df = df.sort_values("Temp").reset_index(drop=True)

    if df["Temp"].duplicated().any():
        df = df.groupby("Temp", as_index=False).mean()

    sample_cols = [c for c in df.columns if c != "Temp"]
    for col in sample_cols:
        if df[col].isna().any():
            df[col] = df[col].interpolate(method="linear", limit_direction="both")

    # Columns still entirely NaN after interpolation were never populated.
    all_nan = [c for c in sample_cols if df[c].isna().all()]
    if all_nan:
        df = df.drop(columns=all_nan)

    return df.dropna().reset_index(drop=True)


# ── Step 4: validate ───────────────────────────────────────────────────────

def _validate(df: pd.DataFrame) -> None:
    if len(df) < 10:
        raise ValueError(
            f"Too little data: only {len(df)} valid row(s) remained after cleaning. "
            "At least 10 are required."
        )
    if len([c for c in df.columns if c != "Temp"]) < 1:
        raise ValueError("At least one sample column is required besides the temperature column.")
