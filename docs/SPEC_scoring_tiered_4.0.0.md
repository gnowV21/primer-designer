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

**Bổ sung sau khi duyệt Giai đoạn 1 (2026-11-17; số liệu §9, `benchmark/tiered_scoring_dryrun.json`):**

17. **Tầng PCR chỉ còn P2** (tối đa 5). P1 (ΔTm F–R) chỉ báo cáo, không chấm, và bỏ khỏi điểm chi tiết (trọng số còn lại chuẩn hóa theo tổng 0,85). Lý do: mồi ngược cố định (Tm 62,93 °C ở điều kiện mặc định), nên P1 chỉ là hàm của Tm mồi xuôi và kéo nó về 62,9 °C trong khi P2 kéo về Ta (r = −0,95 trên 217.780 ứng viên). P2 giữ bậc ≤ 1 / 2 / 3 / 5 °C; **không dùng bậc hẹp hơn 1 °C** vì Tm nearest-neighbor có sai số ~±1–2 °C. P2 không hằng số ở các thiết kế fallback của V4 (khác nhau ở 23/115 pool), nên vẫn có tác dụng bảo vệ ở đó.
18. **S2 giữ ngưỡng.** Mức 4 (7 – < 10 Cq) là mức cao nhất đạt được trên thực tế, nghĩa là "mồi RT bắt được off-target nhưng mồi xuôi không mồi được": ΔCq_FWD chạm trần mô hình 8,3 (DECISIONS D-4). Mức 5 chỉ đạt khi không có off-target nào mà RT bắt được. **Không đặt mốc mức 5 ở 8,3**: trần của mô hình không phải bằng chứng đặc hiệu tối đa. S2 vẫn tham gia xếp hạng vì nó khác nhau giữa các ứng viên ở 5,6 % thiết kế (REV-23) và là căn cứ loại ứng viên (QĐ 4).
19. **S2 tính cả `shifted_5p` và `shifted_3p`**, chỉ bỏ `same_sequence` (đúng chữ của §3.1). Hai trình tự trùng nhau thì không mồi nào phân biệt được. Còn trình tự lệch đầu là nguy cơ phản ứng chéo có thật: lệch 3′ chạm vùng overhang RT, lệch 5′ chạm mồi xuôi. **Khác V4**: `family_discrimination` của V4 bỏ cả ba loại. Khóa luận phải ghi rõ khác biệt này khi so V4 với tiered. Tác động: 39 thiết kế `specificity_fallback` (28 nếu theo cách của V4), 97 thiết kế có ứng viên bị loại (92). Các thiết kế có off-target lệch đầu nên được ưu tiên kiểm tra phản ứng chéo ở wet-lab.
20. **S3 lấy khung bền nhất trong ±2 nt** cho Tm_off (trường hợp xấu nhất). S3 là phép phạt off-target: mồi xuôi gắn trên cDNA của một off-target lệch đầu theo khung dịch vẫn kéo dài được. Tm_on vẫn tính ở khung không dịch (r = 0), tức là gắn đúng đích. Phương án chỉ dùng r = 0 được đo nhưng không dùng (`alternative_s3_register_0_only_not_used`).
21. **F5c (Tm dimer đầu 3′) trên thực tế là veto, không phải tiêu chí chấm theo bậc**: 99,2 % ứng viên ở mức 5. Cả 32 ứng viên ở mức 1 đều cũng có F5a = 1 và F5b = 1 (đầu 3′ tự bổ sung như CTGCAG, GTCGAC). Không thiết kế nào bị veto toàn bộ chỉ vì F5c. Giữ lại vì Primer3 có quy tắc này. F5a (hairpin) cũng gần như nhị phân: 89 % ở mức 5, 11 % ở mức 1, các mức giữa gần như trống.
22. **QĐ 15, thứ tự cắt pool.** Bỏ cả luật "≥ 5 G/C trong 5 nt cuối" khỏi bộ lọc sơ bộ, vì F2 đã chấm trường hợp này ở mức 1. Khi không còn lọc GC, pool 20 đuôi/độ dài được xếp **theo mức F1 (GC % toàn mồi) trước**, rồi mới theo |Tm − Ta|. Không cần xếp theo F2 trước: 5 nt cuối nằm trong vùng đặc hiệu nên F2 giống nhau với mọi đuôi cùng độ dài. Trước khi sửa, 95/2253 mồi #1 của V4 không có trong pool tiered (các đuôi GC lệch có Tm gần hơn đã chiếm chỗ); sau khi sửa: 0/2253. Có test hồi quy (`test_forward_gc_prefilter_flag.py`).
23. **Nguyên tắc chỉnh ngưỡng** (áp cho mọi lần sửa sau): không chỉnh ngưỡng chỉ để phân bố "trải đều"; mỗi ngưỡng cần lý do sinh học hoặc lý do về độ chính xác của mô hình, nếu không có thì ghi "own threshold". Vai trò của từng thành phần do **độ biến thiên trong cùng thiết kế** quyết định: bằng 0 thì chỉ báo cáo; chỉ tách mức 1 thì là bộ lọc/veto; còn lại thì xếp hạng. Bảng chẩn đoán này (§9) là luận cứ cho cấu trúc hàm điểm trong khóa luận.

**Bổ sung khi duyệt ngưỡng, trước Giai đoạn 2 (2026-11-17):** bộ ngưỡng §3 và QĐ 17–23 đã được duyệt.

