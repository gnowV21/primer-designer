# AUDIT REPORT — HG Lab Stem-loop RT-qPCR Primer Designer

**Ngày:** 2026-09-18 · **Nhánh:** `feat/design-focus` @ `db3abd7` + thay đổi UI chưa commit · **Phạm vi:** audit chỉ đọc code và tính lại; các sửa đổi sau đó được ghi ở **mục 10**.
**Hội đồng (mô phỏng):** (1) nhà hóa sinh axit nucleic · (2) kỹ sư bioinformatics · (3) nhà thiết kế UX cho công cụ khoa học.

> Quy ước: mọi khẳng định có bằng chứng (`file:dòng`, output lệnh, hoặc PMID đã kiểm chứng qua PubMed MCP). Không có bằng chứng thì ghi **GIẢ THUYẾT** hoặc **CHƯA KIỂM CHỨNG**. Trích dẫn được lấy từ PubMed, có DOI ở mục 11.
>
> **Về case study miR-16 (exp 220826):** đây chỉ là một ví dụ minh họa, **không phải ground truth**. Audit không dùng nó để hiệu chỉnh thuật toán, không suy ra sai số hệ thống từ nó, và không chẩn đoán sâu thí nghiệm đó. Bộ primer miR-16 chỉ được dùng như một input để tái hiện lỗi code có tính tổng quát (vd. SCI-01).

---

## 0. Công cụ đã dùng thật (kiểm kê, không giả định)

| Công cụ | Trạng thái | Dùng vào việc gì |
|---|---|---|
| PubMed MCP | ✅ có | Kiểm chứng 20 trích dẫn → PMID + DOI (mục 11) |
| primer3-py 2.0.3, ViennaRNA 2.7.2, Biopython 1.85, BLAST+ 2.17.0 | ✅ có | Tính lại độc lập Tm, ΔG, hairpin, dimer, bound fraction |
| `ponytail:ponytail-audit` | ✅ có | Tìm over-engineering (ENG-02) |
| Graphify | ❌ **không cài** | Bỏ qua; luồng dữ liệu truy bằng grep + chạy trực tiếp pipeline |
| agent-skills (`code-review-and-quality`, `security-and-hardening`, `frontend-ui-engineering`, `doubt-driven-development`) | ❌ **không có trong phiên** | Thay bằng tự phản biện thủ công cho mọi mục CRITICAL (mục 6) |
| alphaXiv MCP | ⚠ cần OAuth | Không dùng (cũng không phải nguồn y sinh) |
| Claude Docs, Consensus | có | Không dùng — yêu cầu là file `.md` cục bộ |

Mọi con số tái lập được bằng các lệnh ở Phụ lục A.

---

## 1. Tóm tắt điều hành — 5 phát hiện quan trọng nhất

1. **Analyzer giả định cứng overhang 6 nt, nên chẩn đoán sai mọi RT primer có overhang khác 6 nt.** Với một S có body chuẩn 44 nt + overhang 5 nt bắt cặp hoàn hảo, Analyzer (`/api/analyze`) báo *"chỉ 3/6 nt bắt cặp — overhang sai"*, vì nó cắt nhầm 1 nt của body vào overhang (SCI-01, **CRITICAL**). Lỗi được tái hiện bằng bộ primer miR-16, nhưng không phụ thuộc vào miRNA đó: mọi overhang 4, 5, 7 hay 8 nt đều bị đọc sai.
2. **"Binding occupancy" của vùng đặc hiệu F được tính ở 42 °C (nhiệt độ RT), một bước mà F không tham gia.** Ở nhiệt độ annealing thật (60 °C, Chen 2005), vùng đặc hiệu 12 nt chỉ bám **~2%**, trong khi UI hiển thị ~49–93% và chấm "optimal ≥80%" (SCI-02, **CRITICAL** — số liệu sai mà người dùng không biết). *Ở phiên trước tôi đã giải thích con số 42 °C này như thể hợp lý. Đó là sai sót của tôi.*
3. **Hairpin của stem-loop RT primer (một oligo DNA) được tính bằng tham số RNA (Turner 2004) ở 37 °C.** Ví dụ với một S (miR-16): RNA −27.1 kcal/mol; DNA −14.9 ở 37 °C, −13.1 ở 42 °C, −22.4 ở 16 °C. Tool hiển thị "MFE −28 kcal/mol" như ΔG thật và không đánh giá ở nhiệt độ RT (SCI-04, HIGH). Tiêu chí này chiếm 14% trọng số nhưng **không đổi giữa các candidate của cùng một miRNA**, nên không ảnh hưởng xếp hạng.
4. **Quy tắc "overhang cố định 6 nt" không được thực thi.** UI cho chọn 5/6/7 nt, backend chấp nhận 4–8 nt, trong khi `/api/visualize` hardcode 6. Kết quả: thiết kế 5 hoặc 7 nt bị trả **422 `RT_PRIMER_LENGTH`** (đã kiểm chứng bằng chạy thật) (SCI-08, HIGH, xung đột spec↔code).
5. **Tm và salt correction nhạy với Mg²⁺ nhưng được trình bày như một con số chắc chắn.** Cùng một amplicon 58 bp, Tm dự đoán tăng **~3 °C** khi Mg²⁺ đi từ 1.5 lên 3 mM, trong khi UI chỉ hiện một con số. Công thức Tm amplicon là một tổ hợp chưa được công bố: hệ số Marmur 16.6 ghép với Na_eq của von Ahsen. Spec ghi "Owczarzy 2004 salt correction" nhưng code dùng mặc định `santalucia` của primer3; ở Mg 3 mM mặc định này cao hơn Owczarzy 2008 khoảng ~2 °C (SCI-06, SCI-07).

**Những gì đúng (ngắn gọn):**
- Mg²⁺ và dNTP có được truyền vào primer3 (`thermodynamics.py:53-66`).
- F được báo **cả hai Tm** (binding region và full primer).
- BLAST dùng `blastn-short`, word_size 7, e-value 30000, reward/penalty 1/−1 theo Primer-BLAST (Ye 2012); không có lỗ injection.
- LNA dùng doublet SL98/McTigue04/Owczarzy11, ΔTm tính cùng engine (A5: có thật trong code).
- Nhãn "Simulated — not experimental data" được nhúng vào mọi SVG/PNG.

---

## 2. Bảng phát hiện

Mức: **CRITICAL** = cho ra primer sai hoặc số liệu sai mà người dùng không biết · HIGH · MEDIUM · LOW. Công sức: S (<½ ngày) / M (1–3 ngày) / L (>3 ngày).

### 2.1 Khoa học (Phần A)

