# So sánh V4 và hệ chấm điểm phân tầng (algorithm 4.0.0)

Tài liệu này so V4 (bản 3.8.2, chấm điểm có trọng số 14 tiêu chí) với hệ phân tầng ưu tiên đặc hiệu của 4.0.0 (`docs/SPEC_scoring_tiered_4.0.0.md`). Mọi số liệu tính trong máy (in silico), chưa hiệu chỉnh bằng wet-lab.

## 1. Hai hệ chấm điểm
- **V4** (`scoringSystem: "v4"`): tổng có trọng số của 13 tiêu chí; GC % và kẹp GC là bộ lọc sơ bộ; 3 lọc cứng cấu trúc (`hard_filter_fallback` khi mọi ứng viên trượt).
- **Tiered** (mặc định 4.0.0). Khóa xếp hạng: `(−S_total, structure_veto, binding_floor_fail, has_v4_violation, −P_total, −F_total, −detailed_score, |Tm − Ta|, sequence)`.
  - **S** (đặc hiệu, tối đa 15): S1 BLAST cùng loài (classifier v7, có bước RT), S2 min ΔCq_assay, S3 biên Tm. Ứng viên S1 = 1 (CRITICAL) hoặc S2 = 1 (CO-AMPLIFIED) bị loại; nếu mọi ứng viên bị loại thì giữ cả và gắn `specificity_fallback`.
  - **Veto mềm:** cấu trúc (một chỉ số con F5 = 1), rồi sàn Tm vùng bám (< 39 °C, QĐ 36); chỉ có tác dụng khi cùng S.
  - **Luật V4** (QĐ 34): khi cùng S và veto, bộ không vi phạm luật V4 xếp trước.
  - **P** (tối đa 5): \|Tm − Ta\|. **F** (tối đa 20): GC %, kẹp GC, sàn Tm vùng bám (≥ 45 °C → 5), cấu trúc. Độ dài vùng đặc hiệu chỉ báo cáo (QĐ 29).
  - **Grade** (QĐ 30): A = qua bước loại, S1 ≥ 4, S2 ≥ 3, S3 ≥ 4, không veto; B = có điểm yếu hoặc không có BLAST; C = fallback.

## 2. Nguồn và mẫu số
- 2656 miRNA hsa, miRBase 22.1. **2472** thiết kế có ứng viên ở hệ tiered; **2253** thiết kế mà V4 cũng có mồi (V4 không thiết kế được 403 miRNA, tiered còn 184).
- Xếp hạng offline trên pool đã ghi (`outputs/freeze_cache/tiered_pools_hsa.jsonl.gz`), với S1 của mọi ứng viên từ lượt BLAST gộp của Giai đoạn 2 (`outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz`). Báo cáo: `benchmark/tiered_stage2c_report.json`.
- Pipeline thật trùng offline:
  - bộ #1 của lượt dựng ma trận (API thật, BLAST thật) trùng #1 offline ở **2472/2472** thiết kế;
  - S1 của 215.860 ứng viên trong cache khác offline ở **0** ca;
  - 20 thiết kế ngẫu nhiên chạy 2 lần cho kết quả giống hệt.
- BLAST gộp (một `blastn` multi-FASTA + một `blastdbcmd` cho mỗi thiết kế) khác cách gọi từng mồi ở **0/31.049** lần gọi (`benchmark/blast_batch_equivalence.json`).

## 3. Bộ #1 trên 2656 miRNA hsa
Bốn cột đầu tính trên 2253 thiết kế (V4 có mồi), cột cuối trên 2472. "tiered G2" = hệ tiered như duyệt ở Giai đoạn 1–2 (F3 + F4 hai phía, chưa QĐ 34/36); "cuối" = QĐ 29 + 33 + 34 + 36 (mặc định 4.0.0).