24. **BLAST là việc đầu tiên của Giai đoạn 2.** Lý do: S1 là thành phần đặc hiệu duy nhất khác nhau giữa các ứng viên ở số đông thiết kế (52,8 % trên mẫu; S2 5,6 %, S3 14,9 %).
    - a) Profile trước: tách thời gian `blastn`, `blastdbcmd`, NW, thal cho 1 thiết kế.
    - b) Gộp truy vấn: 1 lần `blastn` multi-FASTA + 1 lần `blastdbcmd` cho mọi entry cần lấy. Test: S1 và từng hit trùng với cách gọi từng mồi trên toàn bộ 31.049 lần gọi của mẫu 309 miRNA.
    - c) Nghiệm thu: p50 ≤ 15 s, chưa cache, trên 20 miRNA hsa ngẫu nhiên (seed cố định), đo trên máy dự án. Báo cả p90.
    - d) Nếu chưa đạt: cắt tỉa chính xác — chỉ BLAST ứng viên mà cận trên (S1 = 5) còn có thể vào top 3 sau bước chọn đa dạng. Test: top 3 trùng với BLAST toàn bộ trên mẫu 309. Không đổi CSDL BLAST, không giảm độ nhạy (`word_size`, `evalue`). Nếu vẫn chưa đạt: dừng và hỏi.
    - e) Thiếu BLAST: cảnh báo `blast_unavailable` ghi rõ "specificity ranking reduced to S2 + S3". Các script số liệu (validation, benchmark, dry run) phải fail nếu BLAST không có.
25. **`v4_rule_violations`** trên mỗi bộ mồi: danh sách luật V4 mà bộ đó vi phạm (lọc GC %, kẹp GC, 3 luật lọc cứng cấu trúc); mảng rỗng nếu không vi phạm. Có trong API, `openapi.yaml` và export. Mục đích: đánh dấu rõ các bộ của 219 miRNA mà V4 không thiết kế được, và các bộ bị veto.
26. **Báo cáo cuối Giai đoạn 2 thêm 3 chỉ số:**
    - (1) tương quan F3–F4 trong cùng thiết kế;
    - (2) phân bố độ dài vùng đặc hiệu và Tm vùng bám của #1 (V4 3.8.2 so với tiered);
    - (3) trong 1659 ca đổi #1, Tm vùng bám của #1 mới gần hay xa 45 °C hơn.

    Nếu tương quan > 0,7: đề xuất phương án gộp F3/F4, không tự sửa.
