# ================================================================
# visualization/coordinates.py — PART A: cDNA coordinate model (CORE)
#
# Implements SPEC_visualization §A.3 exactly. This module computes SEQUENCES and
# GEOMETRY only — it never designs primers, never scores, never recomputes Tm.
# Sequence helpers come from algorithm.sequence_utils (not reimplemented).
#
# Biology (SPEC §A.1), 5 stages:
#   0 Components · 1 RT annealing · 2 RT product (cDNA) ·
#   3 PCR cycle 1 (forward) · 4 PCR cycle 2+ (universal) → stable amplicon
# ================================================================

from dataclasses import dataclass, field
import logging

from algorithm.sequence_utils import rna_to_dna, reverse_complement, calculate_gc
from algorithm.constants import (
    STEMLOOP_BODY_LENGTH, UNIVERSAL_REVERSE,
    AMPLICON_MIN_QPCR, AMPLICON_MAX_QPCR,
    OVERHANG_LENGTH_MIN, OVERHANG_LENGTH_MAX,
)
from .constants import (
    REGION_TAIL, REGION_MIRNA, REGION_STEMLOOP, REGION_UNIVERSAL,
    REGION_COLOR_TOKEN,
)

_log = logging.getLogger(__name__)


# ── Errors ────────────────────────────────────────────────────────────────────

class VisualizationError(Exception):
    """Assertion A1–A6 failure (SPEC §A.4). The route maps this to HTTP 422."""

    def __init__(self, error_code: str, detail: str, expected=None, actual=None):
        super().__init__(detail)
        self.error_code = error_code
        self.detail = detail
        self.expected = expected
        self.actual = actual

    def to_dict(self) -> dict:
        d = {"error_code": self.error_code, "detail": self.detail}
        if self.expected is not None:
            d["expected"] = self.expected
        if self.actual is not None:
            d["actual"] = self.actual
        return d


# ── Data model ──────────────────────────────────────────────────────────────

@dataclass
class Region:
    """One of the 4 amplicon regions (SPEC §A.5). Contiguous, non-overlapping."""
    start: int
    end: int
    name: str
    color_token: str

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class Strand:
    """A sequence bar in one reaction stage."""
    sequence: str
    direction: str            # '5to3' | '3to5'
    offset_nt: int            # column offset for renderer alignment
    region_tag: str | None    # region name for colouring, or None for composite bars


@dataclass
class Stage:
    """One reaction stage (SPEC §A.1 / §B.1)."""
    id: int
    label_en: str
    strands: list             # list[Strand]; when a stage pairs bases, strands[0]
                              #   (top) pairs with strands[1] (bottom)
    pairings: list            # list[tuple[int, int]] — (index in strands[0],
                              #   index in strands[1]); empty when none
    annotation_en: str
    synthesis_direction: str | None = None   # 'left' | 'right' | None (arrow hint)


@dataclass
class AmpliconModel:
    mirna_dna: str
    stemloop_body: str
    overhang: str
    stemloop_rt: str
    forward: str
    tail: str
    forward_binding_length: int
    universal_reverse: str
    cdna: str
    sense_strand: str
    amplicon: str
    universal_offset: int      # j
    regions: list              # list[Region] (exactly 4)
    stages: list               # list[Stage] (exactly 5)
    gc_percent: float
    size_warning: bool


# ── Builder ───────────────────────────────────────────────────────────────────

