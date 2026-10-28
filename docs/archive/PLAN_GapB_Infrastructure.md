# PLAN — Nhóm B: Infrastructure (B1 Calibration · B2 Docker · B3 OpenAPI · B4 Session History)

> Nguồn đối chiếu: `SPEC_phase5.md` PART B, `SPEC_phase6.md` PART D, `SPEC_phase3.md` §9.3/§9.5, `SPEC_week1.md` §15/§17.
> Ngày lập: 2026-08-14 · Đi kèm `PLAN_GapA_ScientificCompleteness.md`

---

## 0. Danh sách endpoint của bạn vừa xác nhận chẩn đoán drift

Bạn liệt kê **6 endpoint thực tế**. `SPEC_week1.md` §17 đặc tả **10**:

| Endpoint (spec §17) | Có trong code? | Thuộc phase |
|---|---|---|
| `/api/design` | ✅ | Phase 2 |
| `/api/mirbase/<id>` | ✅ | Phase 1 |
| `/api/blast-check` | ✅ | Phase 3 |
| `/api/export` | ✅ | Phase 4 |
| `/api/benchmark` | ✅ | Phase 7 |
| `/api/health` | ❌ | — |
| `/api/multiplex-check` | ❌ | **Phase 6 PART B** |
| `/api/batch-design` | ❌ | **Phase 8** |
| `/api/batch-status/<id>` | ❌ | **Phase 8** |
| `/api/lna-suggest` | ❌ | **Phase 8** |
| `/api/blast-status` | ⚠️ **có trong code, KHÔNG có trong spec** | — |

**Kết luận audit (trả lời câu hỏi mở ở PLAN nhóm A):** rơi vào trường hợp **(b)+(c)** — không phải branch chưa merge. Phase 6 PART B và Phase 8 **chưa ship**, đồng thời BLAST đã chuyển sang async (`/api/blast-status`) mà spec chưa ghi nhận. Bảng trạng thái Phase trong `SPEC_week1.md` đang sai ở 2 dòng và cần sửa ngay.

`/api/health` thiếu cũng chặn B2: Docker healthcheck và Railway readiness probe đều cần nó.

---

## 1. Thứ tự tối ưu: **B3 → B4 → B2 → B1(chỉ intake)**

Ngược với thứ tự bạn liệt kê. Lý do: B3 là công cụ chẩn đoán cho chính vấn đề drift ở trên, nên nó phải đi trước; B1 thì spec đã ra phán quyết hoãn.

---

## 2. B3 — OpenAPI / Swagger (~1 ngày, làm trước tiên)

**Giá trị thật không phải là "có docs" — mà là ép liệt kê contract thực tế.** Chính hành động viết schema sẽ phát hiện drift như bảng §0. Đây là lý do làm nó trước.

**Cách làm — chọn static, không thêm dependency:**

Spec §0 cấm thêm thư viện ngoài danh sách, và `SPEC_phase5.md` §21 yêu cầu `backend/requirements.txt` không phình. Vì vậy:

- Viết tay `backend/static/openapi.yaml` (OpenAPI 3.1)
- Route `/api/docs` trả một trang HTML nhúng Swagger UI **từ CDN** → **zero backend dependency**
- Route `/api/openapi.yaml` serve file tĩnh

Tránh `flask-smorest`/`apispec`: chúng buộc refactor toàn bộ route sang marshmallow schema — chi phí lớn hơn giá trị ở giai đoạn này.

**Nguồn schema có sẵn để chép, không phải bịa:**

- `SPEC_week1.md` §20 — data contract đầy đủ của `POST /api/design` (request + response)
- `SPEC_phase3.md` §8.9 — response BLAST kèm `cross_species_excluded`, `hits_truncated`
- `SPEC_week1.md` §17 — bảng route map

**Test chống drift tái diễn (quan trọng hơn cả docs):**

```python
def test_openapi_matches_registered_routes():
    """Mọi route /api/* đăng ký trong Flask phải có trong openapi.yaml, và ngược lại."""
    registered = {r.rule for r in app.url_map.iter_rules() if r.rule.startswith("/api")}
    documented = set(yaml.safe_load(open("static/openapi.yaml"))["paths"])
    assert registered == documented
```

Test này biến spec drift từ lỗi âm thầm thành lỗi CI. Nó là deliverable giá trị nhất của B3.

