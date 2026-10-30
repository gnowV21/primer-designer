# SPEC CHI TIẾT — Stem-loop RT-qPCR Primer Designer
# Phiên bản 4.0 — Phase 1–8 HOÀN THÀNH · Cập nhật 2026-07-09

---

## 0. Hướng dẫn đọc spec này (dành cho Claude Code)

- Đây là tài liệu nguồn sự thật duy nhất. Mọi quyết định kỹ thuật phải tuân theo spec này.
- Khi nhận task mới: đọc lại section liên quan trước khi viết bất kỳ dòng code nào.
- Không tự ý thêm tính năng, thay đổi layout, hoặc dùng thư viện ngoài danh sách cho phép.
- Trước mỗi `git commit`: chạy security check (kiểm tra hardcoded secrets, injection risk).
- **Ngôn ngữ UI:** All UI text MUST be in English — labels, tooltips, errors, warnings, placeholders, buttons. No Vietnamese in the UI layer.
- **Scoring:** SCORING_WEIGHTS_V4 (15 criteria, sum = 1.00) — KHÔNG thay đổi. RT primer KHÔNG scored. Probe KHÔNG scored.
- **LNA Tm:** Informational only — KHÔNG vào SCORING_WEIGHTS_V4, KHÔNG vào hard filters.

---

## 1. Tổng quan dự án

**Tên:** HG Lab — Stem-loop RT-qPCR Designer  
**Mục đích khoa học:** Thiết kế tự động 3 loại primer cho phản ứng Stem-loop RT-qPCR dùng để định lượng mature miRNA. Phát triển từ phương pháp của Chen et al. (2005) với các cải tiến về độ nhạy Tm và scoring đa tiêu chí V4.  
**Người dùng:** Nhà nghiên cứu sinh học phân tử, không cần biết IT.

### Ba primer cần thiết kế

| Primer | Vai trò | Đặc điểm kỹ thuật |
|--------|---------|-------------------|
| Stem-loop RT primer | Phiên mã ngược | Thân hairpin 44 nt (STEMLOOP_BODY) + RC 3' 6 nt miRNA |
| Forward qPCR primer | Khuếch đại đặc hiệu | 12–17 nt specific region + 5' GC-rich tail → Tm ≈ 60°C |
| Universal reverse primer | Cố định cho mọi assay | 5′-CCAGTGCAGGGTCCGAGGTA-3′ (20 nt, Kramer 2011) |

### Trạng thái dự án

| Phase | Nội dung | Trạng thái |
|-------|----------|------------|
| Phase 1 (Week 1) | Setup, form input, miRBase API | ✅ HOÀN THÀNH |
| Phase 2 | Thuật toán thiết kế primer, V3 scoring | ✅ HOÀN THÀNH |
| Phase 3 | V4 scoring (15 criteria), bound fraction, hard filters | ✅ HOÀN THÀNH |
| Phase 4 | TaqMan probe design, multiplex check | ✅ HOÀN THÀNH |
| Phase 5 | Protocol advisor, edge cases, normalization advisor | ✅ HOÀN THÀNH |
| Phase 6 | BLAST off-target, family specificity map | ✅ HOÀN THÀNH |
| Phase 7 | Family benchmark (50 miRNAs), isoMiR flag | ✅ HOÀN THÀNH |
| Phase 8 | Batch design, LNA Tm calculator, session history | ⚠️ GỠ / RÚT GỌN — xem ghi chú dưới |
| Nhóm A | A1 Batch · A2 LNA · A3 Species (`PLAN_GapA_ScientificCompleteness.md`) | 🔧 A1 BỎ · A2 XONG (benchmarked) · A3 XONG — xem ghi chú |

> **⚠️ Phase 8 — GỠ / RÚT GỌN (cập nhật 2026-08-14)**
> Phase 8 đã được rút gọn khỏi sản phẩm. Các phần dưới (14, 15, 17 batch, 22 tests batch, 23) mô tả tính năng **không còn tồn tại** — giữ lại làm lịch sử thiết kế, không phản ánh code hiện tại.
> - **Batch design — GỠ HOÀN TOÀN:** BatchPage, BatchDesignPanel, useBatchDesign, backend `batch_design.py` + test đã xóa; route `/batch` và tab Navbar "Batch" đã bỏ; blueprint `batch_design_bp` không còn đăng ký trong `app.py`. Constants `BATCH_*` cũng đã dọn khỏi `constants.py`.
> - **Session history — GỠ:** HistoryPanel (UI), hook `useHistory.js` và `lib/historyDB.js` (IndexedDB) đã xóa; auto-save trong SearchPage đã gỡ. Không còn lưu/duyệt lịch sử phiên.
> - **LNA Tm calculator — BẬT + ĐÃ BENCHMARK (2026-08-14):** `USE_LNA_SUGGESTIONS=True`. Bảng NN trong `lna_tm.py` nay là **số thật đã kiểm chứng** — Owczarzy 2011 Table 2 (`_MCTIGUE04` = single-LNA full params suy từ McTigue 2004 32NN; `_OWCZARZY11` = consecutive-LNA). Đã sửa bug initiation (áp SantaLucia init cho **cả 2 đầu** duplex). `tests/test_lna_benchmark.py` đối chiếu McTigue 2004 Table 1 (39 oligo đo thực, 1 M Na⁺): **ΔTm RMSD 0.78 °C** (paper 0.85), **absolute Tm RMSD 1.54 °C** (paper method-4 1.47), per-oligo ΔTm ≤ 2.5 °C. `/api/health` expose `features.lna_suggestions`; frontend `useLnaEnabled` hiện/ẩn nút LNA theo flag. LnaPanel render trong `ResultsPage/ThermoTable` + Analyzer.