27. **Hòa hoàn toàn.** Khi mọi chỉ số đều bằng nhau (các biến thể đuôi), thứ tự theo trình tự là tùy ý nhưng tất định (1195 thiết kế ở mức #1 so với #2); bước chọn đa dạng vẫn chọn các đầu 3′ khác nhau (ghi ở §3.5).

**Sau khi duyệt Giai đoạn 2 (2026-11-18; số liệu §10):**

28. **Duyệt 4/5 chi tiết cài đặt ở §10:** (1) chỉ BLAST các ứng viên S2 không loại (BLAST thêm phần còn lại khi fallback); (3) cờ `report_only` / `eliminated`; (4) cách chọn overhang để gợi ý; (5) `v4_rule_violations` ở cả hai hệ. Riêng (2) (`grade` theo điểm chi tiết) được thay bằng QĐ 30.
29. **Gộp F3/F4 theo phương án (d), không theo (b) — chờ duyệt lại sau số đo của Giai đoạn 2b.**
    - Lý do: `TM_BINDING_TARGET = 45 °C` là trung vị Tm của các vùng 12–17 nt (`SPEC_algorithm.md`, sửa ở v2.8.1), không phải mức tối ưu sinh học. Ở chu kỳ 1, Tm vùng bám càng cao thì gắn càng tốt: cân bằng khối lượng 3.8.1 cho 0,08 % ở 12 nt, 7,8 % ở 17 nt, tại 60 °C. Khả năng phân biệt mismatch đã được đo trực tiếp ở tầng S. Giả thuyết ~45 °C của khóa luận là **mức sàn**, không phải đích hai phía.
    - Bỏ F3 khỏi tầng Linh hoạt (tối đa còn 20).
    - F4 thành sàn một phía: Tm vùng bám ≥ 45 → 5; 43–< 45 → 4; 41–< 43 → 3; 39–< 41 → 2; < 39 → 1. Ghi "own threshold; floor = thesis cycle-1 hypothesis (let-7a 33,6 vs 46,2 °C)".
    - Điểm chi tiết: `tm_binding_accuracy` cũng một phía (100 khi ≥ 45 °C, giảm tuyến tính về 0 tại 35 °C). Bỏ `primer_size` (cùng lý do bỏ F3); chuẩn hóa lại trọng số.
    - L vẫn có trong API, chỉ để báo cáo.
    - Cài sau cờ `TIERED_F4_FLOOR` (mặc định tắt cho tới khi duyệt).
30. **Ở hệ tiered, `grade` tính theo tầng, không theo điểm chi tiết.**
    - A: không `specificity_fallback`, S1 ≥ 4, S2 ≥ 3, S3 ≥ 4, không `structure_veto`.
    - B: qua bước loại nhưng có ít nhất một điểm yếu (S1 = 2–3, S2 = 2, S3 ≤ 3, hoặc `structure_veto`).
    - C: `specificity_fallback`.
    - Khi `blast_unavailable`: không cho A; cao nhất là B, ghi lý do.
    - Có test cho từng mức. `total_score` giữ = điểm chi tiết; cách hiển thị để SPEC UI.
    - Cài sau cờ `TIERED_GRADE_BY_TIERS`.
31. **Giai đoạn 3 mở PR vào `master` nhưng KHÔNG merge cho tới khi xong SPEC UI.** Lý do: frontend (ScoreGauge, RerunBar, History, ThermoTable, export CSV, `rankReason`) hiển thị `total_score` / `grade`, nên ở 444 thiết kế bộ #1 trông kém hơn #2. Ghi điều này trong mô tả PR.
32. **Chờ số liệu:** cách xử lý các bộ #1 vi phạm luật V4 trong khi V4 có mồi tuân thủ. Chưa đổi luật; số đo ở Giai đoạn 2b mục 4.

**Sau khi duyệt Giai đoạn 2b (2026-11-18; số liệu §11):**

33. **Duyệt QĐ 29, kèm chỉnh cho các ca dưới sàn.** `tm_binding_accuracy` trong điểm chi tiết: tuyến tính một phía, 0 điểm tại 25 °C, 100 điểm tại ≥ 45 °C (25 °C ≈ Tm vùng bám thấp nhất quan sát được; own threshold). Giữ trọng số 0,10 sau chuẩn hóa.
    - Nghiệm thu, trên bộ #1 của 2472 thiết kế: số thiết kế có F4 = 1 ≤ 179, và % có Tm vùng bám < 45 °C ≤ 39,0.
    - Nếu chưa đạt: thử trọng số 0,15 (chuẩn hóa lại tổng) rồi đo lại. Vẫn chưa đạt → DỪNG, báo cả hai phương án.
34. **Giải quyết QĐ 32.** Khóa xếp hạng tiered thành `(−S_total, structure_veto, has_v4_violation, −P_total, −F_total, −detailed_score, |Tm_full − Ta|, sequence)`, với `has_v4_violation = len(v4_rule_violations) > 0`.
    - Luật này chỉ phân định khi tổng đặc hiệu bằng nhau. Ở Giai đoạn 2b nó không làm giảm S1 hay S3 của #1 ở ca nào.
    - F2 giữ nguyên (xem giới hạn).
    - Nghiệm thu: so với cấu hình không có QĐ 34, ở mọi thiết kế S1, S2, S3 của #1 không đổi (từng thành phần, không chỉ tổng).
    - Cờ: `TIERED_V4_COMPLIANT_FIRST`.
35. **Mặc định của hệ tiered: bật QĐ 29 (+33), QĐ 30, QĐ 34.** Giữ các cờ (`TIERED_F4_FLOOR`, `TIERED_GRADE_BY_TIERS`, `TIERED_V4_COMPLIANT_FIRST`) để script so sánh vẫn tắt được. Cập nhật test và `openapi.yaml`.

**Giới hạn đã biết (ghi vào khóa luận):**
- F2 đếm G/C trong 5 nt cuối, không xét vị trí: …GCAAT được 5 điểm, trong khi V4 loại vì 3 nt cuối không có G/C. QĐ 34 xử lý phần lớn các ca cùng S.
- Mốc 45 °C của Tm vùng bám là mức sàn rút từ giả thuyết chu kỳ 1 của khóa luận, không phải đích tối ưu.
- Các ngưỡng ghi "own threshold" chưa được hiệu chỉnh bằng wet-lab.

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

### 3.2 Tầng 2 — PCR (tối đa 5 từ QĐ 17; trước đó 10)
**P1 · ΔTm F–R** = |Tm(mồi xuôi đầy đủ) − Tm(mồi ngược universal)|, cùng điều kiện. **Chỉ báo cáo (QĐ 17).**
**P2 · Tm so với Ta** = |Tm(mồi xuôi đầy đủ) − Ta người dùng| (cùng tham chiếu với `tm_accuracy` hiện tại).

| Điểm | P1 | P2 |
|---|---|---|
| 5 | ≤ 1 °C | ≤ 1 °C |
| 4 | ≤ 2 (`TM_PAIR_DIFF_MAX` [PAST24]) | ≤ 2 |
| 3 | ≤ 3 | ≤ 3 |
| 2 | ≤ 5 | ≤ 5 |
| 1 | > 5 | > 5 |

Cần đo: mồi ngược là cố định, nên nếu Tm_rev ≈ Ta thì P1 ≈ P2 (đếm đôi). Báo Tm_rev và tương quan P1–P2.
**Đã đo:** Tm_rev = 62,93 °C; r(|F − R|, |F − Ta|) = −0,95 → P1 bỏ khỏi xếp hạng (QĐ 17).

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
| ~~ΔTm F–R~~ | ~~0,15~~ → bỏ (QĐ 17) |
| Tm so với Ta (`tm_accuracy`) | 0,15 |
| Tm vùng bám (`tm_binding_accuracy`) | 0,08 |
| GC % | 0,05 |
| Kẹp GC | 0,05 |
| Độ dài vùng đặc hiệu (`primer_size`) | 0,05 |
| Cấu trúc (trung bình 3 sub-score) | 0,05 |
| Amplicon | 0,02 |

Tổng 1,00 ban đầu; sau QĐ 17 còn 0,85 và được chuẩn hóa theo tổng đó (trước chuẩn hóa: đặc hiệu 0,40, Tm 0,23, cấu trúc 0,05).
Chỉ báo cáo, không chấm (gom vào `assay_qc`): `mfe_stemloop`, `end_stability`, bound fraction (cả 2 vòng), `family_discrimination` của V4, `tm_pair_match` của V4 (đã thay bằng P1).

### 3.5 Khóa xếp hạng
1. Loại ứng viên theo QĐ 4.
2. `key = (−S_total, structure_veto, −P_total, −F_total, −detailed_score, |Tm_full − Ta|, sequence)`, với P_total = P2 (QĐ 17).
3. Chọn top 3 bằng `select_diverse_top(ranked, CANDIDATES_TOP_N)`, giữ nguyên logic đa dạng.
4. Hệ mới bỏ vòng fixpoint `family_discrimination` trong `design_pipeline.py` (không cần nữa vì S2 đã tính theo từng ứng viên).
5. (QĐ 27) Khi mọi phần tử của khóa trừ `sequence` bằng nhau (thường là các biến thể đuôi 5′ có cùng mọi chỉ số), thứ tự theo trình tự là **tùy ý nhưng tất định**. Ở Giai đoạn 1 điều này quyết định #1 so với #2 ở 1195/2253 thiết kế. Không ảnh hưởng tính đa dạng: `select_diverse_top` vẫn chọn các bộ có đầu 3′ khác nhau.

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

### Giai đoạn 2b — đo QĐ 29/30, rồi DỪNG (2026-11-18)
Cài QĐ 29 và QĐ 30 sau cờ, đo trên hệ có BLAST đầy đủ (2472 thiết kế, dùng cache BLAST của §10), chưa chạy lại số liệu Giai đoạn 3:
1. QĐ 29 so với tiered hiện tại và V4 3.8.2: số #1 đổi; phân bố L và Tm vùng bám của #1; % #1 có Tm vùng bám < 45 °C; phân bố mức F4 của #1; % thiết kế mà F4 khác nhau giữa các ứng viên; bảng "#1 so với #2 được phân định bởi tầng nào".
2. QĐ 30: phân bố A/B/C của #1; số ca grade cũ khác grade mới (đặc biệt cũ cao nhất mà nay là C).
3. S1 của #1 V4 3.8.2 (cùng classifier, cùng mồi RT): phân bố mức 1–5; số thiết kế mà #1 V4 có S1 ≤ 2 và #1 tiered có S1 cao hơn (số chính cho chương Kết quả).
4. QĐ 32: các thiết kế mà #1 tiered vi phạm luật V4 còn #1 V4 thì không (trừ 219 ca V4 không thiết kế được), tách theo ΔS_total (tiered − V4): ΔS > 0 (số ca, luật); ΔS = 0 (tầng quyết định, luật; riêng `hard_dimer_full_dg`: phân bố ΔG). Mô phỏng, không áp dụng: "cùng S_total thì mồi không vi phạm luật V4 xếp trước (sau veto)" — số #1 đổi, S1/S3 của #1 đổi thế nào.
5. Danh sách các thiết kế `specificity_fallback`: miRNA, họ seed, off-target gây loại (tên, loại `shifted_5p` / `shifted_3p` / `other`, ΔCq hoặc mức BLAST) → `benchmark/tiered_fallback_list.csv`.

Mọi test pass; hồi quy V4 vẫn trùng 3.8.2. ⛔ DỪNG: chờ duyệt QĐ 29 (theo số đo) và QĐ 32.

### Giai đoạn 2c — đo cấu hình cuối (QĐ 33–35), dùng lại cache BLAST
- A. Trước khi chạy: working tree sạch, test pass, hồi quy V4 trùng 3.8.2. Ghi provenance vào đầu log (git SHA, `ALGORITHM_VERSION`, giá trị mọi cờ, phiên bản `blastn`, metadata + sha256 của BLAST DB, số dòng `blast_cache.sqlite`, giờ bắt đầu). Sao lưu `blast_cache.sqlite` → `blast_cache.<yyyymmdd-hhmm>.bak` (gitignore; không xóa, không ghi đè, không `BLAST_CACHE_DISABLED`). Chỉ một tiến trình ghi cache. Chạy thử 20 miRNA của phép đo thời gian: cache hit ≥ 90 % và S1 của mọi ứng viên trùng Giai đoạn 2. Không đạt → DỪNG, báo thành phần khóa cache đã đổi.
- B. Chạy đủ 2472 thiết kế, thứ tự theo tên, JSONL theo miRNA, có `--resume`, log ở `benchmark/logs/`. Mỗi 100 miRNA một dòng tiến độ. DỪNG nếu sau 200 miRNA cache hit < 90 % hoặc ước tính tổng > 2 giờ. Lỗi BLAST: chạy lại 1 lần cuối lượt; còn > 1 % (24) → DỪNG.
- C. Kiểm tra:
  - tắt QĐ 29/33/34 thì tái tạo Giai đoạn 2 (#1 trùng 2472/2472, fallback 54, có ứng viên bị loại 383);
  - nghiệm thu QĐ 33, QĐ 34;
  - tất định trên 20 miRNA;
  - JSONL không trùng, số dòng = 2472 − số lỗi.
- D. Báo cáo 4 cột (V4 3.8.2 | tiered Giai đoạn 2 | QĐ 29 | cấu hình cuối) → `benchmark/tiered_stage2c_report.json`, SPEC §12, HANDOFF. Đạt hết thì sang Giai đoạn 3 không cần chờ; có mục không đạt → DỪNG.

### Giai đoạn 3 — Số liệu, tài liệu, PR
- (QĐ 31) Mở PR vào `master`, **không merge** cho tới khi xong SPEC UI; ghi lý do trong mô tả PR. `docs/SCORING_TIERED_COMPARISON.md` thêm: S1 của #1 V4 so với tiered (Giai đoạn 2b mục 3) và danh sách fallback kèm gợi ý ưu tiên kiểm phản ứng chéo ở wet-lab (mục 5).
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

## 9. Kết quả Giai đoạn 1 (dry run, 2026-11-17, sau QĐ 17–22)
Nguồn: `benchmark/tiered_scoring_dryrun.json` (`backend/scripts/tiered_scoring_dryrun.py`). 2656 miRNA hsa, miRBase 22.1, mặc định backend. S2/S3/P/F tính trên mọi ứng viên của 2472 thiết kế có ứng viên. S1 (BLAST, classifier v7) chỉ chạy trên mẫu 309 miRNA (300 ngẫu nhiên seed 2026 + 7 ca của mục 8 + ứng viên wet-lab), 31.049 lần gọi, vì một lần BLAST ≈ 1,1 s.

**Bảng chẩn đoán: độ biến thiên trong cùng thiết kế** (% thiết kế mà tiêu chí khác nhau giữa các ứng viên; SD trung bình của mức trong một thiết kế):

| Tiêu chí | Khác nhau | SD | Vai trò |
|---|---|---|---|
| S1 BLAST (mẫu) | 52,8 % | 0,21 | xếp hạng + loại CRITICAL |
| S2 ΔCq | 5,6 % | 0,04 | xếp hạng (ít) + loại CO-AMPLIFIED |
| S3 biên Tm | 14,9 % | 0,09 | xếp hạng |
| P1 ΔTm F–R | 78,2 % | 0,28 | **chỉ báo cáo** (đối nghịch P2) |
| P2 Tm − Ta | 12,1 % | 0,05 | xếp hạng (ít) |
| F1 GC % | 21,2 % | 0,12 | xếp hạng |
| F2 kẹp GC | 85,1 % | 0,71 | xếp hạng |
| F3 độ dài | 96,6 % | 1,20 | xếp hạng |
| F4 Tm vùng bám | 92,6 % | 1,14 | xếp hạng |
| F5 cấu trúc | 95,0 % | 0,95 | xếp hạng + veto |
| F5a hairpin | 92,6 % | 1,02 | gần như bộ lọc (99 % số thiết kế có biến thiên chỉ tách mức 1) |
| F5c dimer đầu 3′ | 19,0 % | 0,04 | veto (QĐ 21) |

**Số liệu chính** (không BLAST, 2472 thiết kế; trong ngoặc: mẫu có BLAST, 309 thiết kế):
- Có ứng viên bị loại: 97 (54); `specificity_fallback`: 39 (7); trả < 3 bộ: 2 (0); #1 bị veto mềm: 118 (13).
- #1 khác #1 của V4 3.8.2: 1659/2253 (73,6 %); trong đó ΔS = 0 ở 1487 ca, ΔL > 0 ở 781 ca, ΔTm trung vị 0. Mẫu có BLAST: 204/277.
- #1 so với #2 trong bảng xếp hạng được phân định bởi: điểm chi tiết 1124, trình tự 1195 (đa số là biến thể đuôi có cùng mọi chỉ số), F 138, |Tm − Ta| 13, veto 1.
- Mức chiếm > 90 %: P2 = 5 (97,3 %), F5c = 5 (99,2 %). S2 = 4 chiếm 89,4 % (QĐ 18).
- 403 miRNA V4 không thiết kế được: 219 có ứng viên ở hệ tiered (#1: F1 mức 5/4/3/2 = 34/70/69/46; F2 = 1 ở 31 ca; veto 43); 184 vẫn không có (cửa sổ Tm, độ dài, homopolymer).
- 115 thiết kế V4 `hard_filter_fallback`: #1 của hệ tiered bị veto ở 72 ca (F5 = 1 ở 72, = 2 ở 41).
- **Thời gian:** BLAST trung vị 1,11 s/ứng viên (2 subprocess: `blastn`, `blastdbcmd`); pool trung vị 100 ứng viên → ước tính ~113 s/thiết kế, vượt xa 15 s (QĐ 12). Giai đoạn 2 phải gộp truy vấn BLAST (§5).
- Nhánh V4 sinh đúng tập ứng viên như 3.8.2 ở 2656/2656 miRNA.

## 10. Kết quả Giai đoạn 2 (cài đặt, 2026-11-18)
Code: `backend/algorithm/tiered_pipeline.py` (tích hợp), `tiered_scoring.py` (hàm thuần), `specificity_check/blast_offtarget.py` (BLAST gộp), `design_pipeline.py` (rẽ nhánh `tiered` / `v4`). Mặc định `scoringSystem = "tiered"`; chọn theo request (`scoringSystem`, trả 400 nếu sai) hoặc biến môi trường `SCORING_SYSTEM`. `ALGORITHM_VERSION = "4.0.0"`.

**QĐ 24 — BLAST**
- a) Profile hsa-miR-21-5p, 100 ứng viên, gọi từng mồi: 212,7 s, gồm `blastn` 111,1 s (100 lần), `blastdbcmd` 97,0 s (100 lần), thal 1,95 s, NW 1,58 s. Gần như toàn bộ thời gian là khởi động tiến trình và nạp CSDL.
- b) Gộp: một `blastn` multi-FASTA và một `blastdbcmd` cho mỗi thiết kế (`check_offtarget_batch`). Truy vấn được chia cho `BLAST_BATCH_PROCESSES = 8` tiến trình `blastn` song song. Chỉ đổi hiệu năng: output giống từng dòng với 1 tiến trình; 1 → 8,5 s, 8 → 2,5 s. Phần phân loại hit dùng chung một hàm (`_classify_hits`) với cách gọi từng mồi. **Đối chiếu: 0/31.049 lần gọi khác nhau** (so toàn bộ JSON, 7.585 hit không-SAFE, gồm S1); S1 cũng khớp 31.049/31.049 kết quả đã lưu ở Giai đoạn 1 (`benchmark/blast_batch_equivalence.json`, `scripts/blast_batch_equivalence.py`). Không đổi CSDL, `word_size` hay `evalue`.
- c) Thời gian, không cache, 20 miRNA hsa có thiết kế (thứ tự `random.Random(2026)`; bỏ hsa-miR-6845-5p vì không có ứng viên), chạy trong tiến trình, tuần tự: **p50 9,78 s, p90 11,89 s**, max 13,38 s. Riêng BLAST: p50 8,07 s, p90 10,04 s (`benchmark/tiered_design_timing.json`). Đạt ≤ 15 s, nên không cần cắt tỉa (d).
- e) Không có BLAST (thiếu binary/CSDL, hoặc lỗi khi chạy): request vẫn trả kết quả; S1 = null cho **mọi** ứng viên, cảnh báo `blast_unavailable` ghi "specificity ranking reduced to S2 + S3". S1 hoặc có cho mọi ứng viên được xếp hạng, hoặc không có cho ứng viên nào, kể cả khi lần BLAST bổ sung của fallback lỗi. Các script số liệu dừng với lỗi khi không có BLAST: `validate_primers.py`, `run_benchmark.py`, `export_benchmark_primers.py`, `tiered_scoring_dryrun.py`, `crossreactivity/design_all.py`, `blast_batch_equivalence.py`, `tiered_design_timing.py`, `tiered_stage2_report.py`.
- Cache: dùng bảng `blast_cache.sqlite`, khóa gồm mồi, mồi ngược, ngày dựng CSDL, tên miRNA, cùng ngữ cảnh thiết kế (classifier, trình tự đích, loài, mồi RT, điều kiện muối). Đặt `BLAST_CACHE_DISABLED=1` để tắt. Lỗi SQLite chỉ làm bỏ qua cache.

