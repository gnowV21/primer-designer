# SPEC_week1 — Patch Notes v3.2
# Những thay đổi cần áp dụng vào SPEC_week1.md để đồng bộ với SPEC_phase2 v2.6
# Áp dụng bằng cách chỉnh sửa trực tiếp SPEC_week1.md theo hướng dẫn bên dưới

---

## Tổng quan: 4 loại thay đổi

| Loại | Số lượng | Mức độ ảnh hưởng |
|------|----------|-----------------|
| BUG FIX — giá trị sai trong defaults.js | 3 | CRITICAL — sẽ làm thuật toán tính Tm sai |
| Thêm field còn thiếu trong defaults.js | 4 | HIGH — thuật toán cần nhưng form chưa gửi |
| Cập nhật Section 25 (Week 2 plan) | 1 | MEDIUM — tài liệu hóa rõ hơn |
| Thêm Section 26 (Data contract) | 1 | HIGH — spec hóa đúng cấu trúc POST body |

---

## THAY ĐỔI 1 — BUG FIX CRITICAL: dntpTotal trong defaults.js

**Vị trí:** Section 6, `DEFAULTS.thermodynamic`

**Hiện tại:**
```js
dntpTotal: 0.2,   // mM total dNTP (chelates Mg2+)
```

**Phải là:**
```js
dntpTotal: 0.8,   // mM total dNTP — tổng 4 loại (4 × 0.2 mM)
// BUG FIX v3.2: 0.2 là nồng độ MỖI LOẠI, không phải tổng
// Primer3 dùng giá trị này trong: [Na+_eq] = [Na+] + 120×√([Mg2+] - [dNTP])
// Nếu dNTP=0.2: sqrt(1.5-0.2)=1.14 → sai
// Đúng: sqrt(1.5-0.8)=0.84 → Tm chênh ~1.5°C
// Nguồn: P3P General Settings + IDT "0.8 mM dNTPs" + Koressaar & Remm 2007
```

**Cũng cần cập nhật LIMITS.thermodynamic:**
```js
dntpMin: 0.4, dntpMax: 2.0,   // range cho tổng 4 loại (từ 0.05×4 đến 1.0×4 → thực tế 0.4–2.0)
// Hoặc giữ nguyên dntpMin: 0.05, dntpMax: 1.0 nếu muốn represent per-species
// NHƯNG phải document rõ: đây là total hay per-species
```

**Thêm vào LIMITS với label rõ ràng:**
```js
dntpMin: 0.2,   // mM minimum total (khuyến nghị: ≥ 0.4 để đủ cho PCR)
dntpMax: 2.0,   // mM maximum total (4 × 0.5 mM = 2.0 mM total)
```

---

## THAY ĐỔI 2 — BUG FIX: primerConcentration default

**Vị trí:** Section 6, `DEFAULTS.thermodynamic`

**Hiện tại:**
```js
primerConcentration: 250,   // nM
```

**Phải là:**
```js
primerConcentration: 200,   // nM — empirical annealing concentration
// Cập nhật v3.2: theo IDT PrimerQuest default = 200 nM
// P3P General Settings: ANNEALING Oligo Concentration = 50 nM
// NOTE: đây KHÔNG phải concentration trong reaction mix (xem tooltip)
// IDT 200 nM gần với thực tế qPCR hơn P3P 50 nM
```

**Cập nhật tooltip trong ThermodynamicGroup.jsx:**
```
"Empirical annealing oligo concentration used for Tm calculation.
 Not the actual primer concentration in the reaction mix.
 Default: 200 nM (IDT PrimerQuest). Range: 50–1000 nM."
```

---

## THAY ĐỔI 3 — BUG FIX: lengthMax trong primerConstraints

**Vị trí:** Section 6, `DEFAULTS.primerConstraints`

**Hiện tại:**
```js
lengthMin: 20,
lengthMax: 24,
```

**Phải là:**
```js
lengthMin: 20,
lengthMax: 27,   // P3P General Settings Max:27 (từ 24 → 27)
// Nguồn: P3P General Settings Primer Size Max=27
// IDT: 18–30 bases, nhưng P3P default Max=27 là conservative hơn
// SPEC_phase2 FORWARD_MAX_LENGTH = 27
```

