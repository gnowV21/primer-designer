# SPEC_visualization.md — HG Lab Stem-loop RT-qPCR Primer Designer
# Module: Reaction Visualization · Simulated Melting Curve · Simulated Agarose Gel
# Phiên bản 1.0 — 2026-09-16 · Sync: algorithm v3.0.0, SCORING_WEIGHTS_V4, SPEC_phase2 §G, SPEC_phase5 PART D

---

## CHANGELOG

### v1.0 — 2026-09-16 — Khởi tạo module visualization
- **PART A — Mô hình toạ độ cDNA:** đặc tả toán học đầy đủ cho chuỗi biến đổi miRNA → cDNA → sợi chu kỳ 1 → amplicon. Đây là phần lõi; hai PART sau phụ thuộc vào nó.
- **PART B — Panel 1 (Reaction):** 5 giai đoạn phản ứng, 3 primer, sản phẩm từng giai đoạn, cDNA cuối cùng.
- **PART C — Panel 2 (Melting curve):** mô hình van 't Hoff 2-state + đạo hàm `-dF/dT`, mô phỏng hoàn toàn từ Tm dự đoán.
- **PART D — Panel 3 (Agarose gel):** mô hình di chuyển semi-log, thang chuẩn 25 bp + 1 band sản phẩm.
- **Quyết định (chốt với Vuong 2026-09-16):** (1) mồi universal kế thừa từ output `/api/design`, module KHÔNG chọn mồi; (2) tài liệu độc lập, không sáp nhập vào SPEC_phase nào; (3) melting curve + gel **mô phỏng hoàn toàn**, không nhận dữ liệu thực nghiệm; (4) sigmoid 2-state + đạo hàm; (5) gel chỉ thang chuẩn + 1 band sản phẩm; (6) backend render SVG, frontend chỉ hiển thị.

---

## 0. Hướng dẫn cho Claude Code

1. **Đọc trước:** `SPEC_algorithm.md` §1 (flow `/api/design`), `SPEC_phase2.md` §G (AMPLICON constants), `SPEC_phase5.md` PART D (`predicted_amplicon_tm`), `backend/algorithm/thermodynamics.py` (NN engine — nguồn ΔH, ΔS), `backend/algorithm/sequence_utils.py` (`reverse_complement`, `rna_to_dna`).
2. **Bất biến tuyệt đối:**
   - Module này **KHÔNG thiết kế primer**, **KHÔNG chấm điểm**, **KHÔNG sửa** `SCORING_WEIGHTS_V4`.
   - Module này **KHÔNG tự sinh trình tự primer**. Mọi trình tự đến từ response `/api/design`. Nó chỉ tính **toạ độ** và **hình học**.
   - Tm amplicon lấy từ `predicted_amplicon_tm` (SPEC_phase5 PART D). **Không tính lại bằng engine khác** — vi phạm nguyên tắc "unified engines".
   - ΔH/ΔS lấy từ `thermodynamics.py` đang có. Không copy bảng NN sang file mới.
3. **Không thêm dependency.** SVG sinh bằng string builder thuần Python trong `svg_builder.py`. KHÔNG dùng matplotlib, cairosvg, svgwrite, plotly.
4. **Trung thực khoa học (bắt buộc):** mọi panel mô phỏng phải mang nhãn `Simulated from predicted values — not experimental data` nhúng thẳng trong SVG, không thể tắt bằng tham số. Đây là điều kiện chặn merge.
5. **Determinism:** cùng input → SVG **byte-identical**. Cấm mọi nguồn ngẫu nhiên (không nhiễu giả trên gel, không jitter, không timestamp trong SVG).
6. **Output UI: English only.** Comment code tiếng Việt được.
7. Mỗi constant có comment `[NGUỒN]`. Không để số magic.
8. Thứ tự implement: §A → §B → §C → §D → §E → §F. Chạy unit test sau mỗi phần.
9. Trước `git commit`: chạy Superpower security check (đặc biệt §E.4 — XML escaping).
. **Đọc trước khi code:** `SPEC_week1.md` (§2b tooling, §6 defaults, §19 backend flow), `SPEC_phase2.md` (§4 constants, scoring), `SPEC_phase3.md` (§7 SCORING_WEIGHTS_V4, §8 BLAST, §13 frontend off-target). Phase 4 **không** đổi thuật toán lõi — chỉ trình bày kết quả, cảnh báo, export, edge-case.
2. **Nguyên tắc bất biến:** giữ nguyên stack (SPEC_week1 §2). Frontend: React 18 + Vite 5 + Tailwind 3 + React Router v6 + Axios — **không thêm** thư viện UI. Backend: chỉ thêm dependency export ở §3, không đụng `primer3-py`/ViennaRNA/BLAST.
3. **Nguồn dữ liệu bảng nhiệt động là dữ liệu ĐÃ CÓ** trong response `/api/design` (§5.3). Tuyệt đối không tính lại thermodynamics ở frontend — chỉ đọc và hiển thị.
4. **Output UI 100% English** (đồng bộ Week 1 §10–13). Comment code có thể tiếng Việt.
5. **Constants tập trung:** ngưỡng edge-case mới đặt trong `backend/algorithm/constants.py`, mỗi hằng số có comment `[NGUỒN]`. Frontend đọc ngưỡng hiển thị từ response, không hardcode.
6. **Test:** mỗi module backend mới có unit test (pytest); ResultsPage + export có E2E (Playwright, thư mục `e2e/`).
7. **Superpower MCP** (SPEC_week1 §2b): chạy security check trước commit (endpoint `/api/export` nhận input → kiểm injection/path traversal); dùng skill `hrm-algorithm-validator` không áp dụng ở đây (Phase 4 không có thuật toán melting).
---

