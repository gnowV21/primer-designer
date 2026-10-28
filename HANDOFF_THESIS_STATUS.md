# HANDOFF — Trạng thái dự án khóa luận (cập nhật 2026-10-28)

> File này dùng để gửi lại cho Claude ở phiên mới, để Claude biết đã làm được gì, đang ở bước nào và còn gì phải làm cho khóa luận.
> Ngôn ngữ trao đổi: **tiếng Việt** (giải thích, feedback). UI labels và code giữ **tiếng Anh**.

## 0. Tóm tắt một đoạn

Đề tài: **công cụ web thiết kế mồi stem-loop RT-qPCR cho miRNA trưởng thành** (phương pháp Chen et al. 2005, NAR 33:e179) của HG Lab. Stack: Flask 3 (Python) + React 18/Vite 5/Tailwind 3. Thiết kế 3 mồi: mồi RT stem-loop, mồi xuôi (forward) đặc hiệu, mồi ngược universal cố định `5'-CCAGTGCAGGGTCCGAGGTA-3'`. Phần mềm đã **hoàn chỉnh về tính năng** (algorithm v3.1.0, đã qua audit khoa học), đã **kiểm chứng in-silico 783/783 check (100 %)** trên 62 miRNA + 4 edge case, đối chiếu với mồi đã công bố từ 8 nguồn. **Việc còn thiếu lớn nhất là dữ liệu wet-lab** (hiệu suất qPCR trên mồi do tool thiết kế) và **viết khóa luận**.

## 1. Git

