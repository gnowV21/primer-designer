# Insight cho slide "Tiêu chí nhiệt động học" — nguyên lý thiết kế (đề cương)

> **Dành cho Claude (phiên sửa slide).** Dùng tài liệu này để viết **một slide** về tiêu chí nhiệt động học trong phần nguyên lý thiết kế của đề cương. Số liệu đọc từ code algorithm **3.8.0** (`master`, merge commit `486d5ce`) và từ `calibration/tm_report.md`. Bản 3.8.0 chỉ đổi trọng số chấm điểm (bỏ GC skew, GC clamp 0,06), không đổi tiêu chí nhiệt động học nào ở đây; các mồi ví dụ ở mục 5.1 đã chạy lại và vẫn đúng. Trích dẫn có PMID đã đối chiếu với PubMed qua NCBI E-utilities (2026-11-11 và 2026-11-16).
>
> **Quy tắc:**
> 1. Không thêm con số, ngưỡng hay trích dẫn không có ở đây.
> 2. Mọi giá trị ΔG hoặc Tm phải kèm điều kiện tính: phần mềm, nhiệt độ, muối.
> 3. Chỗ ghi "mốc riêng của tool" hoặc "chưa xác minh" thì slide cũng phải ghi như vậy.
> 4. Chỉ một slide: chọn mục 2 làm khung, mục 3–5 làm ghi chú người nói và dự phòng câu hỏi.

---

## 1. Thông điệp chính của slide

**Mỗi mồi được đánh giá bằng mô hình nearest-neighbor ở đúng điều kiện phản ứng mà nó sẽ chạy.** Tool tính Tm theo hai bước, đúng cơ chế bám của mồi stem-loop: chu kỳ 1 chỉ vùng đặc hiệu bám khuôn, các chu kỳ sau cả mồi bám. Cấu trúc thứ cấp được loại theo tiêu chí có nguồn: dimer theo ΔG của miPrimer (Kang), hairpin theo Tm của Primer3. Mô hình Tm được kiểm chứng trên 34 oligo có Tm đo bằng UV-melting từ nguồn độc lập.

---

## 2. Khung đề xuất cho slide (4 khối)

### Khối A — Mô hình và điều kiện phản ứng

- **Tm:** nearest-neighbor SantaLucia 1998, qua primer3-py (`PRIMER_TM_FORMULA = 1`).
- **Hiệu chỉnh muối:**
  - Cation hóa trị một: hiệu chỉnh entropy theo SantaLucia.
  - Mg²⁺ được quy đổi sang cation hóa trị một theo von Ahsen 2001: 120·√([Mg²⁺] − [dNTP]). Đây là cách primer3 tự xử lý, đã kiểm trong mã nguồn C `oligotm.c`.
- **Cation hóa trị một hiệu dụng** = [Na⁺] + [K⁺] + [Tris⁺]. Tris⁺ là phần Tris bị proton hóa ở pH đệm, với pKa 8,06 ở 25 °C.
- **Mặc định của form web:**

  | Thành phần | Giá trị |
  |---|---|
  | Na⁺ | 50 mM |
  | K⁺ | 50 mM |
  | Tris | 10 mM, pH 8,4 (≈ 3,1 mM Tris⁺) |
  | Mg²⁺ | 1,5 mM |
  | dNTP tổng | 0,8 mM |
  | Mồi | 200 nM |
  | Ta | 60 °C |

  Tổng cation hóa trị một hiệu dụng là 103 mM. Xem cảnh báo ở mục 5.1.

### Khối B — Tm hai bước của mồi xuôi (điểm riêng của stem-loop)

| Bước | Phần mồi bám | Mục tiêu | Lý do |
|---|---|---|---|
| Chu kỳ 1 | Chỉ vùng đặc hiệu 12–17 nt, bám vào cDNA | Tm = **45 °C** (100 điểm; giảm 50 điểm mỗi 10 °C lệch) | Đuôi 5′ chưa có khuôn bổ sung ở chu kỳ 1 (nguyên lý `SEQUENCE_OVERHANG_LEFT` của Primer3Plus) |
| Chu kỳ 2 trở đi | Toàn mồi = đuôi 5′ (3–12 nt) + vùng đặc hiệu | Tm = **Ta** (mặc định 60 °C; 100 điểm khi trùng, giảm 50 điểm mỗi 2 °C lệch) | Sản phẩm đã mang đuôi, nên cả mồi bám |

