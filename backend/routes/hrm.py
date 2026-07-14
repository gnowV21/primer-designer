"""
routes/hrm.py — POST /api/hrm/analyze [SPEC_Phase1 §4, §6].

Accepts a melt-curve file (CSV/TSV/XLS/XLSX), runs the full pipeline, and returns:
  * `features`  — the NUMERIC TABLE (§4.3). This is the only HRM data the LLM ever sees.
  * `curves`    — normalized / derivative / difference series, FOR DISPLAY ONLY (§4.3).
  * `session_id`— handed to /api/chat so the answer can be grounded in these numbers.

The chart is never an input to analysis. Every number comes from Python [§0].
"""

from flask import Blueprint, jsonify, request

from hrm import auto_detect, derivative, difference, features, loader, normalizer, session
from rag import prompt

hrm_bp = Blueprint("hrm", __name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB — a melt-curve export is a few hundred KB
ALLOWED_EXT = (".csv", ".tsv", ".txt", ".xls", ".xlsx")


@hrm_bp.route("/hrm/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({
            "error":   "No file uploaded.",
            "message": "Attach a melt-curve file as the 'file' form field "
                       "(CSV/TSV/XLS/XLSX with a temperature column and one column per well).",
        }), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected."}), 400
    if not f.filename.lower().endswith(ALLOWED_EXT):
        return jsonify({
            "error":   "Unsupported file type.",
            "message": f"Allowed extensions: {', '.join(ALLOWED_EXT)}",
        }), 400

    # Size check without trusting Content-Length.
    f.stream.seek(0, 2)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        return jsonify({
            "error":   "File too large.",
            "message": f"Maximum upload size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        }), 413

    # Optional overrides; when absent, T_pre/T_post are auto-detected.
    T_pre        = _opt_float(request.form.get("T_pre"))
    T_post       = _opt_float(request.form.get("T_post"))
    positive_col = (request.form.get("positive_control") or "").strip() or None
    smoothing    = (request.form.get("smoothing", "true").lower() != "false")

    warnings: list[str] = []

    try:
        # ── 1. Load + clean ──────────────────────────────────────────────────
        df_raw = loader.load_melt_file(f)

        # ── 2. Baseline temperatures ─────────────────────────────────────────
        if T_pre is None or T_post is None:
            detected   = auto_detect.auto_detect_temps(df_raw)
            T_pre      = detected["T_pre"]  if T_pre  is None else T_pre
            T_post     = detected["T_post"] if T_post is None else T_post
            confidence = detected["confidence"]
            if confidence == "low":
                warnings.append(
                    f"Auto-detected T_pre={T_pre} C / T_post={T_post} C with LOW "
                    "confidence. Check the normalized curve and override them if it looks wrong."
                )
        else:
            confidence = "user"

        # ── 3. Normalize (bilinear) ──────────────────────────────────────────
        df_norm, norm_warnings = normalizer.bilinear_normalize(df_raw, T_pre, T_post)
        warnings.extend(norm_warnings)

        # ── 4. Derivative — on RAW data, per derivative.py: the -dF/dT peak is Tm
        #      and is independent of normalization.
        df_deriv = derivative.compute_derivative(df_raw, smoothing=smoothing)

        # ── 5. Numeric features — the table handed to the LLM ────────────────
        feat = features.extract_features(df_raw, df_deriv, positive_col=positive_col)

        # ── 6. Difference curve vs the positive control (display only) ───────
        diff_payload = None
        ref = feat["positive_control"]
        if ref and ref in df_norm.columns:
            df_diff, diff_warnings = difference.compute_difference(df_norm, ref_col=ref)
            warnings.extend(diff_warnings)
            diff_payload = {
                c: df_diff[c].tolist() for c in df_diff.columns if c != "Temp"
            }
        else:
            warnings.append(
                "No positive control column found, so no difference curve and no "
                "delta-Tm was computed. Name a column 'positive_ctrl' to enable them."
            )

    except (ValueError, RuntimeError) as exc:
        # Bad data / bad parameters — the message is written to be shown to the user.
        return jsonify({"error": "HRM analysis failed.", "message": str(exc)}), 400

    sample_cols = [c for c in df_deriv.columns if c != "Temp"]

    # The canonical question for each well, generated in ONE place [rag.prompt.question_for_well].
    # The frontend used to build its own wording for a row click while the backend built another
    # for the follow-up chips; the two never matched, so the chip row re-offered the question the
    # user had just asked. Shipping the string with the data removes the second generator.
    for name, f in feat["features"].items():
        f["question"] = prompt.question_for_well(name, f)

    payload = {
        "features":         feat["features"],
        "positive_control": feat["positive_control"],
        "negative_control": feat["negative_control"],
        "samples":          sample_cols,
        "params": {
            "T_pre": T_pre, "T_post": T_post,
            "confidence": confidence, "smoothing": smoothing,
        },
        "warnings": warnings,
        # Display only — SPEC_Phase1 §4.3: curves are never an analysis input.
        "curves": {
            "temp":       df_deriv["Temp"].tolist(),
            "normalized": {c: df_norm[c].tolist()   for c in df_norm.columns   if c != "Temp"},
            "derivative": {c: df_deriv[c].tolist()  for c in sample_cols},
            "difference": diff_payload,
        },
    }

    # Persist only the numbers — the curves are big and the LLM must never see them.
    payload["session_id"] = session.save({
        "features":         feat["features"],
        "positive_control": feat["positive_control"],
        "negative_control": feat["negative_control"],
        "params":           payload["params"],
    })

    return jsonify(payload)


def _opt_float(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None
