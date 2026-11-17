# SPEC — Hệ chấm điểm phân tầng, ưu tiên đặc hiệu (algorithm 4.0.0)

Ngày: 2026-11-17 (sửa lần 1, sau báo cáo đo đạc của PROMPT Phần 0–3) · Chủ dự án: Vương · Trạng thái: hướng đã chốt; ngưỡng 1–5 chờ duyệt sau Giai đoạn 1.

## 0. Cách dùng file này
- Đọc thêm: `CLAUDE.md`, `HANDOFF_THESIS_STATUS.md` §4 §7, `SPEC_algorithm.md` (chấm V4), `AUDIT_REPORT.md` REV-18…24, `benchmark/scoring_weight_sensitivity.json`.
- Làm tuần tự theo giai đoạn (§6). Gặp ⛔ DỪNG: gửi báo cáo rồi chờ duyệt, không làm sang giai đoạn sau.
- Báo cáo bằng tiếng Việt; code, commit, UI bằng tiếng Anh.
- Mọi kết luận phải kèm bằng chứng: lệnh đã chạy + output (rút gọn).
- File này thay Phần 1 của `docs/PROMPT_thesis_freeze_4.0.0.md`. Các sửa lỗi nhỏ của V4 (REV-23, REV-21, `end_stability`) vào bản 3.8.2 trước (QĐ 14); hệ phân tầng xây trên 3.8.2.
- Mốc so sánh V4 trong mọi bảng là **3.8.2**, không phải 3.8.1.
- Gặp chỗ SPEC mâu thuẫn với code hoặc không thể làm đúng: dừng và hỏi, không tự chọn.

## 1. Mục tiêu và lý do
Thay cách xếp hạng mồi xuôi bằng tổng có trọng số của 14 tiêu chí (V4) bằng **xếp hạng phân tầng, đặc hiệu với đích đứng đầu**. V4 vẫn chạy được sau cờ để so sánh trong khóa luận.

Lý do (đo trên 2253 thiết kế hsa, pool của 3.7.0):
- 4 tiêu chí (`mfe_stemloop`, `end_stability`, `bound_fraction_full`, `family_discrimination`) có giá trị như nhau với mọi ứng viên ở 100 % pool. `hairpin_penalty`, `dimer_penalty`, `tm_pair_match` khác nhau ở ≤ 3,6 % pool và 0 % top 5. Kết quả: ~0,47/0,95 trọng số không ảnh hưởng thứ hạng.
- Chênh điểm bộ #1 − bộ #2 (sau chọn đa dạng, `benchmark/thesis_freeze_impact.json`): trung vị 1,1; < 1 điểm ở 1046/2248 thiết kế (47 %).
- BLAST không tham gia chọn mồi. Đặc hiệu trong V4 chấm theo độ dài của mồi thắng (REV-23; sửa ở 3.8.2, chỉ đổi nhãn ở 3,5 % thiết kế).
- `end_stability` không thể fail: ΔG duplex 5 nt lớn nhất là 6,86 kcal/mol (GCGCG) < ngưỡng 9,0.
- 115/2253 thiết kế (5,1 %) chạy `hard_filter_fallback`: mọi ứng viên vi phạm lọc cứng cấu trúc mà tool vẫn trả mồi.
- 403/2656 miRNA hsa không thiết kế được, cả 403 do bộ lọc sơ bộ mồi xuôi (GC 40–60 % cứu 181 ca, kẹp GC cứu 34 ca). Nguyên nhân gốc: đuôi 5′ luôn GC ≥ 50 %.

