# ================================================================
# routes/lna_suggest.py — POST /api/lna-suggest
# Phase 8 Part B — LNA position suggester (informational only)
#
# LNA Tm is INFORMATIONAL ONLY — NOT scored or used in hard filters.
# Feature flag: USE_LNA_SUGGESTIONS (constants.py). Returns 503 if False.
# Scope: DNA primers (forward / reverse) only.
#        role="rt" → 400 (DNA:RNA context is out of scope for LNA NN model).
# ================================================================

from flask import Blueprint, jsonify, request

from algorithm.lna_tm import calc_lna_tm, suggest_lna_positions
from algorithm.thermodynamics import calculate_tm_nn
from algorithm.constants import USE_LNA_SUGGESTIONS

lna_suggest_bp = Blueprint("lna_suggest", __name__)

_DNA_BASES = set("ATGC")
_MAX_SEQUENCE_LEN = 60  # nt — LNA primers beyond this length are uncommon


@lna_suggest_bp.route("/lna-suggest", methods=["POST"])
def lna_suggest():
    """
    POST /api/lna-suggest

    Suggest optimal LNA substitution positions for a DNA primer and
    return predicted Tm values (baseline DNA and LNA-modified).

    LNA Tm is INFORMATIONAL ONLY — not scored. Verify with synthesis provider.

    Request body (JSON)
    -------------------
    {
      "sequence":  "ACGTACGT...",         # DNA 5'→3' primer sequence (A/T/G/C)
      "role":      "forward" | "reverse", # primer role; "rt" is rejected (out of scope)
      "mode":      "tm" | "discrimination",
      "target_tm": 60.0,                  # °C target Tm (required for mode="tm")
      "sibling_mismatch_positions": [3, 7],   # 0-based (mode="discrimination")
      "max_lna":   4,                     # max LNA positions (default 4)
      "params": {                         # ion conditions (all optional)
        "saltConcentration":      50.0,   # mM Na+
        "magnesiumConcentration":  1.5,   # mM Mg²+
        "dntpTotal":               0.8,   # mM total dNTP
        "primerConcentration":   200.0    # nM
      }
    }

    Response 200
    ------------
    {
      "sequence":            "ACGTACGT...",
      "role":                "forward",
      "tm_reference_primer3": 58.3,       # primer3.calc_tm for reference (DNA Tm)
      "lna_result": {
        "suggested_positions": [2, 6],
        "tm_achieved":         62.1,
        "target_met":          true,
        "search":              "exhaustive",
        "mode":                "tm",
        "discrimination_gain": 3.8,
        "warnings":            [...]
      },
      "calc_at_suggestion": {
        "tm_dna":        58.3,
        "tm_lna":        62.1,
        "delta_tm":       3.8,
        "lna_positions": [2, 6],
        "method":        ["santalucia98", "mctigue04"],
        "per_doublet":   [...],
        "warnings":      [...]
      },
      "informational_notice": "LNA Tm is informational only — not scored.",
      "warnings":            [...]
    }

    Error responses
    ---------------
    400  sequence invalid / role="rt" / missing required field
    503  USE_LNA_SUGGESTIONS toggle is False
    """
    # --- Feature flag ---
    if not USE_LNA_SUGGESTIONS:
        return jsonify({
            "error": (
                "LNA suggestion endpoint is currently disabled "
                "(USE_LNA_SUGGESTIONS=False in constants.py)."
            )
        }), 503

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    # --- Extract fields ---
    sequence  = (data.get("sequence") or "").strip().upper()
    role      = (data.get("role")     or "").strip().lower()
    mode      = (data.get("mode")     or "tm").strip().lower()
    target_tm = data.get("target_tm")
    sibling   = data.get("sibling_mismatch_positions") or []
    max_lna   = int(data.get("max_lna", 4))
    params    = data.get("params") or {}

    # --- Validate: role ---
    if role == "rt":
        return jsonify({
            "error": (
                "LNA Tm for RT primer overhang is out of scope. "
                "The LNA NN model (McTigue 2004 / Owczarzy 2011) covers "
                "DNA·LNA:DNA duplexes only. For DNA:RNA context (RT primer "
                "binding to miRNA), use the hybrid_tm module (Sugimoto 1995)."
            )
        }), 400

    if role not in ("forward", "reverse", ""):
        return jsonify({
            "error": f"Invalid role {role!r}. Must be 'forward' or 'reverse'."
        }), 400

    # --- Validate: sequence ---
    if not sequence:
        return jsonify({"error": "Field 'sequence' is required and must not be empty."}), 400

    invalid_bases = set(sequence) - _DNA_BASES
    if invalid_bases:
        return jsonify({
            "error": (
                f"Sequence contains non-DNA bases: {sorted(invalid_bases)}. "
                "Only A, T, G, C are accepted."
            )
        }), 400

    if len(sequence) > _MAX_SEQUENCE_LEN:
        return jsonify({
            "error": (
                f"Sequence length {len(sequence)} nt exceeds maximum "
                f"{_MAX_SEQUENCE_LEN} nt for LNA suggestion."
            )
        }), 400

    if len(sequence) < 2:
        return jsonify({
            "error": "Sequence must be ≥ 2 nt for nearest-neighbor calculation."
        }), 400

    # --- Validate: mode ---
    if mode not in ("tm", "discrimination"):
        return jsonify({
            "error": f"Invalid mode {mode!r}. Must be 'tm' or 'discrimination'."
        }), 400

    # --- Validate: target_tm ---
    if mode == "tm" and target_tm is None:
        return jsonify({
            "error": "Field 'target_tm' is required when mode='tm'."
        }), 400
    if target_tm is not None:
        try:
            target_tm = float(target_tm)
        except (TypeError, ValueError):
            return jsonify({"error": "'target_tm' must be a number."}), 400

    # --- Validate: max_lna ---
    if not (1 <= max_lna <= 8):
        return jsonify({
            "error": f"'max_lna' must be between 1 and 8 (got {max_lna})."
        }), 400

    # --- primer3 reference Tm (DNA, for display only) ---
    tm_reference_primer3 = None
    primer3_warning = None
    try:
        tm_reference_primer3 = round(calculate_tm_nn(sequence, params), 1)
    except Exception as exc:  # noqa: BLE001
        primer3_warning = f"primer3 reference Tm unavailable: {exc}"

    # --- Suggest LNA positions ---
    effective_target = target_tm if target_tm is not None else 60.0
    suggest_result = suggest_lna_positions(
        sequence=sequence,
        target_tm=effective_target,
        params=params,
        max_lna=max_lna,
        mode=mode,
        sibling_mismatch_positions=sibling,
    )

    # --- Compute full Tm breakdown for the suggested set ---
    suggested_pos = suggest_result.get("suggested_positions", [])
    calc_result   = calc_lna_tm(sequence, suggested_pos, params)

    # --- Assemble response warnings ---
    response_warnings: list[str] = []
    if primer3_warning:
        response_warnings.append(primer3_warning)

    return jsonify({
        "sequence":             sequence,
        "role":                 role or "unspecified",
        "tm_reference_primer3": tm_reference_primer3,
        "lna_result":           suggest_result,
        "calc_at_suggestion":   calc_result,
        "informational_notice": (
            "LNA Tm values are informational only — not used in scoring "
            "or primer filtering. Verify with synthesis provider."
        ),
        "warnings": response_warnings,
    }), 200