| Bộ #1 | V4 3.8.2 | tiered G2 | QĐ 29 | cuối | cuối (2472) |
|---|---|---|---|---|---|
| #1 khác V4 | — | 1.670 | 1.764 | 1.723 | — |
| L trung bình (nt) | 14,05 | 14,59 | 14,68 | 14,65 | 14,57 |
| Tm vùng bám, trung vị (p05–p95), °C | 44,4 (36,8–47,8) | 45,2 (37,4–52,2) | 45,9 (34,9–53,5) | 45,7 (35,8–53,4) | 46,0 (35,6–54,6) |
| % Tm vùng bám < 45 °C | 59,5 | 45,5 | 38,4 | 40,3 | 38,1 |
| Mức F4 (thang sàn) 1/2/3/4/5 | 201/178/311/651/912 | 179/148/233/465/1.228 | 211/134/207/314/1.387 | 178/190/225/316/1.344 | 196/195/231/321/1.529 |
| S1 BLAST 1/2/3/4/5 | 67/18/34/115/2.019 | 38/17/23/68/2.107 | 38/17/23/68/2.107 | 38/17/23/68/2.107 | 39/18/24/72/2.319 |
| S2 ΔCq 1/2/3/4/5 | 55/49/61/2.011/77 | 39/45/48/2.043/78 | 39/45/48/2.043/78 | 39/45/48/2.043/78 | 39/48/48/2.257/80 |
| #1 vi phạm luật V4 | 115 | 336 | 300 | 200 | 419 |
| #1 structure_veto | — | 77 | 77 | 77 | 120 |
| Thiết kế có ứng viên bị loại | — | 371 | 371 | 371 | 383 |
| specificity_fallback | — | 53 | 53 | 53 | 54 |
| Trả < 3 bộ | — | 0 | 0 | 0 | 2 |
| Grade A/B/C | — | 2.023/177/53 | 2.023/177/53 | 1.881/319/53 | 2.032/386/54 |

- Ở bảng trên, grade của "tiered G2" và "QĐ 29" tính theo QĐ 30, để so được. V4 dùng thang Excellent/Good/Acceptable/Poor theo điểm tổng, không so trực tiếp.
- Trong 2253 thiết kế, #1 của V4 có S2 = 1 (CO-AMPLIFIED theo mô hình assay) ở 55 ca; ở hệ tiered là 39 ca, và cả 39 đều nằm trong thiết kế fallback.
- **#1 so với #2 được phân định bởi** (cuối, 2472): sequence 1.232, detail 1.088, F 134, tm 10, S 3, v4_rule 2, P 1, structure_veto 1. "sequence" = hòa mọi chỉ số (các biến thể đuôi 5′), thứ tự tùy ý nhưng tất định (QĐ 27).
- **Lý do mức B/C** (cuối, 2472): binding Tm below the 39 °C floor 185; structure veto 118; specificity_fallback 54; S3 Tm margin level 1 54; S2 assay ΔCq level 2 44; S3 Tm margin level 3 33; S3 Tm margin level 2 28; S1 BLAST level 3 24; S1 BLAST level 2 6.

