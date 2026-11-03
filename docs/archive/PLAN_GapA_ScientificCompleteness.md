# PLAN — Nhóm A: Scientific Completeness (A1 Batch · A2 LNA · A3 Species)

> Nguồn đối chiếu: `SPEC_week1.md` v4.0 (§14, §17, §18), `SPEC_phase3.md` §5.5–5.7, `SPEC_phase5.md` PART D.
> Ngày lập: 2026-08-14

---

## 0. Phát hiện quan trọng trước khi code

**Đây KHÔNG phải design gap — đây là spec-code drift.**

`SPEC_week1.md` v4.0 đánh dấu **Phase 8 (Batch design, LNA Tm calculator, session history) = ✅ HOÀN THÀNH** và đặc tả đầy đủ:

| Gap | Đã có sẵn trong spec | Vị trí |
|-----|----------------------|--------|
| A1 Batch | `POST /api/batch-design` (NDJSON ≤10 / async >10), `GET /api/batch-status/<id>`, `BATCH_ASYNC_THRESHOLD=10`, `BATCH_MAX_SIZE=50`, BatchPage layout, `useBatchDesign` hook, 7 unit tests | §14, §17 |
| A2 LNA | `algorithm/lna_tm.py`, API `calc_lna_tm()` / `suggest_lna_positions()`, `POST /api/lna-suggest`, `LNA_EXHAUSTIVE_LIMIT=5000`, `USE_LNA_SUGGESTIONS` flag, 29 unit tests | §18, §13 |
| A3 Species | `build_mirbase_db.py` **đã species-agnostic** (parse full multi-species `mature.fa`, lưu cột `organism`); BLAST đã có `_extract_species_prefix()` + `cross_species_excluded` | SPEC_phase3 §8.11 |

**⇒ Hành động đầu tiên KHÔNG phải viết code mới, mà là AUDIT.** Viết lại từ đầu khi spec đã chốt constant/contract là cách chắc chắn tạo ra bản thứ hai lệch spec.

### Bước 0 — Drift audit (~2–4 giờ)

```bash
# Checklist tồn tại
ls backend/algorithm/lna_tm.py backend/routes/batch_design.py backend/routes/lna_suggest.py
ls backend/tests/test_lna_tm.py backend/tests/test_batch_design.py
grep -rn "design_pipeline" backend/          # single source of truth có tồn tại?
grep -rn "BATCH_ASYNC_THRESHOLD\|LNA_EXHAUSTIVE_LIMIT\|USE_LNA_SUGGESTIONS" backend/constants.py
git log --oneline --all -- backend/algorithm/lna_tm.py backend/routes/batch_design.py
git branch -a                                # Phase 8 có nằm ở branch chưa merge?
```

Kết quả audit rơi vào 1 trong 3 trường hợp:

- **(a) Code tồn tại ở branch khác** → merge + chạy `pytest` (expect 36 passed). Xong trong 1 ngày.
- **(b) Code không tồn tại, spec viết aspirational** → implement theo đúng spec, KHÔNG thiết kế lại.
- **(c) Code tồn tại nhưng lệch spec** → sửa code theo spec, hoặc sửa spec + ghi changelog. Không để hai bản khác nhau cùng tồn tại.

**Bắt buộc:** sửa bảng trạng thái Phase trong `SPEC_week1.md` cho khớp thực tế. Spec sai trạng thái nguy hiểm hơn spec thiếu.

---

## 1. Thứ tự tối ưu: **Refactor → A3 → A1 → A2**

Không làm theo thứ tự A1→A2→A3. Lý do là dependency và chi phí biên:

```
[R] design_pipeline.run()  ──┬──> A1 batch (chỉ là vòng lặp quanh R)
   extract single source    └──> A3 species (thread param qua 1 chỗ, không N chỗ)
                                    │
                                    └──> A1 có test corpus rộng hơn (hsa+mmu+rno)
                                              │
                                              └──> A2 LNA (validate trên corpus đó)
```

### R — Refactor nền (làm trước, ~1–2 ngày)

Trích `design_pipeline.run(seq, params, mirna_name) -> dict` làm **single source of truth** cho cả `/api/design` và `/api/batch-design` (spec §17 đã yêu cầu).

- Input: `seq` (RNA uppercase, đã validate), `params` (flat dict), `mirna_name`
- Output: dict khớp đúng schema response của `/api/design`
- `signalMethod` default = `"taqman"` (KHÔNG phải `"sybr"`)

**Vì sao làm trước:** nếu không có R, batch sẽ gọi lại route handler → duplicate validation, khác default, và mọi thay đổi species phải sửa ở 2 nơi. Đây là refactor rẻ nhất mua được nhiều nhất.

