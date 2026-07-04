# SPEC_phase7.md — HG Lab Stem-loop RT-qPCR Primer Designer
# Phase 7: Production hardening & scientific visibility
#   PART A — BLAST database build/bootstrap · PART B — Family discrimination canonical data
#   PART C — Family specificity map (UI) · PART D — Normalization advisor
#   PART E — MIQE validation checklist export · PART F — Benchmark vs miRprimer/miPrimer (UI)
# Phiên bản 1.0 — 2026-07-04 · Sync: algorithm v3.1, SCORING_WEIGHTS_V4 (15 tiêu chí),
#   SPEC_phase3 v2.1, SPEC_phase4 v1.1, SPEC_phase5 v1.0, SPEC_phase6 v1.0, RESEARCH_QUESTIONS_UX.md

---

## CHANGELOG

### v1.0 — 2026-07-04 — Phase 7 khởi tạo
- **Bối cảnh:** 6 hạng mục "functional nhưng chưa hoàn tất / chưa hiển thị" còn lại sau Phase 3–6. Mỗi hạng mục đã có **module hoặc script sẵn** — Phase 7 KHÔNG viết lại thuật toán, chỉ **bootstrap dữ liệu, nâng nguồn lên canonical, và đưa data sẵn-có ra UI**. Nguyên tắc xuyên suốt: *tái dùng, không trùng lặp*.
- **Thứ tự thực hiện (chốt với Vuong 2026-07-04):** tuần tự **A → B → C → D → E → F**. Lý do dependency: (A) BLAST DB là blocker cho smoke test/benchmark specificity; (B) family data canonical là input cho (C) family map; (D)(E)(F) độc lập, xếp theo giá trị UX giảm dần.
- **PART A — BLAST database build/bootstrap:** `build_blast_db.py` đã có (SPEC_phase3 §9.5) nhưng DB **chưa build** → endpoint `/api/blast-check` raise `FileNotFoundError` (v2.0). Phase 7: script bootstrap tự động khi deploy + `/api/blast-status` + Makefile target + CI artifact cache. **Không** đổi logic BLAST.
- **PART B — Family discrimination canonical data:** `mirbase_family_overhangs.json` hiện build bằng **seed-based grouping** (placeholder, SPEC_phase3 §5.5) do URL HTTPS miFam.dat trả HTTP 500. Web-verified 2026-07-04: **miFam.dat vẫn còn qua FTP mirror + archived copy**; **Rfam 15 (2025)** và **MirGeneDB 2.1** là nguồn family canonical thay thế. Phase 7: `build_family_db.py` thử **multi-source fallback chain** (FTP miFam → archived miFam → seed-based), ghi `provenance` vào JSON. **Không** đổi `family_crossreactivity.py` (schema giữ nguyên).
- **PART C — Family specificity map (UI):** `family_crossreactivity.py` đã tính đủ data; response `/api/design` đã có `family_cross_reactivity` (SPEC_phase3 §5). UI hiện chỉ bảng text. Phase 7: React component `FamilySpecificityMap.jsx` (SVG, không thêm lib) — đọc data sẵn có, **không gọi backend mới**.
- **PART D — Normalization advisor:** `protocol_kb.json` đã có P7/P8 (SPEC_phase6 §E.2); `reference_mirnas.json` đã có `cel-miR-39-3p`. Chưa có module đề xuất **reference miRNA theo loại mẫu**. Phase 7: `normalization_advisor.py` (rule-based, citation-backed, advisory-only) + `NormalizationAdvisor.jsx`. **Không** đổi scoring.
- **PART E — MIQE validation checklist export:** `export.py` đã có PDF/CSV (SPEC_phase4 §8). Chưa có **checklist nghiệm thu** (NTC/no-RT/melting/standard curve). Phase 7: mở rộng `export.py` thêm section/sheet "Validation checklist" — dùng `reportlab`/`csv` sẵn có, **không thêm dependency**.
- **PART F — Benchmark vs miRprimer/miPrimer (UI):** `run_benchmark.py` + `benchmark_assays.json` đã có (SPEC_phase6 §C.3). Kết quả chưa hiển thị. Phase 7: endpoint `GET /api/benchmark` serve **kết quả precomputed** (JSON tĩnh, không chạy benchmark runtime) + `BenchmarkPanel.jsx`.
- Nguồn web-verified 2026-07-04: miFam.dat FTP mirror còn sống; Rfam 15 sync miRBase; MirGeneDB 2.1 standardized nomenclature (§2).

---

## 0. Hướng dẫn cho Claude Code

1. **Đọc trước khi code:**
   - SPEC_phase3 **§5 (family), §8–9 (BLAST + kiến trúc cache/circuit breaker/rate limit), §13 (frontend off-target)** — Phase 7 PART A/B/C build trực tiếp trên đây.
   - SPEC_phase4 **§8 (export PDF/CSV)** — PART E mở rộng.
   - SPEC_phase5 **PART A (protocol advisor)** + SPEC_phase6 **§E.2 (P7/P8 normalization KB)** — PART D mở rộng.
   - SPEC_phase6 **§C.3 (benchmark harness)** — PART F đọc output.
   - `backend/algorithm/specificity_check/family_crossreactivity.py`, `backend/scripts/build_family_db.py`, `backend/scripts/build_blast_db.py`, `backend/routes/export.py`, `backend/data/reference_mirnas.json`, `backend/data/protocol_kb.json`, `benchmark/run_benchmark.py`, `benchmark/benchmark_assays.json`.
2. **Bất biến (tuyệt đối):**
   - **Không đổi `SCORING_WEIGHTS_V4`** (15 tiêu chí, tổng 1.00). PART D là advisory, KHÔNG vào weighted-sum.
   - **Không đổi thuật toán lõi** (thermodynamics, family Hamming/ΔTm, BLAST risk classification Ye12/Kwok90).
   - **Không thêm runtime dependency mới.** Frontend giữ React 18 + Vite + Tailwind + React Router + Axios — **không thêm lib chart/D3** (family map + benchmark chart vẽ bằng SVG thuần). Backend giữ `primer3-py`, `biopython`, `numpy`, `flask-limiter`, `reportlab`. FTP fetch trong PART B dùng `urllib`/`ftplib` chuẩn thư viện.
   - **Không thay đổi schema** `family_cross_reactivity` trong response `/api/design` — PART B chỉ đổi *nguồn* data, PART C chỉ *đọc*.
