# RESEARCH_QUESTIONS_UX.md — Câu hỏi nghiên cứu & vấn đề thiết kế primer → Roadmap UX
# HG Lab · Stem-loop RT-qPCR Primer Designer · 2026-07-04
# Sync: SPEC_phase2, SPEC_phase4/5/6, RESEARCH_INSIGHTS.md, RESEARCH_INSIGHTS_probe.md
# Nguồn học thuật: PubMed (DOI dẫn trong từng mục)

---

## 0. Mục đích
Liệt kê những gì thực sự làm nhà nghiên cứu vướng khi thiết kế primer cho phản ứng
stem-loop RT-qPCR, và map từng vấn đề sang **tính năng/UX cụ thể** để tiếp tục tối ưu tool.
Sắp theo mức tác động lên trải nghiệm người dùng.

**Ưu tiên UX (top 5):**
1. Tách Tm (binding vs full) + gắn nhãn RT primer là *approximate (DNA:RNA)*.
2. Trực quan hoá specificity / family map.
3. Normalization advisor (chọn reference đúng).
4. Preanalytical advisor theo loại mẫu (biofluid/hemolysis/spike-in).
5. Xuất validation checklist (NTC/no-RT/melting/standard curve).

---

## A. Vấn đề NGAY tại bước thiết kế primer (lõi tool)

### A1. Tm vùng đặc hiệu quá ngắn (10–12 nt) — bound fraction ≠ Tm
Forward chỉ bám thật 10–12 nt; phần còn lại là tail nhân tạo. Hai primer cùng Tm có thể có
*bound fraction* rất khác nhau ở Ta=60 °C (SantaLucia "myth #3"; đã dự trù Phase 3).
- **UX:** hiển thị **tách bạch** binding-region Tm vs full-primer Tm **và** bound fraction;
  cảnh báo khi vùng thật quá yếu, thay vì một con số Tm gộp gây hiểu nhầm.
- **Module:** `thermodynamics.py` (2-step Tm đã có) + Phase 3 bound fraction.

### A2. Tm của RT primer là DNA:RNA hybrid — primer3 (DNA:DNA) KHÔNG đúng 
RT primer bám vào miRNA (RNA). NN DNA:DNA sai cho bước này (RESEARCH_INSIGHTS E.1;
cần NUPACK/RNAstructure — dependency mới, để sau).
- **UX (quan trọng, giữ uy tín):** gắn nhãn RT Tm là *approximate (DNA:RNA hybrid)*;
  **không tuyên bố độ chính xác Tm** cho RT primer (đã loại khỏi benchmark ở SPEC_phase6 §C.1).
- **Module:** output/label; validation `check_tm.py` (đã loại nhánh RT).
- **DONE (2026-07-04):**
  - Tách bạch chemistry: `tm_full_chemistry: "DNA:DNA"`, `tm_hybrid → chemistry: "DNA:RNA"`.
  - Sugimoto 1995 NN table triển khai thuần Python, không dependency mới (`algorithm/hybrid_tm.py`).
  - `USE_HYBRID_TM = True` (constants.py): A/B toggle để so sánh.
  - RT primer overhang hybrid Tm (4–8 nt × miRNA) tính bằng Sugimoto 1995 tại 4 μM, 75 mM KCl.
  - UI: badge "Tm: modeled (DNA:RNA, Sugimoto 1995)" + Tooltip (caveats) khi USE_HYBRID_TM=True;
    badge "Tm: approximate (DNA:RNA)" khi False. Full-primer Tm vẫn hiện nhãn "indicative".
  - NUPACK/RNAstructure = KHÔNG thêm (không dependency mới).

