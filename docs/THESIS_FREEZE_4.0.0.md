# Bản đóng băng thuật toán 4.0.0 cho khóa luận

Ngày đóng băng: 2026-11-18. Tag `thesis-freeze-4.0.0`, trên merge commit của nhánh `freeze/4.0.0` vào `master`. Lấy hash bằng `git rev-list -n 1 thesis-freeze-4.0.0`.

**Mọi số liệu in silico trong khóa luận lấy từ phiên bản này.** Sau tag chỉ được sửa lỗi không đổi output. Nếu cần đổi output thì phải tăng `ALGORITHM_VERSION` và đóng băng lại (PROMPT, phần Bối cảnh).

## 1. Phiên bản và cấu hình

| Thành phần | Giá trị |
|---|---|
| Algorithm | **4.0.0** (`backend/algorithm/constants.py`) |
| Hệ chấm điểm mặc định | `tiered`: phân tầng, ưu tiên đặc hiệu (`docs/SPEC_scoring_tiered_4.0.0.md`, QĐ 1–41). V4 3.8.2 vẫn chạy được qua `scoringSystem: "v4"` và cho kết quả trùng 3.8.2. |
| Cờ tiered | `TIERED_F4_FLOOR`, `TIERED_GRADE_BY_TIERS`, `TIERED_V4_COMPLIANT_FIRST`, `TIERED_BINDING_FLOOR_VETO`: đều bật |
| Dấu vân tay ngưỡng / trọng số | `tiered_thresholds_sha256` 4f9b87786af5 · `scoring_weights_sha256` (V4) 1fe2b60ada11 |
| Python · primer3-py · ViennaRNA | 3.12.8 · 2.0.3 · 2.7.2 |
| BLAST+ | blastn 2.17.0+; DB `mirbase_multi` (48.885 trình tự trưởng thành, dựng ngày 2026-07-01 bằng makeblastdb 2.17.0+) |
| miRBase | **Release 22.1**. `mature.fa` sha256 `3c521fc9bea3c7993e71cf188b11caf73e2d40ac83454e32876455317cc6d342`, dùng chung cho BLAST DB, chỉ mục overhang và tra cứu cục bộ. Route `/api/mirbase` trả bản cục bộ này; nếu tra online thì có nhãn "release unknown". |
| Dấu vân tay các file BLAST DB | sha256 `e31aee0368c57f385995cb137e6d843edefa7af847a05bdf2ab8cca17eb19aa4`: băm tên + sha256 từng file `mirbase_multi.*`, theo `freeze_pipeline.py`. Cách băm khác provenance của Giai đoạn 3, nên hai giá trị không so trực tiếp được. |
| Máy chạy | Windows 11, 16 luồng CPU; BLAST gộp chạy 8 tiến trình |

Mỗi kết quả thiết kế đều mang khối `metadata.provenance` gồm phiên bản engine, hai dấu vân tay, release và sha256 của miRBase. File xuất MIQE (PDF/CSV) in lại các thông tin này.

## 2. Tái lập: một lượt chạy toàn bộ pipeline (PROMPT 4.1)

Lượt chạy dùng `backend/scripts/freeze_pipeline.py` ở commit `dee9352` trên nhánh `freeze/4.0.0`. Lúc bắt đầu working tree sạch; Flask chạy không có auto-reloader. Provenance và thời gian từng bước ghi ở `benchmark/logs/freeze_run.json`.

| Bước | Lệnh | Kết quả so với bản đã commit |
|---|---|---|
| Validation (tiered) | `validation/validate_primers.py` | **2439/2439**. `results.json` và `results.csv` trùng hoàn toàn. |
| Báo cáo + khối validation của benchmark | `build_validation_report.py`, `build_benchmark_validation.py --in-place` | trùng |
| Hồi quy V4 | `validate_primers.py --scoring-system v4` | 2439/2439, trùng 3.8.2: `results.json` giống hệt khi bỏ `run_date`; `results.csv` cùng blob git `a41790c` |
| Benchmark 50 miRNA | `benchmark/run_benchmark.py` | 50/50, `compare_tools.md` trùng |
| So với mồi đã công bố | `export_benchmark_primers.py` | 223/224 thiết kế được, 193 có mồi công bố; file xuất trùng |
| Độ nhạy cổng Tm của BLAST | `blast_tm_gate_sensitivity.py` | trùng |
| Ma trận phản ứng chéo hsa | `crossreactivity.design_all` + `build_matrix`, dựng **từ đầu** vào `outputs/freeze_matrix/` | 2472/2656 thiết kế; 2656/2656 bản ghi thiết kế trùng `designs_hsa.jsonl` đã commit (bỏ qua thời gian, bộ đếm cache); `crossreactivity_long.csv`, `row_stats`, `top30_offdiagonal`, `failed_designs` trùng hoàn toàn; metadata chỉ khác ngày chạy, thời gian, git commit. `plots` + `validate` chạy lại trên ma trận đã commit: báo cáo trùng; hình SVG chỉ khác ngày và id ngẫu nhiên của matplotlib (giữ bản cũ) |

