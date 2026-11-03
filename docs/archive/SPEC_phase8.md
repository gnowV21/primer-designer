# SPEC_phase8.md — HG Lab Stem-loop RT-qPCR Primer Designer
# Phase 8: Batch design · LNA Tm calculator · Session history
# Phiên bản 1.1 — 2026-07-04 · Sync: SPEC_algorithm v3.1, SCORING_WEIGHTS_V4, SPEC_phase3/4/6, RESEARCH_QUESTIONS_UX A1/A2 + C1

---

## CHANGELOG

### v1.1 — 2026-07-04 — Scientific corrections (PART B model)
Review khoa học phát hiện 3 lỗi nhiệt động học + 4 cải thiện độ chính xác trong PART B (LNA). Batch/History không đổi.

| # | Sửa | Loại | Section |
|---|---|---|---|
| 1 | **Doublet-based NN model:** mỗi LNA sửa **2 doublet** kề (5' và 3'), KHÔNG phải "sum theo position". v1.0 công thức `Σ ΔΔH(positions)` sai → Tm lệch systematic. | Lỗi | §B.3 |
| 2 | **Mô hình hợp nhất per-doublet:** SantaLucia98 (DNA-DNA) + McTigue04 (1 LNA) + Owczarzy11 (LNA-LNA) là MỘT computation, chọn nguồn param **per doublet**. Bỏ nhánh logic `method="single/consecutive/mixed"`; `method` chỉ còn metadata ghi bộ param đã chạm. | Lỗi | §B.3, §B.4 |
| 3 | **ΔTm nội nhất quán:** `lna_tm.py` tự tính CẢ `tm_dna` (LNA positions rỗng) VÀ `tm_lna` bằng **cùng NN engine**. ΔTm = hiệu hai giá trị cùng engine → phản ánh hiệu ứng LNA thuần, không nhiễm chênh lệch primer3↔custom. Convention C_T/x khớp primer3 (x=4). | Lỗi | §B.3, §B.4 |
| 4 | **LNA discrimination mode (giá trị cao nhất):** `suggest_lna_positions(mode="discrimination")` nối `family_crossreactivity` — đặt LNA đúng vị trí mismatch vs HIGH-risk sibling → tối đa hóa ΔΔG(match−mismatch). Đây là ứng dụng LNA khoa học nhất cho bài toán phân biệt family 1 nt. **On-demand** (user bấm). | Bổ sung | §B.4a |
| 5 | **Caveat salt correction:** McTigue/Owczarzy đo ở ~100 mM Na⁺; ΔΔ là differential (ít phụ thuộc salt) nhưng salt-dependence của LNA ≠ DNA → điều kiện xa 100 mM kém chính xác. Ghi rõ. | Document | §B.3, §5 |
| 6 | **Greedy + exhaustive fallback:** search space nhỏ (C(17,≤4) ~ vài nghìn) → chạy exhaustive khi khả thi; greedy cho case lớn. Note cooperativity (consecutive LNA không cộng tuyến tính). | Cải thiện | §B.4 |
| 7 | **3' terminal LNA → warning có citation, không hard-skip:** concern là polymerase extension efficiency, không tuyệt đối cấm. Đổi từ mặc định skip → configurable warning. | Chỉnh | §B.4, §B.5 |

### v1.0 — 2026-07-04 — Phase 8 khởi tạo
- **Mục tiêu:** Scientific completeness (không phải production deployment). Ba module bổ sung năng lực thiết kế, không đổi thuật toán lõi.
- **PART A — Batch design mode (A1):** panel qPCR 5–20 miRNA cùng lúc. Hybrid: ≤10 synchronous streaming (NDJSON), >10 async job + polling (reuse BLAST job pattern).
- **PART B — LNA Tm calculator (A2):** McTigue 2004 (single LNA) base + Owczarzy 2011 (consecutive LNA). Áp dụng forward + reverse (DNA:DNA). RT overhang (DNA:RNA) → future-work với caveat rõ.
- **PART C — Session history (C1):** IndexedDB (dung lượng lớn cho batch >20 kết quả). Export/import → future-work.
- **Quyết định (chốt với Vuong 2026-07-04):**
  - Batch: hybrid sync/async, ngưỡng 10 miRNA.
  - LNA: McTigue 2004 + Owczarzy 2011, chỉ forward/reverse trước, RT hybrid để sau.
  - History: IndexedDB, chưa export/import.
  - **ChatbotPanel KHÔNG làm ở phase này** (defer AI/LLM sang phase riêng — nhất quán với SPEC_phase4/6).
- **Bất biến:** không đổi `SCORING_WEIGHTS_V4`; LNA Tm là **advisory/informational**, KHÔNG vào weighted-sum (nhất quán với hybrid_tm.py Sugimoto 1995 — "informational only, not scored"). Không thêm dependency ngoài stack hiện có.

---

## 0. Hướng dẫn cho Claude Code

1. **Đọc trước:**
   - `SPEC_algorithm.md` §13 (bound_fraction), §10 (thermodynamics), edge case E1 (miRNA ngắn <18 nt)
   - `backend/algorithm/hybrid_tm.py` — Sugimoto 1995 framework (DNA:RNA); LNA sẽ theo pattern tương tự (NN table thuần Python, no dependency)
   - `backend/algorithm/thermodynamics.py` — salt correction pipeline (SantaLucia + von Ahsen 2001); LNA Tm phải reuse salt correction này
   - `backend/routes/blast_check.py` + `backend/utils/circuit_breaker.py` — job pattern cho async batch
   - `SPEC_phase3.md` §9 (job architecture), `SPEC_phase4.md` §8 (export), `RESEARCH_QUESTIONS_UX.md` A1/A2/C1
   - `RESEARCH_INSIGHTS.md` E.1 (DNA:RNA hybrid gap — quan trọng cho caveat RT overhang)

2. **Bất biến:**
   - KHÔNG đổi `SCORING_WEIGHTS_V4` (15 tiêu chí, tổng 1.00).
   - KHÔNG thêm dependency mới (primer3-py, ViennaRNA, biopython, numpy, flask-limiter đã đủ). LNA NN table triển khai thuần Python như `hybrid_tm.py`.
   - LNA Tm = **informational only**, hiển thị bên cạnh Tm DNA:DNA, KHÔNG dùng để lọc/loại candidate hay đổi ranking.
   - Batch = wrapper quanh `/api/design` hiện có; KHÔNG viết lại pipeline design.

3. **Constants tập trung:** LNA params mới đặt trong `constants.py` Section U (với `[NGUỒN]`). Batch constants Section V. History = frontend-only, không có backend constant.

4. **Output UI English.** Comment tiếng Việt được.

5. Mỗi module có unit test; feature bật/tắt qua constant để A/B. Playwright E2E cho batch flow + history persistence.