**Gate:** output của `design_pipeline.run()` phải byte-identical với response `/api/design` hiện tại trên ≥10 miRNA regression (snapshot test).

---

### A3 — Species expansion (làm trước A1, ~2–3 ngày)

**Rẻ nhất, vì dữ liệu đã có sẵn.** `mature.fa` đã là multi-species (~48K sequences, ~2 MB) và `build_mirbase_db.py` đã lưu `organism`. Chỉ tầng family grouping hardcode `hsa-`.

Việc cần làm:

1. `build_family_db.py`: bỏ hardcode `hsa`, nhận `--species hsa,mmu,rno` (default = all). Output `mirbase_family_overhangs.json` giữ nguyên schema §30.5 + field `species` (spec đã dự trù field này).
2. `check_family_crossreactivity(..., species=None)`: mặc định lấy species từ prefix của `mirna_id` (dùng lại `_extract_species_prefix()` đã có trong BLAST module — **đừng viết hàm thứ hai**).
3. **Ranh giới khoa học:** family so sánh **trong cùng species**. Cross-species cùng family (hsa-let-7a vs mmu-let-7a, thường identical sequence) KHÔNG phải off-target thật vì mẫu chỉ có một loài → phải loại, nhất quán với logic `cross_species_excluded` của BLAST v1.9.
4. UI: form `species: 'human'` (§13) → dropdown `human | mouse | rat`, map sang prefix `hsa | mmu | rno`.

**Rủi ro cần chặn:**

- miFam.dat trả HTTP 500 (đã ghi nhận v1.7) → giữ seed-based grouping, không phụ thuộc miFam.
- Kích thước JSON tăng ~3× khi thêm mmu+rno. Nếu >5 MB, chuyển sang index SQLite thay vì load JSON vào RAM.
- Prefix collision: `hsa` vs `has` (typo phổ biến) → validate prefix theo whitelist, không regex tự do.

**Gate:** test `test_let7a_family_loaded_from_miFam` (spec §5.7) hiện assert cả `hsa-let-7a-5p` **và** `mmu-let-7a-5p` — test này chính là acceptance criteria của A3, đã viết sẵn.

---

### A1 — Batch design (~3–4 ngày)

Sau R, batch chỉ là vòng lặp tuần tự quanh `design_pipeline.run()`. Theo đúng spec §17:

- ≤10 miRNA → **sync NDJSON streaming**, `Content-Type: application/x-ndjson`
  `{"type":"meta","total":N}` → N×`{"type":"result",...}` → `{"type":"done","succeeded":X,"failed":Y}`
- \>10 → **async 202** + `job_id` + poll `GET /api/batch-status/<job_id>` mỗi 2s
- `BATCH_MAX_SIZE=50`, truncate kèm warning; dedup bằng `seen` set giữ nguyên thứ tự
- Circuit breaker: chỉ `record_failure()` cho 5xx/network — **KHÔNG cho 404** (404 = miRNA không tồn tại, lỗi của input chứ không phải của upstream)

**Ba cạm bẫy phải xử lý:**

1. **In-process job store vỡ khi multi-worker.** Dict `{job_id: state}` trong RAM chỉ đúng nếu chạy 1 process. Với gunicorn nhiều worker, poll sẽ trúng worker không giữ job → 404 ngẫu nhiên. Chọn một: chạy `--workers 1 --threads N`, hoặc lưu job state vào SQLite. Đừng để mặc định.
   *(Lưu ý: thiết kế cũ nhắc Celery+Redis; với batch ≤50 tuần tự thì Celery là over-engineering — nhưng phải chốt worker model rõ ràng thay cho nó.)*
2. **Isolation lỗi.** Một miRNA lỗi không được kill cả batch. Bọc `try/except` quanh từng item, trả `{"status":"error","error":"..."}` và đi tiếp.
3. **Timeout vs streaming.** Reverse proxy (nginx/HF Spaces) hay buffer response → progress bar đứng im rồi nhảy 100%. Cần `X-Accel-Buffering: no` và flush từng dòng.

**Gate:** 7 unit tests `test_batch_design.py` (spec §16). Thêm 1 test: batch 3 miRNA phải cho kết quả **identical** với 3 lần gọi `/api/design` riêng lẻ.

---

### A2 — LNA substitution calculator (~5–7 ngày, làm sau cùng)

Rủi ro khoa học cao nhất, nhưng **an toàn nhất về mặt hệ thống** vì spec đã chốt: *LNA Tm là informational only — KHÔNG vào `SCORING_WEIGHTS_V4`, KHÔNG vào hard filters.* Giữ nguyên ràng buộc này. Nó có nghĩa A2 không thể làm hỏng output hiện có, nên để cuối cùng là hợp lý.