**Cũng cập nhật LIMITS.primerConstraints:**
```js
lengthMin: 15, lengthMax: 27,   // max từ 35 → 27 để align với P3P
```

---

## THAY ĐỔI 4 — THÊM MỚI: userLevel vào experimentalContext

**Vị trí:** Section 6, `DEFAULTS.experimentalContext`

**Hiện tại:**
```js
experimentalContext: {
  sampleType: 'tissue',
  qpcrSystem: 'other',
  rtEnzyme: 'mmlv',
  exportFormat: ['copy'],
},
```

**Phải là:**
```js
experimentalContext: {
  sampleType: 'tissue',
  qpcrSystem: 'other',
  rtEnzyme: 'mmlv',
  exportFormat: ['copy'],
  userLevel: 'advanced',   // 'beginner' | 'advanced' — MỚI
},
```

---

## THAY ĐỔI 5 — THÊM MỚI: computed fields vào formData

**Vị trí:** Section 7.1 (State management)

Thêm 2 computed fields vào state — những giá trị này được tính từ input nhưng
cần gửi kèm trong POST /api/design để thuật toán dùng trực tiếp:

```jsx
// Thêm vào SearchPage/index.jsx

// Computed fields — tính real-time từ formData, gửi kèm POST body
const computedFields = useMemo(() => {
  const mg = formData.thermodynamic.magnesiumConcentration;
  const dntp = formData.thermodynamic.dntpTotal;
  const freeMg = Math.max(0, mg - dntp);

  // Na+ equivalent theo Owczarzy 2004 + SantaLucia 1998
  // [Na+_eq] = [Na+] + 120 × sqrt([Mg2+] - [dNTP])  (khi Mg2+ > dNTP)
  const naEq = dntp < mg
    ? formData.thermodynamic.saltConcentration + 120 * Math.sqrt(mg - dntp)
    : formData.thermodynamic.saltConcentration;

  return {
    freeMagnesium: parseFloat(freeMg.toFixed(3)),     // mM — free Mg2+ sau chelation
    naEquivalent: parseFloat(naEq.toFixed(2)),         // mM — Na+ equivalent cho Tm calc
  };
}, [formData.thermodynamic]);
```

**Gửi trong POST body:**
```jsx
const handleSubmit = async () => {
  const postBody = {
    ...formData,
    _computed: computedFields,   // backend dùng trực tiếp, không cần tính lại
  };
  const resp = await axios.post(`${API_BASE}/api/design`, postBody);
};
```

---

## THAY ĐỔI 6 — CẬP NHẬT Section 25: Week 2 Plan

**Vị trí:** Section 25 — thay toàn bộ nội dung

**Thay thế bằng:**