---

## 1. Tổng quan Phase 8

### Bối cảnh định hình phase này

Sau Phase 3–7, tool đã có: single-miRNA design, family/isomiR/BLAST specificity, bound fraction, MIQE export, benchmark, normalization advisor. Ba khoảng trống còn lại chặn tool trở thành **scientific tool hoàn chỉnh** cho workflow lab thực tế:

1. **Batch (A1):** panel qPCR thực tế thiết kế 5–20 miRNA cùng lúc; hiện user phải submit từng cái → workflow chậm, dễ sót.
2. **LNA (A2):** miRNA ngắn (<18 nt, edge case E1) cần LNA để đủ Tm; hiện chỉ có text hint "consider LNA", không tính được vị trí nào cần LNA và Tm sau khi thêm.
3. **History (C1):** refresh page → mất kết quả; batch 20 miRNA mất 5–10 phút → mất hết là tổn thất lớn.

### Mục tiêu
- **Batch design:** 1 request → N kết quả, streaming/async tùy size, progress rõ ràng.
- **LNA calculator:** tính Tm (doublet-based NN) sau khi thêm LNA, đề xuất vị trí tối ưu — 2 mục tiêu: (a) đạt Tm target cho miRNA ngắn (E1), (b) **tăng phân biệt family** khi đặt LNA tại vị trí mismatch vs HIGH-risk sibling. Forward/reverse (DNA:DNA).
- **Session history:** kết quả bền qua refresh, load lại nhanh, chịu được batch nặng.

### Thời gian mục tiêu
PART A ~2 ngày · PART B ~2 ngày · PART C ~1 ngày.

### Phase 8 KHÔNG làm
- ChatbotPanel / AI-LLM (defer sang phase riêng).
- Species expansion (A3) — defer Phase 9.
- Calibration module (B1), Docker (B2), OpenAPI (B3) — nhóm production readiness, defer Phase 9.
- RT overhang LNA Tm (DNA:RNA) — future-work, chỉ document caveat.
- Export/import history — future-work.

---

## 2. Nguồn tham chiếu (Phase 8)

| Mã | Nguồn |
|---|---|
| [McTigue04] | McTigue, Peterson & Kahn 2004, Biochemistry 43(18):5388-5405, DOI 10.1021/bi035976d — 32 NN params ΔΔH°/ΔΔS° cho single LNA·DNA:DNA |
| [Owczarzy11] | Owczarzy et al. 2011, Biochemistry 50(43):9352-9367, DOI 10.1021/bi200904e — consecutive LNA + mismatch discrimination; kế thừa McTigue04 cho isolated LNA |
| [SL98] | SantaLucia 1998 — NN base DNA:DNA (đã dùng qua primer3-py) |
| [Sugimoto95] | Sugimoto 1995 — DNA:RNA hybrid NN (đã trong hybrid_tm.py; nền cho caveat RT overhang) |
| [vonAhsen01] | von Ahsen 2001 — divalent→monovalent salt correction (đã trong thermodynamics.py) |
| [Chen05] | Chen 2005 — stem-loop RT-qPCR foundational |
| [MIQE09] | Bustin 2009 — MIQE guidelines |

**Ghi chú khoa học [McTigue04] + [Owczarzy11] (v1.1):**
- Cả hai là **doublet-level NN params** — hợp nhất với [SL98] trong MỘT vòng duyệt doublet (§B.3), KHÔNG phải "ΔΔ per position".
- [McTigue04] đo ΔΔH°/ΔΔS° cho **single internal LNA** trên 100 duplex → 32 NN doublet (`5'-MX^L` và `5'-X^L N`; M,N = A/C/G/T; X^L = LNA). Purine neighbor ổn định hơn; LNA pyrimidine (đặc biệt A^L) đóng góp nhiều nhất. Dùng cho doublet chứa **đúng 1 LNA**.
- [Owczarzy11] **kế thừa** McTigue04 cho isolated LNA, bổ sung params cho **doublet LNA-LNA** (consecutive, stacking cooperativity) + **mismatch discrimination**. Dùng cho doublet chứa **2 LNA** và cho discrimination mode (§B.4a).
- **Context bắt buộc:** cả hai là cho **LNA·DNA : DNA** (LNA substitution trong DNA strand, complement toàn DNA). ĐÚNG cho forward/reverse bám cDNA (DNA:DNA). KHÔNG đúng cho RT overhang bám miRNA (DNA:RNA, A-form) → §B.7 caveat.

---

# PART A — Batch design mode (A1)

## A.1 Rationale

Panel qPCR thực tế (let-7 family, miR-200 family, disease signature panel) thường 5–20 miRNA. Hiện `/api/design` chỉ nhận 1 miRNA → user submit N lần thủ công. Batch giảm friction + đảm bảo cùng params cho cả panel (quan trọng cho so sánh Cq liên assay).

## A.2 Kiến trúc — Hybrid sync/async (chốt v1.0)

**Ngưỡng quyết định:** `BATCH_ASYNC_THRESHOLD = 10` miRNA.

```
Request size ≤ 10  → SYNCHRONOUS streaming (NDJSON)
                     - Xử lý tuần tự, stream từng kết quả ngay khi xong
                     - Progress bar frontend đọc theo dòng NDJSON
                     - Không cần job store, response mở đến khi hết

Request size > 10  → ASYNC job + polling
                     - POST trả job_id ngay (202 Accepted)
                     - Backend xử lý background (thread, reuse BLAST job pattern)
                     - GET /api/batch-status/<job_id> → progress + partial results
                     - Frontend poll mỗi 2s đến status=done
```

**Lý do hybrid (không chọn 1 hướng):**
- Sync streaming đơn giản, phản hồi tức thì cho panel nhỏ (đa số use case).
- Async cần cho panel lớn: sync 20 miRNA × ~1.2s = 24s → vượt HTTP timeout nhiều proxy (Railway ~30s nhưng rủi ro); async không bị chặn.
- Reuse job pattern đã có từ BLAST (§SPEC_phase3 §9) → không viết mới hạ tầng.

## A.3 Endpoint `POST /api/batch-design`

**File:** `backend/routes/batch_design.py`

**Request:**
```json
{
  "mirnas": ["hsa-miR-21-5p", "hsa-let-7a-5p", "hsa-miR-200a-3p", ...],
  "params": {
    "mg_conc": 3.0, "dntp_conc": 0.8, "primer_conc": 200, ...
  }
}
```
- `params` áp dụng đồng nhất cho TẤT CẢ miRNA trong batch (đây là điểm mấu chốt — panel dùng chung điều kiện phản ứng).
- `mirnas`: list, tối đa `BATCH_MAX_SIZE = 50` (warning nếu vượt).
- Validate: mỗi entry qua `sequence_utils.normalize_mirna_name()`; loại duplicate; báo entry invalid nhưng KHÔNG block cả batch.

