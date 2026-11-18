# SPEC UI — hiển thị hệ chấm điểm phân tầng (algorithm 4.0.0)

Ngày: 2026-11-18 · Chủ dự án: Vương · Nhánh: `feat/tiered-scoring` (PR #13, chưa merge)
Điều kiện để merge PR #13 (QĐ 31). Đọc kèm: `docs/SPEC_scoring_tiered_4.0.0.md` §3, §4, QĐ 16, 27, 29–36; `backend/static/openapi.yaml` (`PrimerSetRanking`, `RankingSummary`, `OverhangSuggestion`).

## 0. Cách làm
- Làm tuần tự theo giai đoạn. Gặp ⛔ DỪNG: gửi báo cáo, chờ duyệt.
- Báo cáo bằng tiếng Việt. Nhãn UI, code, commit bằng tiếng Anh (CLAUDE.md).
- Giữ stack cố định của frontend (CLAUDE.md): React 18, Vite 5, Tailwind 3, không thêm thư viện UI.
- Không đổi thuật toán, ngưỡng hay khóa xếp hạng. Chỉ được thêm field vào API nếu frontend thực sự cần; khi thêm phải cập nhật `openapi.yaml` và test. V4 phải giữ nguyên output.
- Mọi kết luận kèm bằng chứng: lệnh + output; ảnh chụp màn hình cho phần giao diện.

## 1. Quyết định đã chốt
U1. Thẻ bộ mồi hiển thị **grade A/B/C + 3 tầng** (Specificity x/15 · PCR x/5 · Flexible x/20). **Bỏ đồng hồ 0–100** ở hệ tiered. Điểm chi tiết chỉ xuất hiện trong phần mở rộng, với nhãn "Tie-break score — used only when all tiers are equal".
U2. **Không** có lựa chọn V4 trên giao diện. V4 chỉ dùng qua API/script.
U3. Câu "Why #1 over #2" giải thích **theo tầng quyết định** (đúng thứ tự khóa xếp hạng), không theo hiệu `total_score`.
U4. Hai bộ có cùng (S_total, structure_veto, binding_floor_fail, has_v4_violation, P_total, F_total) được gắn nhãn **"Equivalent in silico"** (QĐ 16, mở rộng theo QĐ 34/36).
U5. Phản hồi không có `ranking` (V4 qua API, hoặc bản ghi History cũ) vẫn hiển thị như cũ: đồng hồ + ScoreBreakdown. Không lỗi, không trang trắng.

## 2. Thành phần
### 2.1 `TierSummary` (component mới, `pages/SearchPage/ResultsSection/TierSummary.jsx`)
- **Grade badge:** A xanh, B vàng hổ phách, C đỏ. Hover / tooltip hiển thị `grade_reasons`. Khi không có BLAST, ghi "B — BLAST unavailable".
- **Ba thanh tầng:** nhãn, x/max, và các chip mức thành phần:
  - Specificity: S1 BLAST (mức + `overall_risk`), S2 ΔCq (mức + `min_delta_cq` + `worst_target`), S3 Tm margin (mức + margin °C + `worst_target`). Khi `blast_available = false`: S1 ghi "not run", max 10.
  - PCR: P2 (|Tm − Ta|). P1 hiển thị là "report only".
  - Flexible: F1 GC, F2 GC clamp, F4 binding Tm (ghi rõ floor 45 °C), F5 structure (min của 3 chỉ số con).
- **Chip cảnh báo:** `structure_veto` ("Structure veto: hairpin/dimer at level 1"), `binding_floor_fail` ("Binding Tm < 39 °C"), mỗi mã `v4_rule_violations` một chip ("Outside V4 rule: gc_clamp_fail", kèm tooltip giải thích luật), `ranking.eliminated` ("Fails specificity screen").
- Tooltip của từng chip lấy từ `explanations` / bảng nhãn có sẵn. Không viết lại khoa học trong frontend.

### 2.2 `PrimerSetCard`
- Header (thu gọn): thay `ScoreGauge compact` bằng grade badge + "S x/15". Thêm nhãn "Equivalent in silico" (U4) khi thỏa điều kiện.
- Mở rộng: `TierSummary` ở đầu. Bảng chi tiết (gập mặc định) gồm từng tiêu chí: giá trị, mức 1–5, giải thích; cuối bảng là điểm chi tiết với nhãn U1. `ScoreBreakdown` chỉ dùng cho U5.

### 2.3 Banner cấp thiết kế (`ResultsSection` hoặc `EdgeCaseBanner`)
- `specificity_fallback`: banner đỏ. Ghi rõ không ứng viên nào qua sàng lọc đặc hiệu, liệt kê off-target gây loại (lấy từ các bộ trả về: `worst_target` của S2, `worst_hit` của S1, bỏ trùng), kèm câu "Include a cross-reactivity control (synthetic off-target) in the wet-lab run."
- `fewer_than_3_sets`: banner thông tin, ghi số bộ trả về.
- `blast_unavailable`: banner vàng, nguyên văn "Specificity ranking reduced to S2 + S3 (BLAST not run)".
- `overhang_suggestion`: thẻ thông tin. Ghi rõ off-label, chưa kiểm chứng wet-lab; chỉ là gợi ý, không đổi bộ mồi.

### 2.4 `rankReason` (viết lại `utils/rankReason.js`)
So bộ #1 và #2 đang hiển thị theo đúng thứ tự khóa. Lấy bước đầu tiên khác nhau:
1. S_total → "#1 is more specific (S 15 vs 13): <thành phần khác nhau, vd. BLAST SAFE vs MEDIUM>."
2. structure_veto → "Same specificity; #2 has a structure veto (<chỉ số con>)."
3. binding_floor_fail → "Same specificity; #2's binding region Tm is below the 39 °C floor."
4. has_v4_violation → "Same specificity; #2 is outside a V4 rule (<mã>)."
5. P_total → "Same specificity; #1 is closer to Ta (|ΔTm| x vs y °C)."
6. F_total → "Same specificity and PCR; #1 scores higher on flexible criteria (F x vs y): <tiêu chí>."
7. detailed_score → "Equivalent in silico on every tier; ordered by tie-break score (+x)."
8. hòa hoàn toàn → "Identical on every criterion (5′-tail variants); the order is arbitrary but fixed."
Không có `ranking` (U5) → giữ hàm cũ. Phần logic đặt trong một hàm thuần, export riêng để test được.

### 2.5 So sánh và các nơi khác
- `ThermoTable`: thay dòng "Total score" bằng các dòng Grade, S/P/F, cờ veto, vi phạm V4, Tie-break score.
- `RerunBar`: nhãn lần chạy là grade + "S x/15" của bộ #1. Dấu ★ "best" chọn bằng chính khóa xếp hạng tầng (hàm so sánh dùng chung với 2.4), không theo điểm.
- History (`HistoryPage`, `utils/historyDb.js`): lưu và hiển thị grade + S của bộ #1, kèm `scoring_system`. Bản ghi cũ hiển thị như cũ (U5).
- Export CSV (`ExportButtons`): thêm cột `scoring_system, grade, grade_reasons, S1, S2, S3, S_total, P_total, F_total, structure_veto, binding_floor_fail, v4_rule_violations, tie_break_score`. Đổi tên cột cũ `total_score` thành `tie_break_score` (ở V4 thì giữ `total_score`). FASTA header: `Grade=A S=15/15`.
- PDF export (backend `routes/export.py`): kiểm tra đã in grade + 3 tầng + cờ; nếu chưa thì sửa theo cùng nội dung.
- `OffTargetPanel`: hiển thị ngay kết quả BLAST lúc thiết kế (S1, `overall_risk`, `worst_hit`). Nút xem đủ danh sách hit vẫn gọi `/api/blast-check` với `rt_primer` và cùng điều kiện, rồi kiểm tra `overall_risk` trùng với kết quả lúc thiết kế. Nếu khác: hiển thị cảnh báo và ghi vào console, không che đi.

## 3. Kiểm thử
- e2e (Playwright):
  - Nâng timeout cho bước chờ thiết kế lên 30 s.
  - Thêm global setup làm nóng cache: gọi `/api/design` với **tham số mặc định của frontend** cho các miRNA mà e2e dùng.
  - Test mới:
    - (a) thẻ hiển thị grade + 3 tầng, không có đồng hồ;
    - (b) hsa-let-7a-5p hiển thị banner fallback, có tên let-7d-5p;
    - (c) rankReason: một ca phân định ở S, một ca "Equivalent in silico" — dùng ca thật nếu có, không thì mock bằng `page.route`;
    - (d) mock `blast_unavailable`;
    - (e) mock phản hồi V4 không có `ranking` (U5);
    - (f) bản ghi History cũ;
    - (g) CSV export có đủ cột mới.
  - `responsive.spec.js`: không tràn ngang ở 320/360/390 px với thẻ mới và banner.
- Hàm thuần của rankReason và hàm so sánh khóa: test trên đủ 8 nhánh (2.4). Dùng test runner sẵn có; nếu frontend chưa có thì viết dưới dạng test Playwright chạy hàm trong trang, không thêm dependency.
- Đối chiếu dữ liệu thật: với 2472 thiết kế hsa (từ `benchmark/` hoặc cache), áp hàm so sánh khóa phía frontend lên top 3 do API trả về. Thứ tự phải trùng 2472/2472 (bảo đảm frontend và backend hiểu khóa giống nhau). Nếu cần, viết script Node đọc JSON đã lưu.
- Build: `npm run build` không có cảnh báo mới. Backend test pass. Hồi quy V4 vẫn trùng 3.8.2.

## 4. Giai đoạn
- **UI-1:** cài 2.1–2.5 + test.
  ⛔ DỪNG: gửi ảnh chụp màn hình (desktop 1280 và mobile 390) của:
  - một thiết kế grade A (vd. hsa-miR-21-5p);
  - một thiết kế fallback (hsa-let-7a-5p);
  - một thiết kế có `binding_floor_fail` hoặc `structure_veto`;
  - bảng so sánh ThermoTable;
  - History;
  - phản hồi V4 mock.
  Kèm kết quả test, đối chiếu 2472/2472, danh sách file đã đổi.
- **UI-2 (sau khi duyệt):** sửa theo góp ý; cập nhật `CLAUDE.md` (frontend), `HANDOFF`, mô tả PR #13. ⛔ DỪNG chờ duyệt merge.

## 5. Ngoài phạm vi
Đổi thuật toán hoặc ngưỡng; song ngữ; trang diễn giải Ct sau khi chạy; nút chọn V4 trên UI.
