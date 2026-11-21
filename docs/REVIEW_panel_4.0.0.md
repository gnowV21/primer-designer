# Review nhóm 3 vai — algorithm 4.0.0 (2026-11-18)

Review sau tag `thesis-freeze-4.0.0`, ở `master` @ `025c588`. Ba vai: **B** (nhà tin sinh học), **W** (lập trình web tối giản), **E** (người làm stem-loop RT-qPCR thực nghiệm).

Nguồn bằng chứng:
- `/code-review high` trên `frontend/src`, `backend/algorithm`, `backend/routes`.
- Ảnh chụp và chữ hiển thị của trang `/results` (Playwright, 1280 px và 390 px) cho 3 miRNA:
  - hsa-miR-21-5p: grade A;
  - hsa-let-7a-5p: specificity fallback, grade C;
  - hsa-miR-590-3p: #1 dưới sàn Tm vùng bám.
- Gọi `/api/design` trực tiếp.

Trạng thái mỗi mục:
- **Đã xác nhận**: đã chạy lại hoặc đã đọc code.
- **Từ review**: lấy từ báo cáo code review, chưa chạy lại.

Quy tắc sau tag vẫn áp dụng: sửa không đổi output thì làm ngay được; sửa đổi output của thuật toán thì phải tăng `ALGORITHM_VERSION` và đóng băng lại.

## 1. Thuật toán và độ chính xác

### A1. Cảnh báo kẹp GC mâu thuẫn với F2 (đã xác nhận)

- **Hiện tượng:** trên let-7a #1, chip F2 ở L5 (`GTTGT`), nhưng khung Warnings cùng thẻ lại ghi: "Only 1 G/C in the last 3 nt … scored 75/100 on the GC-clamp criterion".
  - "75/100" là điểm của luật V4.
  - Bộ tiered không chấm theo luật này.
- **B:** cùng một mồi bị hai hệ chấm điểm mô tả khác nhau, người đọc sẽ không biết tin cái nào.
- **E:** chỉ có 1 G/C trong 3 nt cuối là bình thường với miRNA, vì đầu 3′ do trình tự miRNA quyết định. Cảnh báo này không dẫn tới hành động nào.
- **Đề xuất (không đổi output):**
  - Bỏ câu "scored 75/100" khỏi bộ tiered.
  - Chỉ nói "1 G/C in the last 3 nt" khi F2 < L3.
  - Bỏ hẳn cảnh báo "3′ end is T".

### A2. Thẻ F4/F3 luôn ghi "floor 45 °C" và "report only" (từ review, đã đọc code)

- `TierSummary.jsx` bỏ qua `binding_tm.mode` và `specific_length.report_only` mà backend gửi sang.
- Cấu hình đóng băng hiện tại không bị ảnh hưởng, vì F4 đang ở chế độ sàn và F3 chỉ báo cáo.
- Nhưng nếu tắt cờ `TIERED_F4_FLOOR`, UI sẽ mô tả sai cách xếp hạng.
- **Đề xuất:** đọc hai trường đó (không đổi output).

### A3. ★ "Best #1" so sánh tổng S trên hai thang khác nhau (đã đọc code)

- Hàm `bestRunIndices` (`utils/tierRank.js`) so tổng S của các lần chạy.
- Lần chạy có BLAST dùng thang /15; lần chạy không có BLAST dùng thang /10. Hai thang này bị so trực tiếp với nhau.
- **Đề xuất:** khi các lần chạy khác nhau về việc có BLAST hay không, không gắn ★.

### A4. Chọn loài "Other" thì kiểm tra đặc hiệu ngầm theo người (đã xác nhận)

- **Thử nghiệm:** trình tự ngẫu nhiên `UGCAUGGACUACGUAGCAUCGA` gửi với `sequence.species = "other"`.
  - S2 và S3 được kiểm tra trên miRNA hsa (worst target hsa-miR-455-5p).
  - Kết quả grade A, không có cảnh báo nào.
- Code review cho rằng trường hợp này sẽ "không kiểm tra gì". Điều đó không tái hiện được. Vấn đề thật là kiểm tra theo người mà không báo cho người dùng.
- **B:** với mẫu thực vật hoặc virus, grade A này không có cơ sở.
- **Câu hỏi Q4.**

### A5. Bộ #1 có Tm vùng bám rất thấp (đã xác nhận)

- Với miR-590-3p, #1 có Tm vùng bám **25,7 °C** (sàn 39 °C; F4 ở L1) nhưng vẫn được grade B.
  - Veto sàn là veto mềm: không có ứng viên nào trong nhóm S tốt nhất đạt 39 °C.
  - Đây là 196/2472 thiết kế hsa.
- **E:** ở chu kỳ 1, mồi xuôi chỉ bám cDNA bằng vùng này. Ở Ta 60 °C, 25,7 °C nghĩa là gần như không bám, nên Cq sẽ muộn hoặc không lên. Ngoài wet-lab thường chữa bằng 2–3 chu kỳ đầu ở Ta thấp (≈ 50 °C) hoặc gắn LNA vào vùng bám.
- **B:** đây không phải lỗi code, mà là chính sách hiển thị và khuyến nghị.
- **Câu hỏi Q2.**

### A6. Đếm ứng viên trong metadata MIQE sai (từ review, đã đọc code)

- `candidates_generated` và `candidates_rejected` đếm số dòng trong `rejection_log`, mà log này ghi một dòng cho mỗi lý do loại.
- Một ứng viên bị loại vì 3 lý do sẽ bị đếm 3 lần.
- Hai con số này đi vào file xuất MIQE.
- **Đề xuất:** đếm theo số ứng viên khác nhau. Việc này không đổi mồi hay thứ hạng, chỉ đổi metadata xuất ra.

### A7. Nồng độ mồi RT trong ghi chú "Use 1 nM … (Kramer 2011), not 50 nM from Chen 2005" (cần kiểm tra nguồn)

- **E:** con số này người làm thí nghiệm sẽ pipet theo, nên phải đúng tuyệt đối. Nếu protocol của lab khác, ghi chú này có hại.
- **Câu hỏi Q3.**

## 2. Code (lỗi đầu vào và độ bền)