**Response — Synchronous (≤10), Content-Type: application/x-ndjson:**
```
{"type":"meta","total":3,"mode":"sync"}
{"type":"result","index":0,"mirna":"hsa-miR-21-5p","status":"ok","data":{...design output...}}
{"type":"result","index":1,"mirna":"hsa-let-7a-5p","status":"ok","data":{...}}
{"type":"result","index":2,"mirna":"hsa-miR-200a-3p","status":"error","error":"miRNA not found in miRBase"}
{"type":"done","succeeded":2,"failed":1}
```
- Mỗi dòng là 1 JSON object độc lập (NDJSON) → frontend parse incrementally, update progress + render kết quả ngay.
- `data` của mỗi result = **y hệt** output `/api/design` hiện tại (reuse `design_pipeline()`).

**Response — Async (>10), 202 Accepted:**
```json
{"job_id":"batch_a1b2c3", "total":15, "mode":"async", "status":"queued"}
```

## A.4 Endpoint `GET /api/batch-status/<job_id>`

```json
{
  "job_id":"batch_a1b2c3",
  "status":"running",          // queued | running | done | error
  "total":15,
  "completed":8,
  "succeeded":7,
  "failed":1,
  "results":[ {...}, {...} ],  // partial — các miRNA đã xong
  "errors":[ {"mirna":"hsa-miR-xyz","error":"not found"} ]
}
```
- Job store: in-memory dict `{job_id: BatchJob}` (đủ cho single-instance Railway; note limitation nếu scale multi-instance → cần Redis, defer).
- TTL job: xoá sau `BATCH_JOB_TTL_SEC = 3600` (1h) — dùng background sweep hoặc lazy cleanup on access.

## A.5 Backend logic — reuse design pipeline

```python
# backend/routes/batch_design.py

from algorithm.design_pipeline import design_pipeline   # hàm lõi /api/design gọi
from sequence_utils import normalize_mirna_name

BATCH_ASYNC_THRESHOLD = 10   # constants.py Section V
BATCH_MAX_SIZE        = 50
BATCH_JOB_TTL_SEC     = 3600

def _run_one(mirna_id: str, params: dict) -> dict:
    """Wrapper — reuse design_pipeline, catch lỗi per-miRNA."""
    try:
        norm = normalize_mirna_name(mirna_id)
        data = design_pipeline(norm, params)   # KHÔNG viết lại — gọi hàm lõi
        return {"mirna": mirna_id, "status": "ok", "data": data}
    except Exception as e:
        return {"mirna": mirna_id, "status": "error", "error": str(e)}

# Sync: generator streaming NDJSON
def _stream_batch(mirnas, params):
    yield json.dumps({"type":"meta","total":len(mirnas),"mode":"sync"}) + "\n"
    succeeded = failed = 0
    for i, m in enumerate(mirnas):
        r = _run_one(m, params)
        if r["status"] == "ok": succeeded += 1
        else: failed += 1
        yield json.dumps({"type":"result","index":i,**r}) + "\n"
    yield json.dumps({"type":"done","succeeded":succeeded,"failed":failed}) + "\n"

# Async: background thread cập nhật job store
def _run_batch_async(job_id, mirnas, params):
    job = _JOB_STORE[job_id]
    job.status = "running"
    for i, m in enumerate(mirnas):
        r = _run_one(m, params)
        job.completed += 1
        if r["status"] == "ok":
            job.succeeded += 1; job.results.append(r)
        else:
            job.failed += 1; job.errors.append({"mirna": m, "error": r["error"]})
    job.status = "done"
```

**Rate limit:** `@limiter.limit("3 per minute")` cho `/api/batch-design` (nặng hơn single). Async job không giới hạn poll (GET status nhẹ).

## A.6 Frontend

**File:** `frontend/src/components/BatchDesignPanel/index.jsx`

- **Input:** textarea multi-line (1 miRNA/dòng) HOẶC paste comma/tab-separated; parse + dedupe + show count.
- **Validation UI:** highlight entry invalid trước submit (basic regex `^[a-z]{3}-(miR|let)-`); vẫn cho submit (backend validate lại).
- **Params:** dùng chung form params hiện có (shared component với single design).
- **Progress:**
  - Sync mode: đọc NDJSON stream qua `fetch` + `ReadableStream`, update progress bar theo `completed/total`, render result card ngay khi nhận dòng.
  - Async mode: nhận `job_id` → poll `/api/batch-status` mỗi 2s; progress bar + partial cards.
- **Kết quả:** grid các `PrimerSetCard` (reuse Phase 3/4 component), mỗi card = 1 miRNA; card lỗi hiển thị error state.
- **Batch export:** nút "Export all" → gọi `/api/export` cho từng set HOẶC combined CSV (1 file, N×3 rows). Reuse Phase 4 export.
- **Auto-save:** mỗi batch hoàn thành → lưu vào IndexedDB history (§C).

**Hook:** `frontend/src/hooks/useBatchDesign.js`
```
status: idle | streaming | polling | done | error
run(mirnas, params) → tự chọn sync/async theo mirnas.length
progress: {completed, total, succeeded, failed}
results: [...]
```

## A.7 Unit + E2E tests

```python
# backend/tests/routes/test_batch_design.py
def test_sync_batch_3_mirnas_streams_ndjson()       # ≤10 → NDJSON, 3 result lines + done
def test_async_batch_15_mirnas_returns_job_id()      # >10 → 202 + job_id
def test_batch_status_partial_results()              # running → partial results present
def test_batch_one_invalid_does_not_block_others()   # 1 lỗi → 2 ok + 1 error, không crash
def test_batch_params_applied_uniformly()            # cùng params cho mọi miRNA
def test_batch_max_size_warning()                    # >50 → warning
def test_batch_dedupe()                              # duplicate miRNA → xử lý 1 lần
```

```javascript
// frontend Playwright: batch-design.spec.js
test('sync batch: submit 3 miRNAs, progress reaches 100%, 3 cards render')
test('async batch: submit 15 miRNAs, poll updates progress, all cards render')
test('batch with 1 invalid miRNA shows error card + others succeed')
test('completed batch auto-saved to history')
```

## A.8 Deliverables (PART A)
- ✅ `POST /api/batch-design` (hybrid sync NDJSON / async job)
- ✅ `GET /api/batch-status/<job_id>`
- ✅ `_run_one` reuse `design_pipeline` (không viết lại design logic)
- ✅ In-memory job store + TTL cleanup
- ✅ `BatchDesignPanel.jsx` + `useBatchDesign.js` + progress bar
- ✅ Batch export (combined CSV) reuse Phase 4
- ✅ Auto-save vào IndexedDB history
- ✅ Unit + Playwright tests

