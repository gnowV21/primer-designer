# SPEC CHI TIẾT — Stem-loop RT-qPCR Primer Designer
# Tuần 1: Thiết lập dự án · Form input · miRBase API
# Phiên bản 3.1 — Week 1 HOÀN THÀNH · Backend SQLite cache + circuit breaker · Bug fixes

---

## 0. Hướng dẫn đọc spec này (dành cho Claude Code)

- Đây là tài liệu gốc. Mọi quyết định kỹ thuật phải tuân theo spec này.
- Khi nhận task mới: đọc lại section liên quan trước khi viết bất kỳ dòng code nào.
- Không tự ý thêm tính năng, thay đổi layout, hoặc dùng thư viện ngoài danh sách cho phép.
- Giải thích bằng tiếng Việt đơn giản khi cài package hoặc khi có lỗi.
- Trước mỗi `git commit`: chạy Superpower security check (xem Section 2b).
- Sau mỗi thay đổi UI có ý nghĩa: chạy Playwright E2E test liên quan (xem Section 21).

---

## 1. Tổng quan dự án

**Tên:** HG Lab — Stem-loop RT-qPCR Designer
**Mục đích khoa học:** Thiết kế tự động 3 loại primer cho phản ứng Stem-loop RT-qPCR dùng để định lượng mature miRNA. Phát triển từ phương pháp tiên phong của Chen et al. (2005), với các cải tiến về độ nhạy và tối ưu Tm.
**Người dùng:** Nhà nghiên cứu sinh học phân tử, không cần biết IT.
**Ngôn ngữ giao diện:** All UI text in English — labels, tooltips, error messages, warnings, info boxes, placeholders, and button text. No Vietnamese in the UI layer.

### Ba primer cần thiết kế (bối cảnh khoa học)

| Primer | Vai trò | Đặc điểm kỹ thuật |
|--------|---------|-------------------|
| Stem-loop RT primer | Phiên mã ngược, kéo dài miRNA từ ~22nt lên >60nt | Thân hairpin ~44nt + đầu thò 3' 6nt bổ sung với đầu 3' miRNA |
| Forward qPCR primer | Bắt cặp đầu 5' của cDNA, khuếch đại đặc hiệu | Phần đặc hiệu 10–12nt từ miRNA + đuôi 5' để nâng Tm lên 60°C |
| Universal reverse primer | Phá vỡ cấu trúc hairpin, dùng chung mọi assay | Chuỗi cải tiến: 5′-CCAGTGCAGGGTCCGAGGTA-3′ (20nt) |

---

## 2. Stack kỹ thuật (KHÔNG thay đổi)

### Frontend
```
React 18 + Vite 5 + Tailwind CSS 3
React Router DOM v6 (routing 3 tab)
Axios (gọi API backend)
```

### Backend
```
Python 3.11 + Flask 3 + flask-cors + requests
```

### Thư viện KHÔNG dùng
- Redux, Zustand, Context API phức tạp (dùng useState là đủ)
- React Hook Form, Formik (tự viết validation đơn giản)
- Ant Design, Material UI, Chakra UI (chỉ dùng Tailwind)

---

## 2b. Công cụ phát triển (Development Tooling)

### Superpower MCP
**Dùng khi nào:**
- Trước `git commit`: chạy security check để phát hiện hardcoded secrets, injection risk, auth bypass
- Khi debug lỗi phức tạp: dùng skill systematic-debugging
- Khi lên kế hoạch feature mới: dùng skill planning

```bash
claude mcp list  # kiểm tra: superpowers phải hiện ✔ Connected
```

### Playwright MCP
**Dùng khi nào:**
- Sau khi tạo xong một component hoặc page: chạy E2E test tương ứng
- Trước khi push lên GitHub: chạy toàn bộ test suite

```bash
claude mcp list  # kiểm tra: playwright phải hiện ✔ Connected
```

**Cấu trúc thư mục test:**
```
primer-designer/
└── e2e/
    ├── sequence-group.spec.js
    ├── detection-method.spec.js
    ├── experimental-context.spec.js
    ├── range-slider.spec.js
    ├── mirbase-lookup.spec.js
    └── form-submit.spec.js
```

---

## 3. Cấu trúc thư mục (bắt buộc đúng tên)