**Chi tiết cài đặt mà SPEC chưa quy định** (cần duyệt):
1. BLAST các ứng viên không bị S2 loại (§5). Nếu mọi ứng viên còn lại đều CRITICAL (tức fallback), BLAST thêm các ứng viên đã bị S2 loại, để tổng S so sánh được.
2. `total_score` = điểm chi tiết; `grade` dùng cùng mốc của V4 (80/65/50) trên điểm chi tiết. `scores` / `weights` = các phần của điểm chi tiết (trọng số đã chuẩn hóa).
3. `ranking.pcr.tm_pair` có `report_only: true` (QĐ 17); `ranking.eliminated = true` chỉ xuất hiện trong thiết kế fallback.
4. `overhang_suggestion` xét các độ dài 5–7 nt khác độ dài đang dùng. Chọn mức S2 cao nhất, rồi ΔCq lớn nhất. Bỏ qua độ dài mà vùng đặc hiệu của #1 không còn vừa (L > độ dài miRNA − overhang).
5. `v4_rule_violations` có ở cả hai hệ, là danh sách mã luật (`gc_out_of_range`, `gc_clamp_fail`, `gc_end_window_fail`, `hard_dimer_full_dg`, `hard_dimer_3prime_critical`, `hard_hairpin_tm`).

