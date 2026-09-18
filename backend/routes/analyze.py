# ================================================================
# routes/analyze.py — POST /api/analyze
#
# Manual primer-set analyzer. The user pastes the THREE primers of a
# stem-loop RT-qPCR assay (RT / forward / universal reverse) plus the
# mature miRNA, and we compute the scientific parameters WITHOUT running
# the design pipeline (no candidate generation, no V4 scoring).
#
# Reuses the exact same thermodynamic engines as /api/design so numbers
# are consistent across the two pages:
#   - Tm            : primer3-py SantaLucia 1998 NN (thermodynamics.py)
#   - hairpin/dimer : primer3-py thermo-alignment (structure_check)
#   - RT hybrid Tm  : Sugimoto 1995 DNA:RNA NN (hybrid_tm.py)
#
# BLAST off-target and LNA-Tm are intentionally NOT run here — the frontend
# calls the existing /api/blast-check and /api/lna-suggest endpoints
# on-demand (they are heavy / optional).
# ================================================================

from flask import Blueprint, jsonify, request

from algorithm.sequence_utils import (
    calculate_gc, calculate_gc_skew, check_homopolymer, check_gc_clamp,
    rna_to_dna, reverse_complement,
)
from algorithm.thermodynamics import calculate_tm_nn, calculate_end_stability
from algorithm.structure_check import (
    _get_p3_params, _check_hairpin, _check_self_dimer, _check_hetero_dimer,
)
from algorithm.hybrid_tm import predict_hybrid_tm
from algorithm.constants import (
    UNIVERSAL_REVERSE, STEMLOOP_BODY, OVERHANG_LENGTH_DEFAULT,
    P3_RT_MV_CONC, USE_HYBRID_TM, MAX_HOMOPOLYMER_RUN,
)

analyze_bp = Blueprint("analyze", __name__)

_DNA_BASES = set("ATGC")
_MAX_PRIMER_LEN = 80   # RT primer is ~50 nt; allow headroom


# ── Validation helpers ────────────────────────────────────────────

def _clean_dna(raw: str) -> str:
    """Uppercase, strip whitespace, convert any U→T (tolerate RNA paste)."""
    return (raw or "").upper().strip().replace("U", "T").replace(" ", "")


def _validate_dna(seq: str, label: str) -> str | None:
    """Return an error string, or None if the DNA primer is valid."""
    if not seq:
        return f"{label} is required."
    if len(seq) < 2:
        return f"{label} is too short ({len(seq)} nt) — need ≥ 2 nt."
    if len(seq) > _MAX_PRIMER_LEN:
        return f"{label} is too long ({len(seq)} nt) — max {_MAX_PRIMER_LEN} nt."
    bad = set(seq) - _DNA_BASES
    if bad:
        return f"{label} contains non-DNA bases: {', '.join(sorted(bad))}. Only A, T, G, C (U auto-converted)."
    return None


# ── Per-primer intrinsic analysis ─────────────────────────────────

def _analyze_single(seq: str, role: str, p3: dict, temp_c: float, params: dict) -> dict:
    """Intrinsic parameters for one primer. `role` ∈ {rt, forward, reverse}."""
    hairpin = _check_hairpin(seq, p3, temp_c)
    self_dimer = _check_self_dimer(seq, p3, temp_c)
    gc_ok, gc_reason = check_gc_clamp(seq)
    last5 = seq[-5:] if len(seq) >= 5 else seq

    result = {
        "role": role,
        "sequence": seq,
        "length": len(seq),
        "gc_percent": calculate_gc(seq),
        "gc_skew": calculate_gc_skew(seq),
        "tm_nn": round(calculate_tm_nn(seq, params), 1),
        "tm_chemistry": "DNA:DNA",
        "end_stability_3prime": calculate_end_stability(last5, params),
        "hairpin": hairpin,
        "self_dimer": self_dimer,
        "homopolymer_run": check_homopolymer(seq, MAX_HOMOPOLYMER_RUN),
        "gc_clamp": {"pass": gc_ok, "reason": gc_reason, "last5": last5},
    }

    # RT primer: the full-primer DNA:DNA Tm is only indicative — the primer is
    # a hairpin whose 3' 6 nt overhang anneals to the miRNA (a DNA:RNA hybrid).
    if role == "rt":
        result["tm_note"] = (
            "Full-primer Tm uses DNA:DNA NN (SantaLucia 1998) and is indicative only. "
            "The RT primer is a hairpin; its 3' overhang anneals to the miRNA as a "
            "DNA:RNA hybrid — see the context section for the Sugimoto 1995 hybrid Tm."
        )
    return result