- Cache BLAST: mọi lượt có BLAST đều đạt cache hit 100 % (ví dụ validation hsa 5840/5840; `benchmark/logs/*_blast_stats.json`). Không có lần ghi cache nào thất bại.
- Kiểm thử ở cùng commit:
  - backend `tests` + `visualization`: 908 passed, 3 skipped;
  - e2e Playwright: 109/109, không retry;
  - `crossreactivity/tests`: 29 passed;
  - `npm run build`: không có cảnh báo.
- Lượt chạy có hai lỗi, cả hai thuộc script chứ không thuộc dữ liệu:
  - `crossreactivity.validate` thoát với mã 1 vì in ký tự "≥" ra stdout mã cp1252 của Windows. Chạy lại với `PYTHONIOENCODING=utf-8` thì exit 0; script nay đặt biến này cho mọi bước.
  - Lượt V4 ghi đè file thống kê, xem ngay dưới.
- Lượt V4 (không BLAST) ghi đè `benchmark/logs/validation_blast_stats.json` của lượt tiered. File đã được khôi phục từ log của lượt tiered và trùng bản đã commit. Script đã sửa để giữ file này.

## 3. Số liệu chính (4.0.0, so với mốc V4 3.8.2)

Mẫu số: 2656 miRNA hsa (miRBase 22.1). V4 có mồi cho 2253; hệ tiered có mồi cho **2472** (184 không có ứng viên). Chi tiết ở `docs/SCORING_TIERED_COMPARISON.md`.

| Số liệu | 4.0.0 (tiered) | 3.8.2 (V4) | Nguồn |
|---|---|---|---|
| Validation in silico (201 mục: 193 miRNA + 4 edge case + 4 mục tham chiếu) | **2439/2439**. 3 giới hạn V4 được chấm bằng `v4_limitation_designed` (QĐ 38). | 2439/2439 | `validation/results.json`, `VALIDATION_REPORT.md` |
| Benchmark 50 miRNA | 50/50 | 50/50 | `benchmark/compare_tools.md` |
| So với mồi đã công bố | 223/224 thiết kế được, 193 có mồi công bố | 220/224 | `benchmark/primer_benchmark_export.*` |
| Độ phủ hsa | **2472/2656** | 2253/2656 | `outputs/crossreactivity_metadata.json` |
| #1 có S1 ≤ 2 (BLAST HIGH/CRITICAL, cùng classifier; trên 2253) | 55 | 85 | `benchmark/tiered_stage2c_report.json` |
| #1 có S2 = 1 (CO-AMPLIFIED) | 39, đều là fallback | 55 | như trên |
| `specificity_fallback` · #1 có veto cấu trúc · #1 có Tm vùng bám < 39 °C (trên 2472) | 54 · 120 · 196 | — · 115 `hard_filter_fallback` · — | như trên |
| Grade #1 A / B / C | 2032 / 386 / 54 | — | như trên |
| Ma trận hsa, ngoài đường chéo, HIGH / MEDIUM / LOW | 172 / 105 / 22.620 (2472 assay) | 195 / 111 / 20.709 (2253) | `outputs/crossreactivity_*` |
| Độ nhạy BLAST, 100 mồi stem-loop, biên 10 °C, có bước RT (như app chạy): hit CRITICAL / mồi có hit CRITICAL | 15 / 8 | 17 / 11 | `benchmark/blast_tm_gate_sensitivity.json` (`stem_loop["10_rt_step"]`) |
| Độ nhạy BLAST, 175 mồi validation (100 stem-loop + 75 Busk poly(A)), biên 10 °C, chỉ mồi xuôi: số mồi SAFE / MEDIUM / HIGH / CRITICAL | 105 / 15 / 4 / 51 | 95 / 22 / 4 / 54 | như trên (`all["10"]`) |
| Thời gian thiết kế không cache (20 hsa, seed 2026) | p50 9,8 s · p90 11,9 s (BLAST p50 8,1 s) | p50 1,4 s (không BLAST) | `benchmark/tiered_design_timing.json` |
| BLAST gộp so với gọi từng mồi | 0/31.049 lần gọi khác nhau | — | `benchmark/blast_batch_equivalence.json` |
| Frontend: hàm khóa so với thứ tự API · nút "Show all hits" so với BLAST lúc thiết kế | 2472/2472 · 0/113 bộ khác | — | `benchmark/ui_tier_order_check.json`, `ui_blast_consistency.json` |