---

## 3. B4 — Session history (~2 ngày)

### ⚠️ Đề xuất của bạn khác spec: localStorage vs IndexedDB

`SPEC_week1.md` §15 đã chốt **IndexedDB** (`historyDB.js`, `DB_NAME="hglab_primer_history"`, `MAX_ENTRIES=100`). Tôi nghiêng về giữ IndexedDB, ba lý do kỹ thuật:

1. **Quota.** Một record chứa `results[]` đầy đủ — top3 candidates × 15 sub-score, probe, BLAST hits, protocol advisory. Ước tính 50–200 KB/record. 100 record → 5–20 MB. localStorage quota chỉ ~5 MB → **`QuotaExceededError` là chắc chắn**, không phải rủi ro.
2. **Blocking.** localStorage đồng bộ. `JSON.stringify` một batch 50 miRNA rồi ghi sẽ **freeze UI thread** đúng lúc user vừa xem xong kết quả.
3. **Batch.** Schema §15 có `type: "single" | "batch"`. Nếu làm localStorage bây giờ thì khi A1 batch lên sẽ phải viết lại — làm hai lần.

localStorage chỉ hợp nếu chấp nhận lưu **summary** (không lưu `results` đầy đủ) và re-run khi load. Đó là sản phẩm khác, kém hơn.

**Nếu vẫn muốn nhanh:** làm IndexedDB nhưng cắt scope — chỉ `saveHistory` + `listHistory` + `loadHistory`, hoãn `deleteHistory`/`clearHistory`. Vẫn rẻ hơn viết lại.

### Chi tiết đã có sẵn trong spec — dùng đúng, đừng nghĩ lại

- **Key collision-safe:** `hist_${Date.now()}_${crypto.randomUUID().slice(0,8)}`. `Date.now()` đơn thuần sẽ đụng nhau khi batch auto-save nhiều record trong cùng millisecond.
- **FIFO eviction atomic:** `put` + `getAllKeys` + `delete` phải **trong cùng một readwrite transaction**. Tách ra sẽ race và vượt `MAX_ENTRIES`.
- **`_dbPromise = null` khi reject** — nếu không, một lần mở DB lỗi sẽ poison vĩnh viễn cả session (promise hỏng bị cache lại).
- **Auto-save non-blocking:** `saveHistory().catch(() => {})` sau khi navigate. Lỗi lưu lịch sử **không bao giờ** được chặn hiển thị kết quả.

**Cạm bẫy thêm:** Safari private mode và một số cấu hình chặn IndexedDB. Bọc toàn bộ module trong feature-detect, fail sang no-op silently — panel history ẩn đi, tool vẫn chạy bình thường.

---

## 4. B2 — Docker + deploy (~2–3 ngày)

### ✅ Tiền đề "BLAST DB ~GB" không còn đúng — bài toán đã tự biến mất

`SPEC_phase3.md` §9.5 (v1.9) đã **loại Ensembl human cDNA** khỏi pipeline. Storage benchmark thực tế còn lại:

| Component | File gz | Giải nén | BLAST index |
|---|---|---|---|
| miRBase mature.fa multi-species (~48K seq) | ~0.6 MB | ~2 MB | **~2 MB** |

**~2 MB, không phải ~GB.** Nghĩa là **không cần cache strategy, không cần volume mount, không cần download lúc runtime**. Bake thẳng DB vào image lúc build.

Lý do khoa học của việc loại Ensembl (§8.2 v1.9): DNase treatment trước RT loại toàn bộ genomic DNA và unspliced RNA → template còn lại chỉ là mature miRNA → off-target risk giới hạn ở miRNA family cross-reactivity, đã được miRBase multi-species cover đủ. Ensembl chỉ tạo false positive mRNA hits và chiếm hết `BLAST_MAX_HITS_RETURNED`.

### Multi-stage Dockerfile

```dockerfile
# ---- Stage 1: build BLAST DB (chạy 1 lần, cache theo layer) ----
FROM ncbi/blast:2.14.0 AS blastdb
WORKDIR /build
COPY backend/scripts/build_blast_db.py .
RUN python build_blast_db.py            # tải mature.fa + makeblastdb + metadata.json
# script đã xoá FASTA gốc sau makeblastdb, chỉ giữ .nhr/.nin/.nsq

# ---- Stage 2: frontend ----
FROM node:20-slim AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- Stage 3: runtime ----
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ncbi-blast+ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=blastdb /build/blast_db/ ./backend/data/blast_db/
COPY --from=frontend /app/dist/ ./backend/static/
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:8000", "backend.app:app"]
```

