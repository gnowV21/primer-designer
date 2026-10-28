# Tài liệu giải thích Web App "Primer Designer" (Stem-loop RT-qPCR)

Tài liệu này giải thích cách web app được xây dựng và đi sâu vào từng thành phần (component) của trang **Designer** (`/search`) — trang chính nơi người dùng nhập thông tin để thiết kế bộ 3 primer cho stem-loop RT-qPCR.

---

## 1. Kiến trúc tổng thể

Đây là một **split-stack app**: backend Python/Flask và frontend React/Vite chạy như hai tiến trình độc lập khi phát triển.

```
Browser → Vite dev server (:5173) → proxy /api/* → Flask (:5000) → miRBase REST API
                                                                  → RNAcentral REST API (fallback)
                                                                  → SQLite cache (local_db)
```

- **Backend** (`backend/`): Flask 3 + flask-cors + requests. Chỉ có 2 endpoint: `GET /api/health` và `GET /api/mirbase/<mirna_id>`.
- **Frontend** (`frontend/`): React 18 + Vite 5 + Tailwind 3 + React Router v6 + Axios. Không dùng Redux, Formik hay UI library nào — toàn bộ state quản lý bằng React hooks thuần.

### Routing (`App.jsx`)
- `/` → redirect đến `/search`
- `/home` → `HomePage`
- `/roadmap` → `RoadmapPage`
- `/search` → `SearchPage` (trang Designer — trọng tâm tài liệu này)

Layout chung: `Navbar` (trên) → `<main>` chứa route hiện tại + `ChatbotPanel` (panel chat bên phải, hiện tại chỉ là placeholder "coming soon") → `Footer` (dưới).

---

## 2. Luồng dữ liệu của trang Designer

`pages/SearchPage/index.jsx` là **nơi duy nhất giữ state** của toàn bộ form. Mọi component con (group) đều là *controlled component* "dumb" — nhận `data` (phần state của riêng nó) và các hàm callback (`onChange`, `onError`, `onFirstOpen`), rồi báo thay đổi lên cha qua các callback này. Không có group nào tự giữ state nghiệp vụ lâu dài (chỉ giữ state UI tạm như "đang mở panel nào").

State chính trong `index.jsx`:

- `formData` — object gồm 6 nhóm con: `sequence`, `thermodynamic`, `primerConstraints`, `qpcr`, `detectionMethod`, `experimentalContext`. Giá trị khởi tạo lấy từ `constants/defaults.js`.
- `errors` — map tên field → thông báo lỗi.
- `seqAnalysis` — kết quả tính toán sinh học từ chuỗi miRNA (qua `utils/seqAnalysis.js`), tính lại mỗi khi chuỗi thay đổi (`useMemo`), rồi truyền xuống các group cần dùng để hiển thị cảnh báo.
- `activeSection`, `visitedSections`, `sectionOpenRequests` — phục vụ thanh điều hướng mini-nav bên cạnh (cuộn tới section, đánh dấu đã xem, mở section theo yêu cầu).
- `resetKey`, `isSubmitting` — phục vụ nút Submit.

Khi bấm Submit: hiện tại `handleSubmit()` chỉ `console.log` toàn bộ `formData` rồi reset form sau 800ms — **thuật toán thiết kế primer thật sự (`POST /api/design`) chưa được cài đặt**, đây là kế hoạch cho Week 2 (theo `SPEC_week1.md`).

Lệnh gọi API duy nhất trong toàn frontend là `GET /api/mirbase/<id>`, thực hiện trong `SequenceGroup` qua hook `useMiRBase`.

---

## 3. Các thành phần UI dùng chung (`components/ui/`)