- Nhánh làm việc: `feat/design-focus` (base: `master`). Chưa mở PR. Xem `git status -sb` để biết số commit chưa push.

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
| 2026-10-22 | Chỉ mục isomiR 3' dựng lại trên **đủ 42.494 mẫu isomiRdb** (ma trận read-count, trước đó 20.635); algorithm **v3.1.1** (chỉ đổi mức cảnh báo 3', không đổi điểm) |
| 2026-10-26 | **Determinism invariant, algorithm v3.1.2**: mỗi pool tail 7–12 nt tự tạo RNG riêng, seed = SHA-256(trình tự, tail_len, max_pool) — trước đó 6 pool dùng chung 1 RNG/lần thiết kế. Sửa kèm lỗi nhánh dự phòng tạo lại `Random(0)` mỗi vòng (pool chỉ còn 1 tail). Mồi xuôi đổi tail ở phần lớn target (1 ca đổi vùng đặc hiệu: miR-10a 14→16 nt); RT + reverse không đổi. So điểm V4 mồi #1 cũ/mới trên 181 miRNA: TB 93,82 → 93,84, tốt hơn 54 / kém 56 / bằng 71, lệch tối đa ±2,2 → tương đương. Validation vẫn **2439/2439**; results.json, VALIDATION_REPORT, benchmark export đã sinh lại |
| 2026-10-28 | **BLAST bộ phân loại v2** (AUDIT §10.1, SPEC_phase3 §8.13): sửa BLAST không chạy khi đường dẫn có dấu cách (dùng `BLASTDB`); sửa bảng Kwok tra sai mạch (sense thay vì khuôn); **cổng Tm duplex so với Tm đúng đích** (SAFE nếu kém > 10 °C, CRITICAL nếu trong 5 °C) thay luật neo 10 nt; bỏ BLAST mồi universal; khóa cache có phiên bản bộ phân loại. Xóa DB Ensembl; DB giữ miRBase **22.1**. Không đổi thiết kế mồi (`ALGORITHM_VERSION` giữ 3.1.2) |
| 2026-10-28 | **BLAST bộ phân loại v3** (AUDIT BLAST-07, SPEC_phase3 §8.14): chính đích = tên khớp có ranh giới + trình tự tương thích (lệch đầu ≤ 2 nt); hit khác tên nhưng trùng/tương thích trình tự → nhóm `identical_sequence`. Sửa lỗi script độ nhạy (tra `id` thay vì `label`) — "35 mồi Busk bị bỏ qua" là do lỗi này, không phải do tên. Độ nhạy 175/178 mồi (loại 3 putative): stem-loop CRITICAL 127 hit/51 mồi → **26/12**; Busk 87/46 → 25/21 |
| 2026-10-28 | **Algorithm v3.2.0 — chấm điểm trước, chọn đa dạng sau** (SPEC_algorithm §C): bộ lọc đa dạng cũ chạy trước khi chấm, giữ 1 mồi/đầu 3' theo \|Tm−60\| (hòa → thứ tự sinh) và bỏ đầu 3' cách 1 nt → 76/169 miRNA (45 %) chỉ có 1 bộ mồi, vd. miR-21-3p mất vùng 13 nt mà sRNAPrimerDB chọn. Nay chấm 20 đuôi/đầu 3' rồi `select_diverse_top` chọn 3 theo điểm, nới dần (≥2 nt → 1 nt → biến thể đuôi, có nhãn). Kẹp GC: chỉ loại 0 G/C; 1 G/C cảnh báo + 75 điểm (trọng số V4 không đổi). Kết quả: **165/165 miRNA thiết kế được có đủ 3 bộ**; #1 luôn điểm cao nhất (60/165 #1 có kẹp 1 G/C). Validation vẫn **2439/2439**; mồi xuôi #1 đổi ở 175/201 target; benchmark export 220/220. BLAST với mồi mới: stem-loop CRITICAL 166/59 → **29/13**. Sửa kèm **ENG-08**: backend sập khi có yêu cầu đồng thời (primer3 không an toàn đa luồng) → `primer3_safe.py` |
| 2026-10-29 | **BLAST bộ phân loại v4** (SPEC_phase3 §8.15): base đầu 3′ bị BLAST cắt (căn chỉnh cục bộ không kết thúc bằng mismatch) được khôi phục từ trình tự đầy đủ → phân loại Kwok theo cặp thật; Tm_off tính trên khung đọc của mồi (+1 base, trùng khớp Tm_on trên đích); vùng Tm sát đích: TOLERANT → CRITICAL, G:G/BLOCKING/REDUCING → HIGH; hai base cuối lệch → SAFE trừ base cuối T → MEDIUM (Kwok 1990 abstract). Sửa trích dẫn Primer3 (`*_TH` là Tm tuyệt đối, đặt dưới `PRIMER_MIN_TM` 10 °C). Độ nhạy stem-loop, biên 10 °C: 29 → **32** hit CRITICAL, 13 mồi (không đổi) |
| 2026-10-29 | **Algorithm v3.3.0 — đặc hiệu cấp assay (mô hình ΔCq)** (SPEC_phase3 §8.16, AUDIT §10.2): ΔCq_assay = ΔCq_RT + ΔCq_FWD, xét lệch đầu ±2 nt, giá trị cận dưới từ Chen 2005 / Czimmerer 2013 / Schamberger 2014 / Stadhouders 2010, nhãn CO-AMPLIFIED < 3,3 ≤ PARTIAL < 4,3 ≤ DISCRIMINATED; thay ma trận RT × FWD cửa sổ cố định. isomiR 5′/3′ + bản trùng trình tự báo cáo, không chấm. `tm_accuracy` theo Ta người dùng; vòng lặp overhang dùng khóa xếp hạng cuối; cảnh báo isomiR 3′ theo Schamberger + ghi chú mẫu dịch sinh học. **BLAST v5**: hit cùng họ seed không còn miễn trừ; tách identical/isomiR; mồi không khớp đích → bỏ cổng Tm; kiểm tra nồng độ + `species`. Kết quả: #1 giữ vùng bám 164/165, điểm #1 +0,67; 7 miRNA cảnh báo (miR-20a↔17/106a/20b, let-7a↔7d, miR-103a-1/2, miR-19a/b, miR-669, miR-27a/b); 90/165 chưa có chỉ mục (chỉ hsa/mmu/rno). Validation **2439/2439**, export 220/220, e2e 62/62; BLAST stem-loop biên 10 °C 32/13 → **63/27** (do họ seed) |
| 2026-10-29 | **Algorithm v3.4.0 — chỉ mục mọi loài + BLAST v6** (SPEC_phase3 §8.17, AUDIT REV-11/12): chỉ mục overhang dựng từ đúng `mature.fa` của BLAST DB (miRBase 22.1, 271 loài, 48.885; script dừng nếu số trình tự lệch, metadata ghi sha256); miRNA virus sàng lọc cùng loài chủ (`VIRUS_HOST_SPECIES`); ghi chú độ phủ chú giải ngoài hsa/mmu; tiền tố loài 3–5 ký tự (trước đó `kshv-`, `hcmv-`, `mdv1-` bị đọc là người). 90 target trước đây `no_index_data`: 77 DISCRIMINATED / 7 PARTIAL / 6 CO-AMPLIFIED, #1 không đổi ở cả 90. Validation **2439/2439**, export 220/220; BLAST stem-loop biên 10 °C **65/29** |

## 3. Kiểm chứng (số liệu dùng được cho chương Kết quả)

- **Validation in-silico (hiện tại, v3.2.0, chạy 2026-10-28):** `validation/results.json` — **2439/2439 check pass (100 %)**, 201 target (197 mục `mirnas` + 4 edge case trong `reference_mirnas.json`; report ghi "193 miRNAs + 4 edge cases"). Bộ gốc ban đầu: 783/783, 62 miRNA + 4 edge case. Báo cáo: `validation/VALIDATION_REPORT.md` (bản đã commit), phương pháp: `validation/VALIDATION_PLAN.md`.
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
- Dữ liệu isomiR 3' từ **isomiRdb** (PMID 36243964) — đủ 42.494/42.494 mẫu (từ 2026-10-22; trước đó 20.635 do tải chậm bị server cắt ở ≈1 GiB).
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
   - **Cross-reactivity cho cổng Tm BLAST:** mồi xuôi miR-21 với oligo tổng hợp miR-374a-3p (Tm duplex 22,1 °C vs 44,3 °C đúng đích; trước v2 bị xếp CRITICAL). < 5 % → bằng chứng trực tiếp cho biên 10 °C.
