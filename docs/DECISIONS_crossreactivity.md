# Quyết định khoa học — ma trận phản ứng chéo cấp assay (2026-11-10)

Mỗi mục gồm: lựa chọn, lý do và các phương án thay thế. Mục **⚠ cần duyệt** là lựa chọn ảnh hưởng tới số liệu, cần xem trước khi dùng cho thesis hoặc bài báo. Mọi trọng số và ngưỡng ở đây **chưa được hiệu chỉnh bằng thí nghiệm wet-lab**.

Đã chạy với: algorithm 3.5.0, BLAST classifier 7, miRBase 22.1 (`mature.fa` sha256 `3c521fc9…`), loài hsa.

---

## A. Mô hình

### D-1 · R dùng lại mô hình ΔCq của webtool — ⚠ cần duyệt
- **Chọn:** p_RT = 2^−ΔCq_RT, p_PCR = 2^−ΔCq_FWD, và R = p_RT × p_PCR = 2^−ΔCq_assay. Cả ΔCq_RT lẫn ΔCq_FWD lấy từ `backend/algorithm/specificity_check/assay_model.py`, không sửa gì.
- **Lý do:**
  - Webtool và ma trận chỉ dùng một mô hình, nên luận văn không có hai kết luận đặc hiệu mâu thuẫn nhau.
  - Mô hình này đã có các yếu tố mà spec yêu cầu: neo đầu 3′ với lệch −2…+2 nt, phạt khi lệch độ dài, trọng số mismatch theo vị trí, lớp Kwok/Stadhouders cho base cuối, và Tm theo khung neo.
  - R có nghĩa vật lý: đó là tỉ lệ tín hiệu chéo so với cặp khớp hoàn toàn.
- **Thay thế:** xây một mô hình xác suất riêng (quy tắc mismatch + ΔG, trọng số đặt trong config). Đã bỏ phương án này theo lựa chọn của bạn ngày 2026-11-10.

### D-2 · Bốn mức và mức sàn NONE — ⚠ cần duyệt

| Mức | ΔCq_assay | R |
|---|---|---|
| HIGH | < 3,3 | > 10 % (CO-AMPLIFIED) |
| MEDIUM | 3,3–4,3 | 5–10 % (PARTIAL) |
| LOW | 4,3–10 | 0,1–5 % |
| NONE | ≥ 10 | < 0,1 %, lưu R = 0 |

- **Lý do:**
  - HIGH và MEDIUM dùng đúng ngưỡng của webtool (lấy từ tiêu chí thành công trong đề cương).
  - 10 Cq ≈ 0,1 % là mức tín hiệu chéo thấp nhất Chen 2005 báo cho một mismatch.
  - File long chỉ lưu các cặp có R > 0.
- **Thay thế:** đặt sàn NONE ở 2^−8,3 hoặc ở mức phát hiện của máy; bỏ mức LOW.
- **Cấu hình:** `crossreactivity/config.json → levels`.

### D-3 · RT và FWD chọn khung đọc độc lập — ⚠ cần duyệt
- **Chọn:** mỗi trục lấy khung (lệch ±2 nt) cho ΔCq nhỏ nhất, không bắt buộc khung RT và khung FWD phải khớp với độ dài thật của miRNA j.
- **Lý do:**
  - Mô hình webtool đang làm như vậy.
  - Đây là cách bảo thủ: nó dự đoán tín hiệu chéo cao nhất mà dữ liệu cho phép.
- **Hệ quả:** một insertion hoặc deletion bên trong phân tử được cho phép ngầm.
  - Ví dụ miR-30b ↔ miR-30c: 30c dài hơn 1 nt ở đoạn giữa. Mô hình cho R = 1 theo cả hai chiều.
- **Thay thế:** ràng buộc k (lệch đầu 3′) và r (lệch đầu 5′) bằng hiệu độ dài, len(j) − len(i) = r + k. Cách này cho R thấp hơn với các cặp có indel bên trong.