### 3.1 Biến thiên của tiêu chí

Câu hỏi: tiêu chí nào thực sự phân biệt các ứng viên trong một thiết kế? Số liệu ở `benchmark/freeze_criterion_variation.json`, tính trên 2472 thiết kế, pool là các ứng viên đã qua sàng lọc S2.

| Tiêu chí (mức 1–5) | Mức khác nhau trong pool | Mức khác nhau trong nhóm S cao nhất |
|---|---|---|
| S1 BLAST | 48,4 % | 0,2 % |
| S2 ΔCq assay | 4,2 % | 0,0 % |
| S3 biên Tm | 14,2 % | 0,2 % |
| P2 \|Tm − Ta\| | 12,1 % | 11,4 % |
| F1 GC % | 21,2 % | 19,9 % |
| F2 kẹp GC | 84,3 % | 77,6 % |
| F4 sàn Tm vùng bám | 80,1 % | 73,0 % |
| F5 cấu trúc | 94,9 % | 94,5 % |
| Veto cấu trúc · sàn Tm < 39 °C | 93,2 % · 51,5 % | 91,9 % · 45,1 % |

- Tầng đặc hiệu tách ứng viên ở khoảng một nửa số thiết kế (S_total khác nhau ở 52,3 %).
- Trong nhóm có S cao nhất (trung vị 80 ứng viên), việc chọn do F2, F4, F5 và hai veto mềm quyết định.

### 3.2 Chênh lệch giữa #1 và #2

Bước của khóa xếp hạng quyết định #1 đứng trên #2, tính trên top 3 do API trả về (`benchmark/ui_tier_order_check.json`, 2471 thiết kế có ít nhất 2 bộ):

| Bước | Số thiết kế |
|---|---|
| F (linh hoạt) | 1112 |
| điểm phân định | 571 |
| sàn Tm vùng bám | 269 |
| luật V4 | 214 |
| S | 140 |
| chỉ khác đuôi 5′ | 121 |
| veto cấu trúc | 26 |
| P | 17 |
| \|Tm − Ta\| | 1 |

- Có 1257 cặp trong top 3 là "Equivalent in silico", tức cùng S, veto, luật V4, P và F.
- Khi đó thứ tự chỉ do điểm phân định (0–100) quyết định. Trong nhóm S cao nhất, khoảng điểm phân định có trung vị 7,8.
- Đây là giả thuyết mà Phần 5 đề xuất kiểm bằng wet-lab: so bộ #1 với bộ #3 của cùng một miRNA.

## 4. Giới hạn chuyển sang phần Thảo luận

**Mô hình đặc hiệu và BLAST**
- **D-16 / REV-15:** rU·dG chưa được coi là cặp wobble ở bước RT; chỉ rG·dT được tính (Chen 2005). Nếu đổi thì R của các cặp C↔U ở vị trí 1–3 của overhang sẽ tăng.
- **D-17 / REV-16:** Tm theo khung đọc vẫn để thal trượt 1–2 nt trong cửa sổ L + 1; chưa kiểm tra base 3′ có bắt cặp hay không.
- **D-3:** khung đọc của RT và FWD được chọn độc lập (cách bảo thủ), nên ngầm cho phép indel bên trong phân tử. Ví dụ miR-30b ↔ 30c cho R = 1.
- **D-4:** ΔCq_FWD có trần 8,3 Cq (Stadhouders 2010), nên R của cặp mà RT bắt được nhưng FWD không bám không bao giờ dưới 0,32 % (đỉnh LOW của histogram).
- **ISO-05:** chưa ghép isomiRdb với mô hình ΔCq; cảnh báo isomiR 3′ chỉ định tính (n = 2 miRNA đo được).
- Chỉ mục họ / overhang chú giải đủ cho hsa/mmu/rno. Ở loài khác, paralog không được gộp.
- miRBase 22.1, chưa nâng lên 23.1. miR-155-5p dài 24 nt là chú giải đúng của 22.1 (REV-28).