---

# PART B — LNA Tm calculator (A2)

## B.1 Rationale

Edge case E1: miRNA ngắn (<18 nt) → forward primer specific region 12–17 nt cho Tm quá thấp (30–45°C), khó đạt Ta=60°C ngay cả với tail. LNA substitution nâng Tm mạnh (single LNA +1 đến +8°C tùy vị trí/context [McTigue04]). Hiện tool chỉ có text hint "consider LNA" — không tính được **vị trí nào** cần LNA và Tm **sau khi** thêm.

**Giá trị:** biến hint mơ hồ thành đề xuất định lượng: "Thêm LNA tại vị trí 3, 7, 11 → Tm 52→61°C".

## B.2 Phạm vi (chốt v1.0)

- **Áp dụng:** forward primer + universal reverse (DNA:DNA context — [McTigue04]/[Owczarzy11] đúng).
- **KHÔNG áp dụng (future-work):** RT stem-loop overhang (DNA:RNA context) — §B.7 caveat. RT overhang chỉ 6 nt cố định, LNA ở đây đổi RT efficiency theo cách khác; params LNA·DNA:DNA không transfer sang LNA·DNA:RNA.
- **Informational only:** LNA Tm hiển thị bên cạnh Tm DNA:DNA, KHÔNG vào `SCORING_WEIGHTS_V4`, KHÔNG lọc candidate.

## B.3 Model khoa học — doublet-based NN hợp nhất (v1.1 CORRECTED)

### Nguyên tắc: bookkeeping ở tầng **doublet**, không phải "position"

NN model tính năng lượng theo từng **doublet** (cặp base kề nhau). Một chuỗi n nt có (n−1) doublet. Một LNA đơn lẻ tại vị trí i **ảnh hưởng 2 doublet**: doublet (i−1, i) và doublet (i, i+1). Vì vậy **KHÔNG** có "một số hạng ΔΔ cho mỗi position" — phải duyệt từng doublet và chọn nguồn param theo thành phần base của doublet đó.

```
Duyệt từng doublet d = (base_j, base_{j+1}) trong sequence:

  cả 2 base đều DNA            → SantaLucia 1998   ΔH°(d), ΔS°(d)
  đúng 1 base là LNA           → McTigue 2004      ΔH°_LNA(d), ΔS°_LNA(d)
    (5'-MX^L hoặc 5'-X^L N)                          (DNA doublet + ΔΔ từ [McTigue04])
  cả 2 base đều LNA            → Owczarzy 2011     ΔH°_LNALNA(d), ΔS°_LNALNA(d)
                                                     (LNA-LNA stacking cooperativity)

ΔH°_total = Σ_doublets ΔH°(d) + ΔH°_init
ΔS°_total = Σ_doublets ΔS°(d) + ΔS°_init

Tm = ΔH°_total / (ΔS°_total + R·ln(C_T / x)) − 273.15   [°C]
     rồi salt correction (SantaLucia + von Ahsen 2001)
```

- **[SL98]** cung cấp 10 DNA-DNA doublet + initiation. Triển khai lại thuần Python trong `lna_tm.py` để giữ **một engine duy nhất** (xem "ΔTm nội nhất quán" dưới).
- **[McTigue04]** cung cấp ΔΔ cho 32 NN doublet chứa **đúng 1 LNA** (`5'-MX^L` và `5'-X^L N`). Isolated LNA → hai doublet kề nó đều là loại "1 LNA".
- **[Owczarzy11]** cung cấp params cho doublet **LNA-LNA** (consecutive). Khi 2 LNA liền nhau, doublet giữa chúng là LNA-LNA → dùng Owczarzy; hai doublet ngoài cùng vẫn là "1 LNA" → McTigue.
- **Không có nhánh "method single vs consecutive".** Luôn là MỘT vòng duyệt doublet; nguồn param chọn per-doublet. Field `method` trong output chỉ là **metadata** liệt kê bộ param đã dùng (vd `["santalucia98","mctigue04"]`, thêm `"owczarzy11"` nếu chạm LNA-LNA), không phải nhánh logic.

### ΔTm nội nhất quán (v1.1)

`calc_lna_tm` tính **cả** baseline và LNA bằng **cùng NN engine trong `lna_tm.py`**:
```
tm_dna   = _nn_tm(sequence, lna_positions=[],    params)   # baseline, cùng engine
tm_lna   = _nn_tm(sequence, lna_positions=[...], params)   # có LNA
delta_tm = tm_lna − tm_dna
```
- ΔTm chỉ phản ánh **hiệu ứng LNA thuần**, không nhiễm chênh lệch giữa primer3 và code custom (khác initiation term, convention C_T, salt).
- **Convention nồng độ:** `x = 4` cho duplex non-self-complementary (khớp primer3 để `tm_dna` cùng thang với Tm hiển thị ở card chính). C_T = primer_conc từ params.
- primer3 Tm vẫn hiển thị riêng như "reference DNA:DNA Tm"; KHÔNG dùng primer3 làm baseline để trừ ra ΔTm.

### Salt correction — reuse + caveat (v1.1)

- **Reuse** pipeline `thermodynamics.py` (SantaLucia entropy salt + von Ahsen 2001 divalent→monovalent). Feed ΔH°_total/ΔS°_total (đã gồm LNA) vào bước salt adjustment — KHÔNG viết lại.
- **Caveat bắt buộc (document + UI):** [McTigue04]/[Owczarzy11] đo ở salt cố định (~100 mM Na⁺ tùy set). ΔΔH°/ΔΔS° là **differential** nên tương đối ít phụ thuộc salt → áp salt correction lên tổng là approximation chấp nhận được. Nhưng salt-dependence của LNA **khác** DNA; ở điều kiện ion xa 100 mM (vd Mg²⁺ cao), ước lượng Tm LNA **kém chính xác hơn** DNA thuần. Ghi rõ trong disclaimer.

## B.4 Module `backend/algorithm/lna_tm.py`

**Triển khai thuần Python — NN table hardcode (như `hybrid_tm.py`), KHÔNG dependency mới.**