**Kiểm chứng**
- Test backend: 869 pass, 3 skip (gồm `test_tiered_scoring.py`, `test_blast_batch.py`); `crossreactivity/tests` 29 pass.
- Hồi quy V4: `validate_primers.py --scoring-system v4` cho `results.json` giống bản 3.8.2 đã commit (bỏ qua `run_date`; 2439/2439) và `results.csv` giống từng byte.
- Pipeline khớp dry run: top 3 của pipeline thật (BLAST thật, không cache) trùng top 3 offline ở 20/20 miRNA của phép đo thời gian; hsa-miR-21-5p trùng bảng ca của Giai đoạn 1.

**Hệ đã cài, BLAST cho cả 2472 thiết kế** (`benchmark/tiered_stage2_report.json`, `scripts/tiered_stage2_report.py`; không BLAST → có BLAST):
- Có ứng viên bị loại 97 → **383**; `specificity_fallback` 39 → **54**; trả < 3 bộ 2 → 2; #1 bị veto mềm 118 → 120.
- #1 khác V4 3.8.2: 1659 → **1670**/2253.
- S1 của #1 (mức 5/4/3/2/1): 2107 / 68 / 23 / 17 / 38. Cả 38 ca mức 1 đều là thiết kế fallback.
- #1 có `total_score` thấp hơn #2 ở 444 thiết kế; `total_score` không giảm dần theo hạng ở 777 thiết kế. Lý do: điểm chi tiết chỉ là bước phân định cuối, xem mục giới hạn bên dưới.

