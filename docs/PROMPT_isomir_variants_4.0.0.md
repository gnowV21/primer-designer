# Nhiệm vụ: hiện isoform 3′ từ isomiRdb + cảnh báo isoform trội (algorithm vẫn 4.0.0)

> Nguồn insight: bản tổng hợp 6 bài của chủ dự án (Schamberger & Orbán 2014; Magee 2017; Nejad 2018; Pillman 2019; McAllan 2025; Gómez-Martín 2025). Phạm vi do chủ dự án chốt ngày 2026-11-21.

Đọc trước: `CLAUDE.md`, `HANDOFF_THESIS_STATUS.md` §4 và §7, `AUDIT_REPORT.md` ISO-01…ISO-06, `docs/THESIS_FREEZE_4.0.0.md`, `docs/REVIEW_panel_4.0.0.md` §5 và §11.
Code liên quan: `backend/algorithm/specificity_check/isomir_flag.py`, `assay_model.py` (`rt_axis`), `constants.py` (`ASSAY_DCQ_RT_3P_*`, `ASSAY_DCQ_RT_SHIFT_RANGE`, `ASSAY_SHIFT_EVIDENCE_NOTE`, `ISOMIR_3P_*`), `stemloop_rt.py` (lời gọi `check_3prime_isomir_flag`, khoảng dòng 132), `frontend/src/pages/SearchPage/ResultsSection/index.jsx` (`SharedPrimers`, `PANEL_WARNING_FIELDS`), `backend/routes/export.py`, `backend/tests/test_isomir_flag.py`, `e2e/tiered-ui.spec.js` (`isomir-note`).
Trao đổi bằng tiếng Việt; code, UI, commit message bằng tiếng Anh.

## Bối cảnh

- `master` @ `22d80dd`, algorithm 4.0.0 đã đóng băng (tag `thesis-freeze-4.0.0`). Sau tag chỉ được thay đổi không đổi output.
- isomiR là **cảnh báo phụ** của khóa luận, không chấm điểm. Không chạm vào chấm điểm, xếp hạng, tầng, BLAST hay hằng số ΔCq.
- Tool đã có: mô hình ΔCq lệch đầu 3′ (±1 nt 0 Ct, khoảng 0–4, n = 2 miRNA; −2 nt 3 Ct, khoảng 3–4, n = 1); tỉ lệ isoform 3′ từ isomiRdb (42.494 mẫu, nhãn lv3p/mlv3p/nta); cảnh báo fold-change (Nejad 2018); ghi chú mẫu dịch sinh học; cờ isomiR 5′ cho 8 miRNA.

Chỗ còn thiếu (đã kiểm trên dữ liệu ngày 2026-11-21):

1. `three_prime_isomir.dominant_3prime_variants` (top 3 isoform 3′, pooled share) đã có trong response API nhưng **UI và export không hiện ở đâu**.
2. Ở **257/2032** miRNA người có dữ liệu biến thể, isoform 3′ phổ biến nhất có pooled share lớn hơn phần reads mang đầu 3′ chuẩn (`1 − pooled_3prime_fraction`). Ví dụ: miR-222-3p (+3 nt 35,9 % so với chuẩn 8,8 %), miR-877-5p, miR-27a-3p. Các ca sát ngưỡng: miR-221-3p (−1 nt 0,300 so với 0,296), miR-27b-3p (0,380 so với 0,381).
3. Câu cảnh báo 3′ viết isoform ±1 nt được bắt "about as well as the canonical form". Câu này chỉ đúng với miR-877-5p; miR-33b-5p trễ 2–4 Ct (ISO-01 đã chuyển giá trị sang khoảng, nhưng câu chữ chưa theo).
4. **`rt_axis` chỉ thử lệch ±2 nt.** Với biến thể dài hơn ≥ 3 nt, nó trả 8,0 Ct "≥ 2 overhang mismatches" ở register 0, ví dụ miR-222-3p 24/25 nt, miR-877-5p 23/24 nt. Đây là giả tạo của mô hình, không phải phân biệt thật: Nejad 2018 thấy TaqMan stem-loop 21 nt cho miR-222-3p vẫn bắt isoform 22–25 nt. Không được đưa số này lên UI.
5. NTA (+A/+U) nằm trong top 3 của **591/2032** miRNA. `rt_axis` coi chúng như đầu 3′ dài thêm theo khuôn mẫu (0 Ct), nhưng chưa bài qPCR nào đo NTA.
6. Trình tự miRBase 22.1 khác trình tự tham chiếu trong các bài: hsa-miR-877-5p ở 22.1 dài 20 nt (…CAGGG), trong khi Schamberger dùng dạng GACA 24 nt làm tham chiếu; hsa-miR-33b-5p ở 22.1 dài 20 nt.