## 2. Quyết định đã chốt (không mở lại)
1. Xếp hạng thứ bậc: **Đặc hiệu → veto cấu trúc → PCR → Linh hoạt → điểm chi tiết → |Tm − Ta| → trình tự**.
2. Tiêu chí của tầng Đặc hiệu, PCR, Linh hoạt chấm số nguyên 1–5 (bước 1). Điểm tầng = tổng số nguyên.
3. Đặc hiệu gồm: BLAST cùng loài (như hiện tại: loài đích, cộng loài chủ nếu là miRNA virus), ΔCq cấp assay tính theo từng ứng viên, biên Tm đặc hiệu.
4. Loại ứng viên có BLAST CRITICAL hoặc ΔCq CO-AMPLIFIED. Nếu mọi ứng viên đều bị → giữ tất cả, gắn cờ `specificity_fallback`.
5. Sau khi loại còn < 3 bộ: trả ít hơn 3 + cảnh báo `fewer_than_3_sets`. Không bù bằng ứng viên đã loại.
6. Tầng PCR: ΔTm mồi xuôi – mồi ngược; Tm mồi xuôi so với Ta.
7. Hệ mới bỏ toàn bộ lọc cứng cấu trúc thứ cấp (3 luật trong `hard_filters.py`). Thay bằng tiêu chí cấu trúc trong tầng Linh hoạt + veto mềm.
8. Veto mềm: ứng viên có bất kỳ chỉ số cấu trúc con nào = 1 bị xếp sau mọi ứng viên không có, **chỉ khi cùng tổng Đặc hiệu**.
9. Overhang RT giữ mặc định 6 nt; chỉ thêm gợi ý, không đổi lựa chọn.
10. Điểm chi tiết (0–100) chỉ giữ tiêu chí thực sự khác nhau giữa ứng viên. Tiêu chí hằng số chuyển thành chỉ số báo cáo.
11. V4 giữ nguyên, chạy bằng `SCORING_SYSTEM = "v4"`.
12. Một lần thiết kế chưa có cache: ≤ 15 s trên máy dự án (Windows, backend dev).
13. Phạm vi: backend + API + test + số liệu. Không sửa frontend (sẽ có SPEC UI riêng).
14. Bản V4 3.8.2 (merge vào `master` trước khi làm SPEC này):
    - REV-23: nhánh `fix/rev23-family-per-candidate` (`1feec12`).
    - REV-21: luật dimer đầu 3′ đổi từ ΔG 8 nt ≤ −5 sang Tm ≥ 47 °C (Primer3 `PRIMER_MAX_SELF_END_TH` / `PRIMER_PAIR_MAX_COMPL_END_TH`). Đã đo: không đổi output.
    - `end_stability`: tính lại đúng Primer3 (ΔG duplex 5 nt cuối, SantaLucia 1998) thay cho `calc_hairpin`. Vẫn chấm như cũ; không ứng viên nào fail nên điểm không đổi, chỉ giá trị hiển thị đổi.
15. Ở hệ tiered, GC % và kẹp GC **không còn là bộ lọc sơ bộ** trong `generate_forward_candidates`; chúng chỉ được chấm ở F1/F2. Ràng buộc hình học (độ dài, vị trí) và cửa sổ Tm giữ nguyên. Cách sinh đuôi 5′ giữ nguyên trong 4.0.0 (đuôi giàu AT là việc sau, cần đo riêng). Nhánh V4 giữ nguyên bộ lọc.
16. Nhãn "equivalent in silico" không làm cho V4. Ở hệ tiered, hai bộ có cùng (S_total, structure_veto, P_total, F_total) là tương đương; cách hiển thị để SPEC UI.

## 3. Tiêu chí và ngưỡng đề xuất (chờ duyệt ở Giai đoạn 1)
Quy ước:
- L = độ dài vùng đặc hiệu của ứng viên (12–17 nt).
- Mọi Tm dùng điều kiện primer3 hiệu lực của lần thiết kế (`effective_p3`), gọi qua `algorithm.primer3_safe`.
- Mốc không có nguồn: ghi "own threshold" trong comment.

### 3.1 Tầng 1 — Đặc hiệu (tối đa 15)
**S1 · BLAST.** Với từng ứng viên, gọi `check_offtarget(forward=<ứng viên>, rt_primer=<mồi RT của thiết kế>, species=…)` (classifier v7, đã lọc cùng loài). Không BLAST mồi ngược. Không tính `same_sequence`.

| Điểm | overall_risk |
|---|---|
| 5 | SAFE |
| 4 | MEDIUM, 1 hit |
| 3 | MEDIUM, ≥ 2 hit |
| 2 | HIGH |
| 1 | CRITICAL → loại (QĐ 4) |

**S2 · ΔCq cấp assay.** min ΔCq_assay (`assay_model`, RT + FWD) trên mọi miRNA cùng loài trong chỉ mục overhang, tính với **L của chính ứng viên** (sửa REV-23; cache theo L, tối đa 6 giá trị). Bỏ `same_sequence`.

