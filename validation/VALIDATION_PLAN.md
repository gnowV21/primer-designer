# VALIDATION_PLAN.md — Scientific validation loop
# HG Lab Stem-loop RT-qPCR Primer Designer
# v1.0 — 2026-07-02 · Sync: algorithm v3.0.0 (SPEC_phase2), scoring V4 (SPEC_phase3), SPEC_phase4

---

## 1. Mục tiêu
Đo **độ tin cậy khoa học** của thuật toán: primer tool sinh ra có đúng nguyên lý stem-loop RT-qPCR ([Chen05]) và khớp kỳ vọng từ tài liệu không. Đây là bước thuyết phục nhất khi trình bày tool cho lab/hội đồng.

## 2. Ý tưởng cốt lõi — Ground-truth TẤT ĐỊNH
Với thiết kế Chen-2005, **2/3 primer bị quy định hoàn toàn bởi trình tự mature miRNA**, nên có thể tự suy ra "đáp án đúng" mà không cần bảng primer công bố (vốn khó trích xuất máy):

| Primer | Mức tất định | Đáp án đúng suy từ miRNA |
|---|---|---|
| RT stem-loop | **Hoàn toàn** | `UNIVERSAL_BODY (44 nt cố định)` + `revcomp(6 nt cuối 3′ của miRNA)` [Chen05] |
| Universal reverse | **Hoàn toàn** | hằng số `CCAGTGCAGGGTCCGAGGTA` |
| Forward | **Một phần** | vùng specific = **tiền tố 5′ của miRNA** (cùng chiều); 5′ tail tự do để nâng Tm |

Validator **tự tính lại** các giá trị này từ *chính trình tự tool đã dùng* (`metadata.mirna_sequence`) rồi so sánh → kết quả không phụ thuộc trình tự nhập tay, tránh sai sót trí nhớ.

## 3. Bộ dữ liệu (`reference_mirnas.json`)
- **Panel chính:** hsa-miR-21-5p (chứng dương kinh điển), miR-16-5p (normalizer), miR-155-5p (23 nt), miR-122-5p, cel-miR-39-3p (spike-in, cross-species).
- **Cụm let-7 (a/c/f):** kiểm **phân biệt đặc hiệu** — [Wang17] cho thấy các thành viên khác nhau **1 nt**, chia sẻ 16 nt đầu 5′ → module cross-reactivity PHẢI cờ siblings.
- **Edge cases:** synthetic 17 nt (E1), GC thấp (E4), GC cao (E5), poly-G (E6) — kiểm `edge_cases` (SPEC_phase4 §7).
- Script **mô phỏng luồng người dùng thật:** `GET /api/mirbase/<id>` lấy sequence → `POST /api/design`.

## 4. Metric & Acceptance criteria

**A. Tất định (phải PASS 100% — nếu fail là bug thuật toán):**
- RT primer: giữ đúng body cố định; 6 nt overhang = `revcomp(6 nt cuối)`; tổng dài = 50 nt.
- Universal reverse == hằng số.
- Forward specific region là tiền tố 5′ của miRNA; forward kết thúc bằng specific region.

**B. Hợp lý nhiệt động (nên PASS; fail = review tham số):**
- Forward Tm ∈ [55, 65] °C (annealing 60 °C [Chen05]); GC ∈ [40, 60]% [IDT][MIQE09]; amplicon ∈ [40, 110] bp.
- Top set không có `has_critical_flag`.

**C. Đặc hiệu (concordance tài liệu):**
- let-7a → siblings let-7c/f được cờ `HIGH`/`IDENTICAL` (khớp [Wang17]).

**D. Edge-case:** đúng code E1/E4/E5/E6 kỳ vọng (SPEC_phase4 §7).

**Ngưỡng chấp nhận tổng:** nhóm A = 100%; nhóm B ≥ 90% panel; C, D = 100%. Script trả exit code ≠ 0 nếu bất kỳ check nào fail (dùng được cho CI).

## 5. Cách chạy
```bash
# Terminal 1
cd backend && python app.py            # http://localhost:5000
# Terminal 2
pip install requests
python validation/validate_primers.py \
    --base-url http://localhost:5000 \
    --dataset validation/reference_mirnas.json \
    --out validation/results.csv
# Regenerate the Benchmark page's validation block from results.json (committed script):
python validation/build_benchmark_validation.py --in-place
```
Kết quả: bảng PASS/FAIL trên console + `results.csv` + `results.json` (chi tiết từng target, overhang expected vs actual, Tm/GC/amplicon, siblings flagged), và khối `validation` trong `benchmark/benchmark_results.json` được **tái sinh bằng script** (không sửa tay). CI chạy `build_benchmark_validation.py --check` (qua `test_validation_block_matches_generator`) để chặn drift.

## 6. Mở rộng (tuỳ chọn)
- **Exact-match với primer công bố:** khi có bảng primer từ paper (vd [Wang17] Table, [Var07]), thêm field `published_forward`/`published_rt` vào dataset để so trùng khớp tuyệt đối.
- **Đối chiếu công cụ khác:** chạy cùng miRNA qua miRPrimer/sRNAPrimerDB, so Tm/GC.
- **Wet-lab loop:** đặt tổng hợp top-1 cho 2–3 miRNA, chạy qPCR thật, kiểm hiệu suất 90–110% [MIQE09] và melting curve đơn đỉnh.
- **CI:** đưa `validate_primers.py` vào GitHub Actions (mock miRBase) như một regression gate cho thuật toán.

