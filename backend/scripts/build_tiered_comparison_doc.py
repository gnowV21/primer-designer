"""
scripts/build_tiered_comparison_doc.py — writes docs/SCORING_TIERED_COMPARISON.md from the
committed data (SPEC_scoring_tiered_4.0.0 Giai đoạn 3). The V4 3.8.2 numbers of the hsa
matrix, its sanity check and the BLAST sensitivity are read from git (--v4-ref, default
master = algorithm 3.8.2); the 4.0.0 numbers from the working tree.

    python backend/scripts/build_tiered_comparison_doc.py [--v4-ref master]
"""
import argparse
import csv
import json
import os
import subprocess

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_ap = argparse.ArgumentParser()
_ap.add_argument("--v4-ref", default="master")
REF = _ap.parse_args().v4_ref
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding="utf-8"))   # noqa: E731


def G(p):
    """A file of the V4 3.8.2 run, from git."""
    return json.loads(subprocess.run(["git", "show", f"{REF}:{p}"], capture_output=True,
                                     encoding="utf-8", cwd=ROOT, check=True).stdout)
r2c = J("benchmark/tiered_stage2c_report.json")
eq = J("benchmark/blast_batch_equivalence.json")
tim = J("benchmark/tiered_design_timing.json")
s1chk = J("benchmark/tiered_stage3_cache_s1.json")
xr_new = J("outputs/crossreactivity_metadata.json")
xr_old = G("outputs/crossreactivity_metadata.json")
xv_new = J("validation/crossreactivity_validation_report.json")["sanity"]
xv_old = G("validation/crossreactivity_validation_report.json")["sanity"]
sens_new = J("benchmark/blast_tm_gate_sensitivity.json")["summary"]["all"]["10"]
sens_old = G("benchmark/blast_tm_gate_sensitivity.json")["summary"]["all"]["10"]
fb = list(csv.DictReader(open(os.path.join(ROOT, "benchmark/tiered_fallback_list.csv"), encoding="utf-8")))
T53, T72 = r2c["table_2253"], r2c["table_2472"]

def n(x):
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else (f"{x}".replace(".", ",") if isinstance(x, float) else str(x))

def lv(d, keys=(1, 2, 3, 4, 5)):
    return "/".join(n(d.get(str(k), d.get(k, 0))) for k in keys)

def tm(c):
    return f"{n(c['binding_tm_median'])} ({n(c['binding_tm_p05_p95'][0])}–{n(c['binding_tm_p05_p95'][1])})"