def build_amplicon_model(
    mirna_sequence: str,
    stemloop_rt: str,
    forward: str,
    forward_binding_length: int,
    universal_reverse: str,
) -> AmpliconModel:
    """
    Build the amplicon coordinate model per SPEC §A.3.

    All sequences are provided by /api/design; this only computes coordinates.
    Raises VisualizationError (A1–A6) on structural inconsistency; A7 (size)
    only sets model.size_warning and logs a WARNING.
    """
    m = rna_to_dna(mirna_sequence).upper()
    L = len(m)
    S = stemloop_rt.upper()
    F = forward.upper()
    U = universal_reverse.upper()
    k = int(forward_binding_length)

    # A1 — RT primer architecture: 44 nt body + 5–7 nt overhang (49–51 nt).
    # The overhang length is read from the primer, not assumed.
    o = len(S) - STEMLOOP_BODY_LENGTH
    if not (OVERHANG_LENGTH_MIN <= o <= OVERHANG_LENGTH_MAX):
        raise VisualizationError(
            "RT_PRIMER_LENGTH",
            f"Stem-loop RT primer must be {STEMLOOP_BODY_LENGTH + OVERHANG_LENGTH_MIN}–"
            f"{STEMLOOP_BODY_LENGTH + OVERHANG_LENGTH_MAX} nt ({STEMLOOP_BODY_LENGTH} body + "
            f"{OVERHANG_LENGTH_MIN}–{OVERHANG_LENGTH_MAX} nt overhang).",
            expected=f"{STEMLOOP_BODY_LENGTH + OVERHANG_LENGTH_MIN}..{STEMLOOP_BODY_LENGTH + OVERHANG_LENGTH_MAX}",
            actual=len(S),
        )
    overhang = S[-o:]
    body = S[:-o]

    # A2 — overhang matches reverse complement of miRNA 3' end
    expected_overhang = reverse_complement(m[-o:])
    if overhang != expected_overhang:
        raise VisualizationError(
            "OVERHANG_MISMATCH",
            "RT overhang does not match the reverse complement of the miRNA 3' end.",
            expected=expected_overhang, actual=overhang,
        )

    # A4 — forward binding length in the fixed 12–17 nt window (checked before A3,
    # which slices by k)
    if not (12 <= k <= 17):
        raise VisualizationError(
            "FORWARD_BINDING_RANGE",
            "Forward binding length k must be 12–17 nt (SPEC_week1 §1).",
            expected="12..17", actual=k,
        )

    # A3 — forward 3' binding region matches the miRNA 5' end
    if F[-k:] != m[:k]:
        raise VisualizationError(
            "FORWARD_BINDING_MISMATCH",
            "Forward primer 3' binding region does not match the miRNA 5' end.",
            expected=m[:k], actual=F[-k:],
        )

    tail = F[: len(F) - k]

    # §A.3 formulas
    ext = reverse_complement(m[: L - o])   # RT-synthesized complement
    cdna = S + ext                                    # len = 44 + L
    sense = tail + m + reverse_complement(body)       # cycle-1 strand

    rc_u = reverse_complement(U)

    # A5 — universal site occurs exactly once
    occurrences = sense.count(rc_u)
    if occurrences != 1:
        raise VisualizationError(
            "UNIVERSAL_SITE_AMBIGUOUS",
            "Universal reverse primer site must occur exactly once in the cycle-1 strand.",
            expected=1, actual=occurrences,
        )
    j = sense.index(rc_u)
    amplicon = sense[: j + len(U)]

    # A6 — universal site must not intrude into the miRNA region
    if not (len(tail) + L <= j):
        raise VisualizationError(
            "REGION_OVERLAP",
            "Universal primer site overlaps the miRNA region.",
            expected=f">= {len(tail) + L}", actual=j,
        )

    # A7 — amplicon size: WARNING only, does not block (SPEC §A.4)
    size_warning = not (AMPLICON_MIN_QPCR <= len(amplicon) <= AMPLICON_MAX_QPCR)
    if size_warning:
        _log.warning(
            "A7 amplicon size out of qPCR range: len=%d, allowed=[%d, %d] — "
            "constants/pipeline mismatch upstream.",
            len(amplicon), AMPLICON_MIN_QPCR, AMPLICON_MAX_QPCR,
        )

    # Four regions (SPEC §A.5) — contiguous, non-overlapping
    regions = [
        Region(0,             len(tail),        REGION_TAIL,      REGION_COLOR_TOKEN[REGION_TAIL]),
        Region(len(tail),     len(tail) + L,    REGION_MIRNA,     REGION_COLOR_TOKEN[REGION_MIRNA]),
        Region(len(tail) + L, j,                REGION_STEMLOOP,  REGION_COLOR_TOKEN[REGION_STEMLOOP]),
        Region(j,             j + len(U),       REGION_UNIVERSAL, REGION_COLOR_TOKEN[REGION_UNIVERSAL]),
    ]

    gc_percent = round(calculate_gc(amplicon), 1)

    stages = _build_stages(m, L, S, body, overhang, F, tail, k, ext, cdna, sense, U, j)

    return AmpliconModel(
        mirna_dna=m,
        stemloop_body=body,
        overhang=overhang,
        stemloop_rt=S,
        forward=F,
        tail=tail,
        forward_binding_length=k,
        universal_reverse=U,
        cdna=cdna,
        sense_strand=sense,
        amplicon=amplicon,
        universal_offset=j,
        regions=regions,
        stages=stages,
        gc_percent=gc_percent,
        size_warning=size_warning,
    )