```python
"""
LNA Tm calculator — informational only, NOT scored.
Doublet-based unified NN: SantaLucia98 (DNA-DNA) + McTigue04 (1 LNA) + Owczarzy11 (LNA-LNA).
Context: LNA·DNA : DNA (forward/reverse trên cDNA). NOT for RT overhang (DNA:RNA) — §B.7.
Baseline (tm_dna) và tm_lna tính bằng CÙNG engine → ΔTm nội nhất quán (§B.3).
"""

# [SL98] 10 DNA-DNA doublet ΔH°(kcal/mol), ΔS°(cal/mol·K) + initiation
SANTALUCIA_1998_DH = { ... }   # AA, AT, ... (đã chuẩn, đối chiếu primer3 oligotm.c)
SANTALUCIA_1998_DS = { ... }
SL98_INIT_DH, SL98_INIT_DS = ...   # initiation + terminal AT penalty

# [McTigue04] 32 doublet chứa đúng 1 LNA — LƯU Ở TẦNG DOUBLET (không phải "ΔΔ per position")
# Key: doublet string với LNA-base viết hoa+^, vd "cA^", "A^g" (5'→3')
MCTIGUE_2004_DH = { ... }   # 32 entries, VERIFY against paper Table 2/3 before production
MCTIGUE_2004_DS = { ... }

# [Owczarzy11] doublet LNA-LNA (consecutive)
OWCZARZY_2011_LNALNA_DH = { ... }   # VERIFY before production
OWCZARZY_2011_LNALNA_DS = { ... }

def _classify_doublet(seq, lna_set, j):
    """doublet (j, j+1) → 'dna_dna' | 'one_lna' | 'lna_lna'."""

def _nn_tm(sequence: str, lna_positions: list[int], params: dict) -> dict:
    """
    Core engine — dùng cho CẢ baseline (lna_positions=[]) và LNA.
    Duyệt (n-1) doublet, chọn param source per-doublet (§B.3), cộng init,
    reuse thermodynamics.py cho salt correction, convention C_T/4.
    Returns: {tm, dh_total, ds_total, param_sources: set}
    """

def calc_lna_tm(sequence: str, lna_positions: list[int], params: dict) -> dict:
    """
    sequence: primer sequence (DNA, 5'→3'); lna_positions: 0-based indices có LNA
    Returns: {
      tm_dna,          # _nn_tm(seq, [], params) — cùng engine
      tm_lna,          # _nn_tm(seq, lna_positions, params)
      delta_tm,        # tm_lna - tm_dna (hiệu ứng LNA thuần)
      lna_positions,
      method,          # METADATA ONLY: list bộ param đã chạm, vd ["santalucia98","mctigue04"]
      per_doublet,     # optional: breakdown từng doublet (debug/transparency)
      warnings,
    }
    """

def suggest_lna_positions(sequence: str, target_tm: float, params: dict,
                          max_lna: int = 4,
                          mode: str = "tm",
                          sibling_mismatch_positions: list[int] = None) -> dict:
    """
    Đề xuất vị trí LNA. Hai mode (§B.4a).
    mode="tm": tối thiểu LNA để đạt target_tm (miRNA ngắn E1).
    mode="discrimination": ưu tiên vị trí trùng mismatch vs HIGH-risk sibling
                           (sibling_mismatch_positions từ family_crossreactivity).

    Search strategy (v1.1):
      - Nếu C(len_eligible, ≤max_lna) ≤ EXHAUSTIVE_LIMIT (~5000) → EXHAUSTIVE
        (LNA có cooperativity — greedy không tối ưu toàn cục; exhaustive chính xác hơn).
      - Ngược lại → GREEDY (thêm vị trí +benefit cao nhất mỗi vòng, tái tính vì
        neighbor thay đổi marginal benefit).

    Design constraints:
      - 3' terminal: KHÔNG hard-skip. Nếu chọn LNA ở nucleotide 3' cuối → thêm warning
        (polymerase extension efficiency concern) nhưng vẫn cho phép (LNA_AVOID_3PRIME_TERMINAL
        controls default behavior). §B.5.
      - Cross-check hairpin/self-dimer sau khi thêm LNA (primer3) → warning nếu xấu đi.
      - max_lna mặc định 4.

    Returns: {suggested_positions, tm_achieved, target_met, mode,
              discrimination_gain, warnings}   # discrimination_gain chỉ ở mode=discrimination
    """
```