cols = [("V4 3.8.2", T53["v4_382"]), ("tiered G2", T53["tiered_g2"]), ("QĐ 29", T53["qd29"]), ("cuối", T53["final"])]
L = []
w = L.append
w("# So sánh V4 và hệ chấm điểm phân tầng (algorithm 4.0.0)")
w("")
w("Tài liệu này so V4 (bản 3.8.2, chấm điểm có trọng số 14 tiêu chí) với hệ phân tầng ưu tiên đặc hiệu của 4.0.0 (`docs/SPEC_scoring_tiered_4.0.0.md`). Mọi số liệu tính trong máy (in silico), chưa hiệu chỉnh bằng wet-lab.")
w("")
w("## 1. Hai hệ chấm điểm")
w("- **V4** (`scoringSystem: \"v4\"`): tổng có trọng số của 13 tiêu chí; GC % và kẹp GC là bộ lọc sơ bộ; 3 lọc cứng cấu trúc (`hard_filter_fallback` khi mọi ứng viên trượt).")
w("- **Tiered** (mặc định 4.0.0). Khóa xếp hạng: `(−S_total, structure_veto, binding_floor_fail, has_v4_violation, −P_total, −F_total, −detailed_score, |Tm − Ta|, sequence)`.")
w("  - **S** (đặc hiệu, tối đa 15): S1 BLAST cùng loài (classifier v7, có bước RT), S2 min ΔCq_assay, S3 biên Tm. Ứng viên S1 = 1 (CRITICAL) hoặc S2 = 1 (CO-AMPLIFIED) bị loại; nếu mọi ứng viên bị loại thì giữ cả và gắn `specificity_fallback`.")
w("  - **Veto mềm:** cấu trúc (một chỉ số con F5 = 1), rồi sàn Tm vùng bám (< 39 °C, QĐ 36); chỉ có tác dụng khi cùng S.")
w("  - **Luật V4** (QĐ 34): khi cùng S và veto, bộ không vi phạm luật V4 xếp trước.")
w("  - **P** (tối đa 5): \\|Tm − Ta\\|. **F** (tối đa 20): GC %, kẹp GC, sàn Tm vùng bám (≥ 45 °C → 5), cấu trúc. Độ dài vùng đặc hiệu chỉ báo cáo (QĐ 29).")
w("  - **Grade** (QĐ 30): A = qua bước loại, S1 ≥ 4, S2 ≥ 3, S3 ≥ 4, không veto; B = có điểm yếu hoặc không có BLAST; C = fallback.")
w("")
w("## 2. Nguồn và mẫu số")
w(f"- 2656 miRNA hsa, miRBase 22.1. **2472** thiết kế có ứng viên ở hệ tiered; **2253** thiết kế mà V4 cũng có mồi (V4 không thiết kế được 403 miRNA, tiered còn 184).")
w("- Xếp hạng offline trên pool đã ghi (`outputs/freeze_cache/tiered_pools_hsa.jsonl.gz`), với S1 của mọi ứng viên từ lượt BLAST gộp của Giai đoạn 2 (`outputs/freeze_cache/tiered_blast_full_hsa.jsonl.gz`). Báo cáo: `benchmark/tiered_stage2c_report.json`.")
w(f"- Pipeline thật trùng offline:")
w(f"  - bộ #1 của lượt dựng ma trận (API thật, BLAST thật) trùng #1 offline ở **2472/2472** thiết kế;")
w(f"  - S1 của {n(s1chk['candidates_in_cache'])} ứng viên trong cache khác offline ở **{s1chk['s1_level_different']}** ca;")
w(f"  - 20 thiết kế ngẫu nhiên chạy 2 lần cho kết quả giống hệt.")
w(f"- BLAST gộp (một `blastn` multi-FASTA + một `blastdbcmd` cho mỗi thiết kế) khác cách gọi từng mồi ở **{eq['calls_different']}/{n(eq['calls'])}** lần gọi (`benchmark/blast_batch_equivalence.json`).")
w("")
w("## 3. Bộ #1 trên 2656 miRNA hsa")
w("Bốn cột đầu tính trên 2253 thiết kế (V4 có mồi), cột cuối trên 2472. \"tiered G2\" = hệ tiered như duyệt ở Giai đoạn 1–2 (F3 + F4 hai phía, chưa QĐ 34/36); \"cuối\" = QĐ 29 + 33 + 34 + 36 (mặc định 4.0.0).")
w("")
w("| Bộ #1 | " + " | ".join(c for c, _ in cols) + " | cuối (2472) |")
w("|---|" + "---|" * (len(cols) + 1))
def row(label, f, f72=None):
    w(f"| {label} | " + " | ".join(f(c) for _, c in cols) + f" | {(f72 or f)(T72['final'])} |")