```
primer-designer/
├── SPEC_week1.md
├── README.md
├── CLAUDE.md
├── frontend/
│   ├── index.html                 ← title, meta description, favicon set
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── constants/
│       │   └── defaults.js
│       ├── hooks/
│       │   └── useMiRBase.js
│       ├── components/
│       │   ├── Navbar.jsx
│       │   ├── Footer.jsx
│       │   ├── ChatbotPanel.jsx
│       │   └── ui/
│       │       ├── Tooltip.jsx
│       │       ├── NumInput.jsx     ← MỚI: controlled number input với local state
│       │       ├── RangeSlider.jsx
│       │       └── Toggle.jsx
│       └── pages/
│           ├── HomePage.jsx
│           ├── RoadmapPage.jsx
│           └── SearchPage/
│               ├── index.jsx
│               ├── SequenceGroup.jsx
│               ├── ThermodynamicGroup.jsx
│               ├── PrimerConstraintsGroup.jsx
│               ├── QpcrConditionsGroup.jsx
│               ├── DetectionMethodGroup.jsx
│               └── ExperimentalContextGroup.jsx
└── backend/
    ├── app.py
    ├── requirements.txt
    ├── routes/
    │   └── mirbase.py           ← local DB first → miRBase API → RNAcentral fallback
    ├── db/
    │   ├── local_db.py          ← SQLite CRUD: init_schema, lookup, upsert (idempotent)
    │   ├── circuit_breaker.py   ← opens after 3 failures, resets after 60s
    │   └── mirbase.db           ← 95 curated entries (KHÔNG commit, xem .gitignore)
    └── scripts/
        ├── seed_db.py           ← 85 offline entries (human oncomiRs, let-7, clusters…)
        └── fetch_and_seed.py    ← fetch từ miRBase API / RNAcentral / --all flag
```

---

## 4. Màu sắc & Design Tokens

```js
// Teal — màu chủ đạo (brand color — dùng NHẤT QUÁN, không dùng blue cho UI chính)
teal = {
  50:  '#E1F5EE',   // bg chip, focus ring, hover
  200: '#5DCAA5',   // border nhẹ
  600: '#0F6E56',   // button gradient start, track fill, thumb
  700: '#0f766e',   // thumb hover, drag callout bg
  800: '#085041',   // button gradient end
}

// Amber — warning (scientific caution)
amber = {
  50:  '#FFFBEB',
  200: '#FCD34D',
  700: '#B45309',
}

// Red — error / invalid
red = {
  50:  '#FEF2F2',
  200: '#FECACA',
  400: '#F87171',
  600: '#DC2626',
}

// Gray — neutral
gray = {
  100: '#F3F4F6',
  200: '#E5E7EB',   // track empty, divider
  400: '#9CA3AF',
  500: '#6B7280',
  700: '#374151',
  900: '#111827',
}
```

### Typography chuẩn

| Phần tử | Class |
|---------|-------|
| Section title (CollapsibleSection) | `text-sm font-semibold text-gray-500` |
| Field label | `text-sm font-medium text-gray-700` |
| Input text | `text-sm text-gray-900` |
| Error message | `text-xs text-red-600` |
| Warning banner | `text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed` |
| Placeholder | `text-sm text-gray-400` |
| Unit suffix inside input | `text-xs text-gray-400` |
| Value badge (RangeSlider) | `text-xs text-teal-700 font-semibold px-2 py-0.5 rounded-md bg-teal-50 border border-teal-100 tabular-nums` |

> ⚠ **QUAN TRỌNG:** Không dùng `uppercase tracking-wider` cho section title — deprecated từ v3.0.
> ⚠ **QUAN TRỌNG:** Tất cả warning banners phải dùng cùng một class string (xem bảng trên). Không dùng `text-amber-600` trần.

---

## 5. Layout tổng thể

```
┌──────────────────────────────────────────────────────────────────┐
│ NAVBAR (height: 56px, border-bottom: 1px solid #E5E7EB)          │
│  [Logo 32px] HG Lab          [Home] [Roadmap] [Designer←active]  │
│             Stem-loop RT-qPCR Designer                            │
├──────────────────────────────────────────────┬───────────────────┤
│ MAIN CONTENT (flex-1, overflow-y: auto)      │ CHATBOT PANEL     │
│ padding: 24px                                │ width: 320px      │
│                                              │ (collapsed: 64px) │
├──────────────────────────────────────────────┴───────────────────┤
│ FOOTER (height: 36px)                                             │
│  HG Lab · Human Genetics Laboratory, HCMUS · v0.1.0-dev          │
│                            Contact: hglab.hcmus.edu.vn            │
└──────────────────────────────────────────────────────────────────┘
```

### Navbar chi tiết
```jsx
// Brand: logo 32px + "HG Lab" bold + subtitle "Stem-loop RT-qPCR Designer" teal nhỏ
// Nav tabs:
Tab thường:  px-4 py-1.5 rounded-lg text-sm font-medium text-gray-500 hover:text-teal-700 hover:bg-teal-50
Tab active:  px-4 py-1.5 rounded-lg text-sm font-semibold text-teal-700 bg-teal-50 border border-teal-200 shadow-sm
// Tab labels: Home | Roadmap | Designer  (KHÔNG dùng "Search")
```

### Chatbot Panel (collapsed/expanded)
```
Collapsed (w-16): chỉ hiện nút pill teal với robot icon + "AI"
Expanded (w-80):
  - Header: "AI Assistant" + badge "SOON"
  - Hero: robot icon lớn + mô tả + badge "In development"
  - Planned capabilities list (4 items với icon)
  - Disabled input area + note "Available after primer design engine is complete"
```