3. **Trung thực khoa học (bắt buộc):** mọi advisory/benchmark phải có `source_doi` + `verified`; benchmark ghi rõ **giới hạn so sánh khác hoá học** (Chen stem-loop vs miRprimer/miPrimer). KHÔNG bịa số. Family data ghi `provenance` (canonical vs seed-based fallback) để user biết mức tin.
4. **Tooling (theo Vuong):**
   - **Brainstorm/superpower:** trước mỗi quyết định thiết kế chưa chốt trong spec (vd: layout family map, cách phân tầng validation checklist) → dùng skill `brainstorming`. Trước mỗi `git commit` → chạy **Superpower security check** (đặc biệt endpoint mới `/api/blast-status`, `/api/benchmark` — kiểm injection/path traversal; `build_family_db.py` fetch FTP — kiểm SSRF/URL whitelist).
   - **Playwright E2E:** mỗi PART có UI (C, D, E, F) phải có test `e2e/*.spec.js`. Sau mỗi thay đổi UI có ý nghĩa → chạy Playwright suite liên quan; suite cũ phải còn xanh.
   - **TDD:** nếu có skill `test-driven-development`, viết test trước cho `normalization_advisor.py` và multi-source fetch    của `build_family_db.py`.
   - **hrm-algorithm-validator:** KHÔNG áp dụng ở đây (Phase 7 không đụng thuật toán melting/HRM).
5. **Output UI 100% English.** Comment code có thể tiếng Việt.
6. **Constants tập trung** `backend/algorithm/constants.py`, mỗi hằng số có `[NGUỒN]`. Frontend đọc ngưỡng/label từ response, không hardcode.
7. Mỗi module backend mới có pytest; feature bật/tắt qua constant để A/B khi hợp lý.

---

## 1. Tổng quan Phase 7

Phase 3–6 đã hoàn thiện **năng lực khoa học** (bound fraction, family, BLAST risk model, probe, multiplex, advisor, calibration-blocked). Còn lại một lớp "**last-mile**": có logic/script nhưng **chưa chạy được end-to-end trong production** hoặc **chưa ra tới mắt người dùng**. Phase 7 đóng lớp này.

**Nguyên tắc định hình:** mỗi feature = *tái dùng module có sẵn* + *một mảnh còn thiếu* (data bootstrap, nguồn canonical, hoặc UI). Tổng effort nhỏ, giá trị hiển thị lớn.

| PART | Feature | Cái ĐÃ có (tái dùng) | Mảnh THIẾU (Phase 7 làm) | Giá trị |
|---|---|---|---|---|
| A | BLAST DB build | `build_blast_db.py`, `blast_offtarget.py`, route, `useBlastCheck`, `OffTargetPanel` | DB chưa build → bootstrap + status endpoint + deploy hook | Blocker cho specificity thực |
| B | Family canonical data | `build_family_db.py`, `family_crossreactivity.py`, JSON schema | Nguồn seed-based → multi-source canonical + `provenance` | Đúng phân loại miRBase |
| C | Family specificity map | `family_crossreactivity.py` data, response field | UI chỉ text → SVG specificity map | ★★★ UX (A3) |
| D | Normalization advisor | `protocol_kb.json` P7/P8, `reference_mirnas.json` | Module reference-miRNA theo sample-type | ★★★ UX (B1) |
| E | MIQE validation checklist | `export.py` PDF/CSV | Checklist nghiệm thu NTC/no-RT/melting/curve | ★★ UX (B4) |
| F | Benchmark UI | `run_benchmark.py`, `benchmark_assays.json` | Endpoint serve precomputed + panel | Vị thế tool (C3) |

**Thứ tự thực hiện:** A → B → C → D → E → F (dependency + giá trị, §CHANGELOG).

**Thời gian mục tiêu:** A ~0.5 ngày · B ~1 ngày · C ~1.5 ngày · D ~1 ngày · E ~1 ngày · F ~1 ngày.

---

## 2. Nguồn tham chiếu (thêm Phase 7)

**Web-verified 2026-07-04 (family data — PART B):**
- **[miFam-FTP]** miRBase family classification `miFam.dat` vẫn phân phối qua FTP mirror `ftp://mirbase.org/pub/mirbase/CURRENT/miFam.dat.gz` (chỉ URL web-based HTTPS `https://www.mirbase.org/download/miFam.dat` trả HTTP 500). Family được cluster single-linkage trên precursor rồi curate tay theo common ancestor.
- **[Rfam15]** Rfam 15 (2025): **hoàn tất đồng bộ hoá microRNA của miRBase vào Rfam** → nguồn family canonical thay thế, có covariance model. DOI 10.1101/2024.09.23.614430 (preprint) — *verify accession trước production.*
- **[MirGeneDB]** MirGeneDB 2.1/3.0: nomenclature **chuẩn hoá**, orthologue nhận diện được across-species, curate mature + star nghiêm ngặt. Fromm et al. — nguồn family canonical cấp cao (nghiêm hơn miRBase, loại mirtron/non-canonical).

