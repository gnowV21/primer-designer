# PROMPTS_accuracy_fixes.md — Claude Code prompts (evidence-based accuracy fixes)
# HG Lab Stem-loop RT-qPCR Primer Designer · 2026-07-02
# Nguồn: RESEARCH_INSIGHTS.md (Busk 2014 DOI 10.1186/1471-2105-15-29; Kang 2017 DOI 10.1261/rna.061150.117)

> Ba fix có bằng chứng, đã audit trên code hiện tại (`scoring.py`, `constants.py`, `routes/design.py`).
> Nguyên tắc chung cho cả 3: **KHÔNG đổi `SCORING_WEIGHTS_V4`** (việc của calibration Phase 5 PART B);
> chỉ đổi *hàm sub-score* và thêm *tầng hard-filter*. Mọi thay đổi bật/tắt qua constant để **A/B so sánh**
> được bằng `validation/validate_primers.py` + `calibration/calibrate_weights.py` (báo cáo tương quan).
> Chạy lại `backend/tests/` + `validation/` sau khi sửa, đảm bảo deterministic checks vẫn 100%.

---

## PROMPT 1 — Sửa `gc_clamp` theo luật miRNA-specific — cite kép [Busk14]+[IDT], phân tầng mức tin

> **Lưu ý thiết kế (đọc trước khi implement):** I3 có HAI nguồn phục vụ hai mục tiêu khác nhau:
> [IDT] → hiệu suất khuếch đại & anchor polymerase (PCR thường); [Busk14] → đặc hiệu phân biệt
> mismatch 1 nt (miRNA-specific). Không áp dụng một chiều bên nào. Phân tầng theo hội tụ nguồn:
> phần đa-nguồn (phạt CCC/run G-C) chốt cứng; phần đơn-nguồn (1 G/C = optimal) để sau cờ
> mặc định False, chờ calibration. Xem RESEARCH_INSIGHTS.md mục D để hiểu lý do.