### Footer
```jsx
// Left: "HG Lab · Human Genetics Laboratory, HCMUS · v0.1.0-dev"
// Right: "Contact: hglab.hcmus.edu.vn" (link màu teal-600)
```

### Page titles (dynamic per route)
```js
HomePage:    document.title = 'HG Lab | Home'
RoadmapPage: document.title = 'HG Lab | Roadmap'
SearchPage:  document.title = 'HG Lab | Primer Designer'
// index.html base title: 'HG Lab | Stem-loop RT-qPCR Primer Designer'
// favicon: /logo.png
```

---

## 6. Constants — Giá trị mặc định (file: src/constants/defaults.js)

```js
export const DEFAULTS = {
  // Nhóm 1 — Sequence
  sequence: {
    mirbaseId: '',
    matureSequence: '',
    species: 'human',
    accession: '',
    family: '',
  },

  // Nhóm 2 — Thermodynamic (6 ionic/buffer parameters added v3.0)
  thermodynamic: {
    tmMin: 58,
    tmMax: 62,
    saltConcentration: 50,        // mM [Na+]
    primerConcentration: 250,     // nM
    magnesiumConcentration: 1.5,  // mM Mg2+ total
    dntpTotal: 0.2,               // mM total dNTP (chelates Mg2+)
    kPlusConc: 50,                // mM [K+] / KCl
    bufferPH: 8.4,                // Tris-HCl pH at 20°C
  },

  // Nhóm 3 — Primer Constraints
  primerConstraints: {
    gcMin: 40,
    gcMax: 60,
    lengthMin: 20,
    lengthMax: 24,
    gcClamp3prime: true,
    bindingRegion3prime: 6,       // KHÔNG đổi default này
  },

  // Nhóm 4 — qPCR Conditions
  qpcr: {
    annealingTemp: 60,
    ampliconMin: 60,
    ampliconMax: 150,
    totalCycles: 40,
    pcrEfficiencyMin: 90,
    pcrEfficiencyMax: 110,
  },

  // Nhóm 5a — Detection Method
  detectionMethod: {
    signalMethod: 'taqman',
    quantMode: 'relative',
    referenceGene: 'miR-16',
    customReferenceGene: '',
    enableFamilyDiscrimination: true,
    enablePrecursorCheck: false,
    enableRefoldingProtocol: true,
  },

  // Nhóm 5b — Experimental Context
  experimentalContext: {
    sampleType: 'tissue',
    qpcrSystem: 'other',
    rtEnzyme: 'mmlv',
    exportFormat: ['copy'],
  },
};

export const LIMITS = {
  thermodynamic: {
    tmMin: 50, tmMax: 70,
    saltMin: 1, saltMax: 500,
    primerConcMin: 50, primerConcMax: 1000,
    mgMin: 0.5, mgMax: 5.0,
    dntpMin: 0.05, dntpMax: 1.0,
    kPlusMin: 0, kPlusMax: 200,
    bufferPHMin: 7.0, bufferPHMax: 9.5,
  },
  primerConstraints: {
    gcMin: 20, gcMax: 80,
    lengthMin: 15, lengthMax: 35,
    bindingMin: 4, bindingMax: 8,
  },
  qpcr: {
    taMin: 50, taMax: 68,
    ampliconMin: 40, ampliconMax: 300,
    cyclesMin: 30, cyclesMax: 50,
    efficiencyMin: 80, efficiencyMax: 120,
  },
};
```

---

## 7. Trang Search — Form 6 nhóm (SearchPage)

### 7.1. State management

```jsx
const [formData, setFormData] = useState({
  sequence:             { ...DEFAULTS.sequence },
  thermodynamic:        { ...DEFAULTS.thermodynamic },
  primerConstraints:    { ...DEFAULTS.primerConstraints },
  qpcr:                 { ...DEFAULTS.qpcr },
  detectionMethod:      { ...DEFAULTS.detectionMethod },
  experimentalContext:  { ...DEFAULTS.experimentalContext },
});
const [errors, setErrors] = useState({});
const [isSubmitting, setIsSubmitting] = useState(false);
const [activeSection, setActiveSection] = useState('seq');
const [visitedSections, setVisitedSections] = useState(new Set());
const [resetKey, setResetKey] = useState(0);
const [sectionOpenRequests, setSectionOpenRequests] = useState({});
```

### 7.2. Mini navigation sidebar (xl+ screens)
- Sticky sidebar trái: 6 items (Sequence / Detection / Thermo. / Primer / qPCR / Context)
- Dot indicator: teal khi section đã visit, gray khi chưa
- Click nav item → expand section + scroll + mark visited
- Progress bar: `{readyCount}/{total} ready`