**Normalization/validation (PART D/E) — kế thừa từ RESEARCH_QUESTIONS_UX.md §B (đã PubMed-verified):**
- **[Hellemans14]** Hellemans J, Vandesompele J. *Methods Mol Biol.* 2014. DOI [10.1007/978-1-4939-0733-5_3](https://doi.org/10.1007/978-1-4939-0733-5_3) — geNorm/NormFinder; panel lớn → global-mean normalization.
- **[Hacimoto24]** *PLoS One* 2024. DOI [10.1371/journal.pone.0306657](https://doi.org/10.1371/journal.pone.0306657) — chọn 3 miRNA ổn định nhất bằng đa thuật toán.
- **[Fujimoto18]** *Forensic Sci Int Genet* 2018. DOI [10.1016/j.fsigen.2018.08.010](https://doi.org/10.1016/j.fsigen.2018.08.010) — reference phụ thuộc loại mẫu.
- **[Liang18]** *PLoS One* 2018. DOI [10.1371/journal.pone.0194436](https://doi.org/10.1371/journal.pone.0194436) — reference theo tissue.
- **[McDonald11]** *Clin Chem* 2011. DOI [10.1373/clinchem.2010.157198](https://doi.org/10.1373/clinchem.2010.157198) — hemolysis lệch miR-16/miR-451a.
- **[Tan15]** *Sci Rep* 2015. DOI [10.1038/srep09430](https://doi.org/10.1038/srep09430) — spike-in cel-miR-39 giảm bias chiết tách.
- **[MIQE09]** Bustin SA et al. *Clin Chem* 2009 — chuẩn báo cáo qPCR (NTC/no-RT/standard curve/efficiency/R²/melting). (đã dùng SPEC_phase4 §8.3.)

---

# PART A — BLAST database build / bootstrap (SPEC_phase3 §9)

## A.1 Rationale & tình trạng
`build_blast_db.py` tồn tại và đúng (SPEC_phase3 §9.5): tải `mature.fa` multi-species → `makeblastdb` → `metadata.json` → verify `blastdbcmd -info`. `blast_offtarget.py` (v2.0) **raise `FileNotFoundError` khi DB vắng mặt** → route trả HTTP 500 → `OffTargetPanel` hiện error state. Đây là hành vi đúng (không false-SAFE) nhưng nghĩa là: **cho tới khi DB được build, feature off-target không dùng được**. Storage rất nhỏ (~2 MB miRBase-only, SPEC_phase3 §9.5 v1.9) → không có rào cản disk.

**Phase 7 làm:** biến "build thủ công" thành "**bootstrap tự động + observable**". Không đổi logic BLAST.

## A.2 Deliverables
1. **Deploy bootstrap hook** — build DB khi container khởi động lần đầu nếu chưa có (idempotent).
2. **`GET /api/blast-status`** — endpoint nhẹ (không rate-limit) trả trạng thái DB để frontend quyết định enable/disable nút "Check off-target".
3. **Makefile / npm-style target** — `make build-blast-db` để build thủ công local.
4. **CI artifact cache** — cache DB build trong GitHub Actions để smoke test hsa-miR-21-5p (SPEC_phase3 §9.7) chạy được mà không rebuild mỗi lần.

## A.3 Bootstrap hook (idempotent)
**File:** `backend/scripts/bootstrap_blast_db.py`
```python
"""
Chạy 1 lần lúc container start (Railway release command / entrypoint).
1. Kiểm tra tồn tại backend/data/blast_db/mirbase_multi.nhr (+ .nin + .nsq).
2. Nếu đủ 3 file + metadata.json hợp lệ → SKIP (log "BLAST DB present, skipping build").
3. Nếu thiếu → gọi build_blast_db.main() (đã có §9.5).
4. Nếu build fail (network mature.fa down) → log ERROR, KHÔNG crash app.
   App vẫn start; /api/blast-status trả available=false; /api/design không ảnh hưởng.
Idempotent: chạy lại nhiều lần an toàn.
"""
```
- **Railway:** thêm vào `Procfile` release/start: `python -m scripts.bootstrap_blast_db && python app.py` (hoặc release command riêng nếu Railway hỗ trợ persistent volume — xác nhận lúc deploy).
- **Bất biến:** bootstrap fail KHÔNG được chặn `/api/design` (pipeline chính độc lập BLAST — SPEC_phase3 §8.1).

## A.4 `GET /api/blast-status`
```python
# routes/blast_check.py — thêm route (không rate-limit, chỉ đọc metadata)
@blast_check_bp.route("/api/blast-status", methods=["GET"])
def blast_status():
    """
    Return: {
      available: bool,               # đủ file .nhr/.nin/.nsq
      sequences_count: int | null,   # từ metadata.json
      build_date: str | null,
      outdated_warning: bool,        # >90 ngày (BLAST_DB_STALE_WARN_DAYS §9.4)
      message: str                   # English, hiển thị được
    }
    """
```
- Không đọc DB nặng — chỉ `os.path.exists` + parse `metadata.json`. Nhanh (<10 ms).

## A.5 Frontend — enable/disable có điều kiện
- `useBlastCheck.js` (đã có, SPEC_phase3 §13): thêm 1 lần gọi `/api/blast-status` lúc mount `OffTargetPanel`.
- Nếu `available=false`: nút "Check off-target" **disabled** + tooltip English "Off-target database is being prepared. Please try again shortly." — thay vì để user bấm rồi nhận HTTP 500.
- Nếu `outdated_warning=true`: giữ badge staleness đã có (§13.6).
- **Không** đổi flow khi `available=true` (giữ nguyên Phase 3).

## A.6 CI (GitHub Actions)
- Mở rộng `test_phase3.yml` (SPEC_phase3 §9.6): thêm step cache DB build key = `blast-db-${{ hashFiles('scripts/build_blast_db.py') }}`.
- Job `smoke-test` (đã có): dùng cached DB nếu hit, build nếu miss. Smoke test hsa-miR-21-5p phải pass (self-hit 100%).
- Unit test scripts vẫn dùng **mock data** (không build DB thật trong unit job — §9.6).

## A.7 Tests
- `backend/tests/scripts/test_bootstrap_blast_db.py`: (a) DB present → skip (mock `os.path.exists`); (b) DB absent + build success → build gọi 1 lần; (c) build fail → không raise, log ERROR.
- `backend/tests/smoke/test_blast_status.py`: `/api/blast-status` trả `available` đúng theo tồn tại file.
- **Playwright** `e2e/blast-status.spec.js`: mock `/api/blast-status` → `available=false` ⇒ nút disabled + tooltip; `available=true` ⇒ nút enabled.

## A.8 PROMPT CLAUDE CODE — PART A
```
Đọc SPEC_phase3 §8–9, §13. KHÔNG đổi logic blast_offtarget.py / risk classification.
1) Tạo backend/scripts/bootstrap_blast_db.py: idempotent, skip nếu DB đủ file, build nếu thiếu,
   fail-soft (log ERROR, không crash app, không chặn /api/design). Test 3 case.
2) Thêm GET /api/blast-status (không rate-limit) đọc metadata.json + os.path.exists, trả
   {available, sequences_count, build_date, outdated_warning, message}. Test tồn tại/vắng mặt DB.
3) Cập nhật useBlastCheck.js gọi /api/blast-status lúc mount OffTargetPanel; disable nút +
   tooltip English khi available=false. Không đổi flow available=true.
4) Cập nhật Procfile/entrypoint chạy bootstrap trước app. Cập nhật test_phase3.yml cache DB build.
5) Playwright e2e/blast-status.spec.js (disabled/enabled). Superpower security check /api/blast-status.
Ràng buộc: English UI; không thêm dependency; smoke test hsa-miR-21-5p self-hit 100% giữ pass.
```

---

# PART B — Family discrimination canonical data (SPEC_phase3 §5.5)

## B.1 Rationale & tình trạng
`mirbase_family_overhangs.json` (367 families, 929 hsa- miRNAs) hiện build bằng **seed-based grouping** — 7-nt seed window (SPEC_phase3 §5.5, algorithm v3.1 §14). Functional: family detection hoạt động, `family_crossreactivity.py` chạy đúng. **Nhưng không canonical:** phân nhóm theo seed ≠ phân loại chính thức miRBase (single-linkage precursor + curate tay theo common ancestor). Ví dụ sai khác: 2 miRNA cùng seed nhưng khác family, hoặc cùng family (paralog) nhưng seed lệch do arm-switch.

**Phát hiện 2026-07-04:** HTTP 500 chỉ ở URL **HTTPS web-based**. miFam.dat vẫn còn qua **FTP** + có nguồn canonical thay thế (Rfam 15, MirGeneDB). → Phase 7 nâng nguồn lên canonical với **fallback chain**, giữ seed-based làm phương án cuối.

## B.2 Multi-source fallback chain
`build_family_db.py` thử tuần tự, dừng ở nguồn đầu tiên thành công:

| Ưu tiên | Nguồn | URL / phương thức | Provenance value |
|---|---|---|---|
| 1 | miFam.dat FTP mirror | `ftp://mirbase.org/pub/mirbase/CURRENT/miFam.dat.gz` (ftplib/urllib) | `mifam_ftp` |
| 2 | miFam.dat archived copy | GitHub raw mirror (whitelist domain — xác minh URL trước, verify checksum) | `mifam_archived` |
| 3 | MirGeneDB families | MirGeneDB download (standardized) — *chỉ nếu Vuong duyệt mapping nomenclature* | `mirgenedb` |
| 4 | Seed-based grouping (fallback hiện tại) | `mature.fa` 7-nt seed window | `seed_based_fallback` |

- **Whitelist domain** cho fetch (SSRF guard): chỉ `mirbase.org`, `raw.githubusercontent.com`, `github.com`, `mirgenedb.org`. Superpower security check bắt buộc.
- **Checksum:** với nguồn archived, verify SHA-256 đã ghi cứng trong script trước khi parse (chống nguồn bị đổi).
- Mỗi nguồn có timeout ngắn (10 s) → fail nhanh sang nguồn sau.

## B.3 Schema — thêm `provenance`, giữ nguyên phần còn lại
Giữ **y hệt** schema `mirbase_family_overhangs.json` hiện tại (family → members → overhang) để `family_crossreactivity.py` KHÔNG đổi. Chỉ thêm block metadata top-level:
```json
{
  "_metadata": {
    "provenance": "mifam_ftp",          // giá trị bảng B.2
    "source_url": "ftp://mirbase.org/pub/mirbase/CURRENT/miFam.dat.gz",
    "build_date": "2026-07-04",
    "families_count": 367,
    "hsa_mirnas_count": 929,
    "canonical": true,                   // false nếu seed_based_fallback
    "verified": false                    // Vuong review trước production
  },
  "families": { ... }                    // schema cũ, KHÔNG đổi
}
```
- `family_crossreactivity.py`: chỉ đọc `families` (bỏ qua `_metadata`) — nếu code cũ đọc top-level trực tiếp, thêm 1 dòng `.get("families", data)` để backward-compat với JSON cũ (không có `_metadata`).

## B.4 Provenance ra UI (mức tin)
- Response `/api/design` field `family_cross_reactivity` thêm `data_provenance` (đọc từ `_metadata.provenance` + `canonical`).
- Frontend (PART C map + text) hiển thị badge nhỏ:
  - `canonical=true` → badge teal "miRBase family (canonical)".
  - `canonical=false` (seed fallback) → badge amber "Seed-based grouping (approximate — canonical source unavailable)".
- Trung thực: user luôn biết family classification đến từ đâu.

## B.5 Regression — không phá seed-based
- Nếu tất cả nguồn canonical fail → **rơi về seed-based y như hiện tại** (không regression). Test: mock 4 nguồn fail → output JSON khớp baseline seed-based hiện có (`canonical=false`).
- Nếu canonical thành công → schema `families` phải **pass cùng bộ test** `family_crossreactivity.py` đang xanh (family detection cho hsa-let-7a / hsa-miR-21-5p không đổi kết quả risk classification cho các case đã có test).

## B.6 Known limitation cập nhật
Kế thừa SPEC_phase3 §5.6 + algorithm v3.1 §14. **Bỏ** limitation "#4 miFam.dat HTTP 500 → seed-based" **nếu** provenance = canonical. Thêm: MirGeneDB (nếu dùng) có nomenclature khác miRBase → cần mapping layer (defer nếu Vuong chưa duyệt, giữ nguồn 1–2).

## B.7 Tests
- `test_build_family_db.py`: (a) FTP success → provenance=mifam_ftp, canonical=true; (b) FTP fail + archived success → mifam_archived; (c) tất cả fail → seed_based_fallback, canonical=false, khớp baseline; (d) checksum mismatch archived → skip sang nguồn sau.
- `test_family_crossreactivity_backward_compat.py`: đọc cả JSON có `_metadata` và JSON cũ (không có) → cùng kết quả.
- **Không** Playwright riêng (data-layer); badge provenance test trong PART C spec.

## B.8 PROMPT CLAUDE CODE — PART B
```
Đọc SPEC_phase3 §5, algorithm v3.1 §14. KHÔNG đổi family_crossreactivity.py logic/schema `families`.
1) Nâng build_family_db.py thành fallback chain 4 nguồn (bảng B.2): miFam FTP → archived (checksum
   SHA-256) → MirGeneDB (chỉ nếu duyệt) → seed-based. Domain whitelist {mirbase.org,
   raw.githubusercontent.com, github.com, mirgenedb.org}, timeout 10s/nguồn.
2) Thêm _metadata block (provenance/canonical/verified/build_date) vào JSON; giữ nguyên `families`.
3) family_crossreactivity.py đọc data.get("families", data) — backward-compat JSON cũ.
4) /api/design field family_cross_reactivity thêm data_provenance {provenance, canonical}.
5) Test 4 case fetch + backward-compat + regression seed-based khớp baseline.
Ràng buộc: KHÔNG bịa checksum (để placeholder + comment "VERIFY before production");
mọi số/nguồn có provenance; verified=false chờ Vuong duyệt; Superpower SSRF check bắt buộc.
```

---

# PART C — Family specificity map (UI · UX A3 ★★★)

## C.1 Rationale & tình trạng
`family_crossreactivity.py` tính đủ: mỗi sibling trong family có Hamming distance (6-nt overhang), ΔTm, risk (IDENTICAL/HIGH/LOW/SAFE). Response `/api/design` đã mang `family_cross_reactivity` (SPEC_phase3 §5). **UI hiện chỉ bảng text** → khó thấy "target khác biệt bao nhiêu so với siblings". Đây là **top-3 UX pain** (RESEARCH_QUESTIONS_UX A3): phân biệt trong họ khác 1 nt (let-7, miR-200).

**Phase 7 làm:** component **specificity map** đọc data sẵn có, KHÔNG backend mới, KHÔNG thêm lib (SVG thuần).

## C.2 Thiết kế map (brainstorm trước khi code)
> Trước khi chốt layout: chạy skill `brainstorming` — cân nhắc 2–3 kiểu (radial distance map vs horizontal ranked bars vs grid heatmap). Spec đề xuất **radial distance map** làm mặc định; brainstorm để xác nhận/điều chỉnh.

**Radial distance map (đề xuất):**
- **Tâm** = target miRNA (RT overhang 6 nt).
- **Mỗi sibling** = 1 điểm; **bán kính** ∝ discrimination (Hamming + ΔTm → khoảng cách): gần tâm = nguy hiểm (khó phân biệt), xa = an toàn.
- **Màu điểm** theo risk (consistent với `RISK_STYLE` có sẵn — SPEC_phase3 §13): IDENTICAL đỏ, HIGH cam, LOW amber, SAFE teal.
- **Vòng ngưỡng** (dashed): vòng "HIGH risk zone" (Hamming=1 & ΔTm<5°C) để mắt thấy ngay sibling nào lọt vùng nguy.
- **Hover/tap sibling** → tooltip: tên sibling, mismatches, ΔTm, risk, overhang sequence (highlight nt khác biệt).
- **Auto-extension flag:** nếu family có HIGH risk & RT overhang được auto-extend 6→8 nt (SPEC_phase3 §5.2) → note "Overhang extended to 8 nt to improve discrimination".

## C.3 Component
**File:** `frontend/src/components/FamilySpecificityMap.jsx`
- Input: prop `familyCrossReactivity` (từ response, không fetch).
- SVG viewBox responsive; không dùng D3/chart lib — tính toạ độ radial bằng JS thuần (góc chia đều siblings, bán kính chuẩn hoá).
- Empty state: nếu `no_family_data` hoặc family chỉ có target → hiện note "No family siblings found — target is unique in this family set." + badge provenance (PART B.4).
- Badge provenance (canonical vs seed-based) hiển thị góc map.
- Đặt trong `PrimerSetCard` expanded panel (cạnh OffTargetPanel) hoặc tab riêng trong ResultsPage (SPEC_phase4 §5) — brainstorm chốt vị trí.
- Giữ **bảng text cũ** làm view thay thế (toggle "Map / Table") — không xoá, người dùng technical vẫn cần số.

## C.4 Accessibility & English
- Mọi text English. Điểm SVG có `<title>` cho screen-reader. Màu risk kèm shape/label (không chỉ dựa màu — colorblind-safe).

## C.5 Tests
- Unit (React Testing Library): render với family 3 siblings → 3 điểm; risk màu đúng; empty state khi no_family_data.
- **Playwright** `e2e/family-map.spec.js`: design hsa-let-7a-5p (family let-7 nhiều siblings) → map render, ≥1 điểm HIGH/LOW trong vùng; toggle Map/Table hoạt động; tooltip hover hiện mismatch. Suite cũ xanh.

## C.6 PROMPT CLAUDE CODE — PART C
```
Đọc SPEC_phase3 §5, §13 (RISK_STYLE), SPEC_phase4 §5 (ResultsPage). KHÔNG thêm lib, KHÔNG backend mới.
0) brainstorming: chốt layout (đề xuất radial distance map) + vị trí đặt (expanded panel vs tab).
1) FamilySpecificityMap.jsx: SVG thuần, radial — tâm=target, bán kính∝discrimination, màu=risk
   (reuse RISK_STYLE), vòng ngưỡng HIGH-zone dashed, tooltip sibling (mismatch/ΔTm/overhang highlight).
2) Empty state (no_family_data / unique); badge provenance (PART B.4 canonical vs seed-based).
3) Toggle Map/Table — giữ bảng text cũ. Colorblind-safe (shape+label, không chỉ màu). English + <title> a11y.
4) Unit test render/empty; Playwright e2e/family-map.spec.js (hsa-let-7a-5p, toggle, tooltip).
Ràng buộc: đọc data từ response family_cross_reactivity — KHÔNG tính lại; suite Playwright cũ giữ xanh.
```

---

# PART D — Normalization advisor (UX B1 ★★★)

## D.1 Rationale & tình trạng
Protocol advisor có sẵn (SPEC_phase5 PART A) + KB `protocol_kb.json` đã có P7 (geNorm/global-mean) và P8 (spike-in biofluid) từ SPEC_phase6 §E.2. `reference_mirnas.json` đã có `cel-miR-39-3p` (spike-in). **Thiếu:** module **riêng** đề xuất **reference/normalizer candidate theo loại mẫu** — hiện advisor chỉ trả rule text chung, chưa map sample-type → danh sách reference miRNA cụ thể để user chọn.

**Phase 7 làm:** `normalization_advisor.py` — rule-based, citation-backed, **advisory-only** (KHÔNG vào scoring). Tái dùng `reference_mirnas.json` + `protocol_kb.json`, không trùng lặp KB.

## D.2 Thiết kế — advisory, không kê đơn
Input: `sample_type` (tissue / plasma / serum / cell-line / FFPE / biofluid-other) + (optional) panel size.
Output: object advisory:
```python
{
  "sample_type": "plasma",
  "recommended_strategy": "spike-in + global-mean",   # từ rule
  "reference_candidates": [                            # từ reference_mirnas.json, lọc theo sample-type
     {"name": "cel-miR-39-3p", "role": "exogenous spike-in", "source_doi": "...", "verified": true},
     {"name": "miR-...", "role": "endogenous candidate", "note": "validate with geNorm/NormFinder"}
  ],
  "cautions": [                                        # sample-specific
     {"text": "Hemolysis skews miR-16/miR-451a in plasma — run hemolysis QC.", "source_doi": "10.1373/clinchem.2010.157198"}
  ],
  "validation_note": "Confirm reference stability with geNorm/NormFinder before use. [Hellemans14]",
  "disclaimer": "Advisory only. Reference selection must be validated experimentally."
}
```
- **Rule base** (mở rộng `protocol_kb.json`, bump `kb_version`), mỗi rule có `source_doi` + `verified`:

| ID | sample_type | recommended_strategy | cautions | Nguồn |
|---|---|---|---|---|
| N1 | tissue / cell-line | endogenous panel (geNorm/NormFinder chọn ≥3 ổn định) | reference phụ thuộc tissue | [Hellemans14][Hacimoto24][Liang18] |
| N2 | plasma / serum / biofluid | exogenous spike-in (cel-miR-39) + global-mean | hemolysis miR-16/451a; plasma>serum cùng cohort | [Tan15][McDonald11] |
| N3 | FFPE / low-input | LNA-enhanced + validate stability | biến thiên chiết tách cao | [Andreasen10] (SPEC_phase5) |
| N4 | large panel / miRNome | global-mean normalization | — | [Hellemans14] |

- **KHÔNG hardcode** reference miRNA trong code — đọc từ `reference_mirnas.json` (thêm field `suitable_sample_types` cho mỗi entry nếu chưa có; `cel-miR-39-3p` → `["plasma","serum","biofluid"]`).

## D.3 Endpoint & tích hợp
- Có thể là field trong response `/api/design` (nếu `sample_type` được gửi ở request) HOẶC endpoint riêng `POST /api/normalization-advice` — **brainstorm chốt** (đề xuất: field trong `/api/design` để không thêm round-trip; advisory rẻ, tính đồng bộ).
- Advisory-only: KHÔNG ảnh hưởng candidate ranking / scoring.

## D.4 Frontend
**File:** `frontend/src/components/NormalizationAdvisor.jsx`
- Hiển thị strategy + reference candidates (chips) + cautions (icon warning) + validation note + disclaimer.
- Link ngoài geNorm/NormFinder (target=_blank, rel noopener).
- Chỉ hiện khi có `sample_type`; nếu user chưa chọn → prompt nhẹ "Select sample type to get normalization guidance."

## D.5 Tests
- `test_normalization_advisor.py`: mỗi sample_type → đúng rule N1–N4; reference candidates lọc đúng từ JSON; mọi rule có source_doi + verified; disclaimer luôn có.
- **Playwright** `e2e/normalization-advisor.spec.js`: chọn sample=plasma → hiện cel-miR-39 spike-in + hemolysis caution; sample=tissue → endogenous + geNorm note.

## D.6 PROMPT CLAUDE CODE — PART D
```
Đọc SPEC_phase5 PART A (advisor), SPEC_phase6 §E.2 (P7/P8), reference_mirnas.json, protocol_kb.json.
Advisory-only — KHÔNG đổi SCORING_WEIGHTS_V4.
0) brainstorming: field trong /api/design vs endpoint riêng (đề xuất field).
1) normalization_advisor.py: rule N1–N4 (bảng D.2), mỗi rule source_doi+verified; reference candidates
   ĐỌC từ reference_mirnas.json (thêm suitable_sample_types nếu thiếu; cel-miR-39-3p→plasma/serum/biofluid).
   Output có cautions sample-specific + validation_note + disclaimer bắt buộc.
2) Bump protocol_kb.json kb_version; thêm N1–N4.
3) NormalizationAdvisor.jsx: strategy + reference chips + cautions + links geNorm/NormFinder + disclaimer.
4) Test mỗi sample_type; Playwright plasma/tissue. English UI.
Ràng buộc: KHÔNG bịa DOI; advisory không vào scoring; disclaimer "validate experimentally" luôn hiển thị.
```

---

# PART E — MIQE validation checklist export (UX B4 ★★)

## E.1 Rationale & tình trạng
`export.py` (SPEC_phase4 §8) đã xuất PDF (`reportlab`) + CSV (`csv`) với thông tin primer MIQE-aligned. **Thiếu:** **checklist nghiệm thu** để user validate assay ướt — NTC, no-RT, melting curve, standard curve ≥5 điểm, efficiency = 10^(−1/slope)−1, R². Đây là bước biến tool từ "chỉ thiết kế" → "thiết kế + nghiệm thu" (RESEARCH_QUESTIONS_UX B4).

**Phase 7 làm:** mở rộng `export.py` thêm section (PDF) + sheet/block (CSV) "Validation checklist". Dùng `reportlab`/`csv` sẵn có, **không thêm dependency**.

## E.2 Nội dung checklist (MIQE09-aligned)
Static checklist (giống nhau mọi assay — là template nghiệm thu, không phụ thuộc primer), có ô tick + trường điền:

| Mục | Tiêu chí chấp nhận | Nguồn |
|---|---|---|
| No-template control (NTC) | Không khuếch đại / Cq ≥ 5 chu kỳ sau lowest standard | [MIQE09] |
| No-RT control | Không tín hiệu (loại genomic DNA / self-priming) | [MIQE09] |
| Melting curve (SYBR) | Single peak; không primer-dimer/non-specific | [MIQE09][Varkonyi-Gasic07] |
| Standard curve | ≥5 điểm, 10-fold dilution | [MIQE09] |
| Efficiency | 90–110% (= 10^(−1/slope)−1) | [MIQE09] |
| R² (linearity) | ≥ 0.98 | [MIQE09] |
| Technical replicates | ≥3; báo Cq SD | [MIQE09] |
| Specificity (this tool) | Off-target risk (BLAST) + family discrimination reviewed | Phase 3 |

- **PDF:** thêm trang/section "Validation Checklist (MIQE-aligned)" — bảng có cột "Criterion / Target / Pass ☐ / Value ___". Màu teal Week 1 (§8.4). Footer disclaimer đã có ("For research use only. Validate primers experimentally.").
- **CSV:** thêm block (sau primer rows) `# VALIDATION CHECKLIST` với cột `Item, Acceptance_Criterion, Reference, Pass, Measured_Value` (2 cột cuối để trống cho user điền). Excel-friendly `\r\n` (đã có §8.3).
- **Bao gồm giá trị assay-specific đã tính:** off-target risk summary + family discrimination worst-case (từ response) để checklist "Specificity" auto-fill mức risk, còn lại user điền tay.

## E.3 Không phá export cũ
- Checklist là **section thêm**, không đổi cột primer hiện có. Format whitelist (`pdf`/`csv`) giữ nguyên; filename sanitize server-side giữ nguyên (SPEC_phase4 §8, algorithm v3.1 B3 `..` collapse).
- Có thể thêm query param `include_checklist=true` (default true) để A/B nếu cần.

## E.4 Tests
- `test_export_checklist.py`: PDF bytes chứa "Validation Checklist"; CSV có block `# VALIDATION CHECKLIST` + 8 mục; specificity row auto-fill từ mock response; format whitelist vẫn chặn input lạ.
- **Playwright** `e2e/export-checklist.spec.js`: export PDF + CSV → file tải về (Blob), reuse `export.spec.js` cũ; kiểm CSV chứa checklist header.

## E.5 PROMPT CLAUDE CODE — PART E
```
Đọc SPEC_phase4 §8 (export.py PDF/CSV), algorithm v3.1 B3 (sanitize). KHÔNG thêm dependency.
1) export.py: thêm section "Validation Checklist (MIQE-aligned)" — 8 mục bảng E.2, mỗi mục
   Criterion/Target/Reference/Pass☐/Value. PDF (reportlab table, teal), CSV (# VALIDATION CHECKLIST block,
   cột Pass+Measured_Value để trống). Auto-fill Specificity row từ off-target + family worst-case response.
2) include_checklist query param default true; giữ nguyên cột primer + sanitize + format whitelist.
3) test_export_checklist.py (PDF chứa header, CSV 8 mục, auto-fill, whitelist giữ chặn).
4) Playwright export-checklist.spec.js (PDF+CSV tải về, CSV có checklist). English.
Ràng buộc: KHÔNG đổi export primer cũ; disclaimer "Validate experimentally" giữ; Superpower check /api/export.
```

---

# PART F — Benchmark vs miRprimer/miPrimer trong UI (SPEC_phase6 §C.3)

## F.1 Rationale & tình trạng
`benchmark/run_benchmark.py` + `benchmark/benchmark_assays.json` đã có (SPEC_phase6 §C.3): panel ≥50 miRNA, gọi `/api/design` + miRprimer, so Tm/GC/dimer/specificity/success/speed → `compare_tools.md`. **Thiếu:** kết quả chưa ra UI → user không thấy vị thế tool (RESEARCH_QUESTIONS_UX C3).

**Phase 7 làm:** serve **kết quả precomputed** (JSON tĩnh, KHÔNG chạy benchmark runtime — nặng, phụ thuộc Ruby miRprimer) + `BenchmarkPanel.jsx`. Benchmark chạy offline (CI/local), commit kết quả JSON.

## F.2 Kiến trúc — precomputed, không runtime
- `run_benchmark.py` (đã có) chạy **offline** → xuất `benchmark/benchmark_results.json` (bên cạnh `compare_tools.md`), commit vào repo. Schema:
```json
{
  "_metadata": {
    "run_date": "2026-07-04", "panel_size": 52,
    "tool_version": "algo-frozen-v1.0",
    "comparison_note": "Different chemistry (Chen stem-loop vs miRprimer/miPrimer). Compares DESIGN characteristics, not experimental performance.",
    "verified": false
  },
  "metrics": {
    "forward_tm":   {"this_tool": {...}, "mirprimer": {...}, "miprimer": {...}},
    "gc_percent":   {...}, "self_dimer_dg": {...}, "hetero_dimer_dg": {...},
    "predicted_specificity": {...}, "design_success_rate": {...}, "speed_ms": {...}
  },
  "per_assay": [ {"mirna": "hsa-miR-21-5p", "this_tool": {...}, "mirprimer": {...}}, ... ]
}
```
- **`GET /api/benchmark`** (không rate-limit, đọc file tĩnh) trả JSON trên. Nếu file thiếu → `{available: false}` (không crash).

## F.3 Frontend — trung thực về giới hạn
**File:** `frontend/src/components/BenchmarkPanel.jsx`
- **Banner giới hạn (bắt buộc, đầu panel):** "Design-characteristic comparison, not experimental performance. Tools use different chemistries." — hiển thị `comparison_note` từ metadata. Không được ẩn.
- Metric summary: bảng/grouped bars (SVG thuần, **không thêm chart lib**) — mỗi metric so 3 tool (this_tool / miRprimer / miPrimer). miPrimer nếu không chạy được → hiển thị "N/A (compared via published examples)" (SPEC_phase6 §C.3).
- Panel size + run_date + tool_version badge; `verified=false` → badge "Preliminary — pending review".
- Đặt trong trang riêng `/benchmark` (link từ About/footer) — KHÔNG chèn vào results per-assay (benchmark là tool-level, không assay-level).

## F.4 Tests
- `test_benchmark_endpoint.py`: file có → trả metrics; file thiếu → `available=false`; metadata có comparison_note.
- **Playwright** `e2e/benchmark.spec.js`: mở `/benchmark` → banner giới hạn hiển thị (không ẩn được); ≥1 metric render; miPrimer N/A xử lý đúng.

## F.5 PROMPT CLAUDE CODE — PART F
```
Đọc SPEC_phase6 §C.3 (run_benchmark.py, benchmark_assays.json). KHÔNG chạy benchmark runtime; KHÔNG thêm lib.
1) run_benchmark.py xuất thêm benchmark_results.json (schema F.2) + _metadata comparison_note + verified=false.
   Commit kết quả (offline run).
2) GET /api/benchmark (không rate-limit) đọc file tĩnh; thiếu file → {available:false}, không crash.
3) BenchmarkPanel.jsx tại route /benchmark: banner giới hạn BẮT BUỘC (comparison_note, không ẩn được),
   grouped bars SVG thuần 3 tool, miPrimer N/A, badge verified. Link từ footer/About.
4) test_benchmark_endpoint.py + Playwright benchmark.spec.js (banner + metric render).
Ràng buộc: KHÔNG bịa số benchmark (chạy thật offline hoặc để verified=false + placeholder rõ ràng);
banner "different chemistry / design not performance" luôn hiển thị; English UI.
```

---

## Định nghĩa "Phase 7 hoàn thành"

**PART A — BLAST bootstrap:**
- [ ] `bootstrap_blast_db.py` idempotent, fail-soft (không crash app, không chặn `/api/design`); 3 test pass
- [ ] `GET /api/blast-status` trả `available/sequences_count/build_date/outdated_warning`; test tồn tại/vắng DB
- [ ] `useBlastCheck.js` gọi status lúc mount; nút disabled + tooltip khi `available=false`
- [ ] Procfile/entrypoint chạy bootstrap; `test_phase3.yml` cache DB; smoke hsa-miR-21-5p self-hit 100% giữ pass
- [ ] Playwright `blast-status.spec.js` (disabled/enabled) pass

**PART B — Family canonical data:**
- [ ] `build_family_db.py` fallback chain 4 nguồn (miFam FTP → archived+checksum → MirGeneDB* → seed-based), domain whitelist + timeout
- [ ] JSON `_metadata` (provenance/canonical/verified); `families` schema KHÔNG đổi
- [ ] `family_crossreactivity.py` backward-compat (`data.get("families", data)`); regression seed-based khớp baseline
- [ ] `/api/design` field `family_cross_reactivity.data_provenance`; 4 test fetch + backward-compat pass
- [ ] `verified=false` chờ Vuong duyệt; checksum placeholder mark "VERIFY before production"; Superpower SSRF check

**PART C — Family map (UX A3):**
- [ ] brainstorm chốt layout/vị trí; `FamilySpecificityMap.jsx` SVG thuần (radial), reuse `RISK_STYLE`
- [ ] Empty state + badge provenance; toggle Map/Table (giữ bảng cũ); colorblind-safe + a11y `<title>`
- [ ] Đọc data từ response (KHÔNG tính lại backend); unit test + Playwright `family-map.spec.js` pass

**PART D — Normalization advisor (UX B1):**
- [ ] `normalization_advisor.py` rule N1–N4 (source_doi+verified); reference candidates đọc từ `reference_mirnas.json`
- [ ] `protocol_kb.json` bump kb_version + N1–N4; disclaimer bắt buộc; advisory KHÔNG vào scoring
- [ ] `NormalizationAdvisor.jsx` (strategy/chips/cautions/links/disclaimer); test mỗi sample_type + Playwright plasma/tissue

**PART E — MIQE checklist:**
- [ ] `export.py` section "Validation Checklist" 8 mục (bảng E.2) PDF + CSV; Specificity auto-fill từ response
- [ ] Cột primer cũ + sanitize + format whitelist giữ nguyên; `include_checklist` param
- [ ] `test_export_checklist.py` + Playwright `export-checklist.spec.js` pass

**PART F — Benchmark UI:**
- [ ] `run_benchmark.py` xuất `benchmark_results.json` (comparison_note + verified=false); committed
- [ ] `GET /api/benchmark` serve tĩnh; thiếu file → `available=false` không crash
- [ ] `BenchmarkPanel.jsx` `/benchmark`: banner giới hạn bắt buộc + grouped bars SVG + miPrimer N/A; test + Playwright pass

**Chung:**
- [ ] UI 100% English; màu theo Week 1 §4; KHÔNG thêm dependency runtime nào
- [ ] `SCORING_WEIGHTS_V4` KHÔNG đổi; thuật toán lõi KHÔNG đổi
- [ ] Superpower security check pass cho mọi endpoint mới (`/api/blast-status`, `/api/benchmark`) + fetch FTP (`build_family_db.py`)
- [ ] Playwright suite cũ (Phase 3/4) vẫn xanh
- [ ] Mọi data chưa Vuong-duyệt để `verified=false`; placeholder mark "VERIFY before production"

**Không làm trong Phase 7 (đẩy phase sau):**
- Chạy benchmark runtime trong app (giữ precomputed offline)
- MirGeneDB nomenclature mapping layer (chỉ dùng nếu Vuong duyệt; mặc định nguồn miFam 1–2)
- Deploy production đầy đủ (Railway persistent volume config — xác nhận riêng lúc deploy)
- AI/LLM giải thích kết quả (phase riêng)
- LNA modification suggestions (deferred)
- Calibration wet-lab (BLOCKED — SPEC_phase6 PART D)

---

*Hết SPEC_phase7.md v1.0 — sync SPEC_phase3 v2.1 / phase4 v1.1 / phase5 v1.0 / phase6 v1.0 / RESEARCH_QUESTIONS_UX. Family-source facts web-verified 2026-07-04 (miFam FTP mirror / Rfam15 / MirGeneDB). Thông tin học thuật trích PubMed — DOI dẫn trong từng mục.*