**Bốn quyết định cần chốt rõ, đừng để mặc định:**

1. **`-w 1 --threads 8`, không phải `-w 4`.** Trực tiếp nối với cạm bẫy A1: job store của batch/BLAST async nằm in-process. Nhiều worker → poll `/api/batch-status` hoặc `/api/blast-status` trúng worker không giữ job → **404 ngẫu nhiên, rất khó debug**. Một worker + nhiều thread là đúng cho workload này (I/O-bound, ≤50 miRNA).
2. **`/api/health` phải tồn tại trước** (hiện đang thiếu). Trả `{status, blast_db: {build_date, sequences_count}, kb_version}` — để healthcheck cũng phát hiện luôn DB stale (`BLAST_DB_STALE_WARN_DAYS = 90`).
3. **`mirbase.db` không commit** (.gitignore). Container phải chạy `seed_db.py` ở build stage, cùng chỗ với BLAST DB.
4. **Pin version.** `ncbi-blast+` từ apt của debian-slim có thể lệch `2.14.0+` mà `metadata.json` ghi. Pin cụ thể hoặc ghi version thực vào health response.

### docker-compose.yml — chỉ để dev/collaborator

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      - FLASK_ENV=development
    volumes:
      - ./backend:/app/backend        # hot reload code
      - blast_db:/app/backend/data/blast_db   # KHÔNG rebuild DB mỗi lần restart
volumes:
  blast_db:
```

**Lưu ý deploy (§9.5):** Railway là target chính. **Render free tier có ephemeral filesystem** → mất DB khi restart → không dùng được. Cloud Run stateless cần mount volume → phức tạp hơn giá trị.

---

## 5. B1 — Calibration module: **HOÃN có chủ đích, không phải bỏ quên**

### Spec đã ra phán quyết BLOCKED, kèm khảo sát literature

`SPEC_phase6.md` **PART D.1** ghi rõ kết luận: *"không có bộ dữ liệu công bố nào cho calibration hợp lệ."* Lý do từng nguồn:

| Nguồn | Vì sao không dùng được |
|---|---|
| **Wang17** | Không có bảng efficiency per-assay, chỉ có range 0.93–1.14 |
| **Busk14** | Table 1 là tham số scoring, chỉ 1 ví dụ efficiency 96% |
| **Kunwar23** Table 2 | 24 miRNA **có** efficiency, nhưng (a) assay Qiagen-LNA/TaqMan → **feature-label mismatch** (feature là primer của tool, label là primer khác); (b) toàn bộ nằm trong 85–100%, SD 3.9pp, **không có ca thất bại** → **survivorship bias** |

Vấn đề (b) là chỗ dễ đánh giá nhầm nhất. Hồi quy trên label không có phương sai và không có ca xấu sẽ cho ra tương quan **thuần nhiễu** — nhưng nó vẫn ra một con số r trông có vẻ hợp lý. Đây là loại sai lầm không tự báo lỗi.

### Điều KHÔNG bị block — làm ngay, rẻ (~1 ngày)

Tách đôi B1. Phần **re-weighting** bị block; phần **thu thập dữ liệu** thì không, và làm trước sẽ tiết kiệm rất nhiều công wet-lab:

1. **`calibration/benchmark_assays.json`** — tạo file với schema §B.2 đã chốt, `assays: []` rỗng, `status: "blocked"`, kèm `blocked_reason` trỏ SPEC_phase6 D.1. Nạp 24 dòng Kunwar23 vào section **`reference`** riêng với `verified: false` — để tham khảo, **không bao giờ vào fit-set**.
2. **`POST /api/calibration/submit`** (sau feature flag `USE_CALIBRATION_INTAKE=False`) — nhận record đúng schema §B.2, validate Pydantic-style, append vào JSON. Chưa cần re-weighting logic.
3. **Form nhập liệu tối giản** — để bạn/cộng tác viên nhập efficiency ngay khi có kết quả chạy, thay vì gõ JSON tay 3 tháng sau.

### Điều quan trọng nhất phải quyết định TRƯỚC khi chạy wet-lab

`SPEC_phase6.md` **D.2** đặt ra yêu cầu mà nếu bỏ sót thì **toàn bộ dữ liệu wet-lab sẽ vô dụng và không cứu được bằng phân tích**:

> **Phải cố ý đưa vào cả thiết kế XẤU.**

Bản năng tự nhiên khi làm thí nghiệm là chỉ chạy primer top-1 mà tool đề xuất. Làm vậy thì label sẽ dồn hết vào 90–105% — chính xác là survivorship bias đã loại Kunwar23. Hồi quy cần thấy primer **thất bại** mới học được tiêu chí nào thật sự dự báo.

Thiết kế thí nghiệm tối thiểu:

| Yêu cầu (D.2) | Cụ thể |
|---|---|
| Primer khớp tool | Đo trên **chính primer tool thiết kế**, không phải primer thương mại |
| Có phương sai + ca xấu | Mỗi miRNA chạy **top-1 VÀ một candidate điểm thấp** (hoặc primer cố ý vi phạm 1 tiêu chí) |
| N | ≥ 20–30 assay, đa dạng GC/length/họ |
| Chuẩn hoá | Cùng master-mix, cùng máy, standard curve ≥5 điểm, `efficiency = 10^(−1/slope) − 1`, báo cả R² |
| Ghi điều kiện | Na/Mg/dNTP — để khớp mô hình Tm |

**Gợi ý bố trí rẻ nhất:** 15 miRNA × 2 primer (top-1 + low-score) = 30 assay, đạt cả N lẫn label spread trong một lần chạy. Chi phí gần như gấp đôi 15 assay, nhưng khác biệt giữa *có dữ liệu dùng được* và *không*.

### Cổng mở lại (D.3) — đã có sẵn trong script, đừng nới

Chỉ chạy `calibrate_weights.py` và tin kết quả khi **tất cả**:

- `N ≥ 20` primer-của-tool có efficiency
- Label spread đủ: **SD > ~5pp, có ca < 90%**
- `LOOCV_RMSE(w_calibrated) < LOOCV_RMSE(V4)` — cải thiện thật, không phải train fit
- Giữ `w_floor` (0.005) cho tiêu chí lõi Tm/dimer/hairpin — bảo toàn tri thức sinh học

Chưa đạt → **giữ V4**, chỉ xuất báo cáo tương quan như định hướng nghiên cứu. Không ghi đè.

---

## 6. Lịch trình tổng hợp

| Bước | Nội dung | Ước lượng | Điều kiện xong |
|------|----------|-----------|----------------|
| B3 | `openapi.yaml` + `/api/docs` + route-sync test | 1 ngày | `test_openapi_matches_registered_routes` pass |
| — | Thêm `/api/health`; sửa bảng Phase trong spec | 0.5 ngày | Spec khớp code |
| B4 | `historyDB.js` (IndexedDB) + HistoryPanel | 2 ngày | Refresh page → kết quả còn; 100 record không vỡ quota |
| B2 | Dockerfile multi-stage + compose + healthcheck | 2–3 ngày | `docker run` → `/api/design` chạy được từ máy sạch |
| B1a | Schema + intake endpoint (flag off) | 1 ngày | File `benchmark_assays.json` tồn tại, status blocked |
| B1b | Re-weighting | **HOÃN** | Chờ N≥20 wet-lab đạt D.3 |

**Xen với nhóm A:** B3 làm ngay tuần này (nó là công cụ audit). B4 nên làm **cùng đợt với A1 batch** vì schema history đã có field `type: "single"|"batch"` — làm một lần cho cả hai. B2 làm **sau khi A1/A3 merge** để image chứa đủ tính năng.

---

## 7. Bất biến bổ sung cho nhóm B

1. `backend/requirements.txt` **không phình** — công cụ calibration là offline tooling riêng (`calibration/requirements.txt`).
2. Không bao giờ fit trên record `verified: false`.
3. Không suy trọng số từ dữ liệu mô phỏng hay ước lượng. N nhỏ → nói thẳng "chưa đủ".
4. Lỗi lưu history không được chặn hiển thị kết quả.
5. Mọi endpoint mới phải có mặt trong `openapi.yaml` cùng commit (được CI ép bằng route-sync test).