```
Bối cảnh: đọc RESEARCH_INSIGHTS.md (mục I3 và mục D), backend/algorithm/scoring.py dòng 203-215
(tiêu chí gc_clamp), backend/algorithm/constants.py.

Vấn đề (đã audit): gc_clamp hiện đếm G/C trong 3 nt cuối forward primer và chấm
2→100, 3→80, 1→60, 0→0. Đây là hành vi nghiêng [IDT] (thưởng G/C ở 3' cho anchor polymerase).
Nhưng [Busk14] (miRNA-specific, DOI 10.1186/1471-2105-15-29) đề xuất khác: 3'-end nên có 1-2 A/T
(= 1-2 G/C) để tăng đặc hiệu; 0 hoặc 3 G/C = kém; đặc biệt tránh 3 C liên tiếp (trượt polymerase).
=> Không phải [IDT] sai hay [Busk14] đúng — hai luật tối ưu hai mục tiêu khác nhau.
   Tool ưu tiên đặc hiệu (miRNA) → nghiêng Busk, nhưng phân tầng theo mức tin.

═══════════════════════════════════════════════════════════════════════
PHẦN (a) — ĐÃ CHỐT (đa-nguồn: [Busk14]+[Kang17]+anti-homopolymer)
═══════════════════════════════════════════════════════════════════════
Hành vi chốt — implement cứng, không cần feature-flag:
   - 3 C liên tiếp ở 3' (last3 == "CCC"): score = GC_CLAMP_SCORE_TRIPLE_C = 25  [Busk14]
   - 3 G/C (gc_last3 == 3): score = GC_CLAMP_SCORE_WEAK = 50   [Busk14] (quá chặt → khó tháo)
   - 0 G/C (gc_last3 == 0): score = GC_CLAMP_SCORE_WEAK = 50   [IDT+Busk14] (thiếu anchor)
   Tất cả case này có bằng chứng từ ít nhất 2 nguồn hoặc có cơ sở lý thuyết rõ.

═══════════════════════════════════════════════════════════════════════
PHẦN (b) — TẠM THỜI (đơn-nguồn: [Busk14], heuristic, sampling bias đã biết)
═══════════════════════════════════════════════════════════════════════
Hành vi tạm thời — bật/tắt qua constant GC_CLAMP_1GC_AS_OPTIMAL (mặc định False):
   Câu hỏi: "1 G/C ở 3' có tốt như 2 G/C không?" — Busk14 nói CÓ (cả hai → score 1.0).
   Nhưng Busk14 là đơn lab, heuristic, có sampling bias tự thừa nhận (xem RESEARCH_INSIGHTS.md D.2).
   IDT phân biệt: 2 G/C > 1 G/C (anchor mạnh hơn).
   => Không thể chốt một chiều.

   GC_CLAMP_1GC_AS_OPTIMAL = False   # [Busk14 đơn-nguồn, heuristic] — chờ calibration
   # True  → 1 G/C = 100 (Busk-style: đặt hiệu tối ưu)
   # False → 1 G/C = 75  (thận trọng: tốt nhưng không ngang 2 G/C — giữa IDT và Busk)

   Khi False (default): gc_last3==1 → score = GC_CLAMP_SCORE_1GC_CONSERVATIVE = 75
   Khi True:            gc_last3==1 → score = GC_CLAMP_SCORE_OPTIMAL = 100

   Chỉ chuyển sang True sau khi calibrate_weights.py xác nhận tương quan cải thiện.

═══════════════════════════════════════════════════════════════════════
NHIỆM VỤ THỰC HIỆN
═══════════════════════════════════════════════════════════════════════
1) Thêm vào constants.py (SECTION scoring) các hằng số với [NGUỒN]:
   GC_CLAMP_SCORE_OPTIMAL          = 100  # 2 G/C ở 3 nt cuối — anchor tốt [Busk14+IDT]
   GC_CLAMP_SCORE_1GC_CONSERVATIVE = 75   # 1 G/C — đặc hiệu tốt nhưng anchor yếu hơn
   GC_CLAMP_SCORE_WEAK             = 50   # 0 G/C (thiếu anchor) hoặc 3 G/C (quá chặt) [Busk14+IDT]
   GC_CLAMP_SCORE_TRIPLE_C         = 25   # 3 C liên tiếp ở 3' — phạt nặng [Busk14, đa nguồn]
   GC_CLAMP_1GC_AS_OPTIMAL         = False  # [Busk14 đơn-nguồn, heuristic] — bật sau calibration

2) Viết lại khối gc_clamp trong scoring.py:
   gc_last3 = sum(1 for b in last3 if b in "GC")
   if last3 == "CCC":
       gc_clamp_score = GC_CLAMP_SCORE_TRIPLE_C      # phần (a) chốt
   elif gc_last3 == 3:
       gc_clamp_score = GC_CLAMP_SCORE_WEAK          # phần (a) chốt
   elif gc_last3 == 0:
       gc_clamp_score = GC_CLAMP_SCORE_WEAK          # phần (a) chốt
   elif gc_last3 == 2:
       gc_clamp_score = GC_CLAMP_SCORE_OPTIMAL       # phần (a) chốt
   else:  # gc_last3 == 1
       gc_clamp_score = (GC_CLAMP_SCORE_OPTIMAL       # phần (b) tạm thời
                         if GC_CLAMP_1GC_AS_OPTIMAL
                         else GC_CLAMP_SCORE_1GC_CONSERVATIVE)

3) Cập nhật explanation cite KÉP [Busk14]+[IDT], nêu rõ trade-off:
   "3'-end composition: {gc_last3} G/C in last 3 nt → score {gc_clamp_score}.
    Rule: 2 G/C = optimal anchor+specificity [Busk14+IDT]; 1 G/C = good specificity, weaker anchor
    [trade-off: IDT prefers G/C for PCR efficiency; Busk14 (miRNA-specific) accepts 1 G/C as optimal —
    single-source heuristic, pending calibration; default conservative]; 0 or 3 G/C = suboptimal [both];
    CCC at 3' = severe penalty [Busk14, multi-source]."

4) KHÔNG đổi weight của gc_clamp trong SCORING_WEIGHTS_V4.

5) Test backend/tests/test_gc_clamp.py — cases:
   - last3 = "ACG" (2 G/C) → 100 (chốt)
   - last3 = "GCG" (3 G/C) → 50  (chốt)
   - last3 = "CCC"          → 25  (chốt)
   - last3 = "ATA" (0 G/C)  → 50  (chốt)
   - last3 = "AAG" (1 G/C), GC_CLAMP_1GC_AS_OPTIMAL=False → 75 (conservative)
   - last3 = "AAG" (1 G/C), GC_CLAMP_1GC_AS_OPTIMAL=True  → 100 (Busk-style, cần monkeypatch)
   Chạy pytest -q xác nhận xanh.

6) Chạy validation/validate_primers.py (nếu backend chạy) — deterministic checks phải 100%.

Ràng buộc: không thêm dependency; comment tiếng Việt được, output/explanation English; giữ V4 weights.
```

