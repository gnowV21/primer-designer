> Phần 1 đã thay bằng docs/SPEC_scoring_tiered_4.0.0.md; Phần 4–5 làm sau khi có 4.0.0.

# Nhiệm vụ: chuẩn bị bản đóng băng thuật toán 4.0.0 cho khóa luận

Đọc trước: `CLAUDE.md`, `HANDOFF_THESIS_STATUS.md`, `AUDIT_REPORT.md` §10, `docs/DECISIONS_crossreactivity.md`, `benchmark/scoring_weight_sensitivity.json`.
Trao đổi bằng tiếng Việt; code, UI, commit message bằng tiếng Anh.

## Bối cảnh
- `master` @ 9182922, algorithm 3.8.1. Từ 26/10 đã đổi `ALGORITHM_VERSION` 9 lần; mỗi lần đổi lại số liệu validation, benchmark, ma trận.
- In silico chính thức: tháng 1–2/2027. Wet-lab: tháng 3–4/2027. Bảo vệ: 12–25/07/2027. Mọi số liệu trong khóa luận phải lấy từ MỘT phiên bản.
- Mục tiêu: xử lý các phần dưới đây, gắn version 4.0.0, tag `thesis-freeze-4.0.0`, hạn 31/12/2026. Sau tag chỉ sửa lỗi không đổi output.

## Quy tắc làm việc
1. Làm trên nhánh tích hợp `release/4.0.0`; mỗi thay đổi thuật toán là một nhánh con + PR vào `release/4.0.0`.
2. Trước khi sửa thuật toán: đo tác động offline trên 2656 miRNA hsa (dùng pool đã ghi, như `backend/scripts/scoring_weight_sensitivity.py`). Báo cáo: số mồi #1 đổi, số ca `hard_filter_fallback` mới, validation pass/fail, thay đổi ở các miRNA ứng viên wet-lab (Phần 5). **Dừng và chờ tôi duyệt** trước khi merge.
3. Chạy lại toàn bộ pipeline ở HANDOFF §7 MỘT lần ở Phần 4, không chạy sau từng PR (trừ khi cần số liệu để duyệt).
4. Không mở lại quyết định ở HANDOFF §4 ngoài những mục ghi ở đây. Không đổi `SCORING_WEIGHTS_V4`.
5. Mọi ngưỡng mới phải có nguồn (bài báo hoặc tài liệu Primer3), nếu không thì ghi rõ "mốc riêng của tool, chưa hiệu chỉnh".
6. Không thêm dependency.

## Phần 0 — Vệ sinh repo (không đổi output)
0.1 26 file trong working tree chỉ khác ký tự xuống dòng (`git diff --ignore-cr-at-eol` rỗng). Thêm `.gitattributes` (`* text=auto eol=lf`; khai báo binary cho *.sqlite, *.zip, *.png, *.parquet, …), chuẩn hóa, xác nhận `git status` sạch. Commit riêng, không trộn thay đổi nội dung.
0.2 Sửa `HANDOFF_THESIS_STATUS.md`: ngày cập nhật ở tiêu đề; §1 (feat/design-focus đã merge); §3 đang ghi số liệu v3.2.0 → cập nhật theo 3.8.1; §5 bỏ mục đã xong (mở PR; "BLAST không mô hình bước RT" đã sửa ở classifier v7), thêm mục còn mở: REV-21, REV-23, D-8, D-16, D-17.

## Phần 1 — Chấm điểm V4: tiêu chí không phân biệt ứng viên
Số đo hiện có (pool 3.7.0, 2253 thiết kế hsa): `mfe_stemloop`, `end_stability`, `bound_fraction_full`, `family_discrimination` thay đổi giữa các ứng viên ở 0 % pool; `hairpin_penalty`, `dimer_penalty`, `tm_pair_match` thay đổi ở ≤ 3,6 % pool và 0 % trong top 5. Khoảng 0,47 / 0,95 trọng số được chấm không ảnh hưởng thứ hạng. Chênh điểm #1 − #2: trung vị 0,0; ≤ 0,5 điểm ở 2016 / 2248 thiết kế.
1.1 REV-23: chấm `family_discrimination` theo từng ứng viên (gọi `check_overhang_collision` với độ dài vùng đặc hiệu của chính ứng viên, cache theo độ dài). Đo: % pool mà tiêu chí thay đổi, số #1 đổi, số #1 có nhãn CO-AMPLIFIED (hiện 52).
1.2 `end_stability`: kiểm tra có bão hòa không (bao nhiêu trong 131.039 ứng viên có `pass = False`; ΔG 5 nt cuối lớn nhất). Chỉ báo cáo và đề xuất phương án, không tự sửa.
1.3 REV-21: đo tác động của tiêu chí Primer3 `PRIMER_MAX_SELF_END_TH` = 47 °C (cách làm như REV-20): số ứng viên bị loại, ca dự phòng mới.
1.4 Sau 1.1–1.3: đo lại bảng biến thiên tiêu chí và phân bố chênh #1 − #2. [QUYẾT ĐỊNH: có/không] Khi chênh < 1 điểm, UI và export ghi các bộ mồi là "equivalent in silico" thay vì ngụ ý #1 tốt hơn. Ghi quy tắc vào `SPEC_algorithm.md`.