| ID | Loại | Mức | Bằng chứng | Cơ sở khoa học | Đề xuất sửa | Công sức | Tin cậy |
|---|---|---|---|---|---|---|---|
| **SCI-01** | SAI | **CRITICAL** | `routes/analyze.py:108-150` `_context_checks` dùng `OVERHANG_LENGTH_DEFAULT`=6 cố định. Tái hiện bằng một S 49 nt (body 44 + overhang 5 nt `CGCCA`, lấy từ case study miR-16): `observed=CCGCCA, expected=CGCCAA, match_count=3, matches=False`, "A mismatched overhang reduces RT priming", `hybrid_tm_c=31.7` tính trên 6-mer sai. Cùng output lại có `starts_with_stemloop_body=True`, tức là độ dài overhang **suy ra được** nhưng bị bỏ qua. | Chen 2005 (PMID 16314309): overhang = bổ sung với đầu 3′ của miRNA | Khi `rt.startswith(STEMLOOP_BODY)`: đặt `overhang = rt[len(BODY):]`, so với `rc(mature[-len(overhang):])`. Báo "overhang X nt (ngoài chuẩn 6 nt)" thay vì "mismatch". Thêm test hồi quy với S tổng hợp có overhang 5 và 7 nt. | S | Cao |
| **SCI-02** | SAI | **CRITICAL** | `constants.py:336` `BOUND_FRACTION_RT_TEMP=42.0`, "Round 1: specific region binds cDNA during RT"; `bound_fraction.py:111-115`. Tính lại cho vùng đặc hiệu miR-16: 12 nt → **49.4% @42 °C, 5.5% @55, 2.0% @60**; 14 nt → 74.4 / 9.5 / 3.0%. UI miR-221 hiển thị "92.6% at 42 °C (RT extension step) … optimal ≥80%". | Chen 2005: RT và PCR là hai bước riêng; F chỉ có mặt trong PCR, annealing 60 °C. Bound fraction (SantaLucia & Hicks 2004, PMID 15139820) phải tính ở nhiệt độ của đúng bước lai. | Tính ở `annealingTemp` của người dùng (mặc định 60 °C). Đổi nhãn thành "Cycle-1 occupancy (specific region vs cDNA)". Trọng số giữ nguyên (quy tắc chốt), nhưng số liệu và nhãn phải đúng. | S | Cao |
| SCI-03 | SAI | MEDIUM | `stemloop_rt.py:~288`: fallback cuối trả `-11.5, "N/A", "default (all MFE libraries unavailable)"`, rồi `scoring.py:105-122` chấm điểm như giá trị thật. | Vi phạm nguyên tắc "không bịa số liệu" của dự án | Trả `None`, loại tiêu chí khỏi tổng (renormalize), hiện lỗi rõ. Xác suất xảy ra thấp vì primer3 là dependency cứng. | S | Cao |
| **SCI-04** | SAI | HIGH | `stemloop_rt.py:245` `_RNA.fold(rna_str)` → tham số RNA Turner 2004, 37 °C, trên oligo DNA. Tính lại S miR-16 (ViennaRNA 2.7): RNA −27.10; **DNA −14.90 @37, −13.06 @42, −10.59 @50, −22.41 @16 °C**. | ViennaRNA 2.0 (Lorenz 2011, PMID 22115189): mặc định là tham số RNA Turner 2004. Nhiệt động học motif DNA: SantaLucia & Hicks 2004 (PMID 15139820). | `RNA.params_load_DNA_Mathews2004()`, gập ở nhiệt độ RT thực (16/42/50 °C theo enzyme). Chỉ đổi thang điểm nếu được phép (mục 7). Tối thiểu: đổi nhãn thành "RNA-parameter proxy". | S | Cao |
| SCI-05 | SAI | LOW | `stemloop_rt.py:279` (chỉ ở nhánh fallback primer3) dùng `saltConcentration` (Na⁺ thuần), khác `effective_monovalent_mM` (Na⁺+K⁺+Tris⁺ ≈ 103 mM) của F/UR/probe. Nhánh chính `tm_full` (`:56`) dùng `calculate_tm_nn`, nên nhất quán. | Quy tắc chốt: không trộn engine | Dùng `_get_p3_params(params)` ở dòng 279 | S | Cao |
| **SCI-06** | SAI / xung đột spec | MEDIUM | `SPEC_phase2.md:331,1506` ghi "Owczarzy 2004 salt correction for Mg²⁺". Code dùng primer3 mặc định `salt_corrections_method='santalucia'` + von Ahsen (`thermodynamics.py:4`). Tính lại (mono 103 mM, dNTP 0.8, 200 nM), chênh `owczarzy − santalucia`: −0.3…−0.9 °C @Mg 1.5, **−1.6…−2.2 °C @Mg 3.0**. | Owczarzy 2004 (PMID 15035624) chỉ hiệu chỉnh **Na⁺**. Mô hình Mg²⁺ là Owczarzy 2008 (PMID 18422348), tối ưu cho điều kiện PCR 1.5–5 mM Mg. von Ahsen 2001 (PMID 11673362). | Sửa trích dẫn trong spec. Cân nhắc `salt_corrections_method='owczarzy'`. **Không tự đổi**: ảnh hưởng mọi Tm và điểm, cần quyết định và chạy lại benchmark. | S (spec) / M (code) | Cao |
| **SCI-07** | SAI | MEDIUM | `thermodynamics.py:115-131`: `81.5 + 0.41·GC − 600/N + 16.6·log10[Na_eq]` với Na_eq theo von Ahsen. Ví dụ amplicon 58 bp, GC 56.9%: tool 80.8 °C @Mg 1.5; 83.1 @2.5; 83.8 @3.0. primer3 NN full-duplex: 81.6 @Mg 1.5, 83.9 @Mg 3. UI chỉ hiện một giá trị, không nêu độ nhạy theo Mg. | von Ahsen 2001 (PMID 11673362) tự fit công thức thực nghiệm **cho Na_eq**: `77.1 + 11.7·log[Na_eq] + 0.41·GC − 528/bp` (SE 1.87 °C, trên oligo). Tool ghép hệ số Marmur (Marmur & Doty 1962, PMID 14470099) với Na_eq → tổ hợp chưa công bố. Hai công thức cho kết quả gần nhau ở Na_eq cao. | Hiển thị **dải** Tm theo Mg (1.5–3 mM) thay vì một con số; ghi nguồn. Độ chính xác tuyệt đối chỉ đánh giá được bằng nhiều assay (mục 4). | S | Cao (về độ nhạy Mg) / chưa đánh giá (về sai số tuyệt đối) |
| **SCI-08** | SAI / xung đột spec | HIGH | Quy tắc chốt "overhang 6 nt". `constants.py:17-18` MIN=4, MAX=8; `stemloop_rt.py` đọc `params["bindingRegion3prime"]`; `PrimerConstraintsGroup.jsx:227` cho chọn [5,6,7]; `visualization/constants.py` `RT_OVERHANG=6`. Chạy thật: overhang 5 → S 49 nt → visualize **REJECTED RT_PRIMER_LENGTH**; 7 → REJECTED; 6 → OK. | Chen 2005 |  cho `coordinates.py` nhận độ dài overhang biến đổi. Quyết định thuộc về chủ dự án. | S | Cao |
| **SCI-09** | UX-SAI | HIGH | `DetectionMethodGroup.jsx:173-175` toggle "Check cross-reactivity with pre-miRNA" có **0 tham chiếu trong backend**. `PRECURSOR_CT_OFFSET_MIN`, `PRECURSOR_SIGNAL_CONTRIBUTION` (`constants.py:418-419`) cũng không được dùng. Tooltip: "Steric hindrance normally prevents stem-loop primers from binding pre-miRNA". | Chen 2005 chứng minh phân biệt mature/precursor **cho các miRNA đã thử**. Tổng quát hóa cho mọi miRNA (đặc biệt miRNA nhánh 3p, có đầu 3′ gần trùng pre-miRNA) là **GIẢ THUYẾT CHƯA KIỂM CHỨNG**. | Gỡ toggle hoặc hiện thực nó. Sửa tooltip: "đã chứng minh cho … (Chen 2005), chưa kiểm chứng tổng quát". | S | Cao (dead code) / Trung bình (khoa học) |
| **SCI-10** | THIẾU | MEDIUM | `stemloop_rt` trả `three_prime_isomir` từ tập tham chiếu chỉ **7 mục** ("partial coverage"). miR-221: "no entry". | Nejad 2018 *RNA* (PMID 29263133): stem-loop TaqMan RT-qPCR **chọn lọc giữa các 3′ isoform theo độ dài**, có thể dẫn đến diễn giải sai. | Dùng dữ liệu isomiR có hệ thống (vd. small-RNA-seq công khai) để cảnh báo miRNA có nhiều 3′ isomiR. Giữ 5′ isomiR ở mức cảnh báo (quy tắc chốt). Xem mục 7. | M–L | Trung bình |
| **SCI-11** | THIẾU | HIGH | NTC/no-RT chỉ là dòng checklist trong export (`routes/export.py:277,284,688,691`). Không có bảng control bắt buộc kèm kết quả mong đợi, không cảnh báo nhiễm cho miRNA dồi dào, không diễn giải NTC sau khi chạy. | MIQE (PMID 19246619) và MIQE 2.0 (PMID 40272429) yêu cầu báo cáo NTC/no-RT. Melt curve phân biệt sản phẩm (Ririe 1997, PMID 9056205). | Module "Controls & contamination": (1) bảng control (NTC-nước, NTC chỉ primer, RT-NTC, no-RT) kèm tiêu chí đạt; (2) cờ "miRNA dồi dào → nguy cơ nhiễm cao"; (3) trang diễn giải nhận Cq/Tm của mẫu, NTC, no-RT. | M | Cao (đang thiếu) |
| SCI-12 | SAI | MEDIUM | `lna_tm.py` dùng NN SL98 riêng. Baseline DNA **thấp hơn primer3 2.8–3.0 °C** trên 3 primer thử (54.9 vs 57.7; 53.5 vs 56.5; 57.1 vs 60.0). `LnaPanel/index.jsx:159-163` hiển thị Tm tuyệt đối "DNA 54.9 °C / +LNA …" cạnh Tm thiết kế 57.7 °C của primer3. | ΔTm cùng engine → nhất quán (quy tắc chốt được giữ ✓). McTigue 2004 (PMID 15122905), Owczarzy 2011 (PMID 21928795). | Hiển thị `Tm_primer3 + ΔTm_LNA`, hoặc chỉ ΔTm, kèm ghi chú engine. | S | Cao |
| SCI-13 | SAI (nhãn) | LOW | Analyzer: cả 3 cặp dimer đều ghi "Hetero-dimer (forward + reverse)". RT self-dimer `dg_overall=-7.31, pass_overall=False` nhưng note ghi "within acceptable range". Dimer này đến từ stem của body, giống nhau ở mọi assay. | — | Sửa nhãn theo từng cặp; loại trừ tương tác stem–stem đã biết, hoặc giải thích. | S | Cao |
| SCI-14 | Đề xuất | LOW | `mfe_stemloop` 14% trọng số, nhưng S = body cố định + overhang → **cùng giá trị cho mọi candidate của một miRNA** → không phân biệt được xếp hạng, chỉ đổi grade. | — | Xem mục 7 (trọng số là quy tắc chốt). | — | Cao |