| Component | Vai trò |
|---|---|
| `CollapsibleSection` | Khung thẻ có thể đóng/mở, bọc mỗi group. Hiển thị tiêu đề, tooltip, dấu đỏ/vàng báo lỗi/cảnh báo khi thu gọn. Hỗ trợ mở từ xa qua `openRequested` (dùng cho mini-nav) và bắn `onFirstOpen` một lần duy nhất khi user mở lần đầu (để đánh dấu "đã xem"). |
| `RangeSlider` | Thanh trượt 2 đầu (min/max) dùng cho Tm range, GC%, chiều dài primer, kích thước amplicon. Vẽ track gradient teal giữa 2 đầu, không cho đầu min vượt qua đầu max và ngược lại. |
| `NumInput` | Input số có xử lý riêng để cho phép xoá trắng ô input mà không bị tự nhảy về 0 (giữ state `raw` dạng string song song với giá trị thật). |
| `Toggle` | Công tắc bật/tắt kiểu iOS, dùng cho "3′ GC Clamp". |
| `Tooltip` | Icon "?" hiện hộp giải thích khi hover/focus, tự lật sang trái nếu không đủ chỗ bên phải, render qua `createPortal` để không bị các thẻ cha cắt mất. |

---

## 4. Chi tiết 6 nhóm (sections) trong trang Designer

Thứ tự hiển thị thực tế trên trang: **Sequence → Detection Method → Thermodynamic → Primer Constraints → qPCR Conditions → Experimental Context**.

### 4.1. Sequence Group — Tìm kiếm & phân tích chuỗi miRNA

Đây là section luôn mở mặc định, vì mọi cảnh báo sinh học ở các section khác phụ thuộc vào kết quả tính ở đây.

**Input:** một ô tìm kiếm duy nhất, nhận 1 trong 3 dạng:
- Tên miRNA (ví dụ `hsa-miR-21-5p`)
- Mã miRBase accession (ví dụ `MIMAT0000076`)
- Chuỗi RNA thô (ví dụ `UAGCUUAUCAGACUGAUGUUGA`)

App tự nhận diện loại input bằng regex (`detectInputType`): mã `MIMAT\d+` → accession; chuỗi chỉ gồm A/U/G/C dài ≥10 → sequence; còn lại → name.

- Nếu là **chuỗi thô**: validate cục bộ (`validateSequence`) — báo lỗi nếu còn chứa `T` (yêu cầu đổi sang `U` vì là RNA), chứa ký tự lạ ngoài A/U/G/C, dài <15 nt (quá ngắn) hoặc >30 nt (quá dài). Nếu hợp lệ, vẫn gọi ngầm `fetchMiRNA` để cố gắng tìm tên/ID tương ứng trong miRBase.
- Nếu là **tên/accession**: gọi `fetchMiRNA(query)` để tra cứu qua backend.

**Kết quả tra cứu** hiển thị: tên, ID, chuỗi đầy đủ (vùng seed nt 2–8 được tô màu riêng), badge chiều dài (nt), %GC toàn chuỗi, %GC vùng seed.

**Các cảnh báo sinh học hiển thị** (tính từ `seqAnalysis`):
- Chuỗi ngắn (15–17 nt) hoặc dài (26–30 nt) bất thường — có thể là đoạn miRNA chưa hoàn chỉnh hoặc isomiR.
- %GC toàn chuỗi <30% (giàu AU, Tm thấp) hoặc >70% (giàu GC, dễ tạo cấu trúc bậc 2).
- %GC ở 6 nt cuối (vùng bắt cặp với RT primer) <33% (overhang Tm quá thấp, dễ tách rời) hoặc >83% (dễ bắt cặp không đặc hiệu).
- 6 nt cuối có ≥3 ký tự lặp liên tiếp — ảnh hưởng độ chính xác tổng hợp cDNA.
- Không bắt đầu bằng U ở đầu 5′ — không điển hình (phần lớn miRNA trưởng thành bắt đầu bằng U để được Ago2 nạp vào).
- Có ≥4 ký tự lặp liên tiếp ở bất kỳ đâu trong chuỗi — chuỗi đồng nhất (homopolymer), thuật toán sẽ tránh vùng này nếu có thể.

### 4.2. Detection Method Group — Phương pháp phát hiện tín hiệu