### D-4 · Trần 8,3 Cq của trục FWD tạo đỉnh R ≈ 0,32 % — ⚠ cần duyệt
- **Quan sát:**
  - Có 20.108 / 20.710 cặp LOW (3.6.0, đếm các cặp có R = 2^−8,3; 3.5.0 theo cùng cách đếm: 20.106 / 20.708) mà mồi RT bắt được (overhang trùng, có thể lệch) nhưng mồi forward không bám.
  - ΔCq_FWD bị chặn ở 8,3, là mức "không khuếch đại" của Stadhouders 2010. Vì vậy R của nhóm này không bao giờ thấp hơn 2^−8,3 ≈ 0,32 %.
  - Histogram có chú thích cho đỉnh này.
- **Lý do giữ:** đây là hành vi của mô hình webtool, và 8,3 Cq là cận dưới có trong tài liệu.
- **Thay thế:** coi ≥ 2 mismatch trong 5 nt cuối, hoặc trường hợp không có khuôn, là NONE. Khi đó LOW còn khoảng 600 cặp.
- **Ảnh hưởng tới ML:** không có. Ngưỡng gộp mặc định là HIGH (D-10).

### D-5 · Không mô hình hóa probe TaqMan
- Các hằng số ΔCq được đo bằng TaqMan, nhưng mô hình không xét probe. Phân biệt ở vùng giữa trình tự vì vậy không được tính.
  - Ví dụ let-7a ↔ let-7d, miR-100 ↔ miR-99a: R = 0,31–1,0.
- Với SYBR, R là giới hạn lạc quan; với TaqMan, R là giới hạn bi quan.

### D-6 · ΔG chỉ báo cáo, xấp xỉ DNA:DNA (`approx_hybrid = True`)
- **dG_rt:** overhang của RT primer ghép với cửa sổ của miRNA j theo khung đã chọn (cộng 1 base). Tính bằng primer3 (DNA:DNA) trên bản DNA tương đương, ở đệm RT Kramer 2011 Table 2 (75 mM KCl, 3 mM Mg²⁺) và 37 °C.
- **dG_pcr:** vùng đặc hiệu forward trên cDNA của j, theo khung neo cộng 1 base (quy ước A2), ở điều kiện qPCR mặc định và Ta = 60 °C.
- **Lý do:** backend có tham số RNA:DNA Sugimoto 1995 nhưng chỉ cho cặp Watson–Crick, trong khi phần lớn các cặp ở đây có mismatch.
- **Hạn chế:** ΔG không đưa vào R, nên không ảnh hưởng tới mức rủi ro.

## B. Tính toán

### D-7 · Mồi #1 thiết kế qua `/api/design` với tham số mặc định của backend
- **Cách gửi:** thân request giống `validation/validate_primers.py`: các nhóm tham số rỗng, kèm `mirnaId`. Tham số mặc định gồm Ta 60 °C, overhang 6 nt, SYBR/TaqMan theo mặc định của API.
- **Hệ quả:** toàn bộ 2253 assay có overhang 6 nt. Độ dài vùng đặc hiệu forward phân bố như sau (algorithm 3.6.0):

| Độ dài (nt) | 12 | 13 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|
| Số assay | 404 | 455 | 474 | 484 | 380 | 56 |
| (3.5.0) | 392 | 450 | 490 | 480 | 385 | 56 |

- **Thay thế:** dùng mặc định của frontend (SYBR). Mồi sẽ không đổi, vì giới hạn amplicon ≤ 120 bp không bị chạm tới.

### D-8 · 403 / 2656 miRNA không thiết kế được — ⚠ cần duyệt
- **Lý do thất bại:** tất cả đều do "no valid forward primer candidates" với tham số mặc định. Trung vị GC của nhóm này là 70 %, so với 50 % ở nhóm thiết kế được; một số ít giàu AT.
- **Có cả miRNA quen thuộc:** 66 ca có số < 1000, ví dụ miR-1-5p, miR-23a-5p, miR-210-5p, miR-326, miR-375-5p, miR-663a.
- **Trong ma trận:** các miRNA này không có hàng (assay) nhưng vẫn có cột (vẫn là đích bị đo bởi assay khác).
- **Danh sách:** `outputs/crossreactivity_failed_designs.csv`.
- **Thay thế:** thiết kế lại nhóm này với tham số nới (GC/Tm rộng hơn) và đánh dấu "relaxed".