| Điểm | min ΔCq_assay | Nguồn mốc |
|---|---|---|
| 5 | ≥ 10 | ≈ 0,1 %, mức thấp nhất Chen 2005 báo (DECISIONS D-2) |
| 4 | 7 – < 10 | own threshold |
| 3 | 4,3 – < 7 | `ASSAY_DCQ_DISCRIMINATED_AT` |
| 2 | 3,3 – < 4,3 (PARTIAL) | `ASSAY_DCQ_COAMPLIFIED_BELOW` |
| 1 | < 3,3 (CO-AMPLIFIED) → loại (QĐ 4) | |

**S3 · Biên Tm đặc hiệu.** ΔTm_spec = Tm_on − max(Tm_off).
- Tm_on: vùng đặc hiệu (L nt) trên cDNA đích, khung neo đầu 3′ (quy ước A2, như `duplex_tm`).
- Off-target được xét: miRNA cùng loài mà mồi RT bắt được (ΔCq_RT < 4,3 theo `rt_axis`). Lý do: miRNA không được phiên mã ngược thì không có khuôn cho mồi xuôi.
- Tm_off: vùng đặc hiệu trên cDNA off-target, cùng khung neo.
- Không có off-target nào → 5.

| Điểm | ΔTm_spec | Nguồn mốc |
|---|---|---|
| 5 | ≥ 15 °C | own threshold |
| 4 | 10 – < 15 | `BLAST_TM_SAFE_MARGIN` |
| 3 | 7,5 – < 10 | own threshold |
| 2 | 5 – < 7,5 | `BLAST_TM_CRITICAL_MARGIN` |
| 1 | < 5 | (không loại; QĐ 4 chỉ áp cho S1, S2) |

### 3.2 Tầng 2 — PCR (tối đa 10)
**P1 · ΔTm F–R** = |Tm(mồi xuôi đầy đủ) − Tm(mồi ngược universal)|, cùng điều kiện.
**P2 · Tm so với Ta** = |Tm(mồi xuôi đầy đủ) − Ta người dùng| (cùng tham chiếu với `tm_accuracy` hiện tại).

| Điểm | P1 | P2 |
|---|---|---|
| 5 | ≤ 1 °C | ≤ 1 °C |
| 4 | ≤ 2 (`TM_PAIR_DIFF_MAX` [PAST24]) | ≤ 2 |
| 3 | ≤ 3 | ≤ 3 |
| 2 | ≤ 5 | ≤ 5 |
| 1 | > 5 | > 5 |

Cần đo: mồi ngược là cố định, nên nếu Tm_rev ≈ Ta thì P1 ≈ P2 (đếm đôi). Báo Tm_rev và tương quan P1–P2.

### 3.3 Tầng 3 — Linh hoạt (tối đa 25)
Thứ tự mốc trong mỗi ô: 5 / 4 / 3 / 2 / 1.

| Mã | Tiêu chí | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|
| F1 | GC % (cùng đầu vào với `gc_content` hiện tại) | 40–60 | 35–<40 hoặc >60–65 | 30–<35 hoặc >65–70 | 25–<30 hoặc >70–75 | còn lại |
| F2 | Kẹp GC, 5 nt cuối 3′ | 2 G/C | 3 G/C, 3 nt cuối không đều là G/C | 1 G/C | 3 nt cuối đều G/C, hoặc 4 G/C | 0 hoặc 5 G/C |
| F3 | L (nt) | 16–17 | 15 | 14 | 13 | 12 |
| F4 | \|Tm vùng bám chu kỳ 1 − `TM_BINDING_TARGET`\| | ≤ 2 °C | ≤ 4 | ≤ 6 | ≤ 8 | > 8 |
| F5 | Cấu trúc thứ cấp = **min** của 3 chỉ số con dưới đây | | | | | |

Chỉ số con của F5:

| Chỉ số con | 5 | 4 | 3 | 2 | 1 (→ veto mềm) | Nguồn mốc "1" |
|---|---|---|---|---|---|---|
| Hairpin Tm (primer3 thal) | < 30 °C | 30–<37 | 37–<42 | 42–<47 | ≥ 47 | Primer3 `PRIMER_MAX_HAIRPIN_TH` |
| Dimer toàn cấu trúc ΔG (RNAcofold DNA, `full_dimer_dg`; lấy giá trị xấu nhất của self và × universal) | > −5 kcal/mol | −5…>−7 | −7…>−9 | −9…>−10 | ≤ −10 | Kang 2017 (−9 ± 1) |
| Dimer đầu 3′, Tm (primer3 `calc_end_stability`; self và × universal, lấy cao nhất) | < 30 °C | 30–<37 | 37–<42 | 42–<47 | ≥ 47 | Primer3 `PRIMER_MAX_SELF_END_TH` (thay luật ΔG 8 nt, REV-21) |

