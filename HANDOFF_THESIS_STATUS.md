# HANDOFF — Trạng thái dự án khóa luận (cập nhật 2026-11-18, Giai đoạn 3 của hệ phân tầng)

> File này dùng để gửi lại cho Claude ở phiên mới, để Claude biết đã làm được gì, đang ở bước nào và còn gì phải làm cho khóa luận.
> Ngôn ngữ trao đổi: **tiếng Việt** (giải thích, feedback). UI labels và code giữ **tiếng Anh**.

## 0. Tóm tắt một đoạn

Đề tài: **công cụ web thiết kế mồi stem-loop RT-qPCR cho miRNA trưởng thành** (phương pháp Chen et al. 2005, NAR 33:e179) của HG Lab. Stack: Flask 3 (Python) + React 18/Vite 5/Tailwind 3. Thiết kế 3 mồi: mồi RT stem-loop, mồi xuôi (forward) đặc hiệu, mồi ngược universal cố định `5'-CCAGTGCAGGGTCCGAGGTA-3'`. Phần mềm đã **hoàn chỉnh về tính năng** (algorithm **3.8.2**, đã qua audit khoa học), đã **kiểm chứng in-silico 2439/2439 check (100 %)** trên 193 miRNA + 4 edge case, đối chiếu với mồi đã công bố. Đang chuẩn bị **bản đóng băng thuật toán 4.0.0** cho khóa luận (`docs/PROMPT_thesis_freeze_4.0.0.md`, hạn 31/12/2026): mọi số liệu trong khóa luận sẽ lấy từ một phiên bản. 4.0.0 thay chấm điểm V4 bằng **hệ phân tầng ưu tiên đặc hiệu** (`docs/SPEC_scoring_tiered_4.0.0.md`); bản V4 3.8.2 là mốc so sánh. **Việc còn thiếu lớn nhất là dữ liệu wet-lab** (hiệu suất qPCR trên mồi do tool thiết kế) và **viết khóa luận**.

## 1. Git

