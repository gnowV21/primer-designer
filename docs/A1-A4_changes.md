# A1–A4 — rà soát lại và tác động (2026-11-10, BLAST classifier v7)

Bản yêu cầu viết cho v3.2.0. Đến v3.5.0, cả bốn mục đã được sửa một lần (AUDIT_REPORT §10.2: REV-01…04, SPEC_phase3 §8.15–8.16). Đợt này đọc lại code để tìm phần còn sót. Kết quả: A1 và A2 đúng, còn A3 và A4 sót một phần ở BLAST. Hai phần sót đã được sửa ở classifier v7.

## 1. Ánh xạ và kết quả rà soát

| Mục | Đã sửa trước đó | Rà soát 2026-11-10 | Việc làm |
|---|---|---|---|
| **A1** Kwok ở base cuối gần như không chạy | REV-01 (BLAST v4): base 3′ bị BLAST cắt được lấy lại từ trình tự đầy đủ, rồi căn chỉnh lại | Đúng cho hit sợi plus. `dangling3` chỉ còn lại khi base nằm vượt quá đầu off-target. | Không đổi |
| **A2** Tm off-target đo sai vị trí | REV-02 (BLAST v4): Tm tính trên khung đọc của mồi cộng 1 base, khớp Tm_on 111/111 | Đúng. Hạn chế còn lại: trong cửa sổ đó, thal vẫn có thể chọn duplex trượt 1–2 nt. Cửa sổ chỉ dài L + 1 nên độ trượt nhỏ. | Ghi hạn chế (DECISIONS D-17) |
| **A3** Nhóm "trình tự tương thích" bị coi như trùng đích | REV-03 (v3.3.0): mô hình ΔCq xét lệch đầu; BLAST tách `same_sequence` / `shifted_5p` / `shifted_3p` | **Còn sót:** BLAST vẫn để mục lệch đầu ngoài `overall_risk`. Một mồi có paralog lệch đầu 5′ (khuếch đại chung, không tránh được) vẫn ra **SAFE**. | **Sửa (v7):** `shifted_5p` → HIGH; `shifted_3p` chấm theo bước RT; `same_sequence` (chính đích dưới tên khác) vẫn không tính |
| **A4** BLAST bỏ qua bước RT | REV-04 (v3.3.0): mô hình ΔCq cấp assay là kết luận chính | **Còn sót:** BLAST vẫn chỉ xét mồi forward. Hit mà overhang RT đã phân biệt vẫn bị báo **CRITICAL**, và trang Results hiện nó là "critical issue". | **Sửa (v7):** `/api/blast-check` nhận `rt_primer`; mỗi hit sợi plus được chấm lại qua bước RT của mô hình assay (`apply_rt_step`) |

### Quy tắc mới (classifier v7)

**Bước RT cho từng hit forward (A4).** Hàm dùng là `apply_rt_step`, với ΔCq_RT lấy từ `assay_model.rt_axis` và ngưỡng của mô hình assay:

| ΔCq_RT | Ý nghĩa | Mức mới |
|---|---|---|
| ≥ 4,3 | dưới 5 % được phiên mã ngược | SAFE (không có cDNA cho mồi forward) |
| 3,3–4,3 | 5–10 % | tối đa MEDIUM |
| < 3,3 | — | giữ nguyên mức của mồi forward |

**Hit có thêm thông tin:** mỗi hit mang thêm `primer_risk` (mức khi chỉ xét forward) và `rt_step`. Phần summary có thêm `rt_discriminated_count`.

**Độ dài overhang:** đọc từ RT primer (`len − 44`, phải nằm trong 5–7 nt), không mặc định 6. Không gửi `rt_primer` thì kết quả như cũ, kèm cờ `rt_step_applied = false`.

**Mục lệch đầu (A3):** `identical_sequence_risk` cho mức của từng mục. `overall_risk` lấy mức tệ nhất giữa các hit và các mục lệch đầu. Summary có thêm `unresolvable_variant_count`.

## 2. Tác động — BLAST, 175 mồi forward #1 của bộ validation

Script `backend/scripts/blast_tm_gate_sensitivity.py`, kết quả ở `benchmark/blast_tm_gate_sensitivity.json`. Biên an toàn (SAFE margin) 10 °C. Nhóm stem-loop có 100 mồi; nhóm Busk 2014 (poly(A)) có 75 mồi.

### Stem-loop: bước RT (A4)