---

## PROMPT 2 — Chốt ngưỡng dimer toàn cấu trúc −9 kcal/mol (Kang17 I1)

```
Bối cảnh: đọc RESEARCH_INSIGHTS.md (I1), scoring.py dòng ~136-152 (dimer_penalty, dùng dg_3prime),
constants.py SECTION F + SECTION P (đã có HETERODIMER_HIGH_RISK_DG = -9.0 [IDT]),
backend/algorithm/structure_check/ (self_dimer/hetero_dimer, các key dg / dg_3prime / has_critical_flag).

Bằng chứng: miPrimer/Kang 2017 (DOI 10.1261/rna.061150.117): ΔG self-/hetero-dimer TOÀN CẤU TRÚC
> -9.0 ± 1 kcal/mol = OK; < -9 = hỏng qPCR (tính bằng RNAcofold DNA params — ta có ViennaRNA).
Lưu ý: đây là ΔG TOÀN cấu trúc, KHÁC ngưỡng 3'-end (-5) hiện có — giữ cả hai, bổ sung không thay thế.

Nhiệm vụ:
1) constants.py: thêm DIMER_FULL_DG_CRITICAL = -9.0  # kcal/mol, full-structure [Kang17]
   (giữ nguyên các ngưỡng 3'-end; ghi rõ khác biệt trong comment).
2) Đảm bảo có sẵn ΔG toàn cấu trúc của self-dimer & hetero-dimer (key 'dg' full, không phải dg_3prime).
   Nếu structure_checks chưa expose full dg, bổ sung (không đổi công thức, chỉ đọc từ primer3/ViennaRNA đã tính).
3) Trong scoring dimer_penalty (hoặc has_critical_flag): nếu min(full self-dimer dg, full hetero dg)
   < DIMER_FULL_DG_CRITICAL → đánh dấu critical (dimer_score = 0) NGOÀI điều kiện 3'-end hiện có.
4) Test test_dimer_full_dg.py: dựng self/hetero dg = -10 → critical(score 0); = -8 → không critical do
   ngưỡng full (nhưng vẫn theo ngưỡng 3'-end nếu áp dụng). Chạy pytest -q.

Ràng buộc: không đổi công thức thermodynamics; không đổi V4 weights; English output.
```

---

## PROMPT 3 — Tầng hard-filter trước weighted-sum (Busk I5/I8 + Kang I1)

