# SPEC_phase6.md — HG Lab Stem-loop RT-qPCR Primer Designer
# Phase 6: TaqMan probe · Multiplex panel check · Validation finalization · Calibration (blocked → wet-lab protocol)
# Phiên bản 1.0 — 2026-07-03 · Sync: algorithm v3.0.0, SCORING_WEIGHTS_V4, SPEC_phase2 §K, SPEC_phase4 v1.1, SPEC_phase5 v1.0

---

## CHANGELOG

### v1.0 — 2026-07-03 — Phase 6 khởi tạo
- **PART A — TaqMan probe design:** module thiết kế probe dùng **hằng số Section K đã có sẵn** trong SPEC_phase2/constants.py (Tm gap, length single-Q/MGB, GC, 5′-no-G, G≤C, poly-G, junction position, custom/universal mode, structure checks).
- **PART B — Multiplex panel cross-dimer check:** kiểm cross-dimer giữa forward primer của nhiều assay chạy chung 1 tube.
- **PART C — Validation finalization:** sửa `check_tm.py` (per-oligo conditions + Ct/4 + loại nhánh RT hybrid), áp 7 accuracy fix + freeze phiên bản, benchmark in-silico vs miRprimer/miPrimer.
- **PART D — Calibration PART B (Phase 5):** **đánh dấu BLOCKED** — literature không cho dữ liệu efficiency hợp lệ (§D.1); spec hoá **giao thức wet-lab** làm future-work.
- **Quyết định (chốt với Vuong 2026-07-03):** Phase 6 gồm PART A+B+C; calibration = blocked + wet-lab protocol; deploy để phase sau.

---

## 0. Hướng dẫn cho Claude Code
1. **Đọc trước:** SPEC_phase2 **§K (K1–K8)** — toàn bộ hằng số probe đã định nghĩa; `backend/algorithm/constants.py` (các `PROBE_*` đã có); SPEC_phase4 §12, SPEC_phase5, `RESEARCH_INSIGHTS.md` (E.1 DNA:RNA hybrid, D.5 phân tầng mức tin), `PROMPTS_accuracy_fixes.md`, `calibration/`, `validation/`.
2. **Bất biến:** không thêm dependency (primer3-py, ViennaRNA đã đủ cho probe & dimer). Không đổi `SCORING_WEIGHTS_V4`. Probe/multiplex là **module bổ sung**, không đổi thuật toán primer lõi.
3. **Constants tập trung:** probe dùng `PROBE_*` sẵn có (§K). Hằng số multiplex mới đặt trong `constants.py` với `[NGUỒN]`.
4. **Output UI English.** Comment tiếng Việt được.
5. Mỗi module có unit test; feature bật/tắt qua constant để A/B.

---

## 1. Tổng quan Phase 6

### Bối cảnh định hình phase này
Calibration hồi quy (SPEC_phase5 PART B) **bị chặn bởi dữ liệu**: qua khảo sát Wang17/Kunwar23/Busk14 (§D.1), literature **không** cung cấp được dữ liệu efficiency hợp lệ để hiệu chỉnh trọng số (khác primer/hoá học + chỉ toàn ca thành công). Vì vậy Phase 6 xoay sang **những việc hoàn tất được ngay + paper cần**, và spec hoá con đường wet-lab cho calibration.

### Mục tiêu
- Mở rộng năng lực khoa học: **TaqMan probe** (đích của Phase 4 "không làm") + **multiplex panel**.
- **Đóng** validation Tm (Phase 5 PART C) + freeze phiên bản thuật toán cho paper.
- **Benchmark** đối đầu miRprimer/miPrimer — bảng lõi tool-paper.
- Trung thực hoá calibration: blocked + giao thức wet-lab.

### Thời gian mục tiêu
PART A ~2 ngày · PART B ~1 ngày · PART C ~1.5 ngày · PART D (spec only) ~0.5 ngày.

---