- **Signal detection**: chọn `TaqMan probe` (mặc định) hoặc `SYBR Green`.
  - TaqMan: cần probe ở vị trí nối miRNA–stem-loop, cần nhóm MGB để đạt Tm ≥70°C trên đoạn ngắn 12–17 nt.
  - SYBR Green: không thiết kế probe; amplicon nên ≤120 bp để giảm primer dimer; bắt buộc phân tích melting curve sau mỗi run.
- **Quantification mode**: `Absolute` hoặc `Relative` (mặc định). Absolute = số copy/thể tích; Relative = fold-change so với gene tham chiếu qua công thức 2^(−ΔΔCt).
  - Nếu chọn Relative: hiện dropdown **Reference gene**: `miR-16` (ổn định ở đa số mô), `U6` (phổ biến cho serum/plasma), `RNU48` (ổn định ở mô người), `cel-miR-39` (spike-in control của C. elegans cho serum/plasma), hoặc `Custom` (tự nhập miRBase ID).
- **Advanced specificity options** (mở rộng, đóng mặc định) — 3 checkbox:
  - *Family discrimination* (bật mặc định) — phạt các candidate có nguy cơ bắt nhầm thành viên khác trong cùng họ miRNA (quan trọng với họ let-7 gồm 13 thành viên chỉ khác 1–2 nt).
  - *Precursor cross-reactivity check* (tắt mặc định) — kiểm tra khả năng bắt nhầm với pre-miRNA; chỉ nên bật khi mẫu có nồng độ pre-miRNA cao.
  - *Re-folding protocol* (bật mặc định) — sinh thêm protocol nhiệt (95°C 10 phút → hạ nhiệt chậm → giữ 60°C) trong kết quả xuất ra.

### 4.3. Thermodynamic Group — Tham số nhiệt động học của phản ứng

Các tham số ảnh hưởng đến việc tính Tm (nearest-neighbor, theo công thức SantaLucia ở Week 2):

| Field | Mặc định | Khoảng | Ý nghĩa |
|---|---|---|---|
| Tm range (min/max) | 58–62°C | 50–70°C | Khoảng Tm mục tiêu; 58–62°C là tối ưu cho stem-loop RT-qPCR |
| [Na⁺] | 50 mM | 1–500 mM | Lực ion đơn hoá trị, ảnh hưởng hiệu chỉnh Tm |
| [K⁺] | 50 mM | 0–200 mM | Taq bị ức chế khi >75–100 mM |
| [Mg²⁺] tổng | 1.5 mM | 0.5–5.0 mM | Cofactor của polymerase; bị dNTP chelate hóa |
| [dNTP] tổng | 0.2 mM | 0.05–1.0 mM | Tổng 4 loại dNTP |
| [Primer] | 250 nM | 50–1000 nM | Nồng độ mỗi primer |
| Buffer pH | 8.4 | 7.0–9.5 | pH buffer Tris-HCl đo ở 20°C |

App tự tính **Mg²⁺ tự do** = Mg²⁺ tổng − [dNTP] (vì dNTP chelate Mg²⁺ theo tỉ lệ 1:1), kèm chỉ báo: ✓ tối ưu (≥1.5 mM), ⚠ dưới tối ưu (≥1.0 mM), ✕ thiếu (<1.0 mM).

Các cảnh báo khác: Na⁺/K⁺/Mg²⁺/dNTP/nồng độ primer/pH nằm ngoài khoảng khuyến nghị; lực ion kết hợp cao (salt>100 và Mg>3.0); và cảnh báo riêng khi Tm tối thiểu mục tiêu cao hơn Tm tính được của vùng 12 nt đặc hiệu miRNA quá 33°C (nghĩa là cần một đuôi 5′ dài để bù Tm).

Có nút **Reset** xác nhận 2 lần (bấm lần 1 hiện "Confirm reset?" trong 2.5 giây, bấm lần 2 mới thực sự khôi phục về giá trị mặc định).

### 4.4. Primer Constraints Group — Ràng buộc thiết kế primer