### 7.3. Layout của SearchPage
```
SearchPage
├── [SequenceGroup]           — Nhóm 1 (always open)
├── [DetectionMethodGroup]    — Nhóm 5a (quyết định algorithm)
├── [ThermodynamicGroup]      — Nhóm 2
├── [PrimerConstraintsGroup]  — Nhóm 3
├── [QpcrConditionsGroup]     — Nhóm 4
├── [ExperimentalContextGroup]— Nhóm 5b
└── [Submit button — STICKY BOTTOM]
```

---

## 8. Nhóm 1: SequenceGroup.jsx

### Giao diện

```
┌─ Sequence Information ──────────────── [tooltip ?] ─────────────┐
│  miRBase ID                                                       │
│  [hsa-miR-21-5p                    ] [Search ⟳]                 │
│  ✓ Found: Homo sapiens · Family: miR-21                          │
│                                                                   │
│  Mature miRNA sequence (5′→3′)                                   │
│  [UAGCUUAUCAGACUGAUGUUGA           ]                             │
│                                                                   │
│  Species                                                          │
│  [Human ▾]                                                       │
│                                                                   │
│  ℹ 22 nt · GC: 40.9% · 3′ end: UGA                             │
└───────────────────────────────────────────────────────────────────┘
```

### Field details

**miRBase ID field:**
- Placeholder: `e.g. hsa-miR-21-5p or MIMAT0000076`
- On Tab / Enter / Search button → call useMiRBase hook
- States: idle | loading | found | not_found | error

**Mature miRNA sequence:**
- textarea 2 rows, auto-uppercase
- Validation onBlur: empty, T→U error, invalid chars, <15nt, >30nt

**Info bar (shown when valid):**
```jsx
// "22 nt · GC: 40.9% · 3′ end: UGA"
// teal style: bg-teal-50 border border-teal-100 text-teal-700
```

---

## 9. Custom Hook: useMiRBase.js

```js
// States: 'idle' | 'loading' | 'found' | 'not_found' | 'error'
// Returns: { status, result, errorMessage, fetchMiRNA, reset }
// Endpoint: GET /api/mirbase/:id
// Tries ?accession= first, then ?name=
```

---

## 10. Nhóm 2: ThermodynamicGroup.jsx

### Giao diện

```
┌─ Thermodynamic Parameters ──────────────── [Reset] [?] ─────────┐
│                                                                   │
│  Melting temperature (Tm) range             [tooltip]            │
│  50°C ──[====58°──────────62°====]── 70°C                       │
│         [58°C]              [62°C]    ← badge chips              │
│                                                                   │
│  ── Buffer & Ionic Conditions ─────────────────────────────────  │
│                                                                   │
│  [Na+] / NaCl [?]  [K+] / KCl  [?]  [Mg2+] total  [?]          │
│  [50        ] mM   [50       ] mM    [1.5       ] mM            │
│                                                                   │
│  [dNTP] total [?]  [Primer]    [?]   Buffer pH     [?]           │
│  [0.2      ] mM   [250      ] nM    [8.4          ]              │
│                                                                   │
│  ┌ Effective free [Mg²⁺]: 1.30 mM (1.5 total − 0.2 dNTP) ⚠ ┐  │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  [Warning banners]                                                │
└───────────────────────────────────────────────────────────────────┘
```

### Ionic parameters (v3.0)

| Field | Default | Range | Unit | Validation error |
|-------|---------|-------|------|-----------------|
| [Na⁺] / NaCl | 50 | 1–500 | mM | Must be between 1 and 500 mM |
| [K⁺] / KCl | 50 | 0–200 | mM | Must be between 0 and 200 mM |
| [Mg²⁺] total | 1.5 | 0.5–5.0 | mM | Must be between 0.5 and 5.0 mM |
| [dNTP] total | 0.2 | 0.05–1.0 | mM | Must be between 0.05 and 1.0 mM |
| [Primer] | 250 | 50–1000 | nM | Must be between 50 and 1000 nM |
| Buffer pH | 8.4 | 7.0–9.5 | — | pH must be between 7.0 and 9.5 |

### Effective free [Mg²⁺] indicator
```
freeMg = max(0, mg_total − dNTP_total)
Colors:
  freeMg >= 1.5 mM → teal  "✓ Optimal (1.5–3 mM)"
  freeMg >= 1.0 mM → amber "⚠ Below optimal"
  freeMg <  1.0 mM → red   "✕ Insufficient"
```

### Warnings (English only, priority order)
1. `freeMgWarning` — free Mg²⁺ < 1.0 mM
2. `saltWarning` — Na⁺ < 20 mM or > 150 mM (với ΔTm estimate)
3. `kPlusWarning` — K⁺ > 75 mM (caution) or > 100 mM (inhibition)
4. `mgWarning` — Mg²⁺ < 1.0 mM (low) or > 3.5 mM (high)
5. `dntpWarning` — dNTP < 0.1 mM (very low) or > 0.4 mM (chelation)
6. `primerConcWarning` — < 100 nM or > 600 nM
7. `phWarning` — pH < 7.5 or > 9.0
8. `showCombinedIonicWarn` — Na⁺ > 100 AND Mg²⁺ > 3.0
9. `showFwdTmWarn` — Tm target deficit > 33°C vs. sequence