- Đuôi được chọn sao cho Tm toàn mồi gần Ta nhất. Tool tính Tm thật cho từng tổ hợp đuôi + vùng đặc hiệu, giữ các đuôi trong ±3 °C quanh Ta (nới ra ±6 °C nếu không đủ ứng viên).
- **Phân số mồi bám** (bound fraction, SantaLucia & Hicks 2004) được tính cho cả hai bước. Chỉ bước toàn mồi được chấm (trọng số 0,03). Bước vùng đặc hiệu chỉ báo cáo, vì chưa có ngưỡng công bố. Theo tính toán của tool, ở 60 °C vùng 12–17 nt chỉ bám khoảng 2–10 % ở chu kỳ 1.

### Khối C — Cấu trúc thứ cấp (lọc cứng + chấm điểm), chỉ cho mồi xuôi

| Cấu trúc | Đại lượng và điều kiện | Ngưỡng | Nguồn |
|---|---|---|---|
| Dimer bền nhất (self-dimer; mồi xuôi × mồi ngược phổ quát) | ΔG theo RNAcofold, tham số DNA, 37 °C, Na⁺ 1,021 M | **Loại** khi ΔG < −9,0 kcal/mol | Kang et al. 2018 (miPrimer): cùng ngưỡng, cùng phạm vi, cùng phần mềm |
| Hairpin | Tm hairpin (primer3 thal, muối của phản ứng) | **Loại** khi Tm ≥ 47 °C | Mặc định `PRIMER_MAX_HAIRPIN_TH` của Primer3 (Untergasser et al. 2012) |
| Dimer đầu 3′ (8 nt cuối) | ΔG theo primer3 thal ở Ta | Loại khi ≤ −5,0 kcal/mol | Premier Biosoft (trang web). Trên thực tế chưa loại ứng viên nào (mục 4) |
| Độ bền đầu 3′ (5 nt cuối) | ΔG theo primer3 | ≤ 9 kcal/mol → 100 điểm | Primer3Plus `PRIMER_MAX_END_STABILITY` (theo chú thích trong code) |
| MFE của mồi RT stem-loop | ViennaRNA, tham số DNA, 37 °C | Cửa sổ −19,5 đến −11,1 kcal/mol, tối ưu −14,5 | Cửa sổ do tool suy ra, không hiệu chỉnh thực nghiệm |

**Vì sao dimer dùng ΔG còn hairpin dùng Tm.** Mỗi quy tắc dùng đúng đại lượng và thang của nguồn mà ngưỡng được lấy ra. Ngưỡng −9 kcal/mol của Kang được đặt trên thang RNAcofold. Ngưỡng 47 °C của Primer3 là một Tm. Đặt ngưỡng của nguồn lên một thang khác là sai: trước đây tool đặt ngưỡng −9 lên ΔG của primer3 ở 60 °C, và lọc lỏng hơn miPrimer rất nhiều (mục 4).

### Khối D — Kiểm chứng mô hình Tm bằng số đo độc lập

- **Dữ liệu:** 34 oligo DNA:DNA có Tm đo bằng UV-melting.
  - Owczarzy 2004 (dãy Na⁺, n = 16).
  - Owczarzy 2008 (dãy Mg²⁺, n = 18).
- **Cách dự đoán:** ở đúng điều kiện muối và nồng độ của từng điểm đo, không dùng mặc định của tool.
- **Không vòng lặp:** tool dùng SantaLucia 1998 và von Ahsen 2001, còn dữ liệu đối chiếu là của Owczarzy, nên hai bên tách rời.

| Dãy | n | MAE | Bias |
|---|---|---|---|
| Tất cả | 34 | 2,69 °C | −2,65 °C |
| Na⁺ (Owczarzy 2004) | 16 | 2,19 °C | −2,19 °C |
| Mg²⁺ (Owczarzy 2008) | 18 | 3,12 °C | −3,06 °C |

- **Kết luận đúng:** mô hình dự đoán Tm **thấp hơn** thực tế một cách hệ thống, khoảng 2–3 °C.
- **Yếu tố gây sai:**
  - Sai lớn nhất ở oligo ≤ 12 nt (MAE 3,75 °C).
  - Đệm đo chỉ có 1 mM cation hóa trị một, khác điều kiện PCR.
- **Quyết định:** không chỉnh mục tiêu Tm khi chưa có số đo ở đúng điều kiện của tool.
- **Mồi RT không nằm trong phép kiểm này,** vì mồi RT lai với RNA tạo duplex DNA:RNA.

---

## 3. Bước phiên mã ngược (chỉ báo cáo, không chấm điểm)