| Field | Mặc định | Khoảng | Ý nghĩa |
|---|---|---|---|
| %GC primer (min/max) | 40–60% | 20–80% | <35% bắt cặp yếu; >65% dễ tạo cấu trúc bậc 2 |
| Chiều dài primer (min/max) | 20–24 nt | 15–35 nt | Tổng chiều dài forward primer (vùng đặc hiệu + đuôi 5′), không tính phần thân stem-loop |
| 3′ GC Clamp | Bật | on/off | Kết thúc primer bằng G/C ở đầu 3′ để tăng ổn định, khuyến nghị bật |
| Vùng bắt cặp 3′ | 6 nt (cố định, không sửa được) | — | Số nt ở đầu 3′ overhang của RT primer bắt cặp với đầu 3′ miRNA — **cố định 6 nt**, là chuẩn đã được kiểm chứng để tránh cản trở không gian từ pri/pre-miRNA |

Cảnh báo: chuỗi miRNA có đoạn lặp đồng nhất; vùng 12 nt đầu (forward region) quá nghèo GC (<30%, cần đuôi dài) hoặc quá giàu GC (>70%, nguy cơ tự bắt cặp); vị trí 10–12 kết thúc bằng A/U trong khi đang bật GC Clamp (thuật toán sẽ điều chỉnh đuôi 5′ để bù).

### 4.5. qPCR Conditions Group — Điều kiện chạy qPCR

| Field | Mặc định | Khoảng | Ý nghĩa |
|---|---|---|---|
| Nhiệt độ bắt cặp (Ta) | 60°C | 50–68°C | Thường thấp hơn Tm 2–5°C |
| Tổng số cycle | 40 | 30–50 | Ct gần số cycle tổng → kết quả không tin cậy |
| Hiệu suất PCR (min/max) | 90%/110% | 80–100% / 100–120% | Lý tưởng 100% (slope −3.32) |
| Kích thước amplicon (min/max) | 60–150 bp | 40–300 bp | 60–150 bp là khoảng thường gặp cho stem-loop RT-qPCR do cDNA template kéo dài |

Cảnh báo: Ta cao hơn (Tm min + 5°C) → dễ bắt cặp sai; số cycle <35 (có thể không đủ phát hiện target ít) hoặc >45 (tăng nguy cơ khuếch đại không đặc hiệu); khoảng hiệu suất PCR quá rộng (>25%) → chấp nhận nhiều candidate chất lượng thấp hơn.

Lưu ý: section này nhận thêm giá trị `tmMin` từ Thermodynamic Group để tính cảnh báo Ta — đây là phụ thuộc chéo (cross-group) duy nhất giữa các section.

### 4.6. Experimental Context Group — Bối cảnh thực nghiệm

Không ảnh hưởng trực tiếp đến thuật toán thiết kế primer nhưng điều chỉnh khuyến nghị và có thể tự động áp preset lên các field khác.

- **Loại mẫu** (`sampleType`, mặc định Tissue): Tissue, Cell culture, Serum, Plasma, FFPE, Urine. Khi đổi loại mẫu, app hiện banner đề xuất áp preset (ví dụ Serum/Plasma → giảm amplicon max về 100bp, giảm nồng độ primer về 50nM kèm khuyến nghị dùng gene tham chiếu spike-in; FFPE → thu hẹp khoảng amplicon 60–80bp do RNA bị phân mảnh/cross-link; Urine → cảnh báo chất ức chế PCR, đề xuất pha loãng 1:5 + BSA).
- **Hệ thống qPCR** (`qpcrSystem`, mặc định Other): ABI, Bio-Rad CFX, Roche LightCycler, Qiagen Rotor-Gene, Other — ảnh hưởng việc chọn dye tham chiếu (ROX/không), thể tích phản ứng, master mix phù hợp.
- **Enzyme RT** (`rtEnzyme`, mặc định M-MLV): M-MLV, SuperScript III/IV, RevertAid, Other — ảnh hưởng nhiệt độ RT tối ưu (SuperScript IV bền nhiệt hơn, phù hợp mẫu khó/lượng RNA thấp).
- **Định dạng xuất kết quả** (`exportFormat`, checkbox nhiều lựa chọn, mặc định Copy to clipboard): Copy, PDF report, CSV (dùng để đặt hàng tổng hợp oligo).