| # | Lỗi | Trạng thái | Hậu quả |
|---|---|---|---|
| C1 | `POST /api/design` với body `null`, list, hoặc `sequence` là chuỗi | đã xác nhận: 500 | lỗi HTML 500 thay vì 400 |
| C2 | `bindingRegion3prime` = 6,9 được nhận thành 6 nt (`int()` cắt phần thập phân); `Infinity` gây OverflowError | đã xác nhận: 200 | mồi khác với overhang người dùng yêu cầu |
| C3 | `_fetch_mirbase` coi mọi status khác 200 là "not found" | từ review | miRBase lỗi 5xx bị báo là 404; không chuyển sang RNAcentral; circuit breaker không đếm lỗi |
| C4 | cache SQLite trong `/api/blast-check` không có try/except | từ review | khi đang ghi batch, chờ 60 s rồi trả 500 và bỏ mất kết quả BLAST |
| C5 | `float(predicted_amplicon_tm)` trong `/api/visualize` nằm ngoài try | từ review | giá trị sai định dạng thì trả 500 thay vì 422 |

Cả 5 lỗi đều không đổi output của thuật toán, nên sửa được sau tag. Mỗi lỗi kèm một test route.

## 3. Giao diện: trang `/results`

**W:** nhìn trang let-7a theo thứ tự từ trên xuống:
1. Parameters.
2. Khối "Shared by all candidates":
   - RT primer;
   - Tm (full) 76,9 °C;
   - ghi chú 1 nM;
   - đoạn **"Fold-change caution" dài 6 dòng**.
3. Banner đỏ "No candidate passed the specificity screen", nằm dưới cả đoạn trên.
4. Câu "#1 so với #2".
5. Thẻ #1: lặp lại RT primer và reverse, 3 tầng, Structure checks, Heterodimer check (lặp lại Hetero-dimer), Warnings, BLAST, 3 nút copy.
6. Hai thẻ #2 và #3.
7. Các khối Assay specificity, Seed family, dòng trích dẫn, Quality summary ("6 issues"), thẻ SYBR, Visualization, Scientific details, Export.

Trang let-7a có khoảng 9 khối cảnh báo hoặc ghi chú. Thông tin quan trọng nhất (assay sẽ bắt chéo let-7d) đứng thứ 3.

Ý kiến của từng vai:
- **E:** điều tôi cần trước tiên là: dùng được không, đặt mua 3 trình tự nào, và cần đối chứng gì. Tm của cả mồi RT (77 °C) không giúp tôi quyết định gì. Đoạn isomiR đúng về khoa học, nhưng hiện ở gần như mọi miRNA (21-5p, let-7a, 590-3p) nên người dùng sẽ bỏ qua.
- **B:** phải giữ được dấu vết đầy đủ (S/P/F, BLAST, ΔCq) cho người kiểm tra lại, nhưng gấp vào.
- **W:** một trang, một thứ tự cố định, mỗi thông tin xuất hiện đúng một lần.

**Đề xuất thứ tự** (chỉ đổi UI, không đổi output):
1. **Kết luận:** một dòng gồm grade #1, câu "#1 so với #2", và banner fallback/BLAST nếu có (đỏ chỉ dành cho fallback).
2. **Bộ #1:** RT + Forward + Reverse, kèm nút "Copy for ordering".
3. **Bảng so sánh #1/#2/#3:** S/P/F, Tm vùng bám, Tm, GC, worst off-target. Thay cho 3 thẻ mở riêng.
4. **Đối chứng nên chạy:** đối chứng chéo khi fallback; với vùng bám thấp thì Ta thấp ở chu kỳ đầu (chờ Q2).
5. **Chi tiết (gấp):** tầng tiêu chí, cấu trúc gộp Structure + Heterodimer làm một, BLAST, assay specificity, seed family, isomiR, visualization, nhiệt động học.
6. **Export:** một chỗ duy nhất; bỏ 3 nút copy trong từng thẻ.

**Cắt hoặc rút gọn:**
- Cảnh báo "3′ end is T".
- Câu "scored 75/100".
- Thẻ "SYBR Green mode".
- Tm (full) của mồi RT; thay bằng Tm overhang trên miRNA.
- Khối Heterodimer lặp lại.
- Đoạn isomiR rút còn một dòng và có nút "Why".
- Quality summary trùng với banner.
- Mã thô như `gc_clamp_fail` và "L1–L5" không chú giải; thay bằng chữ ("GC clamp below V4 rule", "level 1/5").

## 4. Câu hỏi chờ chủ dự án

- Q1: bố cục trang kết quả.
- Q2: chính sách cho bộ #1 có Tm vùng bám thấp.
- Q3: nồng độ mồi RT.
- Q4: xử lý khi chọn loài "Other".

Câu trả lời và quyết định ghi ở §5.

## 5. Quyết định và thay đổi (2026-11-18, nhánh `fix/review-panel`)

### Quyết định của chủ dự án

| Câu | Quyết định |
|---|---|
| Q1 bố cục | Kết luận trước, như đề xuất, **nhưng không có khối "đặt hàng" / "Copy for ordering"** |
| Q2 Tm vùng bám thấp | Thêm khuyến nghị, không đổi grade hay thuật toán |
| Q3 nồng độ mồi RT | Ghi trung lập: đặt hai nguồn cạnh nhau |
| Q4 loài "Other" | Ghi rõ là kiểm tra theo người, kèm cảnh báo |

### Thay đổi

Không thay đổi nào đổi mồi, điểm, thứ hạng hay grade:
- `ALGORITHM_VERSION` giữ 4.0.0;
- thứ tự frontend so với API vẫn 2472/2472 (`check_tier_order.mjs`: 0 mismatch);
- không file số liệu đã commit nào chứa các trường đã sửa.

**Backend**

