# HANDOFF — Trạng thái dự án khóa luận (cập nhật 2026-10-08)

> File này dùng để gửi lại cho Claude ở phiên mới, để Claude biết đã làm được gì, đang ở bước nào và còn gì phải làm cho khóa luận.
> Ngôn ngữ trao đổi: **tiếng Việt** (giải thích, feedback). UI labels và code giữ **tiếng Anh**.

## 0. Tóm tắt một đoạn

Đề tài: **công cụ web thiết kế mồi stem-loop RT-qPCR cho miRNA trưởng thành** (phương pháp Chen et al. 2005, NAR 33:e179) của HG Lab. Stack: Flask 3 (Python) + React 18/Vite 5/Tailwind 3. Thiết kế 3 mồi: mồi RT stem-loop, mồi xuôi (forward) đặc hiệu, mồi ngược universal cố định `5'-CCAGTGCAGGGTCCGAGGTA-3'`. Phần mềm đã **hoàn chỉnh về tính năng** (algorithm v3.1.0, đã qua audit khoa học), đã **kiểm chứng in-silico 783/783 check (100 %)** trên 62 miRNA + 4 edge case, đối chiếu với mồi đã công bố từ 8 nguồn. **Việc còn thiếu lớn nhất là dữ liệu wet-lab** (hiệu suất qPCR trên mồi do tool thiết kế) và **viết khóa luận**.

## 1. Git

- Nhánh làm việc: `feat/design-focus` (base: `master`). Đi trước `origin/feat/design-focus` **22 commit, chưa push**. Chưa mở PR.
- HEAD: `59a6e35` (2026-10-08, "store family-grouping report db_path repo-relative").
- Chưa commit: sửa smoke test `backend/tests/smoke/test_design_e2e.py` + file handoff này. (`VALIDATION_REPORT.md` bị ghi đè bản cũ 184/184 đã được khôi phục về 783/783.)

## 2. Các giai đoạn đã hoàn thành (theo thời gian)

| Giai đoạn | Nội dung |
|---|---|
| Phase 1 | Setup, form nhập liệu, tra cứu miRBase (`/api/mirbase/<id>`) |
| Phase 2 | Thuật toán thiết kế mồi, chấm điểm V3 |
| Phase 3 | Chấm điểm V4 (15 tiêu chí, tổng trọng số = 1.00), bound fraction, hard filters |
| Phase 4–5 | Probe TaqMan, kiểm tra multiplex, protocol advisor, edge cases (E1–E7), normalization advisor |
| Phase 6 | BLAST off-target, Family Specificity Map, Tm lai DNA:RNA (Sugimoto 1995) |
| Phase 7 | Benchmark family 50 miRNA, cờ isomiR, production hardening |
| Phase 8 | Batch design (**đã gỡ** theo quyết định), LNA Tm calculator (**giữ, đã benchmark**), session history (gỡ rồi làm lại bằng IndexedDB ở `/history`) |
| 2026-08 | Áp dụng HG Lab Design System (IBM Plex, tokens); **gỡ toàn bộ AI chatbot/HRM/Ollama** để tập trung vào thiết kế mồi |
| 2026-08 | Sửa BLAST: 3'-anchoring + gộp hit cùng seed-family → 174 CRITICAL giả còn 6 |
| 2026-08 | Gap A: LNA (bảng NN Owczarzy 2011 đã kiểm chứng; RMSD ΔTm 0.78 °C so với McTigue 2004), mở rộng loài hsa/mmu/rno |
| 2026-08 | Gap B3: OpenAPI 3.1 (`/api/docs`, `/api/openapi.yaml`) + test chống lệch route |
| 2026-08 | Trang **Primer Analyzer** (`/analyze`): người dùng dán bộ mồi có sẵn → phân tích nhiệt động (không chấm điểm) |
| 2026-09-17/19 | **Visualization module** (SVG: phản ứng 4 giai đoạn, đường cong melting, gel ảo; `/api/visualize`); **Designer 2 tầng**: `/design` (Basic, 3 bước) và `/design/advanced` |
| 2026-09-18/19 | **Audit khoa học v3.1.0** (`AUDIT_REPORT.md`): sửa SCI-01…SCI-13, ENG-01…06, UX-01…07 (chi tiết mục 4) |
| 2026-10-08 | **Mở rộng bộ kiểm chứng** với mồi đã công bố → 783/783; xuất file benchmark so sánh mồi tool vs mồi công bố |
| 2026-10-09 | Thêm 46 assay từ 7 bài (bm_01–04 thân Chen, bm_11–13 hệ khác) → **1382/1382**; logic so sánh gom vào `compare_published()` (dùng chung validate + export) |
| 2026-10-10 | Thêm 89 assay: Busk 2014 miRprimer (80/82 assay đã kiểm chứng wet-lab, nhóm `polyA_system`, chỉ chấm lõi forward) + bm_001–003 → **2439/2439**; 2 ca từ chối mới ghi là giới hạn đã biết |

## 3. Kiểm chứng (số liệu dùng được cho chương Kết quả)