**Hệ chấm điểm phân tầng**
- Các ngưỡng ghi "own threshold" trong SPEC §3 chưa được hiệu chỉnh bằng wet-lab. Trọng số V4 cũng chưa hiệu chỉnh: cần N ≥ 20 assay, gồm cả bộ xếp hạng thấp.
- **45 °C là mức sàn của Tm vùng bám, không phải đích.** Mức này rút từ giả thuyết chu kỳ 1 của khóa luận (let-7a 33,6 so với 46,2 °C). Ở 196/2472 thiết kế, nhóm đặc hiệu tốt nhất không có ứng viên nào đạt 39 °C.
- **F2 chỉ đếm số G/C trong 5 nt cuối, không xét vị trí.** Ví dụ …GCAAT được 5 điểm, trong khi V4 loại vì 3 nt cuối không có G/C. Bước luật V4 (QĐ 34) xử lý phần lớn các ca cùng S.
- **S3 xét mức trên biên Tm đã làm tròn 0,1 °C** (QĐ 39). Lệch tối đa 0,05 °C, nhỏ hơn nhiều so với sai số ±1–2 °C của Tm nearest-neighbour.
- **54 thiết kế fallback** (mọi ứng viên trượt sàng lọc đặc hiệu) được liệt kê kèm off-target cần kiểm ở `benchmark/tiered_fallback_list.csv`. Trong đó có hsa-let-7a-5p ↔ let-7d-5p, ΔCq dự đoán 1,43 (QĐ 41, ca wet-lab).
- **184/2656 miRNA hsa vẫn không thiết kế được.** Nguyên nhân là không có ứng viên; V4 thì không thiết kế được 403 miRNA (D-8 / REV-27). Đuôi 5′ giàu AT chưa được thử.
- Thiết kế không cache mất khoảng 10–13 s do BLAST. Giao diện chờ tối đa 60 s.

**Nhiệt động và giao diện (từ audit)**
- **SCI-07:** Tm amplicon dùng tổ hợp công thức chưa được công bố. Giao diện hiện dải theo Mg²⁺ 1,5–3 mM (~3 °C), lớn hơn độ chính xác mà một con số duy nhất ngụ ý. Chưa có số đo để nói có sai số hệ thống.
- **SCI-09:** khả năng phân biệt dạng trưởng thành với pre-miRNA mới được Chen 2005 chứng minh cho các miRNA đã thử. Việc tổng quát hóa, nhất là cho nhánh 3p, chưa được kiểm chứng.
- Tm của mồi RT trên khuôn RNA là gần đúng (DNA:RNA). Overhang dùng Sugimoto 1995; cả mồi dùng nearest-neighbour DNA:DNA.

**Ngoài phạm vi 4.0.0, chỉ ghi lại:** UX-02 (song ngữ), UX-05 (mẫu đặt hàng), Docker, ML phản ứng chéo (D-1…D-4, D-13, D-14 giữ mặc định).

## 5. Sau tag
- Chỉ sửa lỗi không đổi output. Muốn kiểm tra thì chạy lại `freeze_pipeline.py` và so với bản đã commit (`git diff --stat` phải rỗng, trừ ngày chạy và thống kê cache).
- Wet-lab: xem `docs/WETLAB_CANDIDATES.md` (Phần 5 của PROMPT, chờ chủ dự án chốt danh sách ứng viên).

## 6. Sau tag: hiệu năng

Phần này chỉ thêm thông tin; mọi số ở các mục trên giữ nguyên.

