# Dry-run isomiR 3′ — Phần 1 (`PROMPT_isomir_variants_4.0.0.md`)

Ngày 2026-11-21, nhánh `feat/isomir-variants` (từ `master` @ `22d80dd`). Chỉ đọc: không thiết kế, không sửa code web app.
Script: `backend/scripts/isomir_variants_dryrun.py` → `benchmark/isomir_variants_dryrun.json` (đủ từng dòng).
Nguồn: `backend/data/known_3prime_isomir_mirnas.json` (isomiRdb) và `backend/db/mirbase.db` (miRBase 22.1, nguồn của `/api/mirbase`). Overhang 6 nt, trừ khi ghi khác. Share là **pooled** trên mọi mẫu isomiRdb.

## Luật đã duyệt (chủ dự án, 2026-11-21)

| Trường hợp | relation | Lớp mức bắt |
|---|---|---|
| Theo khuôn, ±1–2 nt, `rt_axis` cùng register, không mismatch | `trimmed` / `extended` | `measured_range` (khoảng từ `ASSAY_DCQ_RT_SHIFT_RANGE`) |
| Theo khuôn, register hoặc overhang không khớp | `trimmed` / `extended` | `other` (kèm lý do) |
| Theo khuôn, lệch ≥ 3 nt | `trimmed` / `extended` | `outside_measured_range`, ΔCq `null`, không gọi `rt_axis` |
| NTA dài thêm 1–2 nt | `nta` | `assumed_templated` (khoảng của "longer") |
| NTA dài thêm ≥ 3 nt | `nta` | `outside_measured_range` |
| Cắt rồi thêm NTA (hiện "−1 nt then +U") | `nta` + `trimmed_nt` | `not_measured`, ΔCq `null`, không gọi `rt_axis` |
| mlv3p, mv | `other` | `not_measured` |
| Lệch đầu 5′ / khác ở giữa (ở miRNA có tham chiếu đã xác nhận) | `reference_mismatch` | `not_assessed`: "differs from miRBase 22.1 — not assessed" |
| Mọi biến thể của miRNA mà tham chiếu isomiRdb có thể khác 22.1 | (giữ) | `not_assessed`: bảng hiện một dòng "isomiRdb reference may differ from miRBase 22.1 — not assessed" |
| Trình tự thiết kế khác bản 22.1 của tên đó (ví dụ dán dạng GACA 24 nt của miR-877-5p) | (giữ) | `not_assessed`: "design sequence differs from miRBase 22.1 — not assessed"; không bật cảnh báo isoform trội |

- Nhãn hiển thị: nhãn `nta#X#k` chỉ đếm số nt không theo khuôn. Khi đuôi dài hơn k, phần đầu của đuôi là nt theo khuôn. Ví dụ `nta#T#1` trên đuôi `UU` hiện là "+1 nt then +U". Lớp vẫn xếp theo tổng độ dài.

- **Lý do có lớp `not_measured` cho "cắt rồi thêm NTA":** NTA ở đầu sát thân stem chưa được đo bằng qPCR. Giá trị 3,5 Ct của Czimmerer 2013 chỉ đo mismatch nằm bên trong, nên không áp dụng cho trường hợp này.
- **Cảnh báo isoform trội = R2:** so trên giá trị đã làm tròn 3 chữ số, bật khi top 1 ≥ 0,8 × share đầu 3′ chuẩn. **0,8 là mốc riêng của tool, chưa hiệu chỉnh.** Không bật ở miRNA mà tham chiếu có thể khác 22.1.
- **"Tham chiếu có thể khác 22.1" (phương án B):** miRNA có biến thể lệch đầu 5′ hoặc khác ở giữa (hoặc nhãn lv3pT/lv3pE mà đuôi khác 22.1), **và** không có biến thể lv3pT/lv3pE nào khớp đúng 22.1. Biến thể mang nhãn `mv` không tính.

## Tổng quan và đối chiếu số

| | Số |
|---|---|
| miRNA hsa có dữ liệu 3′ / có biến thể | 2032 / 1177 |
| Biến thể (top 3) | 2927 — lv3pT 1581, nta 782, lv3pE 548, mlv3p 15, mv 1 |
| miRNA có NTA trong top 3 | 591 |
| miRNA thiếu trình tự 22.1 | 0 |