Có bất kỳ chỉ số con = 1 → `structure_veto = true`.
Amplicon không có trong tầng này (63–73 bp, khác biệt không có ý nghĩa thực tế); chỉ góp vào điểm chi tiết.

### 3.4 Điểm chi tiết (0–100; chỉ dùng phân định khi 3 tầng hòa)
Mỗi thành phần là sub-score liên tục 0–100. Dùng hàm sub-score hiện có nếu có; nếu không, nội suy tuyến tính theo bảng 1–5 ở trên.

| Thành phần | Trọng số |
|---|---|
| min ΔCq_assay (chặn trên ở 10) | 0,25 |
| Biên Tm đặc hiệu (chặn trên ở 20 °C) | 0,15 |
| ΔTm F–R | 0,15 |
| Tm so với Ta (`tm_accuracy`) | 0,15 |
| Tm vùng bám (`tm_binding_accuracy`) | 0,08 |
| GC % | 0,05 |
| Kẹp GC | 0,05 |
| Độ dài vùng đặc hiệu (`primer_size`) | 0,05 |
| Cấu trúc (trung bình 3 sub-score) | 0,05 |
| Amplicon | 0,02 |

Tổng 1,00, trong đó đặc hiệu 0,40, Tm 0,38, cấu trúc 0,05.
Chỉ báo cáo, không chấm (gom vào `assay_qc`): `mfe_stemloop`, `end_stability`, bound fraction (cả 2 vòng), `family_discrimination` của V4, `tm_pair_match` của V4 (đã thay bằng P1).

### 3.5 Khóa xếp hạng
1. Loại ứng viên theo QĐ 4.
2. `key = (−S_total, structure_veto, −P_total, −F_total, −detailed_score, |Tm_full − Ta|, sequence)`.
3. Chọn top 3 bằng `select_diverse_top(ranked, CANDIDATES_TOP_N)`, giữ nguyên logic đa dạng.
4. Hệ mới bỏ vòng fixpoint `family_discrimination` trong `design_pipeline.py` (không cần nữa vì S2 đã tính theo từng ứng viên).

### 3.6 Gợi ý overhang (không đổi lựa chọn)
Với bộ #1, tính S2 khi overhang là 5 nt và 7 nt. Nếu một trong hai cho mức S2 cao hơn 6 nt → thêm `overhang_suggestion` gồm `{length, min_delta_cq, worst_target, note}`, trong đó note ghi rõ off-label, chưa kiểm chứng wet-lab.

## 4. API (tương thích ngược)
Mỗi bộ mồi trong `POST /api/design` có thêm:
```json
"ranking": {
  "system": "tiered",
  "specificity": {
    "blast":     {"score": 5, "overall_risk": "SAFE", "worst_hit": null},
    "assay_dcq": {"score": 4, "min_delta_cq": 8.1, "worst_target": "hsa-…", "label": "DISCRIMINATED"},
    "tm_margin": {"score": 4, "tm_on": 46.2, "tm_off_max": 33.6, "margin": 12.6, "worst_target": "hsa-…"},
    "total": 13, "max": 15},
  "pcr": {
    "tm_pair":  {"score": 4, "tm_forward": 60.4, "tm_reverse": 59.1, "diff": 1.3},
    "tm_vs_ta": {"score": 5, "tm": 60.4, "ta": 60.0, "diff": 0.4},
    "total": 9, "max": 10},
  "flexible": {
    "gc": {}, "gc_clamp": {}, "specific_length": {}, "binding_tm": {},
    "structure": {"score": 3, "hairpin_tm": 0, "dimer_dg": 0, "end_dimer_tm": 0, "sub_scores": {}},
    "total": 19, "max": 25},
  "structure_veto": false,
  "detailed_score": 87.4
}
```
- `total_score` = `detailed_score`, để frontend hiện tại vẫn chạy. `scores` / `explanations` = các thành phần của điểm chi tiết.
- Cấp thiết kế có thêm `ranking_summary`: `{system, candidates_scored, eliminated_specificity, specificity_fallback, blast_available, returned_sets, timing_ms: {blast, total}}`, cùng `overhang_suggestion` nếu có.
- Cảnh báo mới: `specificity_fallback`, `fewer_than_3_sets`, `blast_unavailable`.
- BLAST không chạy được (thiếu binary hoặc DB): S1 = null, xếp hạng dùng S2 + S3 (tối đa 10), gắn cờ `blast_unavailable`. Request không được lỗi.
- Cập nhật `backend/static/openapi.yaml` (đã có test chống lệch route).
- Ghi `SCORING_SYSTEM` và hash bảng ngưỡng vào `_provenance()` và export.