### Reset button — 2-step confirmation (v3.0)
```
Click 1: button → "Confirm reset?" (red bg, 2.5s timeout to auto-cancel)
Click 2: execute reset — restore all fields to DEFAULTS.thermodynamic
Timeout: auto-cancel after 2.5s, button returns to "Reset"
```

---

## 11. Nhóm 3: PrimerConstraintsGroup.jsx

### Giao diện

```
┌─ Primer Design Constraints ─────────────────────── [?] ─────────┐
│  GC content (%)                           [tooltip]              │
│  20% ──[======40%────────60%======]── 80%                       │
│                                                                   │
│  Primer length (nt)                       [tooltip]              │
│  15nt ──[=====20nt───────24nt=====]── 35nt                      │
│                                                                   │
│  3′ GC Clamp [?]        3′ Binding region [?]                   │
│  [●──────] ON           [6         ] nt                          │
└───────────────────────────────────────────────────────────────────┘
```

### Warnings (English only — all translated v3.0)
- Binding region ≠ 6 nt: "⚠ 6 nt is the validated standard..."
- GC clamp + A/U at 3' end: "⚠ Position 10–12 of the miRNA ends with A/U..."
- Homopolymer run ≥ 4 nt: "⚠ Sequence contains a homopolymer run..."
- GC < 30%: "⚠ AU-rich forward binding region ({x}% GC)..."
- GC > 70%: "⚠ GC-rich forward binding region ({x}% GC)..."

---

## 12. Nhóm 4: QpcrConditionsGroup.jsx

### Giao diện

```
┌─ qPCR Conditions ───────────────────────────────── [?] ─────────┐
│  Annealing temp (Ta)[?]  Total cycles [?]  PCR efficiency [?]   │
│  [60     ] °C            [40   ] cycles    [90]% → [110]%       │
│                                                                   │
│  Amplicon size                                                    │
│  40bp ──[===60────────150===]── 300bp                            │
└───────────────────────────────────────────────────────────────────┘
```

### Warnings (English only)
- Ta > tmMin + 5: "⚠ Ta should be 2–5°C below Tm to avoid mispriming."
- Cycles < 35: "⚠ Fewer than 35 cycles may be insufficient..."
- Cycles > 45: "⚠ Too many cycles increases the risk of non-specific amplification."
- Efficiency range > 25%: "⚠ A wide efficiency range will accept more low-quality primer candidates."

---

## 13. Nhóm 5a: DetectionMethodGroup.jsx

Always visible. Rendered immediately after Group 1.

```
┌─ Detection Method ──────────────────────────────── [?] ─────────┐
│  Signal detection                                                 │
│  (●) TaqMan probe      ( ) SYBR Green                           │
│                                                                   │
│  Quantification mode                                              │
│  ( ) Absolute          (●) Relative                             │
│                                                                   │
│  Reference gene [?]                                              │
│  [miR-16 ▾]   or enter custom: [              ]                 │
│                                                                   │
│  ── Advanced specificity options ──────────────────────────────  │
│  [✓] Penalize off-target in same miRNA family                   │
│  [ ] Check cross-reactivity with pre-miRNA                      │
│  [✓] Generate re-folding protocol in output                     │
└───────────────────────────────────────────────────────────────────┘
```

---

## 14. Nhóm 5b: ExperimentalContextGroup.jsx

```
┌─ Experimental Context ──────────────────────────── [?] ─────────┐
│  Sample type [?]              qPCR system [?]                    │
│  [Tissue ▾]                   [Other ▾]                         │
│                                                                   │
│  RT enzyme [?]                Export format                      │
│  [M-MLV ▾]                    [✓] Copy  [ ] PDF  [ ] CSV        │
└───────────────────────────────────────────────────────────────────┘
```

---

## 15. Shared component: NumInput.jsx (MỚI v3.0)

**Vấn đề giải quyết:** `<input type="number">` controlled với `value={someNumber}` — khi user xóa hết, `Number('') = 0`, state bị set về 0, field hiện "0" thay vì trống.

```jsx
// Props: id, label, tooltip, value, onChange, min, max, step, unit, error
// label là optional — nếu undefined thì không render label row
// onChange emits synthetic { target: { value: string } }

// Behavior:
// - Local raw string state, synced from value prop via useEffect
// - onFocus: e.target.select() — select all text on click
// - Khi raw === '' hoặc NaN: parent handler phải set error và return sớm
//   (không update parent state → parent giữ last valid number)
// - Khi reset từ ngoài: value prop thay đổi → useEffect sync raw
```

**Handler pattern chuẩn trong mọi component:**
```js
function handleXChange(e) {
  const str = e.target.value;
  const val = parseFloat(str);
  if (str === '' || isNaN(val)) {
    onError('fieldName', 'Error message...');
    return; // KHÔNG update parent state
  }
  onError('fieldName', val < min || val > max ? 'Error message...' : '');
  onChange('fieldName', val);
}
```

