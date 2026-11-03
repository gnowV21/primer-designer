# RESEARCH_INSIGHTS.md — Evidence-based design rules để tăng độ chính xác thuật toán
# HG Lab Stem-loop RT-qPCR Primer Designer · v1.0 — 2026-07-02
# Nguồn: khai thác full-text PubMed Central (miRprimer/Busk 2014, miPrimer/Kang 2017, + Chen05, Wang17, Fan19, Andreasen10, MIQE09)

> Mục đích: rút insight định lượng từ các công cụ/protocol đã được kiểm nghiệm thực nghiệm, **ánh xạ vào 15 tiêu chí scoring hiện có** (SCORING_WEIGHTS_V4) và các hằng số, để tăng độ chính xác. Mỗi insight ghi rõ nguồn + DOI + mức độ áp dụng cho phương pháp Chen stem-loop mà tool đang dùng.
>
> *Lưu ý phương pháp:* tool của ta dùng **Chen-2005 stem-loop** (universal body cố định + overhang 6 nt + universal reverse `CCAGTGCAGGGTCCGAGGTA`). miRprimer/miPrimer dùng hệ universal khác (poly-T tag / tail riêng), nên **trình tự primer của họ KHÔNG so trực tiếp** với tool; nhưng **nguyên lý thiết kế (Tm, 3′-end, dimer, tail, scoring) là method-agnostic** và chuyển được. Chỗ nào method-specific sẽ ghi rõ.

---

## A. Insight định lượng → hành động cho scoring

| # | Insight (có bằng chứng) | Nguồn | Tiêu chí tool liên quan | Hành động đề xuất |
|---|---|---|---|---|
| I1 | **Ngưỡng dimer ΔG = −9.0 ± 1 kcal/mol**: self-/hetero-dimer ΔG > −9 ⇒ OK; < −9 ⇒ gây hỏng qPCR. Tính bằng RNAcofold (DNA params). | [Kang17] | `dimer_penalty` | Đặt/hiệu chỉnh **biên critical = −9 kcal/mol** trong constants; ta đã có ViennaRNA → dùng đúng công cụ họ dùng. Là ngưỡng hội tụ từ thực nghiệm, đáng tin. |
| I2 | **Tm forward đích = 59 °C** (nearest-neighbor, NaCl 115 mM); < 57 °C thì kéo dài 5′-tail tới khi đạt 59 °C; > 59 °C thì cắt bớt. | [Busk14],[Kang17] | `tm_accuracy` | Kiểm lại target Tm (tool ~60 °C) và **salt setting**; cân nhắc chuẩn 59 °C. Xác nhận NaCl/Mg²⁺ trong mô hình Tm (Phase5 PART C). |
| I3 | **3′-end thành phần GC — trade-off hai nguồn:** (a) [IDT] khuyến nghị G/C ở 3′ để anchor polymerase & tăng hiệu suất khuếch đại chung (PCR thường, amplicon dài). (b) [Busk14] ưu tiên **1–2 A/T ở 3′** (= 1–2 G/C) để tăng đặc hiệu phân biệt mismatch 1 nt trong ngữ cảnh miRNA; 3 G/C = kém (quá chặt); **3 C liên tiếp** = phạt nặng. Hai luật tối ưu hai mục tiêu khác nhau: IDT→hiệu suất/anchor, Busk→đặc hiệu miRNA. Tool ưu tiên đặc hiệu → nghiêng Busk, nhưng là trade-off có ý thức. *Phân tầng mức tin:* "Phạt CCC / G-run ở 3′" = **đa-nguồn** [Busk14]+[Kang17]+anti-homopolymer chung → **chốt được**. "Nâng 1 G/C = tối ưu ngang 2 G/C" = **đơn-nguồn** [Busk14], heuristic, Busk tự thừa nhận sampling bias → **tạm thời, chờ calibration** (chi tiết xem mục D). | [Busk14]+[IDT] | `gc_clamp` | Đã sửa theo PROMPT 1: (a) phần multi-source (phạt CCC, run G-C ở 3′) **đã chốt** trong scoring. (b) phần đơn-nguồn (1 G/C = optimal ngang 2 G/C) đặt sau constant `GC_CLAMP_1GC_AS_OPTIMAL` mặc định **False** (hành vi thận trọng: 2 G/C > 1 G/C) — chỉ bật khi calibration xác nhận cải thiện. Explanation cite kép [Busk14]+[IDT]. |
| I4 | **Kéo dài 5′-tail để đạt Tm**: thêm nucleotide theo thứ tự **G, A, C, G, C**, tối đa G/C nhưng **tránh poly(C)/poly(G)** (homopolymer). | [Busk14] | edge E4/E6, `gc_skew` | Cụ thể hoá luật tail adaptive (SPEC_phase5 PART D §12.4): dùng chuỗi tail G,A,C,G,C tránh run. Có bằng chứng. |
| I5 | **Chấm điểm dạng NHÂN (multiplicative)**: pair_score = Fscore × Rscore × Fanneal × Ranneal × dimer. Một yếu tố kém → kéo tụt cả cặp (giống soft-AND / hard-filter). | [Busk14] | toàn scoring engine | Hậu thuẫn mạnh cho **hard-filter gates** (SPEC_phase4 §12.1): weighted-SUM hiện có thể bù trừ lỗi chí mạng. Cân nhắc nhân/loại thẳng ứng viên vi phạm ngưỡng cứng (I1) trước khi xếp hạng. |
| I6 | **Length score forward = (độ dài phần specific)² / 400**; reverse **không** phạt độ dài (không thấy tương quan với hiệu năng). | [Busk14] | `primer_size` | Đối chiếu công thức `primer_size` với dạng bậc hai này. Reverse của ta là universal cố định → phù hợp việc "không phạt reverse". |
| I7 | **Đặc hiệu 3′-end**: mismatch càng gần 3′ càng phân biệt tốt; off-target đồng loại chỉ 0.1–1% target đúng. | [Busk14] | `family_discrimination`, isoMiR, Kwok (Phase3) | Củng cố việc **ưu tiên mismatch gần 3′** (Phase3 §8.6 Kwok đã làm). Xác nhận trọng số family_discrimination hợp lý. |
| I8 | **Loại cặp F/R chồng ≥ 2 nt ở 3′-end** (tránh primer-dimer 3′). | [Busk14] | heterodimer 3′ | Bổ sung/loại ứng viên có 3′-overlap ≥2 nt (một dạng hard-filter). |
| I9 | Bối cảnh template có **cấu trúc bậc 2 gần vùng bắt primer** ức chế khuếch đại; phân tích ≥60 bp quanh site. | [Fan19] | (đề xuất `template_structure`) | SPEC_phase4 §12.2 — ưu tiên cao, có bằng chứng định lượng. |