## Quyết định đã chốt (không mở lại)

- **Phiên bản:** giữ `ALGORITHM_VERSION = 4.0.0`. Chứng minh mồi, điểm, tầng, thứ hạng và BLAST không đổi bằng `design_equivalence.py`; diff chỉ được nằm ở các trường isomiR. Cập nhật bản tham chiếu và ghi lại diff như đã làm với PR #22.
- **Làm:** (A) hiện top 3 isoform 3′ kèm loại và mức bắt dự kiến theo khoảng; (B) cảnh báo isoform trội khác trình tự miRBase; (C) kiểm in silico các ca đã công bố; (D) **sửa tối thiểu** câu "about as well": chỉ thay cụm đó bằng khoảng đo được, không thêm Pillman hay NTA vào câu này.
- **Không làm:** "độ tinh khiết tín hiệu %" (ISO-05 vẫn mở, ghi vào Thảo luận), bảng nhập phân bố isoform, chế độ cặp assay, dựng lại chỉ mục 5′ (ISO-06), đổi hằng số ΔCq, đổi chấm điểm hay xếp hạng.
- **UI:** bảng isoform nằm trong nút "Why" của dòng isomiR và trong PDF. Chỉ cảnh báo isoform trội được lên dòng chính (vẫn một dòng). Không thêm banner mới (quy tắc trang gọn, `docs/REVIEW_panel_4.0.0.md` §5).

## Quy tắc làm việc

1. Nhánh `feat/isomir-variants` từ `master` → PR → merge.
2. Không đưa số mới từ tài liệu vào mô hình. Mọi mức bắt lấy từ `ASSAY_DCQ_RT_SHIFT_RANGE` hiện có. Ngưỡng mới (nếu có) ghi "mốc riêng của tool, chưa hiệu chỉnh".
3. Không thêm dependency. Script chạy thiết kế trong tiến trình phải có `if __name__ == "__main__":`.
4. Frontend không chép bảng ΔCq: chỉ hiển thị giá trị và chuỗi do API trả.
5. Không trộn median và pooled share trong cùng một câu. Dòng chính hiện đang dùng median (IQR); cảnh báo isoform trội và bảng dùng pooled, và phải ghi rõ chữ "pooled".

## Phần 1 — Dry-run (chỉ đọc). DỪNG chờ duyệt