## 1. Tổng quan

### Mục tiêu
Sau khi `/api/design` trả Top 3 bộ primer, người dùng chọn 1 candidate và nhấn "Visualize". Backend trả 3 panel SVG:

| Panel | Nội dung | Nguồn dữ liệu |
|---|---|---|
| 1 — Reaction | 5 giai đoạn phản ứng, 3 primer, sản phẩm từng giai đoạn, cDNA cuối | §A (toạ độ) |
| 2 — Melting | Đường cong nóng chảy + đạo hàm `-dF/dT`, đỉnh tại Tm | `predicted_amplicon_tm` + ΔH từ NN |
| 3 — Gel | Thang chuẩn 25 bp + 1 band sản phẩm | Chiều dài amplicon (§A) |

### Vì sao cần
- **Dạy học và kiểm tra thiết kế bằng mắt.** Lỗi phổ biến nhất khi thiết kế thủ công là ghép sai chiều 5'→3' với 3'→5', hoặc quên rằng sản phẩm PCR dừng tại đầu 5' của mồi. Panel 1 làm hai lỗi này lộ ra ngay.
- **Lường trước kết quả wet-lab.** Panel 2 và 3 cho biết cần chờ vạch ở đâu trên gel và đỉnh ở đâu trên melting curve, trước khi tốn mẫu.
- **Hình cho bài báo/khoá luận.** Export SVG + PNG 300 dpi.

### Phạm vi — KHÔNG làm
- Không mô phỏng đường khuếch đại (amplification plot), Ct, hiệu suất.
- Không nhận dữ liệu thực nghiệm để chồng lên (quyết định 2026-09-16).
- Không vẽ đỉnh primer-dimer trên melting curve, không vẽ làn NTC/no-RT trên gel.
- Không vẽ cấu trúc bậc hai của mồi S (đã có MFE/ViennaRNA ở Phase 2, hiển thị riêng).
- Không mô phỏng isomiR hay sản phẩm off-target.

---

## 2. Nguồn tham chiếu

- **[Chen05]** Chen C et al. "Real-time quantification of microRNAs by stem-loop RT-PCR." *Nucleic Acids Res.* 2005;33(20):e179. DOI 10.1093/nar/gni178. → cơ chế stem-loop, overhang 6 nt, kiến trúc 3 primer.
- **[Kramer11]** Kramer MF. "Stem-loop RT-qPCR for miRNAs." *Curr Protoc Mol Biol.* 2011;Chapter 15:Unit 15.10. DOI 10.1002/0471142727.mb1510s95. → mồi universal reverse.
- **[SL04]** SantaLucia J, Hicks D. "The thermodynamics of DNA structural motifs." *Annu Rev Biophys Biomol Struct.* 2004;33:415–40. → bảng NN, ΔH/ΔS, hiệu chỉnh muối.
- **[SL98]** SantaLucia J. "A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics." *PNAS.* 1998;95(4):1460–5. → mô hình 2-state, quan hệ van 't Hoff.
- **[Ririe97]** Ririe KM, Rasmussen RP, Wittwer CT. "Product differentiation by analysis of DNA melting curves during PCR." *Anal Biochem.* 1997;245(2):154–60. → hình thái đường cong nóng chảy và đạo hàm `-dF/dT`; chuẩn trình bày đỉnh đơn cho sản phẩm đặc hiệu.
- **[Dwight11]** Dwight Z, Palais R, Wittwer CT. "uMELT: prediction of high-resolution melting curves." *Bioinformatics.* 2011;27(7):1019–20. DOI 10.1093/bioinformatics/btr065. → chuẩn trình bày trục và thang, tham chiếu hình dạng.
- **[Lagatie17]** đã trích ở SPEC_phase5 — luật P3, phân biệt product vs dimer trong SYBR.
- **[Helling63]** Helling RB — quan hệ semi-log giữa quãng đường di chuyển và log(bp) trên gel agarose; xem thêm hướng dẫn nhà sản xuất thang chuẩn.

> **Ghi chú độ tin cậy:** [Helling63] dùng làm cơ sở định tính cho mô hình semi-log. Panel 3 là **minh hoạ kích thước tương đối**, không phải dự đoán quãng đường di chuyển thực. Nhãn bắt buộc §0.4 áp dụng.

---

# PART A — Mô hình toạ độ cDNA (LÕI)

> Đây là phần Claude Code phải hiểu tuyệt đối chính xác. Hai PART sau chỉ vẽ lại kết quả của phần này.

## A.1 Nguyên lý sinh học — 5 giai đoạn

**Stage 0 — Thành phần.** Ba primer + mature miRNA.