```
Bối cảnh: đọc RESEARCH_INSIGHTS.md (I5, I8, I1), routes/design.py (luồng: generate candidates →
prefilter/rejection_log → structure_checks → heterodimer_checks → score → rank top_n),
scoring.py, constants.py.

Bằng chứng: Busk 2014 chấm điểm dạng NHÂN (pair = F×R×anneal×dimer) — một yếu tố chí mạng kéo tụt cả
cặp (soft-AND). Weighted-SUM hiện tại có thể bù trừ lỗi chí mạng. Bổ sung tầng hard-filter loại thẳng
ứng viên vi phạm ngưỡng cứng TRƯỚC khi xếp hạng bằng weighted-sum (giữ nguyên weighted-sum để xếp hạng
các ứng viên đã 'an toàn').

Nhiệm vụ:
1) Tạo backend/algorithm/hard_filters.py:
   def apply_hard_filters(candidate, structure_checks, heterodimer_checks, params) -> list[str]
   Trả list lý do reject (rỗng = pass). Các luật cứng có [NGUỒN]:
   - full self/hetero-dimer ΔG < DIMER_FULL_DG_CRITICAL (-9) [Kang17]
   - 3'-end dimer critical / polymerase-extendable (has_critical_flag) [Premier Biosoft]
   - forward × reverse 3'-overlap ≥ HETERODIMER_3PRIME_MIN_BP (đã có =3) hoặc ≥2 nt theo Busk [Busk14 I8]
     (chọn ngưỡng, ghi rõ nguồn; mặc định theo hằng số hiện có)
   - hairpin severity == 'critical'
2) Tích hợp vào routes/design.py: sau structure/heterodimer checks, TRƯỚC scoring, chạy hard filter;
   ứng viên bị loại → đưa vào rejection_log với reason (đã có cơ chế rejection_summary); chỉ ứng viên
   pass mới vào score + rank. Thêm constant HARD_FILTER_ENABLED = True để A/B tắt/bật.
3) Fallback: nếu hard-filter loại HẾT ứng viên → nới (trả cảnh báo như nhánh 422 hiện có) thay vì trả rỗng.
4) Test test_hard_filters.py: mỗi luật có 1 case pass + 1 case reject; case tắt cờ → không loại ai.
5) Chạy lại toàn bộ backend/tests + validation/validate_primers.py:
   - deterministic checks (RT overhang, reverse, forward prefix) VẪN 100%
   - so số ứng viên rejected trước/sau (log) để thấy tác động.

Ràng buộc: hard-filter CHỈ loại theo ngưỡng cứng có nguồn; KHÔNG đụng weighted-sum/V4 weights;
giữ tốc độ /api/design (<5s); English output; constant bật/tắt để so sánh qua calibration report.
```

---

# PHẦN 2 — Các insight còn lại

## PROMPT 4 — Đối chiếu Tm target 59 °C & salt (Busk I2) — VERIFY, không sửa mù

```
Bối cảnh: đọc RESEARCH_INSIGHTS.md (I2), SPEC_phase5 PART C, constants.py dòng 95-96
(TM_FORWARD_TARGET=60.0, TOLERANCE=2.0), dòng 209-212 (P3_DEFAULT_MV_CONC=50 mM Na+,
DV_CONC=1.5 mM Mg2+, DNTP=0.8), backend/algorithm/thermodynamics.py.

Bằng chứng: Busk 2014 (DOI 10.1186/1471-2105-15-29) đặt Tm đích = 59 °C, tính NN với NaCl 115 mM;
Kang 2017 (DOI 10.1261/rna.061150.117) Tm 59-60 °C. Tool đang dùng 60 °C và Na+ 50 mM (primer3 default)
nhưng CÓ hiệu chỉnh Mg2+/dNTP (mô hình đầy đủ hơn công thức NaCl-cố-định của Busk).
=> ĐÂY LÀ VIỆC KIỂM ĐỊNH, không đổi hằng số một cách mù quáng.

Nhiệm vụ:
1) Viết calibration/check_tm.py (SPEC_phase5 PART C): so Tm dự đoán của tool với Tm thực nghiệm
   từ calibration/tm_benchmark.json (oligo + Tm đo, có DOI, verified). In MAE, bias.
2) Log rõ tham số salt đang áp (mv/dv/dntp/dna_conc) trong tính Tm — xác nhận Mg2+/dNTP correction
   thực sự được dùng (không bị bỏ qua).
3) BÁO CÁO calibration/tm_report.md: nếu có bias hệ thống (|bias| > 1.5 °C) → đề xuất chỉnh
   salt-correction HOẶC dịch TM_FORWARD_TARGET 60→59, KÈM bằng chứng. KHÔNG tự đổi nếu chưa có dữ liệu.
4) Nếu quyết định đổi: chỉ đổi constant (TM_FORWARD_TARGET / MV_CONC), chạy lại validation/ +
   calibrate_weights.py để xác nhận cải thiện tương quan, không thì rollback.

Ràng buộc: KHÔNG bịa Tm thực nghiệm (verified only); không đổi mô hình NN; English output.
```