---

## B. Số liệu "tỉ lệ thành công" thực (dùng làm kỳ vọng & acceptance criteria)

| Nguồn | Quy mô | Kết quả thực | Ý nghĩa cho ta |
|---|---|---|---|
| [Busk14] miRprimer | 164 primer validate | **93 ± 5%** cặp chạy ngay lần 1; 95±7% forward, 97±5% reverse functional; 99±2% designable | Đặt kỳ vọng: một designer tốt nên đạt ~90%+ "chạy lần đầu". Là benchmark tham chiếu. |
| [Kang17] miPrimer | 120 cặp primer | **95.6%** (non-family) & **93.3%** (family) thành công 1 lần thử; **efficiency 90–110%** | Ngưỡng efficiency 90–110% [MIQE09] xác nhận lại; family discrimination ~93% khả thi. |
| [Busk14] | let-7a/f, miR-125b/c, miR-200b/c, miR-23a/b | off-target 1-nt mismatch: **0.1–1%** target đúng | Mục tiêu đặc hiệu cho module cross-reactivity/isoMiR của ta. |
| [Wang17] | let-7 panel (9 thành viên) | efficiency 0.93–1.14; phân biệt **1 nt** | Đích cross-validation family (đã trong reference_mirnas.json). |

---

## C. Việc cụ thể để nâng độ chính xác (ưu tiên)