- **537 hay 542?** 526 biến thể không khớp tiền tố (241 + 173 + 112) **đã gồm** 5 biến thể mlv3p. Cộng thêm 15 mlv3p + 1 mv thì 5 ca này bị đếm hai lần. Đúng là 526 + 11 = 537.
- **216 hay 214?** 216 biến thể lệch > 2 nt có 2 ca nhãn mlv3p/mv (miR-548ae-5p +3, miR-8485 −4). Hai ca này thuộc lớp `not_measured`, không phải `outside_measured_range`.
- **Các lớp cộng đủ 2927** (script `assert`).

## 1.1 Nhãn isomiRdb so với trình tự 22.1

- **Tiền tố 5′ không khớp: 526 biến thể ở 385 miRNA.**
  - 241 biến thể có đầu 3′ bị thay: cắt rồi thêm NTA, chủ yếu −1 +1 (193 ca), ví dụ let-7b-3p `…CCUUCCC` → `…CCUUCCU`.
  - 173 biến thể lệch đầu 5′. Tất cả mang nhãn `nta`.
  - 112 biến thể khác ở giữa, thường đúng 1 nt. Ví dụ A→G ở vị trí 6 của miR-376a/b/c-3p, trông như RNA editing hoặc SNP.
- **Nhãn lệch với độ lệch tính từ trình tự: 68 ca, đều là `nta`.** Ví dụ nhãn `nta#A#1` nhưng trình tự dài thêm 2–4 nt (theo khuôn + NTA). Nhãn lv3pT/lv3pE có tiền tố khớp: 0 ca lệch.
- **Nghi tham chiếu khác: 179 miRNA**, gồm 175 miRNA có biến thể lệch 5′ hoặc khác ở giữa, và 5 miRNA có nhãn lv3p nhưng đuôi khác 22.1 (miR-4443 thuộc cả hai nhóm).
  - Trong đó 91 miRNA có biến thể lv3p khớp đúng 22.1, tức tham chiếu là 22.1 và nhãn isomiRdb chỉ ghi thiếu.
  - **Còn 88 miRNA "tham chiếu có thể khác 22.1".**

## 1.2 Lớp mức bắt

| Lớp | Tất cả biến thể | Top 1 |
|---|---|---|
| `measured_range` | 1855 | 923 |
| `assumed_templated` | 313 | 58 |
| `outside_measured_range` | 213 | 49 |
| `not_measured` | 243 | 39 |
| `other` | 0 | 0 |
| `not_assessed` | 303 | 108 |
| **Tổng** | **2927** | **1177** |

## Kiểm register của `rt_axis` ở overhang 5, 6 và 7 nt

Kiểm trên 1855 biến thể theo khuôn ±1–2 nt có tiền tố khớp:

| Overhang | Đúng register |
|---|---|
| 6 nt | 1855/1855 |
| 7 nt | 1855/1855 |
| 5 nt | 1851/1855 |

Bốn ca lệch ở 5 nt đều do đầu 3′ lặp lại, nên một register khác cũng ghép hết overhang với cùng ΔCq 0:
- miR-1228-5p `…GUGUG`: −1 và −2 nt.
- miR-498-5p `…UUUUUC`: −2 nt.
- miR-7-5p `…UUGUU`: −2 nt.

Theo luật 2.1, bốn ca này xếp lớp `other` kèm lý do. Phần 2 có test cho cả ba độ dài overhang.

## 1.3 Giả tạo ±2 nt của `rt_axis`

- Có 216 biến thể tiền tố khớp, lệch > 2 nt.
- **201/216 bị `rt_axis` gán 8,0 Ct ở register 0**, ví dụ miR-222-3p +3/+4 nt và miR-877-5p +3/+4 nt.
- 15 ca còn lại nhận 3,5–7,75 Ct, vì có một register lệch tình cờ khớp gần hết. Đây cũng là giả tạo.
- Theo luật mới, mọi ca này không gọi `rt_axis` và không có ΔCq.

## 1.4 Cảnh báo isoform trội