## 5. Ràng buộc kỹ thuật
- Code mới đặt ở `backend/algorithm/tiered_scoring.py`: hàm thuần (metric → 1–5, điểm chi tiết, khóa xếp hạng).
- Ngưỡng đặt trong `constants.py`, gom thành một mục "TIERED SCORING (4.0.0)". Mỗi hằng số có nguồn hoặc ghi "own threshold".
- Nhánh V4 giữ nguyên `scoring.py`, `hard_filters.py`, `SCORING_WEIGHTS_V4`. Nhánh tiered không gọi `apply_hard_filters`.
- Không sửa: logic phân loại BLAST, `assay_model.py`, thiết kế mồi RT, cách sinh đuôi 5′, frontend, dependency.
- `generate_forward_candidates`: chỉ được thêm tham số để tắt lọc GC % và kẹp GC khi chạy tiered (QĐ 15). Mặc định và nhánh V4 giữ nguyên hành vi (test: V4 sinh đúng tập ứng viên như 3.8.2).
- Dùng lại: `check_offtarget`, `check_overhang_collision` / `assay_model`, `duplex_tm`, `full_dimer_dg`, `select_diverse_top`, `algorithm.primer3_safe`, cache BLAST sqlite.
- Hiệu năng: BLAST mọi ứng viên còn lại sau khi tính S2. Nếu p50 thời gian thiết kế chưa cache > 15 s trên 20 miRNA hsa ngẫu nhiên (seed cố định) → gộp truy vấn BLAST thành một lần gọi `blastn` multi-FASTA trong `blast_offtarget.py`, và test rằng kết quả phân loại trùng từng hit với cách gọi từng mồi.
- Tất định: cùng input → cùng output.
- `ALGORITHM_VERSION = "4.0.0"`; mặc định `SCORING_SYSTEM = "tiered"`.

## 6. Giai đoạn
### Giai đoạn 0 — Điều kiện tiên quyết
- Working tree phải sạch. Hiện có 26 file chỉ khác ký tự xuống dòng CRLF; nếu chưa xử lý thì thêm `.gitattributes` và chuẩn hóa trong một commit riêng.
- Bản 3.8.2 (QĐ 14) đã merge vào `master`. Tạo nhánh `feat/tiered-scoring` từ `master` sau đó.

### Giai đoạn 1 — Đo ngưỡng (chưa đổi pipeline)
- Viết `tiered_scoring.py` (hàm thuần) + test biên cho mọi bảng 1–5.
- Viết `backend/scripts/tiered_scoring_dryrun.py`: chấm pool ứng viên của 2656 miRNA hsa (dùng lại cách ghi pool của `backend/scripts/thesis_freeze_impact.py`; pool tiered sinh **không** có lọc GC/kẹp GC theo QĐ 15). Nếu BLAST toàn bộ quá lâu thì BLAST trên mẫu 300 miRNA ngẫu nhiên (seed cố định) và ghi rõ trong báo cáo.
- Output: `benchmark/tiered_scoring_dryrun.json`, kèm bảng trong báo cáo gồm:
  1. Phân bố mức 1–5 của từng tiêu chí (trên toàn bộ ứng viên, và trên top 5 của V4).
  2. % pool mà mỗi tiêu chí khác nhau giữa các ứng viên.
  3. Số thiết kế có ứng viên bị loại, bị `specificity_fallback`, trả < 3 bộ; số thiết kế mà #1 bị veto mềm.
  4. Tm_rev và tương quan P1–P2.
  5. #1 hệ tiered so với #1 V4 (3.8.2): số thiết kế đổi #1; với các ca đổi, cho ΔS_total, ΔL, ΔTm.
  6. Tỉ lệ hòa ở từng tầng (bao nhiêu thiết kế phải dùng tới điểm chi tiết).
  7. Thời gian BLAST mỗi ứng viên và ước tính thời gian một lần thiết kế.
  8. Bảng ca cụ thể cho hsa-let-7a-5p, hsa-miR-17-5p, hsa-miR-20a-5p, hsa-miR-21-5p, hsa-miR-16-5p, hsa-miR-103a-3p, hsa-miR-23a-3p: #1–#3 của V4 và của hệ mới, kèm điểm từng tầng.
  9. Trong 403 miRNA V4 không thiết kế được: bao nhiêu ca hệ tiered có ứng viên; phân bố F1, F2, S_total và structure_veto của bộ #1; danh sách các ca có số < 1000.
  10. Với 115 thiết kế V4 đang `hard_filter_fallback`: bộ #1 của hệ tiered có `structure_veto` không, F5 bao nhiêu.