- `feat/design-focus` đã merge vào `master` (PR #2). Các thay đổi sau đó đi qua PR #3–#11; `master` @ `9182922` = algorithm 3.8.1.
- **`release/4.0.0`** (từ `master` @ `9182922`): vệ sinh repo, đo tác động offline, algorithm **3.8.2** (REV-23 qua nhánh `fix/rev23-family-per-candidate`; REV-21, `end_stability`, nguồn miRBase). PR `release/4.0.0` → `master` chờ duyệt.
- Sau khi merge: nhánh `feat/tiered-scoring` từ `master` cho hệ phân tầng. Giai đoạn 1 (ngưỡng) đã duyệt 2026-11-17 (QĐ 17–27); Giai đoạn 2 (cài đặt) duyệt 2026-11-18 (QĐ 28–32); Giai đoạn 2b duyệt (QĐ 33–35 cài, mặc định bật). QĐ 36–37 (veto sàn Tm vùng bám < 39 °C; cache) duyệt; Giai đoạn 2c đạt (SPEC §12). **Giai đoạn 3 xong 2026-11-18** (SPEC §13): số liệu chạy lại, `docs/SCORING_TIERED_COMPARISON.md`, PR vào `master` mở nhưng **không merge cho tới khi xong SPEC UI** (QĐ 31). QĐ 31: PR vào `master` không merge cho tới khi xong SPEC UI. Tag `thesis-freeze-4.0.0` gắn khi 4.0.0 xong.
- Từ 2026-11-17 repo có `.gitattributes` (`* text=auto eol=lf`, `*.bat` CRLF, khai báo binary): working tree dùng LF, không còn file "chỉ khác ký tự xuống dòng".

## 2. Các giai đoạn đã hoàn thành (theo thời gian)

| Giai đoạn | Nội dung |
|---|---|
| Phase 1 | Setup, form nhập liệu, tra cứu miRBase (`/api/mirbase/<id>`) |
| Phase 2 | Thuật toán thiết kế mồi, chấm điểm V3 |
| Phase 3 | Chấm điểm V4 (15 tiêu chí; từ algorithm 3.8.0 còn 14, bỏ `gc_skew`; tổng trọng số = 1.00), bound fraction, hard filters |
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
| 2026-10-30 | **Algorithm v3.5.0 — rà soát xử lý isomiR** (SPEC_phase3 §8.18, AUDIT §10.3): (a) giá trị lệch đầu 3′ kèm khoảng đo được (±1 nt: **0–4 Ct, n = 2 miRNA**; −2 nt: 3–4, n = 1) — cả bảng dựa trên 1 bài báo 2 trình tự lệch nhau tới 4 Ct, giá trị điểm là cận dưới. (b) Đổi thuật ngữ: mục miRBase lệch đầu là tên đồng nghĩa/paralog, **không phải isomiR** (`same_sequence`/`shifted_5p`/`shifted_3p`; `isomirs` → `same_molecule_entries`). (c) Cảnh báo sai lệch fold-change định tính khi isoform 3′ ≥ 20 % và IQR ≥ 0,15 (32 % miRNA), dẫn Nejad 2018. Đính chính: Ct 36–39,6 trong Schamberger Fig. 6 là của đối chứng tham chiếu, không phải mẫu đo. Không đổi điểm số. Backend 683 test |
| 2026-11-03 | **UI: một trang Design + chỉnh & chạy lại trên Results.** Gộp Basic/Advanced thành `/design` (chỉ hỏi miRNA; mọi thông số gấp trong "Parameters", hiện chip tóm tắt, mặc định cho tới khi mở; `/design/advanced` chuyển hướng về đây). Trên `/results`: thanh "Parameters used" + "Adjust & re-run" dùng chung `ParameterEditor` với trang Design; chỉ chạy khi bấm Re-run, liệt kê thay đổi (vd. Overhang 6 → 7 nt); giữ tối đa 8 lần chạy để chuyển qua lại (nhãn theo thay đổi + điểm top set); chạy lại thất bại giữ nguyên kết quả cũ; mỗi lần chạy lưu vào History và đồng bộ ngược về draft của Design. Overhang giữ 5–7 nt. **Mặc định giao diện: SYBR Green** (API vẫn mặc định TaqMan để không đổi kết quả validation/benchmark). Chi tiết khoa học trên Results gấp mặc định. Xóa `BasicDesignPage.jsx`, `SearchPage/index.jsx`, `DesignModeToggle.jsx`. Sửa tràn ngang trên điện thoại (thẻ primer set, ScoreBreakdown, Multiplex): 0 px ở 360/390 px. Playwright `workers: 4` vì backend thiết kế tuần tự (khóa thal, REV-07): 8 worker xếp hàng >15 s. Rà soát UI toàn bộ 8 trang × 4 độ rộng (320/390/768/1280): menu vừa không cần cuộn từ 320 px tới tablet, lề 16 px trên điện thoại, footer gọn, trang 404 mới (trước là trang trắng), tiêu đề nhóm thông số không còn bị nút "Reset Tm" đè, lưới trang Home và trích dẫn trang Benchmark không tràn, bỏ cảnh báo lặp ở Benchmark, sửa lời nhắn trỏ tới công tắc precursor đã bị gỡ. E2E 74/74 ổn định (thêm `rerun.spec.js`, `overhang-length.spec.js`, `responsive.spec.js`) |
| 2026-11-07 | **Gỡ Multiplex Panel Check** (`/api/multiplex-check`, `MultiplexPanel.jsx`, `algorithm/multiplex_check.py` và test): công cụ chỉ xét forward × forward / probe và **không xét mồi RT × mồi RT**, trong khi gộp RT là kịch bản multiplex thực tế của stem-loop — dễ gây hiểu nhầm nên bỏ. Protocol advisor P4 (gợi ý chung khi multiplex) giữ nguyên. |
| 2026-11-10 | **Rà soát lại A1–A4 + ma trận phản ứng chéo cấp assay** (nhánh `feat/assay-crossreactivity`). BLAST classifier v7 (AUDIT REV-13/14, SPEC §8.19): bước RT cho hit mồi xuôi (`rt_primer`) → stem-loop CRITICAL 65/29 → 16/10; mục lệch đầu 5′/3′ không còn để `overall_risk` = SAFE. Validation vẫn 2439/2439. Module `crossreactivity/`: mồi #1 cho 2253/2656 hsa miRNA (403 thất bại, chủ yếu giàu GC); R(i,j) = 2^−ΔCq_assay trên 5,98 triệu cặp → 211 HIGH / 102 MEDIUM / 20.708 LOW ngoài đường chéo; heatmap 6 họ; API gộp "đơn vị đo được" cho ML TCGA-BRCA. Số liệu kiểm chứng Chen 2005 Fig. 7 / Mestdagh 2014 **chưa có** (template trống). Quyết định cần duyệt: `docs/DECISIONS_crossreactivity.md` |
| 2026-11-11 | **Algorithm 3.6.0 — ΔG dimer toàn cấu trúc bằng RNAcofold (DNA), đúng cách của Kang 2017** (AUDIT REV-17/18/19, SPEC_algorithm §12 "Lọc cứng"). Đối chiếu nguồn: câu gán cho Busk 2014 là sai (Busk nhân điểm, không loại); Kang không nói dimer gây ức chế qPCR. primer3 ở 60 °C lỏng hơn RNAcofold trung vị 5,4 kcal/mol (534/2253 mồi hsa lọt). Validation 2439/2439; 10/193 target dùng `hard_filter_fallback`. Ma trận phản ứng chéo dựng lại bằng 3.6.0 (434 mồi xuôi đổi; ngoài đường chéo HIGH 211 → 208, MEDIUM 102 → 103, LOW 20.708 → 20.710; bộ đệm giờ gắn với phiên bản thuật toán) |
| 2026-11-11 | **Algorithm 3.7.0 — lọc cứng hairpin theo Tm ≥ 47 °C (mặc định Primer3)** (AUDIT REV-20). Quy tắc ΔG ≤ −6 cũ không loại ứng viên nào trong 9.268 ứng viên của 150 miRNA hsa. Validation 2439/2439, 9 target đổi điểm, thêm 1 ca dự phòng; ma trận hsa dựng lại (197 mồi đổi; ngoài đường chéo HIGH 214, MEDIUM 100, LOW 20.700). Còn mở: quy tắc 2 (dimer đầu 3′) cũng không kích hoạt (REV-21) |
| 2026-11-16 | **Algorithm 3.8.0 — bỏ `gc_skew` khỏi chấm điểm, `gc_clamp` 0,04 → 0,06** (AUDIT REV-22; chủ dự án mở lại trọng số V4 đã khóa). Ngưỡng GC skew không có nguồn. Trong 131.039 ứng viên hsa chỉ 1 ứng viên có motif G-quadruplex, và nó không bao giờ đứng #1. `gc_clamp` là tiêu chí vừa khác nhau giữa các ứng viên vừa có quy tắc từ tài liệu: số mồi #1 có 3 G/C hoặc CCC ở đầu 3′ giảm từ 85 xuống 49. Validation 2439/2439 (111/193 dòng đổi điểm, \|Δ\| ≤ 2,1); benchmark 50/50; ma trận hsa dựng lại (863 mồi xuôi đổi; ngoài đường chéo HIGH 208, MEDIUM 107, LOW 20.700). Phát hiện mới: `family_discrimination` chấm chung một giá trị cho mọi ứng viên, nên không ảnh hưởng việc chọn mồi (REV-23, còn mở). Số liệu: `benchmark/scoring_weight_sensitivity.json`. |
| 2026-11-17 | **Algorithm 3.8.1 — tỉ lệ bám theo cân bằng khối lượng** (AUDIT REV-24). θ = K·C_P/(1 + K·C_P) thay cho công thức √ cũ, vốn chỉ đúng tại 50 %. Không đổi điểm, mồi hay xếp loại (thiết kế lại 2656 miRNA hsa: 0 thay đổi). Chỉ số chu kỳ 1 hiển thị đổi: trung vị 0,31 % (trước 2,71 %); 12 nt 0,08 %, 17 nt 7,8 %. |
| 2026-11-17 | **Bản đóng băng 4.0.0, phần chuẩn bị** (nhánh `release/4.0.0`). `.gitattributes` (LF). Đo tác động offline trên 2656 miRNA hsa bằng cách ghi lại toàn bộ ứng viên rồi xếp hạng lại (`backend/scripts/thesis_freeze_impact.py`, `benchmark/thesis_freeze_impact.json`; tái tạo đúng #1 và top 3 của API ở 2253/2253). Phát hiện: `end_stability` luôn bằng 0 (gấp 5-mer thành hairpin) và kể cả tính đúng cũng không thể fail (tối đa 6,86 < 9,0); **115/2253 thiết kế hsa chạy `hard_filter_fallback`**; 403 ca thất bại đều do lọc sơ bộ GC/kẹp GC, gốc là đuôi 5′ luôn GC ≥ 50 %; miR-155-5p 24 nt là chú giải đúng của miRBase 22.1, route khớp `mature.fa` ở 2656/2656 hsa. Chủ dự án chọn hệ chấm điểm phân tầng cho 4.0.0 (`docs/SPEC_scoring_tiered_4.0.0.md`). |
| 2026-11-17 | **Algorithm 3.8.2 — mốc V4 cho 4.0.0** (AUDIT §10.5). REV-23: `family_discrimination` chấm theo độ dài vùng đặc hiệu của từng ứng viên (#1 đổi ở 13/2253 hsa, top 3 ở 28; #1 CO-AMPLIFIED 52 → 45). REV-21: lọc cứng dimer đầu 3′ theo Tm ≥ 47 °C của Primer3 (không đổi output). `end_stability` tính đúng định nghĩa Primer3 (điểm không đổi, giá trị hiển thị đổi). Nguồn miRBase: release + sha256 vào provenance và file xuất MIQE; trình tự ngoài 22.1 có cảnh báo `sequence_not_in_mirbase_release`; kết quả tra online gắn nhãn "online, release unknown" và không ghi cache. Validation 2439/2439 (`results.csv` không đổi dòng nào); benchmark 50/50; ma trận hsa ngoài đường chéo HIGH 208 → 195, MEDIUM 107 → 111, LOW 20.700 → 20.709. |
| 2026-11-17/18 | **Algorithm 4.0.0, hệ phân tầng — Giai đoạn 1–2** (nhánh `feat/tiered-scoring`, SPEC §9–10). Xếp hạng Đặc hiệu (BLAST S1, ΔCq assay S2, biên Tm S3) → veto cấu trúc → PCR (Tm − Ta) → Linh hoạt → điểm chi tiết; mặc định `tiered`, V4 sau cờ `scoringSystem`. BLAST gộp (1 `blastn` multi-FASTA chia 8 tiến trình + 1 `blastdbcmd`/thiết kế): 212 s → ~8 s, giống từng hit trên 31.049 lần gọi. Thiết kế không cache p50 9,8 s / p90 11,9 s. Trên 2472 hsa có BLAST: #1 khác V4 1670/2253, fallback 54, 219/403 miRNA V4 không thiết kế được nay có mồi (`v4_rule_violations` đánh dấu). |

## 3. Kiểm chứng (số liệu dùng được cho chương Kết quả)

> **Số liệu dưới đây là của algorithm 3.8.2 (2026-11-17), mốc V4 để so với hệ phân tầng 4.0.0**, và sẽ bị thay bằng bản 4.0.0 (chạy lại một lần ở Phần 4 của `docs/PROMPT_thesis_freeze_4.0.0.md`). Không trích số nào của mục này vào khóa luận trước khi có `docs/THESIS_FREEZE_4.0.0.md`.

| Số liệu | Giá trị (3.8.2) | So với 3.8.1 | Nguồn |
|---|---|---|---|
| Validation in-silico | **2439/2439** check, 201 target = 193 miRNA + 4 edge case (+ 4 mục tham chiếu) | `results.csv` không đổi dòng nào | `validation/results.json`; `VALIDATION_REPORT.md` sinh lại (trước đó cũ từ 3.4.0) |
| `hard_filter_fallback` trong bộ validation | 11/194 thiết kế được | như cũ | đếm 2026-11-17 |
| Cảnh báo `sequence_not_in_mirbase_release` (bộ validation) | 19: 18 trình tự in trong Busk 2014 + 1 edge case tổng hợp | mới | — |
| Benchmark 50 miRNA | 50/50 | `compare_tools.md` không đổi | `benchmark/` |
| So mồi công bố | 220/224 thiết kế được, 190 có mồi công bố; cột khớp mồi công bố không đổi | file cũ từ 3.4.0: 124 mồi xuôi khác là tích lũy 3.5.0 → 3.8.2 | `benchmark/primer_benchmark_export.json` |
| Độ phủ hsa | 2253/2656 (403 thất bại, D-8 / REV-27) | như cũ | `outputs/crossreactivity_metadata.json` |
| `hard_filter_fallback` hsa | **115/2253** (REV-26) | như cũ (chưa từng báo cáo) | `benchmark/thesis_freeze_impact.json` |
| Mồi hsa đổi | #1 đổi 13/2253, top 3 đổi 28 (REV-23) | — | pool 3.8.2 vs 3.8.1 |
| Ma trận phản ứng chéo hsa (ngoài đường chéo) | HIGH 195, MEDIUM 111, LOW 20.709 | 208 / 107 / 20.700; 24 cặp đổi mức, đều thuộc 13 assay đổi #1 | `outputs/crossreactivity_*` |
| Độ nhạy BLAST (stem-loop, biên 10 °C + bước RT) | CRITICAL 17 hit / 11 mồi | 16 / 10 (file cũ chạy với mồi 3.5.0; 95/175 mồi đã đổi qua 3.6.0–3.8.2; thêm mmu-miR-467c-5p ↔ 467b-5p) | `benchmark/blast_tm_gate_sensitivity.json` |
| Biến thiên tiêu chí V4 | `family_discrimination` 0 % → 3,5 % pool; `end_stability`, `mfe_stemloop`, `bound_fraction_full` vẫn hằng số; chênh bộ #1 − bộ #2 < 1 điểm ở 1046/2248 | — | `benchmark/thesis_freeze_impact.json` |
| Thời gian thiết kế (20 hsa, seed 42, 1 tiến trình) | p50 1,38 s | 1,09 s | đo 2026-11-17 |
| Backend tests | 733 passed, 3 skipped | 714 | 2026-11-17 |
| E2E Playwright | 74/74 | — (lần trước 2026-11-03) | 2026-11-17 |
| Ma trận: test `crossreactivity/tests` | 29 passed | — | 2026-11-17 |

**Số liệu algorithm 4.0.0** (nhánh `feat/tiered-scoring`, chưa merge — QĐ 31; chi tiết `docs/SCORING_TIERED_COMPARISON.md`, SPEC §13):

| Số liệu | 4.0.0 tiered | 3.8.2 (V4) | Nguồn |
|---|---|---|---|
| Validation in-silico | **2436/2439**; 3 `expected_design_failure` (ath-miR171a-3p, ebv-miR-BART6-3p, mmu-miR-124-3p: V4 từ chối vì GC, tiered thiết kế được, trùng vùng đặc hiệu mồi công bố). V4 sau cờ trùng 3.8.2 | 2439/2439 | `validation/results.json` |
| Benchmark 50 / so mồi công bố | 50/50; 223/224 thiết kế được, 193 có mồi công bố | 50/50; 220/224 | `benchmark/` |
| Độ phủ hsa | **2472/2656** (184 thất bại) | 2253/2656 | `outputs/crossreactivity_metadata.json` |
| #1 S1 ≤ 2 (HIGH/CRITICAL, cùng classifier) | 55/2253 (34 ca cải thiện) | 85/2253 | `benchmark/tiered_stage2c_report.json` |
| `specificity_fallback` / `structure_veto` #1 / dưới sàn 39 °C #1 | 54 / 120 / 196 (của 2472) | — / 115 `hard_filter_fallback` / — | như trên |
| Grade #1 A/B/C | 2032/386/54 (2472) | — | như trên |
| Ma trận hsa ngoài đường chéo HIGH/MEDIUM/LOW | 172 / 105 / 22.620 (2472 assay) | 195 / 111 / 20.709 (2253) | `outputs/crossreactivity_*` |
| Độ nhạy BLAST, 175 mồi validation, lề 10 °C: SAFE / CRITICAL | 105 / 51 | 95 / 54 | `benchmark/blast_tm_gate_sensitivity.json` |
| Thiết kế không cache (20 hsa, seed 2026) | p50 9,8 s, p90 11,9 s (BLAST p50 8,1 s) | p50 1,4 s (không BLAST) | `benchmark/tiered_design_timing.json` |
| Backend tests / e2e / `crossreactivity/tests` | 901 passed, 2 failed (`test_benchmark_endpoint`: validation 2436/2439, chờ quyết định ở mục E), 3 skipped / 74/74 (cache có; lần đầu cache trống 8 fail do giới hạn 15 s) / 29 | 733 / 74 / 29 | 2026-11-18 |

- **Validation in-silico:** `validation/results.json` — 2439/2439 check pass, 201 target (197 mục `mirnas` + 4 edge case trong `reference_mirnas.json`; report ghi "193 miRNAs + 4 edge cases"). Bộ gốc ban đầu: 783/783, 62 miRNA + 4 edge case. Báo cáo: `validation/VALIDATION_REPORT.md`, phương pháp: `validation/VALIDATION_PLAN.md`.
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
- **Test suite (lịch sử, lần chạy 2026-10-08 — số hiện tại ở bảng đầu mục):** backend unit + route **578 passed, 3 skipped, 0 failed** (`cd backend && python -m pytest tests visualization -q --ignore=tests/smoke`); smoke API **5/5**; e2e Playwright **62/62**; validation chạy lại với API thật **783/783** — `results.json` sinh ra trùng y bản đã commit (tool tất định). Smoke test `test_design_v4_scoring_present` đã được sửa cho khớp SCI-02 (`bound_fraction_binding` → `bound_fraction_binding_pct`).

## 4. Quyết định khoa học đã chốt (KHÔNG mở lại)

- **Overhang RT: mặc định 6 nt; 5 và 7 nt được hỗ trợ** kèm cảnh báo off-label; ngoài 5–7 → HTTP 400. Độ dài overhang luôn đọc từ mồi (`len(S) − 44`), không giả định 6.
- `SCORING_WEIGHTS_V4` **khóa** — mở lại một lần ngày 2026-11-16 theo quyết định chủ dự án (algorithm 3.8.0: bỏ `gc_skew`, `gc_clamp` 0,06; còn 14 tiêu chí, 13 được chấm); RT primer và probe không chấm điểm; LNA chỉ tham khảo. Occupancy forward ở Ta (SCI-02) chỉ hiển thị, không chấm.
- MFE stem-loop gấp bằng ViennaRNA **tham số DNA** (Mathews 2004, 37 °C).
- Hiệu chỉnh muối: giữ primer3 `santalucia` (+ von Ahsen 2001 cho Mg²⁺).
- Dữ liệu isomiR 3' từ **isomiRdb** (PMID 36243964) — đủ 42.494/42.494 mẫu (từ 2026-10-22; trước đó 20.635 do tải chậm bị server cắt ở ≈1 GiB).
- Family miRNA: nhóm theo seed (nt 2–8) từ `mature.fa` (miFam.dat đã bị miRBase gỡ).
- Thí nghiệm miR-16 exp 220826 của lab chỉ là **case study minh họa** — không dùng để calibrate.
- **2026-11-17 — bản đóng băng 4.0.0:** chấm điểm của 4.0.0 là **hệ phân tầng ưu tiên đặc hiệu** (`docs/SPEC_scoring_tiered_4.0.0.md`, QĐ 1–37); V4 giữ chạy được sau cờ, mốc so sánh là **3.8.2**. Cấu hình cuối (2026-11-18): đặc hiệu trước (BLAST S1 + ΔCq S2 + biên Tm S3, loại CRITICAL / CO-AMPLIFIED), veto mềm cấu trúc rồi sàn Tm vùng bám 39 °C, cùng S thì bộ không vi phạm luật V4 trước, rồi PCR, Linh hoạt (F4 là sàn một phía ≥ 45 °C; độ dài chỉ báo cáo), điểm chi tiết; grade A/B/C theo tầng. Ngưỡng ghi "own threshold" chưa hiệu chỉnh bằng wet-lab. Ở V4: REV-21 theo Tm 47 °C của Primer3; `end_stability` tính đúng Primer3 và vẫn chấm (điểm V4 không đổi); không làm nhãn "equivalent in silico"; D-8 giữ nguyên (giới hạn). Trình tự miRNA ghim về `mature.fa` 22.1 cục bộ; tra online chỉ là dự phòng có nhãn.
- Đã hoãn: song ngữ VI/EN (UX-02), mẫu đặt hàng nhà cung cấp (UX-05), Batch design, Docker (B2), form nhập dữ liệu calibration (B1a), trang diễn giải Cq sau chạy (SCI-11 phần 3).

## 5. Việc còn tồn / bước tiếp theo đề xuất cho khóa luận

**Ưu tiên cao (cho khóa luận):**
1. **Bản đóng băng 4.0.0** (`docs/PROMPT_thesis_freeze_4.0.0.md`, hạn 31/12/2026) — các mục còn mở cần xử lý hoặc ghi thành giới hạn trước khi đóng băng:
   - ~~REV-21, REV-23, `end_stability`~~ — xong ở 3.8.2 (AUDIT §10.5).
   - **Hệ phân tầng** (`docs/SPEC_scoring_tiered_4.0.0.md`): nhánh `feat/tiered-scoring`. Giai đoạn 2 xong (SPEC §10: BLAST gộp 0/31.049 khác biệt, p50 9,8 s; V4 hồi quy giống 3.8.2). Giai đoạn 1–3 xong (SPEC §9–13); cấu hình cuối = QĐ 29 + 30 + 33 + 34 + 36, mặc định bật. Việc tiếp: **SPEC UI** (frontend hiển thị tầng, grade A/B/C, câu "#1 so với #2" theo tầng — hiện sai ở 444 thiết kế), rồi merge PR và Phần 4–5 của PROMPT.
   - **D-8 / REV-27** — 403/2656 hsa không thiết kế được: V4 giữ nguyên (giới hạn); hệ phân tầng bỏ lọc GC %/kẹp GC ở bước sinh ứng viên. Đuôi 5′ giàu AT: chưa làm.
   - **REV-26** — 115/2253 thiết kế hsa chạy `hard_filter_fallback`: xử lý bằng tiêu chí cấu trúc + veto mềm của hệ phân tầng.
   - **D-16** (REV-15) — rU·dG chưa được coi là wobble ở bước RT. Ngoài phạm vi 4.0.0 → giới hạn.
   - **D-17** (REV-16) — Tm theo khung đọc có thể trượt 1–2 nt trong cửa sổ L + 1. Ngoài phạm vi 4.0.0 → giới hạn.
2. **Wet-lab** (phần quyết định giá trị khoa học — xem `AUDIT_REPORT.md` §4):
   - Thiết kế mồi bằng tool cho ≥ vài miRNA → chạy standard curve (hiệu suất 90–110 %), NTC, no-RT, melt curve theo MIQE.
   - Muốn calibrate trọng số (`calibrate_weights.py`): cần **N ≥ 20 assay**, mồi đúng y trình tự tool xuất ra, **gồm cả mồi hạng #2/#3 điểm thấp** (cần ca thất bại). Không dùng hiệu suất lấy từ bài báo.
   - Đo hiệu suất RT theo overhang 5/6/7 nt; kiểm tra sai số Tm amplicon (≥5 bộ).
   - **Cross-reactivity cho cổng Tm BLAST:** mồi xuôi miR-21 với oligo tổng hợp miR-374a-3p (Tm duplex 22,1 °C vs 44,3 °C đúng đích; trước v2 bị xếp CRITICAL). < 5 % → bằng chứng trực tiếp cho biên 10 °C.
3. Viết khóa luận: Tổng quan (stem-loop RT-qPCR, Chen 2005, isomiR, family) → Phương pháp (thuật toán, 14 tiêu chí V4 (13 được chấm), nhiệt động học, BLAST 3'-anchoring + cổng Tm duplex, LNA) → Kết quả (validation 2439/2439, so sánh mồi công bố, benchmark LNA, độ nhạy cổng Tm, ảnh visualization) → Thảo luận (giới hạn: chưa có wet-lab, isomiRdb thiếu mẫu huyết thanh, 4 miRNA bị từ chối, miR-155-5p 24 nt ở miRBase 22.1 khác bản 23 nt mà các bài cũ dùng, dữ liệu miRBase 22.1). *("BLAST không mô hình bước RT" đã sửa ở BLAST classifier v7, REV-13 — không còn là giới hạn.)*
4. **Nâng miRBase lên Release 23.1** (mốc riêng, đổi số liệu): build lại DB BLAST (xử lý 10 tên trùng cho `-parse_seqids`), chỉ mục family + overhang; từ 3.8.2 route `/api/mirbase` chỉ phục vụ bản cục bộ 22.1, tra online gắn nhãn "release unknown"; chạy lại validation + benchmark + độ nhạy BLAST.

**Ưu tiên thấp / tùy chọn:**
- BLAST: chỉ mục family chỉ có hsa/mmu/rno → paralog ở loài khác (ath, osa, ssc, gga) không được gộp "same-family" và hiện CRITICAL.
- BLAST: phân tích độ nhạy biên CRITICAL (3/5/7 °C) — biên này mới quyết định số CRITICAL.
- ~~Bug dữ liệu miR-155-5p 24 nt~~ — không phải lỗi: miRBase 22.1 chú giải MIMAT0000646 dài 24 nt (AUDIT REV-28).
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