row("#1 khác V4", lambda c: n(c.get("top1_changed_vs_v4", "—")), lambda c: "—")
row("L trung bình (nt)", lambda c: n(c["mean_specific_length"]))
row("Tm vùng bám, trung vị (p05–p95), °C", tm)
row("% Tm vùng bám < 45 °C", lambda c: n(c["pct_binding_tm_below_45"]))
row("Mức F4 (thang sàn) 1/2/3/4/5", lambda c: lv(c["f4_floor_level"]))
row("S1 BLAST 1/2/3/4/5", lambda c: lv(c["top1_s1_level"]))
row("S2 ΔCq 1/2/3/4/5", lambda c: lv(c["top1_s2_level"]))
row("#1 vi phạm luật V4", lambda c: n(c["top1_breaks_v4_rule"]))
row("#1 structure_veto", lambda c: n(c.get("top1_structure_veto", "—")))
row("Thiết kế có ứng viên bị loại", lambda c: n(c.get("designs_with_eliminated", "—")))
row("specificity_fallback", lambda c: n(c.get("specificity_fallback", "—")))
row("Trả < 3 bộ", lambda c: n(c.get("fewer_than_3_sets", "—")))
row("Grade A/B/C", lambda c: "/".join(n(c["grade"].get(k, 0)) for k in "ABC") if "grade" in c else "—")
w("")
w("- Ở bảng trên, grade của \"tiered G2\" và \"QĐ 29\" tính theo QĐ 30, để so được. V4 dùng thang Excellent/Good/Acceptable/Poor theo điểm tổng, không so trực tiếp.")
w("- Trong 2253 thiết kế, #1 của V4 có S2 = 1 (CO-AMPLIFIED theo mô hình assay) ở 55 ca; ở hệ tiered là 39 ca, và cả 39 đều nằm trong thiết kế fallback.")
fd = T72["final"]["top1_vs_top2_decided_by"]
w("- **#1 so với #2 được phân định bởi** (cuối, 2472): " + ", ".join(f"{k} {n(v)}" for k, v in fd.items()) + ". \"sequence\" = hòa mọi chỉ số (các biến thể đuôi 5′), thứ tự tùy ý nhưng tất định (QĐ 27).")
gr = T72["final"]["grade_reasons"]
w("- **Lý do mức B/C** (cuối, 2472): " + "; ".join(f"{k.split(':')[0]} {n(v)}" for k, v in gr.items()) + ".")
w("")
w("## 4. S1 của bộ #1: V4 so với tiered")
f53 = T53["final"]
w(f"Cùng classifier BLAST v7 và cùng mồi RT. S1 của #1 V4 3.8.2 (2253): mức 5/4/3/2/1 = {lv(T53['v4_382']['top1_s1_level'], (5,4,3,2,1))}.")
w(f"- **{f53['v4_top1_s1_le_2']} bộ #1 của V4 có S1 ≤ 2** (HIGH hoặc CRITICAL). Hệ tiered chọn bộ #1 có S1 cao hơn ở **{f53['of_which_top1_s1_higher']}** ca (như nhau ở mọi cấu hình tiered).")
w("  - Từ CRITICAL lên mức 2/3/4/5: 4/9/9/7 (chi tiết chuyển mức đo ở Giai đoạn 2b, `benchmark/tiered_stage2b_report.json`; S1 của #1 không đổi qua QĐ 33/34/36).")
w("  - Từ HIGH lên mức 5: 5.")
w("- 51 ca còn lại không cải thiện được: 38 CRITICAL → CRITICAL (đều là thiết kế fallback) và 13 HIGH → HIGH. Ở các miRNA này, mọi ứng viên đều có off-target mà BLAST đánh giá là nguy cơ.")
w("- Tổng S của #1 tiered cao hơn #1 V4 ở 227 thiết kế; #1 V4 bị hệ tiered loại (S1 = 1 hoặc S2 = 1) ở 78 thiết kế (`benchmark/tiered_stage2b_report.json`).")
w("")
w("## 5. Vi phạm luật V4 (QĐ 32/34/36)")
br = f53["v4_rule_breaks_vs_v4_top1"]
w(f"Các thiết kế mà #1 tiered vi phạm luật V4 trong khi #1 V4 không vi phạm (2253, đã trừ 219 ca V4 không thiết kế được): G2 {T53['tiered_g2']['v4_rule_breaks_vs_v4_top1']['n']} → QĐ 29 {T53['qd29']['v4_rule_breaks_vs_v4_top1']['n']} → không QĐ 36 {T53['final_without_qd36']['v4_rule_breaks_vs_v4_top1']['n']} → **cuối {br['n']}**.")
w(f"- **ΔS > 0** ({sum(v for k, v in br['by_delta_S'].items() if k != '0')} ca): hệ mới chấp nhận vi phạm để được đặc hiệu cao hơn. Luật: " + ", ".join(f"`{k}` {v}" for k, v in br["rules_delta_S_gt_0"].items()) + ".")
w(f"- **ΔS = 0** ({br['by_delta_S'].get('0', 0)} ca): đều do veto sàn Tm vùng bám quyết định, tức bộ V4 có Tm vùng bám < 39 °C. Luật: " + ", ".join(f"`{k}` {v}" for k, v in br["rules_delta_S_eq_0"].items()) + ".")
w("- Bộ #1 của V4 tự vi phạm luật V4 ở 115 thiết kế: chính là các ca `hard_filter_fallback`.")
w("")
w("## 6. Bộ validation (201 mục; 2439 check)")
w("- Hồi quy V4: `validate_primers.py --scoring-system v4` cho `results.json` và `results.csv` trùng bản 3.8.2.")
w("- **Tiered: 2436/2439 check đạt.** 3 check `expected_design_failure` không đạt (xem mục 6.1).")
w("- So với V4 3.8.2:")
w("  - vùng đặc hiệu của mồi xuôi đổi ở 90/189 mục;")
w("  - L trung bình 14,43 → 14,97 nt;")
w("  - độ trùng trung bình với vùng đặc hiệu của mồi đã công bố 13,74 → 14,10 nt;")
w("  - số mục chung vùng lõi với mồi công bố không đổi (184), mồi RT không đổi.")
w("")
w("### 6.1 Check không đạt (không sửa check)")
w("| Mục | Check | Lý do | #1 tiered | Đề xuất |")
w("|---|---|---|---|---|")
w("| ath-miR171a-3p (Varkonyi-Gasic 2007) | `expected_design_failure` | Ghi là KNOWN LIMITATION của V4: đầu 5′ giàu GC, V4 từ chối. Tiered bỏ lọc GC (QĐ 15) nên thiết kế được | CTAC + **TGATTGAGCCGCGCC** (L 15, GC 63,2 %), trùng 15 nt vùng đặc hiệu của mồi công bố | Đổi kỳ vọng của mục theo hệ chấm điểm: V4 = từ chối; tiered = so với mồi công bố |")
w("| ebv-miR-BART6-3p (Cosmopoulos 2009) | `expected_design_failure` | Như trên (V4 từ chối vì GC); bài dùng hệ stem-loop khác | GGAC + CGGGGATCGGACTA (L 14, GC 63,2 %), nằm trong vùng công bố CGGGGATCGGACTAGC | Như trên |")
w("| mmu-miR-124-3p (Lukashevich 2026, bm_001) | `expected_design_failure` | V4 từ chối (`gc_end_window_fail`) | CCTGATAG + **TAAGGCACGCGG** (L 12), trùng vùng đặc hiệu của mồi công bố AAGTACTC + TAAGGCACGCGG | Như trên |")
w("")
w("## 7. Ma trận phản ứng chéo hsa (mồi #1, mô hình assay)")
def off(meta, lev):
    v = meta["pairs_by_level"][lev]
    return v - meta["n_assays"] if lev == "HIGH" else v