1.1 Với mỗi miRNA hsa có `top_3prime_variants`, so từng biến thể với trình tự miRBase 22.1 mà `/api/mirbase` dùng: độ lệch đầu 3′ tính từ trình tự (chung tiền tố 5′), loại theo nhãn isomiRdb (`lv3pT` cắt, `lv3pE` kéo dài, `nta#A`/`nta#T` thêm không theo khuôn, `mlv3p`/`mv` khác). Đếm và liệt kê các ca nhãn isomiRdb lệch với độ lệch tính từ trình tự, và các ca tiền tố 5′ không khớp.
1.2 Đếm biến thể theo lớp mức bắt định nghĩa ở 2.1.
1.3 Đếm biến thể có |lệch| > 2 nt và số ca `rt_axis` gán nhầm 8 Ct (xác nhận giả tạo ở mục 4 phần Bối cảnh).
1.4 Luật cảnh báo isoform trội, đo cả hai phương án:
   - R1: pooled share của biến thể lớn nhất > pooled share đầu 3′ chuẩn (đếm sơ bộ: 257/2032).
   - R2: biến thể lớn nhất ≥ 0,8 × đầu 3′ chuẩn (bắt cả ca sát ngưỡng như miR-27b-3p, miR-107; 0,8 là mốc riêng của tool).
   Với mỗi luật: số miRNA bật cảnh báo, và kết quả trên 9 ca ở Phần 4.
1.5 Bảng 9 ca (danh sách ở 4.1): trình tự và độ dài 22.1, overhang 6 nt, mức 3′ hiện tại, cờ fold-change, top 3 biến thể (loại, share, lớp mức bắt), share đầu 3′ chuẩn, R1/R2.
1.6 Ghi `benchmark/isomir_variants_dryrun.json` và một báo cáo ngắn. **Dừng, báo số liệu, đề xuất R1 hoặc R2, chờ tôi chọn.**

## Phần 2 — Backend (sau khi duyệt Phần 1)

2.1 `check_3prime_isomir_flag(..., target_seq=None)`: `stemloop_rt.py` truyền trình tự đích của thiết kế. Bổ sung khóa vào **từng** phần tử của `dominant_3prime_variants` (chỉ thêm khóa; giữ nguyên `sequence_dna`, `label`, `pooled_share`):
   - `shift_3p` (int, tính từ trình tự so với đích);
   - `relation`: `"trimmed"` | `"extended"` | `"nta"` (kèm `added_nt`, viết theo RNA: A/U) | `"other"` | `"reference_mismatch"` (tiền tố 5′ không khớp đích);
   - `rt_capture`: `{class, delta_cq_low, delta_cq_high, n_mirnas, note}`:
     - lệch theo khuôn mẫu, |lệch| ≤ 2 nt → lấy từ `rt_axis(target, variant, overhang_len)` và `shift_range` của nó; `class = "measured_range"`. Nếu register tốt nhất của `rt_axis` khác độ lệch tính từ trình tự, hoặc có mismatch trong overhang, xếp `"other"` và ghi lý do;
     - NTA dài thêm 1–2 nt → cùng khoảng với `"longer"`, `class = "assumed_templated"`, note: non-templated addition not measured by qPCR; treated like a templated extension of the same length;
     - |lệch| > 2 nt → `class = "outside_measured_range"`, ΔCq = `null`, note: no ΔCq measurement for end differences of 3 nt or more. **Không gọi `rt_axis`** cho trường hợp này.
   - Thêm `canonical_3prime_share_pooled = round(1 − pooled_3prime_fraction, 3)`; ghi rõ đây là phần reads mang đầu 3′ của miRBase (kể cả biến thể 5′).
2.2 Cảnh báo isoform trội theo luật được duyệt: `dominant_isoform_risk` (bool) và `dominant_isoform_warning` (str | None). Câu chữ phải nêu:
   - biến thể (loại + pooled share) so với share đầu 3′ chuẩn;
   - mồi RT nhắm đầu 3′ của miRBase 22.1;
   - mức bắt biến thể theo lớp của nó: khoảng đo được, hoặc "not measured";
   - hệ quả: giá trị đo bám theo dạng tham chiếu nhiều hơn dạng trội; nếu tỉ lệ isoform thay đổi giữa các nhóm, fold change có thể sai, kể cả đảo chiều (Pillman 2019: miR-221-3p, miR-27b-3p ở đại thực bào, stem-loop TaqMan). Trích Pillman KA et al. RNA 2019;25(2):232–238, doi:10.1261/rna.069047.118 — **kiểm tra PMID trước khi ghi**;
   - dữ liệu isomiRdb gộp mọi loại mẫu (giữ ghi chú dịch sinh học hiện có).

   Dùng **cả khoảng**, không dùng cận dưới: cận dưới 0 Ct an toàn khi xét đặc hiệu, nhưng với sai lệch fold-change thì ca nguy hiểm là đầu trên (assay bắt kém isoform trội). Nếu thêm vào `warnings[]` (ví dụ `field: "three_prime_isomir_dominant"`), thêm field đó vào `PANEL_WARNING_FIELDS` để không thành banner riêng.
