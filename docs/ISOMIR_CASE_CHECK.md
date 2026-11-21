# Kiểm in silico các ca isomiR 3′ đã công bố

Tạo bởi `backend/scripts/isomir_case_check.py` ngày 2026-11-21, algorithm 4.0.0. Số liệu đầy đủ: `benchmark/isomir_case_check.json`.

> **Đây là báo cáo, không phải kiểm chứng pass/fail.**
> - Pillman 2019 đo ở đại thực bào chuột/người, bằng assay thương mại không công bố trình tự mồi.
> - isomiRdb gộp mẫu người thuộc mọi loại mô và dịch; share ở đây là pooled.
> - Tham chiếu 22.1 của miR-877-5p và miR-33b-5p dài 20 nt, khác tham chiếu trong bài (miR-877-5p: dạng GACA 24 nt).
> - Tool không đo mức bắt; khoảng ΔCq chỉ lấy từ `ASSAY_DCQ_RT_SHIFT_RANGE` (Schamberger 2014, n = 1–2 miRNA). Lệch ≥ 3 nt không có số đo.

Cách chạy: mỗi miRNA được thiết kế qua Flask test client với mặc định của backend (overhang 6 nt), trình tự lấy từ miRBase 22.1 cục bộ.

**Tóm tắt:** cảnh báo isoform trội bật ở 6/9 ca (miR-877-5p, miR-222-3p, miR-221-3p, miR-27b-3p, miR-27a-3p, miR-107); cờ fold-change ở 8/9; cảnh báo 3′ mức high ở 8/9. Ca không có cảnh báo nào: không có.

## Số liệu từ API

| miRNA | 22.1 (nt) | Overhang | Mức 3′ (median) | Fold-change | Top 3 (pooled · mức bắt) | Đầu 22.1 (pooled) | Isoform trội |
|---|---|---|---|---|---|---|---|
| miR-21-5p | UAGCUUAUCAGACUGAUGUUGA (22) | UGUUGA | moderate (0.487) | có | +1 nt 22.7 % · 0–4 Ct later · n = 2 miRNAs; −1 nt 11.4 % · 0–4 Ct later · n = 2 miRNAs; +2 nt 4.1 % · 0–4 Ct later · n = 2 miRNAs | 51.9 % | — |
| miR-33b-5p | GUGCAUUGCUGUUGCAUUGC (20) | CAUUGC | high (0.968) | có | −1 nt 26.0 % · 0–4 Ct later · n = 2 miRNAs; +1 nt 23.1 % · 0–4 Ct later · n = 2 miRNAs; −2 nt 1.5 % · 3–4 Ct later · n = 1 miRNA | 46.5 % | — |
| miR-877-5p | GUAGAGGAGAUGGCGCAGGG (20) | GCAGGG | high (0.887) | không | +3 nt 16.8 % · not measured (≥ 3 nt); +2 nt 13.8 % · 0–4 Ct later · n = 2 miRNAs; +4 nt 11.8 % · not measured (≥ 3 nt) | 12.7 % | ✔ |
| miR-222-3p | AGCUACAUCUGGCUACUGGGU (21) | CUGGGU | high (0.797) | có | +3 nt 35.9 % · not measured (≥ 3 nt); +4 nt 16.9 % · not measured (≥ 3 nt); +2 nt 15.3 % · 0–4 Ct later · n = 2 miRNAs | 8.8 % | ✔ |
| miR-221-3p | AGCUACAUUGUCUGCUGGGUUUC (23) | GGUUUC | high (0.843) | có | −1 nt 30.0 % · 0–4 Ct later · n = 2 miRNAs; −2 nt 10.8 % · 3–4 Ct later · n = 1 miRNA; +U non-templated 6.7 % · assumed like +1 nt (non-templated, not measured) | 29.6 % | ✔ |
| miR-27b-3p | UUCACAGUGGCUAAGUUCUGC (21) | UUCUGC | high (0.637) | có | −1 nt 38.0 % · 0–4 Ct later · n = 2 miRNAs; +U non-templated 4.8 % · assumed like +1 nt (non-templated, not measured); −2 nt 4.1 % · 3–4 Ct later · n = 1 miRNA | 38.1 % | ✔ |
| miR-27a-3p | UUCACAGUGGCUAAGUUCCGC (21) | UUCCGC | high (0.792) | có | −1 nt 34.2 % · 0–4 Ct later · n = 2 miRNAs; −2 nt 5.4 % · 3–4 Ct later · n = 1 miRNA; +U non-templated 5.1 % · assumed like +1 nt (non-templated, not measured) | 28.2 % | ✔ |
| miR-107 | AGCAGCAUUGUACAGGGCUAUCA (23) | CUAUCA | high (0.662) | có | −1 nt 40.3 % · 0–4 Ct later · n = 2 miRNAs; −1 nt then +U 10.6 % · not measured; +U non-templated 1.0 % · assumed like +1 nt (non-templated, not measured) | 43.2 % | ✔ |
| miR-30a-5p | UGUAAACAUCCUCGACUGGAAG (22) | UGGAAG | high (0.782) | có | +2 nt 18.5 % · 0–4 Ct later · n = 2 miRNAs; +1 nt 14.2 % · 0–4 Ct later · n = 2 miRNAs; −1 nt 5.3 % · 0–4 Ct later · n = 2 miRNAs | 45.9 % | — |