## 2. Nguồn tham chiếu (Phase 6)
- **[IDT-TQ]** IDT TaqMan probe design guidelines (đã dùng §K): probe Tm ≥ primer Tm +6–8 °C; GC 40–60%; no-G-at-5′; tránh 4×G; screen probe×primer heterodimer.
- **[RNA13]** Kramer et al. *RNA* 2013 — universal TaqMan probe cho stem-loop (mode "universal", §K5).
- **[Chen05]** Chen 2005 — junction probe (miRNA–stemloop).
- **[patent 10036062]** TaqMan rules — G≤C, 5′ distance from primer.
- Kế thừa: [Kang17] dimer −9 kcal/mol, [MIQE09], [Busk14], [Owczarzy04/08], [Sugimoto95] (E.1).

---

# PART A — TaqMan probe design

## A.1 Rationale
Tool hiện chỉ hỗ trợ SYBR. Với `detectionMethod.signalMethod = "taqman"`, cần thiết kế **probe** bám junction miRNA–stemloop (hoặc universal probe stemloop body [RNA13]). **Toàn bộ hằng số đã có ở §K** — chỉ cần module hiện thực.

## A.2 Module `backend/algorithm/probe_design.py`
```python
def design_probe(mature_seq: str, stemloop_seq: str, forward_primer: dict,
                 params: dict, mode: str = PROBE_MODE_DEFAULT) -> dict:
    """
    Thiết kế TaqMan probe cho stem-loop RT-qPCR.
    mode = "custom" (junction, đặc hiệu per-miRNA) | "universal" (stemloop body [RNA13]).
    Trả: { sequence, length, tm, gc_percent, position_1based, mode,
           quality: {...}, warnings: [...], passes_all: bool }
    KHÔNG side-effect. Dùng primer3 cho Tm/hairpin/dimer.
    """
```

## A.3 Thuật toán
1. **Vị trí (custom):** probe bắc cầu junction — overlap phía miRNA `PROBE_JUNCTION_OVERLAP_MIRNA_SIDE` (7 nt), phía stemloop `PROBE_JUNCTION_OVERLAP_STEMLOOP_SIDE` (4 nt) [§K5]. Junction ở position = `len(mature)` trên cDNA.
2. **Vị trí (universal [RNA13]):** probe bám hoàn toàn stemloop body → dùng chung mọi miRNA.
3. **Độ dài:** quét trong [`PROBE_MIN_LENGTH_SINGLE_Q`..`PROBE_MAX_LENGTH_SINGLE_Q`] (18–27) cho single-Q; hoặc MGB [13–20] nếu `probeType="mgb"` (cộng `PROBE_MGB_TM_BOOST`).
4. **Chọn ứng viên đạt Tm target** `PROBE_TM_OPT` (70 °C) và **Tm gap ≥ `PROBE_TM_MIN_ABOVE_PRIMER`** (6 °C) so với forward primer; ưu tiên gần 8 °C.
5. **5′-no-G rule:** nếu probe bắt đầu bằng G → dịch cửa sổ hoặc lấy strand đối (§K4 Rule 1). Nếu `count(G) > count(C)` → lấy reverse complement (Rule 2).

## A.4 Quality checks (dùng ngưỡng §K — KHÔNG chấm vào SCORING_WEIGHTS_V4)
| Check | Ngưỡng | Nguồn |
|---|---|---|
| Tm gap vs forward | ≥ 6 °C (ideal 8) | `PROBE_TM_MIN_ABOVE_PRIMER` [IDT-TQ] |
| Probe Tm | 66–74 °C | `PROBE_TM_MIN/MAX` |
| GC% | 40–60% | `PROBE_GC_MIN/MAX` |
| 5′ base ≠ G | bắt buộc | `PROBE_NO_G_AT_5PRIME` |
| count(G) ≤ count(C) | bắt buộc | `PROBE_G_NOT_EXCEED_C` |
| Poly-G liên tiếp | ≤ 3 | `PROBE_MAX_CONSECUTIVE_G` |
| Hairpin ΔG | > −3.0 | `PROBE_HAIRPIN_DG_MAX` |
| Self-dimer ΔG | > −6.0 | `PROBE_SELF_DIMER_DG_MAX` |
| Probe×forward, probe×reverse ΔG | > −6.0 | `PROBE_HETERO_DIMER_DG_MAX` [IDT-TQ] |
| Không overlap 3′ forward | ≥ 1 nt | `PROBE_MIN_DIST_FROM_PRIMER` |