2.3 Sửa tối thiểu (D): trong `isomir_flag.py`, ở docstring (khoảng dòng 118) và chuỗi `warning` (khoảng dòng 175), thay "detected about as well as the canonical form and 2-nt-shorter ones ~3 Ct later" bằng khoảng đọc từ `ASSAY_DCQ_RT_SHIFT_RANGE` (ví dụ "detected 0–4 Ct later (two miRNAs measured) and 2-nt-shorter ones 3–4 Ct later (one miRNA)"), không gõ cứng số. Grep cùng nhận định ở frontend, export và các SPEC; chỉ sửa đúng nhận định đó.
2.4 Test (`backend/tests/test_isomir_flag.py`):
   - biến thể 24 nt (+3) của miR-222-3p → `outside_measured_range`, ΔCq `null` (khóa giả tạo ở mục 4);
   - biến thể +1/−1/+2 của miR-21-5p → `measured_range`, khoảng 0–4, n = 2;
   - `nta#A` của miR-486-5p → `relation = "nta"`, `added_nt = "A"`, `assumed_templated`;
   - cảnh báo isoform trội bật ở miR-222-3p, không bật ở miR-21-5p;
   - chuỗi warning không còn "about as well" và chứa khoảng lấy từ hằng số;
   - miRNA không có dữ liệu (mmu) → không lỗi, không có cảnh báo isoform trội.

## Phần 3 — UI và export

3.1 `SharedPrimers`: `isomir-note` hiện khi `three_prime_isomir_risk || fold_change_bias_risk || dominant_isoform_risk`. Dòng chính vẫn một dòng; khi cảnh báo isoform trội bật, dòng này nêu nó (ví dụ "most common 3′ form +3 nt, 36 % of reads (pooled) vs 9 % with the miRBase end").
3.2 Trong "Why": bảng "Most common 3′ isoforms (isomiRdb, pooled)". Hàng: đầu 3′ chuẩn + top 3. Cột:
   - 3′ end: vài nt cuối, nt khác biệt được tô, chữ RNA;
   - Type: −1 nt / +1 nt / +A non-templated / other;
   - Share of reads;
   - Expected RT capture: "0–4 Ct later · n = 2 miRNAs", "3–4 Ct later · n = 1", "not measured (≥ 3 nt)", "assumed like +1 nt (non-templated, not measured)".

   Sau bảng: các câu cảnh báo hiện có + cảnh báo isoform trội + nguồn. Không tràn ngang ở 360/390 px (`responsive.spec.js`).
3.3 Export: PDF thêm bảng và cảnh báo isoform trội. CSV thêm `three_prime_isomir_dominant_risk`, `three_prime_canonical_share_pooled` và mỗi biến thể một hàng (`sequence|relation|share|capture class`).
3.4 E2E: miR-21-5p có bảng 3 biến thể trong "Why"; miR-222-3p có cảnh báo isoform trội trên dòng chính. Toàn bộ e2e vẫn xanh.

## Phần 4 — Kiểm in silico các ca đã công bố

