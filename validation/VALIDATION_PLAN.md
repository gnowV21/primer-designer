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
```
Kết quả: bảng PASS/FAIL trên console + `results.csv` (chi tiết từng target, overhang expected vs actual, Tm/GC/amplicon, siblings flagged).

## 6. Mở rộng (tuỳ chọn)
- **Exact-match với primer công bố:** khi có bảng primer từ paper (vd [Wang17] Table, [Var07]), thêm field `published_forward`/`published_rt` vào dataset để so trùng khớp tuyệt đối.
- **Đối chiếu công cụ khác:** chạy cùng miRNA qua miRPrimer/sRNAPrimerDB, so Tm/GC.
- **Wet-lab loop:** đặt tổng hợp top-1 cho 2–3 miRNA, chạy qPCR thật, kiểm hiệu suất 90–110% [MIQE09] và melting curve đơn đỉnh.
- **CI:** đưa `validate_primers.py` vào GitHub Actions (mock miRBase) như một regression gate cho thuật toán.

## 7. Nguồn (đã kiểm chứng trên PubMed)
- [Chen05] Chen C et al. *Nucleic Acids Res.* 2005;33(20):e179.
- [Wang17] Wang Y et al. *Mol Med Rep.* 2017;17(3):3690–3696. DOI [10.3892/mmr.2017.8297](https://doi.org/10.3892/mmr.2017.8297) (PMID 29257343).
- [Var07] Varkonyi-Gasic E et al. *Plant Methods* 2007;3:12.
- [MIQE09] Bustin SA et al. *Clin Chem* 2009;55(4):611–622. DOI [10.1373/clinchem.2008.112797](https://doi.org/10.1373/clinchem.2008.112797) (PMID 19246619).
- [Fan19] Fan H et al. *J Biomol Struct Dyn.* 2019;37(11):2867–2874. DOI [10.1080/07391102.2018.1498804](https://doi.org/10.1080/07391102.2018.1498804) (PMID 30101656).

*Thông tin tài liệu trích từ PubMed.*