**Stage 1 — Bắt cặp RT.** Mồi S gập kẹp tóc; chỉ `RT_OVERHANG = 6` nt ở **đầu 3'** lộ ra. Sáu nt này bắt cặp **đối song** với **6 nt đầu 3'** của miRNA.

**Stage 2 — Sản phẩm RT.** Reverse transcriptase kéo dài **đầu 3' của S**, chép ngược miRNA về phía **đầu 5'** của miRNA. Sản phẩm = S nguyên vẹn + phần bổ sung `L − 6` nt.

**Stage 3 — Chu kỳ PCR 1.** Mồi F bắt cặp với **đầu 3' của cDNA**. Vùng bắt cặp của F = `k` nt đầu 5' của miRNA (`k` = 12–17, quy tắc "F 3' end phải loại 6 nt cuối của miRNA"). Đuôi GC ở đầu 5' của F **không có khuôn** ở chu kỳ này — nó nhô ra tự do. Polymerase kéo dài chép hết cDNA.

**Stage 4 — Chu kỳ PCR 2 trở đi.** Mồi universal bắt cặp với sợi chu kỳ 1. Sản phẩm **dừng tại đầu 5' của mồi** — đây là điểm cắt sinh ra amplicon ổn định. Từ đây mọi phân tử đều cùng chiều dài.

## A.2 Ký hiệu

| Ký hiệu | Nghĩa | Nguồn |
|---|---|---|
| `m` | mature miRNA dạng DNA (`rna_to_dna`) | input |
| `L` | `len(m)` | dẫn xuất |
| `BODY` | thân kẹp tóc, 44 nt | `constants.STEMLOOP_BODY` |
| `S` | mồi stem-loop RT, `len = 44 + 6 = 50` | `/api/design` |
| `F` | mồi forward | `/api/design` |
| `k` | độ dài vùng bắt cặp của F | `/api/design` (`forward.binding_length`) |
| `tail` | `F[:len(F)-k]`, đuôi GC 5' | dẫn xuất |
| `U` | mồi universal reverse | `/api/design` |
| `rc(x)` | reverse complement | `sequence_utils` |

## A.3 Công thức

```python
RT_OVERHANG = 6          # [Chen05] — CỐ ĐỊNH, cấm tham số hoá

overhang = S[-RT_OVERHANG:]
BODY     = S[:-RT_OVERHANG]

ext      = rc(m[:L - RT_OVERHANG])          # phần RT tổng hợp mới
cdna     = S + ext                          # len = 44 + L

tail     = F[:len(F) - k]
sense    = tail + m + rc(BODY)              # sợi chu kỳ 1, len = len(tail) + L + 44

rcU      = rc(U)
j        = sense.index(rcU)
amplicon = sense[: j + len(U)]
```

### A.3.1 Chứng minh `sense = tail + m + rc(BODY)`

Sợi chu kỳ 1 = `tail` + bản bổ sung của toàn bộ cDNA:

```
rc(cdna) = rc(BODY + overhang + ext)
         = rc(ext) + rc(overhang) + rc(BODY)
         = m[:L-6] + m[L-6:]     + rc(BODY)
         = m                     + rc(BODY)
```

vì theo định nghĩa `overhang = rc(m[-6:])`, nên `rc(overhang) = m[-6:]`.

**Hệ quả quan trọng:** vùng `rc(BODY)` bắt đầu **ngay sau** nt cuối của miRNA, không chồng lấn. Đây là chỗ dễ đếm lặp 6 nt nhất — implement theo công thức, đừng ghép tay.

## A.4 Assertion bắt buộc

Mỗi assertion fail → `HTTP 422` với `error_code` tương ứng, **không** vẽ panel nào.

| # | Kiểm tra | `error_code` | Ý nghĩa |
|---|---|---|---|
| A1 | `len(S) == len(BODY) + 6` và `len(BODY) == 44` | `RT_PRIMER_LENGTH` | Mồi S sai kiến trúc |
| A2 | `S[-6:] == rc(m[-6:])` | `OVERHANG_MISMATCH` | Overhang không khớp đầu 3' miRNA |
| A3 | `F[-k:] == m[:k]` | `FORWARD_BINDING_MISMATCH` | Vùng bắt cặp F không khớp đầu 5' miRNA |
| A4 | `12 <= k <= 17` | `FORWARD_BINDING_RANGE` | Vi phạm quy tắc SPEC_week1 §1 |
| A5 | `sense.count(rcU) == 1` | `UNIVERSAL_SITE_AMBIGUOUS` | Mồi universal bám >1 chỗ hoặc không bám |
| A6 | `len(tail) + L <= j` | `REGION_OVERLAP` | Vị trí mồi universal lấn vào vùng miRNA |
| A7 | `AMPLICON_MIN_QPCR <= len(amplicon) <= AMPLICON_MAX_QPCR` | `AMPLICON_SIZE_WARN` | **Warning, không chặn** — panel vẫn vẽ, kèm nhãn đỏ |

> **A7 là warning chứ không phải error** vì `/api/design` đã lọc kích thước ở tầng scoring. Nếu A7 fail mà candidate vẫn lọt tới đây thì có bất nhất giữa constants và pipeline — log `WARNING` kèm cả hai giá trị để truy vết.

## A.5 Bốn vùng màu của amplicon