> **🔧 Nhóm A — Scientific Completeness (cập nhật 2026-08-14, `PLAN_GapA_ScientificCompleteness.md`)**
> - **A1 Batch — BỎ (quyết định của chủ dự án).** Batch mâu thuẫn với hướng `feat/design-focus`; giữ nguyên trạng thái đã gỡ. Khôi phục từ commit `269a4c9` nếu cần.
> - **A2 LNA — XONG + BENCHMARKED (2026-08-14).** Chủ dự án cung cấp 2 paper gốc (McTigue 2004, Owczarzy 2011). Đã thay placeholder bằng số thật (Owczarzy Table 2), sửa bug initiation 2 đầu, và viết `tests/test_lna_benchmark.py` đối chiếu 39 oligo đo thực trong McTigue Table 1: ΔTm RMSD 0.78 °C, absolute Tm RMSD 1.54 °C (≤ 2 °C). Bật lại `USE_LNA_SUGGESTIONS=True`. Xem ghi chú Phase 8.
> - **A3 Species — XONG.** Family DB `mirbase_family_overhangs.json` rebuild đa loài `hsa,mmu,rno` (300 KB, seed-based) bằng `scripts/build_mirbase_data.py --species hsa,mmu,rno`. `check_family_crossreactivity(..., species=None)` nay scope theo species (prefix từ `mirna_name`, reuse `_extract_species_prefix`; loại same-family ortholog khác loài → `cross_species_excluded`, nhất quán logic BLAST). UI `FamilySpecificityMap` hiển thị species + số cross-species excluded. Test `tests/test_family_species.py` (6 pass) gồm `test_let7a_family_loaded_from_miFam` (hsa + mmu). **Lưu ý:** `_find_family` là name-based → chuỗi dán không có tên miRNA không tra được family (form `species` chỉ là fallback); species scoping thực chất do prefix trong tên miRNA quyết định.

---

## 2. Stack kỹ thuật (KHÔNG thay đổi)

### Frontend
```
React 18 + Vite 5 + Tailwind CSS 3
React Router DOM v6
Axios (API calls)
```

### Backend
```
Python 3.11 + Flask 3 + flask-cors + requests
primer3-py 2.0.3    — SantaLucia 1998 NN Tm, hairpin/dimer ΔG
ViennaRNA 2.6.4     — RNA.fold MFE (optional, falls back to primer3-py)
biopython 1.83      — sequence utilities
numpy 1.26.4        — scoring calculations
```

### Thư viện KHÔNG dùng
- Redux, Zustand (dùng useState/useRef)
- React Hook Form, Formik
- Ant Design, Material UI, Chakra UI (chỉ Tailwind)
- NUPACK, RNAstructure, thư viện hybrid ngoài
- Thêm dependency backend mới — phải có approval

---

## 3. Cấu trúc thư mục hiện tại