4.1 Script `backend/scripts/isomir_case_check.py`: thiết kế qua Flask test client (mặc định backend, overhang 6 nt) cho hsa-miR-21-5p, miR-33b-5p, miR-877-5p, miR-222-3p, miR-221-3p, miR-27b-3p, miR-27a-3p, miR-107, miR-30a-5p. Ghi `benchmark/isomir_case_check.json` và `docs/ISOMIR_CASE_CHECK.md`.
4.2 Bảng gồm số liệu ở 1.5 (lấy từ output API cuối cùng) đặt cạnh quan sát đã công bố:
   - miR-21-5p (Magee 2017): stem-loop TaqMan cho dạng chuẩn bắt cả 0|+1, −1|0, −1|+1; trong tế bào chuyển nạp không phân biệt được.
   - miR-33b-5p (Schamberger 2014): assay "GC" và "GCA" bắt chéo nhau, trễ 2–4 Ct; giải trình tự thấy dạng dài hơn nhiều hơn tham chiếu.
   - miR-877-5p (Schamberger 2014): assay GACA/GAC bắt nhau gần 0 Ct; GA trễ khoảng 3 Ct; assay GA bắt cả ba.
   - miR-222-3p (Nejad 2018, Pillman 2019): TaqMan 21 nt bắt isoform 22–25 nt; isoform dài trội; không thấy mức giảm 70 % sau IFN.
   - miR-221-3p, miR-27b-3p (Pillman 2019): assay nhắm dạng dài hơn dạng trội 1 nt; báo "giảm" trong khi tổng tăng.
   - miR-27a-3p, miR-107, miR-30a-5p (Pillman 2019): kết luận RT-qPCR đã công bố lệch so với RNA-seq mức isoform.
4.3 Cột diễn giải: tool có cảnh báo hay không, và vì sao (ví dụ miR-27b-3p sát ngưỡng 0,380 so với 0,381).
4.4 Đầu file `.md` ghi rõ đây là **báo cáo, không phải kiểm chứng pass/fail**: Pillman đo ở đại thực bào chuột/người bằng assay thương mại không công bố trình tự mồi; isomiRdb gộp mẫu người; tham chiếu 22.1 của miR-877-5p và miR-33b-5p dài 20 nt, khác tham chiếu trong bài.

## Phần 5 — Chứng minh không đổi output, tài liệu, PR

5.1 `design_equivalence.py run` trên 200 hsa với `BLAST_CACHE_PATH` trỏ file trống, rồi `compare` với `benchmark/logs/design_equivalence_ref_hsa200.jsonl`. Diff chỉ được ở: khóa mới trong `stemloop_rt.three_prime_isomir`, chuỗi `warning` đã sửa, `message` tương ứng trong `warnings[]`, và mục warning isoform trội (nếu thêm). Báo cáo theo trường: số bản ghi, số cặp chuỗi cũ → mới (như §11 của REVIEW_panel). **Có bất kỳ khác biệt nào ở mồi, điểm, tầng, thứ hạng hay BLAST → dừng và báo.**
5.2 Validation cache trống: 2439/2439, `results.csv` không đổi dòng nào; benchmark 50/50.
5.3 Test: backend (951 + test mới), e2e, `crossreactivity/tests` 29 — tất cả pass.
5.4 Cập nhật bản tham chiếu jsonl kèm ghi chú. Tài liệu:
   - `AUDIT_REPORT.md`: ISO-07 (hiện biến thể + cảnh báo isoform trội), ISO-08 (giả tạo ±2 nt của `rt_axis` ở đường hiển thị), ghi chú sửa câu ở ISO-01;
   - `docs/THESIS_FREEZE_4.0.0.md`: mục mới "Thay đổi hiển thị isomiR sau tag (không đổi output)";
   - `SPEC_phase3.md` §8.18: ghi chú;
   - `HANDOFF_THESIS_STATUS.md`: dòng mới ở §2, số test ở §3;
   - Claude Doc status + changelog dùng chung (nếu phiên có quyền).
5.5 Mô tả PR: luật đã chọn ở Phần 1, tóm tắt diff ở 5.1, số test.