---

## 5. Backend hỗ trợ trang Designer

### `GET /api/mirbase/<mirna_id>` (backend/routes/mirbase.py)

Chuỗi tra cứu 3 tầng + circuit breaker:

1. **SQLite local cache** (`backend/db/local_db.py`) — tra theo tên, accession, hoặc chuỗi (không phân biệt hoa thường), ưu tiên *Homo sapiens* nếu trùng nhiều loài. Nhanh nhất, trả ngay nếu có (`source: "local"`).
2. Nếu input là chuỗi thô (sequence) → không tra ngược qua API ngoài (vì miRBase không hỗ trợ), trả 404 luôn.
3. **Circuit breaker** kiểm tra trước khi gọi API ngoài — nếu đang mở (do 3 lần lỗi liên tiếp gần đây), trả 503 kèm thời gian chờ còn lại, tránh gọi dồn vào dịch vụ đang lỗi.
4. Gọi **miRBase.org REST API** (retry tối đa 3 lần với độ trễ 0/2/5 giây). Thành công → lưu lại vào cache local, `source: "mirbase"`.
5. Nếu vẫn thất bại → fallback **RNAcentral API**, `source: "rnacentral"`.
6. Nếu cả 2 nguồn ngoài đều thất bại → trả 504, yêu cầu người dùng tự nhập chuỗi.

Circuit breaker: mở sau 3 lỗi liên tiếp, tự đóng lại sau 300 giây (5 phút).

### `GET /api/health`
Trả `{"status":"ok","message":"Backend is running","version":"2.0.0"}` — dùng để kiểm tra backend đã chạy.

---

## 6. Trạng thái hiện tại & hướng phát triển tiếp (theo SPEC_week1.md)

App hiện tại (Week 1) **chỉ thu thập và validate dữ liệu đầu vào** — chưa có thuật toán thiết kế primer thật. Khi bấm Submit, dữ liệu chỉ được log ra console.

Kế hoạch Week 2: thêm endpoint `POST /api/design` nhận toàn bộ 6 nhóm dữ liệu form và trả về:
- `rt_primer` — stem-loop RT primer (~44 nt thân hairpin + đuôi 6 nt bổ sung ngược của 6 nt cuối miRNA)
- `fwd_primer` — forward primer (đuôi 5′ tăng Tm + 10–12 nt đặc hiệu từ đầu 5′ miRNA)
- `rev_primer` — reverse primer cố định: `5'-CCAGTGCAGGGTCCGAGGTA-3'`
- `amplicon_size`, `warnings`

Tm sẽ được tính bằng công thức nearest-neighbor SantaLucia có hiệu chỉnh theo nồng độ muối — đây là lý do các tham số ở Thermodynamic Group đã được thu thập sẵn từ Week 1.

---

## 7. Chi tiết logic cảnh báo theo từng điều chỉnh

Phần này liệt kê đầy đủ điều kiện kích hoạt, ngưỡng cụ thể và lý do sinh học/hóa học đằng sau mỗi cảnh báo, theo đúng thứ tự field xuất hiện trên trang.

### 7.1. Sequence Group