## PROMPT 5 — 5′-tail tránh homopolymer, GC hợp lý (Busk I4)

```
Bối cảnh: đọc RESEARCH_INSIGHTS.md (I4), backend/algorithm/forward_primer.py
(_generate_tail_pool, _find_tails_for_target_tm — tool ĐÃ tự sinh tail để đạt target Tm),
constants.py dòng 78-82 (FORWARD_TAIL_MIN/MAX/OPTIMAL_MAX, GC_ENRICHED).

Bằng chứng: Busk 2014 thêm tail theo thứ tự G,A,C,G,C — tối đa G/C để nâng Tm NHƯNG
tránh stretch poly(C)/poly(G) gây trượt polymerase/homopolymer artifact.

Nhiệm vụ:
1) Trong _generate_tail_pool: LOẠI các tail chứa run homopolymer ≥ 3 (đặc biệt poly-G/poly-C ≥3),
   dùng hằng số mới TAIL_MAX_HOMOPOLYMER_RUN = 3 [Busk14] trong constants.py.
2) Ưu tiên tail GC-rich nhưng phá vỡ run (xen kẽ), phản ánh tinh thần G,A,C,G,C.
3) Đảm bảo vẫn đủ đa dạng tail để đạt target Tm cho miRNA GC thấp (không làm rỗng pool);
   nếu pool cạn → nới run limit có cảnh báo, không fail.
4) Test test_tail_pool.py: không tail nào có run ≥3; vẫn đạt được Tm target cho 1 miRNA GC thấp.
5) Chạy validation/ — deterministic checks vẫn 100% (tail đổi nhưng forward vẫn = tail+specific).

Ràng buộc: không đổi V4 weights; giữ reproducible seed hiện có; English output.
```

## PROMPT 6 — `primer_size` theo độ dài vùng specific, không phạt tail-để-đạt-Tm (Busk I6)

```
Bối cảnh: đọc RESEARCH_INSIGHTS.md (I6), scoring.py dòng ~170-175 (primer_size dùng
size_diff = |primer_len(FULL) - FORWARD_OPTIMAL_LENGTH|), forward_primer.py (specific_length, tail_length).

Vấn đề: primer_size hiện phạt theo TỔNG chiều dài (gồm cả 5′-tail). Nhưng tail được thêm để đạt Tm 60 °C
(cần thiết cho miRNA Tm thấp) → primer dài do tail bị phạt oan. Busk 2014 chấm điểm theo
ĐỘ DÀI PHẦN SPECIFIC (không phải full), công thức (specific_len)^2/400; reverse KHÔNG phạt độ dài
(khớp: reverse của ta là universal cố định).

Nhiệm vụ:
1) Đổi primer_size để dựa trên specific_length (phần bắt cặp miRNA), KHÔNG dựa full length.
   Có thể dùng dạng Busk: score = min(100, round((specific_len^2/ (SPECIFIC_LEN_REF^2)) *100))
   với SPECIFIC_LEN_REF cấu hình (vd 17). Longer specific → specific hơn → điểm cao.
2) Thêm constant + [NGUỒN Busk14]; cập nhật explanation.
3) KHÔNG đổi weight primer_size trong V4.
4) Test test_primer_size.py: specific_len 17 > 15 > 12 về điểm; tail dài KHÔNG làm tụt primer_size.
5) Chạy validation/ + (nếu có data) calibrate_weights.py so tương quan trước/sau.

Ràng buộc: English output; giữ V4 weights; feature-flag nếu muốn A/B (PRIMER_SIZE_MODE = "specific"|"full").
```