### A3. Phân biệt trong họ miRNA khác nhau 1 nt (let-7, miR-200…)
Đặc hiệu do **RT 3′ overhang + forward** quyết định.
- Bằng chứng: thiết kế RT primer riêng phân biệt được **1 nt** — Wang 2017
  [DOI](https://doi.org/10.3892/mmr.2017.8297); hệ tối ưu đạt cross-reaction let-7 **< 5%**
  và mature:pre **270:1** — Jung 2020 [DOI](https://doi.org/10.1016/j.bios.2020.112301);
  đặc hiệu quy về RT+forward — Kang 2012 [DOI](https://doi.org/10.1371/journal.pone.0048536).
- **UX:** khi 5′ region không đủ unique trong họ → đề xuất kéo dài overhang / đổi vị trí;
  **hiển thị "specificity map"** cho biết nucleotide nào đang gánh việc phân biệt.
- **Module:** `specificity_check/family_crossreactivity.py` (đã có) → thêm visualization.

### A4. isomiR — đặc biệt biến thể 3′
RT overhang bám đúng 3′-end mature → **3′ isomiR** (thêm/cắt nt, non-templated addition)
ảnh hưởng trực tiếp hiệu suất RT; 5′ isomiR ảnh hưởng forward.
- **UX:** ngoài flag 5′ isomiR sẵn có, **thêm cảnh báo 3′ isomiR cho RT overhang** —
  vì đó mới là vị trí overhang bám.
- **Module:** `specificity_check/isomir_flag.py` + `known_5prime_isomir_mirnas.json`
  (bổ sung dữ liệu 3′).

### A5. Vị trí đa hình / chỉnh sửa dưới primer (SNP, A-to-I editing)
Analog "primer trên subtype polymorphism" (Hoffman 2008, đã dẫn trong SPEC_phase6 §A.9).
- **UX:** cross-check vị trí biên tập/SNP đã biết; cảnh báo nếu forward/overhang phủ lên.
- **Module:** mở rộng specificity_check (dữ liệu editing/SNP offline).

### A6. Mature vs precursor selectivity
Người dùng thường không biết assay có bắt nhầm pre-miRNA không.
- **UX:** báo **định tính** mức selectivity kỳ vọng dựa trên độ dài overhang + steric (Chen05).
- **Module:** `stemloop_rt.py` (report field).

### A7. Hình học amplicon rất ngắn (~60 bp) — probe khó nhét vừa
(Chi tiết ở RESEARCH_INSIGHTS_probe.md §2.3) — forward+reverse chiếm phần lớn 60 bp.
- **UX:** kiểm tra không gian probe ngay khi thiết kế; tự đề xuất MGB/universal khi single-Q
  không vừa.

---

## B. Vấn đề NGOÀI primer nhưng quyết định thành–bại (Advisor — tăng tin cậy)

### B1. Chuẩn hoá (normalization) — nguồn sai số LỚN NHẤT của miRNA qPCR
Không có "housekeeping" phổ quát cho miRNA; phải chọn reference bằng geNorm/NormFinder,
panel lớn → **global-mean**.
- Bằng chứng: Hellemans 2014 [DOI](https://doi.org/10.1007/978-1-4939-0733-5_3);
  chọn 3 miRNA ổn định nhất bằng nhiều thuật toán — Hacimoto 2024
  [DOI](https://doi.org/10.1371/journal.pone.0306657);
  reference phụ thuộc loại mẫu — Fujimoto 2018 [DOI](https://doi.org/10.1016/j.fsigen.2018.08.010),
  Liang 2018 [DOI](https://doi.org/10.1371/journal.pone.0194436).
- **UX:** đưa normalization thành **bước rõ ràng**; gợi ý reference candidate theo loại mẫu;
  link geNorm/NormFinder. (Đã có P7/P8 trong SPEC_phase6 §E.2 — nâng cấp hiển thị.)

### B2. Tiền phân tích cho miRNA tuần hoàn (biofluid)
- **Hemolysis** làm sai lệch miR-16/miR-451a & miRNA hồng cầu — McDonald 2011
  [DOI](https://doi.org/10.1373/clinchem.2010.157198); signature phát hiện tán huyết —
  Smith 2022 [DOI](https://doi.org/10.3390/genes13071288).
- **Loại ống chống đông:** EDTA tăng tán huyết, đổi profile — Zhelankin 2022
  [DOI](https://doi.org/10.3390/ijms231810340).
- **Spike-in cel-miR-39** hiệu chỉnh bias chiết tách (đã có cel-miR-39-3p trong tool).
- **UX:** khi sample = plasma/serum → bật advisory hemolysis QC + spike-in + gợi ý ống chống đông.

### B3. Biến thiên chiết tách RNA & target thấp copy
Kit khác nhau cho Cq khác nhau đáng kể; low-abundance cần pre-amplification.
- Bằng chứng: Tanriverdi 2016 [DOI](https://doi.org/10.1016/j.ab.2016.02.019);
  preamp giữ định lượng tương đối — Chen09/Tan15 (SPEC_phase6 §E.1).
- **UX:** advisory pre-amp cho target thấp + cảnh báo tăng phương sai ở copy thấp.

### B4. Validation & MIQE
Người dùng cần checklist nghiệm thu: standard curve ≥5 điểm, efficiency = 10^(−1/slope)−1, R²,
**NTC, no-RT, melting curve**.
- **UX:** xuất sẵn **validation checklist/protocol** đi kèm bộ primer → tool = thiết kế + nghiệm thu.
- **Module:** formatter/export (đã có MIQE export SPEC_phase4 §8 — mở rộng).

---

## C. Câu hỏi mở ở tầng "khoa học của tool" (paper / roadmap)

### C1. Không dự đoán được efficiency từ thiết kế (calibration BLOCKED)
Thiếu dữ liệu hợp lệ (SPEC_phase6 PART D).
- **UX trung thực:** luôn gọi output là *"predicted design quality"*, KHÔNG phải
  *"predicted efficiency"*. Giữ uy tín khoa học.

### C2. Thiếu mô hình nhiệt động DNA:RNA cho RT primer
Hướng tính năng tương lai lớn nhất (NUPACK/RNAstructure).
- **DONE (2026-07-04):** Sugimoto 1995 nearest-neighbor triển khai thuần Python, không dependency.
  Informational only, not scored. NUPACK/RNAstructure vẫn không dùng.
  Stub cho future extension để trong `thermodynamics.py` (comment FUTURE).

### C3. Benchmark vs miRprimer/miPrimer
Đã có ở SPEC_phase6 §C.3 → đưa kết quả so sánh vào UI để người dùng thấy vị thế tool.

---

## D. Bảng tổng hợp priority → module

| # | Vấn đề | UX/Feature | Module | Priority |
|---|---|---|---|---|
| A1 | Tm ngắn / bound fraction | Tách Tm + bound fraction + cảnh báo | thermodynamics.py | ★★★ |
| A2 | RT Tm DNA:RNA | Nhãn "approximate"; không claim | label/check_tm.py | ★★★ |
| A3 | Phân biệt họ miRNA | Specificity/family map | family_crossreactivity.py | ★★★ |
| B1 | Normalization | Advisor + reference gợi ý | protocol_kb.json | ★★★ |
| B2 | Preanalytical biofluid | Advisor theo sample-type | protocol_kb.json | ★★ |
| B4 | Validation/MIQE | Xuất checklist nghiệm thu | formatter/export | ★★ |
| A4 | 3′ isomiR | Cảnh báo overhang | isomir_flag.py | ★★ |
| A5 | SNP/editing | Cross-check vị trí | specificity_check | ★★ |
| A6 | Mature vs pre | Selectivity định tính | stemloop_rt.py | ★ |
| A7 | Probe fit amplicon | Kiểm tra không gian | probe_design.py | ★ |
| B3 | Low-abundance/preamp | Advisory | protocol_kb.json | ★ |
| C1 | Efficiency không dự đoán | Nhãn "design quality" | output | ★★★ |

**Bất biến:** không đổi SCORING_WEIGHTS_V4; advisory là mô tả (có DOI + disclaimer),
không đổi thuật toán lõi.

---

*Hết. Thông tin học thuật trích từ PubMed — DOI dẫn trong từng mục.*