4. Viết khóa luận: Tổng quan (stem-loop RT-qPCR, Chen 2005, isomiR, family) → Phương pháp (thuật toán, 15 tiêu chí V4, nhiệt động học, BLAST 3'-anchoring + cổng Tm duplex, LNA) → Kết quả (validation 2439/2439, so sánh mồi công bố, benchmark LNA, độ nhạy cổng Tm, ảnh visualization) → Thảo luận (giới hạn: chưa có wet-lab, isomiRdb thiếu mẫu huyết thanh, 4 miRNA bị từ chối, miR-155 route miRBase trả biến thể 24 nt, BLAST không mô hình bước RT, dữ liệu miRBase 22.1).
5. **Nâng miRBase lên Release 23.1** (mốc riêng, đổi số liệu): build lại DB BLAST (xử lý 10 tên trùng cho `-parse_seqids`), chỉ mục family + overhang; kiểm tra route `/api/mirbase` (API trực tuyến có thể đã trả 23.1 — có thể là nguyên nhân lỗi miR-155 24 nt); chạy lại validation + benchmark + độ nhạy BLAST.

**Ưu tiên thấp / tùy chọn:**
- BLAST: chỉ mục family chỉ có hsa/mmu/rno → paralog ở loài khác (ath, osa, ssc, gga) không được gộp "same-family" và hiện CRITICAL.
- BLAST: phân tích độ nhạy biên CRITICAL (3/5/7 °C) — biên này mới quyết định số CRITICAL.
- Bug dữ liệu: `/api/mirbase/hsa-miR-155-5p` trả `UUAAUGCUAAUCGUGAUAGGGGUU` (24 nt, biến thể) thay vì canonical MIMAT0000646 (23 nt) — chưa điều tra.
- ~~BLAST: thay ngưỡng neo 10 nt bằng cổng Tm~~ — xong 2026-10-28 (so với Tm đúng đích, không phải Ta: SPEC_phase3 §8.13).
- Self-host font IBM Plex (đang dùng Google Fonts CDN).
- Family lookup dựa vào tên → dán trình tự trần không tìm được family.

## 6. Tài liệu trong repo nên đọc trước

- `CLAUDE.md` — lệnh chạy, kiến trúc, quy tắc.
- `AUDIT_REPORT.md` — audit khoa học + trạng thái xử lý (§10) + mục cần wet-lab (§4).
- `validation/VALIDATION_PLAN.md`, `validation/VALIDATION_REPORT.md` — phương pháp và kết quả kiểm chứng.
- `SPEC_algorithm.md`, `SPEC_phase3.md` (BLAST, §8.10–8.15), `SPEC_visualization.md`.
- `docs/archive/` — spec/kế hoạch của các phase đã xong (vd. `SPEC_week1.md`: bảng trạng thái các phase; `SPEC_phase2.md`, `SPEC_phase4…8.md`, `RESEARCH_INSIGHTS*.md`). Tài liệu nhắc tới các file này chỉ bằng tên.
- `benchmark/primer_benchmark_export.csv` — so sánh mồi tool vs mồi công bố.

## 7. Quy tắc kỹ thuật cần nhớ khi sửa code

- Mọi thay đổi output thuật toán → tăng `ALGORITHM_VERSION` (`backend/algorithm/constants.py`).
- Sửa renderer visualization → tăng `_RENDER_VERSION` trong `backend/routes/visualize.py` (cache SQLite 30 ngày). `_bar()` tự đảo chuỗi 3to5 → luôn truyền chuỗi theo chiều 5'→3' của chính nó.
- Đổi forward primer output → chạy `python validation/build_benchmark_validation.py --in-place`.
- Không thêm dependency ngoài danh sách trong CLAUDE.md nếu không ghi lý do.
- **primer3 phải import qua `import algorithm.primer3_safe as primer3`** (primer3-py không an toàn đa luồng → sập server; có test chặn).
- Chạy validation với backend **không bật auto-reloader** (`python -c "import app; app.app.run(port=5000, debug=False, use_reloader=False)"`): reloader trên Windows có thể khởi động lại giữa chừng do sự kiện file giả và cắt ngang validation.
- Mọi thay đổi chọn mồi xuôi → chạy lại validation, `build_validation_report.py`, `build_benchmark_validation.py --in-place`, `export_benchmark_primers.py`, `blast_tm_gate_sensitivity.py`.