**Ghi chú model (v1.1):**
- `method` là **metadata**, không phải nhánh xử lý — engine luôn duyệt doublet thống nhất (§B.3).
- Baseline và LNA cùng `_nn_tm` → ΔTm sạch.
- Exhaustive ưu tiên khi khả thi vì **LNA cooperative** (thêm 1 LNA đổi doublet kề → đổi marginal benefit của vị trí khác); greedy chỉ là fallback cho search space lớn.
- Design constraints (3' terminal, hairpin) là **heuristic guidance có warning**, KHÔNG hard-filter — nhất quán nguyên tắc "LNA informational, không loại candidate".

## B.4a LNA discrimination mode (v1.1 — giá trị khoa học cao nhất)

### Rationale
Lõi tool là **phân biệt miRNA family khác 1 nt** (module `family_crossreactivity`). LNA đặt **đúng tại vị trí mismatch** với sibling làm tăng ΔΔG giữa perfect-match (target) và mismatch-duplex (sibling) mạnh hơn nhiều so với chỉ nâng Tm chung. [Owczarzy11] tiêu đề chính là **mismatch discrimination** của LNA-DNA — đây là ứng dụng LNA đúng nhất cho bài toán này.

### Nguồn data — nối family module (không thêm dependency)
- `family_crossreactivity` (đã có) trả `cross_reactivity[]` với mỗi HIGH-risk sibling + `sibling_overhang`.
- So target overhang vs sibling overhang → **vị trí mismatch** (index trên forward primer specific region tương ứng).
- Truyền các vị trí này vào `suggest_lna_positions(mode="discrimination", sibling_mismatch_positions=[...])`.

### Objective function
```
mode="discrimination":
  Với candidate LNA set L, tính:
    ΔTm_target(L)   = Tm(target duplex, L) − Tm(target, [])           # nâng match
    ΔTm_sibling(L)  ≈ Tm(sibling-mismatch duplex, L) − Tm(sibling, []) # nâng mismatch (ít hơn nếu LNA tại mismatch)
  discrimination_gain = ΔTm_target(L) − ΔTm_sibling(L)   # maximize
  → ưu tiên L phủ vị trí mismatch (LNA tại mismatch → target ổn định, sibling KHÔNG)
```
- **Approximation caveat:** `Tm(sibling-mismatch duplex)` cần mismatch NN params (LNA·mismatch) — [Owczarzy11] có một phần cho mismatch discrimination nhưng không phủ hết context. Khi thiếu param chính xác, dùng **qualitative ranking** (LNA tại vị trí mismatch > LNA nơi khác) thay vì con số ΔTm_sibling tuyệt đối. Ghi rõ đây là **directional guidance**, không phải Tm mismatch định lượng.

### Kích hoạt — ON-DEMAND (chốt v1.1)
- KHÔNG tự động chạy. Trong `FamilyMapPanel` (Phase 3), khi có HIGH/IDENTICAL sibling → hiện nút **"Suggest LNA for discrimination"**.
- User bấm → frontend gọi `POST /api/lna-suggest` với `mode="discrimination"` + mismatch positions (đã có sẵn client từ family output).
- Nhất quán nguyên tắc: LNA informational, không tự chạy để giữ tốc độ `/api/design`.

## B.5 Constants — Section U (constants.py)

```python
# Section U: LNA (Phase 8) — informational only, NOT scored
LNA_MAX_SUBSTITUTIONS      = 4       # đề xuất tối đa 4 LNA/primer
LNA_TARGET_TM_DEFAULT      = 60.0    # °C — mục tiêu Tm khi suggest (mode="tm")
LNA_AVOID_3PRIME_TERMINAL  = True    # True: warning khi LNA ở 3' cuối (KHÔNG hard-skip); vẫn cho phép
LNA_EXHAUSTIVE_LIMIT       = 5000    # số tổ hợp tối đa để chạy exhaustive; vượt → greedy
LNA_HAIRPIN_RECHECK        = True    # cross-check primer3 hairpin sau khi thêm LNA → warning
# NN tables trong lna_tm.py (tầng DOUBLET, không phải "ΔΔ per position"):
#   SANTALUCIA_1998_DH/DS  — 10 DNA-DNA doublet + init [SL98]
#   MCTIGUE_2004_DH/DS     — 32 doublet chứa 1 LNA [McTigue04]
#   OWCZARZY_2011_LNALNA_DH/DS — doublet LNA-LNA [Owczarzy11]
# ⚠ VERIFY tất cả tables against source papers (Table 2/3) before production use
USE_LNA_SUGGESTIONS        = True    # A/B toggle
```

## B.6 Tích hợp vào output

- LNA calculator = **on-demand**, KHÔNG chạy tự động trong `/api/design` (giữ tốc độ <5s).
- Endpoint riêng: `POST /api/lna-suggest`
  ```json
  // Request — mode="tm" (miRNA ngắn E1)
  {"sequence":"ACGTACGTACGT", "role":"forward", "mode":"tm",
   "target_tm":60.0, "params":{...}}

  // Request — mode="discrimination" (family HIGH-risk sibling)
  {"sequence":"ACGTACGTACGT", "role":"forward", "mode":"discrimination",
   "sibling_mismatch_positions":[3,7], "params":{...}}

  // Response
  {
    "tm_dna": 52.3,              // baseline — CÙNG engine với tm_lna (§B.3)
    "tm_lna": 61.1,
    "delta_tm": 8.8,            // tm_lna - tm_dna (hiệu ứng LNA thuần)
    "suggested_positions": [2, 6, 10],
    "target_met": true,
    "search": "exhaustive",     // "exhaustive" | "greedy"
    "method": ["santalucia98","mctigue04"],   // METADATA: bộ param đã chạm
    "per_doublet": [ ... ],     // optional breakdown (transparency)
    "discrimination_gain": null, // chỉ != null khi mode="discrimination"
    "tm_reference_primer3": 51.9, // Tm primer3 DNA:DNA hiển thị tham chiếu (KHÔNG dùng trừ ΔTm)
    "warnings": [
      "LNA at position 10 is at 3' terminal — may affect polymerase extension efficiency",
      "LNA at position 6 may increase hairpin ΔG — verify with synthesis provider"
    ]
  }
  ```
  - `mode="discrimination"` → thêm `discrimination_gain` (ΔTm_target − ΔTm_sibling, directional §B.4a).
  - `method` là **list metadata** bộ param đã dùng, KHÔNG phải nhánh logic (§B.3).
  - `tm_reference_primer3` chỉ để hiển thị đối chiếu; ΔTm luôn tính nội bộ cùng engine.

- Frontend: trong `PrimerSetCard`, khi forward Tm < threshold → nút "Suggest LNA (Tm)". Trong `FamilyMapPanel` khi có HIGH/IDENTICAL sibling → nút "Suggest LNA for discrimination" (§B.4a). Cả hai mở `LnaPanel`.

**File frontend:** `frontend/src/components/LnaPanel/index.jsx`
- Sequence render với LNA positions highlighted (vd `A C [G] T A [C] G T`).
- Tm badge: "DNA 52.3°C → +LNA 61.1°C (Δ +8.8°C)".
- Ở discrimination mode: hiển thị thêm vị trí mismatch được LNA phủ + `discrimination_gain` (directional).
- Disclaimer bắt buộc: "LNA Tm predicted by doublet nearest-neighbor model (SantaLucia 1998 + McTigue 2004 + Owczarzy 2011, LNA·DNA:DNA). Salt correction approximate for LNA away from ~100 mM Na⁺. Informational — confirm with synthesis provider (IDT). Not used in scoring."

## B.7 RT overhang — future-work caveat (BẮT BUỘC document)

**KHÔNG tính LNA Tm cho RT overhang trong Phase 8.** Lý do khoa học:
- RT overhang (6 nt) bám **miRNA (RNA)** → duplex là **LNA·DNA : RNA**.
- [McTigue04]/[Owczarzy11] params là cho **LNA·DNA : DNA** → ΔΔH°/ΔΔS° KHÔNG transfer trực tiếp (RNA backbone, A-form helix khác B-form).
- Cần bộ params LNA·DNA:RNA riêng (chưa có bộ chuẩn thuần-Python; NUPACK/RNAstructure = dependency mới, đã loại từ Phase 6).

**Ghi trong `lna_tm.py` docstring + UI:** "LNA suggestions apply to forward/reverse primers (DNA:DNA). RT primer overhang binds miRNA (DNA:RNA hybrid); LNA thermodynamics for that context require different parameters and are out of scope (see RESEARCH_INSIGHTS E.1)."

## B.8 Unit tests

```python
# backend/tests/algorithm/test_lna_tm.py

# --- Model correctness (v1.1) ---
def test_baseline_matches_primer3_within_tolerance()  # tm_dna (lna=[]) ≈ primer3 ±1°C (cùng convention)
def test_doublet_bookkeeping_single_lna()             # 1 LNA sửa ĐÚNG 2 doublet kề, không phải 1 "position term"
def test_single_lna_touches_mctigue_only()            # method == ["santalucia98","mctigue04"]
def test_consecutive_lna_touches_owczarzy()           # 2 LNA liền → method chứa "owczarzy11" (doublet giữa)
def test_delta_tm_same_engine()                       # tm_dna & tm_lna cùng _nn_tm → ΔTm không nhiễm primer3
def test_lna_raises_tm_positive()                     # ΔTm > 0 (LNA ổn định hơn)
def test_salt_correction_reused()                     # dùng thermodynamics.py salt pipeline (không tự viết)

# --- Search strategy ---
def test_exhaustive_when_search_small()               # C(len,≤4) ≤ 5000 → search=="exhaustive"
def test_greedy_when_search_large()                   # vượt limit → search=="greedy"
def test_suggest_reaches_target_tm()                  # đạt target hoặc dừng ở max_lna
def test_exhaustive_beats_or_equals_greedy()          # exhaustive Tm ≥ greedy Tm (cooperativity)

# --- Design constraints (warning, not hard-skip) ---
def test_3prime_terminal_warns_not_skips()            # LNA ở 3' cuối → có trong result + warning (không loại)
def test_hairpin_recheck_warns()                      # LNA làm xấu hairpin → warning

# --- Discrimination mode (B.4a) ---
def test_discrimination_prefers_mismatch_positions()  # mode=discrimination → LNA phủ sibling_mismatch_positions
def test_discrimination_gain_reported()               # discrimination_gain != null ở mode=discrimination

# --- Invariants ---
def test_lna_not_in_scoring()                         # LNA KHÔNG có trong SCORING_WEIGHTS_V4
def test_rt_overhang_rejected()                       # role="rt" → error/warning "out of scope" (§B.7)
```

## B.9 Deliverables (PART B)
- ✅ `backend/algorithm/lna_tm.py` — **doublet-based unified NN**: SantaLucia98 + McTigue04 + Owczarzy11 (thuần Python)
- ✅ `_nn_tm()` engine dùng chung cho baseline + LNA → **ΔTm nội nhất quán** (§B.3)
- ✅ `calc_lna_tm()` (doublet bookkeeping) + `suggest_lna_positions()` (2 mode: tm / discrimination)
- ✅ Search: exhaustive khi khả thi (cooperativity), greedy fallback
- ✅ Discrimination mode nối `family_crossreactivity` (§B.4a) — on-demand
- ✅ Salt correction reuse `thermodynamics.py` + caveat (LNA salt-dependence ≠ DNA)
- ✅ 3' terminal & hairpin = **warning, không hard-skip**
- ✅ `POST /api/lna-suggest` (mode param) + `tm_reference_primer3` đối chiếu
- ✅ Constants Section U (`LNA_EXHAUSTIVE_LIMIT`, `LNA_AVOID_3PRIME_TERMINAL` warning-mode)
- ✅ `LnaPanel.jsx` — highlight + Tm before/after + disclaimer (salt caveat)
- ✅ RT overhang caveat documented (code + UI, §B.7)
- ✅ NN tables (3 bộ) marked "VERIFY before production"
- ✅ Unit tests (18 cases — model correctness, search, constraints, discrimination, invariants)

---

# PART C — Session history (C1)

## C.1 Rationale

Refresh page → mất kết quả. Batch 20 miRNA mất 5–10 phút compute → mất hết = tổn thất lớn. Cần persist client-side, load lại nhanh, chịu batch nặng.

## C.2 Storage — IndexedDB (chốt v1.0)

**Chọn IndexedDB (không localStorage):**
- Batch >20 miRNA × full result JSON có thể vượt localStorage ~5MB limit.
- IndexedDB: dung lượng lớn (hàng trăm MB), async API, structured storage.
- **Frontend-only** — KHÔNG backend, KHÔNG server storage (privacy + đơn giản).

**Schema (IndexedDB store `design_history`):**
```javascript
{
  id: "hist_<timestamp>",           // key
  type: "single" | "batch",
  created_at: ISO8601,
  mirnas: ["hsa-miR-21-5p", ...],   // 1 cho single, N cho batch
  params: {...},                    // ion conditions dùng
  results: [...],                   // full design output (reuse structure)
  summary: {                        // để render list nhanh không load full
    count: 15,
    succeeded: 14,
    failed: 1,
    best_score: 0.88
  }
}
```

## C.3 Module `frontend/src/lib/historyDB.js`

```javascript
// IndexedDB wrapper — thuần, no dependency (dùng native IndexedDB API)

const DB_NAME = "hglab_primer_history";
const STORE = "design_history";
const DB_VERSION = 1;
const MAX_ENTRIES = 100;   // giữ 100 gần nhất, xoá cũ (FIFO)

export async function saveHistory(entry) { ... }   // add + enforce MAX_ENTRIES
export async function listHistory() { ... }        // return summaries (không load full results)
export async function loadHistory(id) { ... }      // load full result by id
export async function deleteHistory(id) { ... }
export async function clearHistory() { ... }
```

**Retention:** giữ `MAX_ENTRIES = 100` bản gần nhất; vượt → xoá cũ nhất (FIFO). Tránh IndexedDB phình vô hạn.

## C.4 Frontend — History panel

**File:** `frontend/src/components/HistoryPanel/index.jsx`

- **List view:** sidebar/drawer hiển thị history summaries (mirna name(s), date, count, best score). Sort mới nhất trước.
- **Load:** click entry → `loadHistory(id)` → re-render kết quả (không re-compute).
- **Delete:** per-entry delete + "Clear all" (confirm).
- **Auto-save hooks:**
  - Single design done → `saveHistory({type:"single", ...})`.
  - Batch done → `saveHistory({type:"batch", ...})` (§A.6).
- **Badge:** history count trên nav.

**Hook:** `frontend/src/hooks/useHistory.js`
```
entries: [...summaries]
save(entry), load(id) → result, remove(id), clearAll()
refresh() — reload list
```

## C.5 Export/import — future-work

**KHÔNG làm Phase 8.** Document trong spec:
- Future: "Export history" → toàn bộ IndexedDB → 1 JSON file (backup/share).
- Future: "Import history" → load JSON → merge vào IndexedDB.
- Deferred vì: cần versioning schema + conflict resolution; ưu tiên thấp so với core persistence.

## C.6 Unit + E2E tests

```javascript
// frontend/src/lib/__tests__/historyDB.test.js (jsdom + fake-indexeddb)
test('saveHistory persists entry')
test('listHistory returns summaries without full results')
test('loadHistory returns full result by id')
test('MAX_ENTRIES enforced — oldest deleted at 101st entry')
test('deleteHistory removes single entry')

// Playwright: history-persistence.spec.js
test('single design → refresh page → result loadable from history')
test('batch done → history entry created with correct count')
test('load history entry re-renders results without re-compute')
test('clear all empties history')
```

## C.7 Deliverables (PART C)
- ✅ `frontend/src/lib/historyDB.js` — IndexedDB wrapper (native, no dependency)
- ✅ `MAX_ENTRIES=100` FIFO retention
- ✅ `HistoryPanel.jsx` + `useHistory.js`
- ✅ Auto-save hooks (single + batch)
- ✅ Load/delete/clear
- ✅ Export/import documented as future-work
- ✅ Unit (fake-indexeddb) + Playwright persistence tests

---

## 3. Thứ tự implement

1. **PART B first** (lna_tm.py doublet engine + baseline consistency test) — độc lập, giá trị khoa học cao (E1).
2. `suggest_lna_positions` mode="tm" (exhaustive+greedy) → `POST /api/lna-suggest` → `LnaPanel.jsx`.
3. `suggest_lna_positions` mode="discrimination" nối `family_crossreactivity` → nút trong `FamilyMapPanel`.
4. **PART A** — `batch_design.py` (sync NDJSON trước, async sau) + tests.
5. `BatchDesignPanel.jsx` + `useBatchDesign.js` + progress.
6. **PART C** — `historyDB.js` + `useHistory.js` + `HistoryPanel.jsx`.
7. Wire auto-save: single design + batch → history.
8. Playwright E2E: lna → batch → history flows.
9. Superpower security check → commit.

---

## 4. Định nghĩa "Phase 8 hoàn thành"

**PART A — Batch:**
- [ ] `POST /api/batch-design` hybrid: ≤10 NDJSON streaming, >10 async job
- [ ] `GET /api/batch-status/<job_id>` trả partial results + progress
- [ ] `_run_one` reuse `design_pipeline` (không duplicate design logic)
- [ ] 1 miRNA lỗi không block cả batch; params áp dụng đồng nhất
- [ ] `BatchDesignPanel` + progress bar (sync stream + async poll)
- [ ] Batch export combined CSV; auto-save history
- [ ] 7 backend + 4 Playwright tests pass

**PART B — LNA (v1.1):**
- [ ] `lna_tm.py`: **doublet-based unified NN** (SantaLucia98 + McTigue04 + Owczarzy11), thuần Python no dependency
- [ ] Mỗi LNA sửa ĐÚNG 2 doublet kề; nguồn param chọn per-doublet; `method` là metadata (không nhánh logic)
- [ ] `_nn_tm` engine chung cho baseline + LNA → ΔTm nội nhất quán; convention C_T/4 khớp primer3
- [ ] `calc_lna_tm` + `suggest_lna_positions` (2 mode: tm / discrimination)
- [ ] Search: exhaustive khi C(len,≤4)≤5000, greedy fallback; exhaustive Tm ≥ greedy
- [ ] Discrimination mode nối `family_crossreactivity` (on-demand nút "Suggest LNA for discrimination")
- [ ] Salt correction reuse `thermodynamics.py` + caveat LNA salt-dependence
- [ ] 3' terminal & hairpin = warning (không hard-skip)
- [ ] `POST /api/lna-suggest` (mode param, tm_reference_primer3); `LnaPanel` highlight + Tm before/after + Δ
- [ ] LNA informational only — KHÔNG trong SCORING_WEIGHTS_V4
- [ ] Forward/reverse only; RT overhang caveat documented (code + UI, §B.7)
- [ ] 3 NN tables marked "VERIFY before production"
- [ ] 18 unit tests pass

**PART C — History:**
- [ ] `historyDB.js` IndexedDB wrapper (native, no dependency)
- [ ] MAX_ENTRIES=100 FIFO; save/list/load/delete/clear
- [ ] `HistoryPanel` + auto-save (single + batch)
- [ ] Load re-renders without re-compute
- [ ] Export/import documented future-work
- [ ] 5 unit + 4 Playwright tests pass

**Chung:**
- [ ] UI 100% English
- [ ] Không thêm dependency (LNA table + IndexedDB đều native/thuần)
- [ ] `SCORING_WEIGHTS_V4` không đổi
- [ ] Constants: Section U (LNA), Section V (batch)
- [ ] Superpower security check pass (batch + lna-suggest endpoints)
- [ ] Playwright suite cũ vẫn xanh

**Không làm trong Phase 8** (defer Phase 9):
- ChatbotPanel / AI-LLM
- Species expansion (A3): mmu-, rno- family grouping
- Calibration module (B1), Docker (B2), OpenAPI (B3)
- RT overhang LNA Tm (DNA:RNA params)
- History export/import

---

## 5. Rủi ro & lưu ý

**Khoa học (ảnh hưởng độ chính xác Tm — ưu tiên cao):**
1. **NN LNA tables:** ⚠ hardcode 3 bộ từ [SL98]/[McTigue04]/[Owczarzy11] — **VERIFY thủ công against papers** (Table 2/3) trước production (Vuong review, như family/isomiR data). Sai 1 doublet param → Tm lệch systematic. Đối chiếu SantaLucia98 với `oligotm.c` (primer3) để baseline khớp.
2. **Baseline consistency:** nếu `_nn_tm(lna=[])` lệch primer3 >1–2°C → convention/init sai; phải fix trước khi tin ΔTm. Test `test_baseline_matches_primer3_within_tolerance` là gate.
3. **Salt correction cho LNA = approximation:** [McTigue04]/[Owczarzy11] đo ~100 mM Na⁺; salt-dependence LNA ≠ DNA → điều kiện xa 100 mM (Mg²⁺ cao) kém chính xác. Differential ΔΔ giảm nhẹ vấn đề nhưng không loại bỏ. Disclaimer bắt buộc.
4. **Discrimination Tm mismatch = directional, không định lượng:** `Tm(sibling-mismatch duplex)` thiếu full LNA·mismatch params → dùng qualitative ranking (LNA tại mismatch > nơi khác), KHÔNG claim con số ΔTm_sibling tuyệt đối (§B.4a).
5. **Greedy vs cooperativity:** LNA cộng không tuyến tính (neighbor-dependent). Exhaustive ưu tiên khi khả thi; greedy chỉ fallback → note trong output (`search` field) để user biết mức tối ưu.
6. **RT overhang LNA:** dễ hiểu nhầm "sao không tính cho RT?" → caveat rõ, DOI [Sugimoto95] + link RESEARCH_INSIGHTS E.1 (DNA:RNA A-form, params khác).

**Engineering:**
7. **Async job store in-memory:** mất khi restart; multi-instance không share. Đủ Railway single-instance. Scale → Redis (defer).
8. **IndexedDB support:** universal modern browsers; fallback graceful nếu disabled (in-memory only, warn user).
9. **Batch HTTP timeout:** ngưỡng 10 conservative; nếu proxy timeout thấp hơn, hạ threshold hoặc chuyển hết async.
10. **Batch ion conditions:** cả panel dùng chung `params` → Tm chỉ so sánh ngang hàng khi cùng điều kiện. UI cảnh báo rõ "batch uses shared ion conditions".

---

*Hết SPEC_phase8.md v1.1 — sync SPEC_algorithm v3.1 / phase3 / phase4 / phase6. Nguồn khoa học: SantaLucia 1998, McTigue 2004, Owczarzy 2011 (PubMed/ACS). LNA Tm = doublet-based NN, informational, not scored.*