def _build_stages(m, L, S, body, overhang, F, tail, k, ext, cdna, sense, U, j) -> list:
    """Build the 5 reaction stages (SPEC §A.1). Sequences/directions/pairings are
    logical; pixel layout is PART B's job."""

    # Stage 0 — components
    stage0 = Stage(
        id=0,
        label_en="Components",
        strands=[
            Strand(m, "5to3", 0, None),
            Strand(S, "5to3", 0, None),
            Strand(F, "5to3", 0, None),
            Strand(U, "5to3", 0, None),
        ],
        pairings=[],
        annotation_en="Mature miRNA and three primers: stem-loop RT, forward, and universal reverse.",
    )

    # Stage 1 — RT annealing. miRNA on top (5'→3'); stem-loop RT below (3'→5') so the
    # overhang aligns antiparallel under the miRNA 3' end. overhang[i] = S[44+i]
    # pairs with m[L-1-i]; RT extends the S 3' end leftward (toward the miRNA 5' end).
    stage1_pairings = [(L - 1 - i, len(body) + i) for i in range(len(overhang))]
    stage1 = Stage(
        id=1,
        label_en="RT annealing",
        strands=[
            Strand(m, "5to3", 0, REGION_MIRNA),
            Strand(S, "3to5", 0, REGION_STEMLOOP),
        ],
        pairings=stage1_pairings,
        annotation_en=(
            "The stem-loop RT primer folds back; only its "
            f"{len(overhang)}-nt 3' overhang is exposed and "
            "anneals antiparallel to the miRNA 3' end. Reverse transcriptase extends the "
            "primer 3' end leftward, copying the miRNA toward its 5' end."
        ),
        synthesis_direction="left",
    )

    # Stage 2 — RT product (cDNA) shown as two segments: intact S + new extension.
    stage2 = Stage(
        id=2,
        label_en="RT product (cDNA)",
        strands=[
            Strand(S, "5to3", 0, REGION_STEMLOOP),
            Strand(ext, "5to3", len(S), None),
        ],
        pairings=[],
        annotation_en=(
            f"cDNA = intact stem-loop RT primer ({len(S)} nt) plus the newly synthesized "
            f"complement of the miRNA ({len(ext)} nt)."
        ),
    )

    # Stage 3 — PCR cycle 1. cDNA is the template (3'→5' on top); forward primer below
    # (5'→3'); its 5' GC tail has no template (dashed in the renderer). Forward specific
    # base m[i] (F index len(F)-k+i) pairs with cDNA index len(cdna)-1-i.
    stage3_pairings = [(len(cdna) - 1 - i, len(F) - k + i) for i in range(k)]
    stage3 = Stage(
        id=3,
        label_en="PCR cycle 1 (forward primer)",
        strands=[
            Strand(cdna, "3to5", 0, None),
            Strand(F, "5to3", 0, REGION_TAIL),
            Strand(sense, "5to3", 0, None),
        ],
        pairings=stage3_pairings,
        annotation_en=(
            f"The forward primer anneals to the cDNA 3' end via its {k}-nt specific region "
            f"(the miRNA 5' end); its 5' GC tail overhangs with no template. Polymerase "
            "extends rightward, producing the cycle-1 strand."
        ),
        synthesis_direction="right",
    )

    # Stage 4 — PCR cycle 2+. Universal primer binds the cycle-1 strand at [j, j+len(U));
    # product stops at the primer 5' end, fixing the stable amplicon. U[i] pairs with
    # sense[j + len(U) - 1 - i].
    stage4_pairings = [(j + len(U) - 1 - i, i) for i in range(len(U))]
    stage4 = Stage(
        id=4,
        label_en="PCR cycle 2+ (universal reverse)",
        strands=[
            Strand(sense, "5to3", 0, None),
            Strand(U, "3to5", j, REGION_UNIVERSAL),
        ],
        pairings=stage4_pairings,
        annotation_en=(
            "The universal reverse primer binds the cycle-1 strand; synthesis stops at the "
            "primer 5' end. From here every molecule shares the same length — the stable amplicon."
        ),
        synthesis_direction="right",
    )

    return [stage0, stage1, stage2, stage3, stage4]
