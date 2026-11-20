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