- **Số ở §3 giữ nguyên.** Thời gian 9,8 s / 11,9 s ở §3 được đo khi BLAST+ còn gửi báo cáo sử dụng về NCBI.
- **Sau PR #20 và PR #23:**
  - PR #20 chạy phân loại hit song song.
  - PR #23 đặt `BLAST_USAGE_REPORT=false`.
  - Đo cùng giao thức (20 hsa, seed 2026, không cache): p50 / p90 = **5,02 / 6,21 s**, và 0/20 thiết kế treo quá 20 s.
- **Output vẫn trùng bản đóng băng:**
  - 200 hsa với cache trống: 0/200 bản ghi khác;
  - validation: 2439/2439;
  - `ALGORITHM_VERSION` vẫn là 4.0.0.

Chi tiết ở `docs/REVIEW_panel_4.0.0.md` §9–11.

## 7. Thay đổi hiển thị isomiR sau tag (không đổi output)

Nhánh `feat/isomir-variants`, 2026-11-21 (`docs/PROMPT_isomir_variants_4.0.0.md`). `ALGORITHM_VERSION` vẫn là 4.0.0. Chỉ thêm thông tin hiển thị; mồi, điểm, tầng, thứ hạng và BLAST không đổi.

- **Thêm:**
  - Top 3 isoform 3′ (isomiRdb, pooled) được so với trình tự thiết kế, kèm loại và mức bắt dự kiến. Khoảng ΔCq chỉ lấy từ `ASSAY_DCQ_RT_SHIFT_RANGE`; lệch ≥ 3 nt ghi "not measured".
  - Cảnh báo isoform trội khi top 1 ≥ 0,8 × share đầu 3′ của 22.1. Mốc 0,8 là mốc riêng của tool, chưa hiệu chỉnh.
  - Hiển thị trong nút "Why", trong PDF và CSV. AUDIT ISO-07/08/09.
- **Sửa câu chữ:** cảnh báo 3′ không còn viết ±1 nt được bắt "about as well as the canonical form"; nay ghi khoảng đo được (ISO-01).
- **Không làm:** "độ tinh khiết tín hiệu %" (ISO-05 vẫn mở, ghi vào Thảo luận), bảng nhập phân bố isoform, chế độ cặp assay, dựng lại chỉ mục 5′ (ISO-06), đổi hằng số ΔCq, đổi chấm điểm.
- **Chứng minh không đổi output** (cache BLAST trống):

  | Kiểm tra | Kết quả |
  |---|---|
  | 200 hsa, `design_equivalence.py fields` so với bản tham chiếu | 186/200 bản ghi khác, **chỉ** dưới `stemloop_rt.three_prime_isomir` (khóa mới) và `stemloop_rt.warnings[field=three_prime_isomir*]`. Không còn đường dẫn nào khác lệch |
  | Chuỗi đã đổi | 43 câu cảnh báo 3′ (và 43 `message` tương ứng), mỗi câu chỉ khác đúng một cụm: "detected about as well as the canonical form and 2-nt-shorter ones ~3 Ct later" → "detected 0–4 Ct later (two miRNAs measured) and 2-nt-shorter ones 3–4 Ct later (one miRNA measured)" |
  | Mục mới trong `warnings[]` | 27 `three_prime_isomir_dominant` |
  | Bộ #1 so với bản đóng băng | 200/200 trùng |
  | Validation 201 mục | **2439/2439**; `results.csv` không đổi dòng nào; file khác chỉ đổi ngày chạy và thống kê cache (đã trả lại) |
  | Benchmark 50 miRNA | **50/50**; `compare_tools.md` không đổi |

  Bản tham chiếu `benchmark/logs/design_equivalence_ref_hsa200.jsonl` được thay bằng output mới; báo cáo từng đường dẫn ở `benchmark/logs/isomir_design_equivalence_fields.json`, ghi chú ở `design_equivalence_ref_hsa200.md`.
- **Chạy tay thay vì `freeze_pipeline.py`:** working tree có một file người dùng chưa được git theo dõi, nên script dừng. Validation và benchmark được chạy bằng đúng các lệnh của script, với Flask mới và cache trống.
- **Báo cáo kèm theo:** `docs/ISOMIR_VARIANTS_DRYRUN.md` (dry-run, luật đã duyệt), `docs/ISOMIR_CASE_CHECK.md` (9 ca đã công bố; báo cáo, không phải kiểm chứng pass/fail).