```
primer-designer/
├── SPEC_week1.md
├── CLAUDE.md
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── constants/
│       │   └── defaults.js          ← DEFAULTS, LIMITS, SPECIES_OPTIONS, SAMPLE_TYPE_PRESETS, QPCR_SYSTEM_NOTES, RT_ENZYME_NOTES
│       ├── contexts/
│       │   └── ThemeContext.jsx     ← theme switcher (teal/warm/cool/slate)
│       ├── lib/
│       │   └── historyDB.js         ← IndexedDB wrapper: saveHistory/listHistory/loadHistory/deleteHistory/clearHistory/countHistory
│       ├── hooks/
│       │   ├── useMiRBase.js        ← miRNA lookup: idle|loading|found|not_found|error
│       │   ├── useBatchDesign.js    ← batch hybrid sync/async: idle|streaming|polling|done|error
│       │   ├── useHistory.js        ← wraps historyDB.js với React state
│       │   └── useBlastCheck.js     ← BLAST off-target query
│       ├── utils/
│       │   └── seqAnalysis.js       ← computeSeqAnalysis: length, gc, end3
│       ├── components/
│       │   ├── Navbar.jsx           ← Home + Designer tabs + theme swatches
│       │   ├── Footer.jsx
│       │   ├── ProbeCard.jsx        ← TaqMan probe display
│       │   ├── MultiplexPanel.jsx   ← multiplex cross-dimer check
│       │   ├── FamilySpecificityMap.jsx ← family overhang heatmap
│       │   ├── NormalizationAdvisor.jsx ← normalization advisory
│       │   ├── BatchDesignPanel/
│       │   │   └── index.jsx        ← batch input, progress, NDJSON streaming, polling
│       │   ├── HistoryPanel/
│       │   │   └── index.jsx        ← IDB session list, load/delete
│       │   ├── LnaPanel/
│       │   │   └── index.jsx        ← LNA position suggester display
│       │   ├── icons/
│       │   │   └── PrimerIcons.jsx
│       │   └── ui/
│       │       ├── Tooltip.jsx
│       │       ├── NumInput.jsx
│       │       ├── RangeSlider.jsx
│       │       └── Toggle.jsx
│       └── pages/
│           ├── HomePage.jsx
│           ├── RoadmapPage.jsx
│           ├── BenchmarkPage.jsx
│           ├── BatchPage.jsx        ← BatchDesignPanel (left) + HistoryPanel (right)
│           ├── ResultsPage/
│           │   ├── index.jsx        ← full results page (navigated via router state)
│           │   ├── EdgeCaseBanner.jsx
│           │   ├── ExportBar.jsx
│           │   ├── ProtocolAdvisor.jsx
│           │   ├── QualitySummary.jsx
│           │   └── ThermoTable.jsx
│           └── SearchPage/
│               ├── index.jsx        ← state owner, submit handler, mini-nav
│               ├── SequenceGroup.jsx
│               ├── PrimerConstraintsGroup.jsx  ← merged: Thermo + Primer + Detection
│               ├── QpcrConditionsGroup.jsx
│               ├── ExperimentalContextGroup.jsx
│               └── ResultsSection/
│                   ├── index.jsx
│                   ├── PrimerSetCard.jsx
│                   ├── ScoreGauge.jsx
│                   ├── ScoreBreakdown.jsx
│                   ├── StructureChecks.jsx
│                   ├── OverhangComparison.jsx
│                   ├── RejectionLog.jsx
│                   ├── ExportButtons.jsx
│                   └── OffTargetPanel.jsx
└── backend/
    ├── app.py                       ← registers all blueprints
    ├── requirements.txt
    ├── algorithm/
    │   ├── constants.py             ← tất cả magic numbers, weights, thresholds
    │   ├── design_pipeline.py       ← run(seq, params, mirna_name) → full result dict
    │   ├── stemloop_rt.py
    │   ├── forward_primer.py
    │   ├── universal_reverse.py
    │   ├── thermodynamics.py
    │   ├── scoring.py               ← V4 scoring (15 criteria)
    │   ├── sequence_utils.py
    │   ├── edge_cases.py
    │   ├── hard_filters.py
    │   ├── template_structure.py
    │   ├── probe_design.py
    │   ├── protocol_advisor.py
    │   ├── normalization_advisor.py
    │   ├── bound_fraction.py
    │   ├── hybrid_tm.py             ← Sugimoto 1995 DNA:RNA Tm
    │   ├── lna_tm.py                ← LNA doublet NN (McTigue 2004 / Owczarzy 2011)
    │   ├── structure_check/
    │   │   ├── __init__.py
    │   │   └── heterodimer.py
    │   └── specificity_check/
    │       ├── __init__.py
    │       ├── family_crossreactivity.py
    │       └── isomir_flag.py
    ├── routes/
    │   ├── mirbase.py               ← GET /api/mirbase/<id>
    │   ├── design.py                ← POST /api/design (delegates to design_pipeline.run)
    │   ├── batch_design.py          ← POST /api/batch-design, GET /api/batch-status/<id>
    │   ├── lna_suggest.py           ← POST /api/lna-suggest
    │   ├── blast_check.py           ← POST /api/blast-check
    │   ├── multiplex_check.py       ← POST /api/multiplex-check
    │   ├── export.py                ← POST /api/export
    │   └── benchmark.py             ← GET /api/benchmark
    ├── db/
    │   ├── local_db.py
    │   ├── circuit_breaker.py       ← FAILURE_THRESHOLD=3, RESET_TIMEOUT=300s
    │   └── mirbase.db               ← KHÔNG commit (xem .gitignore)
    ├── data/
    │   ├── mirbase_family_overhangs.json
    │   └── known_5prime_isomir_mirnas.json
    ├── tests/
    │   ├── __init__.py
    │   ├── test_lna_tm.py           ← 29 unit tests
    │   └── test_batch_design.py     ← 7 unit tests
    └── scripts/
        ├── seed_db.py
        └── fetch_and_seed.py
```

---

## 4. Màu sắc & Design Tokens

```js
// Teal — màu chủ đạo
teal = {
  50:  '#E1F5EE',   // bg chip, focus ring, hover
  200: '#5DCAA5',   // border nhẹ
  600: '#0F6E56',   // button gradient start, track fill, thumb
  700: '#0f766e',   // thumb hover, drag callout bg
  800: '#085041',   // button gradient end
}
amber = { 50: '#FFFBEB', 200: '#FCD34D', 700: '#B45309' }  // warning
red   = { 50: '#FEF2F2', 200: '#FECACA', 400: '#F87171', 600: '#DC2626' }  // error
gray  = { 100: '#F3F4F6', 200: '#E5E7EB', 400: '#9CA3AF', 500: '#6B7280', 700: '#374151', 900: '#111827' }
```

### Typography chuẩn

| Phần tử | Class |
|---------|-------|
| Section title | `text-sm font-semibold text-gray-500` |
| Field label | `text-sm font-medium text-gray-700` |
| Input text | `text-sm text-gray-900` |
| Error message | `text-xs text-red-600` |
| Warning banner | `text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed` |
| Placeholder | `text-sm text-gray-400` |
| Unit suffix | `text-xs text-gray-400` |
| Value badge (RangeSlider) | `text-xs text-teal-700 font-semibold px-2 py-0.5 rounded-md bg-teal-50 border border-teal-100 tabular-nums` |

> ⚠ KHÔNG dùng `uppercase tracking-wider` cho section title.
> ⚠ Tất cả warning banners phải dùng cùng amber class string trên.

---

## 5. Layout tổng thể & Routing

### Routing (React Router DOM v6)

| Path | Component | Title |
|------|-----------|-------|
| `/` | Redirect → `/search` | — |
| `/home` | HomePage | `HG Lab \| Home` |
| `/roadmap` | RoadmapPage | `HG Lab \| Roadmap` |
| `/search` | SearchPage | `HG Lab \| Primer Designer` |
| `/results` | ResultsPage | (set bởi ResultsPage) |
| `/batch` | BatchPage | `HG Lab \| Batch Design` |
| `/benchmark` | BenchmarkPage | — |