1. **[cao] Xác lập ngưỡng dimer −9 kcal/mol (I1)** trong constants + đảm bảo `dimer_penalty` critical đúng biên này (ViennaRNA RNAcofold). — rẻ, bằng chứng mạnh.
2. **[cao] Hard-filter gates trước weighted-sum (I5, I1, I8)** — chuyển một phần sang cơ chế nhân/loại thẳng để tránh bù trừ lỗi chí mạng.
3. **[cao] `gc_clamp` cho ngữ cảnh miRNA (I3)** — đã điều chỉnh (PROMPT 1): phần đa-nguồn (phạt CCC/run G-C ở 3′) đã chốt; phần đơn-nguồn (1 G/C = optimal) sau cờ `GC_CLAMP_1GC_AS_OPTIMAL=False` (mặc định thận trọng), chờ calibration xác nhận. Cite kép [Busk14]+[IDT] — hai luật phục vụ hai mục tiêu khác nhau (xem D).
4. **[trung bình] Chuẩn Tm 59 °C + salt (I2)** — đối chiếu target Tm & NaCl/Mg²⁺ (Phase5 PART C).
5. **[trung bình] Tail adaptive G,A,C,G,C tránh homopolymer (I4)** — hiện thực hoá cho edge E4 (Phase5 PART D).
6. **[thấp] Công thức length bậc hai (I6)** — đối chiếu `primer_size`.

Các mục 1–3 chính là "hiệu chỉnh để thuật toán chính xác hơn" có bằng chứng trực tiếp nhất, độc lập với việc thu dữ liệu hồi quy (bổ trợ cho SPEC_phase5 PART B).

---

## D. Ghi chú bias & độ tin cậy nguồn

Phần này ghi lại **lý do không thể áp dụng một chiều** kết quả từ bất kỳ công trình đơn lẻ nào — đặc biệt liên quan đến I3 (gc_clamp) và quy tắc thiết kế 3′-end.

### D.1 Busk14 — method-specific, không áp trực tiếp 1:1 vào Chen stem-loop

Busk 2014 dùng hệ primer khác: tail tự do (không có universal body cố định), reverse primer riêng — trình tự cụ thể không so được với hệ Chen stem-loop. Nguyên lý (Tm, anti-homopolymer, tránh dimer) là method-agnostic và chuyển được. Nhưng *hệ số scoring cụ thể* (1 G/C được bao nhiêu điểm? ngưỡng phạt chính xác?) được tối ưu trên dataset hệ **họ** — áp nguyên vào tool của ta là **giả định chưa được calibration xác nhận**. Lưu ý này áp cho cả I3, I6, I7.

### D.2 Reporting bias (Busk tự thừa nhận — Onodera)

Busk 2014 (Methods, tr. 4) thừa nhận: "We cannot exclude that some primers were discarded before testing." Tức là primer khó/có nguy cơ thất bại có thể đã bị loại **trước** khi đưa vào tỉ lệ thành công 93%. Đây là **sampling bias** (khảo sát của Onodera et al. cho thấy các công cụ primer thường báo cáo tỉ lệ tốt hơn thực tế vì chọn lọc trước). Quy tắc 3′-end của miRprimer học từ dataset này → mang bias tương tự. Con số "1–2 A/T → score 100, 3 G/C → score 30" là heuristic học từ một tập dữ liệu bị lọc sẵn, chưa phải chân lý phổ quát.

### D.3 Đơn lab / đơn tác giả — chưa replicate độc lập

Toàn bộ rule-set Busk14 xuất phát từ 164 cặp primer của **một nhóm** (Busk PK, DTU Denmark). Không có bài độc lập replicate xác nhận rằng quy tắc "1–2 A/T ở 3′ cho đặc hiệu miRNA" tốt hơn IDT clamp cho stem-loop RT-qPCR cụ thể. So sánh: ngưỡng dimer −9 kcal/mol (I1) được **cả [Busk14] lẫn [Kang17]** (hai nhóm độc lập, hai hệ primer khác nhau) đồng thuận → mức tin cao hơn nhiều. I3b chưa có đối trọng đó.

### D.4 IDT cũng không trung lập

IDT (Integrated DNA Technologies) là nhà cung cấp thương mại. Hướng dẫn "G/C ở 3′ để anchor polymerase" tối ưu cho PCR thường (amplicon dài, Taq/proofreading polymerase, primer 18–25 nt), không phải stem-loop RT-qPCR (amplicon ~80 bp, nhiệt độ bắt mồi thấp hơn, primer ngắn hơn với specific region 12–17 nt). IDT không có xung đột lợi ích học thuật nhưng có xung đột thương mại tinh tế: khuyến nghị đơn giản hoá dễ áp dụng hơn khuyến nghị có điều kiện.