Tm probe tính ở `PROBE_DV_CONC_DEFAULT` (1.5 mM Mg) + note "Actual Tm may differ if master-mix Mg²⁺ varies" (§K7).

## A.5 Tích hợp `/api/design`
- Khi `signalMethod == "taqman"`: thêm key `probe` vào response (per top set hoặc 1 universal). Khi SYBR: `probe: null` + note.
- KHÔNG chặn/đổi luồng SYBR hiện có.

## A.6 Frontend
- `ProbeCard.jsx` trong ResultsPage: sequence (tô phần miRNA-side vs stemloop-side khác màu), Tm + gap, GC, mode (custom/universal toggle), quality badges, warnings. Disclaimer "Probe Tm at {Mg} mM Mg²⁺". UI English.

## A.7 Unit tests `backend/tests/test_probe_design.py`
```
test_probe_tm_gap_enforced          # gap < 6°C → warning
test_probe_no_g_at_5prime           # probe bắt đầu G → sửa/warn
test_probe_g_not_exceed_c           # G>C → revcomp
test_probe_poly_g_flagged           # GGGG → warning
test_probe_junction_position        # custom: overlap đúng 7/4 nt
test_universal_mode_binds_stemloop  # universal: bám stemloop body [RNA13]
test_probe_heterodimer_vs_primers   # probe×forward/reverse ΔG check
```

## A.8 PROMPT CLAUDE CODE — PART A
```
Đọc SPEC_phase6 PART A, SPEC_phase2 §K (K1-K8), constants.py (mọi PROBE_*),
routes/design.py, algorithm/thermodynamics.py (Tm/hairpin/dimer helpers).

Nhiệm vụ:
1) Tạo backend/algorithm/probe_design.py: design_probe(...) theo §A.2-A.4, dùng HẰNG SỐ PROBE_* sẵn có
   (KHÔNG hardcode số mới; nếu thiếu hằng số nào thì thêm vào constants.py §K với [NGUỒN]).
   Hỗ trợ mode custom (junction 7/4) và universal (stemloop body [RNA13]); single-Q và MGB length.
2) Nhúng key "probe" vào /api/design khi signalMethod=="taqman" (SYBR → probe=null + note). Không đổi luồng SYBR.
3) Frontend ProbeCard.jsx (§A.6): render probe + quality badges + Tm disclaimer. UI English.
4) Test test_probe_design.py (§A.7) — đủ 7 case, pass.
Ràng buộc: không thêm dependency; không đổi SCORING_WEIGHTS_V4; probe là quality-checked, không nhét vào weighted-sum.
Chạy pytest tests/test_probe_design.py -q và validation/validate_primers.py (deterministic vẫn 100%) trước khi báo xong.
```