### Layout tổng thể

```
┌──────────────────────────────────────────────────────────────────────┐
│ NAVBAR (h-14, border-bottom)                                          │
│  [Logo] HG Lab               [Home][Roadmap][Designer][Batch]  ●●●● │
│         Stem-loop RT-qPCR Designer                        theme swatches│
├─────────────────────────────────────────────┬────────────────────────┤
│ MAIN CONTENT (flex-1, overflow-y-auto, p-6) │ CHATBOT PANEL          │
│                                             │ (collapsed/expanded)   │
├─────────────────────────────────────────────┴────────────────────────┤
│ FOOTER (h-9, border-top)                                              │
│  HG Lab · Human Genetics Laboratory, HCMUS · v0.1.0-dev   Contact…  │
└──────────────────────────────────────────────────────────────────────┘
```

### Navbar chi tiết

```jsx
// Brand: logo 32px + "HG Lab" bold 14px + "Stem-loop RT-qPCR Designer" teal 11px
// Nav tabs (4):
Tab thường:  px-4 py-1.5 rounded-lg text-sm font-medium text-gray-500 hover:text-teal-700 hover:bg-teal-50
Tab active:  px-4 py-1.5 rounded-lg text-sm font-semibold text-teal-700 bg-teal-50 border border-teal-200 shadow-sm
// Labels: Home | Roadmap | Designer | Batch

// Theme swatches (sau divider):
// 4 colored circles w-4 h-4 rounded-full
// Active: ring-2 ring-offset-1 ring-gray-400 scale-125
// Inactive: opacity-60 hover:opacity-100 hover:scale-110
```

### ThemeContext (contexts/ThemeContext.jsx)

```jsx
// THEMES: { teal, warm, cool, slate } — mỗi theme có { label, swatch }
// Lưu vào localStorage('hglab-theme')
// Swatches màu inject vào :root CSS vars (theme-aware components dùng)
```

---

## 6. Constants (frontend/src/constants/defaults.js)

```js
export const DEFAULTS = {
  sequence: {
    searchQuery: '', mirnaName: '', mirbaseId: '',
    matureSequence: '', species: 'human', accession: '', family: '',
  },
  thermodynamic: {
    tmMin: 58, tmMax: 62,
    saltConcentration: 50,        // mM [Na+]
    primerConcentration: 200,     // nM (IDT PrimerQuest default)
    magnesiumConcentration: 1.5,  // mM Mg2+ total
    dntpTotal: 0.8,               // mM total 4 dNTPs
    kPlusConc: 50,                // mM [K+]
    bufferPH: 8.4,
  },
  primerConstraints: {
    gcMin: 40, gcMax: 60,
    lengthMin: 20, lengthMax: 27,
    gcClamp3prime: true,
    bindingRegion3prime: 6,       // KHÔNG thay đổi default này
  },
  qpcr: {
    annealingTemp: 60, ampliconMin: 60, ampliconMax: 150,
    totalCycles: 40, pcrEfficiencyMin: 90, pcrEfficiencyMax: 110,
  },
  detectionMethod: {
    signalMethod: 'taqman', quantMode: 'relative',
    referenceGene: 'miR-16', customReferenceGene: '',
    enableFamilyDiscrimination: true, enablePrecursorCheck: false,
    enableRefoldingProtocol: true,
  },
  experimentalContext: {
    sampleType: 'tissue', qpcrSystem: 'other',
    rtEnzyme: 'mmlv', exportFormat: ['copy'], userLevel: 'advanced',
  },
};

export const LIMITS = { /* tmMin/Max, saltMin/Max, mgMin/Max, ... */ };
export const SPECIES_OPTIONS = [ human, mouse, rat, other ];
export const SAMPLE_TYPE_PRESETS = { serum, plasma, ffpe, tissue, cell, urine };
export const QPCR_SYSTEM_NOTES   = { abi, biorad, roche, qiagen, other };
export const RT_ENZYME_NOTES     = { mmlv, superscript, revertaid, other };
```

---

## 7. SearchPage (/search) — Single Design

### 7.1. State & submit flow

```jsx
// State (index.jsx):
formData: { sequence, thermodynamic, primerConstraints, qpcr, detectionMethod, experimentalContext }
errors, isSubmitting, activeSection, visitedSections, resetKey, sectionOpenRequests, designError

// computedFields (useMemo):
freeMagnesium = max(0, mg - dntpTotal)
naEquivalent  = saltConc + 120*sqrt(max(0, mg-dntpTotal))  [von Ahsen 2001, PMID 11673362 — trước ghi nhầm Owczarzy 2004]

// POST /api/design: { ...formData, _computed: computedFields }
// On success → navigate('/results', { state: { results, params } })
//           + saveHistory() non-blocking (single type)
// On 422     → inline error display (ResultsSection với error prop)
// On timeout → ECONNABORTED error message
```

### 7.2. Mini navigation sidebar (xl+ screens)

```
4 nav items: Sequence · Primer · qPCR · Context
Dot: teal khi configured, gray khi chưa
Progress bar: {readyCount}/4 ready
Click → expand section + smooth scroll + mark visited
```

### 7.3. Layout 4 sections

```
SearchPage
├── [SequenceGroup]            — id="seq"
├── [PrimerConstraintsGroup]   — id="constraints"  ← merged: Thermo + Primer + Detection
├── [QpcrConditionsGroup]      — id="qpcr"
├── [ExperimentalContextGroup] — id="context"
└── [Submit button]
```

---

## 8. Nhóm 1: SequenceGroup.jsx