- **Validation in-silico:** `validation/results.json` — **783/783 check pass (100 %)**, 62 miRNA + 4 edge case. Báo cáo: `validation/VALIDATION_REPORT.md` (bản đã commit), phương pháp: `validation/VALIDATION_PLAN.md`.
  - Ground truth tất định theo Chen 2005: RT primer = body universal cố định + revcomp 6 nt đầu 3'; reverse = hằng số; vùng đặc hiệu forward = tiền tố 5' của miRNA. Tính lại độc lập từ trình tự tool thực dùng.
  - Kiểm tra cửa sổ nhiệt động (Fwd Tm ≈ 60 °C, GC %, amplicon 63–73 bp), độ đặc hiệu let-7 (so với Wang 2017), edge cases E1/E4/E5/E6.
- **Mở rộng 2026-10-09 (46 assay, cột `benchmark_group`):** `chen_body` = Mashayekhi 2019 (let-7b, 200b, 145: RT trùng byte-to-byte), Zhang 2007 (let-7a, overhang in 5 nt: thân trùng), Zheng 2014 (143, 145, overhang 8 nt: thân trùng), Bagheri 2021 (15b, 195, 103a-2-5p: thân **biến thể** CGAGAG → chỉ chấm overhang 7 nt + lõi forward). `other_body` = Wang 2018 (9 let-7/miR-98; let-7c/7i dùng thân Chen → RT trùng byte-to-byte), Cao 2023 (21 miRNA chuột; 2 lỗi in RT miR-467a-5p/34c-5p, xác nhận bằng probe trong bài → không chấm; 5 lõi forward 9 nt < 10 → không chấm), Mou 2013 (7 miRNA lúa, overhang 8 nt).
- **Mở rộng 2026-10-10 (89 assay):** Busk 2014 (BMC Bioinformatics 15:29, Additional file 5) — hóa học poly(A)/poly(T), không có mồi RT stem-loop → chỉ chấm lõi forward: 79/79 khớp (ssc-miR-2137 bị từ chối). bm_001 Lukashevich 2026 (thân Chen, chuột): 4 RT trùng byte-to-byte, miR-124-3p bị từ chối. bm_003 Nourmohammadi 2019 (loop Chen biến thể CCGACCGG → chỉ chấm overhang + forward). bm_002 Keyhani 2025 (thân khác; forward miR-155 in trùng forward miR-146a → không chấm).
- **So sánh với mồi đã công bố** (mục 2 của report; full sequence: `benchmark/primer_benchmark_export.csv`, xem `n_design_ok` trong file JSON):
  - **Chen et al. 2005** (NAR) — miR-21, let-7c, miR-10a, miR-22, miR-26b: RT primer **trùng byte-to-byte**.
  - **Varkonyi-Gasic 2007** (Plant Methods 3:12) — ath-miR156a/159a/166a/167a: RT **trùng byte-to-byte**.
  - **Chen, Bosmajian, Woo 2024** — miR-16-5p: RT **trùng byte-to-byte**.
  - **Czimmerer 2013** (PLoS ONE e55168) — miR-1, 181a/b/c, 155: hệ body khác, nhưng **overhang 6 nt trùng** + lõi forward trùng.
  - **Cosmopoulos 2009** (J Virol 83:2357) — 30 miRNA EBV: hệ overhang 8 nt; overhang 6 nt của tool = tiền tố 5' của overhang 8 nt → pass.
  - **Yang 2014** (USLP), **Zhao** (miR-195): chỉ so lõi forward (hệ universal khác).
  - 4 khóa luận cử nhân nội bộ lab (miR-125b, 9-3p, 221-3p, 222-3p) — ghi rõ là **nguồn chưa bình duyệt**.
- **Giới hạn đã ghi nhận (không sửa thuật toán, theo quyết định chủ dự án):** ath-miR171a-3p, ebv-miR-BART6-3p, ssc-miR-2137 (GC 85,7 %) và mmu-miR-124-3p (20 nt, chỉ còn 14 nt cho forward; GC > 60 % / đầu 3′ CGCGG) — tool từ chối thiết kế, trong khi mồi công bố của các bài này vi phạm chính luật của tool mà vẫn chạy được wet-lab (miR-124-3p: E 107 %) → đưa vào Thảo luận: bộ lọc chặt hơn thực tế (check sẽ fail nếu tool đột nhiên thiết kế được). Các assay nhắm isoform ±1 nt không được chấm.
- **LNA:** benchmark với 39 oligo McTigue 2004 — RMSD ΔTm 0.78 °C (bài báo 0.85).
- **Test suite (chạy lại 2026-10-08, cả 2 server đang chạy):** backend unit + route **578 passed, 3 skipped, 0 failed** (`cd backend && python -m pytest tests visualization -q --ignore=tests/smoke`); smoke API **5/5**; e2e Playwright **62/62**; validation chạy lại với API thật **783/783** — `results.json` sinh ra trùng y bản đã commit (tool tất định). Smoke test `test_design_v4_scoring_present` đã được sửa cho khớp SCI-02 (`bound_fraction_binding` → `bound_fraction_binding_pct`).