## 4. S1 của bộ #1: V4 so với tiered
Cùng classifier BLAST v7 và cùng mồi RT. S1 của #1 V4 3.8.2 (2253): mức 5/4/3/2/1 = 2.019/115/34/18/67.
- **85 bộ #1 của V4 có S1 ≤ 2** (HIGH hoặc CRITICAL). Hệ tiered chọn bộ #1 có S1 cao hơn ở **34** ca (như nhau ở mọi cấu hình tiered).
  - Từ CRITICAL lên mức 2/3/4/5: 4/9/9/7 (chi tiết chuyển mức đo ở Giai đoạn 2b, `benchmark/tiered_stage2b_report.json`; S1 của #1 không đổi qua QĐ 33/34/36).
  - Từ HIGH lên mức 5: 5.
- 51 ca còn lại không cải thiện được: 38 CRITICAL → CRITICAL (đều là thiết kế fallback) và 13 HIGH → HIGH. Ở các miRNA này, mọi ứng viên đều có off-target mà BLAST đánh giá là nguy cơ.
- Tổng S của #1 tiered cao hơn #1 V4 ở 227 thiết kế; #1 V4 bị hệ tiered loại (S1 = 1 hoặc S2 = 1) ở 78 thiết kế (`benchmark/tiered_stage2b_report.json`).

## 5. Vi phạm luật V4 (QĐ 32/34/36)
Các thiết kế mà #1 tiered vi phạm luật V4 trong khi #1 V4 không vi phạm (2253, đã trừ 219 ca V4 không thiết kế được): G2 221 → QĐ 29 185 → không QĐ 36 55 → **cuối 85**.
- **ΔS > 0** (57 ca): hệ mới chấp nhận vi phạm để được đặc hiệu cao hơn. Luật: `gc_clamp_fail` 28, `gc_out_of_range` 24, `hard_hairpin_tm` 3, `hard_dimer_full_dg` 2, `gc_end_window_fail` 1.
- **ΔS = 0** (28 ca): đều do veto sàn Tm vùng bám quyết định, tức bộ V4 có Tm vùng bám < 39 °C. Luật: `gc_clamp_fail` 22, `hard_dimer_full_dg` 6.
- Bộ #1 của V4 tự vi phạm luật V4 ở 115 thiết kế: chính là các ca `hard_filter_fallback`.

## 6. Bộ validation (201 mục; 2439 check)
- Hồi quy V4: `validate_primers.py --scoring-system v4` cho `results.json` và `results.csv` trùng bản 3.8.2.
- **Tiered: 2439/2439 check đạt.** Theo QĐ 38, 3 mục V4 từ chối (`expected_design_failure`) được chấm ở tiered bằng check `v4_limitation_designed` (mục 6.1).
- So với V4 3.8.2:
  - vùng đặc hiệu của mồi xuôi đổi ở 90/189 mục;
  - L trung bình 14,43 → 14,97 nt;
  - độ trùng trung bình với vùng đặc hiệu của mồi đã công bố 13,74 → 14,10 nt;
  - số mục chung vùng lõi với mồi công bố không đổi (184), mồi RT không đổi.

### 6.1 Ba giới hạn đã biết của V4, thiết kế được ở 4.0.0 (QĐ 38)
Ở V4 các mục này giữ check `expected_design_failure` (V4 từ chối). Ở tiered, check `v4_limitation_designed` đạt khi cả ba điều kiện đúng: thiết kế thành công; vùng đặc hiệu của #1 trùng, hoặc là chuỗi con, của vùng khớp miRNA trong mồi xuôi đã công bố (hoặc ngược lại); và #1 vi phạm ít nhất một luật V4. Ghi chú trong bộ dữ liệu: "known V4 limitation; designed by 4.0.0 (QD 15), published primer used in wet-lab".

| Mục | Check tiered | Vùng đặc hiệu #1 | Vùng của mồi công bố | Luật V4 #1 vi phạm |
|---|---|---|---|---|
| ath-miR171a-3p | `v4_limitation_designed` đạt | TGATTGAGCCGCGCC | TGATTGAGCCGCGCC | `gc_out_of_range,gc_end_window_fail` |
| ebv-miR-BART6-3p | `v4_limitation_designed` đạt | CGGGGATCGGACTA | CGGGGATCGGACTAGC | `gc_out_of_range` |
| mmu-miR-124-3p | `v4_limitation_designed` đạt | TAAGGCACGCGG | TAAGGCACGCGG | `gc_end_window_fail` |

## 7. Ma trận phản ứng chéo hsa (mồi #1, mô hình assay)
| | V4 3.8.2 | 4.0.0 tiered |
|---|---|---|
| Số assay | 2.253 | 2.472 |
| Cặp ngoài đường chéo HIGH / MEDIUM / LOW | 195 / 111 / 20.709 | 172 / 105 / 22.620 |
| Cặp gần giống (khác 1–2 vị trí, 322 cặp): R trung bình / % R > 10 % | 0,133 / 19,3 | 0,072 / 13,0 |

HIGH ngoài đường chéo = số assay đếm ở mức HIGH trừ đường chéo. LOW tăng chủ yếu vì có thêm 219 assay.

## 8. BLAST và thời gian
- Thiết kế không cache (20 miRNA hsa, `random.Random(2026)`): **p50 9,78 s, p90 11,89 s** (giới hạn 15 s), trong đó BLAST p50 8,07 s. Trước khi gộp, BLAST một thiết kế mất khoảng 213 s.
- Lề an toàn Tm của BLAST (`benchmark/blast_tm_gate_sensitivity.json`, 175 mồi của bộ validation, lề 10 °C): SAFE 95 → 105, CRITICAL 54 → 51 (V4 → tiered).

## 9. Thiết kế `specificity_fallback` (54) và kiểm tra wet-lab
Mọi ứng viên của các miRNA này đều bị loại vì BLAST CRITICAL hoặc ΔCq CO-AMPLIFIED. Tool vẫn trả 3 bộ, kèm grade C. Danh sách đầy đủ ở `benchmark/tiered_fallback_list.csv`; cột `wetlab_check` ghi phản ứng chéo cần kiểm.

- Off-target chính của S2: `other` 35, `shifted_3p` 13, `shifted_5p` 3; S2 không loại 3. Nguyên nhân bị loại: cả S1 và S2 ở 48 thiết kế, chỉ S1 ở 3, chỉ S2 ở 3.
- **Ưu tiên kiểm phản ứng chéo ở wet-lab:**
  1. **hsa-let-7a-5p**, một trong 6 ứng viên wet-lab, rơi vào fallback do let-7d-5p (ΔCq 1,43; BLAST CRITICAL). Thí nghiệm let-7a nên có đối chứng let-7d (và các thành viên let-7 khác) để đo tín hiệu chéo thật.
  2. hsa-miR-17-5p và hsa-miR-20a-5p (ca mẫu của SPEC) phản ứng chéo với miR-106a-5p / miR-20b-5p (họ miR-17).
  3. Các cặp lệch đầu (`shifted_3p` / `shifted_5p`, ví dụ họ miR-548, miR-520): không mồi nào tách được; nên đo tổng tín hiệu.

| miRNA | Họ seed | Off-target chính (loại) | #1: S1 / min ΔCq | Kiểm tra wet-lab |
|---|---|---|---|---|
| hsa-let-7a-5p | let-7 | hsa-let-7d-5p (other) | CRITICAL / 1.43 | co-detection of hsa-let-7d-5p (other) |
| hsa-let-7d-5p | let-7 | hsa-let-7a-5p (other) | CRITICAL / 1.71 | co-detection of hsa-let-7a-5p (other) |
| hsa-miR-103a-1-5p | miR-103 | hsa-miR-103a-2-5p (other) | CRITICAL / 1.06 | co-detection of hsa-miR-103a-2-5p (other) |
| hsa-miR-103a-2-5p | miR-103 | hsa-miR-103a-1-5p (other) | CRITICAL / 0.24 | co-detection of hsa-miR-103a-1-5p (other) |
| hsa-miR-106a-5p | miR-1_AAAGUGC | hsa-miR-17-5p (other) | CRITICAL / 0.0 | co-detection of hsa-miR-17-5p (other) |
| hsa-miR-1290 | — | hsa-miR-1246 (other) | CRITICAL / 6.8 | co-detection of hsa-miR-1246 (other) |
| hsa-miR-17-5p | miR-1_AAAGUGC | hsa-miR-106a-5p (other) | MEDIUM / 2.04 | co-detection of hsa-miR-106a-5p (other) |
| hsa-miR-20a-5p | miR-1_AAAGUGC | hsa-miR-17-5p (other) | CRITICAL / 1.05 | co-detection of hsa-miR-17-5p (other) |
| hsa-miR-30b-5p | miR-30 | hsa-miR-30c-5p (other) | CRITICAL / 0.0 | co-detection of hsa-miR-30c-5p (other) |
| hsa-miR-30c-5p | miR-30 | hsa-miR-30b-5p (other) | CRITICAL / 0.0 | co-detection of hsa-miR-30b-5p (other) |
| hsa-miR-3620-5p | seed_UGGGCUG | hsa-miR-1587 (other) | CRITICAL / 3.68 | co-detection of hsa-miR-1587 (other) |
| hsa-miR-374b-5p | miR-374 | hsa-miR-374a-5p (other) | HIGH / 0.34 | co-detection of hsa-miR-374a-5p (other) |
| hsa-miR-374c-5p | miR-374c | hsa-miR-374b-5p (shifted_5p) | HIGH / 3.0 | co-detection of hsa-miR-374b-5p (shifted_5p) |
| hsa-miR-376b-5p | miR-376 | hsa-miR-376c-5p (other) | MEDIUM / 2.13 | co-detection of hsa-miR-376c-5p (other) |
| hsa-miR-376c-5p | miR-376 | hsa-miR-376b-5p (other) | MEDIUM / 2.31 | co-detection of hsa-miR-376b-5p (other) |
| hsa-miR-378a-3p | miR-378 | hsa-miR-378f (other) | CRITICAL / 4.57 | co-detection of hsa-miR-378f (other) |
| hsa-miR-378d | miR-378 | hsa-miR-378b (other) | CRITICAL / 3.5 | co-detection of hsa-miR-378b (other) |
| hsa-miR-378f | miR-378 | hsa-miR-378a-3p (other) | CRITICAL / 0.0 | co-detection of hsa-miR-378a-3p (other) |
| hsa-miR-518d-5p | miR-5 | hsa-miR-518e-5p (other) | CRITICAL / 1.0 | co-detection of hsa-miR-518e-5p (other) |
| hsa-miR-518e-5p | miR-5 | hsa-miR-518d-5p (other) | CRITICAL / 4.73 | co-detection of hsa-miR-518d-5p (other) |
| hsa-miR-519a-5p | miR-5 | hsa-miR-518d-5p (other) | CRITICAL / 4.73 | co-detection of hsa-miR-518d-5p (other) |
| hsa-miR-519b-5p | miR-5 | hsa-miR-518d-5p (other) | CRITICAL / 4.73 | co-detection of hsa-miR-518d-5p (other) |
| hsa-miR-519c-5p | miR-5 | hsa-miR-518d-5p (other) | CRITICAL / 4.73 | co-detection of hsa-miR-518d-5p (other) |
| hsa-miR-520b-3p | miR-302 | hsa-miR-520c-3p (shifted_3p) | HIGH / 0.0 | co-detection of hsa-miR-520c-3p (shifted_3p) |
| hsa-miR-520c-3p | miR-302 | hsa-miR-520b-3p (shifted_3p) | HIGH / 0.0 | co-detection of hsa-miR-520b-3p (shifted_3p) |
| hsa-miR-520c-5p | miR-5 | hsa-miR-518e-5p (other) | CRITICAL / 1.0 | co-detection of hsa-miR-518e-5p (other) |
| hsa-miR-520f-3p | seed_AGUGCUU | hsa-miR-520c-3p (shifted_5p) | HIGH / 0.0 | co-detection of hsa-miR-520c-3p (shifted_5p) |
| hsa-miR-520g-3p | miR-520 | hsa-miR-520h (shifted_3p) | HIGH / 3.0 | co-detection of hsa-miR-520h (shifted_3p) |
| hsa-miR-520h | miR-520 | hsa-miR-520g-3p (shifted_3p) | HIGH / 0.0 | co-detection of hsa-miR-520g-3p (shifted_3p) |
| hsa-miR-522-5p | miR-5 | hsa-miR-518d-5p (other) | CRITICAL / 4.73 | co-detection of hsa-miR-518d-5p (other) |
| hsa-miR-523-5p | miR-5 | hsa-miR-518d-5p (other) | CRITICAL / 4.73 | co-detection of hsa-miR-518d-5p (other) |
| hsa-miR-526a-5p | miR-5 | hsa-miR-518e-5p (other) | CRITICAL / 1.0 | co-detection of hsa-miR-518e-5p (other) |
| hsa-miR-548ad-5p | miR-548 | hsa-miR-548ay-5p (shifted_3p) | HIGH / 0.0 | co-detection of hsa-miR-548ay-5p (shifted_3p) |
| hsa-miR-548ae-3p | miR-548_AAAAACU | hsa-miR-548x-3p (other) | CRITICAL / 1.47 | co-detection of hsa-miR-548x-3p (other) |
| hsa-miR-548ae-5p | miR-548 | hsa-miR-548ay-5p (shifted_3p) | HIGH / 0.0 | co-detection of hsa-miR-548ay-5p (shifted_3p) |
| hsa-miR-548ah-3p | miR-548_AAAAACU | hsa-miR-548o-3p (other) | CRITICAL / 3.4 | co-detection of hsa-miR-548o-3p (other) |
| hsa-miR-548am-5p | miR-548 | hsa-miR-548au-5p (shifted_3p) | CRITICAL / 0.0 | co-detection of hsa-miR-548au-5p (shifted_3p) |
| hsa-miR-548aq-3p | miR-548_AAAAACU | hsa-miR-548h-3p (other) | CRITICAL / 2.74 | co-detection of hsa-miR-548h-3p (other) |
| hsa-miR-548ar-3p | miR-548_AAAACUG | hsa-miR-548ah-3p (other) | CRITICAL / 1.0 | co-detection of hsa-miR-548ah-3p (other) |
| hsa-miR-548ar-5p | miR-548 | hsa-miR-548am-5p (other) | CRITICAL / 4.74 | co-detection of hsa-miR-548am-5p (other) |
| hsa-miR-548as-5p | miR-548 | hsa-miR-548am-5p (other) | CRITICAL / 2.31 | co-detection of hsa-miR-548am-5p (other) |
| hsa-miR-548au-5p | miR-548 | hsa-miR-548am-5p (shifted_3p) | CRITICAL / 0.0 | co-detection of hsa-miR-548am-5p (shifted_3p) |
| hsa-miR-548av-3p | — | hsa-miR-548ah-3p (shifted_5p) | CRITICAL / 0.0 | co-detection of hsa-miR-548ah-3p (shifted_5p) |
| hsa-miR-548ay-5p | miR-548 | hsa-miR-548ab (other) | CRITICAL / 0.0 | co-detection of hsa-miR-548ab (other) |
| hsa-miR-548c-5p | miR-548 | hsa-miR-548au-5p (shifted_3p) | CRITICAL / 0.0 | co-detection of hsa-miR-548au-5p (shifted_3p) |
| hsa-miR-548d-5p | miR-548 | hsa-miR-548ay-5p (shifted_3p) | HIGH / 0.0 | co-detection of hsa-miR-548ay-5p (shifted_3p) |
| hsa-miR-548i | miR-548 | hsa-miR-548am-5p (other) | CRITICAL / 1.9 | co-detection of hsa-miR-548am-5p (other) |
| hsa-miR-548o-3p | seed_CAAAACU | hsa-miR-548ar-3p (other) | CRITICAL / 5.49 | co-detection of hsa-miR-548ar-3p (other) |
| hsa-miR-548o-5p | miR-548 | hsa-miR-548au-5p (shifted_3p) | CRITICAL / 0.0 | co-detection of hsa-miR-548au-5p (shifted_3p) |
| hsa-miR-548x-3p | miR-548_AAAAACU | hsa-miR-548ae-3p (other) | CRITICAL / 0.0 | co-detection of hsa-miR-548ae-3p (other) |
| hsa-miR-5692b | miR-5692 | hsa-miR-5692c (shifted_3p) | HIGH / 0.0 | co-detection of hsa-miR-5692c (shifted_3p) |
| hsa-miR-5692c | miR-5692 | hsa-miR-5692b (shifted_3p) | HIGH / 3.0 | co-detection of hsa-miR-5692b (shifted_3p) |
| hsa-miR-6511a-5p | seed_AGGCAGA | hsa-miR-6511b-5p (other) | CRITICAL / 8.3 | co-detection of hsa-miR-6511b-5p (other) |
| hsa-miR-99a-5p | miR-99 | hsa-miR-100-5p (other) | CRITICAL / 3.8 | co-detection of hsa-miR-100-5p (other) |

## 10. Giới hạn
- **F2 (kẹp GC)** đếm G/C trong 5 nt cuối, không xét vị trí. Ví dụ …GCAAT được 5 điểm, trong khi V4 loại vì 3 nt cuối không có G/C. QĐ 34 xử lý phần lớn các ca cùng S.
- **Mốc 45 °C của Tm vùng bám là mức sàn** rút từ giả thuyết chu kỳ 1 của khóa luận (let-7a 33,6 so với 46,2 °C), không phải đích tối ưu. Mốc 45 °C là trung vị Tm của các vùng 12–17 nt.
- **196/2472 thiết kế không thể đạt sàn 39 °C**: trong nhóm đặc hiệu cao nhất không có ứng viên nào có Tm vùng bám ≥ 39 °C. Bộ #1 của các thiết kế này nhận grade B.
- Các ngưỡng ghi "own threshold" (S2 mức 4, S3 mức 3/5, P2, F3, F4, mốc 25 °C của điểm chi tiết) **chưa được hiệu chỉnh bằng wet-lab**. Mô hình ΔCq assay cũng chưa được hiệu chỉnh.
- BLAST chỉ tìm trên miRBase 22.1 (miRNA trưởng thành, cùng loài + loài chủ nếu là virus). Chưa xét tRNA, Y RNA, snoRNA.
- Frontend chưa hiển thị hệ tiered. Ở 444 thiết kế, `total_score` (điểm chi tiết) của #1 thấp hơn #2, nên câu giải thích "#1 so với #2" hiện tại có thể sai. Phần này chờ SPEC UI (QĐ 31).