## PROMPT 7 — Module cấu trúc bậc 2 quanh vùng bắt primer (Fan19 I9 / SPEC_phase4 §12.2) — ưu tiên cao

```
Bối cảnh: đọc RESEARCH_INSIGHTS.md (I9), SPEC_phase4 §12.2, SPEC_phase5 PART D.1,
backend/algorithm/ (ViennaRNA đã dùng cho MFE stem-loop), routes/design.py.

Bằng chứng: Fan 2019 (DOI 10.1080/07391102.2018.1498804): hairpin gần vùng bắt primer ức chế
khuếch đại — mạnh nhất khi nằm TRONG amplicon; stem 20-bp → mất sản phẩm. Khuyến nghị phân tích
≥60 bp quanh mỗi vùng bắt primer.

Nhiệm vụ:
1) Tạo backend/algorithm/template_structure.py: dùng ViennaRNA fold cửa sổ ≥60 bp (constant
   TEMPLATE_FOLD_WINDOW = 60 [Fan19]) quanh vùng bắt của forward (và, nếu có ngữ cảnh, reverse) trên
   template cDNA dự kiến. Phát hiện hairpin bền (stem dài/loop nhỏ) tại/near binding site.
   Ưu tiên vùng TRONG amplicon (tác động mạnh hơn theo Fan19).
2) Trả về design_result dưới key 'template_structure' (mfe, has_strong_local_hairpin, vị trí).
   Thêm cảnh báo 'warning' vào global_warnings nếu có hairpin bền tại binding site.
3) (tuỳ chọn, tách riêng) thêm tiêu chí scoring 'template_structure' điểm NHẸ — nhưng
   MẶC ĐỊNH chỉ cảnh báo, KHÔNG đổi V4 weights ở bước này (để calibration quyết định sau).
4) Đo thời gian: fold thêm phải giữ /api/design < 5s; cache theo miRNA nếu cần.
5) Test test_template_structure.py: template có hairpin 20-bp tại binding → cờ; template trơn → không cờ.
6) Chạy validation/ — deterministic checks vẫn 100%.

Ràng buộc: dùng ViennaRNA đã có (không thêm dependency); English output; giữ tốc độ; V4 weights không đổi.
```

---

## Thứ tự chạy & kiểm chứng (sau khi Claude Code làm xong)
1. `cd backend && pytest -q` — tất cả test cũ + mới xanh.
2. `python app.py` (Terminal 1) → `python validation/validate_primers.py` (Terminal 2):
   nhóm deterministic **phải 100%**; xem thay đổi grade/score và số rejected.
3. (Khi có dữ liệu) `python calibration/calibrate_weights.py`: đối chiếu **báo cáo tương quan**
   trước/sau fix — kỳ vọng gc_clamp/dimer tương quan với kết quả thực **tăng** hoặc ổn định.
4. Commit + Superpower security check (endpoint không đổi input surface, nhưng vẫn quét).

## Vì sao an toàn
- Không đổi trọng số → không phá cân bằng V4 đã hiệu chỉnh; chỉ sửa hàm sub-score + thêm cổng lọc.
- Mọi ngưỡng có [NGUỒN] + bật/tắt được → có thể rollback/so sánh khách quan.
- Deterministic validation đảm bảo cấu trúc primer (phần bất biến khoa học) không bị ảnh hưởng.

*Nguồn: Busk 2014 DOI [10.1186/1471-2105-15-29](https://doi.org/10.1186/1471-2105-15-29); Kang 2017 DOI [10.1261/rna.061150.117](https://doi.org/10.1261/rna.061150.117). Thông tin trích từ PubMed.*