Dùng chung cho **cả ba panel**. Đây là hợp đồng màu duy nhất của module.

| Vùng | Khoảng | Ý nghĩa | Token màu |
|---|---|---|---|
| R1 | `[0, len(tail))` | Đuôi GC của mồi F — không có trên miRNA | `viz-tail` |
| R2 | `[len(tail), len(tail)+L)` | Mature miRNA — **vùng đặc hiệu duy nhất** | `viz-mirna` |
| R3 | `[len(tail)+L, j)` | Vùng mồi S, ngoài chỗ mồi universal bám | `viz-stemloop` |
| R4 | `[j, j+len(U))` | Vùng mồi S trùng vị trí mồi universal | `viz-universal` |

Bất biến: `R1 + R2 + R3 + R4 == len(amplicon)`, bốn khoảng liền kề, không chồng lấn.

## A.6 Golden test — hsa-miR-16-5p

Dùng constants hiện hành của tool (`STEMLOOP_BODY` 44 nt, universal [Kramer11] 20 nt).

```
INPUT
  m   = TAGCAGCACGTAAATATTGGCG            (L = 22)
  F   = GGCGTAGCAGCACGTAAA                (k = 14, tail = GGCG)
  U   = CCAGTGCAGGGTCCGAGGTA              (20 nt)

EXPECTED
  S        50 nt  GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAA
  overhang  6 nt  CGCCAA
  cdna     66 nt  GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAATATTTACGTGCTGCTA
  sense    70 nt  GGCGTAGCAGCACGTAAATATTGGCGGTCGTATCCAGTGCGAATACCTCGGACCCTGCACTGGATACGAC
  j        43
  amplicon 63 bp  GGCGTAGCAGCACGTAAATATTGGCGGTCGTATCCAGTGCGAATACCTCGGACCCTGCACTGG

  R1 [ 0,  4)  4 nt  GGCG
  R2 [ 4, 26) 22 nt  TAGCAGCACGTAAATATTGGCG
  R3 [26, 43) 17 nt  GTCGTATCCAGTGCGAA
  R4 [43, 63) 20 nt  TACCTCGGACCCTGCACTGG

  GC% = 57.1
```

**Bẫy đã gặp trong quá trình soạn spec — viết test cho từng cái:**

| Bẫy | Biểu hiện | Test |
|---|---|---|
| Overhang 5 nt thay vì 6 | `S` dài 49 nt, thiếu A cuối | A2 |
| Ghép `m` rồi ghép tiếp `rc(S)` nguyên vẹn | Lặp 6 nt `TTGGCG` trong sense | So `len(sense) == len(tail)+L+44` |
| Không cắt tại đầu 5' mồi universal | Amplicon dài thêm 12–20 nt ở đuôi | So `len(amplicon)` với golden |
| Quên đuôi `tail` | Amplicon ngắn 4 nt | Kiểm `amplicon[:len(tail)] == tail` |
| Nhầm chiều khi bắt cặp | `rc` áp một lần thay vì đối song | A2 + A3 |

## A.7 PROMPT CLAUDE CODE — PART A

```
Tạo backend/visualization/coordinates.py.

1) Hàm build_amplicon_model(mirna_sequence, stemloop_rt, forward, forward_binding_length,
   universal_reverse) -> AmpliconModel (dataclass).
   Dùng sequence_utils.rna_to_dna và sequence_utils.reverse_complement — KHÔNG viết lại.
   Implement đúng công thức SPEC_visualization §A.3.
   RT_OVERHANG = 6 đặt trong constants.py với comment [Chen05]; KHÔNG nhận qua tham số.

2) AmpliconModel chứa: mirna_dna, stemloop_body, overhang, cdna, sense_strand, amplicon,
   universal_offset (j), regions (list 4 tuple start/end/name), stages (list 5 StageModel).

3) StageModel mô tả 1 giai đoạn §A.1: id, label_en, strands (mỗi strand có sequence,
   direction '5to3'|'3to5', offset_nt, region_tag), pairings (list cặp index bắt cặp),
   annotation_en.

4) Assertion A1–A6 raise VisualizationError(error_code) -> route trả HTTP 422.
   A7 chỉ log WARNING và set model.size_warning = True.

5) Test backend/visualization/test_coordinates.py:
   - golden test hsa-miR-16-5p theo §A.6 (so từng chuỗi và từng khoảng vùng)
   - 4 miRNA khác lấy từ validation/ hiện có (chọn L=21,22,23,24 nếu có)
   - 5 test bẫy §A.6: mỗi bẫy phải raise đúng error_code
   - property test: với mọi input hợp lệ, sum(len 4 vùng) == len(amplicon)

Chạy pytest và báo cáo trước khi xong. KHÔNG đụng scoring.py, constants SCORING_WEIGHTS_V4.
```

---

# PART B — Panel 1: Reaction

## B.1 Bố cục

SVG dọc, `viewBox="0 0 900 H"`, H tính động. 5 khối xếp dọc theo Stage 0→4, mỗi khối một nhóm `<g>` có `aria-label`.