| Mục | Thay đổi | File |
|---|---|---|
| C1 | Body không phải object, hoặc một nhóm tham số không phải object → 400 | `routes/design.py` |
| C2 | Overhang phải là số nguyên: 6,9 / 5,5 / `true` / Infinity → 400; 6,0 và "6" vẫn được nhận | `routes/design.py` |
| C3 | miRBase trả 5xx/429 → thử lại, rồi báo lỗi để chuyển sang RNAcentral và circuit breaker đếm được; 404 vẫn là "not found" | `routes/mirbase.py` |
| C4 | Đọc/ghi cache BLAST lỗi chỉ ghi log, không trả 500 | `routes/blast_check.py` |
| C5 | `predicted_amplicon_tm` sai định dạng → 422 `INVALID_REQUEST` | `routes/visualize.py` |
| A4 | `ranking_summary.screen_species` và `screen_species_assumed` (thêm vào OpenAPI) | `algorithm/tiered_pipeline.py`, `static/openapi.yaml` |
| A6 | `candidates_generated` / `candidates_rejected` đếm ứng viên khác nhau, không đếm theo lý do | `algorithm/design_pipeline.py` |
| A7 | Câu nồng độ: "RT primer: 1 nM final reduced non-specific products (Kramer 2011); Chen 2005 used 50 nM." Cùng ý cho Analyzer | `algorithm/stemloop_rt.py`, `routes/analyze.py` |

**Frontend: trang `/results`**

Thứ tự mới:
1. Banner: fallback, BLAST, loài giả định, ít bộ, gợi ý overhang.
2. Câu "#1 so với #2".
3. **Bảng so sánh** #1/#2/#3: grade, S/P/F, mồi xuôi, Tm vùng bám (tô màu khi < 39 °C), Tm, off-target gần nhất (`SetComparison.jsx`).
4. **Shared by all sets**: mồi RT và mồi reverse, chỉ một lần.
5. Thẻ từng bộ.
6. Các khối chi tiết.

Những gì đã cắt hoặc rút gọn:
- dòng RT và Reverse lặp lại trong từng thẻ;
- cảnh báo "3′ end is T" (bỏ hẳn);
- câu "scored 75/100" (chỉ còn ở bộ V4);
- thẻ "SYBR Green mode";
- Tm (full) của mồi RT và badge "approximate", chuyển vào mục "Overhang Tm and model notes"; ở dòng chính hiển thị overhang + ΔG37 DNA:RNA;
- dòng Fwd × Universal Rev, vốn trùng "Hetero-dimer" của Structure checks;
- đoạn isomiR rút còn một dòng có số liệu, kèm nút "Why".

Thêm mới:
- **A5:** ghi chú "Binding-region Tm X °C … Run the first 2–3 cycles at Ta ≈ 50 °C, or consider an LNA forward primer" trên thẻ của bộ dưới sàn 39 °C.
- **A4:** banner "Specificity screened against human (hsa) miRNAs …" khi `screen_species_assumed`.

Sửa:
- **A1:** bỏ câu "75/100" ở bộ tiered.
- **A2:** chip và bảng F4/F3 đọc `binding_tm.mode` và `specific_length.report_only`.
- **A3:** ★ không so các lần chạy khác thang S.
- Chip luật V4 dùng nhãn chữ thay cho mã (`gc_clamp_fail` → "No G/C in the last 3 nt"); chú thích "criterion levels L1–L5, L5 best".

**Kiểm tra**
- Backend: 930 passed, 3 skipped (thêm `tests/test_review_panel_fixes.py`, 19 test, và 3 test C5 trong `visualization/test_visualize_route.py`).
- E2E: 112/112, không retry. Test mới: thứ tự trang, các cảnh báo đã cắt, ghi chú Tm vùng bám, banner loài, ★ khác thang S. `rerun.spec` sửa cách chọn mồi RT.
- Build sạch.

**Chưa làm (ghi nhận):**
- Số ứng viên bị `_candidate_pool` cắt (20 mỗi độ dài) vẫn không được đếm trong metadata.
- `controls_advice` và `protocol_advice` có trong API, nhưng UI chỉ hiển thị qua PDF.

## 6. Bước 0: hit loài khác trong `identical_sequence` (2026-11-18, chỉ đọc)

**Kết luận: (a). Không đổi số liệu đóng băng, và cũng không phải lỗi hiển thị.** Tức là 0 trường hợp trong dữ liệu thật.

### Điều nghi ngờ

Trong `_classify_hits` (`blast_offtarget.py`), phép kiểm tra "giống hệt / lệch đầu" chạy **trước** bộ lọc loài.

### Vì sao không có hậu quả

`subject_seqs` (trình tự đầy đủ của hit) chỉ được lấy cho hit thuộc loài đang sàng lọc. Loài này là `ctx["screen_prefixes"]`: loài của thiết kế, cộng loài chủ trong `VIRUS_HOST_SPECIES` với miRNA virus. Điều này đúng ở cả 2 đường:
- đường gộp lúc thiết kế: `check_offtarget_batch`, khoảng dòng 835;
- đường "Show all hits": `_check_primer`, khoảng dòng 907.

Phép so "giống hệt" cần `subject_full`. Hit loài khác không có `subject_full`, nên luôn đi tiếp xuống `_same_species` và bị loại. Thứ tự trong code gây hiểu lầm, nhưng không đổi kết quả.

### `identical_sequence` được dùng ở đâu

- `identical_sequence_risk`: mục lệch đầu 5′ được tính HIGH; mục lệch đầu 3′ xét theo bước RT. Các mức này **nâng `overall_risk`** (`_assemble`).
- Từ `overall_risk`, chúng đi vào S1 (`blast_s1_inputs`, gồm cả số MEDIUM), rồi vào tổng S, khóa xếp hạng và grade.
- UI: OffTargetPanel. Export: phần BLAST của PDF.

Vì vậy, nếu có hit loài khác lọt vào danh sách này thì số liệu sẽ đổi. Thực tế không có.

### Số liệu

Cách đếm:
- Đọc chỉ-đọc `backend/data/blast_cache.sqlite`, các ngữ cảnh `design-clf7`, muối mặc định, RT 50 nt.
- Đối chiếu với pool của bản đóng băng (`outputs/freeze_cache/`).
- Script: scratchpad `step0_identical.py`, không commit.

| Phạm vi | Ứng viên đã BLAST | Có hit loài khác trong `identical_sequence` | S1 / `overall_risk` đổi | #1 / top 3 đổi |
|---|---|---|---|---|
| 2472 thiết kế hsa (4.0.0) | 215.860 | **0** | 0 | 0 |
| Các thiết kế khác trong cache (validation, benchmark: ssc, mmu, ebv, osa, ath, gga, bta, cel; 140 ngữ cảnh) | — | **0** | 0 | 0 |
| miRNA virus EBV, sàng lọc cùng loài chủ hsa | 3.067 | 0 hit loài khác; 0 mục hsa giống hệt | — | — |