**QĐ 25 — `v4_rule_violations` của #1 (có BLAST):** 555/2472 bộ #1 vi phạm ít nhất một luật V4: `gc_out_of_range` 225, `gc_clamp_fail` 201, `hard_dimer_full_dg` 165, `hard_hairpin_tm` 46, `gc_end_window_fail` 17. Trong 219 miRNA V4 không thiết kế được, mọi bộ #1 đều vi phạm ít nhất một luật: `gc_out_of_range` 185, `hard_dimer_full_dg` 44, `gc_clamp_fail` 34, `hard_hairpin_tm` 23, `gc_end_window_fail` 11.

**QĐ 26**
- (1) Tương quan F3–F4 trong cùng thiết kế: r gộp sau khi trừ trung bình từng thiết kế = 0,21. Nhưng |r| tính theo từng thiết kế có trung vị 0,88, và **1664/2290 thiết kế có |r| > 0,7**. Nguyên nhân: vùng đặc hiệu độ dài L luôn là `dna[:L]`, nên F4 là hàm của L ở 2656/2656 thiết kế, đúng như F3. r gộp thấp chỉ vì dấu đổi giữa các thiết kế (F4 đỉnh tại L có Tm ≈ 45 °C). → Đề xuất phương án gộp, **chưa sửa** (bảng dưới).
- (2) #1, V4 3.8.2 so với tiered có BLAST:
  - L trung bình 14,05 → 14,59; phân bố L 12…17 từ 433/421/478/499/369/53 thành 244/296/423/562/639/89.
  - Tm vùng bám: trung vị 44,4 → 45,2 °C, p95 47,8 → 52,2 °C.
  - |Tm vùng bám − 45|: trung bình 2,53 → 3,17, trung vị 1,6 → 2,1.