| Stage | Nội dung vẽ |
|---|---|
| 0 | 4 thanh ngang: miRNA, S, F, U — kèm trình tự monospace và chiều 5'/3' |
| 1 | miRNA (5'→3') ở trên, 6 nt cuối tô đậm; S ở dưới với overhang thẳng hàng; 6 vạch bắt cặp; thân kẹp tóc vẽ dạng khối bo tròn nét đứt bên phải; mũi tên RT chỉ **sang trái** |
| 2 | Thanh cDNA 2 đoạn: `S` và `ext`, kèm trình tự đầy đủ |
| 3 | Thanh cDNA làm khuôn + mồi F bên dưới, phần `tail` viền nét đứt (chưa bắt cặp); mũi tên kéo dài; thanh sợi chu kỳ 1 kết quả |
| 4 | Thanh sợi chu kỳ 1 + mồi U; **đường nét đứt dọc tại `j + len(U)`** đánh dấu điểm dừng; thanh amplicon 4 vùng màu |

## B.2 Quy tắc vẽ bắt buộc

- **Chiều luôn hiện rõ.** Mỗi thanh trình tự có nhãn `5'` và `3'` ở hai đầu. Khi vẽ mạch khuôn ở Stage 1 và 3, viết theo chiều `3'→5'` để mồi bên dưới đọc `5'→3'` trái sang phải — đúng quy ước sách giáo khoa.
- **Căn ký tự tuyệt đối.** Dùng `<tspan x="...">` cho từng ký tự khi cần khớp cột (Stage 1, Stage 3). Cấm dựa vào `letter-spacing` — font metric khác nhau giữa OS.
- **Bước cột:** `CHAR_PITCH = 20` px cho vùng phóng to (Stage 1, 3), `SCALE_BP` px/nt cho thanh tổng quan (Stage 0, 2, 4), tính sao cho thanh dài nhất vừa 820 px.
- **Cửa sổ phóng to:** Stage 1 hiển thị `min(L, 22)` nt cuối của miRNA + overhang. Stage 3 hiển thị `k + len(tail) + 8` cột quanh điểm bắt cặp. Nếu miRNA dài hơn cửa sổ, cắt ở đầu 5' và vẽ dấu `…`.
- **Mũi tên tổng hợp** luôn chỉ theo chiều `5'→3'` của sợi mới. Ở Stage 1 là **sang trái**; ở Stage 3, 4 là **sang phải**.
- **Đuôi chưa bắt cặp** (`tail` ở Stage 3) vẽ viền `stroke-dasharray` để phân biệt với vùng đã bắt cặp.

## B.3 Chú giải

Legend cố định ở chân panel, 4 ô màu theo §A.5, kèm số nt của từng vùng. Thêm 1 dòng: `Only the miRNA region (R2) is target-specific; R1/R3/R4 are shared across all assays.`

## B.4 Constants

```python
# backend/visualization/constants.py
VIZ_CANVAS_WIDTH      = 900   # px
VIZ_MARGIN            = 40    # px
VIZ_CHAR_PITCH        = 20    # px — bước cột vùng phóng to
VIZ_BAR_HEIGHT        = 44    # px — chiều cao thanh trình tự
VIZ_STAGE_GAP         = 36    # px
VIZ_MAX_ZOOM_COLUMNS  = 34    # số cột tối đa trong 1 cửa sổ phóng to
VIZ_MONO_SIZE         = 13    # px
VIZ_LABEL_SIZE        = 12    # px
```

---

# PART C — Panel 2: Melting curve mô phỏng

## C.1 Mô hình

Chuyển pha 2-state theo van 't Hoff [SL98]. Gọi `θ(T)` là phần phân tử còn ở dạng mạch đôi:

```
θ(T) = 1 / ( 1 + exp[ (ΔH_m / R) · (1/Tm − 1/T) ] )
```

- `T`, `Tm` tính bằng **Kelvin**
- `R = 1.987` cal·mol⁻¹·K⁻¹
- `ΔH_m` = enthalpy nóng chảy, **cal/mol**, dấu dương

Kiểm chứng: `T = Tm` → số mũ = 0 → `θ = 0.5` ✓ · `T > Tm` → số mũ > 0 → `θ → 0` ✓

### C.1.1 Tín hiệu huỳnh quang
SYBR Green phát sáng khi bám mạch đôi, nên `F_norm(T) = θ(T)`, chuẩn hoá `[0, 1]`. Không thêm baseline drift — mô phỏng lý tưởng, và baseline giả sẽ làm người dùng tưởng là dữ liệu thật.

### C.1.2 Đạo hàm — tính giải tích, không sai phân số

```
u(T)      = (ΔH_m / R) · (1/Tm − 1/T)
−dF/dT    = [ e^u / (1 + e^u)² ] · ΔH_m / (R · T²)
```

Đỉnh tại `T = Tm`, giá trị đỉnh `= ΔH_m / (4 · R · Tm²)`.

> Bắt buộc dùng công thức giải tích. Sai phân số trên lưới 0.1 °C gây răng cưa thấy rõ ở amplicon ngắn.

### C.1.3 Nguồn `ΔH_m`

Theo thứ tự ưu tiên:

1. Gọi `thermodynamics.py` tính tổng ΔH nearest-neighbor của amplicon [SL04]. **Đường mặc định.**
2. Nếu engine không nhận chuỗi dài hơn `NN_MAX_LENGTH`: `ΔH_m = VIZ_DH_PER_BP × N` với `VIZ_DH_PER_BP = 8000` cal/mol/bp [SL04, giá trị trung bình]. Khi dùng nhánh này, set `meta.dh_source = "approximate"` và **hiện nhãn trên SVG**: `ΔH approximated — peak width is indicative only`.

`Tm` **luôn** lấy từ `predicted_amplicon_tm`. Không bao giờ tính lại.

## C.2 Lưới và trục

```python
VIZ_MELT_T_START = 60.0   # °C — [Ririe97] dải ramp điển hình
VIZ_MELT_T_END   = 95.0   # °C
VIZ_MELT_T_STEP  = 0.1    # °C — 351 điểm, khớp độ phân giải máy qPCR
```

- Trục X: nhiệt độ, tick mỗi 5 °C, nhãn `Temperature (°C)`
- Trục Y trái: `Normalized fluorescence` `[0, 1]`
- Trục Y phải: `−dF/dT`, tự scale theo max
- Hai đường trên cùng một khung (như [Ririe97] Fig.1): `F_norm` mảnh, `−dF/dT` đậm
- Đường dọc nét đứt tại Tm + nhãn `Tm = XX.X °C`
- Nhãn phụ: `Amplicon: N bp · GC XX.X%`

## C.3 Cảnh báo dimer — chỉ chữ, không vẽ đường

Quyết định 2026-09-16 là không vẽ đỉnh dimer. Nhưng luật P3 [Lagatie17] của SPEC_phase5 PART D vẫn áp dụng: nếu `/api/design` trả `dimer_tm_warning`, in một dòng cảnh báo dưới biểu đồ:

`Predicted dimer Tm is within X.X °C of the product peak — a single melt peak may not confirm specificity.`

Không vẽ thêm curve nào. Chỉ chữ.

## C.4 PROMPT CLAUDE CODE — PART C

```
Tạo backend/visualization/melting.py.

1) simulate_melting(amplicon_seq, tm_celsius, dh_cal_per_mol=None) -> MeltingModel
   - Nếu dh_cal_per_mol là None: gọi thermodynamics.py lấy ΔH của amplicon.
     Nếu engine từ chối (chuỗi quá dài): fallback VIZ_DH_PER_BP * N, set dh_source='approximate'.
   - Sinh lưới 60.0–95.0 step 0.1 (dùng số nguyên chia 10 để tránh lỗi float tích luỹ).
   - theta(T) và -dF/dT theo công thức giải tích §C.1.2. Kelvin = C + 273.15.
   - Trả: temperatures, f_norm, neg_dfdt, peak_temperature, peak_height, dh_source.

2) Test test_melting.py:
   - theta(Tm) == 0.5 (abs tol 1e-9)
   - f_norm giảm đơn điệu trên toàn lưới
   - argmax(neg_dfdt) cách Tm <= 0.05 °C
   - peak_height khớp ΔH/(4·R·Tm²) (rel tol 1e-6)
   - ΔH lớn hơn -> đỉnh cao hơn và hẹp hơn (so FWHM)
   - fallback branch set dh_source='approximate'
   - determinism: gọi 2 lần trả list bằng nhau exact

KHÔNG tự tính Tm. KHÔNG thêm dependency.
```

---

# PART D — Panel 3: Agarose gel mô phỏng

## D.1 Mô hình di chuyển

Quan hệ semi-log giữa quãng đường và kích thước [Helling63]:

```
y(N) = Y_TOP + H_LANE · [ log10(N_max) − log10(N) ] / [ log10(N_max) − log10(N_min) ]
```

`N_max`, `N_min` = band lớn nhất và nhỏ nhất của thang chuẩn. Fragment lớn → `y` nhỏ → gần giếng.

Nếu `len(amplicon)` nằm ngoài `[N_min, N_max]`: kẹp vào biên và hiện nhãn `Outside ladder range`.

## D.2 Thang chuẩn

```python
VIZ_GEL_LADDER_BP = [25, 50, 75, 100, 125, 150, 200, 300, 400, 500]  # 25 bp ladder
VIZ_GEL_AGAROSE_PCT = 3.0    # % — phù hợp phân giải 50–150 bp
VIZ_GEL_LANE_HEIGHT = 420    # px
VIZ_GEL_BAND_HEIGHT = 7      # px
```

Chọn thang 25 bp vì amplicon stem-loop RT-qPCR rơi vào 60–150 bp (SPEC_phase2 §G) — thang 100 bp không phân giải được vùng này.

Band 100, 200, 300, 400, 500 vẽ đậm hơn (reference bands), đúng quy ước nhà sản xuất.

## D.3 Bố cục

Hai làn: `L` (ladder) và `P` (product). Mỗi làn có giếng vẽ ở đỉnh. Band sản phẩm kèm nhãn `N bp` ngay bên phải. Nhãn dưới gel: `3% agarose · simulated migration`.

**Không** vẽ làn NTC, no-RT, dimer (quyết định 2026-09-16).

**Không** thêm nhiễu, blur ngẫu nhiên, hay gradient giả "ảnh chụp". Band là hình chữ nhật bo góc, màu phẳng. Gel mô phỏng phải **trông như sơ đồ**, không được trông như ảnh gel thật — đây là yêu cầu trung thực, không phải yêu cầu thẩm mỹ.