Ghi chú về cách đếm:
- 1.920 ứng viên hsa không có trong cache. Cả 1.920 đều bị S2 loại trong một thiết kế không phải fallback, nên API không BLAST chúng; điều này đúng thiết kế (SPEC §5).
- Với 2.630 ngữ cảnh thiết kế, giá trị trong cache trùng file BLAST đầy đủ của Giai đoạn 2. Lần đếm đầu từng có 19 ứng viên hsa-miR-23b-3p lệch, nhưng đó là do script gộp ngữ cảnh 21 nt của validation với ngữ cảnh 23 nt của miRBase 22.1. Khi thêm trình tự đích vào khóa thì hết lệch.

### Hệ quả cho "cách 2" (loại hit khác loài ngay khi đọc output BLAST)

Kết quả rủi ro và `identical_sequence` sẽ giữ nguyên.

Riêng `summary.cross_species_excluded` (chỉ hiển thị) có thể đổi. Lý do: hiện nay một hit loài khác có tên trùng tên đích theo `_is_self_hit` bị bỏ qua mà không được đếm vào trường này. Nếu loại hit khác loài trước, nó sẽ được đếm. Muốn output trùng byte thì phải giữ nguyên cách đếm này.

**Đã làm (chủ dự án duyệt):**
- Thêm comment trong `_classify_hits` giải thích vì sao phép so "giống hệt" chỉ gặp hit cùng loài.
- Thêm test `test_identical_is_same_species_only` (`tests/test_blast_rt_step.py`), chạy cả đường gộp lẫn đường từng mồi. Hàm fetch giả trả trình tự cho **mọi** id được hỏi, nên nếu sau này code lấy trình tự của loài khác thì test sẽ fail.
- Không đổi output.

## 7. Bước 1: đo lại mốc thời gian (2026-11-18)

Giao thức giống `benchmark/tiered_design_timing.json`:
- 20 miRNA hsa, thứ tự random.Random(2026), cùng 20 miRNA và cùng 1 ca bị bỏ qua như mốc;
- chạy `design_pipeline.run` trong cùng tiến trình, tắt cache BLAST, 1 thiết kế khởi động không tính.

Kết quả ghi ra scratchpad, **không ghi đè** file benchmark đã commit. Trước khi đo đã tắt Vite, Flask, Playwright; không còn tiến trình node hay python nào.

Đã đo 2 lần:

| | Mốc (QĐ 24c) | **Cắm sạc (dùng số này)** | Chạy pin (bỏ) |
|---|---|---|---|
| Tổng, p50 / p90 | 9,78 / 11,89 s | **9,59 / 11,56 s** | 14,84 / 20,63 s |
| BLAST, p50 / p90 | 8,07 / 10,04 s | **7,88 / 9,89 s** | 12,19 / 17,77 s |
| Tổng, nhanh nhất / chậm nhất | 4,93 / 13,38 s | 4,88 / 13,09 s | 7,09 / 28,66 s |
| mmu-miR-1a-3p | — | **10,16 s** (BLAST 8,53 s) | 16,35 s |
| Trình tự tự nhập, loài "Other" | — | **7,55 s** (BLAST 6,11 s) | 11,84 s |

- **Lần cắm sạc:** CPU rảnh (tải 0–8 %), xung nhịp khoảng 107 % danh định, chế độ nguồn Balanced.
- **Lần chạy pin:** pin đang xả, còn 46 %, CPU 1,8 GHz, tải khoảng 60 %.

**Kết luận:**
- Máy cắm sạc tái lập đúng mốc (chênh ≤ 3 %).
- BLAST chiếm khoảng 82 % thời gian thiết kế khi không có cache.
- Chạy bằng pin làm chậm khoảng 1,5 lần. Từ nay mọi phép đo trước/sau phải cắm sạc.

## 8. Bước 2: ghi nhớ ΔCq của bộ lọc assay (2026-11-20, nhánh `perf/design-speed`)

**Thay đổi** (commit `8df6d8f`, không đổi `ALGORITHM_VERSION`, không đổi khóa cache BLAST):
- `overhang_collision.py`: `functools.lru_cache` (tối đa 65 536 mục mỗi bảng) cho Tm duplex và ΔCq forward chỉ-theo-bảng của `assay_screen`. Đây là hàm thuần, nên trả đúng cùng số float.
- Công cụ kiểm tra:
  - `BLAST_CACHE_PATH` (chỉ đổi file cache);
  - `freeze_pipeline.py --blast-cache --log-prefix`;
  - `backend/scripts/design_equivalence.py`;
  - danh sách 200 hsa cố định `benchmark/logs/design_equivalence_hsa200.txt` (random.Random(2026)).

Tiền đề ban đầu sai một phần: lần gọi `assay_screen` thứ hai là cho các overhang **khác** (5/7 nt), không phải tính lại overhang hiện tại.

### Kiểm tra tương đương (đều đạt)

| Kiểm tra | Kết quả |
|---|---|
| 200 hsa, cache BLAST trống: code mới so với code đóng băng (bỏ thời gian và đếm cache) | **0/200 bản ghi khác** |
| 200 hsa: #1 (forward, RT, total_score, grade) so với bản ghi đóng băng | **0/200 khác** |
| 2656 hsa thiết kế lại từ đầu (cache BLAST như trước) so với `freeze_matrix_4.0.0` | **0/2656 bản ghi khác** |
| Ma trận dựng lại so với `outputs/crossreactivity_*` đã commit | Parquet trùng từng byte; CSV trùng sau khi bỏ CRLF; metadata chỉ khác ngày, commit, số giây; diagonal check đạt |
| Validation 201 mục, cache BLAST trống, qua `freeze_pipeline` @ `8df6d8f` (cây sạch) | **2439/2439**; `git diff` chỉ khác `run_date` và số đếm cache, đã trả về bản commit |
| Test backend | 936 passed, 3 skipped |

### Thời gian (cắm sạc, giao thức Bước 1)