### 2.2 Kỹ thuật (Phần B)

| ID | Loại | Mức | Bằng chứng | Đề xuất | Công sức | Tin cậy |
|---|---|---|---|---|---|---|
| **ENG-01** | THIẾU (tái lập) | MEDIUM | `design_pipeline.py:444` hardcode `algorithm_version: "3.0.0"`. Commit `db3abd7` đổi RNG làm output forward tail thay đổi, nhưng version giữ nguyên → **hai kết quả khác nhau mang cùng một nhãn version**. Metadata không ghi phiên bản primer3/ViennaRNA/BLAST+. Overhang index có `mirbase_release: "unknown"`. | Bump version khi output đổi. Ghi `primer3`, `ViennaRNA`, `blast+`, miRBase release, hash của `SCORING_WEIGHTS` vào metadata và export (MIQE 2.0 §1). | S | Cao |
| ENG-02 | Over-engineering | LOW | `ponytail-audit`: **60/229 hằng số (26%) không được tham chiếu** (vd. `SCORING_WEIGHTS`, `SCORING_WEIGHTS_V2`, 14 `PENALTY_WT_*`, 7 `PROBE_*`, 6 `IDT_*`, `LNA_TARGET_TM_DEFAULT`, `LNA_MAX_SUBSTITUTIONS`). 10 trường form backend không đọc: `enablePrecursorCheck`, `enableFamilyDiscrimination`, `totalCycles`, `pcrEfficiencyMin/Max`, `exportFormat`, `qpcrSystem`, `rtEnzyme`, `referenceGene`, `quantMode` (một số chỉ dùng cho ghi chú phía frontend). | `delete:` các hằng số chết. `delete:` các toggle không có tác dụng — nhất là `enableFamilyDiscrimination`: người dùng tắt nhưng check vẫn chạy. Việc `LNA_*` không được dùng cho thấy module LNA tự hardcode giá trị riêng → rủi ro lệch. | S | Cao |
| ENG-03 | THIẾU / xung đột bối cảnh | MEDIUM | Bối cảnh dự án ghi "IndexedDB session history", nhưng `grep indexedDB` trên `frontend/src` cho **0 kết quả**. Memory dự án: "B4 = IndexedDB decided; pending". | Cập nhật tài liệu, hoặc hiện thực B4. | M | Cao |
| ENG-04 | OK | — | BLAST: `constants.py:529-534`. `subprocess.run` dạng list, không `shell=True` (`blast_offtarget.py:258`); input validate `ACGTN` ≤60 nt (`routes/blast_check.py:58-64`); rate limit 10/phút (`app.py:58`); circuit breaker; cache khóa theo `db_version`. Không có endpoint upload. | Chưa kiểm: giới hạn kích thước body (`MAX_CONTENT_LENGTH`) → đề xuất đặt. | S | Cao / (phần chưa kiểm: thấp) |
| ENG-05 | Xung đột tài liệu | LOW | `CLAUDE.md` ghi "Flask 3 + flask-cors + requests — không thêm dependency khác", nhưng `requirements.txt` có thêm primer3-py, biopython, numpy, flask-limiter, ViennaRNA. | Cập nhật CLAUDE.md | S | Cao |
| ENG-06 | SAI nhỏ | LOW | `constants.py:258`: Tris pKa 8.06 @25 °C được dùng cho mọi nhiệt độ, trong khi pKa của Tris phụ thuộc mạnh vào nhiệt độ (**CHƯA KIỂM CHỨNG** hệ số qua PubMed). Tris 10 mM chỉ đóng góp ≤10 mM monovalent. | Ghi chú giả định, hoặc bỏ Tris khỏi Na_eq | S | Trung bình |
| ENG-07 | Hiệu năng | LOW | BLAST đồng bộ: lần đầu ~6 s, cache 0.2 s (đo trong phiên). Client timeout 65 s, backend 60 s. | Chấp nhận được với spinner. Chỉ cần hàng đợi job khi có batch. | — | Cao |

### 2.3 UI/UX (Phần C)

| ID | Loại | Mức | Bằng chứng | Đề xuất | Công sức |
|---|---|---|---|---|---|
| UX-01 | UX | MEDIUM | `SequenceGroup.jsx` `validateSequence`: gặp `T` thì báo lỗi "use 'U' instead of 'T'" thay vì tự chuyển | Tự đổi T→U, kèm thông báo nhẹ | S |
| UX-02 | THIẾU | MEDIUM | `index.html` `lang="en"`, không có i18n | Song ngữ VI–EN cho nhãn, cảnh báo và hướng dẫn hành động (giữ thuật ngữ chuyên ngành) | M |
| UX-03 | UX | MEDIUM | Có 15 tiêu chí nhưng **không có câu tóm tắt "vì sao #1 hơn #2"** bằng ngôn ngữ của người làm wet-lab | 1–2 câu so sánh tự động dựa trên các tiêu chí chênh lệch lớn nhất | S |
| UX-04 | UX | MEDIUM | Trang Advanced có 10 control không tác dụng (ENG-02) và nhiều thuật ngữ (GC skew, Kwok, bound fraction, MFE) | Bỏ control chết; đưa thuật ngữ vào tooltip hoặc "details" | S |
| UX-05 | THIẾU | LOW-MED | Export có PDF, CSV, FASTA; chưa có định dạng đặt hàng IDT bulk/plate hay Macrogen | Thêm template đặt hàng theo nhà cung cấp phổ biến ở VN | S |
| UX-06 | UX | LOW | Nhãn "Simulated from predicted values — not experimental data" đã nhúng trong SVG/PNG (`renderer.py:331,427`) ✓, nhưng tên file tải về `${mirnaId}_${tab}.png` không chứa chữ "simulated" | Đổi thành `…_SIMULATED.png`; thêm watermark mờ chéo cho PNG | S |
| UX-07 | OK / chưa kiểm | — | Tương phản WCAG AA: 0 vi phạm sau thay đổi hôm nay (đo bằng công thức WCAG). **Chưa kiểm**: điều hướng bàn phím toàn trang, responsive < 768 px | Chạy audit bàn phím + mobile | M |
| UX-08 | OK | — | Input nhận tên, miRBase ID hoặc trình tự; có autocomplete; cảnh báo phân mức (critical/warning/info) kèm giải thích | — | — |