# ── Cross-dimer matrix ────────────────────────────────────────────

def _cross_dimer(seq1: str, seq2: str, label: str, p3: dict, temp_c: float) -> dict:
    hd = _check_hetero_dimer(seq1, seq2, p3, temp_c)
    hd["pair"] = label
    return hd


# ── Context checks against the mature miRNA ───────────────────────

def _context_checks(rt: str, fwd: str, rev: str, mature_rna: str) -> dict:
    """Sanity-check the pasted primers against the mature miRNA they target."""
    mature_dna = rna_to_dna(mature_rna).upper()
    ctx: dict = {"provided": True}

    # 1. Universal reverse identity ---------------------------------
    matches_rev = rev == UNIVERSAL_REVERSE
    ctx["reverse_universal"] = {
        "matches": matches_rev,
        "canonical": UNIVERSAL_REVERSE,
        "note": (
            "Reverse primer matches the canonical universal reverse "
            f"(5'-{UNIVERSAL_REVERSE}-3')."
            if matches_rev else
            "Reverse primer differs from the canonical universal reverse "
            f"(5'-{UNIVERSAL_REVERSE}-3'). Stem-loop RT-qPCR shares one fixed "
            "reverse primer across all assays — verify this is intentional."
        ),
    }

    # 2. RT 3' overhang binding -------------------------------------
    #    Expected: last 6 nt of RT == reverse_complement(DNA of miRNA 3' 6 nt)
    n = OVERHANG_LENGTH_DEFAULT
    expected_rc = reverse_complement(mature_dna[-n:])
    observed = rt[-n:] if len(rt) >= n else rt
    match_count = sum(1 for a, b in zip(observed, expected_rc) if a == b)
    overhang_ok = observed == expected_rc

    hybrid = predict_hybrid_tm(observed, dna_conc_nM=4000.0, mv_conc_mM=float(P3_RT_MV_CONC)) \
        if USE_HYBRID_TM else None

    ctx["rt_overhang"] = {
        "expected": expected_rc,
        "observed": observed,
        "matches": overhang_ok,
        "match_count": match_count,
        "overhang_length": n,
        "starts_with_stemloop_body": rt.startswith(STEMLOOP_BODY),
        "hybrid_tm_c": (hybrid or {}).get("tm_c"),
        "hybrid_method": (hybrid or {}).get("method"),
        "note": (
            f"RT 3' overhang ({observed}) is the reverse-complement of the miRNA 3' "
            f"end — anneals correctly ({match_count}/{n} nt)."
            if overhang_ok else
            f"RT 3' overhang ({observed}) does not fully match the expected "
            f"reverse-complement of the miRNA 3' end ({expected_rc}); "
            f"{match_count}/{n} nt pair. A mismatched overhang reduces RT priming."
        ),
    }

    # 3. Forward specific anchoring ---------------------------------
    #    The forward primer is [synthetic tail] + [miRNA 5' specific region].
    #    Its 3' portion should be a prefix of the miRNA (as DNA).
    matched_len = 0
    for L in range(min(len(fwd), len(mature_dna)), 0, -1):
        if fwd.endswith(mature_dna[:L]):
            matched_len = L
            break
    # The specific region should anchor on the miRNA 5' end (~12–17 nt) and stop
    # short of the last 6 nt reserved for the RT overhang.
    max_specific = max(len(mature_dna) - OVERHANG_LENGTH_DEFAULT, 0)
    tail_len = max(len(fwd) - matched_len, 0)
    anchors_ok = matched_len >= 10
    overlaps_overhang = matched_len > max_specific

    if not anchors_ok:
        note = (
            f"Forward primer 3' end matches only {matched_len} nt of the miRNA 5' region. "
            "The specific region should be ~12–17 nt of the miRNA 5' end — verify the primer "
            "targets this miRNA."
        )
    elif overlaps_overhang:
        note = (
            f"Forward primer 3' end matches {matched_len} nt of the miRNA, extending into the "
            f"3' {OVERHANG_LENGTH_DEFAULT} nt reserved for the RT overhang. Forward and RT "
            "primers may compete for the same 3' region — verify the specific region stops short."
        )
    else:
        note = (
            f"Forward primer 3' end matches the miRNA 5' region over {matched_len} nt "
            f"(synthetic tail ≈ {tail_len} nt). Specific region anchors on the mature miRNA "
            "as expected."
        )

    ctx["forward_anchor"] = {
        "matched_len": matched_len,
        "matched_seq": mature_dna[:matched_len],
        "tail_len": tail_len,
        "within_expected": anchors_ok and not overlaps_overhang,
        "max_specific": max_specific,
        "note": note,
    }

    return ctx