| | Hit CRITICAL / HIGH / MEDIUM | Mồi có ≥ 1 CRITICAL | `overall_risk` của 100 mồi |
|---|---|---|---|
| v6 (chỉ forward) | 65 / 0 / 78 | 29 | SAFE 55, MEDIUM 16, CRITICAL 29 |
| **v7 + bước RT** | **16 / 0 / 31** | **10** | **SAFE 78, MEDIUM 10, HIGH 2, CRITICAL 10** |

- Có 96 hit bị bước RT loại (ΔCq_RT ≥ 4,3).
- 16 hit CRITICAL còn lại đều là paralog cùng overhang mà mô hình ΔCq cũng xếp CO-AMPLIFIED. Từ nay BLAST và mô hình assay **thống nhất** với nhau:

| Target | Off-target còn CRITICAL (ΔCq_RT) |
|---|---|
| hsa-let-7a-5p ↔ hsa-let-7d-5p | (0) — hai chiều |
| hsa-miR-20a-5p | miR-17, 20b, 106a (0) |
| hsa-miR-103a-2-5p | 103a-1 (0) |
| mmu-miR-19a-3p | 19b (0) |
| mmu-miR-669a-5p | 669o, 669l (3,0 — lệch đầu 3′ −2 nt) |
| mmu-miR-21a-5p | miR-3965 (3,0) |
| ath-miR156a-5p | 156g, 156j (0) |
| osa-miR164a / 164c | 164b/c/f (0) |

### Mục lệch đầu (A3), không có bước RT

| Nhóm | `overall_risk` v6 | v7 | Mồi đổi mức |
|---|---|---|---|
| stem-loop (100) | SAFE 55, MEDIUM 16, CRITICAL 29 | SAFE 55, MEDIUM 14, **HIGH 2**, CRITICAL 29 | mmu-miR-467a-5p ↔ 467b-5p (shifted_5p): MEDIUM → HIGH |
| Busk 2014 (75) | SAFE 45, MEDIUM 9, CRITICAL 21 | SAFE 44, MEDIUM 9, **HIGH 1**, CRITICAL 21 | ssc-miR-199b-3p (↔ 199a-3p): SAFE → HIGH; ssc-miR-20 vốn đã CRITICAL |

**Số hit theo từng mức không đổi** so với v6 ở mọi cấu hình (biên 5/10/15/20 °C và không có cổng Tm), vì phần sửa A3 không chạm vào các hit.

Phần thay đổi gồm:
- **`overall_risk`:** ở mọi biên có cổng Tm, đúng 3 mồi nói trên lên HIGH (2 stem-loop, 1 Busk).
- **Cấu hình mới `10_rt_step`:** cấu hình này chưa có ở v6.

Cấu hình không có cổng Tm gọi `_check_primer` trực tiếp, nên không xét mục lệch đầu; ở cấu hình này `overall_risk` giữ nguyên.

## 3. Tác động — validation 2439 và benchmark 165

- Phần sửa chỉ chạm BLAST (`/api/blast-check`), không chạm thiết kế mồi. Vì vậy mồi, điểm và nhãn ΔCq của 165 miRNA thiết kế được **giữ nguyên**.
- Hàm `assay_model.evaluate` có thêm tham số `full`, mặc định `False`, nên hành vi cũ không đổi.

| | Trước (v3.5.0, chạy lại 2026-11-10) | Sau (v7) |
|---|---|---|
| Validation in-silico | 2439/2439 | 2439/2439 — `results.csv` giống hệt từng byte |
| Mồi #1 / nhãn ΔCq của 165 miRNA | — | không đổi (không có code thiết kế nào bị sửa) |

## 4. Test

`backend/tests/test_blast_rt_step.py`, 14 test:
- đọc overhang 5/6/7 nt từ RT primer;
- ngưỡng của `apply_rt_step`;
- họ let-7 qua `check_offtarget`: let-7b và let-7c bị RT loại, let-7d vẫn CRITICAL, một mismatch ở vị trí 5 → MEDIUM;
- không có trình tự đích → không áp bước RT;
- `shifted_5p` → HIGH; `shifted_3p` chấm theo RT; `same_sequence` không tính;
- route kiểm tra và chuyển tiếp `rt_primer`.

Toàn bộ backend: **692 passed, 3 skipped**.

## 5. Phát hiện chưa sửa (cần duyệt)

Chi tiết ở `docs/DECISIONS_crossreactivity.md`:
- **D-16:** chưa coi rU·dG là cặp wobble ở bước RT;
- **D-17:** thal có thể trượt trong cửa sổ Tm;
- **D-18:** bước RT trong BLAST dùng cách hạ mức thay vì cộng ΔCq.