---

## 3. Case study miR-16 (exp 220826) — chỉ để minh họa

Bộ primer và dữ liệu miR-16 được xem là **một ví dụ đơn lẻ, không đủ chính xác để xây dựng hay hiệu chỉnh thuật toán**. Audit chỉ rút ra từ nó những gì là lỗi code tổng quát, không chẩn đoán thí nghiệm.

**Đã dùng case study vào việc gì:**
- Làm input tái hiện SCI-01: một S có overhang 5 nt bị Analyzer đọc sai thành "3/6 mismatch". Lỗi này đúng với mọi overhang ≠ 6 nt, không riêng miR-16.
- Làm ví dụ số cho SCI-04 (hairpin RNA vs DNA params) và SCI-07 (độ nhạy Tm theo Mg²⁺). Các kết luận đó dựa trên code và mô hình nhiệt động, không dựa trên số đo của thí nghiệm.

**Không kết luận gì về:** nguyên nhân NTC, chất lượng mẫu q2, sai số tuyệt đối của Tm dự đoán so với melt thực, hay độ dài overhang thực tế đã đặt hàng. Các câu hỏi này cần dữ liệu wet-lab, không phải tính toán.

**Ghi nhận tổng quát (không riêng miR-16):**
- Primer-dimer được tool đánh giá đúng cách (ΔG đầu 3′, `pass_3prime`). Nhưng tool **không có** module nào về control hay nhiễm (SCI-11): NTC/no-RT chỉ là một dòng checklist trong export. Với miRNA dồi dào, đây là khoảng trống thật.

---

## 4. Mục cần kiểm chứng wet-lab (tính toán không thể kết luận)

Các mục dưới đây cần dữ liệu từ **nhiều assay**; một case study đơn lẻ không đủ để kết luận.

1. **Hiệu chỉnh Tm amplicon (SCI-07):** cần ≥5 bộ (trình tự amplicon, melt Tm, master mix với Mg²⁺/monovalent đã biết) để đo sai số hệ thống của công thức.
2. **Hiệu suất RT theo độ dài overhang (5/6/7 nt)** và khả năng phân biệt 3′ isomiR (Nejad 2018 cho thấy có chọn lọc theo độ dài). Đây là dữ liệu cần để quyết định quy tắc 6 nt ở mục 7.
3. **Phân biệt mature và pre-miRNA** cho miRNA nhánh 3p (SCI-09), dùng pre-miRNA tổng hợp.
4. **Standard curve** (hiệu suất 90–110%), no-RT, NTC, melt curve — theo MIQE 2.0, làm đầu vào cho module Controls (SCI-11).
5. **Dữ liệu calibrate `SCORING_WEIGHTS`**: phải là dữ liệu tự sinh của lab trên nhiều miRNA, không lấy từ một thí nghiệm.

---

## 5. Lộ trình sửa (tác động khoa học / công sức)

| Ưu tiên | Mục | Công sức | Gắn với |
|---|---|---|---|
| 1 | SCI-01 Analyzer đọc đúng độ dài overhang + test hồi quy với overhang 5/7 nt tổng hợp | S | Module analyze / Phase 4 |
| 2 | SCI-02 Bound fraction ở Ta thật + sửa nhãn | S | SPEC_phase2 §bound_fraction (v2.8.x) |
| 3 | SCI-08 Khóa 6 nt, hoặc cho visualization nhận độ dài overhang biến đổi | S | SPEC_visualization §A + quy tắc chốt |
| 4 | SCI-09 + ENG-02 Gỡ toggle chết (precursor, family), sửa tooltip | S | Phase 4 UI |
| 5 | ENG-01 Version + phiên bản thư viện/DB trong metadata và export | S | Phase 7 (MIQE export) |
| 6 | SCI-12 Hiển thị LNA = Tm primer3 + ΔTm | S | Phase 8 |
| 7 | SCI-06/07 Dải Tm theo Mg; sửa trích dẫn trong spec; quyết định dùng Owczarzy 2008 | S → M | Phase 5 PART D |
| 8 | SCI-04 Hairpin của S dùng tham số DNA, ở nhiệt độ RT | S | SPEC_phase2 stemloop_rt |
| 9 | SCI-11 Module Controls & Contamination | M | Phase 7 (protocol advisor) |
| 10 | SCI-10 Dữ liệu 3′ isomiR có hệ thống | M–L | SPEC_week2 isomiR |
| 11 | UX-01..05 | S–M | Phase 4 UI |
| 12 | ENG-03 IndexedDB (B4) | M | Gap B |

---

## 6. Tự phản biện — 3 kết luận tôi kém chắc chắn nhất

1. **SCI-07 (Tm amplicon)**: điều tôi khẳng định được là **độ nhạy theo Mg²⁺ (~3 °C trong dải 1.5–3 mM) lớn hơn mức chính xác mà UI ngụ ý**, và công thức là tổ hợp chưa công bố. Tôi **không** khẳng định tool có sai số hệ thống so với thực nghiệm; điều đó cần nhiều assay (mục 4.1).
2. **SCI-09 (phân biệt pre-miRNA)**: tôi cho rằng tooltip đang tổng quát hóa quá mức kết quả của Chen 2005. Nhưng tôi chưa tìm được nghiên cứu nào đo có hệ thống việc này trên miRNA nhánh 3p, nên đây vẫn là nghi vấn, chưa phải lỗi đã chứng minh.
3. **Mức CRITICAL của SCI-02**: con số hiển thị chắc chắn được tính ở sai nhiệt độ, nhưng tác động lên **xếp hạng** nhỏ (trọng số 5%, và cả hai cách tính đều ưu tiên vùng đặc hiệu dài hơn). Nếu hội đồng định nghĩa CRITICAL là "làm đổi primer được chọn", mục này nên hạ xuống HIGH. Tôi giữ CRITICAL theo định nghĩa của nhiệm vụ ("số liệu sai mà người dùng không biết").

*Lưu ý quy trình: bước "doubt-driven-development" được làm thủ công, vì agent-skills không có trong phiên.*

---

## 7. Đề xuất xem xét lại quy tắc đã chốt (không tự thay đổi)

| Quy tắc | Bằng chứng khiến nghi ngờ | Đề xuất |
|---|---|---|
| Overhang cố định 6 nt | Code và UI thực tế **không** cố định (SCI-08). Trong thực tế có bộ primer dùng 5 nt (case study miR-16) và tài liệu có bộ 7 nt (Zhao 2014, nằm trong reference set). | Chủ dự án chọn:  chính thức hóa dải 5–7 nt kèm cảnh báo |
| 5′ isomiR chỉ là cảnh báo | Hợp lý. Nhưng **3′ isomiR** tác động trực tiếp lên overhang (Nejad 2018, PMID 29263133) và hiện chỉ có 7 mục dữ liệu. | Giữ 5′ ở mức cảnh báo; tăng độ phủ dữ liệu 3′ (vẫn ở mức cảnh báo) |
| Không đổi `SCORING_WEIGHTS` | `mfe_stemloop` 14% không phân biệt được các candidate cùng miRNA (SCI-14). "Binding occupancy" tính ở sai nhiệt độ (SCI-02). | Không đổi trọng số; sửa **đầu vào** của tiêu chí; ghi nhận SCI-14 cho lần calibrate bằng dữ liệu wet-lab |
| Không trộn engine | Được giữ ở LNA ΔTm ✓. Vi phạm nhẹ ở fallback `stemloop_rt.py:279` (SCI-05) và ở phần hiển thị Tm tuyệt đối của LNA (SCI-12). | Giữ quy tắc; sửa hai điểm trên |

---

## 8. Xung đột spec ↔ code (báo ngay)