| | Trước (Bước 1) | Sau |
|---|---|---|
| Tổng, p50 / p90 | 9,59 / 11,56 s | 9,68 / 12,19 s |
| BLAST, p50 / p90 | 7,88 / 9,89 s | 7,88 / 10,14 s |
| Phần ngoài BLAST, trung vị | 1,67 s | 1,73 s |
| mmu-miR-1a-3p | 10,16 s | 10,45 s |
| Trình tự tự nhập | 7,55 s | 8,01 s |
| 2656 hsa có cache, 8 worker (`design_all`) | 847 s (lượt đóng băng) | 825 s (−2,6 %) |
| Thiết kế lại **cùng** miRNA trong cùng tiến trình (Re-run) | 2,14 s | 1,47 s |

Tỉ lệ trúng bộ nhớ đệm trong một thiết kế mới:

| | Trúng | Tổng số lần gọi |
|---|---|---|
| Tm duplex | 547 | 3 878 |
| ΔCq forward | 2 775 | 15 930 |

**Kết luận:**
- **Thiết kế mới:** Bước 2 không làm nhanh hơn đo được; chênh lệch nằm trong nhiễu đo. Số −0,41 s/thiết kế ở thử nghiệm trước là do đo lại cùng miRNA, khi bộ nhớ đệm đã đầy.
- **Re-run cùng miRNA:** nhanh hơn khoảng 0,7 s.
- **Ma trận:** nhanh hơn khoảng 2,6 %.
- **Hướng tiếp theo:** BLAST vẫn chiếm khoảng 82 % thời gian, nên muốn nhanh hơn thật phải nhắm vào BLAST và phân loại hit (Bước 3).

## 9. Bước 3: phân loại hit song song bằng tiến trình (2026-11-20, nhánh `perf/parallel-classify`)

Đo trước khi sửa (cache tắt, 3 miRNA hsa), thời gian bước BLAST khoảng 9 s chia ra:
- `_classify_hits`: 4,0–4,7 s;
- `blastn`: 3,2–3,6 s;
- `blastdbcmd`: 0,5–1,1 s.

**Thay đổi** (commit `cb2c2f8`, không đổi `ALGORITHM_VERSION`, không đổi khóa cache BLAST):
- `check_offtarget_batch`:
  - mỗi cặp (mồi, DB) là một tác vụ `_classify_hits` (vẫn là hàm đó);
  - tác vụ chạy trong `ProcessPoolExecutor`;
  - kết quả gộp theo thứ tự đầu vào (`map`);
  - mỗi tác vụ chỉ nhận trình tự subject của chính các hit của nó.
- **Pool:**
  - tạo một lần khi cần lần đầu và sống suốt lượt chạy (tiến trình Flask hoặc script);
  - trong worker, primer3 vẫn đi qua `primer3_safe`.
- **Hằng số:**
  - `BLAST_CLASSIFY_PROCESSES = 12` (env `BLAST_CLASSIFY_PROCESSES` ghi đè, tối đa bằng số CPU);
  - `BLAST_CLASSIFY_MIN_PRIMERS = 16`.
  - Đã đo 12, 14 và 16 tiến trình: 12 và 14 nhanh ngang nhau, 16 chậm hơn.
- **Chạy tuần tự khi:**
  - batch có dưới 16 mồi;
  - đang ở trong worker của pool khác (`crossreactivity.design_all`), để pool không lồng nhau;
  - pool không khởi động được hoặc bị hỏng. Khi đó pool bị bỏ và batch được phân loại tuần tự, cho cùng kết quả.
- **Test:** `backend/tests/test_design_speed.py` có thêm 5 test:
  - pool cho kết quả trùng tuần tự (BLAST giả và BLAST thật), đúng thứ tự, một pool cho cả lượt chạy;
  - batch nhỏ không tạo pool;
  - không lồng pool;
  - pool hỏng thì chạy tuần tự.
- **Script:** mọi script trong repo chạy thiết kế trong tiến trình đều có `if __name__ == "__main__"`. Điều này cần trên Windows, vì worker được tạo kiểu spawn sẽ nạp lại script chính.

### Kiểm tra tương đương (đều đạt)

| Kiểm tra | Kết quả |
|---|---|
| 200 hsa, cache BLAST trống, so với bản tham chiếu của Bước 2 (code master) | **0/200 bản ghi khác**; #1 so với bản đóng băng 0/200 khác |
| 2656 hsa thiết kế lại từ đầu (cache như trước) | **0/2656 bản ghi khác**; Parquet trùng từng byte, CSV trùng sau khi bỏ CRLF, metadata chỉ khác ngày, commit, số giây |
| Validation 201 mục, cache trống, `freeze_pipeline` @ `cb2c2f8` (cây sạch) | **2439/2439**; `git diff` chỉ khác `run_date` và số đếm cache, đã trả về bản commit |
| Top 3 của 20 miRNA trong phép đo thời gian | trùng Bước 1 |
| Test | backend 941 passed, 3 skipped; crossreactivity 29 |

Với 2656 hsa có cache, bước phân loại không chạy (kết quả lấy từ cache), và `design_all` chạy trong worker nên không dùng pool. Pool được kiểm bằng lượt 200 hsa và lượt validation, cả hai đều với cache trống.

### Thời gian (cắm sạc, giao thức Bước 1)

| | Trước (Bước 1) | Sau |
|---|---|---|
| Tổng, p50 / p90 | 9,59 / 11,56 s | **7,53 / 8,39 s** (−21 % / −27 %) |
| BLAST (blastn + phân loại), p50 / p90 | 7,88 / 9,89 s | **5,30 / 6,20 s** |
| Phần ngoài BLAST, trung vị | 1,67 s | 2,13 s |
| mmu-miR-1a-3p | 10,16 s | 7,86 s |
| Trình tự tự nhập | 7,55 s | 6,08 s |
| Thiết kế đầu tiên của tiến trình (gồm khởi động pool) | — | 7,77 s (lần sau 7,29 s) |
| 200 hsa, cache trống, tuần tự | 1692 s | 1206 s |
| Validation 201 mục, cache trống | 2172 s | 1785 s |

**Kết luận:**
- **Tốc độ:** thiết kế mới nhanh hơn khoảng 2 s (p50) và khoảng 3 s (p90), kết quả trùng từng byte.
- **Khởi động pool:** tốn dưới 0,5 s, chỉ ở thiết kế đầu tiên.
- **Phần ngoài BLAST:** tăng khoảng 0,45 s dù code phần này không đổi. Giả thuyết là CPU hạ xung sau đợt chạy 12 tiến trình; chưa tách được nguyên nhân.
- **Phần còn lại:** blastn khoảng 3,5 s. Cách 2 vẫn chờ chủ dự án quyết định.

