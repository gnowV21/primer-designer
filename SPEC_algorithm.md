# SPEC_algorithm.md — HG Lab Stem-loop RT-qPCR Primer Designer
# Tài liệu thuật toán hợp nhất — Phase 2 + Phase 3
# Phiên bản: 3.1 (bug fixes 2026-07-03) — Ngày gốc: 2026-07-02

---

## CHANGELOG

### Lịch sử phiên bản Phase 2 (tóm tắt, nguồn gốc `SPEC_phase2.md`)

| Phiên bản | Thay đổi chính |
|---|---|
| v2.0 | Base spec: 8-criterion scoring (SCORING_WEIGHTS), 4 structure checks |
| v2.1 | BUG FIX dNTP 0.2→0.8 mM; DNA_CONC 250→200 nM; MAX_LENGTH 30→27 nt; GC_CLAMP_MIN_IN_LAST3=2 |
| v2.2 | MAX_HOMOPOLYMER_RUN 4→5; GC_MAX_IN_3PRIME_WINDOW=5; P3_THERMODYNAMIC_OLIGO_ALIGNMENT=True |
| v2.3–2.6 | Section K (probe constants); Penalty weights (Section M); Advanced Seq. tab (Section N) |
| v2.7 | Insights từ literature [K11][C05][V07][PAST24]; SCORING_WEIGHTS_V3 (11 tiêu chí: thêm gc_skew) |
| v2.8 | 4 Core Fixes: tail generation exhaustive, Tm real NN, MFE 3-tier fallback, amplicon exact formula |
| v2.8.1 | 8 bug fixes từ code review (MFE sign error, binding Tm target 35→45°C, diversity filter, pool bias...) |
| v2.8.2 | Specificity Module: heterodimer (fwd×stemloop + fwd×rev), family_crossreactivity, isomir_flag |
| v2.8.3 | Tm caching (lru_cache); URev self-structure check; gc_clamp criterion 12 → SCORING_WEIGHTS_V3 |

### v3.1 — Bug fixes (2026-07-03)

| Mã | File | Loại | Mô tả |
|---|---|---|---|
| B1 | `routes/design.py` | Bug | `detect_edge_cases()` gọi sau early-return 422 → edge_cases không có trong error response |
| B2 | `constants.py` | Calibration | `LOW_COMPLEXITY_TOP2_PCT 60→70%` — 60% quá thấp cho AT-rich miRNA |
| B3 | `routes/export.py` | Security | `_sanitize()` không collapse `..` → thêm `re.sub(r"\.\.+", "_")` |

---

### Lịch sử phiên bản Phase 3 (tóm tắt, nguồn gốc `SPEC_phase3.md`)