1. **Overhang 6 nt** (CLAUDE.md; SPEC_phase2:1072, 2848) ↔ UI 5/6/7, backend 4–8 (SCI-08).
2. **"Owczarzy 2004 salt correction"** (SPEC_phase2:331, 1506) ↔ code dùng primer3 `santalucia` + von Ahsen; hơn nữa Owczarzy 2004 không phải mô hình Mg (SCI-06).
3. **IndexedDB session history** (bối cảnh nhiệm vụ) ↔ không có trong code (ENG-03).
4. **Stack cố định** (CLAUDE.md) ↔ requirements thực tế (ENG-05).
5. Bối cảnh nhiệm vụ ghi "`SPEC_phase2.md` (Phase 3–8)", nhưng repo có các file riêng `SPEC_phase3.md`…`SPEC_phase8.md`, còn SPEC_phase2 là v2.8.3 của Phase 2. Audit này đọc SPEC_phase2 và SPEC_visualization theo yêu cầu, **chưa đọc đầy đủ** SPEC_phase3–8.
6. SPEC_phase2:183 gọi ViennaRNA là "gold standard cho RNA secondary structure", nhưng lại áp cho oligo DNA bằng tham số RNA (SCI-04).

---

## 9. Phạm vi chưa phủ

- Chưa đọc hết SPEC_phase3–8 và SPEC_week1/2 (chỉ đối chiếu các điểm liên quan).
- Chưa audit bàn phím/responsive toàn app; chưa kiểm `MAX_CONTENT_LENGTH`.
- Chưa đo độ nhạy BLAST bằng bộ dương tính đã biết.
- Chưa tính lại probe TaqMan.
- Không chẩn đoán thí nghiệm miR-16 (NTC, mẫu q2) — ngoài phạm vi theo phản hồi của chủ dự án.

---

## 10. Trạng thái xử lý (cập nhật 2026-09-19, algorithm v3.1.0)

Sau khi chủ dự án quyết định các điểm mở, code đã được sửa theo audit. Mọi mục dưới đây có test hồi quy (`backend/tests/test_audit_fixes.py` và các test cập nhật) — **fail trên code cũ, pass trên code mới**.

**Quyết định của chủ dự án:**
- Overhang: **6 nt mặc định; 5 và 7 nt được hỗ trợ chính thức** kèm cảnh báo off-label; ngoài 5–7 → HTTP 400. (Quy tắc "cố định 6 nt" cũ được thay thế; CLAUDE.md và SPEC đã cập nhật.)
- SCI-02: occupancy tính ở Ta, chỉ hiển thị, **không chấm điểm**.
- SCI-04: tham số DNA + ngưỡng tính lại cùng cách.
- SCI-06: **giữ** `santalucia`, chỉ sửa trích dẫn spec.
- SCI-09: gỡ toggle, sửa tooltip.
- SCI-10: dữ liệu từ **isomiRdb** (PMID 36243964).
- SCI-11: làm phần 1 + 2, xuất vào PDF; ΔCq(NTC − mẫu) ≥ 10; danh sách synthetic control để trống.
- Hoãn: UX-02 (song ngữ), UX-05 (mẫu đặt hàng — cần file mẫu thật của nhà cung cấp).

| ID | Trạng thái | Đã làm |
|---|---|---|
| SCI-01 | ✅ Đã sửa | Analyzer đọc độ dài overhang từ mồi (`len(S) − 44`), báo "X nt, ngoài chuẩn 6 nt" thay vì "mismatch"; nhận diện universal reverse biến thể nằm trong body (vd. 18 nt). |
| SCI-02 | ✅ Đã sửa | Occupancy vùng đặc hiệu tính ở Ta của người dùng (≈2–10 %), gắn nhãn "Cycle-1 occupancy", không chấm điểm (`UNSCORED_CRITERIA_V4`); tổng điểm renormalize theo tiêu chí thực sự chấm. `SCORING_WEIGHTS_V4` giữ nguyên. |
| SCI-03 | ✅ Đã sửa | Không còn giá trị −11.5 bịa: thiếu engine → MFE = None, loại khỏi tổng, cảnh báo rõ. |
| SCI-04 | ✅ Đã sửa | ViennaRNA tham số DNA (Mathews 2004, 37 °C), không ảnh hưởng tham số RNA toàn cục; ngưỡng −19.5/−11.1/−14.5 kcal/mol suy ra cùng cách với ngưỡng RNA cũ (ghi trong `constants.py`). RNAfold fallback dùng `-P DNA`. |
| SCI-05 | ✅ Đã sửa | Fallback primer3 dùng `_get_p3_params` (Na⁺+K⁺+Tris⁺). |
| SCI-06 | ✅ Đã sửa (tài liệu) | SPEC_phase2 (5 chỗ) + SPEC_week1: trích dẫn đúng von Ahsen 2001 / primer3 `santalucia`. Code không đổi theo quyết định. |
| SCI-07 | ✅ Đã sửa | Tm amplicon kèm dải theo Mg²⁺ 1.5–3 mM (`predicted_amplicon_tm_mg_span`), hiển thị ở tab Melting. |
| SCI-08 | ✅ Đã sửa | Dải 5–7 nt thực thi ở API (400), thuật toán, recommender (trần 7), visualization (đọc từ mồi; `_RENDER_VERSION` = 3). |
| SCI-09 | ✅ Đã sửa | Gỡ toggle pre-miRNA và toggle family (check luôn chạy); UI nêu rõ giới hạn. |
| SCI-10 | ✅ Đã làm | Dữ liệu từ isomiRdb (PMID 36243964), dựng bằng `backend/scripts/build_isomir_3prime_index.py`. Tỷ lệ 3′ tính trên **đủ 42.494/42.494 mẫu** (cập nhật 2026-10-22, algorithm v3.1.1; trước đó chỉ 20.635 mẫu, serum 3 %, plasma 11 %, blood 19 %). Nguyên nhân cũ: nginx của isomiRdb cắt phản hồi ở ≈1 GiB khi máy khách tải chậm (~0,3 MB/s); dùng ma trận read-count (1,2 GB) tải riêng ở ~2 MB/s thì nhận trọn file, đổi sang RPM theo từng mẫu bằng Σ miRNA_RPM / Σ miRNA_RC — trên 20.635 mẫu đầu cho kết quả trùng bản RPM cũ ở 2.624/2.655 miRNA (còn lại lệch 1 bin 0,005). Độ dồi dào (cho SCI-11) tính trên bảng miRNA đầy đủ (2.655 miRNA × 42.494 mẫu). Kết quả: 2.032 miRNA có dữ liệu 3′; 500 ≥50 % → cảnh báo, 298 mức trung bình. Ví dụ: miR-221-3p **84 %** (IQR 74–92 %), miR-155-5p 84 %, miR-451a 76 %, miR-21-5p 49 %, miR-16-5p 23 %. Cảnh báo ghi rõ biến thể ±1 nt chỉ giảm (không mất) hiệu suất bắt RT. *Đính chính audit:* file dữ liệu cũ **rỗng**, không phải 7 mục như tôi ghi ở SCI-10. |
| SCI-11 | ✅ Phần 1+2 (theo quyết định) | Mục "Controls & Contamination" trong PDF export: bảng control riêng cho từng assay (NTC, RT-NTC, no-RT, control dương bằng synthetic RNA đúng trình tự mature, pre-miRNA tùy chọn), tiêu chí NTC **ΔCq ≥ 10** (quy ước HG Lab, cũng áp vào checklist thay cho "≥5 chu kỳ" chưa kiểm chứng); SYBR: so đỉnh melt NTC với control dương cùng plate. Rủi ro nhiễm: miRNA thuộc top 5 % về độ dồi dào (isomiRdb) hoặc nằm trong danh sách synthetic control của lab (`data/lab_controls.json`, đang để trống) → "elevated" + khuyến nghị NTC lặp ba. Lịch sử thiết kế trong trình duyệt chỉ là ghi chú nhắc carry-over, không nâng mức rủi ro. Phần 3 (trang diễn giải sau khi chạy) chưa làm. |
| SCI-12 | ✅ Đã sửa | LNA hiển thị Tm primer3 + ΔTm; mục tiêu Tm được quy về hệ quy chiếu của engine LNA (trước đó LNA bị gợi ý dư ~3 °C). |
| SCI-13 | ✅ Đã sửa | Nhãn dimer theo đúng cặp; note nhất quán với `pass_overall`; giải thích dimer stem–stem của mồi stem-loop. |
| SCI-14 | Ghi nhận | Chờ dữ liệu wet-lab để calibrate (trọng số khóa). |
| ENG-01 | ✅ Đã sửa | `ALGORITHM_VERSION` = 3.1.0; metadata + export ghi phiên bản primer3-py/ViennaRNA/Python, hash bảng trọng số; miRBase release ghi "unknown" (không đoán). ViennaRNA pin 2.7.2. |
| ENG-02 | ✅ Đã sửa | Xóa 56 hằng số chết (giữ các bảng trọng số cũ vì quy tắc khóa); nối `LNA_MAX_SUBSTITUTIONS`/`LNA_TARGET_TM_DEFAULT` vào route; các trường form "chết" giờ được ghi vào MIQE export (Ta, số chu kỳ, ngưỡng hiệu suất, quant mode, reference, instrument) hoặc bị gỡ (`exportFormat`, `rtEnzyme`). |
| ENG-03 | ✅ Đã làm | Lịch sử thiết kế IndexedDB (50 bản gần nhất, chỉ trên trình duyệt), trang `/history`. |
| ENG-04 | ✅ Đã sửa | `MAX_CONTENT_LENGTH` = 2 MB → 413. |
| ENG-05 | ✅ Đã sửa | CLAUDE.md: stack thực tế, lệnh chạy test. |
| ENG-06 | ✅ Ghi chú | Giả định pKa Tris 25 °C được ghi rõ trong `constants.py`. |
| UX-01 | ✅ Đã sửa | Dán DNA → tự đổi T→U kèm thông báo; trộn T và U → báo lỗi. |
| UX-03 | ✅ Đã làm | Câu "vì sao #1 hơn #2" (hoặc "gần như ngang nhau") dựa trên đóng góp điểm thực. |
| UX-04 | ✅ Một phần | Bỏ control chết; thuật ngữ còn lại giữ trong tooltip. |
| UX-06 | ✅ Đã sửa | Tên file tải về có `_SIMULATED`. Bỏ qua watermark chéo (nhãn đã nhúng trong hình). |
| UX-07 | ✅ Đã kiểm | 375 px: không trang nào tràn ngang (đã sửa navbar tràn). Bàn phím: mọi control hiển thị đều có focus ring. Label của 3 `<select>` đã gắn `htmlFor`. |