### D.5 Quy tắc phân tầng mức tin (áp dụng cho mọi insight)

| Mức hội tụ | Ví dụ | Hành động |
|---|---|---|
| **Đa nguồn độc lập** (≥2 bài, lab khác nhau) | I1: dimer −9 kcal/mol [Busk14]+[Kang17] | **Chốt** — constant cứng |
| **Đơn nguồn, cơ sở lý thuyết rõ** | I9: template hairpin [Fan19], cơ học phân tử rõ ràng | **Chốt** — nhưng chỉ cảnh báo, không phạt scoring cho đến khi calibration |
| **Đơn nguồn, heuristic / bias đã biết** | I3b: 1 G/C = optimal [Busk14 đơn lab, sampling bias] | **Tạm thời**: constant bật/tắt, mặc định **False** (thận trọng), chờ calibration |
| **Tương quan từ calibrate_weights.py** | bất kỳ tiêu chí nào | Association không phải causation — không quy công riêng một tiêu chí khi các tiêu chí đồng biến qua Tm/GC/dimer |

*Nguyên tắc: báo cáo tương quan từ `calibrate_weights.py` chỉ là association. Chỉ khi có controlled experiment (thay đúng một tiêu chí, giữ nguyên các tiêu chí khác) mới kết luận nguyên nhân. Calibration là bằng chứng hỗ trợ, không phải xác nhận cuối cùng.*

---

## E. Giới hạn mô hình Tm — cần biết để diễn giải kết quả calibration

### E.1 DNA:RNA hybrid — khoảng trống độ chính xác chính của RT primer

`primer3.calc_tm()` dùng tham số nearest-neighbor **DNA:DNA** (SantaLucia 1998). RT primer của stem-loop bắt cặp với **miRNA (RNA)** → đây là hybrid **DNA:RNA**. Bộ tham số NN cho DNA:RNA khác hẳn: ΔH và ΔS khác nhau → Tm thực của RT primer trên miRNA template có thể lệch **3–8 °C** so với dự đoán DNA:DNA, tùy trình tự (Sugimoto 1995, DOI 10.1021/bi00035a029).

**Hệ quả:**
- Tm của **RT primer** mà tool hiển thị là Tm DNA:DNA giả định, không phải Tm thực khi bắt cặp với miRNA.
- **Forward primer và reverse primer** (PCR step, bắt cặp với cDNA → DNA:DNA) **không bị ảnh hưởng**.
- Owczarzy benchmark (calibration/tm_benchmark.json) chỉ validate DNA:DNA duplex → **không kiểm được sai số RT primer**.

**Workaround tạm thời:** Dùng Tm RT primer như gần đúng cho *so sánh tương đối* giữa các ứng viên (ranking), không phải Tm tuyệt đối thực tế. Workaround dài hạn: NUPACK hoặc RNAstructure với tham số DNA:RNA (Sugimoto 1995). Chưa triển khai vì cần dependency mới.

### E.2 Salt correction — SantaLucia method (không phải Owczarzy); benchmark độc lập; công thức divalent là von Ahsen 2001

Tool dùng `salt_corrections_method='santalucia'` (default của primer3-py 2.0), **không phải** `'owczarzy'`. Header comment trong `thermodynamics.py` trước đây ghi sai **"Owczarzy 2004 Mg2+ correction"** — sai cả method name (SantaLucia) lẫn năm (2004 là Na⁺, không phải Mg²⁺). Đã sửa 2026-07-03.

**Pipeline salt correction được xác nhận từ C source (oligotm.c, primer3-py 2.0.3):**

```c
// santalucia branch (dòng 447-449):
K_mM = K_mM + divalent_to_monovalent(divalent_conc, dntp_conc);  // ← von Ahsen 2001
delta_S = delta_S + 0.368 * (len - 1) * log(K_mM / 1000.0);     // SantaLucia entropy

// divalent_to_monovalent (dòng 774-784):
return 120 * sqrt(divalent - dntp);   // von Ahsen 2001, DOI 10.1093/clinchem/47.11.1956
```

**Circularity verdict (cập nhật chính xác 2026-07-03):**