```
┌─ Sequence Information ─────────────────── [?] ──────────────────────┐
│  miRBase ID                                                           │
│  [hsa-miR-21-5p              ] [Search ⟳]  ← Tab/Enter triggers     │
│  ✓ Found: Homo sapiens · Family: miR-21                              │
│                                                                       │
│  Mature miRNA sequence (5′→3′)                                       │
│  [UAGCUUAUCAGACUGAUGUUGA                   ]                         │
│                                                                       │
│  Species                                                              │
│  [Human ▾]  (Human / Mouse / Rat / Other)                           │
│                                                                       │
│  ℹ 22 nt · GC: 40.9% · 3′ end: UGA     ← teal info bar             │
└───────────────────────────────────────────────────────────────────────┘
```

- Sequence validation: auto-uppercase, T→U error, invalid chars, <15 nt, >30 nt
- useMiRBase hook: `idle | loading | found | not_found | error`
- seqAnalysis (useMemo từ computeSeqAnalysis): `{ length, gc, end3 }` — drives progress dot + submit guard

---

## 9. Nhóm 2: PrimerConstraintsGroup.jsx (MERGED)

> Section này merge ThermodynamicGroup + PrimerConstraintsGroup cũ + DetectionMethodGroup.

```
┌─ Primer Design Constraints ────────────── [?] ──────────────────────┐
│  [Thermodynamic sub-section]                                          │
│  Tm range:  50°C ──[===58°──62°===]── 70°C                          │
│  Na+ [50] mM  K+ [50] mM  Mg2+ [1.5] mM                            │
│  dNTP [0.8] mM  Primer [200] nM  pH [8.4]                           │
│  Free Mg2+: 0.70 mM ⚠ [colored indicator]                           │
│  [Na+ equivalent: 149.23 mM display]                                 │
│                                                                       │
│  [Primer Constraints sub-section]                                     │
│  GC %: 20% ──[===40%─60%===]── 80%                                  │
│  Length: 15nt ──[===20nt─27nt===]── 27nt                            │
│  3' GC Clamp [●──] ON   Binding region [6] nt                       │
│                                                                       │
│  [Detection Method sub-section]                                       │
│  (●) TaqMan probe  ( ) SYBR Green                                    │
│  (●) Relative  ( ) Absolute    Reference: [miR-16 ▾] [custom…]     │
│  [✓] Family discrimination  [ ] Pre-miRNA check  [✓] Refolding      │
│                                                                       │
│  [Warning banners — ionic conditions, binding region, GC content]    │
└───────────────────────────────────────────────────────────────────────┘
```

**Effective free [Mg²⁺] indicator:**
```
freeMg ≥ 1.5 mM → teal   "✓ Optimal (1.5–3 mM)"
freeMg ≥ 1.0 mM → amber  "⚠ Below optimal"
freeMg < 1.0 mM → red    "✕ Insufficient"
```

**Reset button (ThermodynamicGroup):** 2-step confirmation, 2.5s auto-cancel.

---

## 10. Nhóm 3: QpcrConditionsGroup.jsx

```
┌─ qPCR Conditions ──────────────────────── [?] ──────────────────────┐
│  Annealing temp [60] °C  Total cycles [40]  PCR efficiency [90–110]%│
│  Amplicon size:  40bp ──[===60────150===]── 300bp                   │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 11. Nhóm 4: ExperimentalContextGroup.jsx

```
┌─ Experimental Context ─────────────────── [?] ──────────────────────┐
│  Sample type [Tissue ▾]   qPCR system [Other ▾]   RT enzyme [M-MLV ▾]│
│  Export format: [✓] Copy  [ ] PDF  [ ] CSV                          │
│  [Serum/Plasma/FFPE preset banners khi sample type thay đổi]         │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 12. Submit Button & Error Display

```jsx
// Submit button states:
// Ready:    teal gradient, "Design Primers →"
// Errors:   gray bg, "✕ Fix errors to continue", cursor-not-allowed
// Loading:  gray bg, "⟳ Processing…"

// Below button (khi isSeqReady && !hasErrors):
// "Stem-loop primer · Forward primer · Universal reverse primer"

// Error display (designError state):
// 422 no_candidates → ResultsSection với error prop (rejection summary, edge cases)
// timeout           → ECONNABORTED message
// network           → "Could not reach the backend"
```

---

## 13. ResultsPage (/results)

Navigated via `navigate('/results', { state: { results, params } })`.

```
ResultsPage
├── ExportBar          ← copy / PDF / CSV buttons
├── EdgeCaseBanner     ← E1 (short), E2 (GC-rich), E3 (repeat), E4 (low GC) warnings
├── QualitySummary     ← score gauge, grade badge, algorithm version
├── [Top 3 PrimerSetCards]
│   ├── PrimerSetCard  ← rank, sequence, Tm, GC, amplicon, score breakdown
│   │   ├── ScoreGauge
│   │   ├── ScoreBreakdown  ← 15 criteria weight × score
│   │   ├── StructureChecks ← hairpin/dimer ΔG, end stability
│   │   └── OverhangComparison
│   └── ...
├── ProbeCard          ← TaqMan probe (nếu signalMethod=taqman)
├── ThermoTable        ← Tm, GC, salt params summary
├── ProtocolAdvisor    ← step-by-step protocol recommendation
├── FamilySpecificityMap ← family overhang similarity heatmap
├── NormalizationAdvisor ← advisory khi sampleType khác rỗng
├── OffTargetPanel / RejectionLog
└── LnaPanel           ← LNA position suggester (informational only)
```