**Kiểm chứng:** backend 533 test pass; e2e Playwright 62/62 (trước: 36/62 — 26 spec lỗi thời từ đợt tách Basic/Advanced, đã cập nhật); validation 184/184; `npm run build` OK.

### 10.1 Bổ sung 2026-10-28 — BLAST off-target (bộ phân loại v2)

| ID | Trạng thái | Nội dung |
|---|---|---|
| BLAST-01 | ✅ Đã sửa | **BLAST không chạy khi đường dẫn có dấu cách** (vd. `D:\Users\TIEN VUONG\…`): `-db`/`-in`/`-out` của BLAST+ nhận danh sách cách nhau bằng dấu cách; mẹo rút gọn 8.3 thất bại trên ổ không phải ổ hệ thống (8.3 tắt mặc định từ Windows 10) → `/api/blast-check` trả 500. Nay: DB tìm qua biến `BLASTDB`, truy vấn qua stdin; `build_blast_db.py` chạy trong thư mục đích với tên trần. |
| BLAST-02 | ✅ Đã sửa | **Bảng Kwok 1990 tra sai mạch.** Kwok ghi cặp *mồi : mạch khuôn*, code so base mồi với base **sense** của off-target (cùng chiều với mồi) → nhãn BLOCKING/REDUCING lệch hẳn (vd. "A:G chặn" thực chất là A:C dung nạp; C:C không bao giờ nhận ra). Nay base khuôn = bổ sung của base sense. Lỗi có từ đợt sửa BLAST 2026-08. |
| BLAST-03 | ✅ Đã làm | **Cổng Tm duplex** thay luật neo 3′ tối thiểu 10 nt (vốn xếp CRITICAL các đoạn neo 12 nt có Tm ~22 °C). Mốc so sánh là **Tm đúng đích** của chính mồi, không phải Ta — xem SPEC_phase3 §8.13. Tm_off < Tm_on − 10 → SAFE; vùng xám → luật Ye/Kwok tối đa MEDIUM; Tm_off ≥ Tm_on − 5 → CRITICAL (HIGH nếu base cuối 3′ hở hoặc mismatch chặn). |
| BLAST-04 | ✅ Đã làm | Không BLAST mồi ngược universal (bám thân stem-loop, không bám miRNA). Khóa cache thêm phiên bản bộ phân loại + trình tự đích + điều kiện muối. |
| BLAST-05 | ✅ Dọn dẹp | Xóa DB Ensembl cDNA không dùng (189 MB); `metadata.json` ghi rõ miRBase **22.1**. |
| BLAST-06 | ⏸ Mở | miRBase đã lên **Release 23.1** (09/2026: 74.463 mature; 9.091 trình tự đổi đầu 5′/3′; 20.514 tên đổi; 10 tên trùng làm `makeblastdb -parse_seqids` lỗi). DB BLAST + chỉ mục family/overhang vẫn ở 22.1 để nhất quán; nâng cấp là mốc riêng. |

| BLAST-07 | ✅ Đã sửa (bộ phân loại v3) | **Nhận diện chính đích theo tên + trình tự.** Luật cũ so tên kiểu chuỗi con → `ssc-miR-21` coi `ssc-miR-210` là chính đích (che off-target thật); tên sai định dạng (`ssc-miR15a`) thì đích bị báo CRITICAL. Nay: tên khớp có ranh giới (`-`), và khi biết trình tự thì phải **tương thích** (giống hệt phần giao nhau, mỗi đầu lệch ≤ 2 nt) — ssc-miR-670 của miRBase 22.1 (trình tự khác hẳn bản Busk 2014) không còn bị coi là chính đích. Hit **khác tên** có trình tự giống hệt hoặc tương thích (bản sao ở locus khác như ath-miR156a…f; mục đổi tên như ssc-miR-20 → ssc-miR-20a-5p) được liệt kê trong nhóm `identical_sequence`, không phân loại rủi ro. Thêm tham số `species`. |

| ENG-08 | ✅ Đã sửa | **Backend sập (access violation) khi có yêu cầu đồng thời.** primer3-py 2.0.3 nhả GIL trong phần tính nhiệt động (thal) và dùng trạng thái toàn cục → hai luồng Flask tính cùng lúc làm sập cả tiến trình (vết faulthandler: `calc_homodimer` ‖ `calc_heterodimer`). Có từ trước, lộ ra khi v3.2.0 chấm ~40× ứng viên mỗi lần thiết kế (e2e song song: sập 1/3–1/4 lượt). Nay mọi lời gọi primer3 qua `algorithm/primer3_safe.py` (một khóa toàn tiến trình); test chặn import primer3 trực tiếp. Sau sửa: 5 lượt e2e 62/62 + 80 yêu cầu/16 luồng, không sập. |

**Đính chính (2026-10-28):** bản trước ghi "35 mồi Busk 2014 bị bỏ qua vì tên không có trong miRBase 22.1 hoặc là biến thể" — **sai**. Nguyên nhân là lỗi script phân tích: tra `reference_mirnas.json` theo `id` trong khi `results.json` ghi `label`, nên không lấy được trình tự in trong bài (cả 35 đều có, và vùng đặc hiệu khớp 35/35). Đã sửa; nay chỉ loại 3 "putative miRNA" (không có trong miRBase, bài báo không ghi loài → không xác định được tập off-target).