| Luật | Số miRNA bật / 2032 |
|---|---|
| R1 `>` | 256 |
| R1 `≥` | 257 |
| R2, chưa loại ca tham chiếu nghi ngờ | 322 |
| **R2 đã duyệt** (loại 18 miRNA tham chiếu có thể khác 22.1) | **304** — high 289, moderate 13, low 2 |

Lớp mức bắt của top 1 trong 304 ca: đo được 253, ngoài khoảng 19, `not_measured` 14, NTA giả định 13, `not_assessed` (ở mức biến thể) 5.

## (a) 88 miRNA tham chiếu có thể khác 22.1 đang có cảnh báo cũ

- Cảnh báo 3′ mức high: **26**. Cờ fold-change: **31**. Có ít nhất một trong hai: **42**.
- Danh sách 42 ca này và đủ 88 miRNA được ghi ở `AUDIT_REPORT.md` ISO-09 và trong JSON (`reference_check`).
- PR này không sửa các cảnh báo cũ.

## 1.5 Chín ca đã công bố

Không ca nào thuộc nhóm tham chiếu nghi ngờ.

| miRNA | 22.1 (nt) | Overhang 6 nt | Mức 3′ (median) | Fold-change | Top 3 (pooled, lớp) | Đầu 3′ chuẩn (pooled) | R2 |
|---|---|---|---|---|---|---|---|
| miR-21-5p | UAGCUUAUCAGACUGAUGUUGA (22) | UGUUGA | moderate (0.487) | có | +1 nt 22.7 % (đo được); −1 nt 11.4 % (đo được); +2 nt 4.1 % (đo được) | 51.9 % | — |
| miR-33b-5p | GUGCAUUGCUGUUGCAUUGC (20) | CAUUGC | high (0.968) | có | −1 nt 26.0 % (đo được); +1 nt 23.1 % (đo được); −2 nt 1.5 % (đo được) | 46.5 % | — |
| miR-877-5p | GUAGAGGAGAUGGCGCAGGG (20) | GCAGGG | high (0.887) | không | +3 nt 16.8 % (ngoài khoảng); +2 nt 13.8 % (đo được); +4 nt 11.8 % (ngoài khoảng) | 12.7 % | ✔ |
| miR-222-3p | AGCUACAUCUGGCUACUGGGU (21) | CUGGGU | high (0.797) | có | +3 nt 35.9 % (ngoài khoảng); +4 nt 16.9 % (ngoài khoảng); +2 nt 15.3 % (đo được) | 8.8 % | ✔ |
| miR-221-3p | AGCUACAUUGUCUGCUGGGUUUC (23) | GGUUUC | high (0.843) | có | −1 nt 30.0 % (đo được); −2 nt 10.8 % (đo được); +U NTA 6.7 % (giả định) | 29.6 % | ✔ |
| miR-27b-3p | UUCACAGUGGCUAAGUUCUGC (21) | UUCUGC | high (0.637) | có | −1 nt 38.0 % (đo được); +U NTA 4.8 % (giả định); −2 nt 4.1 % (đo được) | 38.1 % | ✔ |
| miR-27a-3p | UUCACAGUGGCUAAGUUCCGC (21) | UUCCGC | high (0.792) | có | −1 nt 34.2 % (đo được); −2 nt 5.4 % (đo được); +U NTA 5.1 % (giả định) | 28.2 % | ✔ |
| miR-107 | AGCAGCAUUGUACAGGGCUAUCA (23) | CUAUCA | high (0.662) | có | −1 nt 40.3 % (đo được); −1 nt then +U 10.6 % (not measured); +U NTA 1.0 % (giả định) | 43.2 % | ✔ |
| miR-30a-5p | UGUAAACAUCCUCGACUGGAAG (22) | UGGAAG | high (0.782) | có | +2 nt 18.5 % (đo được); +1 nt 14.2 % (đo được); −1 nt 5.3 % (đo được) | 45.9 % | — |

- "Đo được" là 0–4 Ct (n = 2 miRNA) cho ±1 nt và +2 nt, và 3–4 Ct (n = 1) cho −2 nt.
- miR-33b-5p có median 0,968 nhưng pooled chỉ 0,535. Đây là lý do không trộn median và pooled trong cùng một câu.