| Cảnh báo | Điều kiện kích hoạt | Vì sao cảnh báo |
|---|---|---|
| Chuỗi ngắn | `lengthCategory === 'short'` (15–17 nt) | Có thể là đoạn miRNA chưa hoàn chỉnh hoặc bị cắt (fragment) — không phải miRNA trưởng thành đầy đủ. |
| Chuỗi dài | `lengthCategory === 'long'` (26–30 nt) | Có thể là đoạn pre-miRNA còn sót lại hoặc một isomiR (biến thể chiều dài của miRNA gốc). |
| Nghèo GC toàn chuỗi | `gcContent < 30%` | Chuỗi giàu AU → Tm tổng thể thấp, ảnh hưởng cả overhang của RT primer và forward primer. App gợi ý tăng nhiệt độ RT và/hoặc tăng [Mg²⁺] để bù. |
| Giàu GC toàn chuỗi | `gcContent > 70%` | Dễ hình thành cấu trúc bậc 2 (hairpin nội tại), có thể cản trở RT enzyme bắt cặp đúng vị trí. |
| Vùng bắt cặp 3′ nghèo GC | `bindingRegionGC ≤ 33%` (≤2/6 nt là G hoặc C) | Đuôi overhang của RT primer (bổ sung ngược 6 nt cuối miRNA) có Tm quá thấp → dễ tách rời khỏi khuôn trong bước RT. Gợi ý: tăng nhiệt độ RT hoặc dùng RT enzyme bền nhiệt hơn (xem RT enzyme ở Experimental Context). |
| Vùng bắt cặp 3′ giàu GC | `bindingRegionGC ≥ 83%` (≥5/6 nt là G hoặc C) | Overhang có Tm cao bất thường → tăng nguy cơ bắt cặp không đặc hiệu với các miRNA khác có đầu 3′ tương tự. |
| Vùng bắt cặp 3′ có lặp | `bindingRegionHasRepeat` — ≥3 ký tự giống nhau liên tiếp trong 6 nt cuối | Vùng lặp đồng nhất (ví dụ `AAA`, `GGG`) làm giảm độ chính xác base-pairing, ảnh hưởng độ trung thực khi tổng hợp cDNA. |
| Không bắt đầu bằng U | `!startsWithU` | >90% miRNA trưởng thành ở người bắt đầu bằng U vì đây là tín hiệu để protein Ago2 nạp miRNA vào phức hợp RISC. Chuỗi không bắt đầu bằng U là bất thường, có thể ảnh hưởng hiệu suất phát hiện thực tế (xem thêm cảnh báo tương tự ở Detection Method Group). |
| Có đoạn lặp dài | `hasContinuousRepeat` — ≥4 ký tự giống nhau liên tiếp ở bất kỳ vị trí nào trong chuỗi | Đoạn homopolymer (≥4 nt) dễ gây trượt polymerase (polymerase slippage) khi tổng hợp; thuật toán thiết kế (Week 2) sẽ né vùng này nếu có thể khi chọn vị trí bắt cặp primer. |

### 7.2. Detection Method Group

| Cảnh báo | Điều kiện | Vì sao cảnh báo |
|---|---|---|
| Không bắt đầu bằng U (nhắc lại ở đây) | `seqAnalysis && !startsWithU` | Vì hiệu suất nạp vào RISC có thể thấp hơn, app gợi ý **tăng lượng RNA đầu vào** để bù cho hiệu suất phát hiện có thể thấp hơn dự kiến — đây là khuyến nghị thực nghiệm khác với cảnh báo thiết kế primer ở mục 7.1. |

Lưu ý: các lựa chọn TaqMan/SYBR và Absolute/Relative không sinh cảnh báo, chỉ hiện hộp thông tin (info box) mô tả yêu cầu kỹ thuật riêng (MGB cho TaqMan, melting curve bắt buộc cho SYBR, v.v. — xem mục 4.2).

### 7.3. Thermodynamic Group