## Đối chiếu với quan sát đã công bố

### hsa-miR-21-5p

- **Đã công bố (Magee 2017):** Stem-loop TaqMan cho dạng chuẩn bắt cả 0|+1, −1|0, −1|+1; trong tế bào chuyển nạp không phân biệt được các dạng.
- **Tham chiếu:** Ký hiệu 5′|3′ của bài gồm cả lệch đầu 5′; tool chỉ xét đầu 3′.
- **Tool:** mức 3′ **moderate** (median 0.487), không có cảnh báo 3′ mức high; cờ fold-change **có**; isoform trội **không**: top 1 +1 nt 0.227 so với đầu 22.1 0.519 (tỉ lệ 0.437 < 0.8).
- **Nhận xét:** Khớp: bảng xếp ±1/+2 nt vào khoảng đo được 0–4 Ct, tức assay đo tổng các dạng. Đầu 22.1 vẫn là dạng nhiều nhất nên không có cảnh báo isoform trội.

### hsa-miR-33b-5p

- **Đã công bố (Schamberger 2014):** Assay "GC" và "GCA" bắt chéo nhau, trễ 2–4 Ct; giải trình tự thấy dạng dài hơn nhiều hơn tham chiếu.
- **Tham chiếu:** "GC" = đầu 3′ của 22.1 (20 nt); "GCA" = +1 nt so với 22.1.
- **Tool:** mức 3′ **high** (median 0.968); cờ fold-change **có**; isoform trội **không**: top 1 −1 nt 0.260 so với đầu 22.1 0.465 (tỉ lệ 0.559 < 0.8).
- **Nhận xét:** Khớp về mức bắt: khoảng 0–4 Ct của ±1 nt chứa chính số đo 2–4 Ct của miRNA này. Khác về tỉ lệ: isomiRdb (pooled) cho dạng +1 ít hơn đầu 22.1, còn bài thấy dạng dài hơn nhiều hơn. Mẫu khác nhau, nên tool không bật cảnh báo isoform trội.

### hsa-miR-877-5p

- **Đã công bố (Schamberger 2014):** Assay GACA/GAC bắt nhau gần 0 Ct; GA trễ khoảng 3 Ct; assay GA bắt cả ba dạng.
- **Tham chiếu:** Bài dùng dạng GACA (24 nt) làm tham chiếu; 22.1 dài 20 nt (…CAGGG). So với 22.1: GA = +2, GAC = +3, GACA = +4 nt. Dạng 20 nt của 22.1 không được thử trong bài.
- **Tool:** mức 3′ **high** (median 0.887); cờ fold-change không; isoform trội **có**: top 1 +3 nt 0.168 so với đầu 22.1 0.127 (tỉ lệ 1.323 ≥ 0.8).
- **Nhận xét:** Khớp với cách ghi: bài chỉ so các dạng 22–24 nt với nhau, không có assay nhắm đầu 20 nt của 22.1, nên +3/+4 ghi "not measured" là đúng. isomiRdb cũng thấy dạng dài nhiều hơn đầu 22.1, nên cảnh báo isoform trội bật.

### hsa-miR-222-3p