# ── Route ─────────────────────────────────────────────────────────

@analyze_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    POST /api/analyze

    Request body
    ------------
    {
      "primers": {
        "rt":      "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGAC...",
        "forward": "GCGGCGGTAGCTTATCAGACTG",
        "reverse": "CCAGTGCAGGGTCCGAGGTA"
      },
      "matureSequence": "UAGCUUAUCAGACUGAUGUUGA",
      "mirnaId": "hsa-miR-21-5p",         # optional (echoed; used by BLAST on the client)
      "params": { "saltConcentration": 50, "magnesiumConcentration": 1.5,
                  "dntpTotal": 0.8, "primerConcentration": 200,
                  "annealingTemp": 60 }   # all optional
    }

    Response 200: { primers:{rt,forward,reverse}, cross_dimers:[...],
                    context:{...}, meta:{...} }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    primers = data.get("primers") or {}
    rt  = _clean_dna(primers.get("rt"))
    fwd = _clean_dna(primers.get("forward"))
    rev = _clean_dna(primers.get("reverse"))

    for seq, label in ((rt, "RT primer"), (fwd, "Forward primer"), (rev, "Reverse primer")):
        err = _validate_dna(seq, label)
        if err:
            return jsonify({"error": err}), 400

    # Mature miRNA is required (context checks are the point of this page).
    mature = (data.get("matureSequence") or "").upper().strip()
    if not mature:
        return jsonify({"error": "matureSequence (mature miRNA) is required."}), 400
    bad_rna = set(mature) - set("AUGCT")
    if bad_rna:
        return jsonify({
            "error": f"matureSequence contains invalid characters: {', '.join(sorted(bad_rna))}. "
                     "Use RNA bases A, U, G, C."
        }), 400
    if not (15 <= len(mature) <= 30):
        return jsonify({
            "error": f"matureSequence length {len(mature)} nt is outside the accepted range "
                     "(15–30 nt). Canonical mature miRNAs are 17–24 nt."
        }), 400

    # Drop null / blank / NaN condition fields so the module defaults apply.
    # (An emptied numeric input on the client serialises to JSON null; passing
    #  float(None) into the thermo engine would otherwise raise a 500.)
    params = {
        k: v for k, v in (data.get("params") or {}).items()
        if v is not None
        and not (isinstance(v, str) and not v.strip())
        and not (isinstance(v, float) and v != v)  # NaN
    }
    p3 = _get_p3_params(params)
    try:
        temp_c = float(params.get("annealingTemp", 60.0))
    except (TypeError, ValueError):
        temp_c = 60.0

    # ── Per-primer intrinsic metrics ──────────────────────────────
    primer_results = {
        "rt":      _analyze_single(rt,  "rt",      p3, temp_c, params),
        "forward": _analyze_single(fwd, "forward", p3, temp_c, params),
        "reverse": _analyze_single(rev, "reverse", p3, temp_c, params),
    }

    # ── Cross-dimer matrix (all 3 pairs) ──────────────────────────
    cross_dimers = [
        _cross_dimer(rt,  fwd, "RT × Forward",      p3, temp_c),
        _cross_dimer(rt,  rev, "RT × Reverse",      p3, temp_c),
        _cross_dimer(fwd, rev, "Forward × Reverse", p3, temp_c),
    ]

    # ── Context checks vs the mature miRNA ────────────────────────
    context = _context_checks(rt, fwd, rev, mature)

    return jsonify({
        "primers": primer_results,
        "cross_dimers": cross_dimers,
        "context": context,
        "meta": {
            "mirna_id": (data.get("mirnaId") or "").strip(),
            "mature_sequence": mature,
            "annealing_temp_c": temp_c,
            "params_used": {
                "mv_conc_mM":  p3["mv_conc"],
                "dv_conc_mM":  p3["dv_conc"],
                "dntp_mM":     p3["dntp_conc"],
                "primer_nM":   p3["dna_conc"],
            },
            "method_notes": [
                "Tm: primer3-py nearest-neighbor (SantaLucia 1998).",
                "Hairpin / dimer ΔG: primer3-py thermodynamic alignment.",
                "RT overhang hybrid Tm: Sugimoto 1995 DNA:RNA NN (informational).",
                "BLAST off-target and LNA Tm are run on-demand (separate buttons).",
            ],
        },
    }), 200