- (3) Trong 1670 ca đổi #1 (có BLAST): #1 mới **gần 45 °C hơn ở 294 ca, xa hơn ở 621 ca, bằng ở 755 ca**. Không BLAST, 1659 ca: 299 / 609 / 751.

Phương án F3/F4, đo trên hệ có BLAST, **chưa áp dụng**:

| Phương án | #1 đổi so với tiered hiện tại | L trung bình | \|Tm vùng bám − 45\| TB / trung vị |
|---|---|---|---|
| hiện tại F3 + F4 | — | 14,59 | 3,17 / 2,1 |
| a) một tiêu chí = min(F3, F4) | 461 | 14,51 | 3,51 / 2,7 |
| b) bỏ F3, giữ F4 (độ dài còn trong điểm chi tiết) | 639 | 14,11 | 2,75 / 1,6 |
| c) bỏ F4, giữ F3 | 719 | 14,98 | 4,51 / 3,9 |
| V4 3.8.2 | — | 14,05 | 2,53 / 1,6 |

**Giới hạn còn mở (cho SPEC UI, ngoài phạm vi QĐ 13):** frontend `rankReason` giải thích "#1 vs #2" bằng hiệu `total_score`. Ở hệ tiered, `total_score` chỉ là bước phân định cuối, nên ở 444/2472 thiết kế hiệu này âm, và câu giải thích sai ("practically tied" hoặc "−x points"). SPEC UI cần giải thích theo tầng quyết định (S → veto → P → F → chi tiết).

## 11. Kết quả Giai đoạn 2b (QĐ 29/30 sau cờ, 2026-11-18)
Nguồn: `benchmark/tiered_stage2b_report.json`, `benchmark/tiered_fallback_list.csv` (`backend/scripts/tiered_stage2b_report.py`). Dữ liệu là 2472 thiết kế hsa có BLAST đầy đủ (cache của §10); bảng so với V4 dùng 2253 thiết kế mà V4 có mồi. Cờ `TIERED_F4_FLOOR` và `TIERED_GRADE_BY_TIERS` đang tắt; tiered ở đây là bản 4.0.0 của Giai đoạn 2.

**1. QĐ 29 (F4 sàn, bỏ F3)**

| #1 | V4 3.8.2 | tiered | QĐ 29 |
|---|---|---|---|
| #1 đổi so với V4 | — | 1670 | 1764 |
| #1 đổi so với tiered | — | — | 560 |
| L 12/13/14/15/16/17 | 433/421/478/499/369/53 | 244/296/423/562/639/89 | 256/249/382/586/642/138 |
| L trung bình | 14,05 | 14,59 | 14,68 |
| Tm vùng bám, trung vị (p05–p95) | 44,4 (36,8–47,8) | 45,2 (37,4–52,2) | 45,9 (34,9–53,5) |
| % #1 có Tm vùng bám < 45 °C | 59,5 | 45,5 | **38,4** |
| Mức F4 thang sàn 1/2/3/4/5 | 201/178/311/651/912 | 179/148/233/465/1228 | **211**/134/207/314/1387 |
| % thiết kế F4 khác nhau giữa ứng viên | — | 92,6 | 80,8 |
| #1 so với #2 phân định bởi: trình tự / chi tiết / F / Tm / S / veto (2472) | — | 1179/1134/142/12/3/1 | 1226/1098/134/9/3/1 |

- QĐ 29 giảm số #1 dưới 45 °C (45,5 → 38,4 %).
- Nhưng số #1 dưới 39 °C lại tăng (mức 1: 179 → 211). Ở các thiết kế mà mọi vùng đều dưới 39 °C, F4 bằng 1 cho tất cả. Khi đó F3 không còn kéo về vùng dài hơn, và điểm chi tiết của Tm vùng bám (trọng số 0,10 sau chuẩn hóa) không đủ để quyết định.

**2. QĐ 30 (grade theo tầng)** — #1 (tiered và QĐ 29 cho cùng kết quả): A 2190, B 228, C 54.
- Lý do của mức B:
  - `structure_veto`: 118;
  - S2 = 2: 44;
  - S3 = 3: 33;
  - S3 = 2: 28;
  - S1 = 3: 24;
  - S1 = 2: 6.
- So với grade cũ (theo điểm chi tiết), trên hệ tiered:
  - Excellent → A 2089, → B 102;
  - Good → A 101, → B 72, → C 4;
  - Acceptable → B 53, → C 31;
  - Poor → B 1, → C 19.
- Không có bộ nào từ Excellent xuống C.

**3. S1 của #1 V4 3.8.2** (cùng classifier v7, cùng mồi RT):
- Mức 5/4/3/2/1: 2019 / 115 / 34 / 18 / **67**. Tức là 67 CRITICAL và 18 HIGH.
- **85 thiết kế có #1 V4 với S1 ≤ 2.** Trong đó, #1 tiered có S1 cao hơn ở **34 ca**:
  - từ CRITICAL lên 2/3/4/5: 4/9/9/7;
  - từ HIGH lên 5: 5.