- **Phần bám miRNA:** overhang 6 nt của mồi RT, lai DNA:RNA.
- **Tm lai DNA:RNA:** tính bằng tham số nearest-neighbor của Sugimoto 1995 (`hybrid_tm.py`). Giá trị này **chỉ báo cáo**, không dùng để chấm điểm hay lọc.
- **Điều kiện đệm RT:** theo Kramer 2011, Table 2: KCl 75 mM, MgCl₂ 3 mM, dNTP tổng 2 mM, mồi RT 1 nM. Điều kiện này được dùng khi tính ΔG của bước RT trong ma trận phản ứng chéo.
- **Câu nên nói:** độ đặc hiệu của bước RT được đánh giá bằng mô hình ΔCq (mismatch ở overhang), không dựa trên Tm.

---

## 4. Số liệu hỗ trợ (ghi chú người nói)

**Hiệu lực của từng quy tắc lọc cứng** (9.268 ứng viên mồi xuôi, 150 miRNA người chọn ngẫu nhiên):

| Quy tắc | Số ứng viên bị loại |
|---|---|
| Dimer, RNAcofold < −9 | 2.132 |
| Dimer đầu 3′, ΔG ≤ −5 ở 60 °C | 0 |
| Hairpin cũ, ΔG ≤ −6 ở 60 °C (đến 3.6.0) | 0 (ΔG thấp nhất −2,36 kcal/mol) |
| Hairpin mới, Tm ≥ 47 °C (từ 3.7.0) | 847 (9,1 %) có Tm > 47 °C |

**Hai thang ΔG cho cùng một dimer** (2253 mồi xuôi của miRNA người, thiết kế bằng 3.5.0):

| Cách tính | Trung vị | Số mồi < −9 |
|---|---|---|
| primer3, 60 °C | −1,84 kcal/mol | 0 |
| primer3, 37 °C | −5,10 kcal/mol | 93 |
| RNAcofold, tham số DNA, 37 °C | −7,50 kcal/mol | 534 |

**Ý vật lý dùng khi được hỏi.** ΔG phụ thuộc nhiệt độ: ΔG(T) = ΔH·(1 − T/Tm). Ví dụ:
- ΔG hairpin ở 60 °C âm nghĩa là hairpin vẫn đóng ở Ta.
- Một hairpin có Tm 72 °C (mồi ebv-miR-BART15 của 3.6.0) có ΔG ở 60 °C chỉ hơi âm, nên quy tắc ΔG cũ xếp nó là "safe". Tiêu chí Tm bắt được nó.

---

## 5. Cảnh báo — không đưa lên slide, nhưng phải biết

### 5.1 Mặc định muối của form web khác mặc định của API

- **Form web** gửi Na⁺ 50 mM + K⁺ 50 mM + Tris pH 8,4, tổng **103 mM** cation hóa trị một hiệu dụng.
- **Gọi API với tham số trống** chỉ tính Na⁺ 50 mM. Bộ kiểm tra 2439 dùng cách này.
- Chênh lệch làm Tm cao hơn khoảng 1,5 °C, nên tool chọn đuôi khác. Với hsa-miR-21-5p:

  | Cách gọi | Mồi xuôi | Tm vùng đặc hiệu |
  |---|---|---|
  | API, tham số trống | `ACCGCCTAGCTTATCAGACTGA` | 43,4 °C |
  | Form web, mặc định | `CCACTGGTAGCTTATCAGACTGA` | 44,9 °C |

- **Câu hỏi mở:** đệm qPCR thông thường chỉ có một loại muối hóa trị một (thường là KCl, khoảng 50 mM). Cộng cả Na⁺ 50 mM và K⁺ 50 mM có thể tính trùng. Nên quyết định mặc định trước khi bảo vệ, và nêu rõ điều kiện trên slide.

### 5.2 Lỗi trích dẫn trong code (phát hiện khi soạn)

- **`AMPLICON_DIMER_TM_GAP_WARN` (cảnh báo khi Tm dimer cách Tm amplicon dưới 10 °C):** ghi `[Lagatie17] DOI 10.1371/journal.pone.0163435`, nhưng DOI này là bài của Rodrigues et al. 2016 về phế cầu khuẩn.
  - Bài Lagatie 2017 đúng là *Parasitol Res* 116(3):1013–1022, DOI 10.1007/s00436-017-5382-5.
  - Chưa kiểm bài đó có nêu mốc 10 °C hay không. **Không trích mốc 10 °C trên slide.**
- **`hybrid_tm.py`:** ghi Sugimoto 1995 ở *Biochemistry* 34(**37**). PubMed ghi số **35**.
- **`thermodynamics.py`:** chú thích nói Tm lai DNA:RNA của Sugimoto "chưa cài đặt", nhưng `hybrid_tm.py` đã cài để báo cáo. Hai chú thích mâu thuẫn nhau.
- **Kramer 2011:** DOI đúng là `10.1002/0471142727.mb1510s95` (repo không ghi DOI).

