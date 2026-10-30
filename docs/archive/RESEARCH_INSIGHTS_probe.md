# RESEARCH_INSIGHTS_probe.md — Đánh giá thiết kế probe cho Stem-loop RT-qPCR
# HG Lab · 2026-07-04 · Sync: SPEC_phase2 §K, SPEC_phase6 PART A
# Nguồn học thuật: PubMed (DOI dẫn trong từng mục)

---

## 0. Câu hỏi & kết luận

**Câu hỏi:** Thiết kế probe trong SPEC_phase2 §K + SPEC_phase6 PART A đã đủ độ chính xác và
đặc hiệu cho miRNA chưa? Cần thêm yếu tố gì?

**Kết luận ngắn:**
- Về **hóa học/tín hiệu**: đủ chuẩn TaqMan cho probe single-quenched. MGB Tm boost còn thô.
- Về **đặc hiệu miRNA**: probe **không** phải nơi tạo ra độ đặc hiệu. Spec đã đúng khi để
  specificity ở module primer (Phase 2 §2.8.2). Cần (1) nêu rõ giới hạn, (2) siết vài chỗ,
  (3) bổ sung một số tùy chọn.

---

## 1. Đặc hiệu miRNA KHÔNG đến từ probe (insight cốt lõi)

Trong stem-loop RT-qPCR, khả năng phân biệt miRNA nằm ở **stem-loop RT primer** (đoạn 3′ overhang
6 nt bắt cặp với 3′-end của mature miRNA) và **forward primer** (vùng 5′), **không** ở probe.