### D-9 · Bước sàng lọc là cận dưới chính xác, không phải lọc ungapped bằng numpy
- **Spec đề xuất:** sàng lọc bằng numpy (so khớp ungapped).
- **Lý do không dùng:** cận dưới theo số mismatch không chặn được gì ở ngưỡng 10 Cq.
  - RT ≥ 2 mismatch cho 8. FWD ≥ 2 mismatch cho ≥ 1,0, vì ngoại lệ T của Kwok.
  - Tổng tối thiểu vì vậy là 9 < 10, nên không cặp nào bị loại.
- **Thay thế đã dùng:** tính ΔCq **không có hạng Tm** cho mọi cặp (35 µs/cặp). Đây là cận dưới đã được chứng minh, vì ΔCq_FWD = max(bảng, Tm).
- **Kết quả:** 5.960.694 / 5.983.968 cặp bị loại chắc chắn mà không cần gọi primer3. Toàn bộ ma trận mất 62 giây với 14 tiến trình.
- **Test:**
  - `test_screen_is_a_lower_bound`: 906 cặp ngẫu nhiên.
  - `test_screen_keeps_every_known_family_pair_it_should`: họ let-7, miR-17, miR-200bc/429, miR-30.

### D-10 · Đa tiến trình, mỗi tiến trình một primer3
- Khóa trong `primer3_safe.py` chỉ tuần tự hóa các luồng trong cùng một tiến trình. Mỗi worker là một tiến trình riêng, nên không bị tuần tự hóa.
- Bộ nhớ đệm:
  - `outputs/crossreactivity_cache/designs_hsa.jsonl`: mỗi miRNA một dòng.
  - `matrix_hsa/block_*.jsonl`: mỗi block 32 assay; file chỉ được đổi tên khi ghi xong.
  - Cả hai gắn với phiên bản thuật toán (từ 2026-11-11). Bản thiết kế của phiên bản khác được thiết kế lại. Tên file block chứa mã băm của các assay trong block và phiên bản, nên block cũ không bao giờ bị dùng lại. Trước đó bộ đệm chỉ theo tên, nên dựng lại sau khi đổi thuật toán sẽ trả về ma trận cũ.
- Bị ngắt thì chạy lại sẽ tiếp tục từ chỗ dừng.

### D-11 · Đường chéo
- R(i, i) = 1 với mọi assay. Mọi giá trị R(i, j) đều ≤ R(i, i), và kiểm tra này đạt cho cả 2253 assay.
- Các mục miRBase khác tên nhưng cùng trình tự (74 cặp `same_sequence`, ví dụ miR-199a-3p / 199b-3p, miR-517a/b-3p) cũng có R = 1. Chúng là cùng một phân tử, nên vẫn thỏa điều kiện "R(i, i) là mức cao nhất".

## C. API và ML

### D-12 · Thư viện phân tích để riêng
- `crossreactivity/requirements.txt` gồm pandas, pyarrow, matplotlib, scipy, pytest.
- `backend/requirements.txt` không đổi. Bản triển khai web không phải cài thêm khoảng 150 MB.

### D-13 · Gộp thành "đơn vị đo được" — ⚠ cần duyệt
- **Chọn:**
  - Đối xứng hóa bằng S(i, j) = max(R(i, j), R(j, i)).
  - Gộp theo thành phần liên thông của đồ thị S ≥ ngưỡng.
  - Ngưỡng mặc định là 2^−3,3 ≈ 10 % (HIGH).
- **Hạn chế:** thành phần liên thông có thể nối chuỗi (A~B, B~C thì A và C chung nhóm). `group_report()` báo liên kết yếu nhất trong mỗi nhóm để phát hiện trường hợp này.
- **Thay thế:** phân cụm complete-linkage (mọi cặp trong nhóm đều ≥ ngưỡng); hoặc ngưỡng 5 % (MEDIUM).

### D-14 · `aggregate_expression` mặc định là tổng
- **Lý do:** tín hiệu qPCR của một assay là tổng những gì nó bắt được. Đơn vị của TCGA là RPM.
- **Yêu cầu:** tên miRNA phải là tên miRBase 22.1. TCGA dùng mã MIMAT, nên cần ánh xạ trước. Hàm không tự đổi tên.
- **Thay thế:** tổng có trọng số R (mô phỏng đúng tín hiệu assay của i); mean; max.

## D. Kiểm chứng