### 5.3 Giới hạn nên tự nêu

- **Tm thấp hơn thực tế** khoảng 2–3 °C trên dữ liệu đối chiếu. Không nói "Tm chính xác ±1 °C".
- **Mục tiêu Tm vùng đặc hiệu 45 °C và cửa sổ MFE stem-loop là mốc riêng** của tool.
- **Tiêu chí điểm hairpin gần như luôn cho 100,** vì ΔG hairpin ở 60 °C hiếm khi dưới −2 kcal/mol. Hairpin thực chất chỉ được xử lý bằng lọc cứng theo Tm.
- **Quy tắc dimer đầu 3′ chưa loại ứng viên nào** (AUDIT REV-21, còn mở).

---

## 6. Trích dẫn đã đối chiếu (PubMed, NCBI E-utilities)

| Viết tắt | Trích dẫn | PMID |
|---|---|---|
| SantaLucia 1998 | SantaLucia J Jr. A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics. *Proc Natl Acad Sci USA.* 1998;95(4):1460–1465. DOI 10.1073/pnas.95.4.1460 | 9465037 |
| SantaLucia & Hicks 2004 | SantaLucia J Jr, Hicks D. The thermodynamics of DNA structural motifs. *Annu Rev Biophys Biomol Struct.* 2004;33:415–440. DOI 10.1146/annurev.biophys.32.110601.141800 | 15139820 |
| von Ahsen 2001 | von Ahsen N, Wittwer CT, Schütz E. Oligonucleotide melting temperatures under PCR conditions: nearest-neighbor corrections for Mg²⁺, deoxynucleotide triphosphate, and dimethyl sulfoxide concentrations with comparison to alternative empirical formulas. *Clin Chem.* 2001;47(11):1956–1961 | 11673362 |
| Owczarzy 2004 | Owczarzy R, You Y, Moreira BG, et al. Effects of sodium ions on DNA duplex oligomers: improved predictions of melting temperatures. *Biochemistry.* 2004;43(12):3537–3554. DOI 10.1021/bi034621r | 15035624 |
| Owczarzy 2008 (Mg²⁺) | Owczarzy R, Moreira BG, You Y, Behlke MA, Walder JA. Predicting stability of DNA duplexes in solutions containing magnesium and monovalent cations. *Biochemistry.* 2008;47(19):5336–5353. DOI 10.1021/bi702363u | 18422348 |
| Sugimoto 1995 | Sugimoto N, Nakano S, Katoh M, et al. Thermodynamic parameters to predict stability of RNA/DNA hybrid duplexes. *Biochemistry.* 1995;34(35):11211–11216. DOI 10.1021/bi00035a029 | 7545436 |
| Kramer 2011 | Kramer MF. Stem-loop RT-qPCR for miRNAs. *Curr Protoc Mol Biol.* 2011;Chapter 15:Unit 15.10. DOI 10.1002/0471142727.mb1510s95 | 21732315 |
| Kang 2018 | Kang ST, Hsieh YS, Feng CT, Chen YT, Yang PE, Chen WM. miPrimer: an empirical-based qPCR primer design method for small noncoding microRNA. *RNA.* 2018;24(3):304–312 (epub 2017-12-05). DOI 10.1261/rna.061150.117 | 29208706 |
| Untergasser 2012 | Untergasser A, Cutcutache I, Koressaar T, et al. Primer3—new capabilities and interfaces. *Nucleic Acids Res.* 2012;40(15):e115. DOI 10.1093/nar/gks596 | 22730293 |
| Lorenz 2011 | Lorenz R, Bernhart SH, Höner zu Siederdissen C, et al. ViennaRNA Package 2.0. *Algorithms Mol Biol.* 2011;6:26. DOI 10.1186/1748-7188-6-26 | 22115189 |
| Chen 2005 | Chen C, Ridzon DA, Broomer AJ, et al. Real-time quantification of microRNAs by stem-loop RT-PCR. *Nucleic Acids Res.* 2005;33(20):e179. DOI 10.1093/nar/gni178 | 16314309 |

**Không phải bài báo:**
- **Primer3 manual** (primer3.org/manual.html, đọc 2026-11-11): mặc định 47 °C của `PRIMER_MAX_HAIRPIN_TH`, "10 degrees lower than the default value of PRIMER_MIN_TM".
- **Primer3Plus:** `SEQUENCE_OVERHANG_LEFT` và `PRIMER_MAX_END_STABILITY` = 9,0 theo chú thích trong code; chưa đối chiếu trang Primer3Plus.
- **Premier Biosoft:** trang web.