## D.4 PROMPT CLAUDE CODE — PART D

```
Tạo backend/visualization/gel.py.

1) simulate_gel(amplicon_bp, ladder=VIZ_GEL_LADDER_BP) -> GelModel
   - y_position(N) theo §D.1
   - Trả: ladder_bands [(bp, y, is_reference)], product_band (bp, y), out_of_range bool
2) Test test_gel.py:
   - y đơn điệu giảm theo bp
   - band 63 bp nằm giữa band 50 và 75 của thang
   - amplicon = giá trị thang chuẩn -> y trùng band đó (tol 0.5 px)
   - amplicon 20 bp và 800 bp -> out_of_range True, y bị kẹp trong làn
   - determinism
```

---

# PART E — API và render

## E.1 Endpoint

```
POST /api/visualize
```

Request:
```json
{
  "mirna_sequence": "UAGCAGCACGUAAAUAUUGGCG",
  "mirna_id": "hsa-miR-16-5p",
  "stemloop_rt": "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACCGCCAA",
  "forward": "GGCGTAGCAGCACGTAAA",
  "forward_binding_length": 14,
  "universal_reverse": "CCAGTGCAGGGTCCGAGGTA",
  "predicted_amplicon_tm": 79.4,
  "dimer_tm_warning": null,
  "panels": ["reaction", "melting", "gel"],
  "theme": "light"
}
```

Response `200`:
```json
{
  "panels": { "reaction": "<svg …>", "melting": "<svg …>", "gel": "<svg …>" },
  "meta": {
    "amplicon_length": 63,
    "amplicon_sequence": "GGCG…CTGG",
    "gc_percent": 57.1,
    "regions": [{"name":"F_tail","start":0,"end":4}, "…"],
    "peak_temperature": 79.4,
    "dh_source": "nearest_neighbor",
    "size_warning": false
  }
}
```

Lỗi `422`: `{"error_code": "OVERHANG_MISMATCH", "detail": "…", "expected": "CGCCAA", "actual": "CGCCA"}`

**Toàn bộ trường trong request đến từ response `/api/design`.** Frontend chỉ chuyển tiếp. Không có trường nào do người dùng gõ tay ngoài `mirna_id`.

## E.2 Hiệu năng

Mục tiêu `< 400 ms` cho cả 3 panel. Ràng buộc từ dự án là `/api/design < 5 s`; endpoint này nhẹ hơn nhiều vì không gọi BLAST, ViennaRNA hay primer3.

Cache: `SQLiteKVCache` đã có, key = `sha256(canonical_json(request_minus_theme))`, TTL 30 ngày. Theme không vào key — sinh cả hai theme trong một lần, lưu chung.

## E.3 `svg_builder.py`

Module nhỏ, thuần Python, không dependency:
- `Svg(width, height, view_box)` — context manager, `.rect()`, `.text()`, `.line()`, `.path()`, `.group()`
- `.render() -> str`
- Mọi text đi qua `escape_xml()` (§E.4)
- Thuộc tính số làm tròn 2 chữ số thập phân — bảo đảm determinism giữa các nền tảng

## E.4 Bảo mật — XML escaping

`mirna_id` là chuỗi do người dùng nhập, được in vào tiêu đề SVG, và SVG được frontend chèn bằng `dangerouslySetInnerHTML`. Đây là đường XSS trực tiếp.

Bắt buộc:
- `escape_xml()` xử lý `& < > " '` cho **mọi** chuỗi đưa vào SVG, không ngoại lệ
- Validate `mirna_id` ở tầng route bằng regex `^[A-Za-z0-9\-\._]{1,64}$`; không khớp → `422 INVALID_MIRNA_ID`
- Cấm `<foreignObject>`, `<script>`, `<use href>` trong output
- Test riêng: `mirna_id = '"><script>alert(1)</script>'` phải bị chặn ở tầng route **và** bị escape nếu lọt qua

## E.5 Theme

SVG nhận màu qua CSS custom property có fallback:
`fill="var(--viz-mirna, #2A9D8F)"`. Frontend định nghĩa `--viz-*` theo theme sáng/tối. Không sinh hai bản SVG khác nhau.

Bảng token: `--viz-tail`, `--viz-mirna`, `--viz-stemloop`, `--viz-universal`, `--viz-axis`, `--viz-curve`, `--viz-derivative`, `--viz-band`, `--viz-band-ref`.

## E.6 Accessibility

Mỗi SVG có `role="img"`, `<title>` và `<desc>`. `<desc>` mô tả nội dung bằng lời cho screen reader — ví dụ panel 3: `Simulated agarose gel. Ladder lane with ten bands from 25 to 500 base pairs. Product lane with a single band at 63 base pairs, migrating between the 50 and 75 base pair markers.`

## E.7 Frontend

`VisualizationPanel.jsx`:
- Tabs: Reaction · Melting · Gel
- Chèn SVG bằng `dangerouslySetInnerHTML` (nguồn tin cậy là endpoint của chính ta, đã escape ở §E.4)
- Nút `Download SVG` — tải thẳng chuỗi SVG
- Nút `Download PNG (300 dpi)` — render client-side: `new Image()` từ blob SVG → `<canvas>` scale `300/96` → `toBlob()`. **Không** thêm dependency backend cho PNG.
- Đổi candidate trong Top 3 → gọi lại `/api/visualize`