## 10. Kế hoạch tăng tốc 2, Bước 1: đo theo giai đoạn (2026-11-21, chỉ đọc, nhánh `perf/design-speed`)

Cách 2 đã bỏ (chủ dự án, 2026-11-21). Bước này không sửa code.

**Giao thức:** giống Bước 1, đo sau Bước 3.
- 20 hsa, seed 2026, không cache BLAST, 1 lượt khởi động; thêm mmu-miR-1a-3p và 1 trình tự tự nhập.
- Máy cắm sạc, không còn tiến trình python/blastn nào khác.
- Mỗi giai đoạn được đo bằng cách bọc các hàm của module, tính thời gian riêng của từng hàm (không cộng phần hàm con đã bọc).
- Phần hit loài khác được tách bằng cách chạy lại `_classify_hits` trong tiến trình chính, sau mỗi thiết kế.
- Script nằm ở scratchpad, không commit: `speed_stages.py`, `blastn_probe.py`.

### Phát hiện: BLAST+ gửi báo cáo sử dụng về NCBI ở mỗi lần gọi

BLAST+ 2.17 mặc định gửi một báo cáo sử dụng lên NCBI mỗi khi blastn hay blastdbcmd chạy. Trong repo chưa đặt `BLAST_USAGE_REPORT`, nên chức năng này đang bật.

- **Lượt bình thường:** mỗi lần gọi tốn thêm khoảng 1 s.
- **Mạng chậm:** một tiến trình bị treo thêm khoảng 30–35 s.
  - Hôm nay có 11 trên 20 thiết kế hsa bị treo, nên p50 là 38 s.
  - Thử blastn riêng 6 lượt (20 mồi, 8 tiến trình): 2 lượt mất 36 s, 4 lượt mất 1,6 s.
- **Với `BLAST_USAGE_REPORT=false`** (chỉ đặt cho tiến trình đo):
  - blastn còn 0,5 s mỗi lượt, 10 trên 10 lượt không treo;
  - blastdbcmd còn 0,02 s, so với khoảng 1 s trước đó.
- **Kết quả không đổi:** top 3 của cả 22 thiết kế trùng nhau khi bật hay tắt báo cáo, và trùng Bước 1.
- **Hệ quả cho số đo cũ:** các số đo Bước 1–3 đều gồm phần gọi mạng này, khoảng 2 s mỗi thiết kế.

### Thời gian theo giai đoạn, p50 trên 20 hsa (giây)

| Giai đoạn | Hiện trạng (báo cáo bật) | `BLAST_USAGE_REPORT=false` |
|---|---|---|
| Sinh ứng viên forward | 0,16 | 0,14 |
| Kiểm tra cấu trúc (mồi, heterodimer, template) | 0,64 | 0,62 |
| ΔCq + biên Tm (S2/S3, `assay_screen`) | 0,90 | 0,81 |
| Điểm phụ V4 | 0,05 | 0,05 |
| blastn | 19,3 (2,9 ở 9 thiết kế không treo) | **2,11** |
| Phân loại hit (pool, thời gian thực) | 0,73 | 0,70 |
| — trong đó hit loài khác (ước tính) | 0,08 | 0,08 |
| blastdbcmd | 1,00 (34 s ở 3 thiết kế) | 0,04 |
| BLAST khác (Tm_on, ghép task, gộp kết quả) | 0,41 | 0,40 |
| ΔCq báo cáo cấp thiết kế (sau xếp hạng) | 0,11 | 0,09 |
| Phần còn lại | 0,02 | 0,01 |
| **Tổng** p50 / p90 | 38,0 / 43,1 (7,0 ở thiết kế không treo) | **5,01 / 6,25** |
| mmu-miR-1a-3p / trình tự tự nhập | 40,8 / 40,2 | 5,9 / 4,9 |

Ghi chú về phân loại hit:
- **Hit thô:** trung vị 8.537 hit cùng loài và 131.545 hit loài khác mỗi thiết kế.
- **Thời gian CPU nếu chạy tuần tự:** tổng 4,08 s; hit cùng loài 3,55 s; hit loài khác 0,44 s (11 %).
- **Dữ liệu gửi sang pool:** khoảng 15,9 MB pickle mỗi thiết kế, trong đó chỉ 1,2 MB là hit cùng loài.
- **S2 không loại ứng viên nào** trong 20 thiết kế (0/1875), nên mọi ứng viên đều được BLAST.

### Phụ thuộc giữa các giai đoạn (đọc code)

**ΔCq và cấu trúc không dùng kết quả BLAST.**
- Kiểm tra cấu trúc chạy ở `design_pipeline.py:162-176`, trước khi xếp hạng (`:212`).
- `assay_screen` (S2 + biên Tm S3) chạy ở `tiered_pipeline.py:187`; điểm phụ V4 ở `:191-193`. Cả hai chạy trước BLAST (`:202`).
- Các module `structure_check/*`, `template_structure.py`, `overhang_collision.py` và `assay_model.py` không import `blast_offtarget`.
- `family_crossreactivity.py:59` chỉ mượn hàm tách tiền tố loài.

**Chiều phụ thuộc ngược lại có tồn tại:** S2 quyết định mồi nào được BLAST.
- `tiered_pipeline.py:200-201`: `s2_kept`.
- Nhánh fallback ở `:206-214` BLAST thêm phần còn lại.
- Sau xếp hạng, `overhang_suggestion` (`:267`) và `check_overhang_collision` (`design_pipeline.py:220`) dùng độ dài của bộ #1, tức là gián tiếp phụ thuộc BLAST.

**Hit thô của blastn không phụ thuộc điều kiện phản ứng.**
- Dòng lệnh `_blastn_cmd` (`blast_offtarget.py:433-446`) chỉ gồm tên DB và các hằng số:
  - `blastn-short`, word size 7, e-value 30000, max_target_seqs 50000, reward 1 / penalty −1.