**Nguồn tham số (theo đúng spec §18):**

- SantaLucia 1998 — baseline DNA:DNA
- **McTigue 2004** — doublet `one_lna` (ΔΔH/ΔΔS cho 1 LNA trong doublet). Đây là bảng chính.
- **Owczarzy 2011** — doublet `lna_lna` (LNA liền kề)

**Kiến trúc:** phân loại từng doublet thành `dna_dna | one_lna | lna_lna` → cộng ΔH/ΔS tương ứng → Tm theo NN. Trả `per_doublet` để debug được.

**Hai API (đừng gộp):**

- `calc_lna_tm(sequence, lna_positions, params)` — người dùng chỉ định vị trí, ta tính Tm
- `suggest_lna_positions(sequence, target_tm, params, max_lna, mode, sibling_mismatch_positions)` — ta đề xuất vị trí
  Exhaustive khi `C(eligible, ≤max_lna) ≤ LNA_EXHAUSTIVE_LIMIT=5000`, ngược lại greedy. Trả `search: "exhaustive"|"greedy"` để người dùng biết kết quả có tối ưu toàn cục không.

**Ràng buộc khoa học bắt buộc:**

- **RT primer → reject (400).** Stem-loop RT primer bắt cặp DNA:RNA; bảng McTigue/Owczarzy là DNA:DNA duplex. Áp dụng sẽ sai. Spec đã ghi rõ — giữ.
- `hybrid_tm.py` (Sugimoto 1995, DNA:RNA) là **module tách biệt**, không trộn tham số với `lna_tm.py`.
- Đặt LNA tại **vị trí mismatch với sibling trong family** → tăng discrimination (SPEC_phase5 D.2, RESEARCH_INSIGHTS_probe §3.1). Đây là lý do có param `sibling_mismatch_positions` — kết nối trực tiếp với A3.
- Tránh đặt LNA liền kề nhau và tại 3′ end nếu là primer (ảnh hưởng extension).

**Benchmark bắt buộc — đây là phần dễ bị bỏ qua nhất:**

Bảng ΔΔH/ΔΔS chép tay từ paper rất dễ sai một dấu hoặc một ô, và sai đó không gây exception — nó chỉ cho ra Tm sai lệch âm thầm. Vì vậy:

1. **Ground-truth set:** lấy các oligo có Tm đo thực nghiệm trong McTigue 2004 (paper có bảng oligo + Tm đo). Assert `|Tm_predicted − Tm_measured| ≤ 2°C`.
2. **Sanity invariants** (rẻ, bắt được lỗi dấu ngay):
   - `delta_tm > 0` với mọi substitution LNA hợp lệ (LNA luôn làm tăng Tm)
   - `delta_tm` tăng đơn điệu theo số lượng LNA
   - `lna_positions = []` → `tm_lna == tm_dna` chính xác
3. **Regression:** 29 unit tests `test_lna_tm.py` đã có trong spec.

**UI:** `LnaPanel.jsx`, hiển thị disclaimer nguyên văn — *"LNA Tm is informational only — not used in scoring or primer filtering."* Feature flag `USE_LNA_SUGGESTIONS` trong `constants.py`, trả 503 nếu `False` (cho phép ship code trước, bật sau khi benchmark pass).

---

## 2. Tổng hợp lịch trình

| Bước | Nội dung | Ước lượng | Điều kiện xong |
|------|----------|-----------|----------------|
| 0 | Drift audit + cập nhật bảng Phase trong spec | 0.5 ngày | Biết chắc (a)/(b)/(c) |
| R | Trích `design_pipeline.run()` | 1–2 ngày | Snapshot test 10 miRNA byte-identical |
| A3 | Species mmu/rno | 2–3 ngày | `test_let7a_family_loaded_from_miFam` pass |
| A1 | Batch design | 3–4 ngày | 7 tests + batch≡single test pass |
| A2 | LNA calculator | 5–7 ngày | 29 tests + benchmark ≤2°C vs McTigue |

Nếu bước 0 cho kết quả (a) — code đã có ở branch khác — toàn bộ lịch trình rút xuống ~1 tuần.

---

## 3. Bất biến không được phá trong toàn bộ Nhóm A

1. `SCORING_WEIGHTS_V4` giữ nguyên 15 tiêu chí, tổng = 1.00. LNA không được thêm vào.
2. RT primer và TaqMan probe: quality-checked, **không** scored.
3. Batch không được cho kết quả khác single cho cùng input.
4. Mọi text UI bằng tiếng Anh (spec §0).
5. Mọi tính năng mới nằm sau feature flag để rollback được mà không revert commit.