| Bằng chứng PubMed | Phát hiện | Ý nghĩa cho probe |
|---|---|---|
| **[Jung20]** Biosens Bioelectron 2020;163:112301 · [DOI](https://doi.org/10.1016/j.bios.2020.112301) | mature:precursor = **270:1**; cross-reaction let-7 **< 5%** | Discrimination do RT + forward, **không do probe** |
| **[Wang17]** Mol Med Rep 2017;17(3):3690–3696 · [DOI](https://doi.org/10.3892/mmr.2017.8297) | Phân biệt let-7 khác **1 nt** bằng thiết kế **RT primer** khác nhau | Probe không tham gia phân biệt |
| **[Kang12]** PLoS One 2012;7(11):e48536 · [DOI](https://doi.org/10.1371/journal.pone.0048536) | Specificity quy về RT primer + forward primer | Xác nhận nguyên lý |

**Hệ quả trực tiếp cho 2 mode probe của tool:**
- Mode **"universal"** (bám hoàn toàn stemloop body, [RNA13]): đóng góp specificity trình tự = **0**.
  Phát tín hiệu cho *mọi* amplicon dùng chung stemloop body, kể cả **sản phẩm khuếch đại không
  đặc hiệu** miễn có stemloop → không phân biệt được sản phẩm đúng/sai.
- Mode **"custom" junction**: chỉ phủ ~7 nt phía 5′ miRNA (`PROBE_JUNCTION_OVERLAP_MIRNA_SIDE`).
  Điểm biến thiên giữa các họ (vd let-7) thường ở giữa/3′ → tăng discrimination không đáng kể.

→ **Đây là điều đúng khoa học, không phải lỗi.** Nhưng phải **ghi rõ trên UI/Advisor** để người
dùng không hiểu nhầm probe gánh specificity.

---

## 2. Độ chính xác — các chỗ cần siết

### 2.1 Tm probe (DNA:DNA) — GIỮ NGUYÊN
Probe lai với cDNA (DNA:DNA) → primer3 nearest-neighbor (§K7, `PROBE_DV_CONC_DEFAULT`) là đúng.
Disclaimer Mg²⁺ đã có. Không cần đổi.

### 2.2 MGB boost +15 °C là quá thô — HẠ ĐỘ TIN
`PROBE_MGB_TM_BOOST = 15.0` (§K2) là hằng số cố định, nhưng Tm thực của MGB phụ thuộc trình tự &
độ dài, không tuyến tính. **Đề xuất:** coi length MGB (13–20 nt) là mode "cần xác nhận với nhà
cung cấp", **không dùng con số +15 để lọc/loại candidate**; chỉ dùng để hiển thị + cảnh báo.

### 2.3 Ràng buộc không gian trên amplicon ngắn — ĐƯA VỀ MODULE PROBE (đừng defer Phase 4)
Amplicon stem-loop rất ngắn (`AMPLICON_MIN_QPCR = 60` bp). Forward (~12–22 nt) + universal reverse
(20 nt) đã chiếm phần lớn → probe single-Q **18–27 nt** (mode custom) **có thể không nhét vừa**
giữa 3′ forward và 5′ reverse. Đây chính là lý do assay thương mại (ABI TaqMan) dùng **MGB ngắn**
và Kramer dùng **universal probe**.
**Đề xuất:** kiểm tra ngay trong `probe_design.py`:
```
probe_3prime_pos + len(probe) <= cdna_len - len(UNIVERSAL_REVERSE)
```
Nếu không đạt với single-Q → tự đề xuất MGB (ngắn) hoặc universal mode. Hiện `PROBE_MIN_END_DISTANCE`
(§K8) đang để -1 và defer — nên kích hoạt sớm.

---

## 3. Yếu tố nên bổ sung

### 3.1 Thêm probe LNA (probeType="lna")
Với target ngắn như miRNA, LNA nâng Tm và cải thiện cả độ nhạy lẫn phân biệt mismatch.
- **[Liu25]** Clin Chem Lab Med 2025;64(3):717–731 · [DOI](https://doi.org/10.1515/cclm-2025-0824):
  probe gắn **LNA tăng 32% số droplet dương** trong ddPCR miR-192-5p; chọn probe theo Ct thấp nhất
  (Ct < 35), tuân MIQE.
- **Đề xuất:** thêm mode `probeType="lna"` song song single-Q/MGB. Đây là hướng hiệu quả nhất
  nếu muốn tăng đặc hiệu **ở tầng probe** (LNA tại vị trí mismatch tăng discrimination).

### 3.2 Double-quenched chemistry (ZEN/TAO)
Cho probe dài → giảm background, tăng signal-to-noise. Probe hiện chỉ giả định single-quench.
Bổ sung như tùy chọn reporter/quencher (advisory, không đổi thuật toán).

### 3.3 Universal Probe Library (UPL) — củng cố mode universal
- **[Gyongyosi14]** Methods Mol Biol 2014;1182:105–119 · [DOI](https://doi.org/10.1007/978-1-4939-1062-5_10):
  UPL probe dùng được với stem-loop RT-qPCR (FFPE, dịch cơ thể). Củng cố mode "universal" nhưng
  **kèm cảnh báo giới hạn** ở §1.

### 3.4 Advisor note bắt buộc (UI English)
Thêm vào `ProbeCard.jsx`:
> "The probe does not confer miRNA sequence specificity. Discrimination between miRNAs is
> delivered by the stem-loop RT primer (3′ overhang) and the forward primer. A universal probe
> generates signal for any amplicon sharing the stem-loop body, including non-specific products."

### 3.5 Validation ướt (đúng tinh thần Phase 6 PART D — blocked)
`no-G-5′`, `G≤C` chỉ là heuristic. Đặc hiệu thật phải xác nhận bằng **melting curve, no-RT
control, NTC**. Ghi vào protocol wet-lab future-work.

---

## 4. Bảng hành động cụ thể (sync §K / PART A)

| # | Việc | File / hằng số | Loại |
|---|---|---|---|
| 1 | Ghi rõ probe không tạo specificity | `ProbeCard.jsx`, Advisor | UI/note |
| 2 | Cảnh báo giới hạn universal probe (tín hiệu cho sản phẩm không đặc hiệu) | §A.4 warnings | Logic nhẹ |
| 3 | Không dùng MGB +15 °C để loại candidate | `PROBE_MGB_TM_BOOST` §K2 | Sửa dùng |
| 4 | Kích hoạt kiểm tra không gian probe trên amplicon | `probe_design.py`, `PROBE_MIN_END_DISTANCE` | Logic |
| 5 | Thêm mode `probeType="lna"` | §K2 constants + probe_design | Tính năng |
| 6 | Tùy chọn double-quenched (advisory) | Advisor/note | Note |
| 7 | Protocol validation ướt (melting/NTC/no-RT) | wet-lab future-work | Doc |

**Không đổi:** Tm DNA:DNA bằng primer3; SCORING_WEIGHTS_V4 (probe vẫn là quality-check, không
nhét vào weighted-sum).

---

*Hết. Thông tin học thuật trích từ PubMed — DOI dẫn trong từng mục.*