```markdown
## 25. Week 2 — Thuật toán thiết kế primer (SPEC_phase2 v2.6)

> Bắt đầu sau khi Section 23 hoàn thành ✅
> Tham chiếu đầy đủ: SPEC_phase2.md v2.6

### Mục tiêu Week 2
Implement backend thuật toán. Frontend chỉ thay đổi minimal (handleSubmit gọi API thật).

### Thư viện cần cài (thêm vào requirements.txt)
```
primer3-py==2.0.3    # Tm nearest-neighbor SantaLucia 1998, hairpin/dimer ΔG
ViennaRNA==2.6.4     # MFE của stem-loop hairpin (RNA.fold)
biopython==1.83      # sequence utilities
numpy==1.26.4        # scoring calculations
```

### POST /api/design — Data contract

**Frontend gửi:**
```json
{
  "sequence": {
    "matureSequence": "UAGCUUAUCAGACUGAUGUUGA",
    "mirbaseId": "hsa-miR-21-5p",
    "species": "human",
    "accession": "MIMAT0000076",
    "family": "miR-21"
  },
  "thermodynamic": {
    "tmMin": 58, "tmMax": 62,
    "saltConcentration": 50,
    "primerConcentration": 200,
    "magnesiumConcentration": 1.5,
    "dntpTotal": 0.8,
    "kPlusConc": 50,
    "bufferPH": 8.4
  },
  "primerConstraints": {
    "gcMin": 40, "gcMax": 60,
    "lengthMin": 20, "lengthMax": 27,
    "gcClamp3prime": true,
    "bindingRegion3prime": 6
  },
  "qpcr": {
    "annealingTemp": 60,
    "ampliconMin": 60, "ampliconMax": 150,
    "totalCycles": 40,
    "pcrEfficiencyMin": 90, "pcrEfficiencyMax": 110
  },
  "detectionMethod": {
    "signalMethod": "taqman",
    "quantMode": "relative",
    "referenceGene": "miR-16",
    "customReferenceGene": "",
    "enableFamilyDiscrimination": true,
    "enablePrecursorCheck": false,
    "enableRefoldingProtocol": true
  },
  "experimentalContext": {
    "sampleType": "tissue",
    "qpcrSystem": "other",
    "rtEnzyme": "mmlv",
    "exportFormat": ["copy"],
    "userLevel": "advanced"
  },
  "_computed": {
    "freeMagnesium": 0.7,
    "naEquivalent": 150.42
  }
}
```

**Backend trả về (Top 3):**
```json
{
  "top3": [
    {
      "rank": 1,
      "total_score": 88.4,
      "grade": "Excellent",
      "forward_primer": {
        "sequence": "ACACTCCTAGCTTATCAGACTGATG",
        "length": 25,
        "tm_full": 60.1,
        "tm_binding": 34.8,
        "gc_percent": 48.0,
        "amplicon_size": 68
      },
      "structure_checks": {
        "hairpin": { "dg": -1.2, "pass": true, "severity": "safe" },
        "self_dimer": { "dg_3prime": -2.0, "pass_3prime": true },
        "hetero_dimer": { "dg_3prime": -1.8, "pass": true },
        "end_stability": { "stability_kcal_mol": 4.2, "pass": true }
      },
      "scores": {
        "tm_accuracy": 97.5,
        "tm_binding_accuracy": 88.6,
        "gc_content": 90.0,
        "mfe_stemloop": 82.5,
        "hairpin_penalty": 100,
        "dimer_penalty": 100,
        "end_stability": 100,
        "primer_size": 100,
        "amplicon_size": 96.0,
        "tm_pair_match": 97.0
      },
      "explanations": { "...": "..." }
    }
  ],
  "stemloop_rt": {
    "sequence": "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTCAACA",
    "mfe": -11.4,
    "gc_percent": 52.0,
    "refolding_protocol": { "...": "..." }
  },
  "universal_reverse": {
    "sequence": "CCAGTGCAGGGTCCGAGGTA",
    "tm": 60.4,
    "gc_percent": 65.0
  },
  "metadata": {
    "elapsed_seconds": 3.8,
    "candidates_generated": 42,
    "rejection_summary": { "tm_out_of_range": 10, "gc_out_of_range": 6 }
  }
}
```

### Mapping formData → thuật toán (xem SPEC_phase2 Section 4 constants.py)

| formData field | SPEC_phase2 constant | Dùng trong |
|----------------|---------------------|------------|
| `thermodynamic.saltConcentration` | `P3_DEFAULT_MV_CONC` | calc_tm(), calc_hairpin() |
| `thermodynamic.magnesiumConcentration` | `P3_DEFAULT_DV_CONC` | calc_tm(), divalent correction |
| `thermodynamic.dntpTotal` | `P3_DEFAULT_DNTP_CONC` | divalent correction formula |
| `thermodynamic.primerConcentration` | `P3_DEFAULT_DNA_CONC` | calc_tm() |
| `_computed.freeMagnesium` | trực tiếp, không cần tính lại | check Mg²⁺ warnings |
| `_computed.naEquivalent` | `na_eq` trong Tm formula | salt correction |
| `primerConstraints.bindingRegion3prime` | `OVERHANG_LENGTH_DEFAULT` (=6) | stemloop_rt.py |
| `primerConstraints.lengthMax` | `FORWARD_MAX_LENGTH` (=27) | forward_primer.py prefilter |
| `primerConstraints.gcClamp3prime` | check GC_CLAMP_MIN_IN_LAST3 | prefilter |
| `qpcr.annealingTemp` | `TM_ANNEALING_TEMP_DEFAULT` | structure_check temp |
| `detectionMethod.signalMethod` | `PROBE_POSITION` logic | Phase 4 TaqMan |
| `detectionMethod.enableRefoldingProtocol` | flag cho output | stemloop_rt output |
| `experimentalContext.sampleType` | `SAMPLE_TYPE_PRESETS` | amplicon adjust |
| `experimentalContext.rtEnzyme` | `RT_ENZYME_NOTES` | output protocol |

### Parameters không thay đổi (hardcoded trong thuật toán)
Các giá trị sau là constants khoa học, KHÔNG lấy từ form:

| Constant | Giá trị | Lý do hardcode |
|----------|---------|----------------|
| `STEMLOOP_BODY` | "GTCGTATCCAGTGCAGGGTCC..." (44nt) | Chen et al. 2005 — cố định |
| `UNIVERSAL_REVERSE` | "CCAGTGCAGGGTCCGAGGTA" (20nt) | Cố định — universal |
| `MFE_STEMLOOP_MIN` | -13.0 kcal/mol | Scientific sweet spot [R2] |
| `MFE_STEMLOOP_MAX` | -10.0 kcal/mol | Scientific sweet spot [R2] |
| `HAIRPIN_DG_MAX_INTERNAL` | -3.0 kcal/mol | qPCR consensus |
| `SELF_DIMER_DG_MAX` | -6.0 kcal/mol | IDT OligoAnalyzer |
| `END_STABILITY_MAX` | 9.0 kcal/mol | P3P Advanced Settings |
| `GC_MAX_IN_3PRIME_WINDOW` | 5 | P3P Advanced Settings |
| `MAX_HOMOPOLYMER_RUN` | 5 | P3P Advanced Settings Max Poly-X |
| `GC_CLAMP_MIN_IN_LAST3` | 2 | IDT PrimerQuest |
| `FORWARD_MAX_LENGTH` | 27 | P3P General Settings Max:27 |
| `FORWARD_SPECIFIC_LENGTHS` | [10, 11, 12] | Report 2 |
| `CANDIDATES_TOP_N` | 3 | Yêu cầu dự án |
| `OUTPUT_BASE_INDEX` | 1 | P3P 1-based convention |

### Cần thêm vào Test cases (Section 21)
```
Test 18 — dNTP default: kiểm tra DEFAULTS.thermodynamic.dntpTotal === 0.8
Test 19 — primerConc default: kiểm tra DEFAULTS.thermodynamic.primerConcentration === 200
Test 20 — lengthMax default: kiểm tra DEFAULTS.primerConstraints.lengthMax === 27
Test 21 — computed freeMg: Mg=1.5, dNTP=0.8 → freeMg=0.7
Test 22 — computed naEq: Na=50, Mg=1.5, dNTP=0.8 → naEq ≈ 150.4 mM
Test 23 — POST body structure: submit form → verify _computed exists in POST body
Test 24 — POST /api/design: response có top3 array với 3 items
Test 25 — Top 3 scores: rank 1 score > rank 2 > rank 3
Test 26 — Stemloop overhang: hsa-miR-21-5p → overhang_rc = "TCAACA"
```
```