| Series | Pipeline tool | Benchmark | Độc lập? |
|--------|--------------|-----------|----------|
| **Na⁺** | SantaLucia entropy correction áp trực tiếp lên K_mM (Na⁺) | Owczarzy 2004 Na⁺ data | ✓ **Hoàn toàn độc lập** |
| **Mg²⁺** | Bước 1: `120√(Mg−dNTP)` [von Ahsen 2001]; bước 2: SantaLucia entropy | Owczarzy 2008 Mg²⁺ data | ✓ **Độc lập cả hai bước** (von Ahsen 2001 ≠ Owczarzy formula; bước 2 = SantaLucia 1998, trước Owczarzy 2008 10 năm) |

**Diễn đạt an toàn cho paper:**
- Na⁺ series: *"independent validation of the SantaLucia 1998 monovalent salt correction"*
- Mg²⁺ series: *"independent validation of the full divalent pipeline: von Ahsen 2001 divalent-to-monovalent conversion [DOI 10.1093/clinchem/47.11.1956] followed by SantaLucia 1998 entropy correction"*

**So sánh thực nghiệm (34 oligos):** `santalucia` MAE=2.68°C Bias=−2.65°C; `owczarzy` MAE=2.64°C Bias=−2.08°C. Owczarzy nhỉnh hơn một chút (Mg series: 3.12 vs 2.82 MAE) nhưng kém độc lập trong benchmark hiện có → **giữ `santalucia`**.

**Mở rộng benchmark (đã triển khai):**
Chạy `python calibration/check_tm.py --expand-salt` để dùng 242 điểm (9 cột Mg × 18 oligos + 5 cột Na × 16 oligos), kiểm salt correction trên toàn dải. Kết quả: SantaLucia under-predicts ở Mg ≤3 mM nhưng over-predicts ở Mg ≥50 mM (non-monotonic bias). Điều kiện vận hành tool (1.5 mM Mg) ở vùng under-predict — bias −2.65°C vẫn relevant.

---

## Nguồn (đã đọc full-text, trích từ PubMed)
- **[Busk14]** Busk PK. "A tool for design of primers for microRNA-specific quantitative RT-qPCR." *BMC Bioinformatics.* 2014;15:29. PMID 24472427 · DOI [10.1186/1471-2105-15-29](https://doi.org/10.1186/1471-2105-15-29). *(open access; luật thiết kế + score matrix + tỉ lệ thành công)*
- **[Kang17]** Kang ST et al. "miPrimer: an empirical-based qPCR primer design method for small noncoding microRNA." *RNA.* 2017;24(3):304–312. PMID 29208706 · DOI [10.1261/rna.061150.117](https://doi.org/10.1261/rna.061150.117). *(ngưỡng dimer −9 kcal/mol, Tm 59–60 °C, tail, 120-cặp)*
- **[Mei12]** Mei Q et al. "A facile and specific assay for quantifying microRNA by an optimized RT-qPCR approach." *PLoS One.* 2012;7(10):e46890. PMID 23071657 · DOI [10.1371/journal.pone.0046890](https://doi.org/10.1371/journal.pone.0046890).
- **[Chen05]** Chen C et al. *Nucleic Acids Res.* 2005;33(20):e179.
- **[Wang17]** Wang Y et al. *Mol Med Rep.* 2017;17(3):3690–3696. DOI [10.3892/mmr.2017.8297](https://doi.org/10.3892/mmr.2017.8297).
- **[Fan19]** Fan H et al. *J Biomol Struct Dyn.* 2019;37(11):2867–2874. DOI [10.1080/07391102.2018.1498804](https://doi.org/10.1080/07391102.2018.1498804).
- **[Andreasen10]** Andreasen D et al. *Methods.* 2010;50(4):S6–9. DOI [10.1016/j.ymeth.2010.01.006](https://doi.org/10.1016/j.ymeth.2010.01.006).
- **[MIQE09]** Bustin SA et al. *Clin Chem.* 2009;55(4):611–622. DOI [10.1373/clinchem.2008.112797](https://doi.org/10.1373/clinchem.2008.112797).

*Thông tin tài liệu trích từ PubMed. Số liệu tỉ lệ thành công/efficiency là của phương pháp gốc trong từng bài; dùng làm tham chiếu, không phải kết quả của tool này.*