## A.9 Insight literature (PubMed) — tránh vị trí đa hình / isoMiR
**[Hoffman08]** Hoffman NG et al. *J Clin Microbiol.* 2008;46(8):2671–2680. PMID 18562587 · DOI [10.1128/JCM.00258-08](https://doi.org/10.1128/JCM.00258-08). So 7 bộ primer/probe TaqMan → **nguồn sai số lớn nhất = primer/probe nằm trên vị trí đa hình (subtype polymorphism)** gây mismatch → tín hiệu tụt/mất. Analog cho miRNA = **isoMiR / biến thể trình tự**.
- **Hành động (bổ sung §A.4):** probe (và forward primer) nên **tránh phủ vị trí biến thiên đã biết** — tái dùng dữ liệu **isoMiR Phase 3** (`known_5prime_isomir_mirnas.json`). Nếu probe/forward phủ base isoMiR-variable → thêm `warning` "probe covers a known isoMiR-variable position; signal may drop for variant isoforms".
- **Hàm ý MIQE:** dùng standard/reference thống nhất giảm biến thiên liên-assay → ghi rõ điều kiện trong export (đã làm §8 SPEC_phase4).

---

# PART B — Multiplex panel cross-dimer check

## B.1 Rationale
Khi chạy nhiều assay trong **cùng một tube** (multiplex, [Cao23]), forward primer của assay này có thể tạo **cross-dimer** với forward primer/probe của assay khác → nhiễu/giảm hiệu suất. Cần kiểm **pairwise** trước khi đặt panel.

## B.2 Module `backend/algorithm/multiplex_check.py`
```python
def check_multiplex_panel(primer_sets: list[dict], params: dict) -> dict:
    """
    primer_sets: list các set (mỗi set có forward sequence, optional probe, mirna_id).
    Kiểm pairwise cross-dimer giữa MỌI forward-forward, forward-probe, forward-universal_reverse.
    Trả: { pairs: [{a, b, type, dg, risk}], worst_risk, panel_ok, recommendations }
    """
```
- Universal reverse chung 1 (đã cố định) → chỉ cần check forward×forward, forward×probe, probe×probe.

## B.3 Endpoint `POST /api/multiplex-check`
```
body: { "primer_sets": [ {mirna_id, forward, probe?}, ... ] }   # 2..N assays
200 → { pairs[], worst_risk, panel_ok, recommendations }
400 → < 2 sets / thiếu forward
Rate-limit như /api/blast-check (reuse flask-limiter).
```

## B.4 Risk classification (tái dùng ngưỡng đã có)
| ΔG cross-dimer (full) | Risk | Nguồn |
|---|---|---|
| > −6 kcal/mol | SAFE | `HETERODIMER_LOW_RISK_DG` |
| −9 .. −6 | MEDIUM | giữa hai ngưỡng |
| < −9 kcal/mol | HIGH | `HETERODIMER_HIGH_RISK_DG` [IDT]/[Kang17] |
| 3′-end overlap ≥ 3 bp | promote → HIGH | `HETERODIMER_3PRIME_MIN_BP` (extension risk) |

`recommendations`: gợi ý tách assay HIGH-risk sang tube khác.

## B.5 Frontend
- `MultiplexPanel.jsx`: người dùng thêm nhiều miRNA/assay → bấm "Check panel" → ma trận NxN heatmap risk + list cặp HIGH + khuyến nghị. Không tự chạy; user bấm.

## B.6 Unit tests `backend/tests/test_multiplex_check.py`
```
test_two_safe_forwards_panel_ok
test_high_cross_dimer_flagged        # cặp forward ΔG < -9 → HIGH
test_3prime_overlap_promoted_high
test_single_set_returns_400
test_recommendation_splits_high_risk
```

## B.7 PROMPT CLAUDE CODE — PART B
```
Đọc SPEC_phase6 PART B, algorithm/structure_check/heterodimer.py (check_pair/dg), constants.py
(HETERODIMER_* thresholds), routes/blast_check.py (mẫu rate-limit + endpoint).

Nhiệm vụ:
1) Tạo algorithm/multiplex_check.py: check_multiplex_panel(primer_sets, params) — pairwise
   forward×forward, forward×probe, probe×probe (universal reverse cố định → 1 lần). Dùng heterodimer ΔG
   + ngưỡng §B.4. Trả pairs/worst_risk/panel_ok/recommendations.
2) routes/multiplex_check.py: POST /api/multiplex-check (§B.3) + rate-limit reuse.
3) Frontend MultiplexPanel.jsx: NxN risk heatmap + cặp HIGH + khuyến nghị tách tube. UI English, user bấm chạy.
4) Test test_multiplex_check.py (§B.6) pass.
Ràng buộc: reuse heterodimer engine sẵn có; không thêm dependency; English output.
```

## B.8 Insight literature (PubMed) — workflow multiplex miRNA thực tế
Hai protocol chuẩn cho panel miRNA tuần hoàn:
- **[Bell17]** Bell E et al. *Methods Mol Biol.* 2017;1580:265–279. PMID 28439839 · DOI [10.1007/978-1-4939-6866-4_18](https://doi.org/10.1007/978-1-4939-6866-4_18) — panel **tới ~20 miRNA** bằng cách **multiplex các stem-loop RT primer ở bước RT** + **pre-amplification multiplex** → rồi **qPCR singleplex**.
- **[Murray21]** Murray MJ et al. *Methods Mol Biol.* 2021;2195:225–243. PMID 32852767 · DOI [10.1007/978-1-0716-0860-9_15](https://doi.org/10.1007/978-1-0716-0860-9_15) — panel 4-miRNA GCT: multiplex RT (TaqMan stem-loop) + multiplex preamp → singleplex.

**Hàm ý cho §B (quan trọng — thực tế multiplex ở đâu):**
1. Multiplex miRNA stem-loop **không phải multiplex ở qPCR cuối** mà ở **RT + pre-amplification** → điểm nghẽn cross-interaction là **pool RT primer + pool forward primer ở preamp**. Check của ta (forward×forward) đúng cho bước preamp; **bổ sung tuỳ chọn check ở bước RT**.
2. **Stem-loop RT primer chia sẻ universal body (44 nt giống nhau)** — chỉ khác 6-nt overhang. Nên RT×RT cross-dimer bị chi phối bởi **body chung** (đồng nhất cho mọi assay, ≈ self-structure hairpin đã có chủ đích); phần biến thiên = 6-nt overhang. → Check `overhang × overhang` + `forward × forward` là đủ ý nghĩa; không cần so full 50-nt RT (nhiễu bởi body chung).
3. **Kích thước panel khuyến nghị ≤ ~20** [Bell17] → thêm constant `MULTIPLEX_PANEL_MAX = 20` (warning nếu vượt) + note "documented multiplex RT/preamp workflow, singleplex qPCR readout".
4. `MultiplexPanel.jsx` nên ghi rõ đây là check cho **multiplex RT/preamp**, không phải multiplex qPCR — tránh người dùng hiểu nhầm.

*(Thông tin tài liệu trích từ PubMed.)*

---

# PART C — Validation finalization (đóng Phase 5 PART C + freeze)

## C.1 Sửa `check_tm.py` — per-oligo conditions + Ct/4 + loại RT hybrid
- `predict_tm(seq, cond)` đọc **điều kiện từng oligo** từ `tm_benchmark.json` (`salt_na_mm`, `salt_mg_mm`, `primer_conc_nm`) thay vì hardcode default tool.
- Áp **Ct/4** cho duplex non-self-complementary (Ct=2 µM → dna_conc hiệu dụng 0.5 µM) — xác nhận convention primer3.
- Chạy MAE/bias trên **34 oligo Owczarzy** (18 Mg 1.5mM + 16 Na 69mM) + tuỳ chọn toàn dải muối (`tm_by_mg_mM`/`tm_by_na_mM`).
- **Chỉ validate nhánh DNA:DNA** (forward/reverse). **KHÔNG** dùng bộ này để tuyên bố độ chính xác Tm của **RT primer** (DNA:RNA hybrid — RESEARCH_INSIGHTS E.1). Ghi rõ trong `tm_report.md`.
- Báo cáo phân tầng theo **độ dài & GC**; đặt cạnh sàn nhiễu σ≈0.3 °C (Owczarzy).

## C.2 Áp 7 accuracy fix + freeze
- Chạy `PROMPTS_accuracy_fixes.md` P1–P7 **từng cái**, mỗi lần: pytest + `validation/validate_primers.py` (deterministic **phải 100%**), ghi diff grade/score.
- Sau khi ổn: `git tag algo-frozen-v1.0` + lưu snapshot output (baseline cho paper & so sánh về sau).

## C.3 Benchmark in-silico vs miRprimer/miPrimer
- **Panel chung:** ≥50 miRNA đa dạng (GC 20–80%, length 18–25, gồm vài họ let-7/miR-200).
- **miRprimer** (Busk, open-source Ruby) — chạy được → so trực tiếp. **miPrimer** (Quark) — nếu không chạy được, so qua ví dụ đã công bố.
- **Metric (method-agnostic):** forward Tm, GC%, self/hetero-dimer ΔG, predicted specificity (BLAST/family), tỉ lệ "thiết kế thành công" (đạt ràng buộc), tốc độ.
- **Trung thực:** ghi rõ khác hoá học (Chen stem-loop vs hệ của họ) → so **đặc tính thiết kế**, không phải hiệu suất thực. Xuất `benchmark/compare_tools.md` + bảng.
- Harness: `benchmark/run_benchmark.py` (đọc panel, gọi `/api/design`, chạy miRprimer, gộp bảng).

## C.4 PROMPT CLAUDE CODE — PART C
```
1) Sửa calibration/check_tm.py: predict theo điều kiện từng oligo (salt_na/mg, Ct/4), chạy trên 34 oligo
   tm_benchmark.json; report MAE/bias phân tầng length/GC; loại RT primer khỏi claim (DNA:RNA, xem
   RESEARCH_INSIGHTS E.1); ghi tm_report.md. Sửa nhãn Owczarzy 2004(Na)/2008(Mg) cho đúng.
2) Áp P1–P7 trong PROMPTS_accuracy_fixes.md từng cái; sau mỗi cái chạy pytest + validation/ (deterministic 100%).
   Khi xong: đề xuất git tag algo-frozen-v1.0.
3) benchmark/run_benchmark.py + benchmark/panel.json (>=50 miRNA): gọi /api/design + miRprimer, xuất
   benchmark/compare_tools.md (Tm/GC/dimer/specificity/success/speed). Ghi rõ giới hạn so sánh khác hoá học.
Ràng buộc: không đổi V4 weights; không bịa số; English output; deterministic checks giữ 100%.
```

---

# PART D — Calibration PART B: BLOCKED + giao thức wet-lab

## D.1 Vì sao blocked (kết luận từ khảo sát literature)
`calibrate_weights.py` cần: feature = 15 sub-score của primer **do tool thiết kế**; label = efficiency **của chính primer đó**. Literature không cấp được:
- **Wang17:** không có bảng efficiency per-assay (chỉ range 0.93–1.14).
- **Busk14:** Table 1 = tham số scoring; chỉ 1 ví dụ efficiency 96%.
- **Kunwar23 Table 2:** 24 miRNA có efficiency, NHƯNG (a) là assay **Qiagen-LNA/TaqMan** (khác primer/hoá học → **feature-label mismatch**), (b) **restricted range** (Qiagen SD 3.9pp, toàn 85–100%, không ca thất bại → **survivorship bias**). → tương quan sẽ là nhiễu.

**Kết luận:** không có bộ dữ liệu công bố nào cho calibration hợp lệ. `assays` fit-set giữ rỗng/blocked; Kunwar 24 (nếu nạp) để ở section reference, **verified=false, không fit**.

## D.2 Giao thức wet-lab cần (future-work — để mở lại calibration)
Yêu cầu để dữ liệu hợp lệ:
1. **Primer khớp tool:** đo efficiency trên **chính primer TOOL thiết kế** (không phải primer thương mại khác).
2. **Có phương sai + ca xấu:** cố ý gồm cả thiết kế tốt VÀ xấu (vd top-1 vs ứng viên điểm thấp, hoặc primer vi phạm 1 tiêu chí) → label phải trải rộng, **có cả primer kém/thất bại**.
3. **N ≥ 20–30** assay, đa dạng GC/length/họ.
4. **Chuẩn hoá:** cùng master-mix, cùng máy, standard curve ≥5 điểm, efficiency = 10^(−1/slope)−1, báo cả R².
5. **Ghi điều kiện** (Na/Mg/dNTP) để khớp mô hình Tm.

## D.3 Acceptance để mở lại calibration
Chỉ chạy `calibrate_weights.py` và tin kết quả khi: N ≥ 20 primer-của-tool có efficiency; label spread đủ (SD > ~5pp, có ca < 90%); LOOCV cải thiện so V4; giữ w_floor lõi (đã có trong script). Trước đó: chỉ báo cáo tương quan như **định hướng**, không đổi weights.

---

# PART E — Insight literature bổ sung (PubMed) → Advisor & multiplex

## E.1 Pre-amplification cho panel miRNA (bổ trợ PART B)
- **[Chen09]** Chen Y et al. *BMC Genomics.* 2009;10:407. PMID 19715577 · DOI [10.1186/1471-2164-10-407](https://doi.org/10.1186/1471-2164-10-407): pre-amplification cDNA miRNA **tăng độ nhạy + số miRNA phát hiện được**, và **giữ nguyên mức biểu hiện tương đối** (không bias hệ thống trong định lượng tương đối); chỉ **tăng phương sai ở miRNA thấp**.
- **[Tan15]** Tan GW et al. *Sci Rep.* 2015;5:9430. PMID 25800946 · DOI [10.1038/srep09430](https://doi.org/10.1038/srep09430): RT-qPCR high-throughput có bước preamp → nhạy/chính xác/lặp lại tốt **khi kiểm soát chặt**; **spike-in control giảm bias chiết tách**.
- **Hàm ý (§B):** preamp là bước chuẩn cho multiplex miRNA panel → `MultiplexPanel.jsx` note "pre-amplification recommended for low-abundance targets; relative quantification preserved [Chen09], watch added variance at low copy number". Không cần module mới — chỉ ghi chú advisory.

## E.2 Normalization — quy tắc Advisor mới (mở rộng KB SPEC_phase5 PART A)
Thêm vào `protocol_kb.json` (bump `kb_version`):
| ID | Điều kiện | Khuyến nghị | Nguồn |
|---|---|---|---|
| P7 | mọi assay định lượng tương đối | "Validate reference/normalizer với geNorm/NormFinder; panel lớn/miRNome → dùng **global-mean normalization**." | [Hellemans14] DOI [10.1007/978-1-4939-0733-5_3](https://doi.org/10.1007/978-1-4939-0733-5_3) |
| P8 | sample = huyết tương/huyết thanh/biofluid (circulating) | "Dùng **spike-in ngoại sinh** (vd cel-miR-39) để chuẩn hoá bias chiết tách; lưu ý miRNA huyết tương > huyết thanh cùng cohort." | [Tan15] DOI [10.1038/srep09430](https://doi.org/10.1038/srep09430) |

- **Hàm ý:** đây là **advisory** (mô tả, có DOI, disclaimer) — KHÔNG đổi scoring/thuật toán. Nối với `cel-miR-39-3p` đã có trong `reference_mirnas.json` (spike-in control).

*(Thông tin tài liệu trích từ PubMed.)*

---

## Định nghĩa "Phase 6 hoàn thành"

**PART A — Probe:**
- [ ] `probe_design.py` dùng đúng hằng số §K; custom + universal mode; single-Q + MGB
- [ ] `/api/design` trả `probe` khi taqman; `ProbeCard.jsx`; 7 test pass
- [ ] Mọi quality check §A.4 hoạt động; không đụng SCORING_WEIGHTS_V4

**PART B — Multiplex:**
- [ ] `multiplex_check.py` pairwise cross-dimer; `/api/multiplex-check` + rate-limit
- [ ] Risk theo ngưỡng §B.4; `MultiplexPanel.jsx` heatmap; 5 test pass

**PART C — Validation finalization:**
- [ ] `check_tm.py` per-oligo + Ct/4; MAE/bias phân tầng; loại RT hybrid; `tm_report.md`
- [ ] P1–P7 áp xong, deterministic validation 100%; `git tag algo-frozen-v1.0`
- [ ] `benchmark/compare_tools.md` vs miRprimer (+miPrimer nếu được), ghi rõ giới hạn

**PART D — Calibration:**
- [ ] PART B (Phase 5) đánh dấu BLOCKED trong SPEC_phase5 + lý do (§D.1)
- [ ] Giao thức wet-lab (§D.2) + acceptance (§D.3) đã spec; Kunwar 24 chỉ ở reference (không fit)

**Không làm trong Phase 6:**
- Deploy web-server (phase sau — nhưng chuẩn bị hosting bền song song)
- Chạy calibration thật (chờ wet-lab)
- AI chatbot (phase riêng)
- DNA:RNA hybrid Tm cho RT primer (cần NUPACK/RNAstructure — dependency mới, để sau; hiện chỉ documented E.1)

---

*Hết SPEC_phase6.md v1.0 — sync SPEC_phase2 §K / phase4 v1.1 / phase5 v1.0. Thông tin tài liệu trích từ PubMed.*