- `run_blastn_multi` (`:470`) chỉ nhận mồi, DB, timeout và số tiến trình. Cách chia mồi cho các tiến trình không đổi hit (`benchmark/blast_batch_equivalence.json`).
- Điều kiện phản ứng (`mv_conc`, `dv_conc`, `dntp_conc`, `dna_conc`) chỉ vào `_tm_on` (`:660`) và cổng Tm trong `_classify_hits`.
- Ta không dùng ở đâu trong BLAST: ngưỡng neo 3′ là hằng số `PRIMER_BLAST_MIN_3PRIME_ANCHOR` = 10.
- Danh sách id gửi cho blastdbcmd chỉ phụ thuộc loài sàng lọc.

**Khóa cache BLAST hiện tại** (`blast_cache.py:127-135`):
- Công thức: `sha256(FWD | REV | db_version | mirna_id.lower() | context)[:32]`.
- `db_version` là `build_date` trong metadata của DB (`tiered_pipeline.py:96`), không phải sha của DB.
- `context` (`tiered_pipeline.py:112`) = `design-clf7` | trình tự đích (DNA) | mã loài | trình tự mồi RT | `dna_conc` | `dntp_conc` | `dv_conc` | `mv_conc`.
- Giá trị lưu là kết quả đã phân loại, không phải hit thô. TTL 30 ngày.
- Không có trong khóa: các tham số blastn (chỉ gián tiếp qua phiên bản bộ phân loại), phiên bản BLAST+, và Ta (đúng, vì không dùng).

## 11. Kế hoạch tăng tốc 2, Bước 2: tắt báo cáo sử dụng của BLAST+ (2026-11-21, nhánh `perf/design-speed`)

**Thay đổi:**
- `blast_offtarget.blast_subprocess_env()` tạo env cho mọi tiến trình con BLAST+ của engine (`run_blastn`, `run_blastn_multi`, `fetch_sequences`). Hàm đặt `BLAST_USAGE_REPORT=false` bằng `setdefault`, nên giá trị người dùng đã tự đặt được giữ nguyên.
- `BLASTDB` và tên DB trả về y như cũ.
- `build_blast_db.py` (makeblastdb, `blastdbcmd -info`, `makeblastdb -version`) và `freeze_pipeline.py` (`blastn -version`) đặt cùng biến.
- Không còn lệnh gọi BLAST+ nào khác trong `backend/`, `crossreactivity/`, `validation/`, `benchmark/`.
- Không đổi `ALGORITHM_VERSION` hay khóa cache BLAST.
- Test mới: `tests/test_blast_usage_report.py` (7 test).

### Kiểm tra tương đương (bộ rút gọn)

Bộ kiểm được rút gọn vì bước này chỉ đổi biến môi trường của tiến trình con, không đổi tham số blastn hay code phân loại.

| Kiểm tra | Kết quả |
|---|---|
| 200 hsa (cùng danh sách seed Bước 2/3), cache BLAST trống | 186/200 khác bản tham chiếu Bước 2, **chỉ ở `specificity_warnings.data_note`**: chữ "7 entries" → "8 entries" của PR #22, gộp sau khi tạo tham chiếu. Thay đúng chuỗi đó trong tham chiếu (186 chỗ) thì **0/200 khác**; bộ #1 trùng bản đóng băng 200/200 |
| Validation 201 mục, cache trống, qua `freeze_pipeline` | **2439/2439**; diff chỉ khác ngày chạy và thống kê cache (đã trả lại file) |
| 2656 hsa có cache | Không chạy lại. Đường thiết kế chỉ gọi BLAST ở `tiered_pipeline.py:147-149` (`... if missing else {}`), nên khi mọi mồi đã có trong cache thì không có blastn hay blastdbcmd nào chạy. `blast_available()` chỉ gọi `shutil.which` |
| Test | backend **948 passed**, 3 skipped (941 + 7) |

### Thời gian

Giao thức QĐ 24c: cắm sạc, không có Vite, Playwright hay python/blastn thừa. 20 hsa seed 2026 không cache, cộng mmu-miR-1a-3p và 1 trình tự tự nhập. Hai lượt đo bắt đầu lúc 12:43 và 13:27.

| | Trước: Bước 3, số đo ngày 20/11 | Trước: hôm nay, báo cáo bật (§10) | Sau, lượt 1 | Sau, lượt 2 |
|---|---|---|---|---|
| Tổng p50 / p90 (s) | 7,53 / 8,39 | 38,0 / 43,5 | **5,02 / 6,21** | **5,10 / 6,29** |
| blastn p50 / p90 (s) | — | 19,3 / 37,9 | 2,02 / 2,65 | 2,13 / 2,72 |
| blastdbcmd p50 / p90 (s) | — | 1,00 / 5,26 | 0,038 / 0,050 | 0,040 / 0,046 |
| Thiết kế treo > 20 s | — | 11/20 | **0/20** | **0/20** |
| mmu-miR-1a-3p / tự nhập (s) | 7,86 / 6,08 | 40,8 / 40,2 | 5,51 / 4,18 | 5,45 / 4,00 |
| 200 hsa cache trống, tuần tự | 1206 s | — | 857 s | — |
| Validation 201 mục cache trống | 1785 s | — | 1490 s | — |

- Top 3 của 20 thiết kế đo thời gian trùng Bước 1 ở cả hai lượt.
- Số thời gian trong `docs/THESIS_FREEZE_4.0.0.md` không sửa.

### Bằng chứng cho bản tham chiếu đã sửa (200 hsa)