**Phân tích độ nhạy** (`benchmark/blast_tm_gate_sensitivity.json`, bộ phân loại v6; 175/178 mồi xuôi #1 của bộ validation, báo riêng 100 mồi stem-loop và 75 mồi Busk 2014 hệ poly(A)): số hit CRITICAL/HIGH **không đổi** ở biên SAFE 5/10/15/20 °C — theo thiết kế, vì hai bậc này chỉ phụ thuộc biên CRITICAL 5 °C; biên SAFE chỉ dời hit giữa SAFE và MEDIUM. Với mồi algorithm v3.4.0, bộ phân loại v6 (chạy lại 2026-10-29) — stem-loop: không có cổng Tm 343 hit CRITICAL ở 66 mồi → có cổng **65 ở 29 mồi**; Busk: 121/52 → 27/21. Lịch sử stem-loop có cổng: v3 29/13 → v4 32/13 (khôi phục base đầu 3′ bị BLAST cắt, SPEC_phase3 §8.15) → v5 63/27 (hit cùng họ seed không còn được miễn trừ, §8.16) → v6 65/29 (target EBV sàng lọc cả miRNA người, §8.17). 24 hit thuộc nhóm trùng trình tự (20 stem-loop, 4 Busk). CRITICAL còn lại chủ yếu là paralog khác nhau ở giữa trình tự (miR-23a/b, miR-103/107, miR-17/106a/20b, miR-146a/b, let-7) — trường hợp chỉ mồi RT (đầu 3′) phân biệt được, BLAST không mô hình — và paralog ở loài ngoài hsa/mmu/rno (không có chỉ mục family để gộp). Không có ground truth: đây là đầu ra của bộ phân loại, không phải dương tính thật/giả đã xác nhận.

---

### 10.2 Bổ sung 2026-10-29 — review tin sinh học (BLAST v4/v5, algorithm v3.3.0)

| ID | Trạng thái | Nội dung |
|---|---|---|
| REV-01 | ✅ Đã sửa (BLAST v4) | **Phân loại Kwok ở base cuối gần như không chạy.** Căn chỉnh cục bộ không kết thúc bằng mismatch → base cuối lệch bị cắt, thành "dangling" → nhãn chung MEDIUM/HIGH; thiếu 2 nt → SAFE dù base cuối có thể khớp (63 hit trên 175 mồi). Nay base bị cắt được lấy lại từ trình tự đầy đủ (hit sợi plus) rồi căn lại. Vùng Tm sát đích: TOLERANT → CRITICAL, G:G/BLOCKING/REDUCING → HIGH; hai base cuối lệch → SAFE trừ base cuối T → MEDIUM (Kwok 1990 abstract). SPEC_phase3 §8.15. |
| REV-02 | ✅ Đã sửa (BLAST v4) | **Tm_off lấy duplex bền nhất ở bất kỳ đâu** trên off-target. Nay tính trên khung đọc của mồi + 1 base (trên đích cho đúng Tm_on, 111/111). 27 hit vùng xám → SAFE, 4 CRITICAL → vùng xám. |
| REV-03 | ✅ Đã sửa (v3.3.0) | **Nhóm "trình tự tương thích" gộp chung là "assay đo tổng"** và `_evaluate_pair` so cửa sổ cố định vị trí (biến thể lệch 1 nt → SAFE giả). Nay mô hình offset-aware: isomiR đầu 3′ dài hơn 1–2 nt hoặc ngắn hơn 1 nt → ΔCq_RT 0, ngắn hơn 2 nt → 3 (Schamberger 2014, đã đối chiếu bản PDF); isomiR đầu 5′ → khuếch đại chung. BLAST tách `identical` / `isomir_5p` / `isomir_3p` (đổi tên ở ISO-02, 2026-10-30). *Đính chính review:* review ban đầu viết overhang "phân biệt được" biến thể đầu 3′ — sai với dữ liệu Schamberger; chỉ −2 nt bị trễ ~3 Ct. |
| REV-04 | ✅ Đã sửa (v3.3.0) | **Rủi ro chưa ở cấp assay; họ seed được miễn trừ.** Nay ΔCq_assay = ΔCq_RT + ΔCq_FWD trên toàn bộ miRNA cùng loài (chỉ mục overhang), là kết luận chính và tiêu chí `family_discrimination`. BLAST (v5) đánh dấu hit cùng họ (`same_seed_family`) và tính vào `overall_risk`. SPEC_phase3 §8.16. |
| REV-05 | ✅ Đã sửa | Vòng lặp overhang-collision chọn mồi dẫn đầu bằng `max()` (hòa → thứ tự sinh), khác khóa xếp hạng cuối → nay dùng chung `_rank_key`. |
| REV-06 | ✅ Đã sửa | Pool lọc theo Ta người dùng, `tm_accuracy` chấm theo 60 °C cố định → nay đều theo Ta (mặc định 60 °C nên kết quả mặc định không đổi). |
| REV-07 | ⏸ Giữ, ghi hạn chế | Khóa primer3 toàn tiến trình (ENG-08) làm các request chạy tuần tự; đủ cho công cụ khóa luận ít người dùng đồng thời. Hướng phát triển: `ThermoAnalysis` theo thread. |
| REV-08 | ✅ Đã sửa | `/api/blast-check`: nồng độ phải hữu hạn (mv/dna > 0); mồi xuôi không kết thúc bằng tiền tố 5′ của đích → bỏ cổng Tm + `tm_gate_note` (tránh mọi hit thành CRITICAL); nhận `species` (giao diện gửi `metadata.species_code`). |
| REV-09 | ✅ Đã sửa | Trích dẫn Primer3: `*_TH` là Tm tuyệt đối, đặt thấp hơn `PRIMER_MIN_TM` 10 °C (không phải "dưới Tm của mồi"); đo 10 °C từ Tm_on là lựa chọn của tool, chưa hiệu chỉnh. Bảng Kwok trong SPEC bỏ G:C/C:G (cặp Watson–Crick). |
| REV-10 | ✅ Đã sửa | Cảnh báo isomiR đầu 3′: mẫu serum/plasma/urine có ghi chú trung vị gộp mọi loại mẫu (serum + plasma = 2.633/42.494 mẫu, 6 %). Câu chữ cảnh báo đổi theo Schamberger 2014 (±1 nt bắt như nhau → tín hiệu là tổng isoform có trọng số, không phải dạng chính tắc). |
| REV-11 | ✅ Đã sửa (v3.4.0) | Chỉ mục overhang chỉ có hsa/mmu/rno → 90/165 target không có đánh giá cấp assay. Nay mọi loài miRBase 22.1 (cùng file với BLAST DB, kiểm tra số trình tự lúc dựng); miRNA virus sàng lọc cùng loài chủ; ghi chú độ phủ chú giải ngoài hsa/mmu. SPEC_phase3 §8.17. |
| REV-12 | ✅ Đã sửa (BLAST v6) | Regex tiền tố loài chỉ nhận 3 chữ cái → `kshv-`, `hcmv-`, `mdv1-`… bị đọc là người, BLAST loại toàn bộ miRNA virus là "khác loài". Nay 3–5 ký tự và mã loài phải có trong chỉ mục. Không ảnh hưởng số liệu validation (chỉ có `ebv`). |


### 10.3 Bổ sung 2026-10-30 — rà soát xử lý isomiR (algorithm v3.5.0)

| ID | Trạng thái | Nội dung |
|---|---|---|
| ISO-01 | ✅ Đã sửa | **Giá trị lệch đầu 3′ trình bày như số đo chắc chắn.** Cả bảng dựa trên 1 bài báo, 2 miRNA lệch nhau tới 4 Ct. Nay kèm `shift_range` (0–4 Ct ở ±1 nt, n = 2) và `delta_cq_high`; giá trị điểm ghi rõ là cận dưới. SPEC_phase3 §8.18(a). |
| ISO-02 | ✅ Đã sửa | **Gọi sai "isomiR".** `variant_category` so các mục miRBase, bắt được tên đồng nghĩa và paralog chứ không phải isomiR sinh học (loại này không có mục trong miRBase). Đổi tên nhóm thành `same_sequence` / `shifted_5p` / `shifted_3p`, trường `isomirs` → `same_molecule_entries`. |
| ISO-03 | ✅ Đã làm | **Thiếu cảnh báo sai lệch fold-change.** Thêm cảnh báo định tính khi tỷ lệ isoform 3′ ≥ 20 % và IQR ≥ 0,15 (32 % miRNA có dữ liệu), dẫn Nejad 2018 (PMID 29263133). Không quy ra hệ số. |
| ISO-04 | ✅ Đính chính | Ct 36/37/39,6 trong chú thích Figure 6 của Schamberger là của **đối chứng tham chiếu**, không phải phản ứng đo isomiR — nên không kết luận được "thí nghiệm dưới LLOQ". |
| ISO-05 | ⏳ Mở | Chưa ghép isomiRdb với mô hình ΔCq ("assay bắt ≈ X % tổng lượng") — hoãn tới khi có thí nghiệm hiệu chỉnh, vì n = 2 miRNA. |
| ISO-06 | ⏳ Mở | Chỉ mục 5′ vẫn là danh sách 8 miRNA tự tuyển; dựng từ nhãn `lv5p` của isomiRdb cần tải lại 1,2 GB. |

## 11. Tài liệu tham khảo (đã kiểm chứng qua PubMed)

Nguồn: PubMed. Mọi mục dưới đây đã được khớp PMID bằng PubMed MCP trong phiên audit.

| Tag | Trích dẫn | PMID | DOI |
|---|---|---|---|
| Chen05 | Chen C et al. Real-time quantification of microRNAs by stem-loop RT-PCR. *Nucleic Acids Res* 2005;33:e179 | 16314309 | [10.1093/nar/gni178](https://doi.org/10.1093/nar/gni178) |
| Kramer11 | Kramer MF. Stem-loop RT-qPCR for miRNAs. *Curr Protoc Mol Biol* 2011;Unit 15.10 | 21732315 | [10.1002/0471142727.mb1510s95](https://doi.org/10.1002/0471142727.mb1510s95) |
| Varkonyi07 | Varkonyi-Gasic E et al. *Plant Methods* 2007;3:12 | 17931426 | [10.1186/1746-4811-3-12](https://doi.org/10.1186/1746-4811-3-12) |
| SL98 | SantaLucia J. *PNAS* 1998;95:1460-5 | 9465037 | [10.1073/pnas.95.4.1460](https://doi.org/10.1073/pnas.95.4.1460) |
| SL04 | SantaLucia J, Hicks D. *Annu Rev Biophys Biomol Struct* 2004;33:415-40 | 15139820 | [10.1146/annurev.biophys.32.110601.141800](https://doi.org/10.1146/annurev.biophys.32.110601.141800) |
| Owczarzy04 | Owczarzy R et al. Effects of sodium ions on DNA duplex oligomers. *Biochemistry* 2004;43:3537-54 | 15035624 | [10.1021/bi034621r](https://doi.org/10.1021/bi034621r) |
| Owczarzy08 | Owczarzy R et al. Predicting stability of DNA duplexes in solutions containing magnesium and monovalent cations. *Biochemistry* 2008;47:5336-53 | 18422348 | [10.1021/bi702363u](https://doi.org/10.1021/bi702363u) |
| vonAhsen01 | von Ahsen N et al. Oligonucleotide melting temperatures under PCR conditions. *Clin Chem* 2001;47:1956-61 | 11673362 | (PubMed không trả DOI) |
| Sugimoto95 | Sugimoto N et al. RNA/DNA hybrid duplexes. *Biochemistry* 1995;34:11211-6 | 7545436 | [10.1021/bi00035a029](https://doi.org/10.1021/bi00035a029) |
| McTigue04 | McTigue PM et al. LNA-DNA duplex formation. *Biochemistry* 2004;43:5388-405 | 15122905 | [10.1021/bi035976d](https://doi.org/10.1021/bi035976d) |
| Owczarzy11 | Owczarzy R et al. Stability and mismatch discrimination of LNA-DNA duplexes. *Biochemistry* 2011;50:9352-67 | 21928795 | [10.1021/bi200904e](https://doi.org/10.1021/bi200904e) |
| MIQE09 | Bustin SA et al. The MIQE guidelines. *Clin Chem* 2009;55:611-22 | 19246619 | [10.1373/clinchem.2008.112797](https://doi.org/10.1373/clinchem.2008.112797) |
| MIQE25 | Bustin SA et al. MIQE 2.0. *Clin Chem* 2025;71:634-651 | 40272429 | [10.1093/clinchem/hvaf043](https://doi.org/10.1093/clinchem/hvaf043) |
| BLAST+ | Camacho C et al. BLAST+: architecture and applications. *BMC Bioinformatics* 2009;10:421 | 20003500 | [10.1186/1471-2105-10-421](https://doi.org/10.1186/1471-2105-10-421) |
| Ye12 | Ye J et al. Primer-BLAST. *BMC Bioinformatics* 2012;13:134 | 22708584 | [10.1186/1471-2105-13-134](https://doi.org/10.1186/1471-2105-13-134) |
| Ririe97 | Ririe KM et al. Product differentiation by analysis of DNA melting curves during PCR. *Anal Biochem* 1997;245:154-60 | 9056205 | [10.1006/abio.1996.9916](https://doi.org/10.1006/abio.1996.9916) |
| Lorenz11 | Lorenz R et al. ViennaRNA Package 2.0. *Algorithms Mol Biol* 2011;6:26 | 22115189 | [10.1186/1748-7188-6-26](https://doi.org/10.1186/1748-7188-6-26) |
| Marmur62 | Marmur J, Doty P. *J Mol Biol* 1962;5:109-18 | 14470099 | [10.1016/s0022-2836(62)80066-7](https://doi.org/10.1016/s0022-2836(62)80066-7) |
| Nejad18 | Nejad C et al. miR-222 isoforms are differentially regulated by type-I interferon (stem-loop RT-qPCR chọn lọc theo 3′ isoform). *RNA* 2018;24:332-341 | 29263133 | [10.1261/rna.064550.117](https://doi.org/10.1261/rna.064550.117) |
| isomiRdb23 | Aparicio-Puerta E et al. isomiRdb: microRNA expression at isoform resolution. *Nucleic Acids Res* 2023;51(D1):D179-D185 | 36243964 | [10.1093/nar/gkac884](https://doi.org/10.1093/nar/gkac884) |

**CHƯA KIỂM CHỨNG** (không tìm được qua PubMed trong phiên nên không dùng làm bằng chứng): hệ số nhiệt độ của pKa Tris; dải Mg²⁺ điển hình của SYBR master mix; ảnh hưởng của thuốc nhuộm SYBR lên Tm.

---

## Phụ lục A — Tái lập các phép tính

```text
Chạy từ repo; backend đã cài primer3-py và ViennaRNA.

1. Hairpin DNA vs RNA, Tm amplicon theo Mg:
   primer3.calc_heterodimer / calc_end_stability (mv 50, dv 3.0, dNTP 0.8, 250 nM)
   RNA.params_load_DNA_Mathews2004(); RNA.md().temperature = 16/37/42/50

2. Analyzer với S có overhang 5 nt (Flask test client):
   POST /api/analyze {matureSequence, mirnaId, primers:{rt, forward, reverse}}

3. Overhang 5/6/7 nt:
   algorithm.design_pipeline.run(seq, {"bindingRegion3prime": n})
   → visualization.coordinates.build_amplicon_model(...)

4. Bound fraction: algorithm.bound_fraction._calculate_bound_fraction(seq, {}, T), T = 42 / 55 / 60

5. Salt: primer3.calc_tm(..., salt_corrections_method = 'santalucia' | 'owczarzy')

6. Hằng số chết: quét tên hằng trong algorithm/constants.py so với toàn bộ *.py còn lại
```