| Phiên bản | Thay đổi chính |
|---|---|
| v1.0–1.2 | Bound fraction 2-step; family discrimination via miFam.dat; đính chính [SL07]→[SL04] |
| v1.3 | BLAST risk classification (Ye 2012 + Kwok 1990 3'-terminal mismatch table) |
| v1.4 | Kiến trúc: cache SQLite, circuit breaker, rate limit, CI/CD, smoke test |
| v1.5 | Quyết định: primer3-py `calc_heterodimer(seq, revcomp(seq))` để lấy dH/dS; storage ~2 MB (miRBase only) |
| v1.6 | Frontend: hook `useBlastCheck`, `OffTargetPanel`, error handling 429/503/timeout |
| v1.7 | [SL04] đính chính journal; RT temp Round 1 = 42°C (không phải 60°C); miFam.dat HTTP 500 → seed-based grouping |
| v1.8 | Gap fix: stemloop RT × universal reverse heterodimer (one-step RT-qPCR) |
| v1.9 | Loại Ensembl khỏi BLAST (miRBase only); bound fraction recalibrate (Ta=55°C, MIN/OPT=60/80%); self-hit precursor variants; SCORING_WEIGHTS_V4 rebalance |
| v2.0 | Code review fixes: DB unavailable raises FileNotFoundError; `_is_self_hit` word-boundary; regex `[12]`→`\d+`; parallel BLAST |
| v2.1 | Spec consistency fixes: stale pseudocode, Ensembl refs, vestigial geometric check, HTTP 503 spec |

### Phase 3 thay đổi gì so với Phase 2 (summary)

1. **Scoring**: V3 (12 tiêu chí) → **V4.1 (15 tiêu chí)** bằng cách thêm `bound_fraction_binding`, `bound_fraction_full`, `family_discrimination`. V3 được đánh dấu **DEPRECATED** nhưng giữ trong `constants.py` làm reference.
2. **Structure checks**: Phase 3 §5/§6 (family + isoMiR) mở rộng §30/§31 của Phase 2 với data thật (không còn PLACEHOLDER).
3. **BLAST off-target**: Module hoàn toàn mới, endpoint riêng `/api/blast-check`, không ảnh hưởng pipeline `/api/design`.
4. **Bound fraction**: Phase 3 implement công thức [SL04] với 2 bước (binding tại 42°C và full tại 55°C), không còn là "để dành Phase 3" như Phase 2.
5. **Đính chính [SL07]→[SL04]**: SantaLucia & Hicks 2004, Annual Review of Biophysics — không phải 2007.
6. **BLAST database**: miRBase only (~2 MB) sau khi loại Ensembl (v1.9).
7. **stemloop×reverse heterodimer**: Phase 2 §29 check fwd×stemloop và fwd×reverse; Phase 3 v1.8 thêm stemloop×reverse (one-step RT-qPCR gap).

---

## §0 Hướng dẫn cho Claude Code [Both]

- Đây là tài liệu thuật toán DUY NHẤT — không cần đọc SPEC_phase2.md hoặc SPEC_phase3.md.
- Implement theo thứ tự §7 → §8 → §9 → §10 → §11 → §12 → §13 → §14 → §15 → §16.
- Chạy unit test sau mỗi module trước khi chuyển sang module tiếp theo.
- Ưu tiên tuyệt đối: (1) Tính đúng khoa học → (2) Tốc độ < 5s (`/api/design`) → (3) Giải thích rõ ràng → (4) UI đẹp.
- All user-facing strings: **English only**.
- Mỗi constant phải có comment nguồn trích dẫn — không để số "magic".
- Trước mỗi `git commit`: chạy Superpower security check.
- Sau mỗi thay đổi UI có ý nghĩa: chạy Playwright E2E test liên quan.
- Không phá vỡ Phase 2: `SCORING_WEIGHTS_V3` giữ lại làm reference; `SCORING_WEIGHTS_V4` là active version.

---

## §1 Tổng quan thuật toán [Both]

### Mục tiêu
Khi người dùng nhấn "Design Primers", backend nhận formData, chạy thuật toán thiết kế 3 primer cho stem-loop RT-qPCR, trả về Top 3 bộ primer có score cao nhất kèm breakdown điểm từng tiêu chí. Tùy chọn: check off-target qua BLAST.

### Cơ sở khoa học
Stem-loop RT-qPCR (Chen et al. 2005): thiết kế 3 primer cho định lượng mature miRNA:
- **Stemloop RT primer**: cấu trúc kẹp tóc 44 nt + 6 nt overhang bổ sung đầu 3' miRNA
- **Forward primer**: 12–17 nt từ đầu 5' miRNA + 5' tail GC-rich để nâng Tm
- **Universal reverse primer**: `5'-CCAGTGCAGGGTCCGAGGTA-3'` (cố định, dùng chung cho mọi assay)

### Flow `/api/design` — 8 bước tuần tự

```
[Frontend formData]
        ↓
[§1.1. validate_input()]
        Kiểm tra sequence RNA hợp lệ, độ dài, ký tự
        ↓
[§1.2. design_stemloop_rt()]      [Phase 2]
        1 primer duy nhất, MFE bằng ViennaRNA
        ↓
[§1.3. get_universal_reverse()]   [Phase 2]
        Fixed sequence — chỉ return constants + self-structure check
        ↓
[§1.4. generate_forward_candidates()]   [Phase 2]
        Pool exhaustive/weighted-random, ~4000–6000 tails
        2-step Tm: binding region Tm → full primer Tm (SantaLucia 1998 NN)
        ↓
[§1.5. prefilter_candidates()]    [Phase 2]
        Loại: Tm ngoài range, GC ngoài range, homopolymer >5, amplicon out-of-range,
               GC clamp fail, GC end window fail, diversity distance
        Log rejection reasons
        ↓
[§1.6. check_structures()]        [Phase 2 + Phase 3]
        Hairpin ΔG, self-dimer ΔG (overall + 3'), hetero-dimer ΔG (fwd×stemloop RT buffer,
        fwd×reverse PCR buffer), 3' end stability ΔG
        ↓
[§1.7. score_candidates()]        [Phase 2 V3 → Phase 3 V4.1 — 15 tiêu chí]
        + bound_fraction_binding (0.05)  [Phase 3]
        + bound_fraction_full    (0.03)  [Phase 3]
        + family_discrimination  (0.05)  [Phase 3]
        Rank → chọn Top 3
        ↓
[§1.8. format_output()]           [Phase 2 + Phase 3]
        JSON đầy đủ: Top 3 + stemloop + reverse + rejection_log + metadata
        + isomir_flag annotation (warning-only) [Phase 3]
        + stemloop×reverse heterodimer [Phase 3 v1.8]
```

### Flow `/api/blast-check` — async, optional [Phase 3]

```
[User bấm "Check off-target"]
        ↓
[Rate limit check: 10 req/phút/IP]
        ↓
[Cache lookup: SQLite by hash(fwd + rev + db_version), TTL 30 ngày]
     HIT →  Trả cache ngay
     MISS → [Circuit breaker check]
                ↓ (CLOSED)
            [blastn subprocess vs miRBase multi-species]
                ↓
            [NW global alignment realign (Ye 2012)]
                ↓
            [Risk classification (Ye 2012 + Kwok 1990)]
                ↓
            [Write cache → Trả về]
```

### Thời gian mục tiêu

```
/api/design:
    Validate:              < 0.1s
    Stem-loop RT design:   < 0.3s  (ViennaRNA MFE)
    Generate candidates:   < 0.5s
    Pre-filter:            < 0.2s
    Structure checks:      < 2.5s  (primer3-py)
    Scoring + Phase 3:     < 0.7s  (với Tm cache)
    TOTAL TARGET:          < 4.5s  (trong ngân sách <5s)

/api/blast-check:
    Cache hit:             < 0.05s
    Cache miss:            < 30s
```

---

## §2 Nguồn tham chiếu các thông số [Both]

| Ký hiệu | Nguồn |
|---|---|
| [P3P] | Primer3Plus defaults (primer3plus.com) |
| [P3GS] | Primer3Plus General Settings tab |
| [P3AS] | Primer3Plus Advanced Settings tab |
| [P3IO] | Primer3Plus Internal Oligo tab |
| [IDT] | IDT OligoAnalyzer guidelines |
| [IDT-TQ] | IDT TaqMan qPCR probe design rules |
| [IDT-PQ] | IDT PrimerQuest custom design parameters |
| [Kramer] / [K11] | Kramer et al. 2011, Curr. Protoc. Mol. Biol. Unit 15.10 |
| [RNA13] | Kramer et al. 2013, RNA Journal — Universal TaqMan probe |
| [SL98] | SantaLucia 1998, PNAS — nearest-neighbor thermodynamics |
| [SL04] | SantaLucia & Hicks 2004, Annual Review of Biophysics 33:415-440 — bound fraction formula. **Đính chính:** SPEC_phase2.md ký hiệu nhầm là [SL07]. |
| [Chen05] / [C05] | Chen et al. 2005, NAR — stem-loop RT-qPCR foundational paper |
| [R2] | Report 2 (tài liệu kỹ thuật nội bộ HG Lab) |
| [PAST24] | PrimerAST 2024 (PMC13172444) |
| [Kor07] | Koressaar & Remm 2007, Bioinformatics — Primer3 divalent correction |
| [V07] | Varkonyi-Gasic et al. 2007, Plant Methods — forward primer design |
| [Ye12] | Ye et al. 2012, BMC Bioinformatics 13:134 — Primer-BLAST |
| [Kwok90] | Kwok et al. 1990, NAR 18(4):999-1005 — 3'-terminal mismatch types |
| [Neilsen12] | Neilsen et al. 2012, Trends in Genetics 28(11):544-549 — isomiR profiling |
| [Morin08] | Morin et al. 2008, Genome Research — isomiR discovery |
| [miRBase] | miRBase database, mature.fa multi-species |
| [miFam] | miRBase miFam.dat (HTTP 500 từ v22.1 — production dùng seed-based grouping) |

---

## §3 Thư viện và cài đặt [Both]

### requirements.txt

```
# Phase 1 — giữ nguyên
flask==3.0.3
flask-cors==4.0.1
requests==2.31.0

# Phase 2 — thêm
primer3-py==2.0.3
# Dùng cho: Tm NN [SL98], hairpin ΔG, self-dimer ΔG, hetero-dimer ΔG, 3' end stability ΔG
# KHÔNG dùng Wallace formula

ViennaRNA==2.6.4
# Dùng cho: MFE của stem-loop hairpin (RNA.fold) — gold standard RNA secondary structure

biopython==1.83
# Dùng cho: reverse_complement(), NW alignment

numpy==1.26.4
# Dùng cho: scoring calculations

# Phase 3 — thêm
flask-limiter>=3.5.0    # rate limiting /api/blast-check
# blastn: binary BLAST+ — KHÔNG cài qua pip
```

### Cài ViennaRNA (C library bắt buộc)

```bash
# Ubuntu/Debian:
sudo apt-get install -y libRNA-dev
pip install ViennaRNA --break-system-packages

# macOS:
brew install viennarna
pip install ViennaRNA --break-system-packages
```

### Cài Local BLAST+ (Phase 3)

```bash
# Ubuntu/Debian:
sudo apt-get install -y ncbi-blast+
blastn -version && makeblastdb -version
```

---

## §4 Cấu trúc thư mục [Both]

```
backend/
├── app.py
├── requirements.txt
├── routes/
│   ├── mirbase.py                             ← Phase 1, giữ nguyên
│   ├── design.py                              ← Phase 2, cập nhật Phase 3
│   └── blast_check.py                         ← MỚI Phase 3 §16
├── algorithm/
│   ├── __init__.py
│   ├── constants.py                           ← MỌI hằng số khoa học
│   ├── sequence_utils.py                      ← §5
│   ├── stemloop_rt.py                         ← §7
│   ├── forward_primer.py                      ← §8
│   ├── universal_reverse.py                   ← §9
│   ├── thermodynamics.py                      ← §10
│   ├── structure_check.py                     ← §11
│   ├── scoring.py                             ← §12 (V4.1 active)
│   ├── bound_fraction.py                      ← §13 [Phase 3]
│   └── specificity_check/
│       ├── __init__.py
│       ├── heterodimer.py                     ← §11.2 [Phase 2 v2.8.2]
│       ├── family_crossreactivity.py          ← §14 [Phase 2 §30 + Phase 3 §5]
│       ├── isomir_flag.py                     ← §15 [Phase 2 §31 + Phase 3 §6]
│       ├── blast_offtarget.py                 ← §16 [Phase 3]
│       └── blast_cache.py                     ← §20.1 [Phase 3]
├── data/
│   ├── mirbase_family_overhangs.json          ← build từ seed-based grouping (§14.5)
│   ├── known_5prime_isomir_mirnas.json        ← v1.0.0 verified (§15.1)
│   ├── blast_cache.sqlite                     ← runtime cache
│   └── blast_db/
│       ├── mirbase_multi.{nhr,nin,nsq}        ← BLAST index miRBase mature.fa
│       └── metadata.json                      ← version + build_date
├── scripts/
│   ├── build_family_db.py                     ← §14.5
│   └── build_blast_db.py                      ← §20.5
└── utils/
    ├── local_db.py                            ← Phase 1 (refactor thành SQLiteKVCache)
    ├── sqlite_kv_cache.py                     ← Phase 3 base class
    └── circuit_breaker.py                     ← Phase 1, reuse Phase 3
```

---

## §5 Constants (algorithm/constants.py) [Both]

### Section A: Stem-loop RT Primer

```python
# [Chen05] — cấu trúc gốc 44 nt, Varkonyi-Gasic 2007 confirm
STEMLOOP_BODY = "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGAC"
STEMLOOP_BODY_LENGTH = 44

# [Chen05] — 6 nt tối ưu cho steric hindrance vs pre-miRNA
OVERHANG_LENGTH_DEFAULT = 6
OVERHANG_LENGTH_MIN = 4
OVERHANG_LENGTH_MAX = 8

# [R2] — MFE sweet spot: đủ bền để base stacking, không quá bền cho PCR
# DNA proxy (primer3-py):
MFE_STEMLOOP_MIN = -13.0     # kcal/mol
MFE_STEMLOOP_MAX = -10.0     # kcal/mol
MFE_STEMLOOP_OPTIMAL = -11.5  # kcal/mol
# RNA model (ViennaRNA/RNAfold):
MFE_STEMLOOP_MIN_RNA     = -35.0
MFE_STEMLOOP_MAX_RNA     = -20.0
MFE_STEMLOOP_OPTIMAL_RNA = -26.0

# [K11] RT primer concentration:
RT_PRIMER_CONC_OPTIMAL = 1.0    # nM — Kramer optimized (not 50 nM Chen 2005)
RT_PRIMER_CONC_CHEN_2005 = 50.0  # nM — deprecated
```

### Section B: Universal Reverse Primer

```python
# [K11] improved 20nt vs [C05] original 16nt
UNIVERSAL_REVERSE = "CCAGTGCAGGGTCCGAGGTA"
UNIVERSAL_REVERSE_TM_PRECALC = 60.4   # °C
UNIVERSAL_REVERSE_GC_PRECALC = 65.0   # %
UNIVERSAL_REVERSE_CHEN_2005 = "GTGCAGGGTCCGAGGT"  # 16 nt — reference only
```

### Section C: Forward Primer Design

```python
# [K11] 12–17 nt (không phải 10–12 từ Phase 2 v2.0)
FORWARD_SPECIFIC_LENGTH_MIN = 12
FORWARD_SPECIFIC_LENGTH_MAX = 17
FORWARD_SPECIFIC_LENGTHS = [12, 13, 14, 15, 16, 17]

# [V07] tail 3–7 nt, GC-rich
FORWARD_TAIL_MIN = 3
FORWARD_TAIL_MAX = 12
FORWARD_TAIL_OPTIMAL_MAX = 7
FORWARD_TAIL_GC_ENRICHED = True

# [V07] forward primer KHÔNG overlap 6 nt cuối miRNA
FORWARD_EXCLUDES_LAST_NT = 6

# [IDT] + [P3P]
FORWARD_MIN_LENGTH = 18
FORWARD_MAX_LENGTH = 27   # [P3P General Settings] — v2.1 fix từ 30→27
FORWARD_OPTIMAL_LENGTH = 22

# [P3P] — adjusted để accommodate template 22 nt
MIN_CANDIDATE_3PRIME_DISTANCE = 2
```

### Section D: Thermodynamics — Tm Targets

```python
# [SL98] + [IDT]
TM_FORWARD_TARGET = 60.0    # °C
TM_FORWARD_TOLERANCE = 2.0  # °C

# [PAST24] "max Tm difference of 2°C"
TM_PAIR_DIFF_MAX = 2.0

# [SL98 calibrated] binding region Tm target — v2.8.1 fix từ 35°C → 45°C
TM_BINDING_TARGET    = 45.0   # °C — median của 12-17 nt miRNA specific regions
TM_BINDING_TOLERANCE = 10.0   # °C

# [P3GS] (recalibrate Phase 3 v1.9)
TM_ANNEALING_TEMP_DEFAULT = 60.0  # °C
```

### Section E: GC Content

```python
GC_MIN = 40.0     # % [PAST24][IDT][R2]
GC_MAX = 60.0     # %
GC_OPTIMAL = 50.0 # %
GC_STEMLOOP_MIN = 40.0
GC_STEMLOOP_MAX = 60.0

# [IDT-PQ] "3' GC clamp(nt) = 2" — v2.1
GC_CLAMP_MIN_IN_LAST3 = 2      # tối thiểu 2 G/C trong 3 base cuối
GC_CLAMP_3PRIME_WINDOW = 5
GC_CLAMP_MIN_COUNT = 1
GC_CLAMP_MAX_CONSECUTIVE = 3

# [P3P Advanced Settings] Max End GC = 5 — v2.2; fixed: >= not > (v2.8.1 fix #3)
GC_MAX_IN_3PRIME_WINDOW = 5

# [P3P Advanced Settings] Max Poly-X = 5 — v2.2 fix từ 4→5
MAX_HOMOPOLYMER_RUN = 5

# [PAST24] GC-skew
GC_SKEW_OPTIMAL_MAX = 0.0
GC_SKEW_WARNING_THRESHOLD = 0.2
```

### Section F: Secondary Structure Thresholds

```python
# Hairpin
HAIRPIN_DG_MAX_INTERNAL = -3.0   # kcal/mol [ResearchGate qPCR]
HAIRPIN_DG_MAX_3PRIME   = -2.0   # kcal/mol (nghiêm hơn ở 3' end)

# Self-dimer
SELF_DIMER_DG_MAX         = -6.0   # kcal/mol [ResearchGate]
SELF_DIMER_DG_3PRIME_MAX  = -5.0   # kcal/mol [Premier Biosoft]

# Hetero-dimer (forward + universal reverse)
HETERO_DIMER_DG_MAX        = -6.0
HETERO_DIMER_DG_3PRIME_MAX = -5.0

# Critical 3' end extension risk
END_DIMER_DG_CRITICAL = -5.0   # kcal/mol

# [P3P] 3' end stability
END_STABILITY_MAX = 9.0   # kcal/mol
```

### Section G: Amplicon Size

```python
AMPLICON_MIN_QPCR = 60    # bp
AMPLICON_MAX_QPCR = 150   # bp [IDT]
AMPLICON_IDEAL    = 80    # bp
```

### Section H: SCORING_WEIGHTS (Phase 2 v2.0, DEPRECATED — giữ làm reference)

```python
# DEPRECATED: dùng SCORING_WEIGHTS_V3 hoặc SCORING_WEIGHTS_V4 thay thế
SCORING_WEIGHTS = {
    "tm_accuracy": 0.20, "tm_binding_accuracy": 0.10,
    "gc_content": 0.10, "mfe_stemloop": 0.20,
    "hairpin_penalty": 0.10, "dimer_penalty": 0.10,
    "end_stability": 0.10, "amplicon_size": 0.05, "tm_pair_match": 0.05,
}
```

### Section I: Candidate Generation

```python
CANDIDATES_TARGET = 50
CANDIDATES_TOP_N  = 3

REJECTION_REASONS = [
    "tm_out_of_range", "tm_binding_too_low", "gc_out_of_range",
    "gc_clamp_fail", "gc_end_window_fail", "too_short", "too_long",
    "homopolymer_run", "amplicon_out_of_range", "candidate_too_similar",
    "hairpin_fail", "self_dimer_fail", "hetero_dimer_fail", "end_stability_fail",
    "t_at_3prime_warning",   # WARNING-ONLY: không block candidate
]
```

### Section J: Primer3-py Parameters

```python
P3_DEFAULT_MV_CONC    = 50.0    # mM Na+
P3_DEFAULT_DV_CONC    = 1.5     # mM Mg2+
P3_DEFAULT_DNTP_CONC  = 0.8     # mM total dNTP (4×0.2) — v2.1 BUG FIX từ 0.2→0.8
P3_DEFAULT_DNA_CONC   = 200.0   # nM [IDT PrimerQuest] — v2.1 từ 50→200 nM
P3_DEFAULT_TEMP_C     = 37.0    # °C cho ΔG calculation

P3_TM_FORMULA                    = 1     # SantaLucia 1998 [SL98]
P3_SALT_CORRECTIONS              = 1     # SantaLucia 1998
P3_THERMODYNAMIC_OLIGO_ALIGNMENT = True  # checkbox ✓ P3P Advanced Settings
P3_THERMODYNAMIC_TEMPLATE_ALIGNMENT = False  # TẮT — VERY SLOW + template quá ngắn
```

### Section K: TaqMan Probe Constants (Phase 4)

```python
# Probe Tm [IDT-TQ]
PROBE_TM_MIN_ABOVE_PRIMER   = 6.0    # °C
PROBE_TM_IDEAL_ABOVE_PRIMER = 8.0    # °C
PROBE_TM_MIN = 66.0  # °C (primer 60°C + 6°C gap)
PROBE_TM_OPT = 70.0
PROBE_TM_MAX = 74.0

# Probe length [P3P Internal Oligo]
PROBE_MIN_LENGTH_SINGLE_Q = 18  # nt
PROBE_OPT_LENGTH_SINGLE_Q = 20  # nt
PROBE_MAX_LENGTH_SINGLE_Q = 27  # nt
PROBE_MIN_LENGTH_MGB = 13  # nt [BOC Sciences MGB]
PROBE_OPT_LENGTH_MGB = 16  # nt
PROBE_MAX_LENGTH_MGB = 20  # nt
PROBE_MGB_TM_BOOST   = 15.0  # °C ước tính

# Probe sequence rules [IDT-TQ]
PROBE_NO_G_AT_5PRIME     = True   # G tại 5' quenches FAM signal
PROBE_G_NOT_EXCEED_C     = True   # count(G) ≤ count(C)
PROBE_MAX_CONSECUTIVE_G  = 3      # G-quadruplex risk
PROBE_MIN_DIST_FROM_PRIMER = 1    # nt gap với 3' end của forward primer

# Probe position [Chen05][K11]
PROBE_POSITION                   = "junction"
PROBE_JUNCTION_OVERLAP_MIRNA_SIDE    = 7   # nt [P3P Hyb Oligo 5' Junction=7]
PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE = 4   # nt [P3P Hyb Oligo 3' Junction=4]
PROBE_MODE_CUSTOM    = "custom"
PROBE_MODE_UNIVERSAL = "universal"  # [RNA13] universal stemloop body probe
PROBE_MODE_DEFAULT   = PROBE_MODE_CUSTOM
```

### Section L: Bound Fraction Constants (Phase 3 — recalibrate v1.9)

```python
# [SL04] SantaLucia & Hicks 2004 — ĐÍNH CHÍNH từ [SL07] nhầm trong Phase 2
# [K11] RT step: SuperScript III extension temperature
BOUND_FRACTION_RT_TEMP        = 42.0  # °C — Round 1 (RT step)
# [v1.9 FIX] Ta = Tm_target − 5°C — không phải 60°C (= Tm, fraction ~50% → score ~0)
BOUND_FRACTION_ANNEALING_TEMP = 55.0  # °C — Round 2 (qPCR annealing)
# [v1.9 FIX] từ MIN=90/OPT=97 (long duplex) → MIN=60/OPT=80 (primer 12-24 nt)
BOUND_FRACTION_MIN = 60.0
BOUND_FRACTION_OPT = 80.0
BOUND_FRACTION_MAX = 100.0
PENALTY_WT_BOUND_LT = 1.0   # [P3P Penalties]
PENALTY_WT_BOUND_GT = 1.0
```

### Section M: Penalty Weights (Primer3Plus Penalties tab)

```python
PENALTY_WT_SIZE_LT     = 1.0   # [P3P Penalties] Size Lt=1.0
PENALTY_WT_SIZE_GT     = 1.0
PENALTY_WT_TM_LT       = 1.0   # [P3P Penalties] Tm Lt=1.0
PENALTY_WT_TM_GT       = 1.0
PENALTY_WT_GC_LT       = 0.5   # HG Lab departure từ P3P default 0.0
PENALTY_WT_GC_GT       = 0.5
PENALTY_WT_END_STABILITY = 0.5 # HG Lab soft gradient
PENALTY_WT_SELF_COMP   = 0.0   # [P3P default]
PENALTY_WT_HAIRPIN     = 0.0   # [P3P default]
PENALTY_PRIMER_PAIR_WEIGHT = 1.0  # [P3P Penalties]
PENALTY_HYB_OLIGO_WEIGHT  = 0.0  # Phase 2; Phase 4: = 1.0
```

### Section N: Advanced Seq. Tab Constants

```python
OUTPUT_BASE_INDEX           = 1      # 1-based output [P3P PRIMER_FIRST_BASE_INDEX=1]
PRIMER_AVOID_T_AT_3PRIME    = True   # warn [IDT]
PRIMER_T_AT_3PRIME_SEVERITY = "warning"
```

### Section O: RT Buffer Constants (Phase 3)

```python
# [K11] Table 2 — RT reaction conditions
P3_RT_MV_CONC    = 75.0   # mM KCl
P3_RT_DV_CONC    = 3.0    # mM MgCl2
P3_RT_DNTP_CONC  = 2.0    # mM total dNTP
P3_RT_DNA_CONC   = 1.0    # nM RT primer [K11 optimized]
```

### Section P: Heterodimer Thresholds (Phase 3)

```python
# [IDT] + [K11] — Two-layer risk
HETERODIMER_HIGH_DG       = -9.0   # kcal/mol — HIGH risk nếu dG ≤ này AND 3' ≥ 3bp
HETERODIMER_MODERATE_DG   = -9.0   # kcal/mol — MODERATE nếu dG ≤ này, no 3' end
HETERODIMER_LOW_DG_MAX    = -6.0   # kcal/mol — LOW: -9 < dG ≤ -6
HETERODIMER_PASS_DG_MIN   = -6.0   # kcal/mol — PASS: dG > -6
HETERODIMER_3PRIME_BP_MIN = 3      # bp để trigger HIGH (cùng với dG ≤ -9)
```

### Section Q: SCORING_WEIGHTS_V3 (Phase 2 v2.8.3 — 12 tiêu chí, DEPRECATED)

```python
# DEPRECATED khi Phase 3 active — giữ làm reference
SCORING_WEIGHTS_V3 = {
    "tm_accuracy":          0.20,
    "mfe_stemloop":         0.15,
    "tm_binding_accuracy":  0.10,
    "hairpin_penalty":      0.10,
    "dimer_penalty":        0.10,
    "end_stability":        0.10,
    "gc_content":           0.07,
    "tm_pair_match":        0.05,
    "primer_size":          0.04,
    "amplicon_size":        0.04,
    "gc_skew":              0.02,
    "gc_clamp":             0.03,
}  # tổng = 1.00
```

### Section R: SCORING_WEIGHTS_V4 (Phase 3 v4.1 — 15 tiêu chí, ACTIVE)

```python
# ACTIVE — dùng trong scoring.py [Phase 3 v1.9 rebalance = v4.1]
SCORING_WEIGHTS_V4 = {
    "tm_accuracy":             0.20,
    "mfe_stemloop":            0.14,  # -0.01: body 44 nt cố định, variance thấp
    "tm_binding_accuracy":     0.10,
    "hairpin_penalty":         0.08,
    "dimer_penalty":           0.08,
    "end_stability":           0.08,
    "bound_fraction_binding":  0.05,  # [Phase 3] round 1 (cDNA tại 42°C)
    "bound_fraction_full":     0.03,  # [Phase 3] round sau (amplicon tại 55°C)
    "gc_content":              0.08,
    "family_discrimination":   0.05,  # [Phase 3] risk từ miFam.dat/seed-based
    "tm_pair_match":           0.01,  # -0.02: reverse cố định Tm≈60.4°C → redundant
    "gc_clamp":                0.04,  # +0.02: 3' GC critical cho extension
    "primer_size":             0.02,
    "amplicon_size":           0.02,
    "gc_skew":                 0.02,  # +0.01: G-quadruplex risk signal
}
assert abs(sum(SCORING_WEIGHTS_V4.values()) - 1.00) < 0.001  # = 1.00
```

### Section S: BLAST Constants (Phase 3)

```python
# [Ye12] Primer-BLAST defaults
BLAST_WORD_SIZE         = 7
BLAST_EVALUE_CUTOFF     = 30000
BLAST_MAX_TARGET_SEQS   = 50000
BLAST_REWARD            = 1
BLAST_PENALTY           = -1
BLAST_TASK              = "blastn-short"

PRIMER_BLAST_MIN_TOTAL_MISMATCHES    = 2
PRIMER_BLAST_3PRIME_WINDOW           = 5
PRIMER_BLAST_3PRIME_MIN_MISMATCHES   = 2
PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES = 6

# [Kwok90] Table III
KWOK_3PRIME_MISMATCH_CATEGORY = {
    ("A","G"): "BLOCKING", ("G","A"): "BLOCKING", ("C","C"): "BLOCKING",
    ("A","A"): "REDUCING",
    # Còn lại TOLERANT
}

BLAST_CACHE_TTL_DAYS    = 30
BLAST_DB_STALE_WARN_DAYS = 90
BLAST_MAX_HITS_RETURNED  = 200
MIRBASE_HUMAN_PREFIX     = "hsa-"
```

### Section T: Literature Constants (Phase 2 §27)

```python
# [Chen05] discrimination data
DISCRIMINATION_CROSS_REACTION_MAX    = 3.7   # % [C05 Figure 7]
DISCRIMINATION_MISMATCH_CUTOFF       = 3     # mismatches → 100% specific
PRECURSOR_CT_OFFSET_MIN              = 11.0  # cycles [C05 Table 2]
PRECURSOR_SIGNAL_CONTRIBUTION        = 0.05  # %

# [C05] G-T wobble
MISMATCH_GT_WOBBLE_PENALTY_WEIGHT = 0.7
MISMATCH_TRUE_PENALTY_WEIGHT      = 1.0

# [V07] SYBR Green risk
SYBR_GREEN_NON_SPECIFIC_RISK = "HIGH"

# [PAST24]
GC_SKEW_WARNING_THRESHOLD = 0.2
```

---

## §6 sequence_utils.py [Phase 2]

```python
RNA_TO_DNA_TABLE = str.maketrans("AaUuGgCc", "AaTtGgCc")
DNA_COMPLEMENT   = str.maketrans("ATGCatgc", "TACGtacg")

def rna_to_dna(rna_seq): ...
def reverse_complement(dna_seq): ...
def validate_rna_sequence(seq): ...  # 15–30 nt, AUGC only
def calculate_gc(sequence): ...
def check_homopolymer(sequence, max_run=4): ...
def check_gc_clamp(sequence, window=5, min_gc=1, max_consecutive=3): ...
```

---

## §7 Module 1: Stem-loop RT Primer (stemloop_rt.py) [Phase 2]

### Cấu trúc primer

```
[STEMLOOP_BODY 44nt] + [RC(3' overhang 6nt của miRNA)]
```

### 3-tier MFE fallback (v2.8)

```python
def _compute_mfe(primer_seq: str) -> tuple[float, str, str]:
    """
    Tier 1: ViennaRNA Python bindings — RNA.fold() (gold standard)
    Tier 2: RNAfold subprocess (binary trên PATH)
    Tier 3: primer3.calc_hairpin DNA proxy (~15-20% less negative than RNA MFE)

    Returns: (mfe, structure, mfe_method)
    mfe_method: "ViennaRNA" | "RNAfold" | "primer3-py (ViennaRNA unavailable)"
    """
```

**QUAN TRỌNG — Method-aware thresholds:**
- `mfe_method in ("ViennaRNA", "RNAfold")` → dùng `MFE_STEMLOOP_MIN_RNA = -35.0`
- Dùng exact equality (NOT substring) — `"primer3-py (ViennaRNA unavailable)"` chứa "ViennaRNA" như substring (v2.8.1 fix #2)

### Refolding Protocol [K11]

```python
REFOLDING_PROTOCOL = {
    "use_mineral_oil_overlay": True,   # [K11] — critical detail
    "steps": [
        {"temp_c": 95, "duration_min": 10},
        {"temp_c": 75, "duration_min": 60},
        {"temp_c": 68, "duration_min": 60},
        {"temp_c": 65, "duration_min": 60},
        {"temp_c": 62, "duration_min": 60},
        {"temp_c": 60, "duration_min": 240},
    ],
    "storage": "Store at -20°C. Never heat above room temperature again.",
    "source": "Kramer 2011, Unit 15.10, p.10"
}
```

### Output fields

```json
{
  "sequence": "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTCAACA",
  "length": 50, "overhang_rna": "UGUUGA", "overhang_dna": "TGTTGA",
  "overhang_rc": "TCAACA", "binding_length": 6, "gc_percent": 52.0,
  "tm_full": 72.3, "mfe": -11.4, "mfe_method": "ViennaRNA",
  "hairpin_structure": "((((....))))....", "end_stability_3prime": 3.2,
  "warnings": [], "pass_flags": {"mfe_in_range": true, "gc_in_range": true},
  "refolding_protocol": {...}
}
```

---

## §8 Module 2: Forward Primer (forward_primer.py) [Phase 2]

### Nguyên tắc thiết kế

**[V07]** Forward primer lấy từ 12–17 nt đầu 5' của miRNA, **KHÔNG bao gồm 6 nt cuối** (đã dùng cho stemloop overhang):
```python
available_region = miRNA[0 : len(miRNA) - FORWARD_EXCLUDES_LAST_NT]  # = miRNA[0:16] cho 22nt miRNA
```

**[P3P] 2-step Tm (Primer3Plus SEQUENCE_OVERHANG_LEFT principle):**
- Step 1: Tm của `specific_region` (12–17 nt) → quyết định độ dài tail cần
- Step 2: Tm của `full_primer` = `tail + specific_region` → validate final Tm

### Tail generation (v2.8)

```python
def _generate_tail_pool(tail_len: int, max_pool: int = 400, sequence: str = "") -> list:
    """
    tail_len ≤ 6: Exhaustive enumerate 4^n, filter GC≥50% + no homopolymer≥4
                  SORT BY GC% DESCENDING trước khi cap (v2.8.1 fix #8a — không alphabetical)
    tail_len > 6: Weighted-random, GC biased 2× (A:C:G:T = 1:2:2:1). Mỗi lần gọi tự tạo
                  random.Random riêng, seed = SHA-256(sequence|tail_len|max_pool) — không
                  có RNG dùng chung giữa các pool hay giữa các lần thiết kế (v3.1.2).
    """
```

Tổng sequences thử per miRNA: ~4000–6000 (so với 42 cũ).

### 2-step Tm filtering (v2.8)

```python
def _find_tails_for_target_tm(specific_region, tm_binding, target_tm, params, tail_pool_cache):
    """
    Real SantaLucia 1998 NN per (tail+specific) pair.
    Progressive fallback: ±3°C strict → ±6°C wide → top-10 bất kể Tm
    tail_pool_cache: pre-built per tail_len (1 lần per request, không 60×) — v2.8.1 fix #8b
    """
```

### Amplicon size formula (v2.8 — exact derivation)

```python
# cDNA top strand = [tail (T nt)] [miRNA_full (N nt)] [RC(STEMLOOP_BODY[7:44]) (37 nt)]
# UNIVERSAL_REVERSE bắt đầu tại STEMLOOP_BODY position 7
_UNIV_REV_POS    = STEMLOOP_BODY.find(UNIVERSAL_REVERSE)   # = 7
_AMPLICON_OFFSET = STEMLOOP_BODY_LENGTH - _UNIV_REV_POS    # = 44 - 7 = 37

def _compute_amplicon_size(tail_len: int, miRNA_len: int) -> int:
    return tail_len + miRNA_len + _AMPLICON_OFFSET
    # hsa-miR-21-5p (22nt) + tail 5nt = 5+22+37 = 64 bp ✓ [Chen05]
```

### Diversity filter (v2.8.1 fix #6)

```python
# Sort by CLOSEST Tm to target (không phải highest Tm — gây bias ngược với criterion tm_accuracy)
for c in sorted(candidates, key=lambda x: abs(x.get("tm_full", 0) - target_tm)):
```

### GC-Clamp Relaxed Fallback (v2.8)

Nếu tất cả candidates fail GC clamp (AT-rich 5' miRNA như hsa-miR-16-5p):
- Relax: `_gcClampMin = 1` (từ 2)
- Thêm `"gc_clamp_relaxed_warning"` vào `warnings_from_prefilter`

### Prefilter checks

1. `tm_out_of_range` — full primer Tm ngoài [tmMin, tmMax]
2. `tm_binding_too_low` — binding-only Tm < 25°C
3. `gc_out_of_range`
4. `too_short` / `too_long` (27 nt max)
5. `homopolymer_run` — run > 5 [P3P Advanced Settings]
6. `gc_clamp_fail` — < 2 G/C trong 3 base cuối [IDT-PQ]
7. `gc_end_window_fail` — >= 5 G/C trong 5 base cuối [P3P Advanced Settings] (v2.8.1 fix #3: `>=` không phải `>`)
8. `amplicon_out_of_range`
9. `t_at_3prime_warning` — WARNING-ONLY, không block candidate

---

## §9 Module 3: Universal Reverse (universal_reverse.py) [Phase 2]

```python
# [K11] improved 20nt
UNIVERSAL_REVERSE = "CCAGTGCAGGGTCCGAGGTA"
```

### Self-structure check (v2.8.3)

```python
def _check_self_structure(sequence, params) -> dict:
    """
    Hairpin và self-dimer check dưới PCR buffer conditions của user.
    Computed per-request (buffer conditions thay đổi).
    Thresholds:
        Hairpin:   critical ≤ -3.0, warning ≤ -2.0
        Self-dimer: critical ≤ -6.0, warning ≤ -4.0
    Verified: Kramer 2011 pair: hairpin=0.0 (safe), self_dimer=-3.31 (safe)
    """
```

Result include trong API response field `universal_reverse.self_structure_check`. Nếu critical → tự động thêm `global_warning`.

---

## §10 Module 4: Thermodynamics (thermodynamics.py) [Phase 2]

### Tm Caching (v2.8.3)

```python
from functools import lru_cache

@lru_cache(maxsize=4096)
def _calc_tm_cached(sequence, mv_conc, dv_conc, dntp_conc, dna_conc) -> float:
    """primer3.calc_tm() là pure/deterministic → safe to cache globally."""
    return round(float(primer3.calc_tm(...)), 2)

def calculate_tm_nn(sequence, params) -> float:
    """Public API — route qua cache. ~90% reduction trong redundant C-library calls."""
    p3 = _get_p3_params(params)
    return _calc_tm_cached(sequence, p3["mv_conc"], ...)
```

### Các hàm public

```python
def calculate_tm_nn(sequence, params) -> float: ...           # full primer Tm
def calculate_tm_binding_only(specific_region, params) -> float: ...  # binding-only Tm
def calculate_end_stability(last_5_bases, params) -> float: ...       # ΔG 5 base cuối
```

---

## §11 Module 5: Structure Check [Phase 2]

### 11.1 structure_check.py — 4 checks per candidate

1. **Hairpin** — `primer3.calc_hairpin()`, threshold `HAIRPIN_DG_MAX_INTERNAL = -3.0`
2. **Self-dimer** — `calc_homodimer()` + `calc_homodimer_end()`, threshold `-6.0` / `-5.0`
3. **Hetero-dimer (fwd × universal reverse)** — `calc_heterodimer()` + `calc_heterodimer_end()`, threshold `-6.0` / `-5.0`
4. **3' End Stability** — 5-mer cuối, threshold `END_STABILITY_MAX = 9.0` kcal/mol [P3P]

**BUG FIX v2.8.1 #4:** `_check_end_stability` phải dùng `p3` params (không phải `{}`).

### 11.2 heterodimer.py — Module mới (v2.8.2) [Phase 2]

**Rationale:** structure_check.py check fwd×reverse (PCR buffer). Module này thêm:
- **fwd × stemloop RT** (RT buffer Kramer 2011 — xảy ra trong RT step)
- **stemloop × universal reverse** (PCR buffer — one-step RT-qPCR gap, Phase 3 v1.8)

**3' End Complementarity Detection:**
```python
# Pairwise complement check (NOT revcomp check)
condition: complement(seq1[-i]) == seq2[-i] cho i = 1..k
# k consecutive bp tại 3' terminal = extension artifact risk
```

**Risk Classification:**

| Risk | Condition | Interpretation |
|------|-----------|----------------|
| HIGH | dG ≤ −9 AND 3'end ≥ 3 bp | Polymerase CAN extend → artifact thật |
| MODERATE | dG ≤ −9 AND no 3' end | Internal binding |
| LOW | −9 < dG ≤ −6 | Weak, acceptable |
| PASS | dG > −6 | No significant interaction |

**stemloop × reverse (Phase 3 v1.8):**
- Chen 2005 actual pair: dG = −4.40 kcal/mol → PASS (validated)
- Cặp này là FIXED → tính 1 lần per request (không per-candidate)
- HIGH/MODERATE risk → promote lên `global_warnings`
- Scope: one-step RT-qPCR. Two-step: stemloop absent during PCR → dimer không thể xảy ra

---

## §12 Module 6: Scoring Engine (scoring.py) [Phase 2 → Phase 3]

### SCORING_WEIGHTS_V4 (Phase 3 v4.1) — 15 tiêu chí, ACTIVE

| # | Tiêu chí | Weight | Nguồn | Notes |
|---|---|---|---|---|
| 1 | tm_accuracy | 0.20 | [SL98][IDT] | Tm full ≈ 60°C |
| 2 | mfe_stemloop | 0.14 | [R2][Chen05] | MFE sweet spot; −0.01 từ V3 vì body 44nt cố định |
| 3 | tm_binding_accuracy | 0.10 | [P3P] | 2-step Tm, target 45°C (fix từ 35°C) |
| 4 | hairpin_penalty | 0.08 | [ResearchGate] | dG > -3.0 |
| 5 | dimer_penalty | 0.08 | [IDT] | worst 3'-end dimer |
| 6 | end_stability | 0.08 | [P3P] | ≤ 9.0 kcal/mol |
| 7 | bound_fraction_binding | **0.05** | [SL04] | **[Phase 3]** cDNA tại 42°C |
| 8 | gc_content | 0.08 | [PAST24][IDT] | 40–60% |
| 9 | family_discrimination | **0.05** | [Chen05] | **[Phase 3]** risk từ seed-based grouping |
| 10 | bound_fraction_full | **0.03** | [SL04] | **[Phase 3]** amplicon tại 55°C |
| 11 | tm_pair_match | 0.01 | [PAST24] | −0.02 từ V3; reverse cố định → redundant |
| 12 | gc_clamp | 0.04 | [IDT-PQ] | +0.02 từ V3; 3' GC critical cho extension |
| 13 | primer_size | 0.02 | [P3P] | len ≈ 22 nt |
| 14 | amplicon_size | 0.02 | [IDT] | 60–150 bp |
| 15 | gc_skew | 0.02 | [PAST24] | +0.01 từ V3; G-quadruplex signal |
| | **TỔNG** | **1.00** | | verified |

### Scoring formulas chính

**MFE (v2.8.1 fix #1+7 — piecewise linear, continuous at boundaries):**
```python
if mfe_min <= mfe <= mfe_max:
    if mfe <= _mfe_opt:
        frac = (mfe - mfe_min) / (_mfe_opt - mfe_min)
    else:
        frac = (mfe_max - mfe) / (mfe_max - _mfe_opt)
    mfe_score = 60.0 + 40.0 * max(0.0, frac)   # 60–100
elif mfe < mfe_min:
    mfe_score = max(0, 60 + (mfe - mfe_min) * 5)
else:
    mfe_score = max(0, 60 - (mfe - mfe_max) * 5)  # FIX: (mfe-mfe_max) không phải (mfe_max-mfe)
```

**Binding Tm (v2.8.1 fix #5 — target 45°C, tolerance ±10°C):**
```python
tm_bind_diff = abs(tm_bind - TM_BINDING_TARGET)   # 45.0°C
score = max(0, 100 - (tm_bind_diff / TM_BINDING_TOLERANCE) * 50)
```

**GC Clamp (v2.8.3):**
```python
last3 = forward["sequence"][-3:].upper()
gc_last3 = sum(1 for b in last3 if b in "GC")
if gc_last3 == 2:   gc_clamp_score = 100   # optimal [IDT-PQ]
elif gc_last3 >= 3: gc_clamp_score = 80    # over-stabilised
elif gc_last3 == 1: gc_clamp_score = 60    # relaxed fallback
else:               gc_clamp_score = 0     # không nên reach scoring
```

**Grade classification:**
```python
def _classify_score(total) -> str:
    if total >= 80: return "Excellent"
    elif total >= 65: return "Good"
    elif total >= 50: return "Acceptable"
    else: return "Poor"
```

---

## §13 Module 7: Bound Fraction 2-STEP (bound_fraction.py) [Phase 3]

### Rationale [SL04]

Forward primer stem-loop RT-qPCR có 2 vòng binding:
- **Round 1**: specific region (12–17 nt) bind cDNA tại **RT temp = 42°C** (SuperScript III) — quan trọng nhất
- **Round 2**: full primer bind amplicon tại **Ta = 55°C** (= Tm_target − 5°C)

### Lấy dH/dS từ primer3-py

Dùng `primer3.calc_heterodimer(primer, reverse_complement(primer))` — thermodynamics của primer bind với revcomp của nó = perfect duplex binding. API chính thức primer3-py, có `.dh`, `.ds`, `.dg`, `.tm`.

### Công thức [SL04]

```python
def _calculate_bound_fraction(sequence, params, temp_c) -> float:
    """
    dG = dH - T * dS          # T = temp_c + 273.15 K
    K  = exp(-dG / (R * T))   # R = 1.987 cal/(mol·K)
    Ct = dna_conc_nm / 1e9    # mol/L
    fract(%) = (1 / (1 + sqrt(1 / ((Ct/4) * K)))) * 100
    """
```

**LRU cache:** key `(sequence, mv_conc, dv_conc, dntp_conc, dna_conc)` — reuse pattern Tm cache Phase 2.

### API public

```python
def calculate_bound_fraction_binding(specific_region, params) -> float:
    """Round 1: % specific region bind cDNA tại 42°C."""
    return _calculate_bound_fraction(specific_region, params, BOUND_FRACTION_RT_TEMP)

def calculate_bound_fraction_full(full_primer, params) -> float:
    """Round 2: % full primer bind amplicon tại 55°C."""
    return _calculate_bound_fraction(full_primer, params, BOUND_FRACTION_ANNEALING_TEMP)
```

### Scoring (v1.9 recalibrated)

```python
def score_bound_fraction(fract) -> dict:
    """
    fract >= OPT (80%):           score = 100
    MIN (60%) <= fract < OPT:     score = 70 + (fract-MIN)/(OPT-MIN) * 30
    fract < MIN (60%):            score = max(0, fract/MIN * 70)

    Cũ (v1.8): OPT=97/MIN=90 → threshold cho long duplex; không phù hợp primer ngắn
    """
```

---

## §14 Module 8: Family Cross-Reactivity (specificity_check/family_crossreactivity.py) [Phase 2 §30 + Phase 3 §5]

### Rationale

Stemloop RT primer có 6 nt overhang complementary với 3' end mature miRNA. Trong cùng family, members khác 1–2 nt → cross-reaction. [Chen05] Figure 7: 0.1–3.7% trong let-7 family.

### Algorithm

1. Extract overhang = 6 nt cuối miRNA
2. Identify family từ **seed-based grouping** (`mirbase_family_overhangs.json` — 7-nt seed window; miFam.dat HTTP 500 từ miRBase v22.1)
3. Với mỗi sibling: Hamming distance + ΔTm (NN model, perfect-duplex approximation)
4. Risk classification
5. Auto-extension 6→8 nt nếu HIGH risk

### Risk Classification

| Mismatches | ΔTm | Risk |
|---|---|---|
| 0 | any | IDENTICAL |
| 1 | < 5°C | HIGH |
| 1 | ≥ 5°C | LOW |
| 2 | any | LOW |
| ≥ 3 | any | SAFE |

**Lưu ý ΔTm âm:** sibling Tm > target → worse case → `delta_tm < 5.0` vẫn đúng.

### Score mapping

```python
FAMILY_DISCRIMINATION_RISK_SCORE = {
    "SAFE": 100, "LOW": 70, "HIGH": 30, "IDENTICAL": 0, "no_family_data": 100,
}
# Worst-case sibling quyết định score
```

### Data source

```
backend/data/mirbase_family_overhangs.json
- 367 families, 929 hsa- miRNAs
- Build từ mature.fa với 7-nt seed window
- Script: backend/scripts/build_family_db.py
```

**[Chen05] G-T wobble:** main source of cross-reaction → `MISMATCH_GT_WOBBLE_PENALTY_WEIGHT = 0.7`

### Known Limitations

1. ΔTm là approximation (Tm perfect duplex, không mismatch duplex thực)
2. Data offline — cần update khi miRBase release mới
3. Loop-sequence cross-reactivity không implement (steric hindrance của stem-loop là cơ chế chính)
4. miFam.dat HTTP 500 từ v22.1 → seed-based grouping fallback (family detection hoạt động)

---

## §15 Module 9: isoMiR Flag (specificity_check/isomir_flag.py) [Phase 2 §31 + Phase 3 §6]

### Rationale [Neilsen12][Morin08]

5' isomiRs = variants với shift ±1–2 nt tại đầu 5'. Forward primer 3' end nằm ở vùng biến đổi → không phân biệt canonical và isomiR.

### Logic (v2.1: geometric check đã loại)

**Quyết định Phase 3 v2.1:** bỏ `in_risk_window = (forward_3prime_position <= risk_window_nt)` — dead code vì `specific_length` (12–17 nt) >> `risk_window_nt` (2–3 nt). Hàm đơn giản hóa:

1. Lookup miRNA ID trong `known_5prime_isomir_mirnas.json`
2. Found → `isomir_discrimination_risk = True` + `co_amplification_warning`
3. Not found → `isomir_discrimination_risk = False` + `data_warning` (absence ≠ no isomiR)

### Data v1.0.0 — 8 entries, tất cả literature-verified

| miRNA | evidence_level | Source (PMID) |
|---|---|---|
| hsa-miR-10a-5p | study_specific | Morin 2008 [PMID:18285502] |
| hsa-miR-10b-5p | study_specific | Morin 2008 [PMID:18285502] |
| hsa-miR-146b-5p | study_specific | Swierniak 2013 [PMID:23783103] |
| hsa-miR-21-5p | review_supported | Neilsen 2012 [PMID:22883467] |
| hsa-miR-122-5p | review_supported | Neilsen 2012 [PMID:22883467] |
| hsa-miR-155-5p | review_supported | Neilsen 2012 [PMID:22883467] |
| hsa-miR-146a-5p | review_supported | Neilsen 2012 [PMID:22883467] |
| hsa-miR-126-3p | review_supported | Neilsen 2012 [PMID:22883467] |

### Return dict

```python
# Khi found:
{
    "isomir_discrimination_risk": True,
    "mirna_name": str,
    "forward_3prime_position": int,
    "known_5prime_shift_nt": int,
    "risk_window_nt": int,
    "evidence_level": str,           # "study_specific" | "review_supported"
    "note": str,
    "co_amplification_warning": str, # key đổi từ data_warning (Phase 3 v1.7)
}
# Khi not found:
{
    "isomir_discrimination_risk": False,
    "mirna_name": str, "forward_3prime_position": int,
    "risk_window_nt": None, "note": str,
    "data_warning": str,             # giữ key cũ cho unknown case
}
```

**isoMiR flag là WARNING-ONLY — không vào scoring, không block candidate.**

---

## §16 Module 10: BLAST Off-target (specificity_check/blast_offtarget.py) [Phase 3]

### Database — miRBase only (v1.9)

**Ensembl đã loại (v1.9):** DNase treatment trước RT loại genomic DNA và unspliced RNA → template chỉ là mature miRNA → off-target risk giới hạn ở miRNA family cross-reactivity → Ensembl gây false positives không liên quan sinh học.

**Database:** `mirbase_multi` (~48K sequences, ~2 MB index)

**DB unavailable behavior (v2.0):** raise `FileNotFoundError` ngay lập tức (không trả false SAFE). Route catch → HTTP 503.

### BLAST parameters [Ye12]

```python
BLAST_WORD_SIZE=7, BLAST_EVALUE_CUTOFF=30000, BLAST_MAX_TARGET_SEQS=50000
BLAST_REWARD=1, BLAST_PENALTY=-1, BLAST_TASK="blastn-short"
```

### NW global alignment sau BLAST [Ye12]

BLAST local alignment có thể miss mismatch ở 5'/3' end → NW realign toàn bộ chiều dài primer.

### 3'-terminal mismatch classification [Kwok90 Table III]

| Primer 3'-base | Template 3'-base | Category | PCR yield |
|---|---|---|---|
| A | G | **BLOCKING** | ~1% |
| G | A | **BLOCKING** | ~1% |
| C | C | **BLOCKING** | ~1% |
| A | A | **REDUCING** | ~5% |
| T | any | **TOLERANT** | ~100% |
| any | T | **TOLERANT** | ~100% |
| còn lại | - | **TOLERANT** | ~100% |

### Risk classification tổng hợp

```python
def classify_hit_risk(primer, alignment) -> str:
    """Returns: SAFE | MEDIUM | HIGH | CRITICAL"""
    total_mm = alignment["mismatches"]
    if total_mm >= 6:     return "SAFE"    # [Ye12] ignore threshold
    if terminal == "BLOCKING":  return "SAFE"     # [Kwok90] PCR ~1%
    if terminal == "MATCH":
        if total_mm <= 2: return "CRITICAL"
        if total_mm <= 4: return "HIGH"
        return "MEDIUM"
    if terminal == "REDUCING":
        return "MEDIUM" if total_mm >= 2 else "HIGH"
    # TOLERANT:
    return "MEDIUM" if mm_in_3prime_window >= 2 else "HIGH"
```

### Cross-species filtering (v1.7)

```python
def _extract_species_prefix(mirna_id) -> str:
    """'hsa-miR-21-5p' → 'hsa-'. Hits không match prefix → cross_species_excluded."""
```

Smoke test hsa-miR-21-5p: 3,623 cross-species hits filtered đúng.

### Self-hit detection — precursor variants (v1.9 + v2.0)

```python
def _normalize_mirna_name(name) -> str:
    """
    Strip precursor copy number: hsa-miR-16-1-5p → hsa-mir-16-5p
    v2.0: regex \d+ (không phải [12]) để bắt copy number ≥3
    Guard ≥5 components: hsa-miR-1-5p (4 components) → UNCHANGED
    """

def _is_self_hit(subject_id, mirna_id, m_norm=None) -> bool:
    """
    v2.0: bỏ nhánh `s in m` (false-positive: 'hsa-mir-1' in 'hsa-mir-10-5p')
    Chỉ kiểm tra `m in s` + word-boundary prefix check + normalized comparison.
    m_norm: pre-computed 1 lần trong check_offtarget (không N lần per hit)
    """
```

**Edge case (v2.1):** API route `blast_check.py` phải validate `mirna_id` có arm suffix (-5p/-3p). Thiếu arm → 400 Bad Request.

### Performance (v2.0)

Forward + reverse BLAST chạy song song qua `ThreadPoolExecutor(max_workers=2)` → giảm latency 50%.

---

## §17 API Endpoints [Both]

### 17.1 POST `/api/design` — cập nhật Phase 3

Schema giữ nguyên Phase 2, mở rộng:
```json
{
  "top_n": [{
    "...": "Phase 2 fields giữ nguyên",
    "scores": {
      "...": "...",
      "bound_fraction_binding": 78.5,
      "bound_fraction_full": 65.2,
      "family_discrimination": 70.0
    },
    "family_cross_reactivity": {"family": "let-7", "cross_reactivity": [...], "recommendation": {...}},
    "isomir_flag": {"isomir_discrimination_risk": false, "mirna_name": "...", ...}
  }],
  "universal_reverse": {
    "...": "Phase 2 fields",
    "self_structure_check": {"hairpin_dg": 0.0, "self_dimer_dg": -3.31, "any_issue": false},
    "stemloop_reverse_heterodimer": {
      "dg": -4.40, "risk_level": "PASS",
      "three_prime_overlap": false, "three_prime_bp": 0,
      "protocol_note": "Relevant for one-step RT-qPCR protocols..."
    }
  },
  "metadata": {"...": "...", "mirna_id": "hsa-miR-21-5p"}
}
```

### 17.2 POST `/api/blast-check` — mới [Phase 3]

**Request:**
```json
{
  "forward_primer": "CACGCATGGAAGGACGGG",
  "reverse_primer": "CCAGTGCAGGGTCCGAGGTA",
  "mirna_id": "hsa-miR-21-5p"
}
```

**Response:**
```json
{
  "forward_primer_hits": [
    {
      "subject_id": "hsa-miR-21-5p",
      "alignment": {"identity_pct": 94.7, "mismatches": 1, "mismatch_positions": [12],
                    "primer_3prime_base": "G", "template_3prime_base": "G", "terminal_category": "MATCH"},
      "evalue": 0.003, "risk": "HIGH",
      "risk_reason": "1 total mismatch, 3' terminal matches"
    }
  ],
  "reverse_primer_hits": [...],
  "summary": {
    "total_hits": 5, "critical_count": 0, "high_risk_count": 1,
    "medium_risk_count": 2, "safe_count": 2,
    "cross_species_excluded": 3623,
    "overall_risk": "HIGH",
    "hits_truncated": false
  },
  "cache": {"hit": false, "cache_key": "abc123..."},
  "database_info": {
    "mirbase_version": "22.1", "build_date": "2026-06-15",
    "age_days": 16, "outdated_warning": false
  }
}
```

**Overall risk logic:**
```
CRITICAL → HIGH → MEDIUM → SAFE (worst-case wins)
```

**HTTP error codes:**
- 400: thiếu arm suffix trong mirna_id
- 429: rate limit (flask-limiter, 10 req/min/IP)
- 503: DB not found (FileNotFoundError) hoặc circuit breaker OPEN

---

## §18 Output JSON Example — hsa-miR-21-5p [Phase 2]

```json
{
  "top3": [{
    "rank": 1, "total_score": 88.4, "grade": "Excellent",
    "sequence": "ACACTCCTAGCTTATCAGACTGATG",
    "specific_region": "TAGCTTATCAG", "tail": "ACACTCC",
    "length": 25, "specific_length": 11, "gc_percent": 48.0,
    "tm_full": 60.1, "tm_binding": 34.8, "amplicon_size": 68,
    "structure_checks": {
      "hairpin": {"dg": -1.2, "severity": "safe", "pass": true},
      "self_dimer": {"dg_overall": -3.1, "dg_3prime": -2.0, "pass_overall": true, "critical_3prime": false},
      "hetero_dimer": {"dg_overall": -4.2, "dg_3prime": -1.8, "pass_overall": true, "critical_3prime": false},
      "end_stability": {"last_5_bases": "TGATG", "stability_kcal_mol": 4.2, "pass": true},
      "overall_pass": true
    },
    "scores": {
      "tm_accuracy": 97.5, "mfe_stemloop": 82.5, "tm_binding_accuracy": 88.6,
      "gc_content": 90.0, "hairpin_penalty": 100, "dimer_penalty": 100,
      "end_stability": 100, "bound_fraction_binding": 80.0, "bound_fraction_full": 68.0,
      "family_discrimination": 100, "tm_pair_match": 97.0, "gc_clamp": 100,
      "primer_size": 80.0, "amplicon_size": 96.0, "gc_skew": 90.0
    }
  }],
  "stemloop_rt": {
    "sequence": "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTCAACA",
    "mfe": -11.4, "mfe_method": "ViennaRNA", "gc_percent": 52.0,
    "refolding_protocol": {"use_mineral_oil_overlay": true, "steps": [...]}
  },
  "universal_reverse": {
    "sequence": "CCAGTGCAGGGTCCGAGGTA", "gc_percent": 65.0, "tm": 60.4,
    "self_structure_check": {"hairpin_dg": 0.0, "self_dimer_dg": -3.31, "any_issue": false},
    "stemloop_reverse_heterodimer": {"dg": -4.40, "risk_level": "PASS"}
  },
  "metadata": {
    "mirna_id": "hsa-miR-21-5p", "mirna_sequence": "UAGCUUAUCAGACUGAUGUUGA",
    "algorithm_version": "3.0", "elapsed_seconds": 3.8
  }
}
```

---

## §19 Frontend Integration [Phase 2 + Phase 3]

### 19.1 Design flow (Phase 2)

```jsx
// SearchPage/index.jsx
const handleSubmit = async () => {
  const resp = await axios.post('/api/design', formData, { timeout: 15000 });
  setResults(resp.data);
};
// Error 422: no candidates found → hiển thị rejection_summary
```

### 19.2 Frontend folder structure

```
src/pages/SearchPage/
├── index.jsx
└── ResultsSection/
    ├── index.jsx
    ├── PrimerSetCard.jsx      ← thêm mirnaId prop (Phase 3)
    ├── ScoreGauge.jsx
    ├── ScoreBreakdown.jsx     ← 15 criteria (Phase 3)
    ├── StructureChecks.jsx
    ├── RejectionLog.jsx
    ├── OffTargetPanel.jsx     ← MỚI Phase 3
    └── ExportButtons.jsx
src/hooks/
    ├── useMiRBase.js
    └── useBlastCheck.js       ← MỚI Phase 3
```

### 19.3 useBlastCheck.js [Phase 3]

```js
// Status machine: idle → loading → done | error
// Error types: '429'|'503'|'timeout'|'network'|'server'
export default function useBlastCheck() {
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  // run(forwardPrimer, reversePrimer, mirnaId)
  // reset()
}
```

### 19.4 OffTargetPanel [Phase 3]

Placement trong `PrimerSetCard` (expanded):
```
PrimerSetCard (expanded)
  ├── Primer sequences
  ├── Score + structure checks
  ├── Heterodimer checks
  ├── isoMiR flag detail
  ├── Warnings
  ├── [OffTargetPanel]    ← nút "Check off-target" + results
  └── ExportButtons
```

Risk badge styles:
```js
const BLAST_RISK_STYLE = {
  CRITICAL: 'text-red-700 bg-red-50 border-red-300',
  HIGH:     'text-orange-700 bg-orange-50 border-orange-300',
  MEDIUM:   'text-amber-700 bg-amber-50 border-amber-200',
  SAFE:     'text-teal-700 bg-teal-50 border-teal-200',
};
```

Error handling:
- **429**: countdown timer `retryAfter` seconds
- **503**: circuit breaker message (không phải system error — design vẫn hoạt động)
- **timeout/network**: retry button

---

## §20 Infrastructure — Cache, Circuit Breaker, Rate Limit, CI [Phase 3]

### 20.1 SQLiteKVCache (base class)

```python
# backend/utils/sqlite_kv_cache.py
class SQLiteKVCache:
    """Generic SQLite KV cache with optional TTL.
    Reused by Week 1 (MirbaseLocalDB) và Phase 3 (BlastCache).
    Schema: key, value, metadata (JSON), created_at, expires_at"""
    def get(self, key) -> Optional[dict]: ...
    def set(self, key, value, metadata=None, ttl_days=None): ...

class BlastCache(SQLiteKVCache):
    def __init__(self):
        super().__init__(db_path="backend/data/blast_cache.sqlite",
                         table_name="blast_cache", default_ttl_days=30)
    def get_result(self, fwd, rev, db_version) -> Optional[dict]: ...
    def set_result(self, fwd, rev, result, db_version): ...
    @staticmethod
    def _compute_key(fwd, rev, db_version) -> str:
        return hashlib.sha256(f"{fwd}|{rev or ''}|{db_version}".encode()).hexdigest()[:32]
```

### 20.2 Circuit Breaker

Reuse `backend/utils/circuit_breaker.py` từ Week 1:
```python
BLAST_CB_FAILURE_THRESHOLD = 3     # 3 fails → OPEN
BLAST_CB_RECOVERY_TIMEOUT = 60     # 60s → HALF_OPEN
```
Circuit OPEN → HTTP 503 + `retry_after` header.

### 20.3 Rate Limiting

```python
# routes/blast_check.py
@blast_check_bp.route("/api/blast-check", methods=["POST"])
@limiter.limit("10 per minute")
def blast_check(): ...
```

### 20.4 Database Version Tracking

```json
{
  "mirbase_version": "22.1",
  "build_date": "2026-06-15",
  "sequences_count": {"mirbase_multi": 48885},
  "makeblastdb_version": "2.14.0+"
}
```

Nếu `age_days > BLAST_DB_STALE_WARN_DAYS (90)` → `outdated_warning: true` trong response.

### 20.5 build_blast_db.py

```python
# 1. Tải miRBase mature.fa: https://www.mirbase.org/download/mature.fa
# 2. makeblastdb -in mature.fa -dbtype nucl -out mirbase_multi -parse_seqids
# 3. Xoá FASTA gốc sau makeblastdb
# 4. Ghi metadata.json
# 5. Verify: blastdbcmd -db mirbase_multi -info
MIRBASE_MATURE_URL = "https://www.mirbase.org/download/mature.fa"
```

**Storage:** ~2 MB (Railway free tier 1GB → OK. Render ephemeral → KHÔNG phù hợp.)

### 20.6 GitHub Actions CI

```yaml
# .github/workflows/test_phase3.yml
jobs:
  test-algorithm:
    steps:
      - name: Unit tests (không cần DB thật)
        run: pytest backend/tests/algorithm/ -v
      - name: Build script logic với MOCK data
        run: pytest backend/tests/scripts/ -v -m "not slow"
  smoke-test:
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Smoke test /api/blast-check với hsa-miR-21-5p
        run: pytest backend/tests/smoke/test_blast_check_e2e.py -v
```

---

## §21 Unit Tests [Both]

### Key tests Phase 2

```python
# stemloop_rt:
def test_mir21_stemloop_overhang():  # overhang TCAACA, length 50

# scoring:
def test_scoring_weights_v3_sum_to_1():  # 12 criteria, total=1.00
def test_scoring_weights_v4_sum_to_1():  # 15 criteria, total=1.00

# thermodynamics:
def test_tm_cache_hit():   # lru_cache hit >= 1

# forward_primer:
def test_forward_excludes_last_6nt():   # available = miRNA[:-6]

# constants:
def test_dntp_concentration_correct():     # P3_DEFAULT_DNTP_CONC == 0.8
def test_forward_max_length_updated():     # == 27 (không phải 30)
def test_max_poly_x_updated_to_5():        # == 5
def test_gc_clamp_min_in_last3_exists():   # == 2
```

### Key tests Phase 3

```python
# bound_fraction:
def test_bound_fraction_binding_at_opt_scores_100():
    assert score_bound_fraction(80.0)["score"] == 100  # OPT recalibrated to 80%

def test_bound_fraction_full_below_min_scores_low():
    assert score_bound_fraction(40.0)["score"] < 70   # MIN=60%

def test_calc_heterodimer_returns_thermodynamics():
    r = primer3.calc_heterodimer('ATCGATCGATCGATCG', 'CGATCGATCGATCGAT')
    assert r.dh < 0 and r.ds < 0 and r.dg < 0 and 40 < r.tm < 60

# blast:
def test_hsa_mir_21_5p_forward_primer_finds_self():
    # 100% identity self-hit trong miRBase
def test_rate_limit_blocks_11th_request_per_minute():
    # HTTP 429
def test_cache_hit_returns_immediately():
    # < 100ms
def test_circuit_breaker_opens_after_3_blastn_failures():
    # HTTP 503

# isomir:
def test_isomir_flag_triggers_for_known_mirna():    # DB lookup → risk=True
def test_co_amplification_warning_key():             # key renamed từ data_warning

# normalize:
def test_normalize_mirna_name():
    # hsa-miR-16-1-5p → hsa-mir-16-5p
    # hsa-miR-509-3-5p → hsa-mir-509-5p  # copy number ≥3
    # hsa-miR-1-5p → hsa-mir-1-5p          # unchanged (4 components)
```

---

## §22 Completion Criteria [Both]

### Phase 2 phải hoàn thành (bắt buộc)

- [ ] `POST /api/design` trả JSON hợp lệ < 5s cho hsa-miR-21-5p
- [ ] Stemloop: `overhang_rc` = RC(6 nt cuối miRNA); MFE bởi ViennaRNA; 3-tier fallback
- [ ] Forward: `tm_binding` field; 2-step Tm; FORWARD_SPECIFIC_LENGTHS = [12..17]
- [ ] `P3_DEFAULT_DNTP_CONC = 0.8`; `FORWARD_MAX_LENGTH = 27`; `MAX_HOMOPOLYMER_RUN = 5`
- [ ] `GC_CLAMP_MIN_IN_LAST3 = 2`; GC end window `>=` (không phải `>`)
- [ ] Structure checks: 4 checks đúng (hairpin/self-dimer/hetero-dimer/end_stability)
- [ ] Scoring V3: 12 tiêu chí, weights tổng = 1.00
- [ ] MFE method detection: exact match, không substring
- [ ] Amplicon formula: `tail_len + miRNA_len + 37`
- [ ] Binding Tm target: 45°C (không phải 35°C)
- [ ] Diversity filter: closest Tm, không highest Tm
- [ ] All English output

### Phase 3 phải hoàn thành (bắt buộc)

**Khoa học:**
- [ ] `bound_fraction.py`: 2 hàm (binding/full), công thức [SL04], test heterodimer workaround
- [ ] `SCORING_WEIGHTS_V4` = 15 tiêu chí, tổng 1.00, binding (0.05) > full (0.03)
- [ ] `family_crossreactivity.py`: seed-based grouping (miFam.dat unavailable)
- [ ] `mirbase_family_overhangs.json`: build thật từ mature.fa
- [ ] `isomir_flag.py`: data v1.0.0, key `co_amplification_warning` (không phải `data_warning`)
- [ ] Đính chính [SL07] → [SL04] trong constants.py

**BLAST:**
- [ ] BLAST params đúng [Ye12]: word_size=7, evalue=30000, 1:1 reward:penalty
- [ ] NW global alignment realign
- [ ] Default thresholds [Ye12]: ≥2 mm trong 5 base cuối, ≥6 mm total = SAFE
- [ ] [Kwok90]: BLOCKING (A:G/G:A/C:C), REDUCING (A:A), TOLERANT
- [ ] Risk matrix §16 đúng

**Kiến trúc:**
- [ ] SQLite cache TTL 30 ngày, reuse `local_db.py`
- [ ] Circuit breaker blastn (3 fails → OPEN, 60s recovery)
- [ ] Rate limit 10 req/phút/IP
- [ ] CI với mock data; smoke test hsa-miR-21-5p
- [ ] DB unavailable → HTTP 503 (không phải false SAFE)
- [ ] `mirna_id` có arm suffix validation → 400 nếu thiếu

**Frontend:**
- [ ] `useBlastCheck.js` hook
- [ ] `OffTargetPanel` (button + spinner + risk badge + error states)
- [ ] Error: 429 countdown, 503 circuit message, timeout retry

**Không làm trong Phase 2 và Phase 3:**
- TaqMan probe design → Phase 4
- PDF/CSV export → Phase 4
- AI/LLM → Phase riêng
- Template alignment (VERY SLOW + template 66 nt quá ngắn) → không bao giờ cần

---

## §23 Literature Insights [Phase 2 §27]

### A. Stemloop RT Primer — Kramer 2011 [K11]

- **RT primer concentration**: 1 nM (không phải 50 nM [C05]) — "greatly reduced non-specific amplifications"
- **Refolding**: "most critical parameter"; cần mineral oil overlay; never heat above room temperature after refolding
- **Forward specific length**: 12–17 nt (không phải 10–12 từ Phase 2 v2.0) — "Start with 12 nt... maximize probe coverage"
- **Tail**: 3–7 nt GC-rich [V07]: "sequences chosen randomly, relatively GC-rich"

### B. Discrimination — Chen 2005 [C05]

- Cross-reaction 0.1–3.7% cho 1-nt mismatch trong let-7 family (Figure 7)
- "Only detected targeted miRNA if >3 mismatches" → `DISCRIMINATION_MISMATCH_CUTOFF = 3`
- "stem-loop RT ≥100× more efficient and specific than linear RT" (Figure 9)
- "Most cross-reactions resulted from G–T mismatches" → `MISMATCH_GT_WOBBLE_PENALTY_WEIGHT = 0.7`
- Precursor CT offset: ≥11 cycles → precursor contribution < 0.05%

### C. Universal Reverse — Kramer 2011 [K11]

- [K11] recommends 20-nt: `"5'-CCA GTG CAG GGT CCG AGG TA-3'"` — "improved sensitivity vs Chen 2005 original"
- Chen 2005 original: 16-nt `"5'-GTG CAG GGT CCG AGG T-3'"`

### D. qPCR Reaction Conditions [K11]

- RT: 16°C/30 min → 42°C/30 min → 85°C/5 min
- qPCR: 95°C/10 min; 40 cycles (95°C/15s + 60°C/1 min)
- Primer conc in PCR: forward 1.5 μM, reverse 0.7 μM, probe 0.8 μM [K11 Table 3]

### E. SYBR Green Risk [V07]

- "Non-specific products detected in minus-RT and water controls at 40 cycles"
- "Melting curve analysis could NOT distinguish specific from non-specific products"
- → `SYBR_GREEN_NON_SPECIFIC_RISK = "HIGH"` → WARNING mandatory nếu user chọn SYBR

### F. PrimerAST 2026 [PAST24]

- RF AUC = 0.982 — xác nhận GC content + Tm là features quan trọng nhất
- Thêm GC-skew (G-quadruplex risk), AT-skew vào feature set
- Tm range khuyến nghị: 58–62°C; max Tm diff: 2°C

---

## §24 Algorithm Bug Fixes [Phase 2 §28 + post-Phase 4]

### Bảng tổng hợp v3.1 (2026-07-03)

| # | File | Loại | Mô tả | Severity |
|---|---|---|---|---|
| B1 | `routes/design.py` | Bug | `detect_edge_cases()` gọi sau early-return 422 (no candidates) → `edge_cases` không được đính kèm vào error response; E1/E4/E5 không bao giờ được validator thấy | High |
| B2 | `algorithm/constants.py` | Calibration | `LOW_COMPLEXITY_TOP2_PCT = 60.0` quá thấp → hsa-miR-21-5p (T:36%+A:27%=63.6%) bị flag E7 spuriously; nâng lên 70.0% | Medium |
| B3 | `routes/export.py` | Security | `_sanitize("../../etc/passwd")` → `.._.._etc_passwd` vẫn chứa `..` (path traversal token); thêm `re.sub(r"\.\.+", "_", s)` để collapse | Medium |

**B1 root cause:** Edge-case detection được đặt ở cuối `design_primers()` (dòng 190), sau `if not candidates: return 422` ở dòng 124. Fix: move `detect_edge_cases(seq)` lên trước step 4 (generate candidates), include `edge_cases` và `global_warnings` trong 422 body.

**B2 root cause:** `TOP2_PCT = 60%` dựa trên convention cho sequence chung, không tính đến đặc điểm AT-rich của miRNA sinh học. Cho 22-nt miRNA với phân phối ngang bằng (A≈27%, T≈36%, G≈23%, C≈14%), top-2 = 63.6% là bình thường. 70% phù hợp hơn — chỉ flag khi 2 base thực sự chiếm ưu thế (ATATAT..., GCGCGC...).

**B3 root cause:** `_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")` giữ dấu `.` để hỗ trợ tên như `hsa-miR-21.2`. Chuỗi `../../` → `.._.._` (slash bị replace nhưng `..` giữ nguyên). Fix: thêm post-step collapse `..+` → `_`.

### Bảng tổng hợp (v2.8.1)

| # | File | Loại | Mô tả | Severity |
|---|---|---|---|---|
| 1 | `scoring.py` | Bug | MFE above-max formula sign error → weak stem score tăng | Critical |
| 7 | `scoring.py` | Bug | MFE in-range floor creates boundary discontinuity | Medium |
| 2 | `scoring.py` | Bug | ViennaRNA substring match misclassifies primer3 fallback | Critical |
| 3 | `forward_primer.py` | Bug | `> 5` thay vì `>= 5` → GC end window filter không bao giờ fire | High |
| 4 | `structure_check.py` | Bug | `{}` thay vì `p3` trong `_check_end_stability` → user salt settings bị ignore | High |
| 5 | `scoring.py` | Scientific | Binding Tm target 35°C → sai (thực tế 40–52°C cho 12-17 nt) | High |
| 6 | `forward_primer.py` | Logic | Diversity filter sort by highest Tm (không phải closest to target) | Medium |
| 8a | `forward_primer.py` | Efficiency/bias | Alphabetical cap: 83% len-6 tails không bao giờ được thử | Medium |
| 8b | `forward_primer.py` | Efficiency | Pool regenerated 60× per request thay vì 10× | Medium |

### Fix MFE (v2.8.1 #1+7)

```python
# Piecewise linear, liên tục tại cả hai biên:
if mfe_min <= mfe <= mfe_max:
    frac = (mfe - mfe_min) / (mfe_opt - mfe_min)  if mfe <= mfe_opt \
      else (mfe_max - mfe) / (mfe_max - mfe_opt)
    score = 60 + 40 * max(0, frac)
elif mfe < mfe_min:
    score = max(0, 60 + (mfe - mfe_min) * 5)
else:
    score = max(0, 60 - (mfe - mfe_max) * 5)   # FIX: sign
```

---

## §25 Known Limitations [Phase 2 §32 + Phase 3]

1. **Loop-sequence cross-reactivity**: Không implement. Cơ chế specificity là steric hindrance của cấu trúc stem-loop (Chen 2005), không phải sequence specificity của overhang với loop. Check này sẽ tạo false signal.

2. **ΔTm approximation** (family check): Tính Tm của mỗi overhang binding perfect complement, không phải Tm của mismatch duplex thực. ΔTm âm (sibling Tm > target) được xử lý đúng trong `delta_tm < 5.0`.

3. **Offline data**: `mirbase_family_overhangs.json` và `known_5prime_isomir_mirnas.json` cần update định kỳ khi miRBase release mới. Script tự động chưa có.

4. **isoMiR coverage**: Chỉ 8 entries verified. Absence ≠ no isomiR exists — cần `data_warning` rõ ràng.

5. **miFam.dat HTTP 500**: miRBase v22.1 không còn serve file này. Seed-based grouping thay thế; ít chính xác hơn về phân loại family chính thức.

6. **BLAST word_size=7 limitation**: Ye 2012 §Comparison note "will miss targets with ≤6 consecutive matches" — probability ~0.5% cho 20 nt primer với 2 random mismatches.

7. **SYBR Green**: melting curve analysis bắt buộc; kết quả có thể có non-specific bands. Khuyến nghị TaqMan.

8. **primer3-py bound fraction**: `calc_heterodimer(seq, revcomp(seq))` để lấy dH/dS là workaround chính thức nhưng không phải API được thiết kế cho mục đích này — cần document rõ trong comments.

9. **Binding Tm 2-step**: `tm_binding` của forward primer thường thấp (30–50°C) do specific_region ngắn 12–17 nt. Đây là thiết kế đúng — tail làm nhiệm vụ nâng Tm.

10. **Render deployment**: Ephemeral filesystem → không thể giữ BLAST database giữa các restarts. Cần Railway (persistent disk 1 GB) hoặc Cloud storage.
