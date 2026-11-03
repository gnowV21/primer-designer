# SPEC_phase4.md — HG Lab Stem-loop RT-qPCR Primer Designer
# Phase 4: Results page hoàn thiện · Quality checks · Export PDF/CSV · Edge-case handling
# Phiên bản 1.1 — 2026-07-02 · Sync với SPEC_phase3 (algorithm v3.0.0, scoring V4 15 tiêu chí) & SPEC_week1 v3.2

---

## CHANGELOG

### v1.1 — 2026-07-02 — Kiểm chứng tài liệu PubMed
- Đã kéo abstract thật từ PubMed để chốt ngưỡng (trước đó dựa kiến thức nền). Bổ sung [NGUỒN] + DOI:
  - [Fan19] cho ngưỡng amplicon secondary structure (§12.2): "phân tích ≥60 bp quanh vùng bắt primer" — ngưỡng định lượng cụ thể.
  - [MIQE09], [Cao23], [Wang17] xác thực PMID + DOI (§2).
- Cập nhật §12.2 (nâng ưu tiên amplicon fold, có bằng chứng định lượng) và §2.

### v1.0 — 2026-07-02 — Phase 4 khởi tạo
- Đóng 5 hạng mục Roadmap "Week 3 — Results page & quality checks":
  1. ResultsPage hiển thị 3 primer (§4)
  2. Bảng thông số nhiệt động chi tiết — dạng tabs (§5)
  3. Quality warnings thống nhất taxonomy: dimer, hairpin, off-target (§6)
  4. Export PDF / CSV — kiến trúc **backend** (§8)
  5. Edge-case handling: miRNA ngắn, GC cực đoan (§7)
- Thêm section **Recommendations** (§12): đề xuất tối ưu thuật toán, KHÔNG bắt buộc, chờ Vuong duyệt trước khi làm Phase sau.
- **Quyết định kiến trúc (chốt với Vuong 2026-07-02):**
  - Export: **backend sinh file** (reportlab PDF + module `csv`) — endpoint mới `POST /api/export`.
  - Bảng nhiệt động: **cả hai qua tabs** — Tab A so sánh 3 set, Tab B chi tiết từng primer.
  - Phạm vi: đúng 5 mục ảnh + Recommendations tách riêng (§12).
  - Tài liệu: ngưỡng edge-case chốt bằng chứng, gắn [NGUỒN].

---

## 0. Hướng dẫn cho Claude Code

1. **Đọc trước khi code:** `SPEC_week1.md` (§2b tooling, §6 defaults, §19 backend flow), `SPEC_phase2.md` (§4 constants, scoring), `SPEC_phase3.md` (§7 SCORING_WEIGHTS_V4, §8 BLAST, §13 frontend off-target). Phase 4 **không** đổi thuật toán lõi — chỉ trình bày kết quả, cảnh báo, export, edge-case.
2. **Nguyên tắc bất biến:** giữ nguyên stack (SPEC_week1 §2). Frontend: React 18 + Vite 5 + Tailwind 3 + React Router v6 + Axios — **không thêm** thư viện UI. Backend: chỉ thêm dependency export ở §3, không đụng `primer3-py`/ViennaRNA/BLAST.
3. **Nguồn dữ liệu bảng nhiệt động là dữ liệu ĐÃ CÓ** trong response `/api/design` (§5.3). Tuyệt đối không tính lại thermodynamics ở frontend — chỉ đọc và hiển thị.
4. **Output UI 100% English** (đồng bộ Week 1 §10–13). Comment code có thể tiếng Việt.
5. **Constants tập trung:** ngưỡng edge-case mới đặt trong `backend/algorithm/constants.py`, mỗi hằng số có comment `[NGUỒN]`. Frontend đọc ngưỡng hiển thị từ response, không hardcode.
6. **Test:** mỗi module backend mới có unit test (pytest); ResultsPage + export có E2E (Playwright, thư mục `e2e/`).
7. **Superpower MCP** (SPEC_week1 §2b): chạy security check trước commit (endpoint `/api/export` nhận input → kiểm injection/path traversal); dùng skill `hrm-algorithm-validator` không áp dụng ở đây (Phase 4 không có thuật toán melting).

---

## 1. Tổng quan Phase 4

### Mục tiêu
Biến output thô của `/api/design` (đã đầy đủ số liệu từ Phase 2/3) thành **trang kết quả hoàn chỉnh, xuất bản được**: dễ so sánh 3 bộ primer, cảnh báo chất lượng rõ ràng, xuất file PDF/CSV để đặt tổng hợp oligo, và xử lý êm các ca biên.

### Hiện trạng — Gap analysis (QUAN TRỌNG)
Phần lớn "Results page" đã tồn tại từ Phase 2/3. Phase 4 là **hoàn thiện + lấp lỗ hổng**, KHÔNG làm lại từ đầu:

| Hạng mục Roadmap | Hiện trạng | Việc Phase 4 |
|---|---|---|
| ResultsPage hiển thị 3 primer | ✅ Có `ResultsSection/` (PrimerSetCard, ScoreGauge, RejectionLog…) nhưng là **section nhúng** trong SearchPage, chưa có route riêng | Tách route `/results` + refactor tối thiểu (§4) |
| Bảng thông số nhiệt động | ⚠️ Số liệu rải rác trong card, **chưa có bảng so sánh ma trận** | Thêm component `ThermoTable` dạng tabs (§5) |
| Quality warnings (dimer, hairpin, off-target) | ✅ Có `global_warnings`, `StructureChecks`, `OffTargetPanel` nhưng **taxonomy severity không thống nhất**, off-target async chưa gom vào 1 chỗ | Chuẩn hóa `QualitySummary` (§6) |
| Export PDF / CSV | ❌ `ExportButtons` chỉ **copy clipboard** TSV/FASTA — chưa tải file thật | Làm mới hoàn toàn: backend `/api/export` (§8) |
| Edge-case (miRNA ngắn, GC cực đoan) | ⚠️ Vài `global_warnings` rời rạc, **chưa có bộ quy tắc hệ thống** | Module `edge_cases.py` + ngưỡng có nguồn (§7) |

### Flow tổng quát
```
SearchPage (form)                         Phase 4 thêm/hoàn thiện
   │ POST /api/design (đã có, Phase 2/3)
   ▼
results object ──────────────► [§7] edge_cases (backend, trong /api/design response)
   │ (lưu state / navigate)
   ▼
ResultsPage  /results  [§4]
   ├── QualitySummary        [§6]  (gom global_warnings + structure + off-target async)
   ├── PrimerSetCard ×3      (đã có; giữ)
   ├── ThermoTable (tabs)    [§5]  Tab A so sánh · Tab B chi tiết
   ├── EdgeCaseBanner        [§7.4]
   └── ExportBar             [§8.6] → POST /api/export → tải primer_report.pdf / primers.csv
```

### Thời gian mục tiêu
- ResultsPage route + refactor: 0.5 ngày
- ThermoTable (tabs): 0.5 ngày
- QualitySummary taxonomy: 0.5 ngày
- Edge-case module + test: 1 ngày
- Export backend + frontend + test: 1.5 ngày
- E2E + polish: 0.5 ngày
- **Tổng: ~4.5 ngày** (chưa gồm §12 Recommendations)

---

## 2. Nguồn tham chiếu các thông số (thêm mới Phase 4)

Ký hiệu nối tiếp Phase 2/3. Nguồn mới **đã kiểm chứng trên PubMed** (v1.1) — kèm PMID + DOI:

- **[MIQE09]** Bustin SA et al. "The MIQE guidelines: minimum information for publication of quantitative real-time PCR experiments." *Clin Chem.* 2009;55(4):611–622. PMID 19246619 · DOI [10.1373/clinchem.2008.112797](https://doi.org/10.1373/clinchem.2008.112797). → checklist thông số tối thiểu cần công bố (full disclosure reagents/sequences/analysis) → nền cho nội dung CSV/PDF §8.
- **[Fan19]** Fan H, Wang J, Komiyama M, Liang X. "Effects of secondary structures of DNA templates on the quantification of qPCR." *J Biomol Struct Dyn.* 2019;37(11):2867–2874. PMID 30101656 · DOI [10.1080/07391102.2018.1498804](https://doi.org/10.1080/07391102.2018.1498804). → **bằng chứng định lượng:** hairpin gần vùng bắt primer ức chế khuếch đại (mạnh nhất khi nằm *trong* amplicon; stem 20-bp → mất hẳn sản phẩm); khuyến nghị **phân tích ≥60 bp quanh mỗi vùng bắt primer**. Nền cho §12.2.
- **[Cao23]** Cao Y et al. "Stem-loop RT-qPCR system for multiplex miRNA profiling…" *Anal Biochem.* 2023;678:115267. PMID 37516424 · DOI [10.1016/j.ab.2023.115267](https://doi.org/10.1016/j.ab.2023.115267). → chiến lược thiết kế & sàng lọc stem-loop RT primer, xác nhận cách tiếp cận Phase 2.
- **[Wang17]** Wang Y et al. "Quantification of distinct let-7 microRNA family members by a modified stem-loop RT-qPCR." *Mol Med Rep.* 2017;17(3):3690–3696. PMID 29257343 · DOI [10.3892/mmr.2017.8297](https://doi.org/10.3892/mmr.2017.8297). → stem-loop phân biệt được miRNA khác **1 nucleotide**; với các let-7 chia sẻ **16 nt giống nhau ở đầu 5′** cần RT primer riêng — hậu thuẫn family discrimination Phase 3 & vùng specific forward.
- **[IDT]** IDT OligoAnalyzer / Design Guidelines → GC primer tối ưu 40–60%, độ dài 18–30 nt, tránh run ≥4 G. (đã dùng Phase 2)
- **[Chen05]** Chen C et al. *Nucleic Acids Res.* 2005;33(20):e179 — stem-loop RT-qPCR gốc; mature miRNA ~22 nt, overhang 6 nt. (đã dùng Phase 1/2)
- **[R2]** (tài liệu nội bộ lab Phase 2 §2.1.2) — forward specific region = 10–12 nt đầu từ 5′ mature.
- **[Var07]** Varkonyi-Gasic E et al. *Plant Methods.* 2007;3:12 — protocol stem-loop; xác nhận overhang 6 nt tối ưu.
- **[SL98]/[SL04]** SantaLucia 1998 / SantaLucia & Hicks 2004 — nearest-neighbor Tm & bound fraction (đã dùng Phase 2/3).

> *Nguồn từ PubMed (v1.1). Ghi chú verify:* ngưỡng edge-case §7.2 gắn nguồn ở từng dòng. Ngưỡng đánh dấu `[convention]` là **quy ước kỹ thuật** (chưa có bằng chứng định lượng trực tiếp) — Vuong review/thay bằng số liệu lab nếu có.

---

## 3. Thư viện và cài đặt (thêm cho export)

### requirements.txt — thêm mới Phase 4
```
# Phase 1+2+3 giữ nguyên (flask, flask-cors, primer3-py, ViennaRNA, biopython, numpy, flask-limiter…)

# Phase 4 — export
reportlab>=4.0        # sinh PDF thuần Python, không cần binary hệ thống
# csv  → dùng module chuẩn thư viện Python, KHÔNG cần cài
```

**Lý do chọn `reportlab` (không WeasyPrint):** WeasyPrint kéo theo Pango/Cairo/GDK-Pixbuf (binary hệ thống nặng, hay lỗi trên Railway/Render free tier). `reportlab` là pure-Python wheel, deploy nhẹ, đủ sức layout bảng + màu thương hiệu. Đánh đổi: viết layout bằng API thay vì HTML/CSS — chấp nhận được cho 1 template report cố định.

**Không thêm dependency frontend.** Nút export chỉ gọi API rồi trigger download bằng `Blob` + `URL.createObjectURL` (API trình duyệt gốc).

---

## 4. Module: ResultsPage — route độc lập + refactor

### 4.1 Rationale
Roadmap ghi "**ResultsPage**". Hiện `ResultsSection` render inline dưới form → cuộn dài, khó chia sẻ link, khó in. Tách thành page riêng cho phép: URL riêng, layout in-friendly, back về form giữ nguyên input.

### 4.2 Route + state handoff
- Thêm route trong `App.jsx`: `<Route path="/results" element={<ResultsPage/>} />`.
- **State handoff:** dùng React Router `useNavigate('/results', { state: { results, params } })` sau khi `/api/design` trả về thành công tại `SearchPage/index.jsx`. `ResultsPage` đọc qua `useLocation().state`.
- **Fallback:** nếu vào `/results` trực tiếp mà `state == null` → hiển thị empty-state "No results yet" + nút "Go to designer" (`navigate('/')`). Không tự gọi API.
- **Không dùng** localStorage/sessionStorage (ràng buộc artifact & Week 1 giữ state ở component).

### 4.3 Cấu trúc component (tái dùng tối đa)
```
pages/
├── SearchPage/…                 (giữ nguyên; chỉ đổi: sau design → navigate('/results'))
└── ResultsPage/
    ├── index.jsx                (layout page + đọc location.state + empty-state)
    ├── QualitySummary.jsx       [§6] MỚI
    ├── ThermoTable.jsx          [§5] MỚI
    ├── EdgeCaseBanner.jsx       [§7.4] MỚI
    └── ExportBar.jsx            [§8.6] MỚI (thay ExportButtons cũ)
```
- **Tái dùng nguyên trạng** từ `SearchPage/ResultsSection/`: `PrimerSetCard`, `ScoreGauge`, `ScoreBreakdown`, `StructureChecks`, `OffTargetPanel`, `RejectionLog`, `OverhangComparison`. Di chuyển hoặc import chéo — ưu tiên **di chuyển** `ResultsSection/` → dùng chung, tránh trùng lặp.
- `ExportButtons.jsx` cũ (chỉ copy clipboard) → giữ chức năng "Copy FASTA/TSV" như tiện ích phụ bên trong card, nhưng nút tải file chính chuyển sang `ExportBar` (§8.6).

---

## 5. Module: Bảng thông số nhiệt động — `ThermoTable.jsx` (tabs)

### 5.1 Tab A — So sánh 3 set (mặc định)
Bảng ma trận **hàng = tiêu chí, cột = 3 set** (Rank 1/2/3). Giúp mắt quét dọc để chọn. Ô "tốt nhất theo tiêu chí" tô nền `teal-50`.

| Tiêu chí (hàng) | Nguồn cột | Định dạng |
|---|---|---|
| Total score | `set.total_score` | số 1 chữ số thập phân + grade badge (`set.grade`) |
| Forward Tm (full) | `set.tm_full` | °C, 1 thập phân |
| Forward Tm (binding only) | `set.tm_binding` nếu có | °C |
| GC% (forward) | `set.gc_percent` | % |
| Amplicon size | `set.amplicon_size` | bp |
| Hairpin ΔG | `set.structure_checks.hairpin.dg` | kcal/mol |
| Self-dimer ΔG | `set.structure_checks.self_dimer.dg` | kcal/mol |
| Hetero-dimer (fwd×rev) ΔG | `set.heterodimer_checks.fwd_reverse.dg` | kcal/mol |
| Hetero-dimer (fwd×RT) ΔG | `set.heterodimer_checks.fwd_stemloop.dg` | kcal/mol |
| 3′ end stability ΔG | `set.structure_checks.end_stability.stability_kcal_mol` | kcal/mol |
| Bound fraction (binding) | `set.scores.bound_fraction_binding` nếu expose | % hoặc điểm |
| GC clamp | `set.scores.gc_clamp` | ✓/✗ hoặc điểm |
| isoMiR flag | `set.isomir_flag.status` | badge |

> Chỉ hiển thị hàng nếu key tồn tại (một số key optional). Không tính toán — chỉ format.

### 5.2 Tab B — Chi tiết từng primer (của set đang chọn)
Selector chọn set (Rank 1/2/3) → hiển thị 3 khối primer:
- **Stem-loop RT primer** (`stemloop_rt`): sequence (phân đoạn màu: universal body / 6-nt overhang), MFE hairpin, length.
- **Forward primer** (`set`): sequence (5′ tail vs specific region tô khác màu — tái dùng logic `OverhangComparison`), Tm full/binding, GC%, GC clamp, hairpin/self-dimer ΔG, 3′ stability, binding_start/end (1-based).
- **Universal reverse** (`universal_reverse`): sequence cố định, Tm, self-check ΔG, stemloop×reverse heterodimer ΔG.

Định hướng: Tab B phục vụ **đặt tổng hợp oligo** — mỗi khối có nút copy sequence riêng.

### 5.3 Data mapping
Tất cả từ response `/api/design` (SPEC_phase3 §10.1 shape — xác nhận trong `routes/design.py`):
```
results.top3[i]              → set (đã có: sequence, tm_full, gc_percent, amplicon_size,
                                total_score, grade, structure_checks, heterodimer_checks,
                                isomir_flag, scores, rank, specific_region, specific_length,
                                binding_start_1based, binding_end_1based, explanations)
results.stemloop_rt          → RT primer block
results.universal_reverse    → reverse block (+ stemloop_reverse_heterodimer)
results.metadata             → header (mirna_id, mirna_length, algorithm_version, elapsed_seconds)
```
**Không thêm field backend cho §5** — dữ liệu đã đủ. Nếu `tm_binding`/`bound_fraction_*` chưa expose ra top-level, thêm vào dict trả về của `score_candidate` (đổi tối thiểu, ghi rõ ở §8.5 API summary).

---

## 6. Module: Quality Summary — `QualitySummary.jsx`

### 6.1 Severity taxonomy (THỐNG NHẤT — 3 mức)
Chuẩn hóa mọi cảnh báo về 3 mức, màu đồng bộ toàn app (khớp `RISK_STYLE` Phase 3):

| Mức | Màu | Ý nghĩa | Ví dụ |
|---|---|---|---|
| `critical` | red-50/red-800 | Có thể làm hỏng thí nghiệm — nên đổi thiết kế | reverse hairpin/self-dimer critical; miRNA quá ngắn (§7); IDENTICAL cross-reactivity |
| `warning` | amber-50/amber-800 | Rủi ro đáng lưu ý — cân nhắc | HIGH cross-reactivity; GC cực đoan; hetero-dimer ΔG vượt ngưỡng |
| `info` | teal-50/teal-800 | Ghi chú/khuyến nghị — không chặn | isoMiR informational; off-target chưa chạy |

### 6.2 Nguồn cảnh báo (gom về 1 panel)
`QualitySummary` gom từ:
1. `results.global_warnings[]` (đã có `severity`, `message`) — map `severity` cũ: `critical`→critical, `warning`→warning.
2. **Per-set structure/dimer** (`structure_checks`, `heterodimer_checks`): tổng hợp cờ `has_critical_flag`/`any_high_risk` thành badge cạnh mỗi rank ("Rank 1 · 1 warning").
3. `edge_cases[]` từ §7 (mới).
4. **Off-target** (async, §6.3).

Hiển thị: 1 header "Quality summary — N issues (X critical, Y warnings)" + list gom nhóm. Nếu 0 issue → dải teal "All checks passed ✓".

### 6.3 Off-target async state
`/api/blast-check` là async có chủ đích (Phase 3 §13). Trong QualitySummary:
- Chưa chạy → dòng `info`: "Off-target (BLAST) not run yet — [Run check]" (bấm gọi `useBlastCheck.run()`).
- Đang chạy → spinner "Running BLAST…".
- Xong → merge kết quả `OffTargetPanel` risk vào taxonomy (CRITICAL/HIGH→critical/warning).
- Lỗi (429/503/timeout) → dòng `warning` với message tương ứng (tái dùng error handling Phase 3 §13).

---

## 7. Module: Edge-case handling — `backend/algorithm/edge_cases.py`

### 7.1 Rationale
Người dùng nhập miRNA bất thường (quá ngắn, GC cực đoan, homopolymer, low-complexity) → thuật toán vẫn chạy nhưng kết quả kém tin cậy. Cần **phát hiện có hệ thống + thông điệp hành động**, thay vì cảnh báo rời rạc. Chạy trong `/api/design` (đồng bộ, rất nhẹ — chỉ đếm/so ngưỡng, không thermodynamics).

### 7.2 Bảng edge-case rules (ngưỡng + [NGUỒN])
Đặt hằng số trong `constants.py` (SECTION mới `EDGE_CASE_THRESHOLDS`):

| # | Điều kiện | Ngưỡng | Mức | Message (English) | Nguồn |
|---|---|---|---|---|---|
| E1 | miRNA rất ngắn | `len < 18 nt` | critical | "miRNA length {n} nt is unusually short; the 6-nt overhang + specific region may be unreliable." | mature miRNA canonical ~22 nt [Chen05]; forward specific = 10–12 nt từ 5′ [R2] → cần ≥ ~16–18 nt |
| E2 | miRNA ngắn (biên) | `18 ≤ len < 20` | warning | "Short miRNA ({n} nt) — consider verifying forward primer Tm." | như E1 [convention] |
| E3 | miRNA dài bất thường | `len > 26 nt` | info | "miRNA longer than typical mature length (~22 nt); verify this is a mature sequence, not a pre-miRNA." | [Chen05] |
| E4 | GC rất thấp | `mirna_gc < 30%` | warning | "Low miRNA GC ({gc}%) → low primer Tm; a longer 5′ tail may be needed." | primer GC tối ưu 40–60% [IDT][MIQE09] |
| E5 | GC rất cao | `mirna_gc > 70%` | warning | "High miRNA GC ({gc}%) → strong secondary structure / melting difficulty." | [IDT] |
| E6 | Homopolymer run | `≥ 5 nt lặp cùng base` (poly-G ≥4) | warning | "Homopolymer run detected (…); may cause polymerase slippage / mispriming." | run ≥4 G tránh [IDT]; G-quadruplex signal (khớp `gc_skew` scoring) |
| E7 | Low complexity | `≥ 60% chỉ 2 loại base` HOẶC dinucleotide repeat ≥ 5 lần | info | "Low sequence complexity — specificity may be reduced." | [convention] |
| E8 | Ký tự lạ | có base ngoài A/C/G/U(T) (vd N) | critical | "Ambiguous/invalid base detected ({chars}); cannot design reliably." | validation [convention] |

> `mirna_gc` tính trên mature sequence (`results.metadata.mirna_sequence`). Ngưỡng E1/E4/E5 dựa nguồn; E2/E7/E8 là quy ước — Vuong xác nhận. Có thể tinh chỉnh sau khi có dữ liệu thực.

### 7.3 Return shape (thêm key `edge_cases` vào `/api/design`)
```python
# routes/design.py — sau bước build metadata, trước jsonify:
edge_cases = detect_edge_cases(seq)   # from algorithm.edge_cases
# thêm vào response:
"edge_cases": edge_cases,   # list[dict]: {code, severity, message, value}
# đồng thời: các edge_case severity=critical được promote vào global_warnings
```
`detect_edge_cases(seq: str) -> list[dict]`:
```python
[{"code": "E1", "severity": "critical", "message": "...", "value": 17}, ...]
```

### 7.4 Frontend — `EdgeCaseBanner.jsx`
- Đặt trên cùng ResultsPage nếu có edge_case severity `critical`/`warning`.
- Dùng cùng màu taxonomy §6.1. Mỗi dòng: icon + message + (nếu có) gợi ý hành động (E4 → "increase 5′ tail length in the form").
- `info`-level gộp vào QualitySummary, không banner riêng.

### 7.5 Unit tests — `backend/tests/test_edge_cases.py`
```
test_short_mirna_critical         # len 17 → E1 critical
test_borderline_short_warning     # len 19 → E2 warning
test_long_mirna_info              # len 28 → E3 info
test_low_gc_warning               # GC 25% → E4
test_high_gc_warning              # GC 75% → E5
test_homopolymer_run              # "...GGGGG..." → E6
test_ambiguous_base_critical      # chứa "N" → E8
test_normal_mirna_no_edge_cases   # hsa-miR-21-5p (22 nt, GC ~48%) → []
```

---

## 8. Module: Export PDF / CSV — backend `POST /api/export`

### 8.1 Kiến trúc (backend — chốt với Vuong)
Frontend gửi object `results` (đã có sẵn client) + `format` → backend render file → trả `application/pdf` hoặc `text/csv` với `Content-Disposition: attachment`. Không lưu file server (stream in-memory `io.BytesIO`/`io.StringIO`).

### 8.2 Thư viện: `reportlab` (PDF) + `csv` chuẩn (§3).

### 8.3 CSV format (MIQE-aligned [MIQE09])
Một hàng/primer-role, đủ thông tin đặt oligo + báo cáo:
```
csv columns:
Set_Rank, Primer_Role, Sequence, Length, Tm_C, GC_percent,
Hairpin_dG, SelfDimer_dG, Amplicon_bp, Total_Score, Grade, Notes
```
- Role: `Forward`, `RT_StemLoop`, `Universal_Reverse` (3 hàng × mỗi set forward; RT & reverse lặp lại hoặc ghi 1 lần ở block header — chốt: liệt kê đủ 3 role cho từng set để file tự chứa).
- Header comment dòng đầu: `# HG Lab Primer Designer — miRNA {id}, algorithm v{ver}, exported {date}`.
- Encoding UTF-8, xuống dòng `\r\n` (Excel-friendly).

### 8.4 PDF format (report 1–2 trang)
Layout `reportlab.platypus` (SimpleDocTemplate + Table + Paragraph):
1. **Header:** logo/tên "HG Lab — Stem-loop RT-qPCR Primer Report", miRNA id + sequence, ngày export, algorithm/scoring version.
2. **Recommended set (Rank 1):** 3 sequence (RT/Forward/Reverse) khổ lớn, monospace, kèm Tm/GC/amplicon.
3. **Comparison table:** rút gọn Tab A (§5.1) — 3 set × tiêu chí chính.
4. **Quality summary:** liệt kê issues theo taxonomy §6 (màu).
5. **Edge cases:** nếu có.
6. **Footer:** disclaimer "For research use only. Validate primers experimentally." + nguồn ([Chen05], [MIQE09]).
- Màu thương hiệu teal (Week 1 §4): `#0F6E56`, `#5DCAA5`.

### 8.5 Endpoint `POST /api/export`
```python
# routes/export.py  (blueprint mới, đăng ký trong app.py)
# POST /api/export
# body: { "format": "pdf" | "csv", "results": <object /api/design đã trả> }
# 200 → file stream (Content-Disposition: attachment; filename=...)
# 400 → format không hợp lệ / results thiếu field bắt buộc
# 413 → payload quá lớn (giới hạn ~256KB, results bình thường nhỏ hơn nhiều)
#
# BẢO MẬT (Superpower security check trước commit):
#  - validate format ∈ {pdf, csv}; whitelist, không eval
#  - filename cố định server-side (primer_report_<mirna_id_sanitized>.<ext>) — KHÔNG lấy từ client (chống path traversal)
#  - sanitize mirna_id: chỉ [A-Za-z0-9._-]
#  - không ghi file ra disk; render in-memory
#  - CORS giữ như app.py hiện tại (localhost:5173/3000)
```
**Thay đổi tối thiểu khác:** nếu §5 cần `tm_binding`/`bound_fraction_*` ở top-level set → bổ sung trong `score_candidate` return (đồng bộ, không đổi công thức).

### 8.6 Frontend — `ExportBar.jsx`
- 2 nút: "Download PDF", "Download CSV" (+ giữ "Copy FASTA/TSV" cũ như phụ).
- Gọi `axios.post('/api/export', { format, results }, { responseType: 'blob' })` → tạo `URL.createObjectURL(blob)` → `<a download>` click ảo → revoke URL.
- Trạng thái: idle / generating (spinner, disable) / error (toast inline). Không dùng thư viện toast — reuse pattern message có sẵn.
- filename từ header `Content-Disposition` nếu có, fallback `primers.csv`/`primer_report.pdf`.

### 8.7 Unit tests
Backend `backend/tests/test_export.py`:
```
test_export_csv_has_all_roles        # 3 role/set, header comment đúng
test_export_csv_content_type         # text/csv + attachment
test_export_pdf_returns_pdf_bytes    # bytes bắt đầu b"%PDF"
test_export_invalid_format_400
test_export_missing_results_400
test_export_filename_sanitized       # mirna_id "../../etc" → filename an toàn
```
E2E `e2e/export.spec.js`: chạy design → vào /results → bấm Download CSV → assert file tải về (Playwright `waitForEvent('download')`).

---

## 9. Kiến trúc & Constants

### 9.1 Constants mới (`backend/algorithm/constants.py`, SECTION mới)
```python
# ----------------------------------------------------------------
# SECTION F: EDGE-CASE THRESHOLDS (Phase 4)
# Nguồn: [Chen05] mature ~22nt, [IDT] GC 40-60%/run≥4G, [MIQE09] reporting
# ----------------------------------------------------------------
MIRNA_LEN_CRITICAL_SHORT = 18   # < → critical  [Chen05]+[R2]
MIRNA_LEN_WARN_SHORT     = 20   # < → warning   [convention]
MIRNA_LEN_INFO_LONG      = 26   # > → info      [Chen05]
MIRNA_GC_LOW             = 30.0 # % < → warning [IDT][MIQE09]
MIRNA_GC_HIGH            = 70.0 # % > → warning [IDT]
HOMOPOLYMER_RUN_MIN      = 5    # ≥ → warning (poly-G ≥4) [IDT]
POLY_G_RUN_MIN           = 4    # ≥ → warning (G-quadruplex) [IDT]
```

### 9.2 API summary sau Phase 4
| Endpoint | Đổi Phase 4 |
|---|---|
| `POST /api/design` | +key `edge_cases[]`; (optional) expose `tm_binding`, `bound_fraction_*` top-level |
| `POST /api/export` | **MỚI** — pdf/csv stream |
| `POST /api/blast-check` | không đổi (Phase 3) |
| `GET /api/mirbase/<id>` | không đổi (Week 1) |

---

## 10. Thứ tự implement
1. Backend `edge_cases.py` + constants SECTION F + test (§7) — độc lập, làm trước.
2. Tích hợp `edge_cases` vào `routes/design.py` + promote critical → global_warnings.
3. Backend `routes/export.py` (CSV trước, PDF sau) + test + đăng ký blueprint (§8).
4. Frontend: route `/results` + `ResultsPage/index.jsx` + state handoff + empty-state (§4).
5. Di chuyển/tái dùng `ResultsSection/` components sang ResultsPage.
6. `ThermoTable.jsx` tabs (§5) → `QualitySummary.jsx` (§6) → `EdgeCaseBanner.jsx` (§7.4).
7. `ExportBar.jsx` (§8.6) nối `/api/export`.
8. E2E `export.spec.js` + `results-page.spec.js`.
9. Superpower security check → commit.

---

## 11. Định nghĩa "Phase 4 hoàn thành"

**Results page (§4–6):**
- [ ] Route `/results` hoạt động; state handoff từ SearchPage; empty-state khi vào trực tiếp
- [ ] Tái dùng PrimerSetCard/ScoreGauge/OffTargetPanel… không trùng lặp code
- [ ] `ThermoTable` 2 tab: Tab A so sánh 3 set (highlight ô tốt nhất), Tab B chi tiết từng primer
- [ ] `QualitySummary` gom global_warnings + structure + edge_cases + off-target async, 3 mức taxonomy thống nhất màu
- [ ] Off-target chưa chạy hiển thị nút Run; loading/error xử lý đúng (reuse Phase 3)

**Edge-case (§7):**
- [ ] `edge_cases.py` với 8 rule E1–E8, ngưỡng đọc từ constants SECTION F (có [NGUỒN])
- [ ] `/api/design` trả `edge_cases[]`; critical promote sang global_warnings
- [ ] `EdgeCaseBanner` hiển thị đúng mức; test đủ 8 case + case bình thường (hsa-miR-21-5p → rỗng)

**Export (§8):**
- [ ] `POST /api/export` trả PDF (bytes `%PDF`) và CSV (text/csv) đúng Content-Disposition
- [ ] CSV đủ cột MIQE-aligned; PDF có recommended set + comparison + quality + footer disclaimer
- [ ] Filename sanitize server-side (không path traversal); format whitelist
- [ ] `ExportBar` tải file qua Blob; trạng thái generating/error
- [ ] Test backend export + E2E download pass

**Chung:**
- [ ] UI 100% English; màu theo Week 1 §4
- [ ] Không thêm dependency ngoài `reportlab`; frontend không thêm lib
- [ ] Superpower security check pass (endpoint export)
- [ ] Playwright suite cũ vẫn xanh

**Không làm trong Phase 4** (đẩy Phase sau):
- TaqMan probe design
- AI chatbot giải thích kết quả (Week 4+)
- Responsive mobile hoàn chỉnh (Week 4+)
- Deploy Render/Vercel (Week 4+)
- Các mục §12 (Recommendations) — chỉ làm sau khi Vuong duyệt

---

## 12. Recommendations — Tối ưu thuật toán (KHÔNG bắt buộc, chờ duyệt)

> Phần trả lời câu hỏi của Vuong: "cần điều chỉnh gì để thuật toán tốt hơn". Đây là đề xuất, tách khỏi phạm vi bắt buộc Phase 4. Mỗi mục có: vấn đề → đề xuất → effort → rủi ro.
>
> **→ Đã mở rộng thành `SPEC_phase5.md`:** Protocol/Evidence Advisor (PART A), **hồi quy hiệu chỉnh trọng số scoring** (PART B — trọng tâm, dùng dữ liệu paper), Tm accuracy (PART C), amplicon melting + LNA (PART D). Các mục §12.1–12.6 dưới đây vẫn hợp lệ; §12.2 (amplicon fold) và calibration là ưu tiên cao nhất.

### 12.1 Hard-filter gates trước scoring
**Vấn đề:** scoring hiện là weighted-sum 15 tiêu chí (SPEC_phase3 §7). Weighted-sum có thể cho điểm cao một set mắc 1 lỗi chí mạng (vd self-dimer ΔG rất âm) vì bù trừ bởi tiêu chí khác.
**Đề xuất:** thêm tầng **hard-filter** loại thẳng candidate vi phạm ngưỡng cứng (self-dimer ΔG < −9, 3′ hairpin che vùng priming) *trước* khi tính weighted-sum. Weighted-sum chỉ để xếp hạng các candidate đã "an toàn".
**Effort:** ~0.5 ngày (thêm gate trong `scoring.py`, giữ nguyên weights). **Rủi ro:** có thể giảm số candidate → cần fallback nới ngưỡng (giống thông báo 422 hiện có).

### 12.2 Fold vùng quanh primer-binding site (secondary structure) — ƯU TIÊN CAO (có bằng chứng)
**Vấn đề:** hiện chỉ kiểm hairpin/dimer *từng primer*; **cấu trúc bậc 2 của template/amplicon** quanh vùng bắt primer có thể ức chế khuếch đại. [Fan19] chứng minh định lượng (PubMed, DOI [10.1080/07391102.2018.1498804](https://doi.org/10.1080/07391102.2018.1498804)): hairpin gần vùng bắt primer làm giảm/mất khuếch đại, **mạnh nhất khi hairpin nằm bên trong amplicon**; mức ức chế tăng theo chiều dài stem & giảm theo kích thước loop; **stem 20-bp → không tạo được sản phẩm**. Cơ chế: cạnh tranh ức chế primer bám template.
**Đề xuất (bám khuyến nghị [Fan19]):** dùng ViennaRNA (đã có) fold **≥60 bp quanh mỗi vùng bắt primer** (cả trong lẫn ngoài amplicon), phát hiện hairpin bền gần binding site → thêm tiêu chí `template_structure` (điểm nhẹ) hoặc cảnh báo `warning` nếu có stem dài/loop nhỏ tại binding site. Ưu tiên vùng *trong* amplicon (tác động mạnh hơn theo [Fan19]).
**Effort:** ~1–1.5 ngày. **Rủi ro:** tăng thời gian `/api/design` (fold chuỗi dài hơn) — đo & cache theo miRNA. Cần template ngữ cảnh (60 bp quanh site) — với miRNA ngắn amplicon nhỏ nên chi phí thấp.
**Ưu tiên:** cao hơn các mục khác trong §12 vì đây là mục **duy nhất có bằng chứng thực nghiệm định lượng trực tiếp** ([Fan19]).

### 12.3 Tm matching tường minh forward vs reverse/effective
**Vấn đề:** `tm_pair_match` weight rất thấp (0.01) vì reverse là universal cố định — nhưng chênh Tm lớn giữa forward và điều kiện annealing vẫn ảnh hưởng 2-step.
**Đề xuất:** báo cáo rõ ΔTm(forward, reverse) trong ThermoTable + cân nhắc cảnh báo nếu |ΔTm| > 5°C. Không nhất thiết đổi weight.
**Effort:** ~0.25 ngày (chủ yếu hiển thị). **Rủi ro:** thấp.

### 12.4 Adaptive edge-case (thay vì chỉ cảnh báo)
**Vấn đề:** §7 chỉ *cảnh báo* miRNA GC thấp/ngắn.
**Đề xuất:** với E1/E4, tự động **đề xuất tăng độ dài 5′ tail** (tail nâng Tm mà không đổi vùng bắt cặp — Phase 2 §C) và hiển thị "suggested tail length" tính ngược từ Tm target. Nâng cao hơn: gợi ý base biến đổi (LNA) — chỉ ghi chú, không tự thiết kế.
**Effort:** ~1 ngày. **Rủi ro:** cần validate công thức tail-Tm; đánh dấu "gợi ý, cần kiểm nghiệm".

### 12.5 Giải thích "vì sao set này thắng" (Pareto view)
**Vấn đề:** người dùng thấy điểm tổng nhưng khó hiểu trade-off giữa 3 set.
**Đề xuất:** trong ThermoTable Tab A, highlight với mỗi set 2–3 tiêu chí nó vượt trội / thua kém (đã có `set.explanations` — tận dụng). Không đổi thuật toán, chỉ trình bày. (Có thể coi là mở rộng §5, làm luôn nếu nhanh.)
**Effort:** ~0.5 ngày. **Rủi ro:** thấp.

### 12.6 Ưu tiên đề xuất (cập nhật v1.1 sau kiểm chứng tài liệu)
Nếu làm: **12.5 (rẻ, UX cao) → 12.2 (có bằng chứng [Fan19], tác động khoa học lớn nhất) → 12.1 (an toàn kết quả) → 12.3 → 12.4**. 12.2 được nâng lên vì là mục duy nhất có bằng chứng thực nghiệm định lượng. Tất cả chờ Vuong chốt trước khi mở Phase 5.

---

## 13. Câu hỏi mở cho Vuong (nếu muốn tinh chỉnh)
1. Ngưỡng edge-case E2/E7/E8 (`[convention]`) — giữ mặc định hay Vuong có số liệu lab riêng?
2. ResultsPage: tách route `/results` (spec này) hay Vuong muốn giữ inline + chỉ thêm bảng/export? (spec mặc định tách route)
3. PDF: cần chèn logo lab thật (`HuynhLuanAI.jpg` trong repo) vào header report không?
4. Có muốn gộp §12.5 vào Phase 4 luôn (rẻ) không, hay để riêng?

---

*Hết SPEC_phase4.md v1.0 — đồng bộ SPEC_week1 v3.2 / SPEC_phase2 v2.8.3 / SPEC_phase3. Cập nhật version khi có thay đổi.*