- Tiêu chí nào có một mức chiếm > 90 % ứng viên → đề xuất chỉnh ngưỡng, không tự sửa.

⛔ DỪNG: gửi báo cáo, chờ duyệt ngưỡng.

### Giai đoạn 2 — Cài đặt
- Áp ngưỡng đã duyệt; tích hợp vào `design_pipeline.py` theo §3.5; làm API theo §4.
- Test trong `backend/tests/test_tiered_scoring.py`, và cập nhật các test liên quan:
  - Giá trị đúng tại mọi mốc của các bảng 1–5.
  - Đặc hiệu thắng PCR: ứng viên S = 15, P = 7 xếp trên S = 13, P = 10.
  - Veto mềm: cùng S_total thì ứng viên bị veto xếp sau; khác S_total thì veto không có tác dụng.
  - Loại theo đặc hiệu; fallback khi mọi ứng viên đều bị; trả < 3 bộ khi chỉ còn ít.
  - 3 tầng hòa → so điểm chi tiết → |Tm − Ta| → trình tự.
  - Không có BLAST → request không lỗi, có cờ `blast_unavailable`.
  - Tất định.
  - Hồi quy V4: với `SCORING_SYSTEM = "v4"`, chạy validation cho ra `validation/results.json` trùng bản 3.8.2 đã commit (bỏ qua trường version/provenance).
  - Nếu đã gộp BLAST: kết quả trùng từng hit với cách gọi từng mồi.
- Toàn bộ test hiện có phải pass: `cd backend && python -m pytest tests visualization -q --ignore=tests/smoke`.

### Giai đoạn 3 — Số liệu, tài liệu, PR
- Chạy lại pipeline theo HANDOFF §7 (backend tắt auto-reloader): validation + report, benchmark export, `blast_tm_gate_sensitivity.py`, benchmark 50, ma trận hsa; chạy e2e Playwright.
- Check validation nào fail: không sửa check cho pass. Liệt kê từng check fail, lý do và đề xuất.
- Viết `docs/SCORING_TIERED_COMPARISON.md` so V4 với hệ tiered trên 2656 hsa và trên bộ validation. Gồm các chỉ số 3–6 của Giai đoạn 1, cộng thêm cho bộ #1: phân bố S1 (SAFE/MEDIUM/HIGH/CRITICAL), phân bố min ΔCq, L trung bình, số bộ có `structure_veto`.
- Cập nhật tài liệu:
  - `SPEC_algorithm.md`: thêm mục mới.
  - `AUDIT_REPORT.md` §10: ghi hệ tiered (REV-21, REV-23, `end_stability` đã đóng ở 3.8.2); ghi phát hiện `hard_filter_fallback` 115 ca và D-8.
  - `HANDOFF_THESIS_STATUS.md`: thêm dòng ở §2, quyết định mới ở §4.
  - `CLAUDE.md`: chỉ sửa nếu lệnh chạy thay đổi.
- Review: dùng subagent đọc diff và đối chiếu với file SPEC này. Chỉ báo lỗi ảnh hưởng tính đúng, bỏ qua style.
- Mở PR vào `master`.

⛔ DỪNG: chờ duyệt trước khi merge.

## 7. Ngoài phạm vi
- Frontend (sẽ có SPEC UI riêng sau khi duyệt số liệu).
- Đổi overhang mặc định.
- Mở rộng CSDL BLAST (tRNA, Y RNA, snoRNA).
- Hiệu chỉnh ngưỡng bằng dữ liệu wet-lab.
- Phân tích mới trên ma trận phản ứng chéo (chỉ dựng lại).

## 8. Báo cáo cuối mỗi giai đoạn
Viết bằng tiếng Việt, gồm: việc đã làm; lệnh đã chạy + output rút gọn; file đã đổi; số liệu; vấn đề còn mở.
