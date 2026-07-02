# SPEC_phase5.md — HG Lab Stem-loop RT-qPCR Primer Designer
# Phase 5: Evidence Advisor · Data-driven Scoring Calibration (hồi quy) · Tm accuracy
# Phiên bản 1.0 — 2026-07-02 · Sync: algorithm v3.0.0, scoring V4 (15 tiêu chí), SPEC_phase4 v1.1

---

## CHANGELOG

### v1.0 — 2026-07-02 — Phase 5 khởi tạo
- **PART A — Protocol/Evidence Advisor:** lớp cố vấn dựa trên nghiên cứu/protocol đã công bố (rule base có citation, ưu/nhược, match score). Mô tả, không kê đơn.
- **PART B — Data-driven Scoring Calibration (TRỌNG TÂM):** hồi quy có ràng buộc để **tăng trọng số của tiêu chí tương quan cao với kết quả thực**, dùng dữ liệu từ bài báo khoa học; chống overfit bằng shrinkage về prior V4 + LOOCV. Sinh `SCORING_WEIGHTS_V5`.
- **PART C — Tm model accuracy:** kiểm định Tm dự đoán vs thực nghiệm, xác nhận hiệu chỉnh Mg²⁺/dNTP.
- **PART D — Amplicon melting Tm + LNA-assist:** dự đoán đỉnh melting cho SYBR, gợi ý LNA cho miRNA khó.
- Mỗi PART kèm **PROMPT CLAUDE CODE** copy-paste được.
- Nguồn mới đã kiểm chứng PubMed: [Andreasen10], [Kunwar23], [Lagatie17].

---

## 0. Hướng dẫn cho Claude Code
1. **Đọc trước:** SPEC_phase2 §4 (constants, scoring), SPEC_phase3 §7 (SCORING_WEIGHTS_V4 — 15 tiêu chí), SPEC_phase4 §12 (recommendations), `backend/algorithm/scoring.py` (hàm `score_candidate` trả `scores`/`weights`), `validation/` (Phase 4.5 validation loop — Phase 5 dùng lại).
2. **Bất biến:** không đổi công thức thermodynamics lõi. PART B chỉ **đổi giá trị trọng số** (không đổi cách tính sub-score), và chỉ khi vượt cổng chấp nhận (§B.5). Runtime backend KHÔNG thêm dependency nặng — công cụ calibration là **offline tooling** riêng (`calibration/requirements.txt`), không đụng `backend/requirements.txt`.
3. **Tính trung thực khoa học (bắt buộc):** mọi con số hiệu suất/đặc hiệu phải có `source_doi`+`verified`. KHÔNG bịa số liệu. Dữ liệu chưa xác minh để `verified:false` và loại khỏi fit mặc định.
4. **Output UI English.** Comment tiếng Việt được.

---

## 1. Tổng quan Phase 5
Phase 4 hoàn thiện trình bày. Phase 5 nâng **độ chính xác & độ tin cậy khoa học** của lõi:
- Cho người dùng gợi ý protocol phù hợp có dẫn chứng (A).
- Biến scoring từ "trọng số chuyên gia đặt tay" → "trọng số học từ dữ liệu thực" (B) — đây là bước tăng *độ chính xác dự báo* lớn nhất.
- Kiểm định nền tảng Tm (C) và mở rộng đích khó (D).

Thứ tự ưu tiên giá trị-độ-chính-xác: **B → C → A → D**.

---

