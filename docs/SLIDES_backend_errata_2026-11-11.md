# Đính chính và cập nhật nội dung slide backend — 2026-11-11

> **Dành cho Claude (phiên sửa slide).** Tài liệu này là nguồn chuẩn để sửa bộ slide backend của khóa luận "Stem-loop RT-qPCR primer designer". Mọi con số được đọc từ code **algorithm 3.7.0** (nhánh `fix/hairpin-tm-rule`, PR #7; bản trước đó trên `master` là 3.6.0, commit `626c362`) hoặc từ file kết quả có ghi đường dẫn. Mọi trích dẫn có PMID đã được đối chiếu với bản ghi PubMed qua NCBI E-utilities ngày 2026-11-11.
>
> **Quy tắc khi sửa slide:**
> 1. Không thêm con số, ngưỡng hay trích dẫn không có trong tài liệu này.
> 2. Không đặt câu trích dẫn trong ngoặc kép nếu tài liệu này không ghi rõ đó là nguyên văn.
> 3. Khi gán một luận điểm cho một bài báo, chỉ gán đúng điều bài đó nói (xem mục 6).
> 4. Chỗ nào tài liệu ghi "chưa xác minh" thì slide cũng phải ghi như vậy, hoặc bỏ đi.

---

## 1. Tóm tắt các thay đổi (theo thứ tự)

| PR (merge commit) | Thay đổi | Ảnh hưởng tới slide |
|---|---|---|
| #3 (`63dc590`) | Gỡ hẳn chức năng kiểm tra multiplex (`/api/multiplex-check`). Công cụ cũ chỉ xét mồi xuôi × mồi xuôi/probe, không xét mồi RT × mồi RT. | Bỏ mọi nhắc tới multiplex (slide 3.2, 3.3) |
| #4 (`715d854`) | **BLAST classifier v7**: thêm bước RT cho hit của mồi xuôi; tính các mục miRBase trùng/lệch đầu vào `overall_risk`. **Ma trận phản ứng chéo cấp assay** cho toàn bộ miRNA người. | Có thể thêm slide mới (mục 4.3, 4.4) |
| #5 (`61e44f4`) | **Algorithm 3.6.0**: ΔG dimer toàn cấu trúc (quy tắc lọc cứng 1) tính bằng **RNAcofold, tham số DNA**, đúng phương pháp của Kang et al. Đính chính trích dẫn Busk 2014 và Kang. | Sửa slide 1.4, 2.1, 2.2, 3.2, 3.4 |
| #6 (`626c362`) | Dựng lại ma trận phản ứng chéo bằng 3.6.0; sửa lỗi bộ đệm không theo phiên bản thuật toán. | Số liệu ma trận (mục 4.4) |
| #7 (nhánh `fix/hairpin-tm-rule`) | **Algorithm 3.7.0**: lọc cứng hairpin theo **Tm hairpin ≥ 47 °C** (mặc định Primer3), thay cho ΔG ≤ −6 kcal/mol, vốn không bao giờ kích hoạt. Dựng lại ma trận bằng 3.7.0. | Sửa slide 2.1, 2.2 (mục 3.1, 3.2) |

---

## 2. Bảng sửa từng slide

Mã slide theo bản nội dung đã soạn trước đó (Phần 1 – Nguyên lý thiết kế, Phần 2 – Bộ tiêu chí chấm điểm, Phần 3 – Xây dựng backend).

| Slide | Nội dung cũ | Vấn đề | Nội dung mới |
|---|---|---|---|
| 1.3, bước 6 | "Lọc cứng để loại ứng viên có lỗi chí mạng" | Thiếu phạm vi và cơ chế dự phòng | "Lọc cứng 3 quy tắc, chỉ áp cho ứng viên mồi xuôi. Nếu không ứng viên nào qua, trả về ứng viên tốt nhất kèm cảnh báo `hard_filter_fallback`." |
| 1.3, bước 9 | "Đánh giá độ đặc hiệu (họ miRNA, isomiR, BLAST)" | BLAST không chạy tự động | "Đặc hiệu theo mô hình ΔCq cấp assay (tự động); kiểm tra off-target bằng BLAST khi người dùng yêu cầu, có bước RT (classifier v7)." |
| 1.4 | "Mọi ngưỡng đều có trích dẫn (Chen 2005, SantaLucia 1998, Busk 2014, Kang 2017, Stadhouders 2010…)" | **Sai.** Có ngưỡng là mốc riêng của tool (các mức điểm hairpin −2/−3/−6 kcal/mol, cửa sổ MFE stem-loop, hệ số 0,66 Cq/°C) và có ngưỡng chỉ có nguồn là trang web (Premier Biosoft, IDT) | "Mỗi ngưỡng ghi rõ nguồn; ngưỡng nào là mốc riêng của tool thì ghi là mốc riêng." |
| 1.4 | "Lọc cứng trước, chấm điểm sau: một lỗi chí mạng không thể bị điểm cao ở tiêu chí khác bù lại" | Đúng về ý, nhưng phải là lập luận của tool, không gán cho Busk | Giữ nguyên ý; không kèm trích dẫn |
| 2.1 | Bảng lọc cứng: "Dimer toàn phần, ΔG < −9, Kang 2017"; "Dimer đầu 3′, mức critical, Premier Biosoft"; "Hairpin, mức critical, Primer3Plus" | Không nêu ngưỡng thật, không nêu áp cho mồi nào, sai nguồn hairpin, thiếu điều kiện tính | Thay bằng bảng ở mục 3.1 |
| 2.1 | Khung trích: "Lý do (Busk 2014): chỉ một lỗi dimer hay hairpin là cả assay hỏng; tổng có trọng số không bù được." | **Trích sai.** Busk 2014 không có câu này (mục 6.1) | Thay bằng đoạn lý do ở mục 3.1 |
| 2.2 | Cột "Ngưỡng / mục tiêu" | Nhiều dòng chỉ ghi gần đúng | Thay bằng bảng ở mục 3.2 |
| 2.2, dòng Dimer | "ΔG đầu 3′ > −5; ΔG toàn phần > −9" | Phần "toàn phần" nay tính bằng RNAcofold, khác thang của primer3 | Xem mục 3.2 |
| 2.2, dòng GC-skew | "≤ 0 (giảm nguy cơ G-quadruplex)" | Cơ chế G-quadruplex chưa có nguồn đã kiểm; trong code nhãn nguồn còn lệch nhau ("PrimerAST 2024" và "PrimerAST 2026") | Ghi "≤ 0 cho điểm tối đa (heuristic)" và bỏ cơ chế; hoặc kiểm nguồn trước khi giữ |
| 2.4 | Xếp loại Excellent ≥ 80 | Đúng, nhưng nên biết một giới hạn | Mồi đi qua chế độ dự phòng vẫn có thể đạt Excellent, ví dụ cel-miR-39-3p được 87,3 điểm dù dimer RNAcofold −10,5 kcal/mol. Xem mục 5 |
| 3.1 | "algorithm/, ~5.400 dòng, 20+ module" | Đã lỗi thời | "`backend/algorithm/`: 31 file Python, 8.353 dòng (kể cả gói con)" |
| 3.2 | ViennaRNA: "MFE cấu trúc stem-loop (tham số DNA, Mathews 2004)" | Thiếu vai trò mới | "ViennaRNA 2.7.2, bộ tham số DNA Mathews 2004, 37 °C: (1) MFE của mồi RT stem-loop; (2) ΔG dimer toàn cấu trúc cho lọc cứng (RNAcofold)" |
| 3.2 | flask-limiter: "BLAST, multiplex: 10 lần/phút" | Không còn multiplex | "Giới hạn `/api/blast-check`: 10 lần/phút/IP" |
| 3.2 | Flask: "chia thành 10 blueprint" | Đã gỡ 1 blueprint | "9 blueprint" |
| 3.3 | 13 endpoint, có `POST /api/multiplex-check` | Không còn multiplex | 12 endpoint API cộng `GET /api/health` (danh sách ở mục 3.6) |
| 3.4 | "683 test đạt (3 bỏ qua)"; "phiên bản thuật toán (v3.5.0)" | Đã lỗi thời | "Backend 707 test đạt, 3 bỏ qua; e2e Playwright 74/74; gói ma trận 29/29"; "algorithm 3.7.0" |
| Kiểm chứng – Mồi LNA | "Kiểm chứng mô hình LNA với dữ liệu thực nghiệm McTigue 2004 … tốt hơn sai số bài gốc" | **Không phải kiểm chứng độc lập.** Tham số Owczarzy 2011 được dẫn xuất từ chính bộ dữ liệu McTigue 2004 Table 1 | "Kiểm chứng cài đặt: tái hiện mô hình Owczarzy 2011 trên bộ dữ liệu gốc McTigue 2004 (n = 38, RMSD ΔTm 0,72 °C). Vì tham số được dẫn xuất từ chính bộ dữ liệu này, đây chưa phải kiểm chứng độc lập của mô hình." *(Điểm này chưa được ghi trong AUDIT_REPORT.)* |

Các slide kiểm chứng khác giữ nguyên số. Validation tạo lại ngày 2026-11-11 bằng 3.6.0, rồi bằng 3.7.0, cho cùng kết quả:
- **2439/2439** phép kiểm đạt trên 201 target;
- vùng đặc hiệu mồi xuôi trùng với mồi đã công bố **184/189** (5 mục N/A vì lõi công bố < 10 nt);
- overhang RT trùng **98**;
- mồi RT trùng tuyệt đối **22**, cộng 3 trùng phần thân (2 có overhang 8 nt, 1 có overhang 5 nt);
- mồi xuôi trùng tuyệt đối **0/189**.

---

## 3. Nội dung chuẩn để đưa lên slide

### 3.1 Lọc cứng (thay slide 2.1)

**Lý do lọc cứng** (lập luận của tool, không phải trích dẫn): Khi cộng điểm có trọng số, một cấu trúc thứ cấp nghiêm trọng có thể bị các tiêu chí khác bù lại. Busk (2014) hạn chế việc này bằng cách **nhân** điểm: tự bắt cặp đầu 3′ dài 5 nt nhân 0,1, dài 4 nt nhân 0,2. Tool này chọn **loại hẳn**.

Các quy tắc chỉ áp cho **ứng viên mồi xuôi (F)**. URP là mồi ngược phổ quát `CCAGTGCAGGGTCCGAGGTA`.

| Quy tắc | Áp dụng cho | Ngưỡng loại | Cách tính | Nguồn |
|---|---|---|---|---|
| 1. Dimer bền nhất (ở bất kỳ vị trí nào) | F tự bắt cặp (self-dimer); F × URP (hetero-dimer) | ΔG < −9,0 kcal/mol | RNAcofold, tham số DNA, 37 °C, Na⁺ 1,021 M | Kang et al. 2018 (miPrimer): cùng ngưỡng, cùng phạm vi, cùng phần mềm |
| 2. Dimer đầu 3′ | 8 nt cuối của F tự bắt cặp; 8 nt cuối của F × 8 nt cuối của URP | ΔG ≤ −5,0 kcal/mol | primer3 thal ở Ta | Trang hướng dẫn của Premier Biosoft (không phải bài báo) |
| 3. Hairpin | Chỉ F | **Tm hairpin ≥ 47 °C** | primer3 `calc_hairpin` (thal), Tm của hairpin bền nhất | Mặc định `PRIMER_MAX_HAIRPIN_TH` = 47.0 của Primer3 (Untergasser et al. 2012). Tài liệu Primer3 ghi: "The default value is 10 degrees lower than the default value of PRIMER_MIN_TM" (57.0) |

**Điều kiện tính của quy tắc 2–3:**
- Phần mềm: primer3-py, thermodynamic alignment ("thal"), tham số nearest-neighbor SantaLucia & Hicks 2004.
- Thành phần phản ứng: cation hóa trị một 50 mM, Mg²⁺ 1,5 mM, dNTP 0,8 mM, mồi 200 nM, trừ khi người dùng đổi.
- Quy tắc 2 tính ΔG ở Ta (mặc định 60 °C).
- Quy tắc 3 so Tm của hairpin với mốc **cố định** 47 °C. Mốc không đổi theo Ta, giống mặc định của Primer3. Hairpin là cấu trúc một phân tử nên Tm không phụ thuộc nồng độ mồi.

**Mỗi quy tắc loại được bao nhiêu ứng viên.** Đo trên 9.268 ứng viên mồi xuôi của 150 miRNA người chọn ngẫu nhiên:

| Quy tắc | Số ứng viên bị loại |
|---|---|
| 1. Dimer, RNAcofold < −9 | 2.132 |
| 2. Dimer đầu 3′, ΔG ≤ −5 ở Ta | **0** |
| 3 cũ. Hairpin, ΔG ≤ −6 ở Ta (đến 3.6.0) | **0** (ΔG thấp nhất chỉ −2,36 kcal/mol) |
| 3 mới. Hairpin, Tm ≥ 47 °C (từ 3.7.0) | 847 có Tm > 47 °C (9,1 %) |

Quy tắc 2 hiện không có tác dụng (AUDIT REV-21, còn mở). Primer3 có tiêu chí tương ứng là `PRIMER_MAX_SELF_END_TH` (mặc định 47 °C), nhưng chưa được áp dụng.

**Tác động của 3.7.0:**
- **Validation:** vẫn 2439/2439; 9 target đổi điểm; thêm 1 ca dự phòng (ssc-miR-101).
- **Toàn bộ miRNA người:** 197/2253 mồi xuôi đổi. Mồi có Tm hairpin ≥ 47 °C giảm từ 215 xuống 19, và 19 mồi này đều ở chế độ dự phòng.
- **Ví dụ:** mồi ebv-miR-BART15 của 3.6.0 (`ACCACCGTCAGTGGTTTTGTT`) có Tm hairpin 72 °C nhưng được xếp "safe" theo ΔG; từ 3.7.0 nó bị loại.

**Quy tắc 1 dùng điều kiện cố định** (mặc định của RNAcofold), không theo thành phần phản ứng người dùng nhập, vì ngưỡng −9 được đặt trên thang này.

**Không áp dụng:**
- **Mồi RT stem-loop:** cố ý là một hairpin; cấu trúc của nó được chấm qua tiêu chí MFE stem-loop.
- **URP:** cố định; chỉ được kiểm tra một lần mỗi bản thiết kế và chỉ cảnh báo.
- **Cặp F × mồi RT:** được tính nhưng không thuộc lọc cứng.

**Quy tắc 2 là phép xấp xỉ.** Nó tính ΔG trên đoạn 8 nt cuối, không kiểm tra base cuối cùng ở đầu 3′ có thực sự bắt cặp hay không.

**Đối chiếu Primer3 (nếu hội đồng hỏi):** Primer3 (Untergasser et al. 2012) không dùng ngưỡng ΔG cho hairpin và dimer. Nó dùng **Tm của cấu trúc** (`PRIMER_MAX_HAIRPIN_TH`, `PRIMER_MAX_SELF_ANY_TH`, `PRIMER_MAX_SELF_END_TH`, mặc định 47 °C). Từ 3.7.0 quy tắc hairpin dùng đúng tiêu chí này. Quy tắc 1 vẫn dùng ΔG theo Kang, quy tắc 2 vẫn dùng ΔG ở Ta. Không ghi "Primer3Plus" làm nguồn cho các ngưỡng ΔG của tool.

**Vì sao đổi sang RNAcofold (3.6.0).** Trước 3.6.0, quy tắc 1 tính ΔG bằng primer3 ở 60 °C, một thang ít âm hơn nhiều. Phép đo trên 2253 mồi xuôi của miRNA người (thiết kế bằng 3.5.0), lấy min(ΔG self-dimer, ΔG F × URP):

| Cách tính | Trung vị (kcal/mol) | Số mồi có ΔG < −9 |
|---|---|---|
| primer3 thal, 60 °C (cách cũ) | −1,84 | 0 |
| primer3 thal, 37 °C | −5,10 | 93 |
| RNAcofold, tham số DNA, 37 °C (cách của Kang) | −7,50 | 534 (23,7 %) |

Với cùng một mồi, RNAcofold cho ΔG âm hơn primer3 ở 60 °C, trung vị 5,44 kcal/mol (P10–P90: −8,24 đến −3,78). Nguồn: `backend/scripts/dimer_dg_method_compare.py` → `benchmark/dimer_dg_method_compare.json`.

**Tác động của 3.6.0:**
- **Validation:** vẫn 2439/2439. 32/193 target đổi điểm; khoảng 23 target đổi mồi xuôi.
- **Dự phòng:** 10/193 target không còn ứng viên nào qua quy tắc 1 và dùng `hard_filter_fallback`; điểm giảm 8,4 vì tiêu chí dimer bằng 0. Lý do: dimer nằm trong vùng đặc hiệu của miRNA, nên đổi đuôi 5′ không gỡ được. Ví dụ cel-miR-39-3p có self-dimer RNAcofold −10,5 kcal/mol, liên quan đoạn CACCGGGTG.
- **Toàn bộ miRNA người:** 434/2253 mồi xuôi đổi; 123 mồi (5,5 %) vẫn có dimer < −9 và đi qua chế độ dự phòng.

### 3.2 Mười lăm tiêu chí chấm điểm (thay cột ngưỡng của slide 2.2)

Trọng số `SCORING_WEIGHTS_V4` có tổng bằng 1,00. Mỗi tiêu chí cho 0–100 điểm.

| Tiêu chí | Trọng số | Cách chấm (đúng theo `scoring.py`) | Nguồn ghi trong code |
|---|---|---|---|
| Tm mồi xuôi toàn phần | 0,20 | 100 khi Tm = Ta (mặc định 60 °C); giảm 50 điểm cho mỗi 2 °C lệch (50 điểm ở ±2 °C, 0 ở ±4 °C) | Tm theo SantaLucia 1998 + hiệu chỉnh Mg²⁺ |
| MFE mồi RT stem-loop | 0,14 | Trong cửa sổ −19,5 đến −11,1 kcal/mol: 60–100, tối đa ở −14,5 | Cửa sổ do tool suy ra, không hiệu chỉnh bằng thực nghiệm; ViennaRNA tham số DNA |
| Tm vùng đặc hiệu | 0,10 | 100 ở 45 °C; giảm 50 điểm cho mỗi 10 °C lệch | Nguyên lý `SEQUENCE_OVERHANG_LEFT` của Primer3Plus |
| Hairpin | 0,08 | Theo mức ΔG ở Ta: > −2 → 100; −2 đến −3 → 80; −3 đến −6 → 40; ≤ −6 → 0. Bằng 0 nếu Tm hairpin ≥ 47 °C (chỉ gặp ở chế độ dự phòng). Vì ΔG hairpin ở 60 °C hầu như không xuống dưới −2, tiêu chí này gần như luôn cho 100 | Các mức ΔG là mốc riêng của tool; mốc Tm theo Primer3 |
| Dimer | 0,08 | ΔG đầu 3′ (primer3): > −4 → 100; > −5 → 75; > −6 → 40; còn lại 0. Bằng 0 nếu dimer đầu 3′ ≤ −5 hoặc dimer toàn cấu trúc (RNAcofold) < −9 | Premier Biosoft; Kang et al. 2018 |
| Độ bền đầu 3′ (5 nt cuối) | 0,08 | ≤ 9 kcal/mol → 100; vượt thì 80 − 15 × (phần vượt) | Primer3Plus `PRIMER_MAX_END_STABILITY` = 9,0 (theo chú thích trong code) |
| %GC | 0,08 | 40–60 %: max(60, 100 − 2·\|GC − 50\|) | Hướng dẫn của IDT |
| Phân biệt họ miRNA | 0,05 | DISCRIMINATED 100, PARTIAL 70, CO-AMPLIFIED 0 (mô hình ΔCq, mục 4.1) | Chen 2005, Czimmerer 2013, Stadhouders 2010, Kwok 1990 |
| Tỉ lệ bám, vùng đặc hiệu | 0,05 | **Không chấm, chỉ báo cáo** (chưa có ngưỡng công bố); tổng điểm được chuẩn hóa lại trên các tiêu chí còn lại | SantaLucia & Hicks 2004 |
| GC clamp (3 nt cuối) | 0,04 | 2 G/C → 100; 1 G/C → 75; 0 hoặc 3 G/C → 50; CCC → 25 | Busk 2014 + IDT |
| Tỉ lệ bám, toàn mồi | 0,03 | Chấm theo phân số mồi bám (bound fraction) của toàn mồi, xem `bound_fraction.py` | SantaLucia & Hicks 2004 |
| GC-skew | 0,02 | ≤ 0 → 100; ≤ 0,1 → 85; ≤ 0,2 → 70; giảm dần sau đó | Heuristic; nguồn chưa kiểm |
| Độ dài vùng đặc hiệu | 0,02 | min(100, (L/17)² × 100), với L = 12–17 nt | Dạng bậc hai theo Busk 2014 (hệ số chưa đối chiếu lại) |
| Kích thước amplicon | 0,02 | 60–150 bp: max(70, 100 − 0,5·\|bp − 80\|) | Hướng dẫn của IDT |
| Chênh Tm F – URP | 0,01 | ≤ 1 °C → 100 | Trọng số thấp vì URP cố định |

Kích thước amplicon = độ dài đuôi + độ dài miRNA + 37 bp, với 37 = 44 − 7 (URP bám từ vị trí 7 của thân 44 nt).

### 3.3 Xếp hạng và xếp loại (slide 2.4 giữ nguyên)

- **Xếp hạng:** theo tổng điểm; nếu bằng điểm thì ưu tiên Tm gần Ta hơn, sau đó theo trình tự.
- **Xếp loại:** Excellent ≥ 80, Good 65–79, Acceptable 50–64, Poor < 50.

### 3.4 Thông số mồi (slide 1.1–1.2 giữ nguyên, kiểm lại đúng)

- **Mồi RT:** thân 44 nt cố định cộng overhang 3′. Overhang mặc định 6 nt; 5 và 7 nt được hỗ trợ kèm cảnh báo; ngoài 5–7 nt thì trả HTTP 400.
- **Mồi xuôi:** đuôi 5′ dài 3–12 nt cộng vùng đặc hiệu 12–17 nt từ đầu 5′ của miRNA. Vùng đặc hiệu không chồng lên N nt cuối của miRNA (N = độ dài overhang).
- **Chế độ phát hiện:** SYBR Green là mặc định; TaqMan có thiết kế probe.

### 3.5 Công nghệ (slide 3.2)

| Thư viện | Vai trò |
|---|---|
| Flask 3 + flask-cors | Web API, 9 blueprint |
| primer3-py | Tm nearest-neighbor (SantaLucia 1998) có hiệu chỉnh muối; ΔG hairpin và dimer bằng thal (SantaLucia & Hicks 2004); độ bền đầu 3′ |
| ViennaRNA 2.7.2 | Tham số DNA Mathews 2004, 37 °C: MFE mồi RT stem-loop và ΔG dimer toàn cấu trúc (RNAcofold) |
| BLAST+ | Dò off-target trên miRBase 22.1 cục bộ |
| biopython, numpy | Xử lý trình tự, tính toán |
| reportlab | Xuất PDF |
| flask-limiter | `/api/blast-check`: 10 lần/phút/IP |

### 3.6 Endpoint (slide 3.3)

`GET /api/mirbase/<id>`, `GET /api/mirbase/suggest`, `POST /api/design`, `POST /api/analyze`, `POST /api/blast-check`, `GET /api/blast-status`, `POST /api/lna-suggest`, `POST /api/visualize`, `POST /api/export`, `GET /api/benchmark`, `GET /api/docs`, `GET /api/openapi.yaml`. Tổng cộng 12 endpoint, cộng `GET /api/health`.

---

## 4. Nội dung mới có thể thêm slide

### 4.1 Mô hình ΔCq cấp assay (bổ sung số cho slide 2.3)

ΔCq_assay = ΔCq_RT + ΔCq_FWD, có xét lệch đầu ±2 nt.

| Trục | Trường hợp | ΔCq | Nguồn số liệu |
|---|---|---|---|
| RT | 1 mismatch rG·dT (wobble) | 4,75 | Chen 2005 (assay let-7a đo let-7c: 3,7 %) |
| RT | 1 mismatch khác, vị trí 1–3 từ đầu 3′ mồi RT | 7,0 | Chen 2005 |
| RT | 1 mismatch khác, vị trí 4–6 | 3,5 | Czimmerer 2013 (6,8–9,0 %) |
| RT | ≥ 2 mismatch | 8,0 | Chen 2005 (≤ 0,3 %) |
| FWD | Mismatch ở base cuối 3′, nhóm nặng (A–A, A–G, G–A, G–G, C–C) | 8,3 | Stadhouders 2010 (8,29–9,09 Ct) |
| FWD | Nhóm trung bình (T–C, C–T, T–T) | 3,8 | Stadhouders 2010 (3,77–4,75 Ct) |
| FWD | Nhóm nhẹ (A–C, C–A, T–G, G–T) | 1,0 | Stadhouders 2010 (0,99–1,91 Ct) |
| FWD | Vị trí 2 (kế cuối) | 1,9 | Stadhouders 2010 (trung bình 1,87 Ct) |
| FWD | Vị trí 3–5 | 0,5 | Stadhouders 2010 |
| FWD | ≥ 2 mismatch trong 5 nt cuối | 8,3 | Stadhouders 2010; ngoại lệ base cuối T (Kwok 1990) |
| FWD | Độ bền duplex | 0,66 × (Tm_on − Tm_off), trần 8,3 | **Hệ số do tool tự suy, không từ tài liệu** |

**Phân loại:**

| ΔCq_assay | Kết luận | Tín hiệu chéo 2^−ΔCq |
|---|---|---|
| < 3,3 | CO-AMPLIFIED | > 10 % |
| 3,3 – < 4,3 | PARTIAL | 5–10 % |
| ≥ 4,3 | DISCRIMINATED | < 5 % |

**Giới hạn phải nêu:**
- Giá trị tra được đo với enzyme và master mix khác, nên chỉ đúng về thứ tự độ lớn.
- Mô hình giả định hai trục RT và FWD độc lập.
- Chưa tính tỉ lệ nồng độ giữa off-target và đích trong mẫu.
- Mô hình không xét probe TaqMan. Với SYBR, R là giới hạn lạc quan; với TaqMan là giới hạn bi quan.

### 4.2 Thuật ngữ cần dùng thống nhất

| Thuật ngữ trên slide | Nghĩa chính xác |
|---|---|
| Overhang (vùng bắt cặp 3′ của mồi RT) | Đoạn 5–7 nt ở đầu 3′ mồi RT, bổ sung với đầu 3′ của miRNA |
| Vùng đặc hiệu (specific region) của mồi xuôi | Đoạn 12–17 nt giống đầu 5′ của miRNA (cùng chiều) |
| Đuôi 5′ (tail) | Nucleotide thêm ở đầu 5′ mồi xuôi để nâng Tm; không bám khuôn ở chu kỳ 1 |
| Dimer bền nhất / dimer toàn cấu trúc | Cấu trúc hai phân tử có ΔG thấp nhất, ở bất kỳ vị trí nào (không dùng "dimer toàn phần") |
| Dimer đầu 3′ | Dimer tính trên 8 nt cuối, dùng làm đại diện cho dimer polymerase có thể kéo dài |
| Self-dimer / hetero-dimer | Hai bản sao của cùng một mồi / hai mồi khác nhau |
| ΔG (kcal/mol) | Năng lượng tự do Gibbs của cấu trúc; càng âm càng bền. Luôn kèm phần mềm, nhiệt độ và muối |
| MFE | Năng lượng tự do tối thiểu của cấu trúc thứ cấp dự đoán |
| ΔCq | Chênh chu kỳ định lượng giữa đích và off-target; tín hiệu chéo = 2^−ΔCq |
| `hard_filter_fallback` | Không ứng viên nào qua lọc cứng; tool trả ứng viên tốt nhất kèm cảnh báo |
| Ta | Nhiệt độ gắn mồi của phản ứng qPCR (mặc định 60 °C) |

### 4.3 Kiểm tra off-target bằng BLAST, classifier v7

- **Bước RT:** hit của mồi xuôi trên mạch cùng chiều được xét tiếp xem mồi RT có bắt được off-target đó không, theo ΔCq_RT của mô hình assay.
  - ΔCq_RT ≥ 4,3 → SAFE (dưới 5 % được phiên mã ngược).
  - 3,3–4,3 → tối đa MEDIUM.
  - < 3,3 → giữ mức của mồi xuôi.
- **Mục miRBase trùng hoặc lệch đầu**, nay được tính vào `overall_risk`:
  - `same_sequence` → SAFE (chính là đích dưới tên khác);
  - `shifted_5p` → HIGH;
  - `shifted_3p` → theo ΔCq_RT.
- **Kết quả** trên 100 mồi stem-loop của bộ validation, biên Tm 10 °C, **đo với thiết kế 3.5.0, chưa chạy lại với 3.6.0**:
  - Hit CRITICAL giảm từ 65 xuống 16; số mồi có ≥ 1 hit CRITICAL giảm từ 29 xuống 10; `overall_risk` SAFE tăng từ 55 lên 78.
  - Bước RT loại 96 hit.
  - 16 hit CRITICAL còn lại là các paralog có cùng overhang, ví dụ let-7a ↔ 7d, miR-20a ↔ 17/106a/20b.

### 4.4 Ma trận phản ứng chéo cấp assay (offline, `crossreactivity/`)

**Định nghĩa:** R(i, j) = 2^−ΔCq_assay = p_RT × p_PCR. Assay i là bộ mồi #1 của miRNA i; j là mọi miRNA trưởng thành người, miRBase 22.1.

| | Algorithm 3.7.0 (2026-11-11) | 3.6.0 (2026-11-11) | 3.5.0 (2026-11-10) |
|---|---|---|---|
| miRNA trưởng thành hsa | 2656 | 2656 | 2656 |
| Thiết kế được / thất bại | 2253 / 403 | 2253 / 403 | 2253 / 403 |
| Mồi xuôi đổi so với lần trước | 197 | 434 | — |
| Số cặp | 5.983.968 | 5.983.968 | 5.983.968 |
| Ngoài đường chéo HIGH / MEDIUM / LOW | 214 / 100 / 20.700 | 208 / 103 / 20.710 | 211 / 102 / 20.708 |
| Kiểm tra đường chéo (R(i, i) là cực đại của hàng) | đạt | đạt | đạt |
| Kiểm tra hợp lý: R trung bình của cặp chỉ khác 1–2 vị trí so với cặp ngẫu nhiên | 0,1445 so với 0,000011 | 0,1408 so với 0,000011 | 0,1414 so với 0,000011 |

- **403 thiết kế thất bại** đều do không có ứng viên mồi xuôi hợp lệ với tham số mặc định; nhóm này có GC trung vị 70 %.
- **Đỉnh LOW:** 20.108 cặp LOW có R = 2^−8,3 (≈ 0,32 %). Đó là trần của trục FWD: mồi RT bắt được off-target nhưng mồi xuôi không bám.
- **Mức:** HIGH < 3,3, MEDIUM < 4,3, LOW < 10, NONE ≥ 10 (Cq).
- **Không hiệu chỉnh bằng thực nghiệm:** dữ liệu đo của Chen 2005 (Fig. 7) và Mestdagh 2014 chưa được nhập, nên các file mẫu để trống.

---

## 5. Giới hạn nên nói thẳng nếu bị hỏi

1. **Ngưỡng −9 kcal/mol** nay cùng thang với Kang. Kang ghi ngưỡng là "−9.0 ± 1 kcal/mol" và kiểm lại thủ công bằng OligoAnalyzer 3.1 các mồi sát ngưỡng; tool dùng mốc cứng −9,0 và không có bước OligoAnalyzer. Ví dụ ebv-miR-BHRF1-1 có dimer −9,3, nằm trong dải ± 1.
2. **Kang không nêu nhiệt độ và nồng độ muối** cho RNAcofold, nên tool dùng mặc định của ViennaRNA (37 °C, Na⁺ 1,021 M). Đây là giả định.
3. **Kang sửa mồi, tool loại ứng viên.** Khi vượt ngưỡng, miPrimer đổi đuôi 5′ sang biến thể IUPAC khác hoặc bỏ các nucleotide tạo dimer; tool chọn ứng viên khác.
4. **Mồi đi qua chế độ dự phòng vẫn có thể đạt Excellent.** Tiêu chí dimer chỉ nặng 0,08, nên điểm 0 ở tiêu chí này chỉ làm tổng giảm khoảng 8,4. Cảnh báo `hard_filter_fallback` là tín hiệu chính, không phải điểm.
5. **Các mức điểm hairpin (−2/−3/−6 kcal/mol ở Ta)** và **cửa sổ MFE stem-loop** là mốc riêng của tool. Tiêu chí điểm hairpin gần như luôn cho 100, nên trên thực tế hairpin chỉ được xử lý bằng lọc cứng (Tm ≥ 47 °C).
7. **Quy tắc 2 (dimer đầu 3′) chưa loại ứng viên nào** trong phép đo trên 9.268 ứng viên (AUDIT REV-21, còn mở).
6. **Benchmark LNA** là kiểm chứng cài đặt, không phải kiểm chứng độc lập (mục 2).

---

## 6. Trích dẫn

### 6.1 Điều mỗi bài nói và không nói

**Busk 2014** (đối chiếu toàn văn PMC3922658):
- Nguyên văn: "all the scores for each parameter are multiplied". Điểm của cặp mồi = forward × reverse × hai hạng anneal × primer dimer.
- Table 1: tự bắt cặp hoặc dimer ở đầu 3′ dài 5 nt nhân 0,1, dài 4 nt nhân 0,2; bắt cặp bên trong dài 8 / 7 / 6 nt nhân 0,1 / 0,3 / 0,8.
- Nguyên văn: mồi có điểm 0,2 "will not be designed in practice if alternatives with more optimal 3′-ends are available", tức chỉ bị xếp hạng thấp, không bị loại.
- Loại cứng duy nhất: không ghép cặp mồi xuôi và mồi ngược chồng nhau từ 2 nt trở lên ở đầu 3′.
- **Không có:** câu "một lỗi làm hỏng cả assay"; từ "hairpin"; ngưỡng ΔG −9 kcal/mol.

**Kang et al. 2018** (đối chiếu đoạn Methods do người dùng cung cấp ngày 2026-11-11):
- Ở bước xác nhận, miPrimer xét self-dimer của mồi xuôi và hetero-dimer giữa mồi xuôi với mồi ngược phổ quát bằng ΔG (theo Shen et al. 2010).
- Nguyên văn: "when the ΔG of either the self-dimer or hetero-dimer is greater than −9.0 ± 1 kcal/mol, no additional modification is needed".
- Dưới ngưỡng: "either the 5′-tailed sequence is changed to other IUPAC alternatives or the dimer-forming nucleotides of the forward primer is removed", lặp lại đến khi đạt.
- Nguyên văn: "The ΔG value is calculated by RNAcofold algorithm using the DNA parameters (Gruber et al. 2008)". Các mồi có ΔG gây tranh cãi được kiểm lại thủ công bằng OligoAnalyzer 3.1 (Owczarzy et al. 2008), ví dụ hsa-miR-18b-5p-F ở −8,95 kcal/mol (Table 2).
- **Không có:** câu nói dimer dưới −9 gây ức chế qPCR. Câu này từng có trong chú thích code và đã được bỏ.

### 6.2 Danh mục tham khảo (đã đối chiếu PubMed qua NCBI E-utilities, 2026-11-11)

| Viết tắt | Trích dẫn đầy đủ | PMID | DOI |
|---|---|---|---|
| Chen 2005 | Chen C, Ridzon DA, Broomer AJ, et al. Real-time quantification of microRNAs by stem-loop RT-PCR. *Nucleic Acids Res.* 2005;33(20):e179. PMC1292995 | 16314309 | 10.1093/nar/gni178 |
| Busk 2014 | Busk PK. A tool for design of primers for microRNA-specific quantitative RT-qPCR. *BMC Bioinformatics.* 2014;15:29. PMC3922658 | 24472427 | 10.1186/1471-2105-15-29 |
| Kang 2018 | Kang ST, Hsieh YS, Feng CT, Chen YT, Yang PE, Chen WM. miPrimer: an empirical-based qPCR primer design method for small noncoding microRNA. *RNA.* 2018;24(3):304–312. Epub 2017-12-05. PMC5824350 | 29208706 | 10.1261/rna.061150.117 |
| Gruber 2008 | Gruber AR, Lorenz R, Bernhart SH, Neuböck R, Hofacker IL. The Vienna RNA websuite. *Nucleic Acids Res.* 2008;36(Web Server issue):W70–W74. PMC2447809 | 18424795 | 10.1093/nar/gkn188 |
| Owczarzy 2008 | Owczarzy R, Tataurov AV, Wu Y, et al. IDT SciTools: a suite for analysis and design of nucleic acid oligomers. *Nucleic Acids Res.* 2008;36(Web Server issue):W163–W169. PMC2447751 | 18440976 | 10.1093/nar/gkn198 |
| Shen 2010 | Shen Z, Qu W, Wang W, et al. MPprimer: a program for reliable multiplex PCR primer design. *BMC Bioinformatics.* 2010;11:143. PMC2858037 | 20298595 | 10.1186/1471-2105-11-143 |
| Lorenz 2011 | Lorenz R, Bernhart SH, Höner zu Siederdissen C, et al. ViennaRNA Package 2.0. *Algorithms Mol Biol.* 2011;6:26. PMC3319429 | 22115189 | 10.1186/1748-7188-6-26 |
| Mathews 2004 | Mathews DH, Disney MD, Childs JL, Schroeder SJ, Zuker M, Turner DH. Incorporating chemical modification constraints into a dynamic programming algorithm for prediction of RNA secondary structure. *Proc Natl Acad Sci USA.* 2004;101(19):7287–7292. PMC409911 | 15123812 | 10.1073/pnas.0401799101 |
| SantaLucia 1998 | SantaLucia J Jr. A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics. *Proc Natl Acad Sci USA.* 1998;95(4):1460–1465. PMC19045 | 9465037 | 10.1073/pnas.95.4.1460 |
| SantaLucia & Hicks 2004 | SantaLucia J Jr, Hicks D. The thermodynamics of DNA structural motifs. *Annu Rev Biophys Biomol Struct.* 2004;33:415–440 | 15139820 | 10.1146/annurev.biophys.32.110601.141800 |
| Untergasser 2012 | Untergasser A, Cutcutache I, Koressaar T, et al. Primer3—new capabilities and interfaces. *Nucleic Acids Res.* 2012;40(15):e115 | 22730293 | 10.1093/nar/gks596 |
| Stadhouders 2010 | Stadhouders R, Pas SD, Anber J, Voermans J, Mes TH, Schutten M. The effect of primer-template mismatches on the detection and quantification of nucleic acids using the 5′ nuclease assay. *J Mol Diagn.* 2010;12(1):109–117. PMC2797725 | 19948821 | 10.2353/jmoldx.2010.090035 |
| Kwok 1990 | Kwok S, Kellogg DE, McKinney N, et al. Effects of primer-template mismatches on the polymerase chain reaction: human immunodeficiency virus type 1 model studies. *Nucleic Acids Res.* 1990;18(4):999–1005. PMC330356 | 2179874 | 10.1093/nar/18.4.999 |
| Czimmerer 2013 | Czimmerer Z, Hulvely J, Simandi Z, et al. A versatile method to design stem-loop primer-based quantitative PCR assays for detecting small regulatory RNA molecules. *PLoS One.* 2013;8(1):e55168. PMC3561390 | 23383094 | 10.1371/journal.pone.0055168 |
| Schamberger 2014 | Schamberger A, Orbán TI. 3′ IsomiR species and DNA contamination influence reliable quantification of microRNAs by stem-loop quantitative PCR. *PLoS One.* 2014;9(8):e106315 | 25170848 | 10.1371/journal.pone.0106315 |

**Lưu ý về năm của Kang.**
- Bài công bố trực tuyến ngày 2017-12-05 và in trong số tháng 3/2018, nên trích dẫn chuẩn là **Kang et al. 2018**.
- Code và tài liệu trong repo vẫn dùng nhãn `[Kang17]`, trong khi slide và khóa luận nên ghi 2018. Ghi "2017" thì phải ghi rõ đó là năm công bố trực tuyến, và dùng nhất quán.

**Lưu ý về Mathews 2004.** "DNA Mathews 2004" là tên bộ tham số DNA trong ViennaRNA (`params_load_DNA_Mathews2004`). Bài PNAS ở trên là bài Mathews 2004 thường được gán cho bộ tham số này, nhưng chưa được đối chiếu với tài liệu ViennaRNA. Kiểm trước khi trích riêng; nếu không, chỉ cần trích ViennaRNA (Lorenz 2011) và ghi "tham số DNA".

### 6.3 Nguồn chưa xác minh hoặc không phải bài báo

Chỉ dùng trên slide kèm ghi chú như cột phải:

| Nguồn | Dùng cho | Ghi chú |
|---|---|---|
| Premier Biosoft (trang hướng dẫn) | Dimer đầu 3′ −5 kcal/mol | Trang web, không phải bài báo |
| IDT (hướng dẫn thiết kế mồi) | %GC, amplicon, GC clamp | Trang web của nhà cung cấp |
| PrimerAST (nhãn `[PAST24]`, PMC13172444 theo SPEC) | GC-skew, chênh Tm ≤ 2 °C | Chưa đối chiếu; trong code nhãn năm còn lệch (2024 / 2026) |
| Primer3 manual (https://primer3.org/manual.html, đọc ngày 2026-11-11, copyright 1996–2022) | Mặc định `PRIMER_MAX_HAIRPIN_TH`, `PRIMER_MAX_SELF_ANY_TH`, `PRIMER_MAX_SELF_END_TH` = 47 °C; `PRIMER_MIN_TM` = 57.0 | **Đã đối chiếu nguyên văn.** Đây là tài liệu phần mềm, không phải bài báo; phần mềm được trích qua Untergasser 2012. Tài liệu chỉ nêu 47 °C như một quan hệ với mặc định của `PRIMER_MIN_TM`, không trình bày nó như một kết quả thực nghiệm |
| Primer3Plus | `PRIMER_MAX_END_STABILITY` = 9,0 | Giá trị theo chú thích trong code; chưa đối chiếu với trang Primer3Plus |
| McTigue 2004 (PMID 15122905), Owczarzy 2011 | Tham số và dữ liệu LNA | Lấy từ danh mục tham khảo trong repo, chưa đối chiếu lại trong đợt này |
| Đoạn trích Busk 2014 trong tài liệu lưu trữ: "phạt CCC / G-run ở 3′" gán thêm cho Kang | GC clamp | Phần gán cho Kang chưa được đối chiếu |

---

## 7. File liên quan trong repo

- `SPEC_algorithm.md`: changelog 2026-11-11 và §12 "Lọc cứng trước khi chấm điểm".
- `SPEC_phase3.md`: §8.16 (mô hình ΔCq), §8.19 (BLAST v7), §8.20 (ma trận).
- `AUDIT_REPORT.md`:
  - REV-17: đính chính trích dẫn Busk;
  - REV-18: nguồn của các ngưỡng lọc cứng;
  - REV-19: chuyển ΔG dimer sang RNAcofold;
  - REV-20: lọc cứng hairpin theo Tm ≥ 47 °C;
  - REV-21: quy tắc 2 không kích hoạt (còn mở).
- `docs/DECISIONS_crossreactivity.md`: các quyết định khoa học của ma trận (D-1 … D-20).
- `benchmark/dimer_dg_method_compare.json`, `validation/results.csv`, `outputs/crossreactivity_metadata.json`.