**LnaPanel (informational only):**
- Calls `POST /api/lna-suggest`
- Displays: suggested positions, tm_dna, tm_lna, delta_tm, search strategy (exhaustive/greedy)
- Disclaimer: "LNA Tm is informational only — not used in scoring or primer filtering."
- Feature flag: `USE_LNA_SUGGESTIONS` trong constants.py (503 nếu False)
- RT primer role → 400 (DNA:RNA context out of scope)

---

## 14. BatchPage (/batch)

```
BatchPage
├── LEFT: BatchDesignPanel (flex-1)
│   ├── Textarea: paste miRNA IDs (one per line)
│   ├── Submit → POST /api/batch-design
│   ├── ≤10 miRNAs → NDJSON streaming (sync path)
│   │   Progress: "3/10 · 2 ok · 1 error" live-update
│   ├── >10 miRNAs → async job (202 + job_id + polling every 2s)
│   │   Progress bar + ETA
│   ├── Results table: miRNA | Status | Tm | Score
│   └── Loaded-from-history display (nếu loadedEntry state)
└── RIGHT: HistoryPanel (w-64, border-left)
    ├── List saved runs (newest first)
    ├── Click → load vào left panel
    └── Delete button per entry
```

**useBatchDesign hook:**
- `BATCH_ASYNC_THRESHOLD = 10` — phải match backend constant
- `POLL_INTERVAL_MS = 2000`
- Cleanup: useEffect unmount clears setInterval
- Status: `idle | streaming | polling | done | error`

---

## 15. Session History (historyDB.js)

```js
// IndexedDB: DB_NAME="hglab_primer_history", STORE="design_history", MAX_ENTRIES=100
// Key: `hist_${Date.now()}_${crypto.randomUUID().slice(0,8)}` — collision-safe

// Schema mỗi record:
{
  id:         "hist_<ms>_<uuid8>",
  type:       "single" | "batch",
  created_at: ISO8601,
  mirnas:     string[],
  params:     {},           // thermodynamic params used
  results:    [],           // full design output
  summary:    { count, succeeded, failed, best_score }
}

// FIFO eviction: put + getAllKeys + delete trong 1 readwrite transaction (atomic)
// _dbPromise = null on reject (no permanent poison)

// Public API:
saveHistory(entry)   → Promise<id>
listHistory()        → Promise<Array<summary>>   (newest first)
loadHistory(id)      → Promise<record | null>
deleteHistory(id)    → Promise<void>
clearHistory()       → Promise<void>
countHistory()       → Promise<number>
```

**Auto-save:**
- Single design (SearchPage): non-blocking `saveHistory().catch(() => {})` sau navigate
- Batch design (BatchPage): `save()` trong `handleBatchDone`

---

## 16. Shared UI Components

### NumInput.jsx
```jsx
// Local raw string state → syncs từ value prop via useEffect
// onFocus: select all; khi '' hoặc NaN → set error, không update parent
// onChange emits synthetic { target: { value: string } }
```

### RangeSlider.jsx
```jsx
// Props: min, max, valueMin, valueMax, step, unit, label, tooltip, onChange
// Track fill: teal-600, thumbs: teal-600/hover-700
// Drag callout bubble trên thumb đang kéo
// Constraint: valueMin ≤ valueMax - step
```

### CollapsibleSection.jsx
```jsx
// Title: text-sm font-semibold text-gray-500 (KHÔNG uppercase)
// Arrow: ▸ teal-600, rotate 90° khi open
// Status dots: red-500 (error) | amber-400 (warning) khi collapsed
// Animation: grid-template-rows 0fr ↔ 1fr
// onFirstOpen: fired once → mark visited
// openRequested: counter trigger từ mini-nav
```

### Tooltip.jsx
```jsx
// Show delay: 250ms; keyboard focus: immediate
// Position: right (flip left nếu < 290px to viewport edge)
// Renders via createPortal vào document.body (position: fixed)
```

---

## 17. Backend API — Route Map

| Method | Path | Module | Mô tả |
|--------|------|--------|-------|
| GET | `/api/health` | app.py | Health check |
| GET | `/api/mirbase/<id>` | mirbase.py | Lookup miRNA (SQLite → miRBase REST → RNAcentral) |
| POST | `/api/design` | design.py | Single primer design (→ design_pipeline.run) |
| POST | `/api/batch-design` | batch_design.py | Batch: sync NDJSON (≤10) hoặc async job (>10) |
| GET | `/api/batch-status/<job_id>` | batch_design.py | Poll async job progress |
| POST | `/api/lna-suggest` | lna_suggest.py | LNA position suggestion (informational) |
| POST | `/api/blast-check` | blast_check.py | BLAST off-target check |
| POST | `/api/multiplex-check` | multiplex_check.py | Multiplex cross-dimer check |
| POST | `/api/export` | export.py | PDF/CSV export |
| GET | `/api/benchmark` | benchmark.py | Load benchmark results |

**Batch design chi tiết:**

```python
# ≤ BATCH_ASYNC_THRESHOLD=10: sync NDJSON streaming
# Content-Type: application/x-ndjson
# Lines: {"type":"meta","total":N} → N×{"type":"result","mirna":"...","status":"ok/error",...} → {"type":"done","succeeded":X,"failed":Y}

# > BATCH_ASYNC_THRESHOLD=10: async 202
# Response: {"job_id":"batch_xxxx","total":N,"mode":"async","status":"queued","warnings":[...]}
# Poll: GET /api/batch-status/<job_id> → {"status":"queued|running|done","completed":X,...}

# BATCH_MAX_SIZE=50 — truncate với warning
# Dedup: seen set, giữ thứ tự
# Circuit breaker: chỉ record_failure() cho 5xx / network, KHÔNG cho 404
```