- **Đã công bố (Nejad 2018; Pillman 2019):** TaqMan 21 nt bắt isoform 22–25 nt; isoform dài trội; không thấy mức giảm 70 % sau IFN.
- **Tham chiếu:** TaqMan 21 nt = độ dài 22.1; isoform 22–25 nt = +1 đến +4 nt so với 22.1.
- **Tool:** mức 3′ **high** (median 0.797); cờ fold-change **có**; isoform trội **có**: top 1 +3 nt 0.359 so với đầu 22.1 0.088 (tỉ lệ 4.080 ≥ 0.8).
- **Nhận xét:** Khớp: cảnh báo isoform trội và cờ fold-change đều bật. Tool ghi +3/+4 là "not measured", không nói assay bắt kém; Nejad thấy TaqMan vẫn bắt các dạng này nhưng không có số Ct theo từng dạng, nên tool không có số để dùng.

### hsa-miR-221-3p

- **Đã công bố (Pillman 2019):** Assay nhắm dạng dài hơn dạng trội 1 nt; báo "giảm" trong khi tổng tăng.
- **Tham chiếu:** Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.
- **Tool:** mức 3′ **high** (median 0.843); cờ fold-change **có**; isoform trội **có**: top 1 −1 nt 0.300 so với đầu 22.1 0.296 (tỉ lệ 1.014 ≥ 0.8).
- **Nhận xét:** Khớp: dạng trội là −1 nt, tức đầu 22.1 mà mồi RT nhắm dài hơn dạng trội 1 nt như bài mô tả; cảnh báo isoform trội bật.

### hsa-miR-27b-3p

- **Đã công bố (Pillman 2019):** Assay nhắm dạng dài hơn dạng trội 1 nt; báo "giảm" trong khi tổng tăng.
- **Tham chiếu:** Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.
- **Tool:** mức 3′ **high** (median 0.637); cờ fold-change **có**; isoform trội **có**: top 1 −1 nt 0.380 so với đầu 22.1 0.381 (tỉ lệ 0.997 ≥ 0.8) — chỉ bật nhờ mốc 0,8; luật R1 (> 1) không bật.
- **Nhận xét:** Khớp nhưng sát ngưỡng: dạng −1 nt gần bằng đầu 22.1; cảnh báo chỉ bật nhờ mốc 0,8 (luật R1 "> 1" sẽ bỏ sót ca này).

### hsa-miR-27a-3p

- **Đã công bố (Pillman 2019):** Kết luận RT-qPCR đã công bố lệch so với RNA-seq mức isoform.
- **Tham chiếu:** Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.
- **Tool:** mức 3′ **high** (median 0.792); cờ fold-change **có**; isoform trội **có**: top 1 −1 nt 0.342 so với đầu 22.1 0.282 (tỉ lệ 1.213 ≥ 0.8).
- **Nhận xét:** Khớp: dạng −1 nt nhiều hơn đầu 22.1; cảnh báo isoform trội bật.

### hsa-miR-107

- **Đã công bố (Pillman 2019):** Kết luận RT-qPCR đã công bố lệch so với RNA-seq mức isoform.
- **Tham chiếu:** Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.
- **Tool:** mức 3′ **high** (median 0.662); cờ fold-change **có**; isoform trội **có**: top 1 −1 nt 0.403 so với đầu 22.1 0.432 (tỉ lệ 0.933 ≥ 0.8) — chỉ bật nhờ mốc 0,8; luật R1 (> 1) không bật.
- **Nhận xét:** Khớp nhưng sát ngưỡng: dạng −1 nt gần bằng đầu 22.1; cảnh báo chỉ bật nhờ mốc 0,8.

### hsa-miR-30a-5p

- **Đã công bố (Pillman 2019):** Kết luận RT-qPCR đã công bố lệch so với RNA-seq mức isoform.
- **Tham chiếu:** Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.
- **Tool:** mức 3′ **high** (median 0.782); cờ fold-change **có**; isoform trội **không**: top 1 +2 nt 0.185 so với đầu 22.1 0.459 (tỉ lệ 0.403 < 0.8).
- **Nhận xét:** Cảnh báo isoform trội không bắt được: trong isomiRdb (pooled), đầu 22.1 vẫn nhiều hơn hẳn biến thể lớn nhất. Tool vẫn có cảnh báo 3′ mức high và cờ fold-change. Sai lệch trong bài có thể đến từ tỉ lệ isoform đổi theo kích thích ở đại thực bào, điều mà dữ liệu gộp không thấy.