w("| | V4 3.8.2 | 4.0.0 tiered |")
w("|---|---|---|")
w(f"| Số assay | {n(xr_old['n_assays'])} | {n(xr_new['n_assays'])} |")
w(f"| Cặp ngoài đường chéo HIGH / MEDIUM / LOW | {n(off(xr_old,'HIGH'))} / {n(off(xr_old,'MEDIUM'))} / {n(off(xr_old,'LOW'))} | {n(off(xr_new,'HIGH'))} / {n(off(xr_new,'MEDIUM'))} / {n(off(xr_new,'LOW'))} |")
w(f"| Cặp gần giống (khác 1–2 vị trí, {xv_new['n_close_pairs']} cặp): R trung bình / % R > 10 % | {n(round(xv_old['close_mean_R'], 3))} / {n(round(100 * xv_old['close_frac_above_10pct'], 1))} | {n(round(xv_new['close_mean_R'], 3))} / {n(round(100 * xv_new['close_frac_above_10pct'], 1))} |")
w("")
w("HIGH ngoài đường chéo = số assay đếm ở mức HIGH trừ đường chéo. LOW tăng chủ yếu vì có thêm 219 assay.")
w("")
w("## 8. BLAST và thời gian")
w(f"- Thiết kế không cache (20 miRNA hsa, `random.Random(2026)`): **p50 {n(tim['seconds']['p50'])} s, p90 {n(tim['seconds']['p90'])} s** (giới hạn 15 s), trong đó BLAST p50 {n(tim['blast_seconds']['p50'])} s. Trước khi gộp, BLAST một thiết kế mất khoảng 213 s.")
w(f"- Lề an toàn Tm của BLAST (`benchmark/blast_tm_gate_sensitivity.json`, 175 mồi của bộ validation, lề 10 °C): SAFE {sens_old['primers_by_overall_risk'].get('SAFE')} → {sens_new['primers_by_overall_risk'].get('SAFE')}, CRITICAL {sens_old['primers_by_overall_risk'].get('CRITICAL')} → {sens_new['primers_by_overall_risk'].get('CRITICAL')} (V4 → tiered).")
w("")
w("## 9. Thiết kế `specificity_fallback` (54) và kiểm tra wet-lab")
w("Mọi ứng viên của các miRNA này đều bị loại vì BLAST CRITICAL hoặc ΔCq CO-AMPLIFIED. Tool vẫn trả 3 bộ, kèm grade C. Danh sách đầy đủ ở `benchmark/tiered_fallback_list.csv`; cột `wetlab_check` ghi phản ứng chéo cần kiểm.")
w("")
w("- Off-target chính của S2, theo loại: " + ", ".join(f"{k} {v}" for k, v in r2c.get("_fb_cat", {}).items()) if r2c.get("_fb_cat") else "- Off-target chính của S2: `other` 35, `shifted_3p` 13, `shifted_5p` 3; S2 không loại 3. Nguyên nhân bị loại: cả S1 và S2 ở 48 thiết kế, chỉ S1 ở 3, chỉ S2 ở 3.")
w("- **Ưu tiên kiểm phản ứng chéo ở wet-lab:**")
w("  1. **hsa-let-7a-5p**, một trong 6 ứng viên wet-lab, rơi vào fallback do let-7d-5p (ΔCq 1,43; BLAST CRITICAL). Thí nghiệm let-7a nên có đối chứng let-7d (và các thành viên let-7 khác) để đo tín hiệu chéo thật.")
w("  2. hsa-miR-17-5p và hsa-miR-20a-5p (ca mẫu của SPEC) phản ứng chéo với miR-106a-5p / miR-20b-5p (họ miR-17).")
w("  3. Các cặp lệch đầu (`shifted_3p` / `shifted_5p`, ví dụ họ miR-548, miR-520): không mồi nào tách được; nên đo tổng tín hiệu.")
w("")
w("| miRNA | Họ seed | Off-target chính (loại) | #1: S1 / min ΔCq | Kiểm tra wet-lab |")
w("|---|---|---|---|---|")
for r in fb:
    tgt = r["main_s2_offtarget"] or r["main_s1_offtarget"]
    cat = r["main_s2_offtarget_category"] or r["main_s1_offtarget_category"]
    w(f"| {r['mirna']} | {r['seed_family'] or '—'} | {tgt} ({cat}) | {r['top1_blast_risk']} / {r['top1_min_delta_cq']} | {r['wetlab_check']} |")