**design_pipeline.run(seq, params, mirna_name):**
- Single source of truth cho cả `/api/design` và `/api/batch-design`
- Input: seq (RNA uppercase, đã validated), params (flat dict), mirna_name
- Output: dict matching /api/design response schema
- signalMethod default: `"taqman"` (KHÔNG `"sybr"`)

---

## 18. LNA Tm Module (algorithm/lna_tm.py)

```python
# Sources: SantaLucia 1998 (DNA-DNA), McTigue 2004 (one-LNA), Owczarzy 2011 (LNA-LNA)
# Doublet classification: dna_dna | one_lna | lna_lna
# Public API:
calc_lna_tm(sequence, lna_positions, params) → {
  tm_dna, tm_lna, delta_tm, lna_positions,
  method, per_doublet, warnings
}
suggest_lna_positions(sequence, target_tm, params, max_lna, mode, sibling_mismatch_positions) → {
  suggested_positions, tm_achieved, target_met,
  search,  # "exhaustive" | "greedy"
  mode, warnings
}
# Exhaustive khi C(eligible, ≤max_lna) ≤ LNA_EXHAUSTIVE_LIMIT=5000, else greedy
# RT primer role → rejected (DNA:RNA context out of scope)
```

---

## 19. Scoring V4 (15 criteria, sum = 1.00)

```python
SCORING_WEIGHTS_V4 = {
  "tm_accuracy":             0.20,  # forward primer Tm vs TM_FORWARD_TARGET=60°C
  "mfe_stemloop":            0.14,  # RT primer hairpin MFE (ViennaRNA preferred)
  "tm_binding_accuracy":     0.10,  # specific region Tm vs TM_BINDING_TARGET=45°C
  "hairpin_penalty":         0.08,  # forward hairpin ΔG
  "dimer_penalty":           0.08,  # 3'-end & full-structure dimer ΔG
  "end_stability":           0.08,  # 3' end stability kcal/mol
  "gc_content":              0.08,  # GC% vs optimal 50%
  "bound_fraction_binding":  0.05,  # specific region at 42°C (RT step)
  "family_discrimination":   0.05,  # cross-reactivity risk [Chen05]
  "gc_clamp":                0.04,  # 3'-end G/C count
  "bound_fraction_full":     0.03,  # full primer at 55°C (qPCR annealing)
  "primer_size":             0.02,  # specific_length vs FORWARD_SPECIFIC_LEN_REF=17
  "amplicon_size":           0.02,  # amplicon bp
  "tm_pair_match":           0.01,  # |Tm_fwd - Tm_rev|
  "gc_skew":                 0.02,  # GC-skew (more C than G optimal)
}
assert abs(sum(SCORING_WEIGHTS_V4.values()) - 1.00) < 0.001
```

**Quan trọng:**
- RT primer: quality-checked ONLY — KHÔNG scored
- TaqMan probe: quality-checked ONLY — KHÔNG scored
- LNA Tm: informational ONLY — KHÔNG vào V4
- Dimer breakpoints: derived from `SELF_DIMER_DG_3PRIME_MAX ± 1.0`
- `scoring.py:261`: dùng `"specific_region"` key (không phải `"specific_sequence"`)

---

## 20. Data contract — POST /api/design

### Request body
```json
{
  "sequence": { "matureSequence": "UAGCUUAUCAGACUGAUGUUGA", "mirnaId": "hsa-miR-21-5p", ... },
  "thermodynamic": { "tmMin":58,"tmMax":62,"saltConcentration":50,"primerConcentration":200,
                     "magnesiumConcentration":1.5,"dntpTotal":0.8,"kPlusConc":50,"bufferPH":8.4 },
  "primerConstraints": { "gcMin":40,"gcMax":60,"lengthMin":20,"lengthMax":27,
                          "gcClamp3prime":true,"bindingRegion3prime":6 },
  "qpcr": { "annealingTemp":60,"ampliconMin":60,"ampliconMax":150,"totalCycles":40,
             "pcrEfficiencyMin":90,"pcrEfficiencyMax":110 },
  "detectionMethod": { "signalMethod":"taqman","quantMode":"relative","referenceGene":"miR-16",
                        "enableFamilyDiscrimination":true,"enablePrecursorCheck":false,
                        "enableRefoldingProtocol":true },
  "experimentalContext": { "sampleType":"tissue","qpcrSystem":"other","rtEnzyme":"mmlv",
                            "exportFormat":["copy"],"userLevel":"advanced" },
  "_computed": { "freeMagnesium":0.70,"naEquivalent":149.23 }
}
```