### 6.1 Kiểm chứng ma trận phản ứng chéo (2026-11-10, SPEC_phase3 §8.20)

**Câu hỏi.** R(i, j) dự đoán có xếp đúng thứ tự, và có phân loại đúng "có / không phản ứng chéo" so với độ đặc hiệu đo được của assay stem-loop hay không.

**Dữ liệu** — `validation/crossreactivity_<nguồn>.csv`, cột `assay_mirna, target_mirna, measured_value, unit, source_figure_or_table`. Đơn vị `%` (phát hiện tương đối so với khớp hoàn toàn) hoặc `dCq`.
- **Không bịa số liệu:** dòng có `measured_value` trống bị bỏ qua và đếm riêng, không bao giờ được nội suy.

| Nguồn | Phạm vi | Trạng thái | Độc lập? |
|---|---|---|---|
| Chen 2005, NAR 33:e179, **Figure 7** | 5 × 5: let-7a, b, c, d, e (bài không có let-7f/g/i hay miR-98); đơn vị % | template 25 dòng, **trống**: giá trị chỉ in trong ảnh hình, không có trong bảng/chữ — cần điền tay | **Không** — hằng số ΔCq_RT (3,7 %, 0,1 %, ≤ 0,3 %) lấy từ bài này; so sánh chỉ kiểm tra cài đặt |
| Mestdagh 2014, Nat Methods 11:809 (miRQC, doi 10.1038/nmeth.3014) | cặp miRNA gần giống nhau, nhiều nền tảng | chỉ có header: không có bản PMC, nature.com yêu cầu đăng nhập | Có — chỉ lấy số của nền tảng TaqMan stem-loop, và ghi rõ trong cột nguồn |

**Chỉ số** (`python -m crossreactivity.validate [--threshold-pct 1]`):
- Spearman ρ giữa R dự đoán và R đo (R đo = % / 100, hoặc 2^−ΔCq);
- ROC AUC (Mann–Whitney) cho "có phản ứng chéo" với R ≥ ngưỡng; mặc định 1 %, đổi theo ngưỡng của bài báo;
- bảng các cặp dự đoán sai phía ngưỡng;
- cặp đường chéo bị loại khỏi phép so sánh.

Kết quả ghi ở `validation/crossreactivity_validation_report.{md,json}`.

**Tiêu chí chấp nhận (đề xuất, chưa chốt):** với nguồn độc lập, ρ ≥ 0,6 và AUC ≥ 0,8. Nguồn vòng tròn (Chen 2005) chỉ dùng làm kiểm tra cài đặt.

**Kiểm tra hợp lý** (đã chạy, đạt): các cặp miRNA cùng độ dài chỉ khác 1–2 vị trí phải có R trung bình lớn hơn 10 lần cặp ngẫu nhiên. Kết quả (algorithm 3.7.0): 322 cặp có thứ tự, R trung bình 0,1445 (trung vị 0,0083; 22,7 % trên 10 %; 3.6.0: 0,1408 và 20,8 %; 3.5.0: 0,1414, trung vị 0,0089, 21,1 %), so với 20.000 cặp ngẫu nhiên có R trung bình 0,000011 (0 % trên 10 %).

**Wet-lab đề xuất** (oligo RNA tổng hợp cùng nồng độ, đo cả SYBR và TaqMan):
- let-7a ↔ let-7c (rG·dT, dự đoán R 3,7 % — điểm hiệu chỉnh);
- let-7a ↔ let-7d và miR-100 ↔ miR-99a (vùng mù giữa trình tự, dự đoán R 0,37 / 1,0);
- miR-30b ↔ miR-30c (indel giữa phân tử, R = 1 do khung độc lập — D-3);
- một cặp ở đỉnh trần FWD (R ≈ 0,32 %, D-4) để biết trần này quá cao hay vừa đủ.

## 7. Nguồn (đã kiểm chứng trên PubMed)
- [Chen05] Chen C et al. *Nucleic Acids Res.* 2005;33(20):e179.
- [Wang17] Wang Y et al. *Mol Med Rep.* 2017;17(3):3690–3696. DOI [10.3892/mmr.2017.8297](https://doi.org/10.3892/mmr.2017.8297) (PMID 29257343).
- [Var07] Varkonyi-Gasic E et al. *Plant Methods* 2007;3:12.
- [MIQE09] Bustin SA et al. *Clin Chem* 2009;55(4):611–622. DOI [10.1373/clinchem.2008.112797](https://doi.org/10.1373/clinchem.2008.112797) (PMID 19246619).
- [Fan19] Fan H et al. *J Biomol Struct Dyn.* 2019;37(11):2867–2874. DOI [10.1080/07391102.2018.1498804](https://doi.org/10.1080/07391102.2018.1498804) (PMID 30101656).

*Thông tin tài liệu trích từ PubMed.*