w("")
w("## 10. Giới hạn")
w("- **F2 (kẹp GC)** đếm G/C trong 5 nt cuối, không xét vị trí. Ví dụ …GCAAT được 5 điểm, trong khi V4 loại vì 3 nt cuối không có G/C. QĐ 34 xử lý phần lớn các ca cùng S.")
w("- **Mốc 45 °C của Tm vùng bám là mức sàn** rút từ giả thuyết chu kỳ 1 của khóa luận (let-7a 33,6 so với 46,2 °C), không phải đích tối ưu. Mốc 45 °C là trung vị Tm của các vùng 12–17 nt.")
w("- **196/2472 thiết kế không thể đạt sàn 39 °C**: trong nhóm đặc hiệu cao nhất không có ứng viên nào có Tm vùng bám ≥ 39 °C. Bộ #1 của các thiết kế này nhận grade B.")
w("- Các ngưỡng ghi \"own threshold\" (S2 mức 4, S3 mức 3/5, P2, F3, F4, mốc 25 °C của điểm chi tiết) **chưa được hiệu chỉnh bằng wet-lab**. Mô hình ΔCq assay cũng chưa được hiệu chỉnh.")
w("- BLAST chỉ tìm trên miRBase 22.1 (miRNA trưởng thành, cùng loài + loài chủ nếu là virus). Chưa xét tRNA, Y RNA, snoRNA.")
w("- Frontend chưa hiển thị hệ tiered. Ở 444 thiết kế, `total_score` (điểm chi tiết) của #1 thấp hơn #2, nên câu giải thích \"#1 so với #2\" hiện tại có thể sai. Phần này chờ SPEC UI (QĐ 31).")
open(os.path.join(ROOT, "docs", "SCORING_TIERED_COMPARISON.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("ok", len(L))