---

## THAY ĐỔI 7 — THÊM Section 26: Changelog update

**Thêm dòng vào cuối bảng Changelog (Section 24):**

```markdown
| v3.2 | — | **Sync với SPEC_phase2 v2.6.** BUG FIX: dntpTotal 0.2→0.8 (tổng 4 loại); primerConcentration 250→200nM (IDT PrimerQuest); lengthMax 24→27 (P3P General Settings). Thêm: userLevel vào experimentalContext; computed freeMagnesium + naEquivalent gửi trong POST body; Section 25 cập nhật đầy đủ data contract + mapping table với SPEC_phase2 |
```

---

## Tóm tắt thứ tự áp dụng

1. Sửa `dntpTotal: 0.2 → 0.8` trong DEFAULTS.thermodynamic ← CRITICAL nhất
2. Sửa `primerConcentration: 250 → 200` trong DEFAULTS.thermodynamic
3. Sửa `lengthMax: 24 → 27` trong DEFAULTS.primerConstraints và LIMITS
4. Thêm `userLevel: 'advanced'` vào DEFAULTS.experimentalContext
5. Thêm `computedFields` useMemo vào SearchPage/index.jsx
6. Thêm `_computed` vào POST body trong handleSubmit
7. Thay toàn bộ Section 25 bằng nội dung mới
8. Thêm dòng v3.2 vào bảng Changelog Section 24
9. Thêm Test 18–26 vào Section 21