### Response body (200)
```json
{
  "top3": [{
    "rank": 1,
    "sequence": "ACGGATCGATCG...",
    "specific_region": "AUGCAUGCAUGC",
    "specific_length": 12,
    "tail_length": 10,
    "gc_percent": 50.0,
    "tm_full": 60.1,
    "tm_binding": 46.3,
    "amplicon_size": 72,
    "total_score": 0.873,
    "grade": "Excellent",
    "scores": { "tm_accuracy":95, "mfe_stemloop":88, ... },
    "weights": { ...SCORING_WEIGHTS_V4 },
    "explanations": { "tm_accuracy": "Forward primer Tm = 60.1°C...", ... },
    "structure_checks": { "hairpin":{...},"self_dimer":{...},"end_stability":{...} },
    "heterodimer_checks": { "fwd_stemloop":{...},"fwd_reverse":{...},"any_high_risk":false },
    "template_structure": { "has_strong_local_hairpin":false },
    "isomir_flag": { "isomir_discrimination_risk":false, ... },
    "binding_start_1based": 1,
    "binding_end_1based": 12
  }],
  "probe": { "sequence":"...", "tm":70.2, "gc":55, ... },
  "probe_note": null,
  "stemloop_rt": {
    "sequence": "GTCGTATCCAGTGCAGG...UCAACA",
    "mfe": -27.5, "mfe_method": "ViennaRNA",
    "tm_hybrid_c": 52.3, "tm_chemistry": "DNA:RNA",
    "overhang_rna": "UCAACA", "binding_length": 6
  },
  "universal_reverse": {
    "sequence": "CCAGTGCAGGGTCCGAGGTA",
    "tm": 60.4, "gc_percent": 65.0,
    "stemloop_reverse_heterodimer": { "dg":-4.1,"risk_level":"LOW" }
  },
  "global_warnings": [{ "field":"signalMethod","severity":"critical","message":"..." }],
  "edge_cases": [{ "code":"E4","severity":"warning","message":"..." }],
  "protocol_advice": { ... },
  "normalization_advice": null,
  "lna_hints": null,
  "specificity_warnings": {
    "cross_reactivity": { "family":"miR-21","cross_reactivity":[],"recommendation":{...} }
  },
  "metadata": {
    "mirna_id":"hsa-miR-21-5p","mirna_length":22,
    "binding_region_nt":6,"candidates_generated":45,
    "elapsed_seconds":0.84,
    "algorithm_version":"3.0.0","scoring_version":"V4 (15 criteria)",
    "output_label":"predicted design quality",
    "output_note":"Score reflects in-silico design quality. NOT PCR efficiency."
  }
}
```

---

## 21. Backend Flask (app.py)

```python
from flask import Flask
from flask_cors import CORS
from routes.mirbase import mirbase_bp
from routes.design import design_bp
from routes.batch_design import batch_design_bp
from routes.lna_suggest import lna_suggest_bp
from routes.blast_check import blast_check_bp
from routes.multiplex_check import multiplex_check_bp
from routes.export import export_bp
from routes.benchmark import benchmark_bp

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://localhost:3000"]}})

for bp in [mirbase_bp, design_bp, batch_design_bp, lna_suggest_bp,
           blast_check_bp, multiplex_check_bp, export_bp, benchmark_bp]:
    app.register_blueprint(bp, url_prefix='/api')
```

---

## 22. Chạy dự án

```bash
# Terminal 1 — Backend
cd backend
pip install -r requirements.txt
python app.py          # → http://localhost:5000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev            # → http://localhost:5173

# Tests
cd backend
python -m pytest tests/ -q
# Expected: 36 passed (29 lna_tm + 7 batch_design)
```

---

## 23. Definition of Done — Phase 8 Complete

> **STATUS: ✅ TẤT CẢ PHASES HOÀN THÀNH** — Verified 2026-07-09

**Phase 8 checklist:**
- [x] Batch design endpoint POST /api/batch-design (sync NDJSON ≤10, async >10)
- [x] Batch status polling GET /api/batch-status/<job_id>
- [x] BatchDesignPanel.jsx: NDJSON streaming reader, polling, progress display
- [x] useBatchDesign.js: cleanup interval on unmount
- [x] Circuit breaker: chỉ trip trên 5xx, không phải 404
- [x] LNA Tm calculator (lna_tm.py): McTigue 2004 + Owczarzy 2011 doublet tables
- [x] POST /api/lna-suggest: validate sequence, role, mode, max_lna (with try/except)
- [x] LnaPanel.jsx: display LNA suggestions (informational only)
- [x] 29 unit tests cho lna_tm.py
- [x] 7 unit tests cho batch_design.py
- [x] historyDB.js: IndexedDB FIFO, atomic eviction, collision-safe key
- [x] useHistory.js hook
- [x] HistoryPanel.jsx: list, load, delete
- [x] Auto-save: single design (SearchPage), batch design (BatchPage)
- [x] design_pipeline.py: signalMethod default = "taqman"
- [x] routes/design.py: collapsed to 30-line wrapper (no duplication)
- [x] 9 algorithm inconsistencies fixed (key mismatch, hardcoded salt, stale comments)

**Known issues (out of scope):**
- ViennaRNA Python bindings required cho RNA MFE (fallback: primer3-py DNA proxy)
- BLAST local DB phải tự build với scripts/build_blast_db.sh
- miRBase.org thỉnh thoảng down → circuit breaker active, dùng local SQLite

---

## 24. Changelog

| Version | Ngày | Thay đổi chính |
|---------|------|----------------|
| v1.0–v3.1 | 2026-06-20 | Week 1: setup, form, miRBase API, SQLite cache, circuit breaker |
| v3.2 | 2026-06-30 | Sync SPEC_phase2: bug fixes defaults (dntpTotal, primerConc, lengthMax), computed fields |
| v4.0 | 2026-07-09 | **Phase 1–8 HOÀN THÀNH.** Cập nhật toàn bộ: routing (4 tabs), BatchPage, ResultsPage, BenchmarkPage, LnaPanel, HistoryPanel, BatchDesignPanel, historyDB.js, useBatchDesign, useHistory, ThemeContext; merged PrimerConstraintsGroup; V4 scoring 15 criteria; design_pipeline.run() dedup; 9 algorithm inconsistencies fixed; 36 unit tests; data contract V4 |