- 51 ca còn lại không cải thiện được. Gồm 38 ca CRITICAL → CRITICAL, đều là thiết kế fallback, và 13 ca HIGH → HIGH.
- #1 của V4 bị hệ tiered loại ở 78 thiết kế. #1 tiered có S_total cao hơn #1 V4 ở 227 thiết kế.

**4. QĐ 32** — thiết kế mà #1 tiered vi phạm luật V4 trong khi #1 V4 thì không (đã trừ 219 ca V4 không thiết kế được). Số ngoài ngoặc là tiered, trong ngoặc là QĐ 29: 221 (185).
- ΔS > 0: 75 (68). Hệ mới chấp nhận vi phạm để được đặc hiệu cao hơn; ΔS = 1 ở 35 ca.
  - Luật bị vi phạm: `gc_clamp_fail` 39, `gc_out_of_range` 25, `hard_dimer_full_dg` 8 (ΔG −9,4…−12,8), `hard_hairpin_tm` 3, `gc_end_window_fail` 1.
- ΔS = 0: 146 (117). Tầng quyết định là F ở 141 ca (111), điểm chi tiết 4 (6), trình tự 1 (0).
  - Luật bị vi phạm: `gc_clamp_fail` 118 (78), `hard_dimer_full_dg` 15 (15; ΔG −9,1…−9,9, tức F5b mức 2, sát ngưỡng), `gc_out_of_range` 12 (24), `gc_end_window_fail` 3.
  - `gc_clamp_fail` chiếm đa số vì F2 chấm số G/C trong 5 nt cuối, không xét vị trí. Một đầu 3′ như …GCAAT (2 G/C trong 5 nt, 0 G/C trong 3 nt cuối) được F2 = 5, trong khi V4 loại.
- ΔS < 0: 0.
- Mô phỏng, không áp dụng: "cùng S_total thì mồi không vi phạm luật V4 xếp trước (sau veto)".
  - #1 đổi ở 166 thiết kế (130 với QĐ 29), và cả 166 (130) #1 mới đều tuân thủ luật V4.
  - **S1 và S3 của #1 không đổi ở ca nào** (ΔS1 = ΔS3 = 0).

**5. Fallback:** 54 thiết kế, giống nhau dưới QĐ 29 (`benchmark/tiered_fallback_list.csv`).
- Họ seed: miR-548 (11 + 5 họ con), miR-5 (9), miR-1 (3), miR-378 (3), let-7, miR-103, miR-30, miR-376, miR-302, miR-520, miR-5692 (mỗi họ 2), …
- Nguyên nhân bị loại: cả S1 và S2 ở 48 thiết kế; chỉ S1 ở 3; chỉ S2 ở 3.
- Off-target chính của S2: `other` 35, `shifted_3p` 13, `shifted_5p` 3. Có 16 thiết kế fallback do mục nhập lệch đầu (QĐ 19).

## 12. Giai đoạn 2c — DỪNG ở nghiệm thu QĐ 33 (2026-11-18)
QĐ 33–35 đã cài; mặc định theo QĐ 35 (cờ bật). Nghiệm thu đo offline trên pool đã ghi và kết quả BLAST của §10 (`benchmark/tiered_stage2c_offline.json`, `backend/scripts/tiered_stage2c.py offline`).

| #1 | F4 = 1 / % < 45 °C (2472) | F4 = 1 / % < 45 °C (2253) | #1 vi phạm luật V4 (2472) |
|---|---|---|---|
| V4 3.8.2 | — | 201 / 59,5 | — |
| tiered Giai đoạn 2 | 197 / 42,8 | 179 / 45,5 | 555 |
| QĐ 29 (mốc 35 °C) | 237 / 36,4 | 211 / 38,4 | 519 |
| QĐ 29 + 33, chưa QĐ 34 | 243 / 36,8 | 217 / 38,8 | 510 |
| **cấu hình cuối (QĐ 29 + 33 + 34), trọng số 0,10** | **262 / 38,3** | 236 / 40,5 | 389 |
| cấu hình cuối, trọng số 0,15 | 260 / 38,1 | 234 / 40,3 | 389 |

- **QĐ 33: không đạt** (F4 = 1 ≤ 179) ở cả trọng số 0,10 và 0,15. Điều kiện % < 45 °C ≤ 39,0 thì đạt trên 2472 thiết kế.
- Chẩn đoán 262 #1 có F4 = 1 (cấu hình cuối):
  - **226 ca không có ứng viên nào cùng S, veto và QĐ 34 đạt F4 ≥ 2.** Không có QĐ 34 là 196 ca.
  - 32 ca thua ở tầng F, vì F1/F2/F5 lấn át F4 khi không còn F3.
  - 4 ca thua ở điểm chi tiết.

  → Trọng số của điểm chi tiết không thể đưa con số về 179. Mức tối thiểu khi giữ S trước rồi veto là 196 ca, và 226 ca nếu có QĐ 34. Mốc 179 được đọc trên 2253 thiết kế; trên 2472 thiết kế, tiered Giai đoạn 2 là 197.
- **QĐ 34: đạt.** #1 đổi ở 121 thiết kế; S1, S2, S3 của #1 không đổi ở thiết kế nào. Số #1 vi phạm luật V4 giảm 510 → 389.
- **Bước A5 chưa chạy:** `blast_cache.sqlite` chỉ có 425 dòng (5 thiết kế, từ test). Lượt BLAST toàn bộ ở §10 gọi thẳng `check_offtarget_batch` và lưu tóm tắt S1 vào `outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz`, không qua cache SQLite. Vì vậy cache hit sẽ ≈ 0 % dù khóa cache không đổi.