### D-15 · Nguồn dữ liệu kiểm chứng — dữ liệu chưa có
- **Chen 2005 (NAR 33:e179), Figure 7:** chỉ gồm let-7a–e (5 × 5); không có let-7f/g/i hay miR-98. Giá trị chỉ in trong ảnh, không có trong bảng hay trong chữ.
  - Đã tạo `validation/crossreactivity_chen2005.csv` với 25 dòng, cột `measured_value` để trống.
  - **Không độc lập:** ΔCq_RT (3,7 %, 0,1 %, ≤ 0,3 %) lấy từ chính bài này. So sánh chỉ kiểm tra cài đặt.
- **Mestdagh 2014 (Nat Methods 11:809, doi 10.1038/nmeth.3014):** không có bản PMC, và nature.com yêu cầu đăng nhập.
  - `validation/crossreactivity_mestdagh2014.csv` mới có header.
  - Khi điền, chỉ nên lấy số của nền tảng TaqMan stem-loop.
- **Script và ngưỡng:** `python -m crossreactivity.validate`. Ngưỡng "có phản ứng chéo" mặc định là 1 %; đổi bằng `--threshold-pct` theo ngưỡng của bài báo.

## E. Phát hiện trong lúc rà soát A1–A4 (chưa sửa, cần duyệt)

### D-16 · Chưa coi rU·dG là cặp wobble ở bước RT — ⚠ cần duyệt
- **Hiện tại:** chỉ rG·dT được tính là wobble, ΔCq 4,75 (Chen 2005 đo được cho let-7a assay trên let-7c). rU·dG (đích C, off-target U) bị tính như mismatch thường: 7,0 nếu ở vị trí 1–3, 3,5 nếu ở vị trí 4–6.
- **Mâu thuẫn:** nguyên tắc "cận dưới" của mô hình cho rằng nên coi rU·dG là wobble, ví dụ min(vị trí, 4,75). Nhưng chưa có số đo nào cho rU·dG.
- **Ảnh hưởng nếu đổi:** tăng R với các cặp có C↔U ở vị trí 1–3 của overhang. Số liệu validation và webtool sẽ thay đổi, nên chưa đổi.

### D-17 · Tm theo khung đọc vẫn cho thal trượt trong cửa sổ (phần còn lại của A2)
- Cửa sổ dài L + 1 nt, nên duplex tối ưu có thể trượt 1–2 nt.
- Chưa kiểm tra base cuối 3′ có bắt cặp trong cấu trúc thal trả về hay không.
- Mức độ: nhỏ (cửa sổ ngắn). Hướng làm tiếp: dùng `output_structure` của primer3.

### D-18 · Bước RT trong BLAST dùng cách hạ mức, không cộng ΔCq (A4)
- **Chọn:** ΔCq_RT ≥ 4,3 → SAFE; 3,3–4,3 → tối đa MEDIUM; còn lại giữ nguyên mức của forward.
- **Lý do:** mức của BLAST là định tính (theo luật Kwok và cổng Tm), không có ΔCq_FWD để cộng vào. Con số ΔCq đầy đủ nằm ở mô hình assay và trong ma trận.
- **Thay thế:** quy đổi mức BLAST sang ΔCq rồi cộng.

### D-19 · Mục lệch đầu trong BLAST (A3)
- **Chọn:**
  - `shifted_5p` → HIGH (không chọn CRITICAL, vì không thiết kế mồi nào tránh được).
  - `shifted_3p` chấm theo bước RT; khi không có RT primer thì là HIGH.
  - `same_sequence` không tính (đó là chính đích dưới tên khác).
- **Thay thế:** `shifted_5p` → CRITICAL. Cách này đúng nghĩa "khuếch đại chung" hơn, nhưng sẽ hiện thành "critical issue" ở những trường hợp người dùng không thể sửa được.

### D-20 · Nối `rt_primer` từ trang Results
- `QualitySummary.jsx` gửi thêm `results.stemloop_rt.sequence`. Đây là thay đổi ở dây nối API, không phải giao diện (UI nằm ngoài phạm vi), nhưng cần có thì sửa A4 mới có tác dụng.
- Client cũ không gửi trường này vẫn nhận kết quả như v6, kèm cờ `rt_step_applied = false`.
