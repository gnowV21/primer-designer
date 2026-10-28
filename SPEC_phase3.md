# SPEC_phase3.md — HG Lab Stem-loop RT-qPCR Primer Designer

**Status:** DESIGN — viết qua quy trình brainstorming (skill: `brainstorming`), dựa trên SPEC_week1_full.md, SPEC_phase2.md v2.8.3, và literature trong project knowledge (bao gồm Ye 2012 + Kwok 1990 upload cho v1.3).

---

## CHANGELOG

| Phiên bản | Thay đổi chính |
|---|---|
| v1.0 | Bản nháp đầu tiên — 3 hạng mục độc lập (bound fraction, family discrimination, BLAST off-target) |
| v1.1 | Hợp nhất family discrimination với thiết kế SPEC_phase2 §30; thêm isomiR flag §31; format theo SPEC_phase2 |
| v1.2 | **VÒNG 1 — RỦI RO KHOA HỌC:** Bound fraction tính 2 bước (binding 0.05 + full 0.03) đối xứng với 2-step Tm Phase 2; family detection dùng `miFam.dat` chính thức thay heuristic; **đính chính [SL07] → [SL04]** (SantaLucia & Hicks 2004, Annual Review, `annrevbbs3341504.pdf`) |
| v1.3 | **VÒNG 2 — BLAST RISK CLASSIFICATION:** Formalize risk rules theo Ye 2012 Primer-BLAST + Kwok 1990 3'-terminal mismatch table. Cụ thể: (1) Default specificity — "≥2 mismatch trong 5 base cuối 3' end" từ Ye 2012 §User Interface; (2) Ignore threshold — target với ≥6 mismatch coi như safe; (3) BLAST params — word_size=7, evalue=30000, reward:penalty=1:1; (4) NW global alignment sau BLAST để bù local-alignment gap; (5) 3'-terminal mismatch **có loại** (Kwok 1990 Table III): A:G/G:A/C:C giảm ~100x, A:A giảm ~20x, các mismatch còn lại (đặc biệt T:X, X:T) gần như không ảnh hưởng |
| v1.4 | **VÒNG 3 — KIẾN TRÚC HỆ THỐNG:** (1) BLAST cache SQLite reuse pattern `local_db.py` Week 1, TTL 30 ngày; (2) Circuit breaker cho blastn subprocess (reuse `circuit_breaker.py` Week 1); (3) Rate limit 10 req/phút/IP cho `/api/blast-check`; (4) Database version tracking + cảnh báo khi >90 ngày; (5) GitHub Actions CI test — script logic với mock data, không build database thật trên CI; (6) Smoke test end-to-end với `hsa-miR-21-5p` |
| v1.5 | **VÒNG 4 — LÀM RÕ 3 QUYẾT ĐỊNH IMPLEMENTATION** (đã benchmark bằng code + phân tích infra): (1) **primer3-py DÙNG `calc_heterodimer(primer, revcomp(primer))`** để lấy dH/dS — verified bằng `ThermoResult` object có `.dh`, `.ds`, `.dg` (§4.7); (2) **BLAST database size ~370 MB** — verify Railway free 1 GB OK; Render cần paid persistent disk; fallback option "protein-coding only" ~200 MB (§9.5); (3) **`LocalDB` Week 1 refactor thành base class `SQLiteKVCache`** — reuse tối đa, backward-compatible với Week 1 (§9.1 mở rộng) |
| v1.6 | **§13 FRONTEND INTEGRATION** — Full spec cho nút "Check off-target": hook `useBlastCheck`, button placement trong `PrimerSetCard`, loading state, risk badge styling (4 mức), error handling (429/503/timeout/network), result panel layout, integration với `ResultsSection` có sẵn |
| v1.7 | **[ĐÍNH CHÍNH IMPLEMENTATION 2026-07-01]** (1) §2: Neilsen12 journal = *Trends in Genetics* (không phải Bioinformatics); (2) §4.1+4.2: `BOUND_FRACTION_RT_TEMP = 42°C` cho Round 1 — spec cũ ghi 60°C sai; (3) §5.5: miFam.dat HTTP 500 trên miRBase v22.1 — production dùng seed-based grouping; (4) §6: isoMiR data v1.0.0 verified (8 entries, PMIDs), `evidence_level` field, key đổi từ `data_warning` → `co_amplification_warning`; (5) §8.9+8.11: cross-species filtering + `cross_species_excluded`/`hits_truncated` trong summary; smoke test hsa-miR-21-5p passed |
| v1.8 | **[GAP FIX — stemloop RT × universal reverse heterodimer 2026-07-01]** Phase 2 chỉ check 2 cặp heterodimer: fwd×stemloop (RT buffer) và fwd×reverse (PCR buffer). Trong one-step RT-qPCR tất cả 3 primer cùng hiện diện trong PCR tube → cặp stemloop×reverse chưa bao giờ được check. Fix: `check_stemloop_reverse_heterodimer()` mới trong `heterodimer.py`; gọi 1 lần trong `design.py` (không per-candidate vì cả hai sequence cố định); kết quả expose tại `universal_reverse.stemloop_reverse_heterodimer` trong API response; HIGH/MODERATE risk promote lên `global_warnings`. Thực tế Chen 2005 pair: dG = −4.40 kcal/mol → PASS (hệ thống validated thực nghiệm). 3 tests mới, 105/105 pass. commit `78a5e22`. |
| v1.9 | **[CẢI THIỆN TÍNH ĐÚNG KHOA HỌC — 2026-07-01]** commit `b36f124`. (1) **Loại Ensembl khỏi BLAST:** DNase treatment trước RT loại toàn bộ genomic DNA và unspliced RNA — template còn lại chỉ là mature miRNA; off-target risk giới hạn ở miRNA family cross-reactivity đã được miRBase multi-species cover đủ. (2) **Bound fraction recalibrate:** `BOUND_FRACTION_ANNEALING_TEMP` 60→**55°C** (Tm−5°C = Ta thực tế qPCR); tại đúng Tm=60°C fraction ~50% theo định nghĩa nhiệt động học → score luôn gần 0 → vô nghĩa. `BOUND_FRACTION_MIN/OPT` 90/97→**60/80%**: threshold cũ dành cho duplex hybridization dài (~27 nt), không phù hợp primer ngắn 12–24 nt. Formula `score_bound_fraction` sửa sang `fract/MIN*70` thay vì `(fract-50)/40*70` hardcoded. (3) **Self-hit precursor variants:** thêm `_normalize_mirna_name()` (strip precursor copy number, guard ≥5 components) + `_is_self_hit()` — loại đúng hsa-miR-16-1-5p và hsa-miR-16-2-5p khỏi off-target khi design cho hsa-miR-16-5p. (4) **SCORING_WEIGHTS_V4 v3.1 rebalance:** `mfe_stemloop` 0.15→**0.14** (body 44 nt cố định; chỉ overhang 6 nt thay đổi → variance thấp), `tm_pair_match` 0.03→**0.01** (reverse cố định Tm≈60.4°C, redundant với tm_accuracy), `gc_clamp` 0.02→**0.04** (3' GC critical cho extension), `gc_skew` 0.01→**0.02**. (5) **E2E / frontend:** baseURL centralize qua `playwright.config.js`; `OffTargetPanel` loại Ensembl references; `detectInputType` bỏ `q.length >= 10` (fix 8–9 nt gap). |
| v2.1 | **[SPEC CONSISTENCY FIXES — 2026-07-02]** 9 điểm không nhất quán giữa spec và implementation. *Stale pseudocode:* (1) §4.7 test examples cập nhật 97.0→80.0 / 85.0→40.0 (v1.9 recalibrate); (2) §4.3/4.4/4.5 pseudocode thêm `temp_c` parameter (42°C vs 55°C), `Ct = dna_conc_nm/1e9` thay vì `dna_conc/4e9`. *Ensembl stale (v1.9 đã loại):* (3) §3 folder structure xóa `ensembl_human_cdna.{nhr,nin,nsq}`; (4) §9.5 rewrite storage table (370 MB Ensembl → ~2 MB miRBase-only); (5) §13.6 cache footnote sửa `ensembl_version` → `miRBase version + build_date`. *Inconsistency:* (6) §12 checklist 2 items đổi "miFam.dat" → "seed-based grouping" theo thực tế §5.5 (HTTP 500). *Logic:* (7) §6.3 vestigial `in_risk_window` — quyết định bỏ geometric check, đơn giản hóa flag thành DB lookup only; (8) §8.2 thêm HTTP 503 spec cho FileNotFoundError trong route; (9) §8.12 thêm note về `m in s` edge case khi thiếu arm designation + yêu cầu validate tại API layer. |
| v2.0 | **[CODE REVIEW FIXES — 2026-07-02]** commit `c18a9a4`. 8 vấn đề từ medium code review. *Correctness:* (1) DB vắng mặt → `check_offtarget` nay raise `FileNotFoundError` thay vì trả `overall_risk='SAFE'` sai; (2) `_is_self_hit` bỏ nhánh `s in m` gây false-positive (e.g. 'hsa-mir-1' match bên trong 'hsa-mir-10-5p') — thay bằng word-boundary prefix check + áp dụng boundary rule tương tự cho normalized comparison; (3) `_normalize_mirna_name` regex `[12]` → **`\d+`** — bắt copy number ≥3 (hsa-miR-509-**3**-5p và hsa-miR-550a-**3**-5p có trong project data); (4) `test_bound_fraction.py` cập nhật theo MIN=60/OPT=80 (bị bỏ sót ở v1.9). *Efficiency:* (5) Forward + reverse BLAST nay chạy song song qua `ThreadPoolExecutor(max_workers=2)` — giảm latency 50%; (6) `m_norm` tính 1 lần trong `check_offtarget`, truyền qua `_check_primer` → `_is_self_hit` — loại N lần tính lại per hit; (7) `_RISK_ORDER` hoisted lên module-level constant. *Cleanup:* (8) `bound_fraction.py` private `_reverse_complement`/`_to_dna` thay bằng delegate sang `sequence_utils.reverse_complement` / `sequence_utils.rna_to_dna`. |

---

## 0. Hướng dẫn cho Claude Code

- Đọc SPEC_phase2.md (đặc biệt Section 25, 27.2 về 2-step Tm, 29, 30, 31, 32) và SPEC_week1.md (đặc biệt `local_db.py`, `circuit_breaker.py`) trước khi implement — Phase 3 build trực tiếp trên các pattern đã có.
- Trước khi viết bất kỳ module mới nào: dùng skill `brainstorming` nếu phát sinh quyết định thiết kế chưa có trong spec này.
- Implement theo thứ tự ở Section 11 — chạy unit test sau mỗi module. Nếu có cài skill `test-driven-development` (từ bộ superpowers): viết test trước, xem fail, viết code tối thiểu để pass, rồi refactor.
- Nếu gặp lỗi khó (BLAST output không parse được, bound fraction lệch...): nếu có skill `systematic-debugging`, dùng quy trình 4 bước root-cause thay vì sửa mò.
- Ưu tiên tuyệt đối: (1) Tính đúng khoa học → (2) Không phá vỡ tốc độ <5s của `/api/design` Phase 2 → (3) Giải thích rõ ràng → (4) UI đẹp.
- All user-facing strings: English only.
- Mỗi constant phải có comment nguồn trích dẫn — không để số "magic" không có nguồn.
- Không phá vỡ Phase 2: thêm `SCORING_WEIGHTS_V4` mới, giữ `SCORING_WEIGHTS_V3` làm reference. Đính chính ký hiệu [SL07] → [SL04] không phải breaking change.
Trước mỗi `git commit`: chạy Superpower security check
Sau mỗi thay đổi UI có ý nghĩa: chạy Playwright E2E test liên quan 
---

## 1. Tổng quan Phase 3

### Mục tiêu
Bổ sung 3 hạng mục hoãn từ Phase 2: bound fraction (2 bước, đối xứng 2-step Tm), family discrimination + isomiR flag (đặc hiệu sinh học), và BLAST off-target (kiểm tra toàn hệ gen, optional với cache/circuit breaker/rate limit). AI/LLM sang phase riêng.

### Flow tổng quát — mở rộng trong `/api/design` (đồng bộ, giữ tốc độ)
```
[... 8 bước Phase 2 giữ nguyên ...]
        |
[7. score_candidates()]   <- MỞ RỘNG: 12 -> 15 tiêu chí
        + bound_fraction_binding (0.05)  [round 1 - binding cDNA - QUAN TRỌNG NHẤT]
        + bound_fraction_full    (0.03)  [round sau - binding amplicon]
        + family_discrimination  (0.05)  [miFam.dat + risk classification §30]
        |
[8. format_output()]   <- MỞ RỘNG: isomir_flag annotation (warning-only §31)
        |
[Frontend - có nút "Check off-target" mới]
```

### Flow mới — `/api/blast-check` (async, có cache + circuit breaker + rate limit)
```
[User bấm "Check off-target"]
        |
[Rate limit check: 10 req/phút/IP]
        |
[Cache lookup: SQLite by hash(fwd + rev + db_version)]
     |                          |
     v (HIT, <30 ngày)          v (MISS hoặc expired)
[Trả cache ngay]         [Circuit breaker check]
                              |
                              v (CLOSED)
                        [blastn subprocess]
                        vs miRBase multi-species (Ensembl đã loại — v1.9)
                              |
                        [NW global alignment realign (Ye 2012)]
                              |
                        [Risk classification (Ye 2012 + Kwok 1990)]
                              |
                        [Write cache, TTL 30 ngày]
                              |
                        [Trả về]
```

### Thời gian mục tiêu
```
/api/design (Phase 2 + 3 tiêu chí mới):
    bound_fraction (2 bước):  < 0.15s/candidate  (reuse NN cache Phase 2 v2.8.3)
    family_discrimination:    < 0.1s/candidate   (lookup local miFam.dat)
    TOTAL:                    < 4.5s              (trong ngân sách <5s)

/api/blast-check:
    Cache hit:                < 0.05s              (SQLite lookup)
    Cache miss:               < 30s cho 1 primer set (benchmark khi có database)
```

---

## 2. Nguồn tham chiếu các thông số

Kế thừa từ SPEC_phase2.md Section 2 ([P3P], [IDT], [SL98], [Chen05], [Kramer/K11], [Kor07]...). Thêm/sửa Phase 3:

- **[SL04]** = SantaLucia & Hicks 2004, *Annual Review of Biophysics* 33: 415-440 (`annrevbbs3341504.pdf`). **Đây là nguồn thực sự cho "bound fraction myth"** — SPEC_phase2 hiện ký hiệu nhầm là [SL07].
- **[Ye12]** = Ye et al. 2012, *BMC Bioinformatics* 13: 134, "Primer-BLAST" (`1471-2105-13-134.pdf`). Nguồn cho BLAST risk classification rules.
- **[Kwok90]** = Kwok et al. 1990, *Nucleic Acids Research* 18(4): 999-1005 (`nar00188-0292.pdf`). Nguồn thực nghiệm cho 3'-terminal mismatch types.
- [Ensembl] = Ensembl genome browser, human transcriptome GRCh38 cDNA
- [miRBase] = miRBase database, mature.fa multi-species
- [miFam] = miRBase miFam.dat (https://www.mirbase.org/download/miFam.dat)
- [Neilsen12] = Neilsen CT et al. 2012, *Trends in Genetics* 28(11):544-549 [PMID:22883467, DOI:10.1016/j.tig.2012.07.005] — isomiR profiling. **[ĐÍNH CHÍNH]** Spec này trước đây ghi nhầm journal là "Bioinformatics"; journal thực là *Trends in Genetics*.
- [Morin08] = Morin 2008 Genome Research — isomiR discovery

---

## 3. Thư viện và cài đặt

### requirements.txt — thêm mới cho Phase 3
```
# Phase 1 + 2 giữ nguyên (flask, primer3-py, ViennaRNA, biopython, numpy)

# Phase 3 — thêm mới
flask-limiter>=3.5.0    # rate limiting cho /api/blast-check (§8.9)
# blastn KHÔNG cài qua pip — binary BLAST+ (§3.2)
```

### Cài Local BLAST+ (binary)
```bash
# Ubuntu/Debian:
sudo apt-get install -y ncbi-blast+
blastn -version && makeblastdb -version

# Windows dev: cài thủ công NCBI BLAST+ installer .exe hoặc test sau deploy Railway/Render.
```

### Cấu trúc thư mục backend — mở rộng Phase 3
```
backend/
├── algorithm/
│   ├── bound_fraction.py                    <- MỚI §4 — 2 hàm (binding/full)
│   ├── scoring.py                            <- CẬP NHẬT — SCORING_WEIGHTS_V4 (15 tiêu chí)
│   ├── constants.py                          <- CẬP NHẬT — Section O (đính chính SL07->SL04)
│   └── specificity_check/
│       ├── __init__.py
│       ├── family_crossreactivity.py         <- IMPLEMENT §5 (dùng miFam.dat)
│       ├── isomir_flag.py                    <- IMPLEMENT §6
│       ├── blast_offtarget.py                <- MỚI §8 (Ye 2012 + Kwok 1990 rules)
│       └── blast_cache.py                    <- MỚI §9.2 (SQLite, reuse local_db.py)
├── data/
│   ├── mirbase_family_overhangs.json         <- BUILD THẬT (§5.5)
│   ├── known_5prime_isomir_mirnas.json       <- BUILD THẬT (§6)
│   ├── blast_cache.sqlite                    <- MỚI, cache runtime
│   └── blast_db/
│       ├── mirbase_multi.{nhr,nin,nsq}       <- BLAST index từ miRBase mature.fa (v1.9: Ensembl đã loại)
│       └── metadata.json                     <- version + build_date (§9.4)
├── scripts/
│   ├── build_family_db.py                    <- MỚI §5.5 (miFam.dat + mature.fa)
│   └── build_blast_db.py                     <- MỚI §9.3 (Ensembl + miRBase, makeblastdb)
├── routes/
│   ├── design.py                              <- CẬP NHẬT (gọi bound_fraction + family check)
│   └── blast_check.py                         <- MỚI §8.10 (POST /api/blast-check)
└── .github/
    └── workflows/
        └── test_phase3.yml                    <- MỚI §10 (GitHub Actions CI)
```

---

## 4. Module 7: Bound Fraction 2-STEP (algorithm/bound_fraction.py)

### 4.1 Rationale
[SL04] khuyến nghị quan tâm bound fraction — % target bind đúng — thay vì chỉ Tm, vì hai primer cùng Tm có thể bound fraction khác nhau tại Ta thực tế do dH/dS khác nhau.

Forward primer stem-loop RT-qPCR có cấu trúc đặc biệt: **specific region (12-17 nt) bind cDNA + tail (3-12 nt) artificial GC-rich**. Phase 2 giải vấn đề này cho Tm bằng **2-step Tm** (§27.2). Bound fraction dùng cùng mô hình:

- **Round 1 — `bound_fraction_binding`:** % specific region bind cDNA tại **RT temp = 42°C** (SuperScript III RT extension step [K11]). **Quan trọng nhất** — quyết định RT-PCR khởi động. **[ĐÍNH CHÍNH v1.6]** Spec này trước đây ghi 60°C cho Round 1 — sai. Round 1 xảy ra tại bước RT (42°C), không phải bước qPCR annealing (60°C). Đã fix bằng `BOUND_FRACTION_RT_TEMP = 42.0` trong `constants.py`.
- **Round sau — `bound_fraction_full`:** % full primer bind amplicon (đã có tail-complement) tại **Ta=55°C (= Tm_target − 5°C)**. Tại đúng Tm=60°C, ~50% primer unbound theo định nghĩa nhiệt động học — evaluate tại đây cho score ~0 luôn, vô nghĩa về mặt thiết kế. Đánh giá tại Tm−5°C là nhiệt độ annealing thực tế qPCR. Ít quan trọng hơn Round 1 — amplicon đã có sẵn. **[FIX v1.9]**

Nguồn: [SL04]; [P3GS] Primer Bound% (Opt 97.0)

### 4.2 Constants (đính chính nguồn v1.2; recalibrate v1.9)
Kế thừa SPEC_phase2.md Section L, đổi ký hiệu:
```python
# Source: [SL04] SantaLucia & Hicks 2004, Annual Review of Biophysics
# (SPEC_phase2 hiện đang ghi [SL07] - đính chính khi có dịp cập nhật)
BOUND_FRACTION_RT_TEMP        = 42.0  # [K11] SuperScript III RT extension step — Round 1
BOUND_FRACTION_ANNEALING_TEMP = 55.0  # [v1.9 FIX] Tm_target − 5°C = Ta thực tế qPCR
                                      # Cũ: 60.0°C (= Tm) → fraction ~50% by definition → score ~0 luôn
BOUND_FRACTION_MIN = 60.0   # [v1.9 FIX] Cũ: 90.0 — threshold cho long duplex ~27 nt, không phù hợp primer ngắn
BOUND_FRACTION_OPT = 80.0   # [v1.9 FIX] Cũ: 97.0 — primer 14 nt / 50% GC tại 42°C đạt ~63-80%; 97% không khả thi
BOUND_FRACTION_MAX = 100.0
PENALTY_WT_BOUND_LT = 1.0    # [P3P Penalties]
PENALTY_WT_BOUND_GT = 1.0    # [P3P Penalties]
```

**Lý do recalibrate v1.9:**
- Nhiệt động học: tại đúng Tm (60°C), 50% duplex và 50% single-strand là định nghĩa của Tm → bound fraction ~50% với mọi primer tốt → score ≈ 0 với threshold cũ (OPT=97%). Evaluate tại Tm−5°C = 55°C cho primer Tm=60°C: fraction ≈ 82% → score ≥100.
- Calibration short oligo: OPT=97%/MIN=90% được thiết lập cho long symmetric-duplex hybridization (~27 nt equimolar). Primer RT 12–17 nt tại 42°C và primer full 22–24 nt tại 55°C thực tế chỉ đạt 60–85%.
- Formula suboptimal: `(fract-50)/40*70` hardcode anchor 50% và range 40 từ threshold cũ → sai sau khi đổi MIN. Mới: `fract/MIN*70` — tuyến tính từ 0%→0 đến MIN%→70, consistent với MIN constant.

### 4.3 Công thức
```python
def _calculate_bound_fraction(sequence: str, params: dict, temp_c: float) -> float:
    """
    [SL04] formula:
        dG = dH - T * dS
        K  = exp(-dG / (R * T))    # T = temp_c + 273.15 K
        Ct = dna_conc_nm / 1e9     # mol/L từ nM
        fract(%) = (1 / (1 + sqrt(1 / ((Ct/4) * K)))) * 100
    dna_conc = P3_DEFAULT_DNA_CONC = 200.0 nM (Phase 2 chuẩn hoá)
    temp_c: nhiệt độ evaluate — 42°C (Round 1) hoặc 55°C (Round 2)
    """
```

### 4.4 Lấy dH và dS từ primer3-py (QUYẾT ĐỊNH v1.5)

**Vấn đề:** `primer3.calc_tm()` chỉ trả về Tm (float), KHÔNG expose dH/dS trực tiếp. Nhưng công thức bound fraction cần cả dH và dS.

**Giải pháp — verified bằng test thực tế v1.5:**

Dùng `primer3.calc_heterodimer(primer, reverse_complement(primer))`. Vì thermodynamics của primer bind với reverse-complement của nó CHÍNH LÀ thermodynamics của perfect duplex primer-cDNA. Test:

```python
>>> import primer3
>>> r = primer3.calc_heterodimer('ATCGATCGATCGATCG', 'CGATCGATCGATCGAT')
>>> r.dh, r.ds, r.dg, r.tm
(-126200.0, -354.58, -16225.5, 49.82)   # cal/mol, cal/(mol·K), cal/mol, °C
```

`ThermoResult` object có sẵn 4 attribute: `.tm`, `.dh`, `.ds`, `.dg`. Đây là API chính thức primer3-py, không phải hack. Documented trong `primer3.thermoanalysis.ThermoResult`.

**Implementation:**
```python
def _get_thermodynamics_for_perfect_duplex(sequence: str, params: dict) -> tuple[float, float]:
    """
    Trả (dH, dS) cho perfect duplex của `sequence` bind với reverse complement của nó.
    Unit: cal/mol cho dH, cal/(mol·K) cho dS.
    """
    p3 = _get_p3_params(params)   # từ Phase 2 thermodynamics.py
    revcomp = _reverse_complement(sequence)
    result = primer3.calc_heterodimer(
        seq1=sequence,
        seq2=revcomp,
        mv_conc=p3["mv_conc"],
        dv_conc=p3["dv_conc"],
        dntp_conc=p3["dntp_conc"],
        dna_conc=p3["dna_conc"],
    )
    return result.dh, result.ds

def _calculate_bound_fraction(sequence: str, params: dict, temp_c: float) -> float:
    """[SL04] formula, dùng calc_heterodimer để lấy dH/dS.
    temp_c: 42.0 (Round 1 RT) hoặc 55.0 (Round 2 qPCR annealing)
    """
    import math
    R = 1.987  # cal/(mol·K), gas constant
    T = temp_c + 273.15   # K — nhận từ caller, không hardcode
    dna_conc_nm = params.get("primerConcentration", P3_DEFAULT_DNA_CONC)   # nM

    dH, dS = _get_thermodynamics_for_perfect_duplex(sequence, params)
    dG = dH - T * dS   # cal/mol
    K = math.exp(-dG / (R * T))
    Ct = dna_conc_nm / 1e9   # mol/L
    fract = (1 / (1 + math.sqrt(1 / ((Ct / 4) * K)))) * 100
    return round(fract, 2)
```

**Lưu ý cache:** dùng `functools.lru_cache` với key `(sequence, mv_conc, dv_conc, dntp_conc, dna_conc)` — reuse pattern memoization Phase 2 v2.8.3. Với candidates gọi bound_fraction nhiều lần, cache hit rate rất cao (specific region ngắn, tail patterns lặp lại).

### 4.5 API (2 hàm public)
```python
def calculate_bound_fraction_binding(specific_region: str, params: dict) -> float:
    """Round 1: % specific region bind cDNA tại 42°C (RT step). Quan trọng nhất."""
    return _calculate_bound_fraction(specific_region, params, BOUND_FRACTION_RT_TEMP)

def calculate_bound_fraction_full(full_primer: str, params: dict) -> float:
    """Round sau: % full primer bind amplicon tại 55°C (Ta = Tm_target − 5°C)."""
    return _calculate_bound_fraction(full_primer, params, BOUND_FRACTION_ANNEALING_TEMP)
```

### 4.6 Scoring (chung cho cả 2 hàm) — recalibrate v1.9

```python
def score_bound_fraction(fract: float) -> dict:
    """
    [v1.9 recalibrated — OPT=80%, MIN=60%]
    fract >= OPT (80%):              score = 100
    MIN (60%) <= fract < OPT (80%):  score = 70 + (fract-MIN)/(OPT-MIN) * 30  # tuyến tính 70→100
    fract < MIN (60%):               score = max(0, fract/MIN * 70)             # tuyến tính 0→70

    Cũ (v1.8 và trước):
    fract >= 97: 100
    90 <= fract < 97: 70 + (fract-90)/7 * 30
    fract < 90: max(0, (fract-50)/40 * 70)   ← hardcode 50/40 từ threshold cũ
    """
```

### 4.7 Unit tests
```python
def test_bound_fraction_binding_at_opt_scores_100():
    # OPT recalibrated to 80% (v1.9) — cũ: 97.0
    assert score_bound_fraction(80.0)["score"] == 100

def test_bound_fraction_full_below_min_scores_low():
    # MIN recalibrated to 60% (v1.9); 40% < 60% → suboptimal, score < 70 — cũ: 85.0
    assert score_bound_fraction(40.0)["score"] < 70

def test_binding_vs_full_independent():
    specific = "ATCGATGCAT"
    full     = "GCGCGC" + specific
    fb = calculate_bound_fraction_binding(specific, DEFAULT_PARAMS)
    ff = calculate_bound_fraction_full(full, DEFAULT_PARAMS)
    assert 0 <= fb <= 100 and 0 <= ff <= 100

def test_calc_heterodimer_returns_thermodynamics():
    """Verify primer3-py workaround: calc_heterodimer trả dH/dS đúng."""
    import primer3
    r = primer3.calc_heterodimer('ATCGATCGATCGATCG', 'CGATCGATCGATCGAT')
    assert r.dh < 0    # exothermic (spontaneous binding)
    assert r.ds < 0    # entropy decrease (duplex ordered)
    assert r.dg < 0    # negative dG = binding favorable
    assert 40 < r.tm < 60   # reasonable Tm range for 16 nt duplex

def test_bound_fraction_formula_matches_santalucia():
    # So giá trị tính tay theo [SL04] cho 1 primer cụ thể
    ...
```

---

## 5. Module 8: Family Cross-Reactivity (algorithm/specificity_check/family_crossreactivity.py)

Đã có thiết kế đầy đủ ở SPEC_phase2.md §30 — Phase 3 chỉ implement code thật + chuyển source family definition sang **miFam.dat**.

### 5.1 Rationale
Stem-loop RT primer có 6 nt overhang complementary với 3' end mature miRNA. Cùng family, members khác 1-2 nt → cross-reaction. Chen 2005 Fig.7: cross-reaction 0.1-3.7% giữa let-7 members.

Nguồn: [Chen05] Fig.7; [Kramer/K11]; [SL98]

### 5.2 Algorithm (nguyên bản §30.2-30.4)
1. Extract overhang = 6 nt cuối mature miRNA
2. Identify family từ **miFam.dat** (§5.5 — thay heuristic)
3. Với mỗi sibling: Hamming distance + delta-Tm (NN model, perfect-duplex)
4. Risk classification (bảng 5.3)
5. Auto-extension 6->8 nt nếu HIGH risk

### 5.3 Risk Classification (giữ nguyên §30.3)
| Mismatches | delta-Tm | Risk |
|---|---|---|
| 0 | any | IDENTICAL |
| 1 | < 5°C | HIGH |
| 1 | >= 5°C | LOW |
| 2 | any | LOW |
| >= 3 | any | SAFE |

### 5.4 Map risk → scoring criterion
```python
FAMILY_DISCRIMINATION_RISK_SCORE = {
    "SAFE": 100,
    "LOW": 70,
    "HIGH": 30,
    "IDENTICAL": 0,
    "no_family_data": 100,   # note rõ trong explanation
}
# Worst-case: risk tệ nhất trong tất cả siblings quyết định score
```
Weight `SCORING_WEIGHTS_V4`: **0.05**.

### 5.5 Data source — `miFam.dat` (thay heuristic v1.1)

> **[PRODUCTION STATUS — 2026-07-01]** miFam.dat KHÔNG còn available từ miRBase v22.1. URL `https://www.mirbase.org/download/miFam.dat` trả về HTTP 500. File đã bị remove khi miRBase chuyển sang web-based interface. **Production implementation dùng seed-based grouping thay thế** (`mirbase_family_overhangs.json` — 367 families, 929 hsa- miRNAs, build từ `mature.fa` với 7-nt seed window). Tính năng đang hoạt động đúng trên production.

**Format miFam.dat (archived reference):**
```
AC   MIPF0000001
ID   let-7
MI   MI0000060  hsa-let-7a-1
MI   MI0000061  hsa-let-7a-2
MI   MI0000063  mmu-let-7a-1
//
AC   MIPF0000002
ID   mir-17
...
```

**Script `backend/scripts/build_family_db.py`:**
```python
"""
1. Tải miFam.dat: https://www.mirbase.org/download/miFam.dat  [hiện trả HTTP 500]
2. Tải mature.fa multi-species
3. Parse miFam.dat -> mỗi family: list precursor MI IDs
4. Join mature.fa -> precursor MI -> mature miRNA sequences
5. Trích overhang 6 nt cuối cho từng mature
6. Output: mirbase_family_overhangs.json (schema §30.5) + field `species`
"""
```

**Lợi ích (nếu miFam.dat available):**
- Loại Limitation #4 §32 (heuristic fail khi user nhập accession `MIMAT0000062` thay vì tên).
- Đồng nhất với phân loại chính thức miRBase (peer-reviewed).
- Auto-update khi miRBase release mới.

### 5.6 Known Limitations (cập nhật)
Kế thừa §30.7, §32 nhưng **bỏ Limitation #4** (đã fix bằng miFam.dat). Còn lại:
1. delta-Tm là approximation (Tm perfect duplex, không mismatch duplex thực).
2. Data offline: chỉ update khi chạy lại script.
3. Loop-sequence cross-reactivity không implement.

### 5.7 Unit tests
```python
def test_let7a_family_loaded_from_miFam():
    family = load_family("let-7")
    assert any(m["id"] == "hsa-let-7a-5p" for m in family["members"])
    assert any(m["id"] == "mmu-let-7a-5p" for m in family["members"])

def test_let7a_vs_let7c_matches_chen2005():
    """1 mismatch, risk HIGH nếu delta_tm < 5."""
    ...

def test_no_family_data_returns_safe_score():
    assert score_family_discrimination_risk("no_family_data") == 100

def test_family_detection_works_with_accession():
    """Limitation #4 đã fix."""
    family = identify_family_by_accession("MIMAT0000062")
    assert family is not None and family["id"] == "let-7"

def test_family_discrimination_weight_in_v4():
    assert SCORING_WEIGHTS_V4["family_discrimination"] == 0.05
```

---

## 6. Module 9: isoMiR Flag (algorithm/specificity_check/isomir_flag.py)

Đã có thiết kế đầy đủ SPEC_phase2 §31 — implement nguyên bản.

- Logic: `in_risk_window = (forward_3prime_position <= risk_window_nt)` (§31.2)
- **Warning-only** — không vào scoring
- Data: `known_5prime_isomir_mirnas.json` **v1.0.0 (literature-verified, 2026-07-01)** — tất cả PLACEHOLDER đã thay bằng citations PubMed thực

### 6.1 Data v1.0.0 — 8 entries, tất cả verified

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

`evidence_level` taxonomy:
- **study_specific**: ≥1 primary paper explicitly reported 5'-isomiR với sequence-level evidence + read counts
- **review_supported**: documented across multiple independent deep-sequencing datasets; cited in systematic reviews — no single primary PMID retrieved but widely reproduced

### 6.2 Return dict — key đã đổi tên

Key `data_warning` → `co_amplification_warning` (biology-first naming, 2026-07-01):

```python
# Khi miRNA found trong DB:
{
    "isomir_discrimination_risk": bool,
    "mirna_name": str,
    "forward_3prime_position": int,
    "known_5prime_shift_nt": int,
    "risk_window_nt": int,
    "evidence_level": str,           # "study_specific" | "review_supported"
    "note": str,
    "co_amplification_warning": str, # biology-first warning message
}

# Khi miRNA không có trong DB:
{
    "isomir_discrimination_risk": False,
    "mirna_name": str,
    "forward_3prime_position": int,
    "risk_window_nt": None,
    "note": str,
    "data_warning": str,             # giữ nguyên key cũ cho unknown case
}
```

### 6.3 Logic note (vestigial geometric check — v2.1: RECOMMEND REMOVE)

`in_risk_window = (forward_3prime_position <= risk_window_nt)`. Với `specific_length` thực tế (12-17 nt) >> `risk_window_nt` (2-3), điều kiện này **KHÔNG BAO GIỜ True** cho primer trong range spec. Flag hiện chỉ identify **miRNAs WHERE co-amplification risk exists** (DB lookup only); geometric sub-check không có tác dụng thực tế.

**Quyết định v2.1:** Bỏ geometric check `in_risk_window` khỏi code. Hàm flag đơn giản hóa thành:
1. Lookup miRNA ID trong `known_5prime_isomir_mirnas.json`
2. Nếu found → `isomir_discrimination_risk = True` + trả `co_amplification_warning`
3. Nếu not found → `isomir_discrimination_risk = False` + `data_warning` (absence ≠ no isomiR exists)

Geometric sub-check (`forward_3prime_position <= risk_window_nt`) là dead code — remove để tránh confusion. Nếu cần trong tương lai (primer < 8 nt, ngoài range spec hiện tại), thêm lại với logic rõ ràng.

```python
def test_isomir_flag_triggers_for_known_mirna(): ...    # DB lookup → risk=True
def test_isomir_flag_absent_for_unlisted_mirna(): ...   # absence != no isomiR exists
def test_evidence_level_field_present(): ...             # evidence_level in return dict
def test_co_amplification_warning_key(): ...             # key renamed from data_warning
```

---

## 7. Scoring Engine — SCORING_WEIGHTS_V4 (12 → 15 tiêu chí)

### 7.1 Bảng weight — v4 (Phase 3 ra mắt) → v4.1 (v1.9 rebalance)

| Tiêu chí | V3 (12) | V4 ra mắt | **V4.1 (v1.9)** | Ghi chú v1.9 |
|---|---|---|---|---|
| tm_accuracy | 0.20 | 0.20 | **0.20** | core, giữ nguyên |
| mfe_stemloop | 0.15 | 0.15 | **0.14** | body 44 nt cố định; variance thấp |
| tm_binding_accuracy | 0.10 | 0.10 | **0.10** | core, giữ nguyên |
| hairpin_penalty | 0.10 | 0.08 | **0.08** | |
| dimer_penalty | 0.10 | 0.08 | **0.08** | |
| end_stability | 0.10 | 0.08 | **0.08** | |
| **bound_fraction_binding** | — | **0.05** | **0.05** | round 1 (cDNA) |
| **bound_fraction_full** | — | **0.03** | **0.03** | round sau (amplicon) |
| gc_content | 0.07 | 0.08 | **0.08** | |
| **family_discrimination** | — | **0.05** | **0.05** | risk từ miFam.dat |
| tm_pair_match | 0.05 | 0.03 | **0.01** | reverse cố định Tm≈60.4°C → redundant |
| gc_clamp | 0.03 | 0.02 | **0.04** | 3' GC critical cho extension |
| primer_size | 0.04 | 0.02 | **0.02** | |
| amplicon_size | 0.04 | 0.02 | **0.02** | |
| gc_skew | 0.02 | 0.01 | **0.02** | G-quadruplex risk signal |
| **TỔNG** | **1.00** | **1.00** | **1.00** | verified |

```python
# SCORING_WEIGHTS_V4 — v4.1 (commit b36f124, v1.9)
SCORING_WEIGHTS_V4 = {
    "tm_accuracy":             0.20,
    "mfe_stemloop":            0.14,  # -0.01: body 44 nt cố định, chỉ overhang 6 nt thay đổi
    "tm_binding_accuracy":     0.10,
    "hairpin_penalty":         0.08,
    "dimer_penalty":           0.08,
    "end_stability":           0.08,
    "bound_fraction_binding":  0.05,
    "bound_fraction_full":     0.03,
    "gc_content":              0.08,
    "family_discrimination":   0.05,
    "tm_pair_match":           0.01,  # -0.02: reverse cố định Tm≈60.4°C → redundant với tm_accuracy
    "gc_clamp":                0.04,  # +0.02: 3' end GC là critical cho polymerase extension
    "primer_size":             0.02,
    "amplicon_size":           0.02,
    "gc_skew":                 0.02,  # +0.01: G-quadruplex risk signal
}
assert abs(sum(SCORING_WEIGHTS_V4.values()) - 1.00) < 0.001   # = 1.00
```

**Lý do chia 5:3 cho bound fraction:** round 1 quyết định RT-PCR khởi động. Nếu fail, không có amplicon cho round sau. Tỷ lệ 5:3 ≈ 1.67 phản ánh "quan trọng hơn nhưng không áp đảo".

**Lý do rebalance v1.9:**
- `mfe_stemloop` 0.15→0.14: Tất cả designs dùng cùng 44-nt body; MFE chỉ thay đổi theo 6-nt overhang → inter-candidate variance thấp → không xứng đáng 15%.
- `tm_pair_match` 0.03→0.01: Universal reverse Tm ≈ 60.4°C (cố định). Forward target là 60°C. Bất kỳ primer nào score cao `tm_accuracy` đều tự động score cao `tm_pair_match` → redundant, giảm về 1%.
- `gc_clamp` 0.02→0.04: Primer không có GC tại 3' end (score 0) gần như không thể extend. Tác động 2 điểm (0.02×100) quá thấp so với tầm quan trọng sinh học.
- `gc_skew` 0.01→0.02: Tín hiệu G-quadruplex; tăng nhẹ để có tác động ≥2 điểm.

**isomir_flag KHÔNG trong weights** (warning-only §31).
**BLAST off-target KHÔNG trong weights** (optional, endpoint riêng).

### 7.2 Unit test
```python
def test_scoring_weights_v4():
    assert abs(sum(SCORING_WEIGHTS_V4.values()) - 1.00) < 0.001
    assert len(SCORING_WEIGHTS_V4) == 15
    assert SCORING_WEIGHTS_V4["bound_fraction_binding"] > SCORING_WEIGHTS_V4["bound_fraction_full"]
    assert "isomir_flag" not in SCORING_WEIGHTS_V4
```

---

## 8. Module 10: BLAST Off-target (algorithm/specificity_check/blast_offtarget.py)

Chi tiết đầy đủ theo Ye 2012 + Kwok 1990 (v1.3). Kiến trúc hệ thống (cache/circuit breaker/rate limit) ở §9 (v1.4).

### 8.1 Kiến trúc
- Tách khỏi `/api/design` — không ảnh hưởng pipeline chính.
- Endpoint `POST /api/blast-check` optional theo yêu cầu người dùng.
- Công cụ: Local BLAST+ (`blastn` subprocess).

### 8.2 Database — **miRBase only** (v1.9)

- **miRBase** (multi-species mature.fa) — build chung với Module 8. ~48K sequences, ~2 MB index.
- ~~**Ensembl human cDNA GRCh38**~~ — **ĐÃ LOẠI (v1.9).** Lý do khoa học: DNase treatment trước bước RT loại toàn bộ genomic DNA và unspliced RNA khỏi mẫu. Template còn lại cho RT-PCR chỉ là mature miRNA. Off-target risk trong stem-loop RT-qPCR giới hạn ở **miRNA family cross-reactivity** — đã được miRBase multi-species cover đầy đủ. Ensembl cDNA gây false positives (mRNA hits) không liên quan sinh học và chiếm phần lớn BLAST_MAX_HITS_RETURNED.

**Trước v1.9:** `dbs = [_MIRBASE_DB, _ENSEMBL_DB]`
**v1.9+:** `db_available = [_MIRBASE_DB] if _db_exists(_MIRBASE_DB) else []`

**v2.0 — DB unavailable behavior:** Nếu `db_available` rỗng (DB chưa build), `check_offtarget` raise `FileNotFoundError` ngay lập tức. Trước v2.0, hàm silently trả về `overall_risk='SAFE'` với 0 hits — frontend hiển thị "No significant off-target hits detected." mặc dù không có kiểm tra nào được chạy. Raise exception để API route trả 500, frontend hiển thị error state thay vì false SAFE.

```python
if not db_available:
    raise FileNotFoundError(
        f"BLAST database not found at {_MIRBASE_DB!r}. "
        "Run 'python scripts/build_blast_db.py' to build it first."
    )
```

**HTTP status cho route `blast_check.py`:** Khi `check_offtarget` raise `FileNotFoundError`, route phải catch và trả **HTTP 503** (Service Unavailable), không phải 500:
```python
# routes/blast_check.py
try:
    result = check_offtarget(...)
except FileNotFoundError as e:
    return jsonify({"error": str(e), "retry_after": None}), 503
```
Lý do: 503 báo "service tạm thời không có" (admin cần chạy build script), semantic đúng hơn 500 ("lỗi server bất ngờ"). Frontend đã handle 503 qua `CircuitOpenError` component (§13.5.2).

### 8.3 BLAST parameters (Ye 2012 defaults)

Nguồn: Ye 2012 §Implementation:
> "detect a target that contains up to 35% mismatches to the primer sequence. The default BLAST expect value cutoff is 30,000 for the primer-only case... word size of seven (standard BLAST uses 11), 50,000 for the maximum number of database sequences (standard BLAST uses 250) and 1 for match reward to mismatch penalty ratio."

```python
BLAST_WORD_SIZE = 7                # [Ye12] - vs standard 11
BLAST_EVALUE_CUTOFF = 30000        # [Ye12] - primer-only case, cao hơn standard 3000 lần
BLAST_MAX_TARGET_SEQS = 50000      # [Ye12] - vs standard 250
BLAST_REWARD = 1                   # [Ye12] - match reward
BLAST_PENALTY = -1                 # [Ye12] - mismatch penalty, ratio 1:1
BLAST_TASK = "blastn-short"        # cho query ngắn <30 nt
```

**Word size 7 giới hạn:** Ye 2012 §Comparison note "will miss any targets that have 6 or fewer consecutive matches to a primer" - probability sai lệch ~0.5% cho primer 20 nt với 2 mismatch random.

### 8.4 NW global alignment sau BLAST (Ye 2012)

Ye 2012 §Implementation:
> "the NW global alignment algorithm is incorporated into Primer-BLAST to realign any regions that are not fully aligned by BLAST."

Lý do: BLAST local alignment có thể miss mismatch ở 5' hoặc 3' end (giảm score cục bộ). Ye 2012 Fig.5 Example 1: BLAST bỏ sót G:G mismatch tại 3'-terminal vì làm giảm alignment score.

**Implementation:**
```python
def realign_blast_hit_with_nw(primer: str, subject_region: str) -> dict:
    """
    Sau khi có BLAST hit, dùng Needleman-Wunsch global alignment
    trên toàn bộ chiều dài primer để lấy đúng số mismatch + vị trí.

    Dùng biopython pairwise2 hoặc parasail — không viết NW từ đầu.
    """
```

### 8.5 Default specificity thresholds (Ye 2012)

Ye 2012 §User Interface (mặc định Primer-BLAST public server):
> "at least one primer (for a given primer pair) must have **two or more mismatches** to unintended targets in the **last five bases at the 3' end**, and that any targets with **six mismatches or more** to at least one primer should be ignored."

```python
# [Ye12] Primer-BLAST defaults
PRIMER_BLAST_MIN_TOTAL_MISMATCHES = 2       # Ye12 - tổng mismatch tối thiểu
PRIMER_BLAST_3PRIME_WINDOW = 5              # Ye12 - "last 5 bases at 3' end"
PRIMER_BLAST_3PRIME_MIN_MISMATCHES = 2      # Ye12 - trong 5 base cuối
PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES = 6    # Ye12 - safe nếu >=6 mismatch
```

### 8.6 3'-terminal mismatch classification (Kwok 1990 Table III)

**KEY INSIGHT:** Không phải mọi mismatch bằng nhau. Kwok 1990 test thực nghiệm 12 loại mismatch tại 3'-terminal với HIV-1 gag PCR (800 μM dNTP):

| Primer 3'-base | Template 3'-base | Product yield (relative) | Category |
|---|---|---|---|
| A | G | 1/100 (~1%) | **BLOCKING** |
| G | A | 1/100 (~1%) | **BLOCKING** |
| C | C | 1/100 (~1%) | **BLOCKING** |
| A | A | 1/20 (~5%) | **REDUCING** |
| T | C/G/T | 1.0 | **TOLERANT** |
| C/G | T | 1.0 | **TOLERANT** |
| G | G | 1.0 (800 μM); poor (50 μM) | context-dep, mặc định **TOLERANT**; ở vùng Tm sát đích (classifier v4) hạ CRITICAL → **HIGH** |
| còn lại (C:A, A:C) | | 1.0 | **TOLERANT** |

Các cặp Watson–Crick (A:T, T:A, G:C, C:G) là MATCH, không thuộc bảng này. Abstract Kwok 1990 (PMID 2179874): *"All other 3'-terminal mismatches were efficiently amplified, although the G:G mismatches appeared to be more sensitive to sequence context and dNTP concentrations"*; *"mismatches of T with either G, C, or T had a minimal effect"*; *"The presence of a mismatched T at the 3'-terminus, however, allowed significant amplification even when coupled with an adjacent mismatch."*

Trích Kwok 1990 §Conclusions:
> "A:G and C:C resulted in approximately a 100-fold reduction... A:A mismatch moderately reduced PCR amplification efficiency per cycle... some 3'-terminal mismatches (T:C, T:G, T:T, G:G, and A:C) appear to amplify as efficiently as the fully complementary primer-template duplex."

**Implementation:**
```python
# [Kwok90] Table III - loại mismatch tại 3'-terminal, phân loại theo tác động PCR
KWOK_3PRIME_MISMATCH_CATEGORY = {
    # (primer_base, template_base) -> category
    ("A","G"): "BLOCKING",  ("G","A"): "BLOCKING",  ("C","C"): "BLOCKING",
    ("A","A"): "REDUCING",
    # Còn lại TOLERANT (T:X, X:T, G:G, C:A, A:C, C:G, G:C, ...)
}

def classify_3prime_mismatch(primer_3prime_base: str, template_3prime_base: str) -> str:
    """Trả về 'BLOCKING' | 'REDUCING' | 'TOLERANT' | 'MATCH' theo Kwok 1990."""
    if primer_3prime_base == template_3prime_base:
        return "MATCH"
    return KWOK_3PRIME_MISMATCH_CATEGORY.get(
        (primer_3prime_base, template_3prime_base),
        "TOLERANT"   # mặc định theo Kwok 1990 - hầu hết mismatch còn lại đều tolerant
    )
```

### 8.7 Risk classification tổng hợp (Ye 2012 + Kwok 1990)

Logic cuối cùng cho 1 hit BLAST vs 1 primer:

```python
def classify_hit_risk(primer: str, alignment: dict) -> str:
    """
    alignment = {"mismatches": int, "mismatch_positions": [int],
                 "primer_3prime_base": str, "template_3prime_base": str,
                 "coverage": float}

    Returns: "SAFE" | "MEDIUM" | "HIGH" | "CRITICAL"
    """
    total_mm = alignment["mismatches"]

    # Rule 1 [Ye12]: ignore threshold
    if total_mm >= PRIMER_BLAST_IGNORE_ABOVE_MISMATCHES:   # >=6
        return "SAFE"

    # Rule 2 [Ye12]: đếm mismatch trong 5 base cuối 3' end
    primer_len = len(primer)
    mm_in_3prime_window = sum(
        1 for pos in alignment["mismatch_positions"]
        if pos >= primer_len - PRIMER_BLAST_3PRIME_WINDOW
    )

    # Rule 3 [Kwok90]: phân loại 3'-terminal mismatch
    terminal_category = classify_3prime_mismatch(
        alignment["primer_3prime_base"],
        alignment["template_3prime_base"],
    )

    # Combining rules:
    if terminal_category == "MATCH":
        # 3' terminal khớp -> risk theo số mismatch tổng
        if total_mm <= 2:  return "CRITICAL"   # <=2 mm tổng, 3' khớp -> gần identical
        if total_mm <= 4:  return "HIGH"
        return "MEDIUM"

    if terminal_category == "BLOCKING":
        # A:G, G:A, C:C tại 3' terminal -> PCR ~1% (Kwok90) -> luôn SAFE
        return "SAFE"

    if terminal_category == "REDUCING":
        # A:A -> PCR ~5%
        if total_mm >= PRIMER_BLAST_MIN_TOTAL_MISMATCHES: return "MEDIUM"
        return "HIGH"

    # terminal_category == "TOLERANT" (T:X, X:T, G:G, ...)
    # Vẫn nguy hiểm - Kwok90 cho thấy PCR gần như bình thường
    # Ye12 default: cần >=2 mm total AND >=2 mm trong 5 base cuối để SAFE
    if mm_in_3prime_window >= PRIMER_BLAST_3PRIME_MIN_MISMATCHES:
        return "MEDIUM"    # có mm gần 3' end -> giảm hiệu suất
    return "HIGH"          # 3' end tolerant + mm chỉ ở giữa/5' -> nguy hiểm
```

### 8.8 Ma trận risk (tổng kết)

| Total mm | 3' terminal category | mm trong 5 base cuối | Risk |
|---|---|---|---|
| >=6 | any | any | SAFE (Ye12 ignore) |
| any | BLOCKING (A:G, G:A, C:C) | any | SAFE (Kwok90 ~1% PCR) |
| <=2 | MATCH | any | CRITICAL |
| <=4 | MATCH | any | HIGH |
| >4, <6 | MATCH | any | MEDIUM |
| any (<6) | REDUCING (A:A) + total>=2 | any | MEDIUM |
| any (<6) | REDUCING (A:A) + total<2 | any | HIGH |
| any (<6) | TOLERANT + mm_3'>=2 | >=2 | MEDIUM |
| any (<6) | TOLERANT + mm_3'<2 | <2 | HIGH |

### 8.9 Endpoint `POST /api/blast-check`

```json
// Request
{
  "forward_primer": "CACGCATGGAAGGACGGG",
  "reverse_primer": "CCAGTGCAGGGTCCGAGGTA",
  "mirna_id": "hsa-miR-21-5p"     // để loại self-hit
}

// Response
{
  "forward_primer_hits": [
    {
      "subject_id": "ENST00000...",
      "organism": "Homo sapiens",
      "gene_name": "PIK3CG",
      "alignment": {
        "identity_pct": 94.7,
        "coverage_pct": 100.0,
        "mismatches": 1,
        "mismatch_positions": [12],
        "primer_3prime_base": "G",
        "template_3prime_base": "G",
        "terminal_category": "MATCH"
      },
      "evalue": 0.003,
      "risk": "HIGH",
      "risk_reason": "1 total mismatch, 3' terminal matches - potential off-target amplification"
    }
  ],
  "reverse_primer_hits": [...],
  "summary": {
    "total_hits": 5,
    "critical_count": 0,
    "high_risk_count": 1,
    "medium_risk_count": 2,
    "safe_count": 2,
    "cross_species_excluded": 3623,   // [THÊM 2026-07-01] số hits miRBase khác species bị loại
    "overall_risk": "HIGH",
    "hits_truncated": false           // [THÊM 2026-07-01] true nếu hit >= BLAST_MAX_HITS_RETURNED (200)
  },
  "cache": {"hit": false, "cache_key": "abc123..."},
  "database_info": {
    "mirbase_version": "22.1",
    "build_date": "2026-06-15",
    "age_days": 16,
    "outdated_warning": false
    // "ensembl_version" ĐÃ BỎ (v1.9) — Ensembl không còn trong pipeline
  }
}
```

### 8.10 Overall risk logic
```
if any hit CRITICAL:       overall = "CRITICAL"
elif any hit HIGH:         overall = "HIGH"
elif any hit MEDIUM:       overall = "MEDIUM"
else:                      overall = "SAFE"
```

### 8.11 Cross-species filtering (thêm 2026-07-01)

**Vấn đề:** miRBase mature.fa chứa ~49K sequences đa loài. miRNA conserved (vd. let-7) tồn tại ở hầu hết vertebrates với sequence gần như giống hệt nhau. Nếu không filter, các orthologs khác loài sẽ:
- Lấp đầy BLAST_MAX_HITS_RETURNED (200) với false positives sinh học
- Che khuất genuine human off-targets

**Giải pháp:** `_extract_species_prefix(mirna_id)` — extract 3-letter prefix từ miRNA ID (`hsa-miR-21-5p` → `hsa-`). Hits trong `mirbase_multi` không bắt đầu bằng prefix này bị loại; chỉ tính `cross_species_excluded` để báo cáo.

```python
def _extract_species_prefix(mirna_id: Optional[str]) -> str:
    """
    'hsa-miR-21-5p' → 'hsa-'
    'mmu-let-7a'    → 'mmu-'
    None / malformed → MIRBASE_HUMAN_PREFIX ('hsa-')
    """
    if mirna_id:
        m = re.match(r'^([a-z]{3})-', mirna_id.lower())
        if m:
            return m.group(1) + "-"
    return MIRBASE_HUMAN_PREFIX   # fallback = 'hsa-'
```

**Smoke test kết quả (2026-07-01, hsa-miR-21-5p):**
- cross_species_excluded: 3,623 — filter loại đúng
- Self-hit (hsa-miR-21-5p) excluded correctly: 0 hits có "miR-21" trong subject_id
- Cache: miss (lần 1) → hit (lần 2) — SQLiteKVCache TTL 30d hoạt động đúng
- Database searched: mirbase_multi only (v1.9, Ensembl đã loại)

### 8.12 Self-hit detection cho precursor variants (v1.9)

**Vấn đề:** Cùng mature miRNA có thể được encode bởi nhiều precursor gene. miRBase list chúng như các FASTA entry riêng biệt:
```
hsa-miR-16-1-5p  (from hsa-mir-16-1)
hsa-miR-16-2-5p  (from hsa-mir-16-2)
```
Cả hai có sequence giống hệt `hsa-miR-16-5p`. Check cũ: `mirna_id.lower() in subject_id.lower()` → `"hsa-mir-16-5p" in "hsa-mir-16-1-5p"` = **False** → tất cả precursor variants xuất hiện trong off-target results của chính mình.

**Fix (v1.9 + v2.0):**

```python
def _normalize_mirna_name(name: str) -> str:
    """
    Strip precursor copy number: hsa-miR-16-1-5p → hsa-mir-16-5p
    Guard ≥5 components: hsa-miR-1-5p (4 components) → UNCHANGED

    v2.0: regex widened [12] → \d+ để bắt copy number ≥3.
    Project data có hsa-miR-509-3-5p, hsa-miR-550a-3-5p (copy number 3).

    Examples:
      hsa-miR-16-1-5p  → hsa-mir-16-5p   (5 components, drops '1')
      hsa-miR-16-2-5p  → hsa-mir-16-5p   (5 components, drops '2')
      hsa-miR-509-3-5p → hsa-mir-509-5p  (5 components, drops '3') [v2.0]
      hsa-miR-1-5p     → hsa-mir-1-5p    (4 components → unchanged)
      hsa-let-7a-1-5p  → hsa-let-7a-5p   (5 components, drops '1')
    """
    parts = name.strip().lower().split('-')
    if (len(parts) >= 5
            and re.fullmatch(r'[35]p', parts[-1])
            and re.fullmatch(r'\d+', parts[-2])):   # v2.0: [12] → \d+
        parts.pop(-2)
    return '-'.join(parts)

def _is_self_hit(subject_id: str, mirna_id: str, m_norm: Optional[str] = None) -> bool:
    """
    v2.0: bỏ nhánh `s in m` (false-positive); thêm word-boundary prefix check.
    m_norm: pre-computed _normalize_mirna_name(mirna_id.lower()) từ caller.

    Vấn đề với `s in m` cũ: 'hsa-mir-1' là substring của 'hsa-mir-10-5p'
    → off-target thật bị suppress. Fix: chỉ kiểm tra `m in s` (mirna_id là
    substring của subject, e.g. FASTA ID có accession suffix); nhánh ngược
    dùng word-boundary check để phân biệt 'hsa-mir-16' vs 'hsa-mir-10-5p'.
    """
    s, m = subject_id.lower(), mirna_id.lower()
    # mirna_id là substring của subject (FASTA ID có thể có accession suffix)
    if m in s:
        return True
    # subject là prefix word-boundary của mirna_id
    # 'hsa-mir-16' match 'hsa-mir-16-5p', KHÔNG match 'hsa-mir-10-5p'
    if len(s) <= len(m) and m.startswith(s) and (len(m) == len(s) or m[len(s)] == '-'):
        return True
    # Normalized: strip copy numbers rồi áp dụng cùng boundary rules
    s_norm = _normalize_mirna_name(s)
    if m_norm is None:
        m_norm = _normalize_mirna_name(m)
    if m_norm in s_norm:
        return True
    if len(s_norm) <= len(m_norm) and m_norm.startswith(s_norm) and (len(m_norm) == len(s_norm) or m_norm[len(s_norm)] == '-'):
        return True
    return False
```

**Tại sao guard ≥5 components?** `hsa-miR-1-5p` chỉ có 4 components `['hsa', 'miR', '1', '5p']`. Penultimate là `'1'` — nhưng đây là MIR NAME number, không phải precursor copy number. Nếu không guard, sẽ strip thành `hsa-miR-5p` (sai).

**Edge case — thiếu arm designation (v2.1 note):** Nhánh `if m in s` có thể cho false positive nếu user nhập miRNA ID không có arm suffix (vd. `hsa-miR-1` thay vì `hsa-miR-1-5p`). Khi đó `m = 'hsa-mir-1'` là substring của `'hsa-mir-10-5p'` → self-hit false positive, off-target thật bị suppress. Giải pháp: **API route `blast_check.py` phải validate `mirna_id` có arm suffix (-5p/-3p) trước khi gọi `check_offtarget`**. Nếu thiếu arm, trả 400 Bad Request với message gợi ý format đúng. User lookup từ miRBase (§routes/mirbase.py) luôn trả full ID có arm nên đây chỉ là edge case khi user nhập tay.

**Performance (v2.0):** `m_norm` được tính 1 lần trong `check_offtarget` rồi truyền xuống `_check_primer` → `_is_self_hit`. Trước v2.0, mỗi BLAST hit gọi `_normalize_mirna_name(mirna_id)` lại từ đầu (N lần tính cùng 1 giá trị).

### 8.13 Cổng Tm duplex — bộ phân loại v2 (2026-10-28)

**Thứ tự cổng trong `classify_hit_risk`:**
1. **Neo 3′** — ≥2 nt đầu 3′ của mồi nằm ngoài vùng căn → SAFE. Đứng trước vì Tm của cả duplex không thấy được đầu 3′ có bắt cặp hay không.
2. **Cổng Tm duplex** (khi có Tm đúng đích):
   - `Tm_off < Tm_on − 10 °C` → SAFE
   - `Tm_on − 10 ≤ Tm_off < Tm_on − 5` → luật Ye 2012 / Kwok 1990, **tối đa MEDIUM**
   - `Tm_off ≥ Tm_on − 5 °C` → CRITICAL; **HIGH** nếu base cuối 3′ hở (1 nt) hoặc là mismatch chặn Kwok (A:G, G:A, C:C)
3. **Luật Ye/Kwok** — khi không có Tm đúng đích (không biết trình tự đích): áp dụng như cũ, kèm luật neo tối thiểu 10 nt.

**Tính Tm.** `primer3.calc_heterodimer(mồi, revcomp(miRNA))` — mồi xuôi mang trình tự sense của miRNA và bám cDNA (bổ sung đảo). Cùng điều kiện với thiết kế (`effective_p3`: mv hiệu dụng Na⁺+K⁺+Tris⁺, Mg²⁺ theo von Ahsen 2001, dNTP, nồng độ mồi); frontend gửi `metadata.design_settings.effective_p3` và `metadata.mirna_sequence`. Trình tự đầy đủ của off-target lấy bằng `blastdbcmd` (DB có `-parse_seqids`).

**Vì sao so với Tm đúng đích chứ không phải Ta.** Vùng đặc hiệu được thiết kế để bám ở ~45 °C (`TM_BINDING_TARGET`); đuôi 5′ chỉ nâng Tm lên ~60 °C từ chu kỳ 2. Đo trên 189 mồi xuôi của bộ validation: Tm duplex đúng đích trung vị **45,5 °C** (33,1–58,6); **161/189 (85 %) < 50 °C** — nếu dùng `Tm_off < Ta − 10` thì chính miRNA đích cũng bị xếp SAFE. Off-target đi đúng con đường bám chu kỳ 1 như đích, nên câu hỏi là "bám kém đích bao nhiêu".

**Cơ sở của biên 10 °C.** Theo quy ước của Primer3, ngưỡng mispriming nhiệt động được đặt thấp hơn Tm tối thiểu của mồi (`PRIMER_MIN_TM`) 10 °C: *"The default value is 10 degrees lower than the default value of PRIMER_MIN_TM"* (`PRIMER_MAX_SELF_ANY_TH`, `PRIMER_MAX_HAIRPIN_TH`) và *"47.0 would be a reasonable choice if PRIMER_MIN_TM is 57.0"* (`PRIMER_MAX_TEMPLATE_MISPRIMING_TH`, mặc định −1 = tắt trong Primer3, 47 trong Primer3Plus) — đã đối chiếu manual primer3.org. Các ngưỡng `*_TH` của Primer3 là giá trị Tm tuyệt đối, không phải độ chênh; việc đo khoảng 10 °C từ Tm_on của vùng đặc hiệu là lựa chọn của tool, chưa hiệu chỉnh bằng thực nghiệm. Ước tính hai trạng thái (van 't Hoff, ΔH ≈ −90 kcal/mol, tự tính — không lấy từ tài liệu): quanh Tm_on ≈ 45 °C, Tm_off thấp hơn 5 °C → tỷ lệ bám off/on ~10 %; thấp hơn 10 °C → ~1 %, dưới ngưỡng cross-reactivity 5 %.

**Phân tích độ nhạy** (`backend/scripts/blast_tm_gate_sensitivity.py` → `benchmark/blast_tm_gate_sensitivity.json`, bộ phân loại v5): mồi xuôi #1 của bộ validation, 175/178 mồi (loại 3 "putative miRNA" Busk 2014: không có trong miRBase, bài báo không ghi loài). Biên SAFE 5/10/15/20 °C, biên CRITICAL cố định 5 °C. Báo riêng nhóm stem-loop (100 mồi) — nhóm Busk 2014 (75 mồi, hệ poly(A), không có mồi RT stem-loop) có trong file JSON.

Số liệu dưới đây dùng mồi #1 của **algorithm v3.3.0**, bộ phân loại v5 (chạy lại 2026-10-29). Lịch sử stem-loop, biên 10 °C: v3 29 hit CRITICAL / 13 mồi → v4 32 / 13 (base đầu 3′ bị BLAST cắt được khôi phục, §8.15) → **v5 63 / 27** (hit cùng họ seed không còn được miễn trừ, §8.16).

| Biên SAFE (stem-loop, 100 mồi) | Mồi SAFE / MEDIUM / HIGH / CRITICAL | Hit CRITICAL / HIGH / MEDIUM |
|---|---|---|
| 5 °C | 73 / 0 / 0 / 27 | 63 / 0 / 0 |
| **10 °C** | **61 / 12 / 0 / 27** | **63 / 0 / 72** |
| 15 °C | 42 / 31 / 0 / 27 | 63 / 0 / 157 |
| 20 °C | 34 / 39 / 0 / 27 | 63 / 0 / 271 |
| Không có cổng Tm | 17 / 9 / 8 / 66 | 343 / 132 / 529 |

Busk 2014 (75 mồi), biên 10 °C: hit CRITICAL 121 → 27 (mồi có CRITICAL 52 → 21). Ở mọi cài đặt, 24 hit (20 stem-loop, 4 Busk) thuộc nhóm trùng trình tự (xem dưới) và không được tính vào bậc rủi ro nào.

CRITICAL/HIGH không đổi theo biên SAFE là **do cấu trúc** (chỉ phụ thuộc biên 5 °C), không phải bằng chứng thực nghiệm; biên SAFE chỉ dời hit giữa SAFE và MEDIUM, và số MEDIUM tăng đều chứ không có "bình nguyên" quanh 10 °C. Lựa chọn 10 °C vì thế dựa trên quy ước Primer3 + ước tính van 't Hoff, không dựa trên độ nhạy.

**Giới hạn (đưa vào Thảo luận).**
- Tm toàn duplex không phân biệt được đầu 3′ khớp hoàn toàn với mismatch giữa duplex; cổng neo 3′ đứng trước để bù một phần.
- Không mô hình bước RT: off-target thật phải qua cả mồi RT (overhang 6 nt, 16 °C → 42 °C, Chen 2005) — rủi ro báo cáo cao hơn thực tế. Không áp cổng cho mồi RT (cần nhiệt độ RT và mô hình DNA:RNA, Sugimoto 1995).
- Không mô hình LNA (primer3 không có tham số LNA).
- Chỉ mục family chỉ có hsa/mmu/rno → paralog ở loài khác không được gộp "same-family" và hiện là CRITICAL.
- Paralog khác nhau ở giữa trình tự (miR-23a/b, miR-103/107, miR-17/106a/20b) vẫn là CRITICAL vì mồi xuôi bám như nhau; thực tế chúng chỉ được phân biệt (một phần) nhờ mồi RT ở đầu 3′.
- Nhóm "trùng trình tự" coi lệch đầu ≤ 2 nt là cùng một phân tử; khác biệt đầu 3′ (isomiR, chú giải lệch) chỉ được phân biệt ở bước RT, không mô hình ở đây.
- Ngưỡng chưa hiệu chỉnh bằng wet-lab. Đề xuất: thử cross-reactivity mồi miR-21 với oligo tổng hợp miR-374a-3p (Tm duplex 22,1 °C so với 44,3 °C đúng đích; trước v2 bị xếp CRITICAL) — kết quả < 5 % là bằng chứng trực tiếp cho cổng Tm.

**Sửa kèm.** Bảng Kwok tra theo base **mạch khuôn** (= bổ sung của base sense off-target); mồi ngược universal không còn BLAST; khóa cache gồm `BLAST_CLASSIFIER_VERSION` + trình tự đích + điều kiện muối; DB tìm qua `BLASTDB` (đường dẫn có dấu cách).

### 8.14 Chính đích và hit trùng trình tự — bộ phân loại v3 (2026-10-28)

Mỗi hit BLAST cùng loài được xét theo thứ tự (trình tự đầy đủ lấy bằng `blastdbcmd`):

1. **Chính đích** — tên khớp với `mirna_id` **có ranh giới**: bằng nhau, hoặc tên này nối dài tên kia bằng `-` sau khi chuẩn hóa số bản sao tiền chất (`hsa-miR-16-1-5p` ↔ `hsa-miR-16-5p`; `ssc-miR-21` ↔ `ssc-miR-21-5p`). Khi biết cả hai trình tự, phải **tương thích**: giống hệt trên phần giao nhau ≥ 15 nt, mỗi đầu lệch ≤ 2 nt (`SELF_MAX_END_SHIFT`). → bỏ qua.
2. **Trùng trình tự** — tên khác nhưng trình tự giống hệt hoặc tương thích: bản sao ở locus khác (ath-miR156a = 156b–f) hoặc mục đã đổi tên/chú giải (Busk `ssc-miR-20` = 22.1 `ssc-miR-20a-5p`, lệch 1 nt đầu 3′). → `identical_sequence_hits`, không phân loại rủi ro, không tính vào `overall_risk`.
3. Khác loài → `cross_species_excluded`. 4. Còn lại → các cổng của §8.13 và §8.15.

**Vì sao không còn so chuỗi con.** Luật cũ `mirna_id in subject_id` làm `ssc-miR-21` khớp `ssc-miR-210` (che off-target thật); tên sai định dạng (`ssc-miR15a`) thì không khớp và chính đích bị báo CRITICAL.

**Vì sao cần trình tự khi tên khớp.** miRBase đổi chú giải theo phiên bản: `mmu-miR-138-5p` 22.1 là `AGCTGG…`, bản Busk 2014 là `CAGCTGG…` (lệch 1 nt) → vẫn là chính đích; còn `ssc-miR-670` 22.1 là trình tự **khác hẳn** bản Busk → là off-target, không phải chính đích. Ngưỡng 2 nt bao trọn độ lệch quan sát được giữa 22.1 và các trình tự Busk 2014 (138-5p, 31-3p, 194-5p, 7134-3p, 1468: 1–2 nt).

Khi không biết trình tự đích (mirna_id không có trong DB, không gửi `mirna_sequence`), chỉ dùng luật tên — vì vậy route vẫn bắt buộc `-5p/-3p`: ID thiếu nhánh khớp tên với cả hai nhánh. `check_offtarget(species=…)` cho phép chỉ định loài khi tên không có tiền tố.

---


### 8.15 Bộ phân loại v4 — base đầu 3′ thật và Tm theo khung đọc (2026-10-29)

**Base đầu 3′ bị BLAST cắt.** Căn chỉnh cục bộ không bao giờ kết thúc bằng một mismatch, nên base cuối 3′ của mồi bị lệch luôn bị cắt và hiện ra như "dangling" (Ye 2012 Fig. 5). Đo trên 175 mồi: 234 hit sợi plus thiếu 1 nt (148 thực ra là TOLERANT, 46 BLOCKING, 20 REDUCING) và 262 hit thiếu 2 nt (63 có base cuối khớp thật — trước đây bị gán SAFE sai). Với hit sợi plus (mồi = trình tự sense của off-target, bám vào cDNA của nó), v4 lấy các base đối diện từ trình tự đầy đủ của off-target, nối vào alignment rồi căn lại Needleman–Wunsch; chỉ các base vượt quá đầu off-target mới còn là "dangling".

**Luật Kwok 1990 (abstract, PMID 2179874) ở vùng Tm sát đích** (Tm_off ≥ Tm_on − 5 °C):

| Cặp mồi:khuôn ở đầu 3′ | Mức |
|---|---|
| khớp | CRITICAL |
| TOLERANT (trừ G:G) — *"efficiently amplified"* | CRITICAL |
| G:G — *"more sensitive to sequence context and dNTP concentrations"* | HIGH |
| BLOCKING (A:G, G:A, C:C) / REDUCING (A:A) | HIGH |
| base cuối vượt quá đầu off-target (không có khuôn) | HIGH |

**Hai base cuối cùng lệch** (bất kể Tm): SAFE — *"double mismatches … reduced PCR product yield dramatically"* — trừ khi base cuối của mồi là T → MEDIUM (*"a mismatched T at the 3'-terminus … allowed significant amplification even when coupled with an adjacent mismatch"*); nếu Tm_off thấp hơn Tm_on quá 10 °C thì vẫn SAFE.

**Tm_off theo khung đọc.** `calc_heterodimer` trên toàn off-target trả về duplex bền nhất ở bất kỳ đâu, có thể không phải duplex mà đầu 3′ của mồi kéo dài được. v4 chỉ tính Tm trên đoạn off-target đối diện mồi trong khung BLAST, cộng 1 base phía sau (thal chỉ tính năng lượng dangling của 1 base liền kề — trên chính đích, cửa sổ này cho Tm **trùng khớp** Tm_on tính trên cả miRNA, 111/111 mồi, nên Tm_on và Tm_off vẫn so sánh trực tiếp). Trên 542 hit có đầu 3′ bắt cặp: Tm toàn trình tự cao hơn Tm khung đọc trung bình 2,1 °C (tối đa 19 °C); 27 hit chuyển vùng xám → SAFE, 4 CRITICAL → vùng xám, 1 SAFE → vùng xám.

Hit sợi minus (mồi bổ sung với off-target sense, không bám cDNA của nó) giữ cách tính cũ; với cổng Tm chúng đều ra SAFE (1 MEDIUM trên 175 mồi).

### 8.16 Đặc hiệu cấp assay — mô hình ΔCq và bộ phân loại BLAST v5 (2026-10-29, algorithm v3.3.0)

**Vì sao đổi.** Đến v3.2.0 có hai kết luận đặc hiệu tách rời: BLAST chỉ hỏi *mồi xuôi* bám vào đâu (không xét bước RT), còn `overhang_collision` dùng ma trận rủi ro RT × FWD với cửa sổ **cố định vị trí** (`target[-6:]` so `other[-6:]`, `target[:L]` so `other[:L]`). Biến thể lệch 1 nt làm trượt cả cửa sổ → khoảng cách Hamming lớn → SAFE giả cho đúng nhóm dễ khuếch đại chung nhất. Thêm vào đó, BLAST miễn trừ hit cùng họ seed (`same_family_count`) và gộp mọi trình tự "tương thích" (đầu lệch ≤ 2 nt) thành "assay đo tổng".

**Mô hình.** Off-target chỉ cho tín hiệu khi qua **cả hai** bước: overhang RT bắt được nó, *và* mồi xuôi mồi được trên cDNA của nó (chỉ vài chu kỳ đầu chịu mismatch — sản phẩm sau đó mang trình tự mồi). Độ trễ cộng lại:

  ΔCq_assay ≈ ΔCq_RT + ΔCq_FWD,  tín hiệu chéo ≈ 2^−ΔCq × 100 %.

Mỗi trục thử lệch đầu −2…+2 nt và giữ khung đọc cho ΔCq **nhỏ nhất**. Mọi giá trị lấy **cận dưới** của khoảng đã công bố (quyết định 2026-10-29) — mô hình dự đoán tín hiệu chéo cao nhất mà dữ liệu cho phép.

| Trục | Tình huống | ΔCq | Nguồn |
|---|---|---|---|
| RT | đầu 3′ off-target dài hơn 1–2 nt | 0 | Schamberger 2014 Fig. 6 (*"'GA' specific assay detected all three isoforms similarly"*) |
| RT | ngắn hơn 1 nt | 0 | *"Assays specific for the 'GACA' and 'GAC' 3′ ends detected both … similarly"* |
| RT | ngắn hơn 2 nt | 3,0 | *"'GA' ending was detected with ~3 Ct delay"* |
| RT | 1 mismatch rG·dT | 4,75 | Chen 2005: 3,7 % (assay let-7a đo let-7c) |
| RT | 1 mismatch khác, vị trí 1–3 từ đầu 3′ mồi RT | 7,0 | Chen 2005: 0,1 % ≈ 10 Cq; khoảng 7–10 → 7 |
| RT | 1 mismatch khác, vị trí 4–6 | 3,5 | Czimmerer 2013: 6,8–9,0 % |
| RT | ≥ 2 mismatch | 8,0 | Chen 2005: ≤ 0,3 % |
| FWD | base cuối 3′ nhóm nặng A–A, A–G, G–A, G–G, C–C | 8,3 | Stadhouders 2010 (PMC2797725): 8,29–9,09 Ct |
| FWD | nhóm trung bình T–C, C–T, T–T | 3,8 | 3,77–4,75 Ct |
| FWD | nhóm nhẹ A–C, C–A, T–G, G–T | 1,0 | 0,99–1,91 Ct |
| FWD | vị trí 2 (kế cuối) | 1,9 | trung bình 1,87 Ct (không có khoảng) |
| FWD | vị trí 3–5 | 0,5 | trung bình 0,53 / 0,71 Ct (vị trí 4 không đo) |
| FWD | ≥ 6 nt từ đầu 3′ | 0 | Kwok 1990; Ye 2012 |
| FWD | ≥ 2 mismatch trong 5 nt cuối | 8,3 | Stadhouders: Taq không khuếch đại — *trừ* base cuối T với đúng 1 mismatch kế bên (Kwok 1990) → lấy giá trị của cặp cuối |
| FWD | độ bền duplex | 0,66 × (Tm_on − Tm_off), trần 8,3 | tự tính (van 't Hoff, như §8.13); ΔCq_FWD = max(bảng, Tm) |

Tm_off tính trên khung đọc của mồi + 1 base phía sau, cùng quy ước BLAST v4 (§8.15). Nhãn theo tiêu chí thành công của đề cương: **CO-AMPLIFIED** ΔCq < 3,3 (> 10 %), **PARTIAL** 3,3–4,3 (5–10 %), **DISCRIMINATED** ≥ 4,3 (< 5 %).

**Ba nhóm off-target.** *isomiR đầu 5′* (khuếch đại chung, không tránh được), *isomiR đầu 3′* (khuếch đại chung hoặc phân biệt một phần, kèm ΔCq), *trùng trình tự* — báo cáo riêng, **không chấm điểm** (không thiết kế mồi nào tránh được; báo cáo kết quả là tổng isoform, Magee 2017). *miRNA khác* — nhãn tệ nhất quyết định tiêu chí `family_discrimination` (100 / 70 / 0) và là kết luận đặc hiệu chính trên giao diện ("Assay Specificity").

**BLAST (bộ phân loại v5).** Giữ làm chi tiết "mồi xuôi bám đâu". Hit cùng họ seed được đánh dấu (`same_seed_family`) và tính vào `overall_risk` như mọi hit; nhóm trùng trình tự tách thành `identical` / `isomir_5p` / `isomir_3p` (`identical_sequence_variants`). Mồi xuôi không kết thúc bằng tiền tố 5′ của đích (gõ sai, nhầm nhánh) → bỏ cổng Tm, ghi `tm_gate_note`. Route kiểm tra nồng độ (hữu hạn, mv/dna > 0) và nhận `species` (mã miRBase 3 chữ).

**Ví dụ — vùng mù ở giữa.** let-7a so với let-7d khác ở nt 1 và nt 16. Với mồi xuôi 12 nt, nt 16 nằm ngoài cả cửa sổ mồi xuôi (nt 1–12) lẫn overhang RT (nt 17–22): mô hình dự đoán khuếch đại chung (~94 %). Chen 2005 đo bằng TaqMan, probe phủ đoạn giữa mới phân biệt được; với SYBR không có lớp này. Dự đoán của mô hình là **giới hạn lạc quan** cho SYBR.

**Kiểm chứng đề xuất (thí nghiệm cross-reactivity của đề cương, oligo RNA tổng hợp cùng nồng độ):** let-7a ↔ let-7c (rG·dT ở bước RT, dự đoán ΔCq 4,75 — đây là điểm hiệu chỉnh, không phải kiểm chứng độc lập); miR-21-5p ↔ isomiR 0|+1 (dự đoán ΔCq ≈ 0); một cặp lệch đầu 5′ −1|0 (dự đoán ≈ 0); let-7a ↔ let-7d (vùng mù, dự đoán khuếch đại chung với SYBR).

**Giới hạn.** Giá trị tra đo ở enzyme/master mix khác (Stadhouders báo hiệu ứng lệch đến ~2 lần giữa các hệ RT-PCR) → chỉ là thứ tự độ lớn. Mô hình cộng hai trục giả định độc lập. Chưa tính độ phong phú tương đối của off-target trong mẫu (rủi ro thật = tín hiệu chéo × tỷ lệ nồng độ). Hệ số 0,66 Cq/°C tự suy, không từ tài liệu.

**Kết quả trên 165 miRNA thiết kế được (v3.2.0 → v3.3.0).** Mồi #1 giữ vùng bám ở 164/165 (đổi: mmu-miR-467c-5p, 12 → 13 nt); điểm #1 trung bình +0,67 (−3,7 … +5,3) — chủ yếu vì bản sao trùng trình tự không còn bị tính là CRITICAL. Nhãn tệ nhất: 68 DISCRIMINATED, 6 CO-AMPLIFIED, 1 PARTIAL, **90 không có chỉ mục** (chỉ mục overhang mới có hsa/mmu/rno). Các ca cảnh báo đều là paralog đã biết khó tách: miR-20a ↔ miR-17/106a/20b (ΔCq 1,0–1,7), let-7a ↔ let-7d (1,4), miR-103a-2 ↔ 103a-1 (0,2), miR-19a ↔ 19b (2,8), miR-669 (3,0), miR-27b ↔ 27a (3,5, PARTIAL). 14 mục isomiR/trùng trình tự (10 identical — thường là tên cũ ↔ tên miRBase 22.1, ví dụ hsa-miR-25 ↔ hsa-miR-25-3p; 4 isomiR 5′, ví dụ mmu-miR-467a/b).


## 9. Kiến trúc hệ thống — Cache, Circuit Breaker, Rate Limit, CI (v1.4)

### 9.1 Cache SQLite — Refactor `LocalDB` Week 1 thành base class `SQLiteKVCache` (QUYẾT ĐỊNH v1.5)

**Vấn đề:** Week 1 có `local_db.py` cache miRBase lookup. Phase 3 cần cache BLAST results. Reuse pattern hay copy-paste?

**Quyết định:** Refactor `LocalDB` Week 1 thành base class chung `SQLiteKVCache`, cả Week 1 (miRBase cache) và Phase 3 (BLAST cache) đều extend base này. Lý do:
- Tránh duplicate 50-100 dòng SQLite bootstrap (connect, create table, error handling)
- Backward-compatible với Week 1 nếu giữ nguyên method signatures
- Chuẩn hoá TTL/expiry logic ở 1 chỗ

**Bước triển khai (Claude Code follow):**

**Step 1 — Đọc `backend/utils/local_db.py` (Week 1)** để xác định 1 trong 2 tình huống:

- **Tình huống A — `LocalDB` đã generic (có `.get(key)`, `.set(key, value)`, `.delete(key)`):**
  Chỉ cần rename file thành `sqlite_kv_cache.py`, thêm cột `expires_at` vào schema, và cập nhật interface. Week 1 miRBase logic không đổi.

- **Tình huống B — `LocalDB` hardcoded cho miRBase (schema có cột `mirna_id`, `sequence`, `family`; method như `.get_by_mirna_id()`):**
  Tạo file mới `backend/utils/sqlite_kv_cache.py` với `SQLiteKVCache` base class. Refactor `LocalDB` cũ thành `MirbaseLocalDB(SQLiteKVCache)`, chỉ giữ methods miRBase-specific. Kiểm tra tất cả import `from utils.local_db import LocalDB` trong Week 1 code còn work.

**Step 2 — Base class `SQLiteKVCache`:**
```python
# backend/utils/sqlite_kv_cache.py
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional

class SQLiteKVCache:
    """
    Generic SQLite key-value cache with optional TTL.
    Reused by Week 1 (MirbaseLocalDB) and Phase 3 (BlastCache).
    """
    DEFAULT_SCHEMA = """
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            metadata TEXT,                       -- JSON blob for extra context
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP                 -- NULL = no expiry
        );
        CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at);
    """

    def __init__(self, db_path: str, table_name: str = "cache",
                 default_ttl_days: Optional[int] = None):
        self.db_path = db_path
        self.table = table_name
        self.default_ttl = default_ttl_days
        self._init_schema()

    def get(self, key: str) -> Optional[dict]:
        """Return {value, metadata, created_at} or None if not found / expired."""
        ...

    def set(self, key: str, value: str, metadata: dict = None,
            ttl_days: Optional[int] = None) -> None:
        """Store key -> value. TTL overrides default_ttl if provided."""
        ...

    def delete(self, key: str) -> bool: ...

    def cleanup_expired(self) -> int: ...

    def _init_schema(self): ...
```

**Step 3 — `BlastCache` (Phase 3):**
```python
# backend/algorithm/specificity_check/blast_cache.py
from ...utils.sqlite_kv_cache import SQLiteKVCache

BLAST_CACHE_TTL_DAYS = 30
BLAST_CACHE_DB_PATH = "backend/data/blast_cache.sqlite"

class BlastCache(SQLiteKVCache):
    def __init__(self):
        super().__init__(
            db_path=BLAST_CACHE_DB_PATH,
            table_name="blast_cache",
            default_ttl_days=BLAST_CACHE_TTL_DAYS,
        )

    def get_result(self, fwd: str, rev: str, db_version: str) -> Optional[dict]:
        key = self._compute_key(fwd, rev, db_version)
        entry = self.get(key)
        if entry:
            return json.loads(entry["value"])
        return None

    def set_result(self, fwd: str, rev: str, result: dict, db_version: str) -> None:
        key = self._compute_key(fwd, rev, db_version)
        self.set(
            key=key,
            value=json.dumps(result),
            metadata={"forward": fwd, "reverse": rev, "db_version": db_version},
        )

    @staticmethod
    def _compute_key(fwd: str, rev: str, db_version: str) -> str:
        raw = f"{fwd}|{rev or ''}|{db_version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

**Constants (cập nhật từ v1.4):**
```python
BLAST_CACHE_TTL_DAYS = 30           # v1.4 giữ nguyên
BLAST_CACHE_DB_PATH = "backend/data/blast_cache.sqlite"
```

**Kiểm tra tương thích Week 1 (nếu chọn Tình huống B):**
```python
def test_week1_mirbase_cache_still_works_after_refactor():
    """Regression test: Week 1 miRBase lookup vẫn work sau khi refactor LocalDB."""
    from utils.local_db import LocalDB   # legacy import
    db = LocalDB(":memory:")
    db.cache_mirna("hsa-miR-21-5p", {"sequence": "UAGCUUAUCAGACUGAUGUUGA"})
    assert db.get_mirna("hsa-miR-21-5p")["sequence"] == "UAGCUUAUCAGACUGAUGUUGA"
```

### 9.2 Circuit Breaker cho blastn subprocess

**Reuse:** `backend/utils/circuit_breaker.py` Week 1 (đã build cho RNAcentral).

**Constants:**
```python
BLAST_CB_FAILURE_THRESHOLD = 3      # 3 lần fail liên tiếp -> OPEN
BLAST_CB_RECOVERY_TIMEOUT = 60      # 60s trước khi thử HALF_OPEN
BLAST_CB_EXPECTED_EXCEPTIONS = (subprocess.CalledProcessError, subprocess.TimeoutExpired)
```

**Sử dụng:**
```python
@circuit_breaker(
    failure_threshold=BLAST_CB_FAILURE_THRESHOLD,
    recovery_timeout=BLAST_CB_RECOVERY_TIMEOUT,
    expected_exceptions=BLAST_CB_EXPECTED_EXCEPTIONS,
)
def run_blastn(query_fasta: str, db_path: str) -> str:
    result = subprocess.run(
        ["blastn", "-query", query_fasta, "-db", db_path, "-outfmt", "6", ...],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return result.stdout
```

Khi circuit OPEN: `/api/blast-check` trả HTTP 503 kèm `retry_after` header.

### 9.3 Rate Limiting

**Thư viện:** `flask-limiter` (thêm vào requirements.txt).

```python
# routes/blast_check.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@blast_check_bp.route("/api/blast-check", methods=["POST"])
@limiter.limit("10 per minute")    # v1.4 - user tự chọn
def blast_check(): ...
```

Khi vượt limit: HTTP 429 kèm `Retry-After` header (mặc định flask-limiter tự trả).

### 9.4 Database Version Tracking

**File:** `backend/data/blast_db/metadata.json` — v1.9 (miRBase only)
```json
{
  "mirbase_version": "CURRENT",
  "build_date": "2026-06-15",
  "sequences_count": {
    "mirbase_multi": 48885
  },
  "makeblastdb_version": "2.14.0+"
}
```
*(Fields `ensembl_version`, `ensembl_url`, `protein_coding_only` đã bỏ trong v1.9.)*

**Cảnh báo cũ:**
```python
BLAST_DB_STALE_WARN_DAYS = 90       # v1.4 - cảnh báo nếu build_date >90 ngày

def check_db_freshness(metadata_path: str) -> dict:
    """
    Trả về {age_days, outdated_warning, message}
    Nếu age > 90 ngày: outdated_warning=True, log WARNING, thêm vào response.
    """
```

Response `/api/blast-check` đã có field `database_info.outdated_warning` để frontend hiển thị badge cảnh báo.

### 9.5 Script `build_blast_db.py` + Ước tính storage (cập nhật v1.9)

**File:** `backend/scripts/build_blast_db.py`

**[v1.9 — Ensembl đã loại]** Ensembl human cDNA đã bị remove khỏi pipeline (§8.2). Database chỉ gồm miRBase mature.fa.

**Storage benchmark thực tế (v1.9 — miRBase only):**

| Component | File gốc (gz) | Giải nén | BLAST index (.nhr+.nin+.nsq+...) |
|---|---|---|---|
| miRBase mature.fa multi-species (~48K sequences) | ~0.6 MB | ~2 MB | **~2 MB** |

**Kiểm tra khả năng deploy:**
- **Railway free tier:** 1 GB disk → **OK** (~2 MB << 1 GB).
- **Render free tier:** ephemeral filesystem, mất khi restart → **KHÔNG dùng được** cho bất kỳ persistent DB nào.
- **Google Cloud Run:** stateless container, DB phải mount volume → phức tạp.

**Quyết định:** Railway là deploy target chính (đã chọn từ Phase 2).

**Script:**
```python
"""
1. Tải miRBase mature.fa multi-species
   URL: https://www.mirbase.org/download/mature.fa
2. Chạy `makeblastdb -in mature.fa -dbtype nucl -out mirbase_multi -parse_seqids`
3. Xoá FASTA gốc sau makeblastdb (giữ chỉ .nhr, .nin, .nsq)
4. Ghi metadata.json (§9.4) với version, build_date, sequences_count, size_mb
5. Verify build bằng `blastdbcmd -db mirbase_multi -info` — phải trả sequences_count > 0
6. Log tổng thời gian + kích thước database cuối
"""

MIRBASE_MATURE_URL = "https://www.mirbase.org/download/mature.fa"

def verify_db_build(db_path: str) -> dict:
    """
    `blastdbcmd -db <db_path> -info` để check DB build không corrupt.
    Return: {sequences_count, size_bytes, ok: bool}
    """
```

### 9.6 GitHub Actions CI

**File:** `.github/workflows/test_phase3.yml`
```yaml
name: Phase 3 Tests

on:
  push:
    branches: [main, phase3-*]
  pull_request:
    branches: [main]

jobs:
  test-algorithm:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          pip install -r requirements.txt
          sudo apt-get install -y ncbi-blast+
      - name: Unit tests (không cần database thật)
        run: pytest backend/tests/algorithm/ -v
      - name: Cache/CircuitBreaker/RateLimit tests
        run: pytest backend/tests/utils/ -v
      - name: Build script logic test với MOCK data
        run: |
          # Test build_family_db.py + build_blast_db.py logic
          # với miFam.dat mock + mature.fa mock (10-20 sequences)
          # KHÔNG build database thật (nặng, chậm, tốn CI runtime)
          pytest backend/tests/scripts/ -v -m "not slow"

  smoke-test:
    runs-on: ubuntu-latest
    needs: test-algorithm
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Start backend
        run: python backend/app.py &
      - name: Smoke test /api/blast-check with hsa-miR-21-5p
        run: pytest backend/tests/smoke/test_blast_check_e2e.py -v
```

**Test data mock cho scripts:**
```
backend/tests/fixtures/
├── miFam_mock.dat            # 3 families (let-7, mir-17, mir-21) với 5-6 members mỗi cái
├── mature_mock.fa            # ~20 mature miRNA sequences khớp với miFam_mock
└── ensembl_cdna_mock.fa      # ~50 transcript sequences (đủ để makeblastdb chạy)
```

### 9.7 Smoke test end-to-end

**File:** `backend/tests/smoke/test_blast_check_e2e.py`

```python
def test_hsa_mir_21_5p_forward_primer_finds_self():
    """
    Design primer cho hsa-miR-21-5p, gửi forward primer vào /api/blast-check.
    Expected: có ít nhất 1 hit với identity 100% (self-hit trong miRBase database).
    """
    fwd = "TAGCTTATCAGACTGATGTTGA"  # forward primer từ hsa-miR-21-5p
    response = client.post("/api/blast-check", json={
        "forward_primer": fwd,
        "reverse_primer": UNIVERSAL_REVERSE,
        "mirna_id": "hsa-miR-21-5p",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_hits"] >= 1
    # Self-hit trong miRBase phải là 100% identity
    assert any(h["alignment"]["identity_pct"] == 100.0 for h in data["forward_primer_hits"])

def test_rate_limit_blocks_11th_request_per_minute():
    """Rate limit 10/phút - request thứ 11 trong 60s phải HTTP 429."""
    for _ in range(10):
        r = client.post("/api/blast-check", json=VALID_PAYLOAD)
        assert r.status_code == 200
    r11 = client.post("/api/blast-check", json=VALID_PAYLOAD)
    assert r11.status_code == 429
    assert "Retry-After" in r11.headers

def test_cache_hit_returns_immediately():
    r1 = client.post("/api/blast-check", json=VALID_PAYLOAD)
    t1 = time.time()
    r2 = client.post("/api/blast-check", json=VALID_PAYLOAD)
    t2 = time.time()
    assert r1.json()["cache"]["hit"] is False
    assert r2.json()["cache"]["hit"] is True
    assert (t2 - t1) < 0.1   # cache hit phải <100ms

def test_circuit_breaker_opens_after_3_blastn_failures():
    """Mock blastn để fail 3 lần liên tiếp - request thứ 4 phải HTTP 503."""
    with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(...)):
        for _ in range(3):
            r = client.post("/api/blast-check", json=VALID_PAYLOAD)
            assert r.status_code == 500
        r4 = client.post("/api/blast-check", json=VALID_PAYLOAD)
        assert r4.status_code == 503
```

---

## 10. API Endpoint — cập nhật `routes/design.py` + mới `routes/blast_check.py`

### 10.1 `/api/design` — thay đổi tối thiểu
Output JSON Phase 2 giữ schema, mở rộng:
```json
{
  "top_n": [{
    "...": "... (giữ nguyên fields Phase 2)",
    "scores": {
      "...": "...",
      "bound_fraction_binding": 95.2,
      "bound_fraction_full": 88.7,
      "family_discrimination": 70.0
    },
    "family_cross_reactivity": { "...": "schema §30.5" },
    "isomir_flag": { "...": "schema §31.3" }
  }],
  "universal_reverse": {
    "...": "... (giữ nguyên fields Phase 2)",
    "stemloop_reverse_heterodimer": {
      "dg": -4.40,
      "risk_level": "PASS",
      "three_prime_overlap": false,
      "three_prime_bp": 0,
      "note": "Stem-loop RT × Universal Reverse (one-step PCR): ...",
      "protocol_note": "Relevant for one-step RT-qPCR protocols where all primers coexist in one tube. In two-step protocols, the stemloop RT primer is absent during PCR amplification and this interaction cannot occur."
    }
  }
}
```

**Ghi chú §10.1a — stemloop × reverse heterodimer:**
- Cặp này là **FIXED** (không phụ thuộc miRNA) — tính 1 lần per request, không per candidate.
- Buffer: PCR conditions (user params) — interaction xảy ra trong PCR step khi cả hai primer hiện diện.
- Scope: one-step RT-qPCR (all primers coexist). Two-step: stemloop absent during PCR → dimer không thể xảy ra.
- Chen 2005 actual pair: dG = −4.40 kcal/mol → PASS. High risk threshold: ≤ −9.0 kcal/mol AND 3' end complementarity ≥ 3 bp.
- HIGH/MODERATE risk → tự động promote lên `global_warnings` để user thấy ngay.
```

### 10.2 `/api/blast-check` — mới, xem §8.9

---

## 11. Thứ tự implement

1. `bound_fraction.py` + unit tests (Module 7)
2. Cập nhật `constants.py` (đính chính SL07 -> SL04) + `scoring.py` -> `SCORING_WEIGHTS_V4`
3. `build_family_db.py` (miFam.dat) -> `mirbase_family_overhangs.json` thật
4. `family_crossreactivity.py` — implement §30
5. Tích hợp family_discrimination vào `scoring.py`
6. `isomir_flag.py` — implement §31
7. Tích hợp `family_cross_reactivity` + `isomir_flag` vào `/api/design` output
8. `blast_cache.py` (SQLite reuse `local_db.py`) + unit tests
9. `build_blast_db.py` — benchmark thời gian/dung lượng
10. `blast_offtarget.py` — logic Ye 2012 + Kwok 1990 (§8.3-8.8)
11. `routes/blast_check.py` — endpoint + rate limit + circuit breaker
12. GitHub Actions workflow (`test_phase3.yml`)
13. Smoke test end-to-end với hsa-miR-21-5p
14. Frontend: nút "Check off-target" — xem §13

---

## 12. Định nghĩa "Phase 3 hoàn thành"

**Bắt buộc 100%:**

**Khoa học (v1.2):**
- [ ] `bound_fraction.py` có 2 hàm binding/full, đúng công thức [SL04]
- [ ] `SCORING_WEIGHTS_V4` = 15 tiêu chí, tổng 1.00, `binding > full` (0.05 > 0.03)
- [ ] `family_crossreactivity.py` implement đầy đủ §30, dùng **seed-based grouping** (miFam.dat HTTP 500 — §5.5)
- [ ] `mirbase_family_overhangs.json` build từ seed-based grouping + mature.fa multi-species
- [ ] Family detection đúng với accession qua seed lookup (miFam.dat unavailable — §5.5)
- [ ] `isomir_flag.py` implement §31, data verify với [Neilsen12]/[Morin08]
- [ ] Đính chính [SL07] -> [SL04] trong constants.py

**BLAST khoa học (v1.3):**
- [ ] BLAST params đúng [Ye12]: word_size=7, evalue=30000, reward:penalty=1:1, max_target_seqs=50000
- [ ] NW global alignment realign sau BLAST
- [ ] Default thresholds [Ye12]: >=2 mm trong 5 base cuối, >=6 mm total = SAFE
- [ ] 3'-terminal mismatch classification [Kwok90]: BLOCKING (A:G, G:A, C:C), REDUCING (A:A), TOLERANT
- [ ] Risk classification ma trận §8.8 đúng cho tất cả cases

**Kiến trúc hệ thống (v1.4):**
- [ ] SQLite cache TTL 30 ngày, reuse pattern `local_db.py` Week 1
- [ ] Circuit breaker blastn (3 fails liên tiếp -> OPEN, 60s recovery), reuse `circuit_breaker.py`
- [ ] Rate limit 10 req/phút/IP dùng flask-limiter
- [ ] Database metadata.json + cảnh báo >90 ngày
- [ ] `build_blast_db.py` verify checksum + `blastdbcmd -info` sau build
- [ ] GitHub Actions CI với mock data (không build DB thật trên CI)
- [ ] Smoke test hsa-miR-21-5p pass (self-hit 100%)
- [ ] Smoke test rate limit + cache hit + circuit breaker pass
- [ ] `POST /api/blast-check` không ảnh hưởng tốc độ `/api/design` (<5s vẫn giữ)
- [ ] All English output

**Quyết định implementation (v1.5):**
- [ ] Bound fraction dùng `primer3.calc_heterodimer(seq, revcomp(seq))` để lấy dH/dS (§4.4) — có test `test_calc_heterodimer_returns_thermodynamics`
- [ ] Refactor `LocalDB` Week 1 thành base class `SQLiteKVCache` (§9.1) — có regression test Week 1 miRBase cache vẫn work
- [ ] BLAST database build ≤ 500 MB trên Railway free tier (§9.5) — verify bằng `du -sh backend/data/blast_db/` sau build
- [ ] Nếu vượt limit: fallback `--protein-coding-only` mode với metadata.json ghi rõ mode đang chạy

**Cần làm rõ lúc implement:**
- (không còn — 3 vấn đề đã giải quyết ở v1.5: primer3-py dùng `calc_heterodimer` §4.4, storage ~370 MB fit Railway free §9.5, `LocalDB` refactor thành `SQLiteKVCache` §9.1)

**Frontend (v1.6):**
- [x] `useBlastCheck.js` hook — status: `idle | loading | done | error`, expose `run()` + `reset()`
- [x] Button "Check off-target" trong `PrimerSetCard` (expanded panel) — disabled khi `loading`
- [x] Loading spinner (animate-spin) + "Running…" text khi status = `loading`
- [x] Risk badge 4 mức: CRITICAL (red), HIGH (orange), MEDIUM (amber), SAFE (teal) — consistent với `RISK_STYLE` có sẵn
- [x] Error handling: 429 → retry countdown, 503 → circuit open message, timeout → timeout message, network → generic
- [x] Result panel: summary row + hits accordion (max 5 hits) + `database_info` staleness badge
- [x] Không gọi `/api/blast-check` tự động — phải user bấm nút

**Không làm trong Phase 3:**
- TaqMan probe design -> Phase 4
- PDF/CSV export -> Phase 4
- AI/LLM -> Phase riêng
- Alternative BLAST risk models (Kwok 1990 chỉ test HIV-1 gag context; mở rộng test/tuning tuỳ dữ liệu thực tế sau khi có feedback user)

---

## 13. Frontend Integration — Nút "Check off-target" (v1.6)

### 13.1 Tổng quan và placement

**Nguyên tắc thiết kế:**
- BLAST check tốn thời gian (5–30s); **không tự động** — user phải chủ động bấm
- Mỗi `PrimerSetCard` có forward primer khác nhau → state/result là **per-card** (local state trong `PrimerSetCard`, không lift lên parent)
- Universal reverse primer là cố định → giống nhau cho tất cả cards
- Gọi `POST /api/blast-check` với `forward_primer`, `reverse_primer`, `mirna_id`

**Placement:**
```
PrimerSetCard (expanded)
  ├── Primer sequences (forward/RT/reverse)
  ├── Score + structure checks
  ├── Heterodimer checks
  ├── isoMiR flag detail
  ├── Warnings
  ├── [NEW] OffTargetPanel  ← §13.4 — button + result, nằm trước ExportButtons
  └── ExportButtons
```

### 13.2 Hook `useBlastCheck.js`

**File:** `frontend/src/hooks/useBlastCheck.js`

```js
// useBlastCheck — manages a single /api/blast-check request lifecycle.
// Status machine: idle → loading → done | error
// Error shape: { type: '429'|'503'|'timeout'|'network'|'server', message, retryAfter? }

import { useState, useRef } from 'react';
import axios from 'axios';

const BLAST_TIMEOUT_MS = 70_000;  // 70s — longer than server 60s timeout

export default function useBlastCheck() {
  const [status, setStatus] = useState('idle');  // 'idle'|'loading'|'done'|'error'
  const [result, setResult] = useState(null);
  const [error,  setError]  = useState(null);
  const abortRef = useRef(null);

  async function run(forwardPrimer, reversePrimer, mirnaId) {
    if (status === 'loading') return;

    // Cancel any previous in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('loading');
    setResult(null);
    setError(null);

    try {
      const { data } = await axios.post(
        '/api/blast-check',
        { forward_primer: forwardPrimer, reverse_primer: reversePrimer, mirna_id: mirnaId },
        { signal: controller.signal, timeout: BLAST_TIMEOUT_MS }
      );
      setResult(data);
      setStatus('done');
    } catch (err) {
      if (axios.isCancel(err)) return;  // user navigated away — ignore

      const parsed = parseBlastError(err);
      setError(parsed);
      setStatus('error');
    }
  }

  function reset() {
    abortRef.current?.abort();
    setStatus('idle');
    setResult(null);
    setError(null);
  }

  return { status, result, error, run, reset };
}

// ── Error parser ──────────────────────────────────────────────────────────────

function parseBlastError(err) {
  const status = err.response?.status;
  const data   = err.response?.data;

  if (status === 429) {
    // Flask-Limiter injects Retry-After header (seconds)
    const retryAfter = parseInt(err.response?.headers?.['retry-after'] ?? '60', 10);
    return {
      type: '429',
      message: 'Rate limit reached — too many requests.',
      retryAfter,  // seconds; UI shows countdown
    };
  }
  if (status === 503) {
    return {
      type: '503',
      message: data?.error ?? 'BLAST service temporarily unavailable (circuit breaker open).',
      retryAfter: data?.retry_after ?? 60,
    };
  }
  if (err.code === 'ECONNABORTED' || err.code === 'ERR_CANCELED') {
    return { type: 'timeout', message: 'Check timed out after 70 s. Try again.' };
  }
  if (!err.response) {
    return { type: 'network', message: 'Network error — check your connection.' };
  }
  return {
    type: 'server',
    message: data?.error ?? `Server error (HTTP ${status}).`,
  };
}
```

### 13.3 Button + loading state

**Loading spinner** — dùng Tailwind `animate-spin`, consistent với pattern hiện tại:

```jsx
// ── BlastCheckButton ────────────────────────────────────────────────────────
// Standalone button component; all blast state lives in parent OffTargetPanel.

function BlastCheckButton({ onClick, loading, done }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`
        inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold
        border transition-colors
        ${loading
          ? 'bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed'
          : done
          ? 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
          : 'bg-white border-teal-300 text-teal-700 hover:bg-teal-50'
        }
      `}
    >
      {loading ? (
        <>
          <svg className="animate-spin h-3 w-3 text-slate-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Analyzing…
        </>
      ) : done ? (
        'Re-check off-target'
      ) : (
        'Check off-target'
      )}
    </button>
  );
}
```

**Disable rule:** button bị disable (`disabled`) chỉ khi `status === 'loading'`. Khi `status === 'done'`, button đổi label thành "Re-check off-target" và vẫn clickable (user có thể chạy lại sau khi DB cập nhật).

### 13.4 Risk badge styling

Dùng cùng `RISK_STYLE` map đã có trong `PrimerSetCard.jsx` — không định nghĩa lại:

```js
// Reuse từ PrimerSetCard.jsx (move to shared const nếu cần)
const BLAST_RISK_STYLE = {
  CRITICAL: 'text-red-700   bg-red-50   border-red-300',
  HIGH:     'text-orange-700 bg-orange-50 border-orange-300',
  MEDIUM:   'text-amber-700  bg-amber-50  border-amber-200',
  SAFE:     'text-teal-700   bg-teal-50   border-teal-200',
};

// Ý nghĩa mỗi mức (tooltip text):
const BLAST_RISK_TOOLTIP = {
  CRITICAL: 'Near-perfect off-target match — primer likely amplifies non-target sequence',
  HIGH:     'Strong off-target hit — risk of non-specific amplification',
  MEDIUM:   'Moderate off-target — monitor with melt curve or no-template control',
  SAFE:     'No significant off-target detected (≥6 mismatches or blocking 3′ mismatch)',
};
```

**Overall risk badge** hiển thị trong summary row theo overall_risk từ API (§8.10).

**Per-hit risk badge** hiển thị trong bảng hits, lấy từ `hit.risk` của mỗi entry trong `forward_primer_hits`.

### 13.5 Error handling — 3 trường hợp đặc biệt

#### 13.5.1 HTTP 429 — Rate limit

Hiển thị error panel với countdown timer:

```jsx
function RateLimitError({ retryAfter, onRetry }) {
  const [seconds, setSeconds] = useState(retryAfter);

  useEffect(() => {
    if (seconds <= 0) { onRetry?.(); return; }
    const id = setTimeout(() => setSeconds((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [seconds]);

  return (
    <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
      <span className="font-semibold">Rate limit reached.</span>
      {' '}Please wait{' '}
      <span className="font-mono font-bold tabular-nums">{seconds}s</span>
      {' '}before checking again.
    </div>
  );
}
```

`onRetry` — callback được gọi khi countdown về 0, reset error state về `idle` (không tự gọi lại BLAST, chỉ enable button).

#### 13.5.2 HTTP 503 — Circuit breaker open

```jsx
function CircuitOpenError({ retryAfter }) {
  return (
    <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
      <span className="font-semibold">BLAST service temporarily unavailable.</span>
      {' '}The service is recovering from errors — retry in ~{retryAfter}s.
      {' '}This does not affect primer design results above.
    </div>
  );
}
```

Lưu ý: không show "Service unavailable" theo nghĩa hệ thống bị lỗi — cần giải thích rõ đây là circuit breaker, primer design vẫn hoạt động bình thường.

#### 13.5.3 Timeout và network error

```jsx
function GenericBlastError({ error, onRetry }) {
  const icons = { timeout: '⏱', network: '⚡', server: '⚠' };
  return (
    <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-700 flex items-center justify-between gap-3">
      <span>
        <span className="mr-1">{icons[error.type] ?? '⚠'}</span>
        {error.message}
      </span>
      <button
        type="button"
        onClick={onRetry}
        className="text-teal-700 font-semibold hover:underline shrink-0"
      >
        Retry
      </button>
    </div>
  );
}
```

### 13.6 Result panel layout — `OffTargetPanel`

**Component:** `frontend/src/pages/SearchPage/ResultsSection/OffTargetPanel.jsx` (file mới)

```jsx
// OffTargetPanel — renders the "Check off-target" button + result inline.
// All state managed locally via useBlastCheck hook.

import { useState } from 'react';
import useBlastCheck from '../../../../hooks/useBlastCheck.js';

const BLAST_RISK_STYLE = {
  CRITICAL: 'text-red-700   bg-red-50   border-red-300',
  HIGH:     'text-orange-700 bg-orange-50 border-orange-300',
  MEDIUM:   'text-amber-700  bg-amber-50  border-amber-200',
  SAFE:     'text-teal-700   bg-teal-50   border-teal-200',
};

export default function OffTargetPanel({ forwardPrimer, reversePrimer, mirnaId }) {
  const { status, result, error, run, reset } = useBlastCheck();
  const [hitsExpanded, setHitsExpanded] = useState(false);

  function handleRun() {
    run(forwardPrimer, reversePrimer, mirnaId);
  }

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      {/* ── Panel header ── */}
      <div className="bg-slate-50 border-b border-slate-200 px-3 py-2 flex items-center justify-between">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Off-target (BLAST)
        </p>
        <BlastCheckButton
          onClick={handleRun}
          loading={status === 'loading'}
          done={status === 'done'}
        />
      </div>

      {/* ── Idle state — brief explanation ── */}
      {status === 'idle' && (
        <div className="px-3 py-2">
          <p className="text-xs text-slate-500">
            Checks primer against miRBase (all species) for miRNA family cross-reactivity
            using blastn (Ye 2012 + Kwok 1990 rules). Results are cached 30 days.
          </p>
        </div>
      )}

      {/* ── Error states ── */}
      {status === 'error' && error && (
        <div className="px-3 py-2">
          {error.type === '429' && (
            <RateLimitError retryAfter={error.retryAfter} onRetry={reset} />
          )}
          {error.type === '503' && (
            <CircuitOpenError retryAfter={error.retryAfter ?? 60} />
          )}
          {(error.type === 'timeout' || error.type === 'network' || error.type === 'server') && (
            <GenericBlastError error={error} onRetry={reset} />
          )}
        </div>
      )}

      {/* ── Done state — result panel ── */}
      {status === 'done' && result && (
        <div className="px-3 py-3 space-y-3">
          {/* ── Summary row ── */}
          <OverallRiskRow result={result} />

          {/* ── Database staleness warning ── */}
          {result.database_info?.outdated_warning && (
            <div className="rounded bg-amber-50 border border-amber-200 px-2 py-1.5 text-xs text-amber-700">
              ⚠ BLAST database is {result.database_info.age_days} days old (updated{' '}
              {result.database_info.build_date}). Consider rebuilding for latest sequences.
            </div>
          )}

          {/* ── Hits accordion (max 5 shown) ── */}
          {result.summary?.total_hits > 0 && (
            <HitsAccordion
              hits={result.forward_primer_hits ?? []}
              expanded={hitsExpanded}
              onToggle={() => setHitsExpanded((v) => !v)}
            />
          )}

          {/* ── Cache / DB info footnote ── */}
          <p className="text-xs text-slate-400">
            {result.cache?.hit ? 'Cached result' : 'Fresh result'}
            {result.database_info && ` · DB: miRBase ${result.database_info.mirbase_version} (built ${result.database_info.build_date})`}
          </p>
        </div>
      )}
    </div>
  );
}
```

#### 13.6.1 `OverallRiskRow`

```jsx
function OverallRiskRow({ result }) {
  const overall = result.summary?.overall_risk ?? 'SAFE';
  const counts  = result.summary ?? {};
  const style   = BLAST_RISK_STYLE[overall] ?? BLAST_RISK_STYLE.SAFE;

  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${style}`}>
          {overall}
        </span>
        <span className="text-xs text-slate-600">
          {counts.total_hits ?? 0} hit{counts.total_hits !== 1 ? 's' : ''} total
        </span>
      </div>
      <div className="flex gap-2 text-xs text-slate-500">
        {counts.critical_count > 0 && (
          <span className="text-red-700 font-semibold">{counts.critical_count} critical</span>
        )}
        {counts.high_count > 0 && (
          <span className="text-orange-700 font-semibold">{counts.high_count} high</span>
        )}
        {counts.medium_risk_count > 0 && (
          <span className="text-amber-700">{counts.medium_risk_count} medium</span>
        )}
        {counts.safe_count > 0 && (
          <span className="text-teal-700">{counts.safe_count} safe</span>
        )}
      </div>
    </div>
  );
}
```

#### 13.6.2 `HitsAccordion`

Hiển thị tối đa 5 hits; nếu nhiều hơn thì show "Show all N hits" link. Mỗi hit là 1 row có risk badge + gene name + mismatch count + 3′-terminal info:

```jsx
const MAX_HITS_DEFAULT = 5;

function HitsAccordion({ hits, expanded, onToggle }) {
  const shown = expanded ? hits : hits.slice(0, MAX_HITS_DEFAULT);

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-slate-100 border-b border-slate-200">
          <tr>
            <th className="text-left px-3 py-1.5 font-semibold text-slate-600">Target</th>
            <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Mismatch</th>
            <th className="text-center px-2 py-1.5 font-semibold text-slate-600">3′ mm</th>
            <th className="text-center px-2 py-1.5 font-semibold text-slate-600">3′ type</th>
            <th className="text-center px-2 py-1.5 font-semibold text-slate-600">Risk</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {shown.map((hit, i) => {
            const style = BLAST_RISK_STYLE[hit.risk] ?? BLAST_RISK_STYLE.SAFE;
            return (
              <tr key={i}>
                <td className="px-3 py-1.5 text-slate-700 font-mono truncate max-w-[160px]" title={hit.target_name}>
                  {hit.target_name}
                </td>
                <td className="px-2 py-1.5 text-center tabular-nums text-slate-600">
                  {hit.alignment?.mismatches ?? '—'}
                </td>
                <td className="px-2 py-1.5 text-center tabular-nums text-slate-600">
                  {hit.alignment?.mm_in_3prime_window ?? '—'}
                </td>
                <td className="px-2 py-1.5 text-center font-mono text-slate-500">
                  {hit.alignment?.terminal_category ?? '—'}
                </td>
                <td className="px-2 py-1.5 text-center">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${style}`}>
                    {hit.risk}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* ── Expand / collapse toggle ── */}
      {hits.length > MAX_HITS_DEFAULT && (
        <button
          type="button"
          onClick={onToggle}
          className="w-full text-center text-xs text-teal-700 hover:text-teal-800 py-1.5 border-t border-slate-200 bg-slate-50"
        >
          {expanded ? 'Show fewer hits ▲' : `Show all ${hits.length} hits ▼`}
        </button>
      )}
    </div>
  );
}
```

### 13.7 Integration vào `PrimerSetCard`

**Thay đổi tối thiểu** trong `PrimerSetCard.jsx` — chỉ thêm `<OffTargetPanel>` trước `<ExportButtons>`:

```jsx
// Thêm import ở đầu file:
import OffTargetPanel from './OffTargetPanel.jsx';

// Trong expanded panel, trước ExportButtons:
{/* ── Off-target check ── */}
<OffTargetPanel
  forwardPrimer={set.sequence}
  reversePrimer={reverse?.sequence}
  mirnaId={mirnaId}   // ← xem §13.7.1
/>

{/* ── Export ── */}
<ExportButtons set={set} stemloop={stemloop} reverse={reverse} />
```

#### 13.7.1 Truyền `mirnaId` xuống card

`PrimerSetCard` hiện không nhận `mirnaId`. Cần pass từ `ResultsSection`:

```jsx
// ResultsSection/index.jsx — thêm mirnaId vào destructure:
const { top3, stemloop_rt, universal_reverse, global_warnings = [], metadata, specificity_warnings } = results;
const mirnaId = metadata?.mirna_id ?? '';  // backend cần thêm field này vào metadata

// Và truyền xuống PrimerSetCard:
<PrimerSetCard key={i} set={set} stemloop={stemloop_rt} reverse={universal_reverse} mirnaId={mirnaId} />
```

**Backend change cần thiết:** `routes/design.py` thêm `"mirna_id"` vào `metadata` object trong response (hiện tại chưa có). Thêm 1 dòng:
```python
# trong format_output() hoặc cuối routes/design.py:
"metadata": {
    ...existing fields...,
    "mirna_id": mirna_name,   # ← ADD này
}
```

#### 13.7.2 `PrimerSetCard` props sau thay đổi

```jsx
// Prop types cập nhật:
export default function PrimerSetCard({ set, stemloop, reverse, mirnaId }) {
  // ...existing code...
}
```

Không cần thay đổi gì khác trong SearchPage/index.jsx — `mirnaId` flow tự nhiên qua results metadata.

### 13.8 Files cần tạo / sửa (v1.6)

| File | Loại | Mô tả |
|------|------|-------|
| `frontend/src/hooks/useBlastCheck.js` | NEW | Hook quản lý BLAST request lifecycle |
| `frontend/src/pages/SearchPage/ResultsSection/OffTargetPanel.jsx` | NEW | Panel component (button + result + error) |
| `frontend/src/pages/SearchPage/ResultsSection/PrimerSetCard.jsx` | EDIT | Thêm `<OffTargetPanel>` + `mirnaId` prop |
| `frontend/src/pages/SearchPage/ResultsSection/index.jsx` | EDIT | Pass `mirnaId` xuống PrimerSetCard |
| `backend/routes/design.py` | EDIT | Thêm `mirna_id` vào `metadata` response |

**Không cần:**
- Không cần Redux / global state — local state trong OffTargetPanel là đủ
- Không cần new route / API — `/api/blast-check` đã implement (§8, §10.2)
- Không cần thay đổi constants/defaults.js — không có user-configurable BLAST params

### 13.9 Edge cases cần handle

| Case | Behavior |
|------|----------|
| `reverse?.sequence` là undefined | Vẫn gọi API với `reverse_primer: null`; backend validate và trả 400 nếu cần |
| User bấm "Re-check" ngay sau lần đầu | Abort request cũ (AbortController), chạy lại |
| User collapse card (expanded = false) trong khi loading | State vẫn giữ; khi expand lại, spinner vẫn hiện — không cancel |
| `total_hits = 0` và `overall_risk = 'SAFE'` | Không render HitsAccordion; chỉ show OverallRiskRow với "0 hits" |
| `database_info.age_days > 90` | `outdated_warning = true` từ backend — show amber banner §13.6 |
| `result.cache.hit = true` | Footnote hiện "Cached result" thay "Fresh result" |