## 2. Nguồn tham chiếu (thêm Phase 5 — đã kiểm chứng PubMed)
- **[Andreasen10]** Andreasen D et al. "Improved microRNA quantification in total RNA from clinical samples." *Methods.* 2010;50(4):S6–9. PMID 20215018 · DOI [10.1016/j.ymeth.2010.01.006](https://doi.org/10.1016/j.ymeth.2010.01.006). → LNA-enhanced primer cho định lượng chính xác/lặp lại ở mẫu ít RNA (FFPE, huyết tương).
- **[Kunwar23]** Kunwar A et al. "Analytical Validation of a Novel MicroRNA Panel…" *Diagnostics.* 2023;13(13):2170. PMID 37443567 · DOI [10.3390/diagnostics13132170](https://doi.org/10.3390/diagnostics13132170). → so trực tiếp stem-loop TaqMan vs LNA-qPCR; cả hai tin cậy xuống ~20 copy; LNA "thân thiện" hơn cho lab lâm sàng.
- **[Lagatie17]** Lagatie O et al. *Parasitol Res.* 2017;116(3):1013–1022. PMID 28111713 · DOI [10.1007/s00436-017-5382-5](https://doi.org/10.1007/s00436-017-5382-5). → ngay cả assay LNA cho tín hiệu KHÔNG đặc hiệu, chỉ lộ qua **melting curve** → bắt buộc xác nhận đặc hiệu.
- Kế thừa: [Chen05], [Wang17] DOI [10.3892/mmr.2017.8297](https://doi.org/10.3892/mmr.2017.8297), [Cao23] DOI [10.1016/j.ab.2023.115267](https://doi.org/10.1016/j.ab.2023.115267), [Fan19] DOI [10.1080/07391102.2018.1498804](https://doi.org/10.1080/07391102.2018.1498804), [MIQE09] DOI [10.1373/clinchem.2008.112797](https://doi.org/10.1373/clinchem.2008.112797), [Var07], [SL04].

*(Thông tin tài liệu trích từ PubMed.)*

---

## 3. Thư viện
```
# backend/requirements.txt — KHÔNG đổi (numpy đã có, dùng cho PART B nếu tích hợp weights)
# calibration/requirements.txt — offline tooling MỚI, KHÔNG ship vào backend runtime
numpy>=1.24
requests>=2.31
# scipy: TÙY CHỌN (nếu có → dùng SLSQP; nếu không → projected-gradient numpy-only)
```

---

# PART A — Protocol / Evidence Advisor

## A.1 Rationale
Người dùng thường phân vân chọn hoá học/RT strategy. Advisor ánh xạ (đặc tính miRNA đã tính + lựa chọn form) → protocol công bố phù hợp, kèm **ưu/nhược + DOI + match score**, giúp tránh làm ướt-lab sai hướng. Dạng **mô tả, không kê đơn**.

## A.2 Tín hiệu đầu vào (tái dùng dữ liệu đã có — KHÔNG tính lại)
- Từ `/api/design` response: `metadata.mirna_length`, GC (từ `top3[0].gc_percent` hoặc tính từ mature), `specificity_warnings.cross_reactivity` (family risk), `edge_cases`.
- Từ form (đã có group): `detectionMethod.signalMethod` (sybr/taqman), `experimentalContext` (sample type, input amount, multiplex…).

## A.3 Rule base (bảng luật — mỗi luật có citation + pro/con)
Đặt trong `backend/data/protocol_kb.json` (versioned, có `kb_version` + `updated`):

| ID | Điều kiện kích hoạt | Khuyến nghị | Ưu | Nhược | Nguồn |
|---|---|---|---|---|---|
| P1 | signalMethod=sybr **và** family risk ∈ {HIGH, IDENTICAL} | "SYBR không phân biệt đồng loại khác 1 nt; cân nhắc TaqMan, hoặc RT stem-loop riêng cho từng thành viên." | rẻ | không đặc hiệu đồng loại | [Wang17], [Chen05] |
| P2 | sample = FFPE/plasma/serum **hoặc** input thấp | "Cân nhắc LNA-enhanced primer: chính xác/lặp lại tốt ở mẫu ít RNA." | nhạy, ổn định mẫu khó | chi phí LNA cao | [Andreasen10], [Kunwar23] |
| P3 | signalMethod=sybr (bất kỳ) | "Bắt buộc phân tích melting-curve: tín hiệu không đặc hiệu chỉ lộ qua melting." | phát hiện artifact/dimer | thêm bước | [Lagatie17] |
| P4 | multiplex=true hoặc nhiều đích | "Tham chiếu multiplex stem-loop + dual-probe TaqMan." | tiết kiệm mẫu/chi phí/lần chạy | thiết kế phức tạp | [Cao23] |
| P5 | miRNA GC thấp/ngắn (nối edge E1/E4) | "LNA spike hoặc kéo dài 5′ tail để nâng Tm cho đích khó." | cứu đích Tm thấp | cần kiểm nghiệm | [Andreasen10] |
| P6 | clinical/diagnostic context | "LNA-qPCR vận hành thân thiện cho lab CAP/CLIA (theo [Kunwar23])." | phù hợp lab lâm sàng | — | [Kunwar23] |

> **match score**: mỗi gợi ý kèm mức khớp `high|medium|low` (dựa số điều kiện thỏa) thay vì phán quyết tuyệt đối.

## A.4 Module `backend/algorithm/protocol_advisor.py`
```python
def advise_protocol(design_result: dict, form_params: dict) -> list[dict]:
    """Trả list gợi ý; KHÔNG side-effect. Mỗi item:
    { "id","recommendation","match","pros":[...],"cons":[...],
      "sources":[{"tag","doi"}], "disclaimer" }"""
```
- Tích hợp vào `/api/design` response dưới key `protocol_advice` (hoặc endpoint riêng `/api/advise` nếu muốn tách). Mặc định: nhúng vào `/api/design` (đồng bộ, rẻ).

## A.5 Frontend
- Panel mở rộng `ProtocolAdvisor.jsx` trong ResultsPage (SPEC_phase4 §4), **không chặn luồng**, mặc định collapsed.
- Mỗi gợi ý: badge match + pros/cons + link DOI + disclaimer "For research use only. Validate experimentally."

## A.6 Guardrails
- KB versioned (`kb_version`, `updated`) + hiển thị ngày cập nhật → chống lỗi thời.
- Giọng mô tả ("consider", "literature suggests"), luôn kèm nguồn, không tuyệt đối hoá.

## A.7 Unit tests (`backend/tests/test_protocol_advisor.py`)
```
test_sybr_high_family_triggers_P1
test_ffpe_low_input_triggers_P2
test_sybr_always_triggers_P3_melting
test_multiplex_triggers_P4
test_no_conditions_returns_empty_or_generic
test_every_advice_has_source_doi   # bắt buộc mọi gợi ý có DOI
```

## A.8 PROMPT CLAUDE CODE — PART A
```
Bối cảnh: repo primer-designer (Flask + React). Đọc SPEC_phase5.md PART A, SPEC_phase4 §4,
backend/routes/design.py (return shape), backend/algorithm/specificity_check/ (family risk).

Nhiệm vụ:
1) Tạo backend/data/protocol_kb.json chứa 6 luật P1–P6 (bảng §A.3), mỗi luật có:
   id, when (điều kiện), recommendation, match_hint, pros[], cons[], sources[{tag,doi}].
   Thêm kb_version="1.0", updated="2026-07-02".
2) Tạo backend/algorithm/protocol_advisor.py với advise_protocol(design_result, form_params)
   -> list[dict] theo §A.4. Đọc điều kiện từ design_result (family risk, edge_cases, gc, length)
   và form_params (signalMethod, sampleType, inputAmount, multiplex). Tính match high/medium/low.
   MỌI gợi ý phải kèm sources có doi + disclaimer.
3) Nhúng key "protocol_advice" vào return của routes/design.py (không đổi các key cũ).
4) Frontend: pages/ResultsPage/ProtocolAdvisor.jsx — panel collapsible, render match badge,
   pros/cons, link DOI (mở tab mới), disclaimer. UI English. Không chặn luồng.
5) Viết backend/tests/test_protocol_advisor.py theo §A.7 (đủ 6 test, tất cả pass).

Ràng buộc: không thêm dependency; UI English; giọng mô tả không kê đơn; mỗi advice có DOI.
Chạy pytest tests/test_protocol_advisor.py -q và xác nhận xanh trước khi báo xong.
```

---

# PART B — Data-driven Scoring Weight Calibration (TRỌNG TÂM)

## B.1 Rationale & rủi ro
`SCORING_WEIGHTS_V4` (15 tiêu chí, SPEC_phase3 §7) do chuyên gia đặt tay. Mục tiêu Phase 5: **học trọng số từ kết quả thực** để `total_score` **tương quan cao hơn với hiệu suất qPCR thực tế** → tiêu chí nào dự báo tốt thì tăng trọng số, tiêu chí nào không tương quan (hoặc ngược) thì giảm.

**Rủi ro chính = overfitting** khi dữ liệu ít. Giải pháp bắt buộc:
1. Ràng buộc `w ≥ 0`, `Σw = 1` (giữ diễn giải + thang 0–100).
2. **Shrinkage về prior V4** (ridge `λ‖w−w₀‖²`) → không đi quá xa kiến thức chuyên gia khi dữ liệu yếu.
3. **LOOCV**: chỉ nhận trọng số mới nếu cross-validation **giảm sai số** so với V4.
4. Cổng dữ liệu tối thiểu `N ≥ N_MIN` (mặc định 20 assay verified).
5. Nếu chưa đủ dữ liệu → **KHÔNG đổi weights**, chỉ xuất **báo cáo tương quan** (phần user coi trọng) để định hướng.

## B.2 Bộ dữ liệu nhãn (`calibration/benchmark_assays.json`)
Mỗi assay = 1 primer set stem-loop RT-qPCR **đã công bố** kèm **kết quả đo thực** (hiệu suất khuếch đại). Schema:
```json
{
  "assay_id": "wang17_let7a",
  "mirna_id": "hsa-let-7a-5p",
  "mirna_sequence": "UGAGGUAGUAGGUUGUAUAGUU",     // optional; tool sẽ tự lấy nếu trống
  "method": "stemloop_sybr",                        // stemloop_taqman|stemloop_sybr|polyA_sybr|lna
  "published_forward": "…",                          // optional — nếu có, chấm CHÍNH primer này
  "published_rt": "…",                               // optional
  "efficiency_pct": 102.0,                            // 100 = lý tưởng [MIQE09]
  "r_squared": 0.99,                                  // optional
  "specificity_ok": true,
  "source_pmid": "29257343",
  "source_doi": "10.3892/mmr.2017.8297",
  "verified": true,                                   // chỉ verified mới vào fit
  "notes": "efficiency range 0.93–1.14 reported for let-7 panel"
}
```
**Nguồn dữ liệu (khai thác từ paper — đọc bảng/supplement):** [Wang17] (let-7 panel, efficiency 0.93–1.14), [Kunwar23] (24-miRNA panel, R² 0.94–0.99), [Cao23] (21 miRNA multiplex), [Chen05] (assay gốc). Ưu tiên paper công bố **cả trình tự primer lẫn hiệu suất**. Chỗ chưa xác minh → `verified:false`.

> Trung thực: seed file chỉ chứa số liệu có nguồn; con số per-assay chưa trích được đánh dấu `verified:false` + `notes`, KHÔNG dùng để fit cho tới khi Vuong xác minh từ supplement.

## B.3 Trích đặc trưng (feature = 15 sub-score)
Với mỗi assay: gọi `POST /api/design` bằng `mirna_sequence`/`mirna_id`. Response `top3[*]` có sẵn `scores` (dict 15 sub-score 0–100) và `weights`.
- Nếu có `published_forward`: chọn candidate có `sequence` khớp nhất (tránh so top-1 nhầm) → lấy `scores`.
- Nếu không: dùng `top3[0].scores` (giả định assay tốt ≈ thiết kế tool). Đánh dấu `feature_source` để biết độ mạnh bằng chứng.
- Vector đặc trưng `x ∈ [0,100]¹⁵` theo **thứ tự key cố định** = key của `SCORING_WEIGHTS_V4`.

## B.4 Mô hình hồi quy (ràng buộc + shrinkage)
- Mục tiêu (target) `y`: **goodness** = `100 − |efficiency_pct − 100|` (100 = hoàn hảo; phạt cả >100 do artifact/inhibitor). Cấu hình được (`--target efficiency` để dùng thẳng eff).
- Dự đoán tuyến tính `ŷ = x·w`. Vì `x∈[0,100]` và `w` là tổ hợp lồi (Σw=1, w≥0) → `ŷ∈[0,100]`, **cùng thang với y** (khớp tự nhiên).
- Bài toán: `min_w ‖Xw − y‖² + λ‖w − w₀‖²`  s.t. `w ≥ 0, Σw = 1`, với `w₀` = vector V4.
  - `λ` (shrinkage) chọn qua grid trên LOOCV. `λ→∞` ⇒ giữ nguyên V4.
- Giải: **projected gradient** (numpy-only) — gradient descent + chiếu lên simplex (Duchi 2008); nếu có scipy → SLSQP với ràng buộc tương đương (kết quả kiểm chéo).
- **Báo cáo tương quan (mục Vuong coi trọng):** Pearson & Spearman r của **từng sub-score cột với y**, sắp giảm dần → "tiêu chí nào tương quan cao với kết quả thực". Đây là output độc lập, có ý nghĩa **kể cả khi chưa đổi weights**.

## B.5 Cổng chấp nhận (adopt gate) → `SCORING_WEIGHTS_V5`
Chỉ đề xuất V5 khi **tất cả**:
- `N_verified ≥ N_MIN` (mặc định 20).
- `LOOCV_RMSE(w_calibrated) < LOOCV_RMSE(w₀=V4)` (cải thiện thực, không chỉ train fit).
- Không tiêu chí nào bị đẩy về 0 một cách phi lý (giữ sàn `w_i ≥ w_floor`, mặc định 0.005, cho tiêu chí lõi Tm/dimer/hairpin) — bảo toàn tri thức sinh học.
- Chênh V5 vs V4 đi kèm giải thích từng tiêu chí (tăng/giảm + r tương ứng).

Nếu KHÔNG đạt cổng → giữ V4, xuất `calibration_report.md` (tương quan + khuyến nghị thu thêm dữ liệu). **Không tự ý ghi đè.**

## B.6 Đầu ra
- `calibration/SCORING_WEIGHTS_V5.json` (chỉ khi đạt cổng) — kèm `provenance` (N, λ, LOOCV, ngày, danh sách DOI nguồn).
- `calibration/calibration_report.md` — bảng tương quan per-tiêu chí, LOOCV V4 vs V5, quyết định adopt/không, cảnh báo dữ liệu.
- Tích hợp: nếu adopt, thêm `SCORING_WEIGHTS_V5` vào `constants.py` (giữ V4 để so sánh), bật qua cờ; chạy lại `validation/` (Phase 4.5) để đảm bảo không phá deterministic checks.

## B.7 Script `calibration/calibrate_weights.py` (khung đã có sẵn — §file)
Xem file khung kèm theo repo: đọc benchmark → trích feature qua `/api/design` → hồi quy ràng buộc + shrinkage → LOOCV → report + (nếu đạt) V5. Numpy-only, scipy tùy chọn.

## B.8 Quy tắc trung thực dữ liệu
- Chỉ `verified:true` vào fit. Ghi rõ N, nguồn DOI trong `provenance`.
- KHÔNG suy trọng số từ dữ liệu mô phỏng/bịa. Nếu N nhỏ → nói thẳng "chưa đủ, chỉ báo cáo tương quan".
- Báo cáo là **định hướng nghiên cứu**, không phải chân lý; kèm khoảng tin cậy khi có thể.

## B.9 PROMPT CLAUDE CODE — PART B
```
Bối cảnh: repo primer-designer. Đọc SPEC_phase5.md PART B, backend/algorithm/scoring.py
(score_candidate trả scores/weights 15 tiêu chí), backend/algorithm/constants.py
(SCORING_WEIGHTS_V4), calibration/calibrate_weights.py (khung), calibration/benchmark_assays.json.

Nhiệm vụ:
1) Hoàn thiện calibration/calibrate_weights.py:
   - Đọc benchmark_assays.json, chỉ dùng verified==true.
   - Với mỗi assay: POST /api/design (mirna_sequence hoặc mirna_id). Nếu có published_forward,
     chọn candidate khớp nhất; else top3[0]. Lấy scores (15 sub-score) theo thứ tự key V4.
   - target y = 100 - |efficiency_pct - 100| (cờ --target efficiency để đổi).
   - Hồi quy min ||Xw - y||^2 + lambda*||w - w0||^2, s.t. w>=0, sum w=1 (w0 = V4).
     Dùng projected-gradient + simplex projection (numpy). Nếu scipy có, thêm nhánh SLSQP kiểm chéo.
   - Chọn lambda qua grid trên LOOCV. Tính LOOCV RMSE cho w_calibrated và cho w0.
   - Báo cáo Pearson & Spearman của từng sub-score vs y (sắp giảm dần).
   - Adopt gate §B.5: N>=N_MIN(20) & LOOCV cải thiện & giữ w_floor tiêu chí lõi.
   - Xuất calibration/calibration_report.md; nếu đạt cổng xuất SCORING_WEIGHTS_V5.json (kèm provenance).
2) Nếu adopt: thêm SCORING_WEIGHTS_V5 vào constants.py (GIỮ V4), thêm cờ dùng V5; chạy lại
   validation/validate_primers.py đảm bảo deterministic checks vẫn 100%.
3) Test calibration/test_calibrate.py: (a) simplex projection đúng (sum=1,>=0);
   (b) lambda lớn -> w≈V4; (c) trên synthetic data biết trước, tiêu chí tương quan mạnh được tăng.

Ràng buộc: calibration là offline tooling (calibration/requirements.txt), KHÔNG thêm vào
backend/requirements.txt. KHÔNG bịa số liệu; chỉ verified vào fit. Không đạt cổng thì KHÔNG ghi V5.
Chạy python calibration/test_calibrate.py và báo cáo trước khi xong.
```

---

# PART C — Tm model accuracy validation

## C.1 Rationale
Sai số Tm làm lệch toàn bộ scoring (nhiều tiêu chí phụ thuộc Tm). Cần kiểm định Tm dự đoán vs Tm thực nghiệm và xác nhận hiệu chỉnh ion.

## C.2 Phương pháp
- Tập nhỏ oligo có Tm thực nghiệm công bố (hoặc đo tại lab) → so `tm_full` tool dự đoán; báo cáo MAE, bias.
- Xác nhận đường tính Tm áp **hiệu chỉnh Mg²⁺/dNTP (SantaLucia 2004)** nhất quán cho forward & RT (đối chiếu `thermodynamics.py`, `bound_fraction.py` SPEC_phase3 §4).
- Nếu MAE lớn/bias hệ thống → hiệu chỉnh tham số muối, KHÔNG đổi mô hình NN.

## C.3 PROMPT CLAUDE CODE — PART C
```
Đọc backend/algorithm/thermodynamics.py và SPEC_phase3 §4. Nhiệm vụ:
1) Tạo calibration/tm_benchmark.json: oligo + Tm thực nghiệm (nguồn DOI, verified).
2) calibration/check_tm.py: so tm dự đoán (gọi /api/design hoặc gọi trực tiếp hàm Tm) vs thực nghiệm;
   in MAE, bias, scatter; xác nhận Mg2+/dNTP correction được áp (log tham số muối dùng).
3) Nếu bias hệ thống > 1.5°C: đề xuất điều chỉnh salt-correction trong constants (không đổi mô hình NN),
   ghi calibration/tm_report.md. KHÔNG bịa số liệu; chỉ verified.
```

---

# PART D — Amplicon melting Tm + LNA-assist (nhỏ)

## D.1 Amplicon melting-Tm prediction
Dự đoán Tm/đỉnh melting của amplicon để lường trước phân biệt product vs primer-dimer trong SYBR (nối luật P3 [Lagatie17]). Dùng ViennaRNA/primer3 đã có; thêm `predicted_amplicon_tm` vào output, cảnh báo nếu gần Tm dimer.

## D.2 LNA-assist
Với miRNA Tm thấp/ngắn (edge E1/E4), gợi ý **vị trí đặt LNA** để nâng Tm (chỉ gợi ý, không tự thiết kế), dẫn [Andreasen10][Kunwar23].

## D.3 PROMPT CLAUDE CODE — PART D
```
1) Thêm predicted_amplicon_tm vào /api/design (dùng thư viện đã có), cảnh báo nếu |Tm_amplicon - Tm_dimer|
   nhỏ (nguy cơ nhầm trong SYBR). 2) Thêm gợi ý LNA (vị trí + lý do) khi edge E1/E4 kích hoạt, kèm DOI
   [Andreasen10][Kunwar23], disclaimer research-use. UI English. Test tối thiểu cho mỗi nhánh.
```

---

## Định nghĩa "Phase 5 hoàn thành"

**PART A — Advisor:**
- [ ] `protocol_kb.json` 6 luật P1–P6, versioned, mỗi luật có DOI
- [ ] `protocol_advisor.py` trả gợi ý có match + pros/cons + sources + disclaimer
- [ ] Nhúng `protocol_advice` vào `/api/design`; `ProtocolAdvisor.jsx` panel collapsible
- [ ] 6 unit test pass; mọi advice có DOI

**PART B — Calibration (trọng tâm):**
- [ ] `benchmark_assays.json` chỉ chứa số liệu có nguồn; `verified` phân biệt rõ
- [ ] `calibrate_weights.py`: trích 15 sub-score qua `/api/design`, hồi quy ràng buộc + shrinkage V4 + LOOCV
- [ ] Báo cáo **tương quan per-tiêu chí** (Pearson/Spearman) — luôn xuất, kể cả không đổi weights
- [ ] Adopt gate §B.5 nghiêm ngặt: N≥20, LOOCV cải thiện, giữ w_floor lõi
- [ ] Nếu adopt: `SCORING_WEIGHTS_V5` + provenance; chạy lại `validation/` vẫn 100% deterministic
- [ ] KHÔNG bịa số liệu; offline tooling không đụng backend runtime deps
- [ ] `test_calibrate.py` pass (simplex, lambda→prior, synthetic recovery)

**PART C — Tm accuracy:**
- [ ] `check_tm.py` báo MAE/bias vs Tm thực nghiệm có nguồn; xác nhận Mg²⁺/dNTP correction

**PART D:**
- [ ] `predicted_amplicon_tm` + cảnh báo SYBR; gợi ý LNA cho edge E1/E4 có DOI

**Không làm trong Phase 5:** wet-lab thật (ngoài phạm vi phần mềm); tự động thiết kế oligo LNA; đổi mô hình thermodynamics lõi.

---

*Hết SPEC_phase5.md v1.0 — sync SPEC_phase4 v1.1. Thông tin tài liệu trích từ PubMed.*