| Field | Ngưỡng cảnh báo | Mức độ | Nội dung/Lý do |
|---|---|---|---|
| Mg²⁺ tự do (Mg tổng − dNTP) | `< 1.0 mM` | Amber | Cofactor không đủ cho hoạt tính polymerase — kết hợp ảnh hưởng từ cả [Mg²⁺] và [dNTP], hiện dưới dạng cảnh báo gộp (`freeMgWarning`). |
| [Na⁺] | `< 20 mM` | Amber | Tm tính toán sẽ giảm đáng kể do thiếu hiệu chỉnh muối — công thức Tm phụ thuộc log([Na⁺]). |
| [Na⁺] | `> 150 mM` | Amber | Tm tăng bất thường; nên kiểm tra lại nồng độ muối trong master mix đang dùng. |
| [K⁺] | `> 100 mM` | Amber (mạnh hơn) | Taq polymerase bị ức chế đáng kể ở mức này. |
| [K⁺] | `> 75 mM` | Amber (nhẹ) | Đã vượt giới hạn khuyến nghị trên, nên theo dõi. |
| [Mg²⁺] tổng | `< 1.0 mM` | Amber | Giảm hoạt tính cofactor của polymerase. |
| [Mg²⁺] tổng | `> 3.5 mM` | Amber | Tăng nguy cơ khuếch đại không đặc hiệu và hình thành primer dimer. |
| [dNTP] tổng | `< 0.1 mM` | Amber | Nguy cơ cạn cơ chất (substrate) giữa chu trình khuếch đại dài. |
| [dNTP] tổng | `> 0.4 mM` | Amber | Lưu ý: dNTP chelate hóa Mg²⁺ theo tỉ lệ 1:1 — nồng độ dNTP cao sẽ kéo Mg²⁺ tự do xuống thấp hơn dự kiến. |
| [Primer] | `< 100 nM` | Amber | Tm hiệu dụng giảm khoảng 3–5°C so với tính toán lý thuyết. |
| [Primer] | `> 600 nM` | Amber | Tăng nguy cơ primer dimer và nền tín hiệu SYBR cao hơn. |
| pH buffer | `< 7.5` | Amber | Hoạt tính polymerase giảm. |
| pH buffer | `> 9.0` | Amber | Nguy cơ primer bị thoái hóa và khuếch đại không đặc hiệu tăng. |
| Lực ion kết hợp | `[Na⁺] > 100 mM` **và** `[Mg²⁺] > 3.0 mM` đồng thời | Amber | Cảnh báo riêng khi 2 yếu tố lực ion cộng hưởng — ảnh hưởng tổng hợp lớn hơn từng yếu tố riêng lẻ. |
| Thiếu hụt Tm forward primer | `tmMin − fwdRegionTm(12 nt đầu miRNA) > 33°C` | Amber | Vùng 12 nt đặc hiệu miRNA ở đầu 5′ tự nó có Tm rất thấp (theo quy tắc Wallace), không thể đạt Tm mục tiêu nếu không có đuôi 5′ đủ dài. Gợi ý: hạ Tm min xuống 3–5°C hoặc chấp nhận đuôi dài hơn. |

Chỉ báo Mg²⁺ tự do hiển thị 3 mức màu: ✓ teal (≥1.5 mM, tối ưu) / ⚠ amber (≥1.0 mM, dưới tối ưu) / ✕ đỏ (<1.0 mM, thiếu).

### 7.4. Primer Constraints Group

| Cảnh báo | Điều kiện | Vì sao cảnh báo |
|---|---|---|
| Có đoạn lặp đồng nhất | `seqAnalysis.hasContinuousRepeat` | Giống mục 7.1 — nguy cơ trượt polymerase khi tổng hợp primer/cDNA tại vùng lặp. |
| Forward region nghèo GC | `fwdRegionGC < 30%` (12 nt đầu miRNA) | Cần đuôi 5′ dài hơn để kéo Tm primer lên mục tiêu — liên quan trực tiếp đến cảnh báo "thiếu hụt Tm" ở mục 7.3; gợi ý hạ Tm min nếu đuôi quá dài không khả thi. |
| Forward region giàu GC | `fwdRegionGC > 70%` | Nguy cơ tự bắt cặp (self-complementarity) hoặc tạo hairpin nội tại trong chính forward primer; gợi ý bật "Precursor cross-reactivity check" ở Detection Method Group để kiểm tra kỹ hơn. |
| Vị trí 10–12 không phải G/C khi đang bật GC Clamp | `!fwdEndGC && gcClamp3prime === true` | Khi user yêu cầu primer phải kết thúc bằng G/C (3′ GC Clamp) nhưng chính vị trí 10–12 nt của miRNA (đầu 3′ của vùng đặc hiệu) lại là A/U, thuật toán thiết kế sẽ phải tự điều chỉnh phần đuôi 5′ để bù — đây là cảnh báo mang tính thông báo trước, không phải lỗi chặn submit. |