---

## 16. Shared component: RangeSlider.jsx

```jsx
// Props:
// - min, max: absolute limits
// - valueMin, valueMax: current values
// - step: default 1
// - unit: "°C" | "%" | "nt" | "bp"
// - label, tooltip: string (tooltip được render — không bỏ qua)
// - onChange: function(newMin, newMax)

// Behavior:
// - Track fill: teal-600 (#0d9488), không dùng blue
// - Thumbs: teal-600, hover teal-700
// - Value display: badge chip teal bên dưới (tabular-nums)
// - Drag callout: bubble teal-700 hiện phía trên thumb đang kéo
//   (onPointerDown set dragging state, onPointerUp clear)
// - Constraints: valueMin <= valueMax - step (thumbs không overlap)
// - Guard: if (max === min) range = 1 để tránh NaN trong gradient
```

---

## 17. Submit button — Sticky bottom (v3.0)

```jsx
// Vị trí: sticky bottom-0 bên trong main scroll container
// Background: gradient fade from-white from-70% via-white/90 to-transparent
// z-index: 10

// States:
// 1. Ready:   teal gradient, "Design Primers →"
// 2. Errors:  gray bg, "✕ Fix errors to continue", cursor-not-allowed
// 3. Loading: gray bg, "⟳ Processing…" (spin animation)

// Below button (khi isSeqReady && !hasErrors):
// "Stem-loop primer · Forward primer · Universal reverse primer"
```

---

## 18. CollapsibleSection.jsx — quy tắc

```jsx
// Title style: text-sm font-semibold text-gray-500 (KHÔNG uppercase)
// Arrow: Unicode ▸ (rotate 90° khi open) — màu teal-600
// Status dots (khi collapsed):
//   - Error: w-1.5 h-1.5 rounded-full bg-red-500
//   - Warning: w-1.5 h-1.5 rounded-full bg-amber-400
// Animation: grid-template-rows transition (0fr ↔ 1fr)
// onFirstOpen: fired once on first expand, dùng để mark section visited
// openRequested: increment để trigger open từ mini-nav
```

---

## 19. Backend Flask

### File: backend/app.py