## Phần 2 — miRNA không thiết kế được (D-8)
403 / 2656 hsa thất bại ("no valid forward primer candidates"), GC trung vị 70 %; có miR-1-5p, miR-23a-5p, miR-210-5p, miR-326, miR-375-5p, miR-663a.
2.1 Phân tích: đếm lý do thất bại theo từng ràng buộc / hard filter (GC, Tm, độ dài, hairpin Tm, dimer). Bảng + danh sách miRNA có số < 1000.
2.2 [QUYẾT ĐỊNH: A = thêm tầng "relaxed" | B = giữ nguyên, ghi là giới hạn]. Nếu A:
  - Chỉ chạy khi tầng chuẩn không có ứng viên; nới đúng ràng buộc gây thất bại, theo bậc.
  - Mọi bộ mồi gắn `design_tier: "relaxed"` + cảnh báo rõ trong UI và export.
  - Test: 2253 thiết kế hiện có không đổi byte nào.
  - Đổi 4 check "giới hạn đã biết" trong validation (ath-miR171a-3p, ebv-miR-BART6-3p, ssc-miR-2137, mmu-miR-124-3p) thành kiểm tra nhãn relaxed; so mồi relaxed của mmu-miR-124-3p với mồi đã công bố (E 107 %).

## Phần 3 — Nguồn trình tự miRNA
3.1 Điều tra `/api/mirbase/hsa-miR-155-5p` trả 24 nt (`UUAAUGCUAAUCGUGAUAGGGGUU`) thay vì MIMAT0000646 (23 nt).
3.2 Chạy trên toàn bộ hsa: bao nhiêu ID mà route trả trình tự khác `mature.fa` 22.1 (file dùng cho BLAST DB và chỉ mục overhang).
3.3 [QUYẾT ĐỊNH: ghim route về `mature.fa` 22.1 cục bộ (đề xuất) | nâng toàn bộ lên release mới]. Mục tiêu: trình tự thiết kế, chỉ mục overhang, BLAST DB cùng một release; ghi release + sha256 vào metadata kết quả và export.

## Phần 4 — Đóng băng
4.1 Gộp các thay đổi đã duyệt trên `release/4.0.0`; `ALGORITHM_VERSION = "4.0.0"`; chạy lại toàn bộ pipeline HANDOFF §7, backend tests, e2e, ma trận hsa.
4.2 Viết `docs/THESIS_FREEZE_4.0.0.md`: commit hash; phiên bản primer3-py, ViennaRNA, BLAST+; miRBase release + sha256; bảng số liệu chính (validation, benchmark, độ nhạy BLAST, độ phủ hsa, biến thiên tiêu chí, chênh #1 − #2); danh sách giới hạn chuyển sang phần Thảo luận (D-16/REV-15, D-17, D-3, D-4, ISO-05, SCI-07, SCI-09, trọng số chưa hiệu chỉnh, …).
4.3 Merge vào `master`, tag `thesis-freeze-4.0.0`, cập nhật HANDOFF.

## Phần 5 — Hỗ trợ thiết kế wet-lab (chỉ phân tích, không đổi code)
Bối cảnh: huyết tương, 3 miRNA người, 3 lặp, PTN Di truyền Người. 3 miRNA × 3 lặp không đủ để hiệu chỉnh trọng số (cần N ≥ 20) — đừng đề xuất mục tiêu đó.
Tạo `docs/WETLAB_CANDIDATES.md` bằng bản 4.0.0:
- Ứng viên để xét [tôi sẽ chốt]: hsa-miR-16-5p, hsa-miR-21-5p, hsa-let-7a-5p, hsa-miR-451a, hsa-miR-126-3p, hsa-miR-223-3p. Mỗi miRNA: bộ mồi #1–#3, điểm, chênh điểm, nhãn đặc hiệu cấp assay, paralog CO-AMPLIFIED/PARTIAL, cảnh báo isomiR 3′, kết quả BLAST.
- Hai thí nghiệm dùng oligo tổng hợp: (a) phản ứng chéo trong họ (vd. assay let-7a trên oligo let-7c, let-7d, …) để so với R dự đoán và Chen 2005 Fig. 7; (b) mồi xuôi miR-21 với oligo miR-374a-3p (kiểm cổng Tm BLAST). Liệt kê trình tự oligo cần đặt.
- So #1 với #3 của một miRNA để kiểm giả thuyết "các bộ mồi tương đương in silico".
- Control theo MIQE: standard curve 5 điểm, NTC, no-RT, melt curve.
Dừng sau khi viết, chờ tôi chốt.

## Ngoài phạm vi
- Ma trận phản ứng chéo / ML (D-1…D-4, D-13, D-14): giữ mặc định, chỉ dựng lại ở 4.0.0. Không mở phân tích mới.
- D-16, D-17, ISO-05, UX-02, UX-05, Docker: ghi vào giới hạn, không làm.

## Báo cáo cuối
Bảng: mục — trạng thái — tác động số liệu — file thay đổi — PR.