Phép so: bản tham chiếu **gốc** (tạo ngày 2026-11-19, trước PR #22, chưa thay chuỗi) với output Bước 2, so từng trường, cả trạng thái của bản ghi.

| Trường | Số bản ghi khác | Chuỗi cũ → mới |
|---|---|---|
| `specificity_warnings.data_note` | 186 / 200 | "isoMiR data: curated from literature (**7** entries, partial coverage)" → "(**8** entries, partial coverage)" |

- Không có trường nào khác bị lệch, không có giá trị không phải chuỗi bị lệch, và chỉ có đúng 1 cặp chuỗi cũ → mới.
- 14 bản ghi còn lại là thiết kế trả lỗi, không có `data_note`.
- Bản tham chiếu đã sửa được commit tại `benchmark/logs/design_equivalence_ref_hsa200.jsonl`; dòng ghi nguồn gốc nằm ở `design_equivalence_ref_hsa200.md`.
  - Bản này được tạo bằng cách thay đúng chuỗi trên ở 186 chỗ, ghi ở chế độ nhị phân để giữ LF.
  - Nó **trùng từng byte** với output Bước 2.

### E2E

`npx playwright test`, chạy với cả hai dev server và máy cắm sạc: **109/109 passed** trong 1,7 phút, không có lần thử lại.
- `global-setup` làm nóng cache: miR-21-5p 2,0 s, let-7a-5p 1,9 s, miR-590-3p 1,0 s.
- Khi tắt server thì thấy 12 worker của pool phân loại (Bước 3) còn sống sau khi tiến trình Flask bị dừng cưỡng bức, và mình đã tắt tay.
  - Lúc tắt bình thường (Ctrl+C) thì pool được đóng.
  - Đây chỉ là chuyện dọn dẹp tiến trình; output không bị ảnh hưởng.

### Provenance

`freeze_pipeline.provenance()` ghi thêm `env_BLAST_USAGE_REPORT`: giá trị mà `blast_subprocess_env()` trả về, tức "false" trừ khi người dùng tự đặt. Có test tương ứng trong `tests/test_blast_usage_report.py` (thêm 2 test, tổng 9).

### Đóng kế hoạch

**Kế hoạch tăng tốc 2 đóng ngày 2026-11-21; Bước 3–5 không làm vì lợi ≤ 1,4 s, không đáng rủi ro sau tag.**

## 12. Worker của pool phân loại bị mồ côi (2026-11-21, nhánh `fix/pool-orphan-workers`)

**Lỗi:** tiến trình sở hữu pool phân loại (Flask, hoặc một script) bị dừng cưỡng bức thì một phần worker vẫn chạy mãi.
- Khi tắt server sau lượt E2E ở §11 còn 12 worker.
- Khi dựng lại với pool 3 worker thì còn 1/3 sau 15 s.

**Nguyên nhân:** mỗi worker chờ trên hàng đợi lệnh của pool, mà chính nó cũng giữ mở pipe của hàng đợi đó. Vì vậy khi tiến trình cha chết, worker không nhận được EOF. Tắt bình thường (Ctrl+C, `shutdown`) thì không gặp lỗi này.

**Sửa:**
- Initializer của pool là `_exit_with_parent` (`blast_offtarget.py`). Nó khởi một luồng daemon chờ `multiprocessing.parent_process()` kết thúc rồi gọi `os._exit(0)`.
- Không đổi phần tính toán, `ALGORITHM_VERSION` hay khóa cache BLAST.

**Kiểm tra:**

| | Kết quả |
|---|---|
| Dựng lại lỗi, pool 3 worker, kill tiến trình sở hữu | trước: 1/3 worker còn sống sau 15 s; sau: 0/3 sau 1 s (3 lần) |
| Flask thật, cache tắt, 1 thiết kế rồi dừng cưỡng bức | 13 tiến trình con; 0/13 còn sống sau 3 s; cổng 5000 trống |
| Test mới `test_workers_exit_when_owner_is_killed` | fail khi chưa sửa (1 worker còn sống), pass khi đã sửa |
| 200 hsa, cache BLAST trống, đi qua pool | **trùng từng byte** với `benchmark/logs/design_equivalence_ref_hsa200.jsonl`; bộ #1 trùng bản đóng băng 200/200 (887 s) |
| Test backend | 951 passed, 3 skipped |

### Các script offline dùng `mp.Pool` khi bị kill (2026-11-21, chỉ đọc)

**Kết luận: không sửa.** Sau khi tiến trình cha bị kill, worker làm nốt phần việc đang nhận rồi tự thoát. Kết quả chúng ghi ra trong lúc đó đều đúng.

Cách thử:
- Script `kill_check.py` (trong scratchpad, không commit) dừng tiến trình cha bằng TerminateProcess khi các worker đã chạy.
- Mọi cache và output đều trỏ vào thư mục trống trong scratchpad.

| Phép thử | Worker còn sống | Sau khi kill, worker còn làm gì |
|---|---|---|
| `mp.Pool` tối thiểu, việc 0,5 s (2 lần) | 0/4 sau 1 s | — |
| `design_all`, 4 worker, cache trống (3 lần) | 4/4 sau 60 s, 0/4 trước mốc 120 s | Chạy hết chunk đang có (`chunksize=4`) và ghi 1460 mục vào cache BLAST trong 1–2 phút sau khi kill |
| `build_matrix`, 4 worker, bản sao cache đóng băng đã xóa block | 2/4 sau 5 s, 0/4 sau 15 s | Ghi xong 4 block, không còn `.part`; cả 4 trùng từng byte với block của bản đóng băng |

**Vì sao khác `ProcessPoolExecutor` (phần trên của §12):**
- Worker `ProcessPoolExecutor` đang rảnh thì chờ mãi trên hàng đợi lệnh.
- Worker `mp.Pool` chỉ phát hiện tiến trình cha đã mất khi gửi kết quả về. Vì vậy nó sống thêm đúng bằng thời gian làm nốt phần việc đang có:
  - `design_all`, `scoring_weight_sensitivity`, `ui_top3_dump`: 4 thiết kế mỗi chunk;
  - `thesis_freeze_impact`, `tiered_scoring_dryrun` (phần thiết kế): 2;
  - `build_matrix`, `blast_batch_equivalence`, `tiered_stage2_report`: 1.
- Chỉ đo thật `design_all` và `build_matrix`; thời gian của các script còn lại được suy từ chunksize.

**Kết quả không bị ảnh hưởng:**
- **Cache BLAST:** mục do worker mồ côi ghi là kết quả đúng. Cache dùng WAL và chờ khóa 60 s, vốn dành cho nhiều tiến trình cùng ghi.
- **Block ma trận:** được ghi vào `.part` rồi mới `os.replace`, nên lần chạy sau không đọc phải block dở dang.
- **Thiết kế của chunk bị kill:** không vào `designs_<species>.jsonl` (file này do tiến trình cha ghi). Lần chạy sau sẽ thiết kế lại các miRNA đó.

**Hậu quả còn lại:** nếu chạy lại ngay sau khi kill thì trong khoảng 1–2 phút đầu sẽ tốn thêm CPU. Không thêm cơ chế thoát theo tiến trình cha cho các script này: nó sẽ dừng worker giữa lúc đang ghi cache, đổi một phiền toái nhỏ lấy rủi ro mới cho các script dùng để sinh số liệu khóa luận.