## E.8 PROMPT CLAUDE CODE — PART E

```
1) backend/visualization/svg_builder.py — SVG serializer thuần Python, escape_xml cho mọi text,
   làm tròn toạ độ 2 chữ số. Không dependency.
2) backend/visualization/renderer.py — render_reaction / render_melting / render_gel,
   nhận model từ coordinates.py, melting.py, gel.py; dùng var(--viz-*) với fallback hex.
   Mọi panel nhúng dòng "Simulated from predicted values — not experimental data" (§0.4).
3) backend/routes/visualize.py — POST /api/visualize; validate mirna_id regex §E.4;
   assertion A1–A6 -> 422 kèm error_code; cache qua SQLiteKVCache TTL 30 ngày.
4) frontend/src/components/VisualizationPanel.jsx theo §E.7. UI English.
5) Test:
   - test_svg_builder.py: escape_xml đủ 5 ký tự; output parse được bằng xml.etree
   - test_visualize_route.py: golden request miR-16 -> 200 và meta khớp §A.6;
     6 request lỗi -> đúng error_code; XSS payload bị chặn 422
   - test_determinism.py: gọi 3 lần -> SVG byte-identical
   - Playwright: chuyển tab, đổi candidate, download SVG
Trước commit: chạy Superpower security check, chú ý §E.4.
```

---

# PART F — Định nghĩa "hoàn thành"

**PART A — Toạ độ**
- [ ] `coordinates.py` implement đúng §A.3, `RT_OVERHANG = 6` là constant không tham số hoá
- [ ] Golden test miR-16 §A.6 pass từng chuỗi và từng khoảng vùng
- [ ] 4 miRNA khác (L = 21–24) pass
- [ ] 5 test bẫy §A.6 raise đúng `error_code`
- [ ] Property test `sum(4 vùng) == len(amplicon)` pass

**PART B — Reaction**
- [ ] 5 stage vẽ đủ, mỗi stage có `aria-label`
- [ ] Nhãn `5'`/`3'` hiện trên mọi thanh trình tự
- [ ] Vùng phóng to dùng `<tspan x>` từng ký tự, không dựa `letter-spacing`
- [ ] Mũi tên RT chỉ sang trái ở Stage 1
- [ ] Legend 4 vùng + dòng ghi chú đặc hiệu

**PART C — Melting**
- [ ] `θ(Tm) = 0.5`; đỉnh `−dF/dT` cách Tm ≤ 0.05 °C
- [ ] Đạo hàm giải tích, không sai phân số
- [ ] `Tm` lấy từ `predicted_amplicon_tm`, không tính lại
- [ ] Nhánh fallback ΔH set `dh_source='approximate'` và hiện nhãn trên SVG
- [ ] Cảnh báo dimer dạng chữ khi `/api/design` trả `dimer_tm_warning`

**PART D — Gel**
- [ ] Band 63 bp nằm giữa band 50 và 75
- [ ] Band ngoài dải thang bị kẹp và có nhãn
- [ ] Không nhiễu, không blur, không gradient giả ảnh chụp

**PART E — API**
- [ ] `/api/visualize` < 400 ms (3 panel, chưa cache)
- [ ] `escape_xml` phủ mọi text; XSS payload bị chặn 422
- [ ] SVG byte-identical qua 3 lần gọi
- [ ] Download SVG và PNG 300 dpi hoạt động
- [ ] Nhãn "Simulated…" có trên cả 3 panel, không tắt được

**Bất biến toàn module**
- [ ] Không thêm dependency vào `backend/requirements.txt`
- [ ] `SCORING_WEIGHTS_V4` không đổi
- [ ] `/api/design` không đổi behavior
- [ ] Mọi constant `VIZ_*` có comment `[NGUỒN]`

---

## Phụ lục — Câu hỏi để ngỏ cho phiên bản sau

1. **Đa loài / miRNA dài bất thường.** Công thức §A.3 giả định `L > 6`. Với miRNA rất ngắn (`L < 18`) thì `k` có thể không đạt 12 nt — hiện raise `FORWARD_BINDING_RANGE`. Cần quyết định có nới quy tắc hay không.
2. **Panel cho TaqMan probe.** SPEC_phase6 PART A đã có probe. Vẽ vị trí probe trên amplicon là mở rộng tự nhiên của Panel 1, nhưng cần chốt probe nằm ở vùng nào (junction position đã spec ở §K).
3. **Batch.** SPEC_phase8 có batch design. Panel 3 có thể vẽ nhiều làn sản phẩm cho một panel miRNA — nhưng đó là gel multiplex giả định, cần cân nhắc rủi ro hiểu nhầm.
4. **ΔH cho amplicon dài.** Nếu `thermodynamics.py` giới hạn chiều dài, nên đo xem ngưỡng thực tế là bao nhiêu trước khi chốt `NN_MAX_LENGTH`.

---

*Hết SPEC_visualization.md v1.0 — sync algorithm v3.0.0, SPEC_phase2 §G, SPEC_phase5 PART D.*