## 4. Quyết định khoa học đã chốt (KHÔNG mở lại)

- **Overhang RT: mặc định 6 nt; 5 và 7 nt được hỗ trợ** kèm cảnh báo off-label; ngoài 5–7 → HTTP 400. Độ dài overhang luôn đọc từ mồi (`len(S) − 44`), không giả định 6.
- `SCORING_WEIGHTS_V4` (15 tiêu chí) **khóa**; RT primer và probe không chấm điểm; LNA chỉ tham khảo. Occupancy forward ở Ta (SCI-02) chỉ hiển thị, không chấm.
- MFE stem-loop gấp bằng ViennaRNA **tham số DNA** (Mathews 2004, 37 °C).
- Hiệu chỉnh muối: giữ primer3 `santalucia` (+ von Ahsen 2001 cho Mg²⁺).
- Dữ liệu isomiR 3' từ **isomiRdb** (PMID 36243964) — giới hạn: chỉ 20.635/42.498 mẫu (server cắt file ~1 GB), serum/plasma ít đại diện.
- Family miRNA: nhóm theo seed (nt 2–8) từ `mature.fa` (miFam.dat đã bị miRBase gỡ).
- Thí nghiệm miR-16 exp 220826 của lab chỉ là **case study minh họa** — không dùng để calibrate.
- Đã hoãn: song ngữ VI/EN (UX-02), mẫu đặt hàng nhà cung cấp (UX-05), Batch design, Docker (B2), form nhập dữ liệu calibration (B1a), trang diễn giải Cq sau chạy (SCI-11 phần 3).

## 5. Việc còn tồn / bước tiếp theo đề xuất cho khóa luận

**Ưu tiên cao (cho khóa luận):**
1. ~~Khôi phục `VALIDATION_REPORT.md`, chạy lại toàn bộ test + validation~~ — xong 2026-10-08 (mục 3).
2. Commit sửa smoke test, push nhánh `feat/design-focus`, mở PR vào `master`.
3. **Wet-lab** (phần quyết định giá trị khoa học — xem `AUDIT_REPORT.md` §4):
   - Thiết kế mồi bằng tool cho ≥ vài miRNA → chạy standard curve (hiệu suất 90–110 %), NTC, no-RT, melt curve theo MIQE.
   - Muốn calibrate trọng số (`calibrate_weights.py`): cần **N ≥ 20 assay**, mồi đúng y trình tự tool xuất ra, **gồm cả mồi hạng #2/#3 điểm thấp** (cần ca thất bại). Không dùng hiệu suất lấy từ bài báo.
   - Đo hiệu suất RT theo overhang 5/6/7 nt; kiểm tra sai số Tm amplicon (≥5 bộ).
4. Viết khóa luận: Tổng quan (stem-loop RT-qPCR, Chen 2005, isomiR, family) → Phương pháp (thuật toán, 15 tiêu chí V4, nhiệt động học, BLAST 3'-anchoring, LNA) → Kết quả (validation 783/783, so sánh mồi công bố, benchmark LNA, ảnh visualization) → Thảo luận (giới hạn: chưa có wet-lab, isomiRdb thiếu mẫu huyết thanh, 2 miRNA GC-rich bị từ chối, miR-155 route miRBase trả biến thể 24 nt).

**Ưu tiên thấp / tùy chọn:**
- Bug dữ liệu: `/api/mirbase/hsa-miR-155-5p` trả `UUAAUGCUAAUCGUGAUAGGGGUU` (24 nt, biến thể) thay vì canonical MIMAT0000646 (23 nt) — chưa điều tra.
- BLAST: thay ngưỡng neo 10 nt bằng cổng Tm (Tm duplex so với Ta).
- Self-host font IBM Plex (đang dùng Google Fonts CDN).
- Family lookup dựa vào tên → dán trình tự trần không tìm được family.

## 6. Tài liệu trong repo nên đọc trước

- `CLAUDE.md` — lệnh chạy, kiến trúc, quy tắc.
- `AUDIT_REPORT.md` — audit khoa học + trạng thái xử lý (§10) + mục cần wet-lab (§4).
- `validation/VALIDATION_PLAN.md`, `validation/VALIDATION_REPORT.md` — phương pháp và kết quả kiểm chứng.
- `SPEC_week1.md` (bảng trạng thái các phase), `SPEC_algorithm.md`, `SPEC_visualization.md`.
- `benchmark/primer_benchmark_export.csv` — so sánh mồi tool vs mồi công bố.

## 7. Quy tắc kỹ thuật cần nhớ khi sửa code

- Mọi thay đổi output thuật toán → tăng `ALGORITHM_VERSION` (`backend/algorithm/constants.py`).
- Sửa renderer visualization → tăng `_RENDER_VERSION` trong `backend/routes/visualize.py` (cache SQLite 30 ngày). `_bar()` tự đảo chuỗi 3to5 → luôn truyền chuỗi theo chiều 5'→3' của chính nó.
- Đổi forward primer output → chạy `python validation/build_benchmark_validation.py --in-place`.
- Không thêm dependency ngoài danh sách trong CLAUDE.md nếu không ghi lý do.