```python
from flask import Flask
from flask_cors import CORS
from routes.mirbase import mirbase_bp

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://localhost:3000"]}})
app.register_blueprint(mirbase_bp, url_prefix='/api')

@app.route('/api/health')
def health():
    return {"status": "ok", "message": "Backend is running", "version": "2.0.0"}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

### File: backend/routes/mirbase.py

```python
# GET /api/mirbase/<mirna_id>
# Request flow (3 tiers):
#   1. Local SQLite DB (local_db.lookup) — zero latency, Homo sapiens prioritized
#   2. miRBase REST API (nếu circuit breaker closed)
#      - Tries ?accession= first (MIMAT…), then ?name=
#   3. RNAcentral fallback (nếu miRBase fails hoặc circuit breaker open)
# Returns: { id, accession, sequence, family, species, length }
# HTTP errors: 400 (invalid input), 404 (not found), 503 (connection), 504 (timeout)
# Note: khi miRBase.org down → circuit breaker kích hoạt → invalid IDs trả 504, không phải 404
```

### File: backend/db/local_db.py

```python
# init_schema()  — idempotent, gọi khi app start
# lookup(mirna_id) → dict | None
#   ORDER BY CASE: Homo sapiens ưu tiên hơn các species khác
# upsert(record)  — INSERT OR REPLACE
```

### File: backend/db/circuit_breaker.py

```python
# check() → tuple[bool, int]  — atomic: (is_open, failure_count)
# is_open property             — delegate to check()
# record_failure()             — +1 failure; nếu >= 3 → open
# record_success()             — reset failure count
# Cooldown: 60s sau lần failure cuối → tự reset sang closed
```

### File: backend/scripts/seed_db.py

```python
# 85 offline entries không cần internet:
# - Human oncomiRs: miR-21, miR-155, miR-210, miR-221/222, miR-31, miR-200 family
# - let-7 family: let-7a/b/c/d/e/f/g/i
# - miR-17-92 cluster: miR-17/18a/19a/19b/20a/92a
# - Cardiac: miR-1-3p, miR-133a/b, miR-208a/b
# - Liver: miR-122-5p, miR-192-5p
# - Immune: miR-146a, miR-223-3p
# - Circulating: miR-16-5p, miR-451a
# - Mouse orthologs: mmu-miR-21-5p, mmu-let-7a-5p, mmu-miR-122-5p
# - Rat orthologs: rno-miR-21-5p, rno-miR-155-5p
```

### File: backend/scripts/fetch_and_seed.py

```python
# Usage:
#   python scripts/fetch_and_seed.py hsa-miR-21-5p MIMAT0000076
#   python scripts/fetch_and_seed.py --file my_mirnas.txt
#   python scripts/fetch_and_seed.py --all   # full ~38k entries từ mature.fa.gz
#
# Fallback chain: miRBase API → RNAcentral
# RNAcentral species parsing: regex r'\bfrom\s+([A-Z][a-z]+ [a-z]+)' (đã fix v3.1)
```

### File: backend/requirements.txt
```
flask==3.0.3
flask-cors==4.0.1
requests==2.31.0
```

---

## 20. Tooltip.jsx — quy tắc

```jsx
// aria-label: "More information" (English only)
// Show delay: 250ms (clearTimeout on mouseleave)
// Keyboard focus: show immediately (no delay)
// Position: right side by default, flip to left if < 290px to viewport edge
// Renders into document.body via createPortal (position: fixed)
// Style: bg-white border border-gray-200 text-gray-700 shadow-xl rounded-xl
```

---

## 21. Test cases đầy đủ

### Test miRBase API
```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/mirbase/hsa-miR-21-5p   # → UAGCUUAUCAGACUGAUGUUGA
curl http://localhost:5000/api/mirbase/MIMAT0000076     # same
curl http://localhost:5000/api/mirbase/hsa-miR-16-5p   # → UAGCAGCACGUAAAUAUUGGCG
curl http://localhost:5000/api/mirbase/hsa-let-7a-5p
curl http://localhost:5000/api/mirbase/invalid-id-xyz   # → 404
```

### Test Form & UI
```
Test 1  — NumInput clear: xóa hết số → field trống, không hiện "0"
Test 2  — NumInput focus: click vào ô số → text được select all
Test 3  — Reset 2-step: click Reset → "Confirm reset?" → click lại → reset
Test 4  — Reset cancel: click Reset → chờ 2.5s → tự huỷ về "Reset"
Test 5  — Sticky button: scroll xuống giữa form → button vẫn hiện dưới màn hình
Test 6  — Error state button: nhập giá trị lỗi → button hiện "✕ Fix errors to continue"
Test 7  — Tooltip delay: di chuột nhanh qua icon → không flash, phải dừng 250ms
Test 8  — RangeSlider drag callout: kéo thumb → bubble hiện giá trị phía trên
Test 9  — Tm slider: kéo min/max, thumbs không overlap
Test 10 — Mg²⁺ chelation: nhập Mg=1.5, dNTP=0.8 → freeMg=0.7 → red indicator
Test 11 — K⁺ warning: nhập K+=80 → warning "upper recommended limit"
Test 12 — pH warning: nhập pH=7.2 → warning về polymerase activity
Test 13 — miRBase lookup: nhập hsa-miR-21-5p → Tab → sequence auto-fill
Test 14 — TaqMan/SYBR toggle → info box thay đổi đúng
Test 15 — Sample type Serum → preset banner → Apply → Group 4 values update
Test 16 — Page title: navigate Home/Roadmap/Designer → browser tab title đúng
Test 17 — Warning style: tất cả warning banners cùng bg-amber-50 rounded-lg
```

---

## 22. README.md

```markdown
# HG Lab: Stem-loop RT-qPCR Primer Designer

Automated primer design tool for Stem-loop RT-qPCR miRNA quantification.

## Requirements
- Node.js 20+
- Python 3.11+
- Internet connection (for miRBase API)

## Running (open 2 terminals)

### Terminal 1 — Backend
cd primer-designer/backend
pip install -r requirements.txt
python app.py          # → http://localhost:5000

### Terminal 2 — Frontend
cd primer-designer/frontend
npm install
npm run dev            # → http://localhost:5173

## Quick check
1. Open http://localhost:5173 → tab title "HG Lab | Primer Designer"
2. Click Designer tab
3. Enter hsa-miR-21-5p → Tab → sequence auto-fills
4. Select TaqMan or SYBR Green → observe info box change