### 7.5. qPCR Conditions Group

| Cảnh báo | Điều kiện | Vì sao cảnh báo |
|---|---|---|
| Ta quá cao so với Tm | `annealingTemp > tmMin + 5°C` (tmMin lấy từ Thermodynamic Group) | Nhiệt độ bắt cặp nên thấp hơn Tm khoảng 2–5°C; nếu cao hơn mức này dễ gây bắt cặp sai (mispriming) hoặc giảm hiệu suất khuếch đại. Đây là cảnh báo phụ thuộc chéo duy nhất giữa 2 section. |
| Số cycle thấp | `totalCycles < 35` | Có thể không đủ chu kỳ để phát hiện target có nồng độ thấp (Ct cao). |
| Số cycle cao | `totalCycles > 45` | Tăng nguy cơ khuếch đại không đặc hiệu và nhiễu nền ở các cycle cuối. |
| Khoảng hiệu suất PCR quá rộng | `(pcrEfficiencyMax − pcrEfficiencyMin) > 25%` | Khoảng chấp nhận hiệu suất quá rộng đồng nghĩa thuật toán sẽ chấp nhận nhiều candidate primer có chất lượng thấp hơn — nên thu hẹp lại nếu muốn kết quả primer chặt chẽ hơn. |

### 7.6. Experimental Context Group

Nhóm này không có cảnh báo dạng ngưỡng số học, mà dùng **banner đề xuất preset** (amber) kèm ghi chú khi đổi loại mẫu:

| Loại mẫu | Banner / Lưu ý |
|---|---|
| Serum | RNA đầu vào thường thấp → đề xuất amplicon ngắn hơn (max 100 bp), giảm nồng độ primer (50 nM), khuyến nghị dùng gene tham chiếu nội sinh ổn định (miR-16) hoặc spike-in ngoại sinh (cel-miR-39). |
| Plasma | Cùng preset số như Serum, kèm lưu ý riêng: loại chất chống đông máu ảnh hưởng phản ứng — heparin có thể ức chế polymerase, nên ưu tiên mẫu chống đông bằng EDTA. |
| FFPE | RNA bị phân mảnh và cross-link do cố định formalin → thu hẹp khoảng amplicon (60–80 bp), cần bước giải nến (deparaffinization) trước khi tách RNA. |
| Urine | Không có preset số, nhưng cảnh báo về các chất ức chế PCR có sẵn trong nước tiểu (muối, urea) — gợi ý pha loãng mẫu 1:5 và bổ sung BSA để giảm ức chế. |
| Tissue, Cell culture | Không có preset/cảnh báo đặc biệt — coi là điều kiện chuẩn. |

Các lựa chọn **qPCR system** và **RT enzyme** không sinh cảnh báo, chỉ hiển thị ghi chú kỹ thuật tham khảo (dye tham chiếu, nhiệt độ RT tối ưu — xem bảng ở mục 4.6).

---

## 8. Phân loại mức độ cảnh báo

Toàn app dùng 2 cấp độ hiển thị nhất quán (theo quy ước trong `SPEC_week1.md`, không dùng `text-amber-600` rời rạc mà dùng banner thống nhất):

- **Lỗi (đỏ / error)** — chặn submit, ví dụ: chuỗi chứa ký tự không hợp lệ, giá trị nhập ngoài khoảng cho phép, min ≥ max trong các cặp range. Hiển thị ngay dưới field và làm chấm đỏ trên header section khi thu gọn.
- **Cảnh báo (vàng / warning)** — không chặn submit, chỉ nhắc người dùng xem xét lại vì có thể ảnh hưởng chất lượng thiết kế hoặc kết quả thực nghiệm. Hiển thị chấm vàng trên header section khi thu gọn (chỉ hiện nếu không có lỗi nào, vì lỗi có độ ưu tiên cao hơn).