## Contact
https://hglab.hcmus.edu.vn
```

---

## 23. Definition of "Week 1 complete"

> **STATUS: ✅ HOÀN THÀNH** — Verified 2026-06-20

**Required 100%:**
- [x] `python app.py` runs without error, port 5000
- [x] `npm run dev` runs without error, port 5173
- [x] Browser tab: "HG Lab | Primer Designer" on Designer page
- [x] Navbar: "HG Lab" brand + teal color, tab "Designer" active
- [x] Layout correct: navbar + main + chatbot panel + footer
- [x] Footer: lab name + version + teal link  *(v0.1.0-dev — user added manually)*
- [x] Tab switching works, page titles update
- [x] All 6 form groups display with correct default values
- [x] RangeSlider: teal track/thumb, drag callout bubble, tooltips visible
- [x] RangeSlider: thumbs do not overlap
- [x] NumInput: click → select all; clear → empty field (not "0")
- [x] miRBase ID → Tab → sequence auto-fills (hsa-miR-21-5p → UAGCUUAUCAGACUGAUGUUGA)
- [x] Sequence validation: T character → "Character 'T' detected. use 'U' instead of 'T'"
- [x] ThermodynamicGroup: 6 ionic/buffer parameters display correctly
- [x] Effective free [Mg²⁺] indicator changes color correctly
- [x] All warnings display in English, consistent amber style
- [x] Reset button: 2-step confirmation (Confirm reset? → execute)
- [x] Submit button: sticky at bottom, shows "Fix errors" state when errors exist
- [x] TaqMan/SYBR radio → info box changes correctly
- [x] Relative/Absolute radio → reference gene field shows/hides
- [x] Sample type Serum → preset suggestion banner
- [x] Design Primers → spinner → console.log shows all 6 groups

**Nice to have:**
- [ ] Tooltips complete for all fields
- [ ] Responsive on tablet at 768px
- [ ] Error boundary (friendly crash page)

**Not in week 1:**
- Primer calculation algorithm (weeks 2–3)
- Family discrimination scoring (week 3)
- Real results page (week 4)
- Real AI chatbot (later)
- Real PDF/CSV export (later)
- Server deployment (optional)

### Bugs fixed trong Week 1
| Bug | Mô tả | File | Fix |
|-----|-------|------|-----|
| Bug 2 | Tab key không trigger miRBase search | SequenceGroup.jsx:148 | `e.key === 'Tab'` thêm vào onKeyDown |
| Bug 3 | T validation là dead code (regex `[AUGCU]+` bỏ T) | SequenceGroup.jsx:10 | Đổi regex thành `[AUGCUT]+` |
| Bug DB | RNAcentral species parse sai ("ncRNA from" thay vì "Homo sapiens") | fetch_and_seed.py:96 | Regex `r'\bfrom\s+([A-Z][a-z]+ [a-z]+)'` |

### Trạng thái database (2026-06-20)
- 95 entries trong SQLite (`backend/db/mirbase.db`)
- 85 từ seed_db.py (offline, curated) + 10 từ RNAcentral fallback
- miRBase.org đang DOWN — khi online chạy `python scripts/fetch_and_seed.py --all` để seed ~38k entries
- DB không commit vào git (xem `.gitignore`)

---

## 24. Changelog

| Version | Ngày | Thay đổi chính |
|---------|------|----------------|
| v1.0 | — | Initial spec: 4 nhóm input cơ bản |
| v2.0 | — | +DetectionMethodGroup, +ExperimentalContextGroup, +Mg²⁺ param |
| v3.0 | 2026-06-20 | +6 ionic/buffer params (dNTP, K⁺, pH), NumInput component, UI/UX polish toàn bộ: teal color system, sticky submit, reset confirmation, drag callout, tooltip delay, warning style unification, English-only UI |
| v3.1 | 2026-06-20 | **Week 1 HOÀN THÀNH.** +Backend SQLite cache (local_db.py) với 95 entries; +Circuit breaker (circuit_breaker.py, 3 failures → open, 60s cooldown); +seed_db.py (85 offline curated entries); +fetch_and_seed.py với RNAcentral fallback; Fix Bug 2 (Tab trigger), Bug 3 (T validation dead code), Bug DB (RNAcentral species parse); Cập nhật folder structure, checklist 22/22 PASS |

---

## 25. Week 2 — Kế hoạch (chưa bắt đầu)

> Bắt đầu sau khi Section 23 hoàn thành ✅

### Mục tiêu Week 2: Thuật toán thiết kế primer

**Primer 1 — Stem-loop RT primer**
```
Cấu trúc: 5'-[stem-loop hairpin ~44nt]-[binding tail 6nt]-3'
Binding tail: bổ sung (reverse complement) với 6nt cuối 3' của miRNA
Hairpin stem: ~6bp, loop: ~4nt
```

**Primer 2 — Forward qPCR primer**
```
Cấu trúc: 5'-[tail để nâng Tm]-[phần đặc hiệu 10–12nt từ 5' miRNA]-3'
Phần đặc hiệu: bắt đầu từ nt 1 của miRNA
Tail: thiết kế để đạt Tm target (từ ThermodynamicGroup)
```

**Primer 3 — Universal reverse primer (cố định)**
```
5'-CCAGTGCAGGGTCCGAGGTA-3'  (20nt, không thay đổi)
```

**Tm calculation:**
- Nearest-neighbor thermodynamics (SantaLucia 1998)
- Corrected for salt: SantaLucia salt correction formula
- Input: Na⁺, K⁺, Mg²⁺, dNTP, primer concentration từ ThermodynamicGroup

**Output (ResultsPage):**
- 3 primer sequences với Tm, GC%, length
- Amplicon size estimate
- Warnings nếu có vấn đề với primer quality

**API endpoint mới:**
```
POST /api/design
Body: { sequence, thermodynamic, primerConstraints, qpcr, detectionMethod, experimentalContext }
Response: { rt_primer, fwd_primer, rev_primer, amplicon_size, warnings }
```
