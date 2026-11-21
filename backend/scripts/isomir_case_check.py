"""
In silico check of published 3' isomiR cases (docs/PROMPT_isomir_variants_4.0.0.md, Part 4).

A REPORT, not a pass/fail validation: the published observations come from other
cells, assays and reference sequences (see the header written to the .md file).

Designs each miRNA through the Flask test client with the backend defaults (overhang
6 nt, nothing else sent), reads stemloop_rt.three_prime_isomir from the API output and
puts it next to what the papers observed.

Usage (from backend/):
  python scripts/isomir_case_check.py
Writes ../benchmark/isomir_case_check.json and ../docs/ISOMIR_CASE_CHECK.md.
"""
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

OUT_JSON = os.path.join(ROOT, "benchmark", "isomir_case_check.json")
OUT_MD = os.path.join(ROOT, "docs", "ISOMIR_CASE_CHECK.md")

# Published observation per case (owner's synthesis, PROMPT §4.2) and how the paper's
# reference relates to miRBase 22.1. No numbers here feed the tool.
CASES = [
    ("hsa-miR-21-5p", "Magee 2017",
     "Stem-loop TaqMan cho dạng chuẩn bắt cả 0|+1, −1|0, −1|+1; trong tế bào chuyển nạp "
     "không phân biệt được các dạng.",
     "Ký hiệu 5′|3′ của bài gồm cả lệch đầu 5′; tool chỉ xét đầu 3′.",
     "Khớp: bảng xếp ±1/+2 nt vào khoảng đo được 0–4 Ct, tức assay đo tổng các dạng. "
     "Đầu 22.1 vẫn là dạng nhiều nhất nên không có cảnh báo isoform trội."),
    ("hsa-miR-33b-5p", "Schamberger 2014",
     "Assay \"GC\" và \"GCA\" bắt chéo nhau, trễ 2–4 Ct; giải trình tự thấy dạng dài hơn "
     "nhiều hơn tham chiếu.",
     "\"GC\" = đầu 3′ của 22.1 (20 nt); \"GCA\" = +1 nt so với 22.1.",
     "Khớp về mức bắt: khoảng 0–4 Ct của ±1 nt chứa chính số đo 2–4 Ct của miRNA này. "
     "Khác về tỉ lệ: isomiRdb (pooled) cho dạng +1 ít hơn đầu 22.1, còn bài thấy dạng dài "
     "hơn nhiều hơn. Mẫu khác nhau, nên tool không bật cảnh báo isoform trội."),
    ("hsa-miR-877-5p", "Schamberger 2014",
     "Assay GACA/GAC bắt nhau gần 0 Ct; GA trễ khoảng 3 Ct; assay GA bắt cả ba dạng.",
     "Bài dùng dạng GACA (24 nt) làm tham chiếu; 22.1 dài 20 nt (…CAGGG). So với 22.1: "
     "GA = +2, GAC = +3, GACA = +4 nt. Dạng 20 nt của 22.1 không được thử trong bài.",
     "Khớp với cách ghi: bài chỉ so các dạng 22–24 nt với nhau, không có assay nhắm đầu "
     "20 nt của 22.1, nên +3/+4 ghi \"not measured\" là đúng. isomiRdb cũng thấy dạng dài "
     "nhiều hơn đầu 22.1, nên cảnh báo isoform trội bật."),
    ("hsa-miR-222-3p", "Nejad 2018; Pillman 2019",
     "TaqMan 21 nt bắt isoform 22–25 nt; isoform dài trội; không thấy mức giảm 70 % "
     "sau IFN.",
     "TaqMan 21 nt = độ dài 22.1; isoform 22–25 nt = +1 đến +4 nt so với 22.1.",
     "Khớp: cảnh báo isoform trội và cờ fold-change đều bật. Tool ghi +3/+4 là \"not "
     "measured\", không nói assay bắt kém; Nejad thấy TaqMan vẫn bắt các dạng này nhưng "
     "không có số Ct theo từng dạng, nên tool không có số để dùng."),
    ("hsa-miR-221-3p", "Pillman 2019",
     "Assay nhắm dạng dài hơn dạng trội 1 nt; báo \"giảm\" trong khi tổng tăng.",
     "Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.",
     "Khớp: dạng trội là −1 nt, tức đầu 22.1 mà mồi RT nhắm dài hơn dạng trội 1 nt như bài "
     "mô tả; cảnh báo isoform trội bật."),
    ("hsa-miR-27b-3p", "Pillman 2019",
     "Assay nhắm dạng dài hơn dạng trội 1 nt; báo \"giảm\" trong khi tổng tăng.",
     "Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.",
     "Khớp nhưng sát ngưỡng: dạng −1 nt gần bằng đầu 22.1; cảnh báo chỉ bật nhờ mốc 0,8 "
     "(luật R1 \"> 1\" sẽ bỏ sót ca này)."),
    ("hsa-miR-27a-3p", "Pillman 2019",
     "Kết luận RT-qPCR đã công bố lệch so với RNA-seq mức isoform.",
     "Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.",
     "Khớp: dạng −1 nt nhiều hơn đầu 22.1; cảnh báo isoform trội bật."),
    ("hsa-miR-107", "Pillman 2019",
     "Kết luận RT-qPCR đã công bố lệch so với RNA-seq mức isoform.",
     "Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.",
     "Khớp nhưng sát ngưỡng: dạng −1 nt gần bằng đầu 22.1; cảnh báo chỉ bật nhờ mốc 0,8."),
    ("hsa-miR-30a-5p", "Pillman 2019",
     "Kết luận RT-qPCR đã công bố lệch so với RNA-seq mức isoform.",
     "Đại thực bào người/chuột, assay thương mại không công bố trình tự mồi.",
     "Cảnh báo isoform trội không bắt được: trong isomiRdb (pooled), đầu 22.1 vẫn nhiều "
     "hơn hẳn biến thể lớn nhất. Tool vẫn có cảnh báo 3′ mức high và cờ fold-change. "
     "Lý do bỏ sót là **giả thuyết, chưa kiểm**: tỉ lệ isoform của miR-30a-5p có thể đổi "
     "theo kích thích ở đại thực bào, điều mà dữ liệu isomiRdb gộp mọi mẫu không thấy."),
]


def _design(client, name: str) -> dict:
    from db import local_db
    row = local_db.lookup(name)
    if row is None:
        raise SystemExit(f"{name}: not in the local miRBase 22.1 database")
    r = client.post("/api/design", json={"sequence": {
        "matureSequence": row["sequence"], "mirnaName": row["name"]}})
    if r.status_code != 200:
        raise SystemExit(f"{name}: /api/design returned HTTP {r.status_code}")
    return {"sequence_rna": row["sequence"], "response": r.get_json()}


def _record(name: str, sequence_rna: str, resp: dict) -> dict:
    sl = resp["stemloop_rt"]
    t = sl["three_prime_isomir"]
    from algorithm.constants import ISOMIR_DOMINANT_RATIO
    variants = t.get("dominant_3prime_variants") or []
    canon = t.get("canonical_3prime_share_pooled")
    top = variants[0]["pooled_share"] if variants else None
    return {
        "mirna": name,
        "algorithm_version": resp.get("metadata", {}).get("algorithm_version"),
        "sequence_rna_22_1": sequence_rna,
        "length": len(sequence_rna),
        "overhang_rna": sl.get("overhang_rna"),
        "overhang_len": sl.get("binding_length"),
        "level": t.get("level"),
        "median_3prime_fraction": t.get("median_3prime_fraction"),
        "iqr_3prime_fraction": t.get("iqr_3prime_fraction"),
        "three_prime_isomir_risk": t.get("three_prime_isomir_risk"),
        "fold_change_bias_risk": t.get("fold_change_bias_risk"),
        "canonical_3prime_share_pooled": canon,
        "reference_status": t.get("reference_status"),
        "dominant_isoform_risk": t.get("dominant_isoform_risk"),
        "dominant_isoform_short": t.get("dominant_isoform_short"),
        "dominant_ratio": round(top / canon, 3) if top is not None and canon else None,
        "dominant_threshold": ISOMIR_DOMINANT_RATIO,
        "top3": [{"sequence_dna": v["sequence_dna"], "label": v["label"],
                  "type_label": v.get("type_label"), "relation": v.get("relation"),
                  "shift_3p": v.get("shift_3p"), "pooled_share": v["pooled_share"],
                  "capture_class": (v.get("rt_capture") or {}).get("class"),
                  "capture_label": (v.get("rt_capture") or {}).get("label")}
                 for v in variants],
        "warning_fields": [w["field"] for w in sl.get("warnings", [])
                           if w.get("severity") == "warning"],
    }


def _verdict(rec: dict) -> str:
    """Which warnings the tool raises and why (from the API values only)."""
    out = []
    lvl, med = rec["level"], rec["median_3prime_fraction"]
    out.append(f"mức 3′ **{lvl}** (median {med:.3f})"
               + ("" if rec["three_prime_isomir_risk"] else ", không có cảnh báo 3′ mức high"))
    out.append("cờ fold-change **có**" if rec["fold_change_bias_risk"] else "cờ fold-change không")
    ratio, thr = rec["dominant_ratio"], rec["dominant_threshold"]
    top = rec["top3"][0] if rec["top3"] else None
    if rec["reference_status"] != "matches":
        out.append(f"isoform trội không đánh giá ({rec['reference_status']})")
    elif top is None:
        out.append("không có biến thể")
    else:
        cmp_ = "≥" if rec["dominant_isoform_risk"] else "<"
        out.append(f"isoform trội **{'có' if rec['dominant_isoform_risk'] else 'không'}**: top 1 "
                   f"{top['type_label']} {top['pooled_share']:.3f} so với đầu 22.1 "
                   f"{rec['canonical_3prime_share_pooled']:.3f} (tỉ lệ {ratio:.3f} {cmp_} {thr})"
                   + (" — chỉ bật nhờ mốc 0,8; luật R1 (> 1) không bật"
                      if rec["dominant_isoform_risk"] and ratio < 1 else ""))
    return "; ".join(out)


def _pct(x):
    return f"{100 * x:.1f} %"


def _base_rates() -> dict:
    """Share of all hsa miRNAs with 3' data that raise each isomiR warning (overhang 6 nt,
    miRBase 22.1 sequence) — the background against which 9 published cases are read."""
    from algorithm.specificity_check.isomir_flag import check_3prime_isomir_flag, _load_db3
    names = [k for k, v in _load_db3().items()
             if not k.startswith("_") and "median_3prime_fraction" in v]
    n = dict(any=0, dominant=0, high=0, fold_change=0)
    for name in names:
        r = check_3prime_isomir_flag(name, 6)
        h, f, d = r["three_prime_isomir_risk"], bool(r["fold_change_bias_risk"]), r["dominant_isoform_risk"]
        n["any"] += h or f or d
        n["dominant"] += d
        n["high"] += h
        n["fold_change"] += f
    return {"n_mirnas": len(names), **n}


def _md(records: list, notes: dict, base: dict) -> str:
    N = base["n_mirnas"]

    def rate(k):
        return f"{base[k]}/{N} ({100 * base[k] / N:.1f} %)"

    L = [
        "# Kiểm in silico các ca isomiR 3′ đã công bố",
        "",
        f"Tạo bởi `backend/scripts/isomir_case_check.py` ngày {date.today().isoformat()}, "
        f"algorithm {records[0]['algorithm_version']}. Số liệu đầy đủ: "
        "`benchmark/isomir_case_check.json`.",
        "",
        "> **Đây là báo cáo, không phải kiểm chứng pass/fail.**",
        "> - Pillman 2019 đo ở đại thực bào chuột/người, bằng assay thương mại không công bố "
        "trình tự mồi.",
        "> - isomiRdb gộp mẫu người thuộc mọi loại mô và dịch; share ở đây là pooled.",
        "> - Tham chiếu 22.1 của miR-877-5p và miR-33b-5p dài 20 nt, khác tham chiếu trong bài "
        "(miR-877-5p: dạng GACA 24 nt).",
        "> - Tool không đo mức bắt; khoảng ΔCq chỉ lấy từ `ASSAY_DCQ_RT_SHIFT_RANGE` "
        "(Schamberger 2014, n = 1–2 miRNA). Lệch ≥ 3 nt không có số đo.",
        "> - **Mốc 0,8 của cảnh báo isoform trội được chọn sau khi đã thấy miR-27b-3p và "
        "miR-107** (dry-run Phần 1, `docs/ISOMIR_VARIANTS_DRYRUN.md`). Vì vậy kết quả 6/9 dưới "
        "đây không phải đánh giá độc lập của luật: ít nhất hai ca đã ảnh hưởng tới việc chọn mốc.",
        "> - Cột \"Nhận xét\" do người viết tay, chỉ so sánh định tính; dòng \"Tool\" sinh tự "
        "động từ output của API.",
        "",
        "Cách chạy: mỗi miRNA được thiết kế qua Flask test client với mặc định của backend "
        "(overhang 6 nt), trình tự lấy từ miRBase 22.1 cục bộ.",
        "",
        "**Tóm tắt:** cảnh báo isoform trội bật ở "
        f"{sum(r['dominant_isoform_risk'] for r in records)}/{len(records)} ca "
        f"({', '.join(r['mirna'].replace('hsa-', '') for r in records if r['dominant_isoform_risk'])}); "
        f"cờ fold-change ở {sum(bool(r['fold_change_bias_risk']) for r in records)}/{len(records)}; "
        f"cảnh báo 3′ mức high ở {sum(bool(r['three_prime_isomir_risk']) for r in records)}/"
        f"{len(records)}. Ca không có cảnh báo nào: "
        + (", ".join(r["mirna"].replace("hsa-", "") for r in records
                     if not (r["dominant_isoform_risk"] or r["fold_change_bias_risk"]
                             or r["three_prime_isomir_risk"])) or "không có") + ".",
        "",
        f"**Tỉ lệ nền** trên toàn bộ {N} miRNA hsa có dữ liệu 3′ (overhang 6 nt, trình tự "
        f"22.1): có ít nhất một cảnh báo isomiR 3′ {rate('any')}; cảnh báo isoform trội "
        f"{rate('dominant')}; mức high {rate('high')}; cờ fold-change {rate('fold_change')}. "
        "Chín ca ở đây được chọn vì đã có bài báo về isomiR, nên tỉ lệ cảnh báo cao hơn nền là "
        "điều có thể đoán trước.",
        "",
        "## Số liệu từ API",
        "",
        "| miRNA | 22.1 (nt) | Overhang | Mức 3′ (median) | Fold-change | Top 3 (pooled · mức bắt) "
        "| Đầu 22.1 (pooled) | Isoform trội |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        top = "; ".join(f"{v['type_label']} {_pct(v['pooled_share'])} · {v['capture_label']}"
                        for v in r["top3"]) or "—"
        L.append(
            f"| {r['mirna'].replace('hsa-', '')} | {r['sequence_rna_22_1']} ({r['length']}) "
            f"| {r['overhang_rna']} | {r['level']} ({r['median_3prime_fraction']:.3f}) "
            f"| {'có' if r['fold_change_bias_risk'] else 'không'} | {top} "
            f"| {_pct(r['canonical_3prime_share_pooled'])} "
            f"| {'✔' if r['dominant_isoform_risk'] else '—'} |")
    L += ["", "## Đối chiếu với quan sát đã công bố", ""]
    for r in records:
        src, obs, ref, cmp_ = notes[r["mirna"]]
        L += [f"### {r['mirna']}", "",
              f"- **Đã công bố ({src}):** {obs}",
              f"- **Tham chiếu:** {ref}",
              f"- **Tool:** {_verdict(r)}.",
              f"- **Nhận xét:** {cmp_}",
              ""]
    return "\n".join(L).rstrip() + "\n"


def main() -> None:
    from app import app
    client = app.test_client()
    records, notes = [], {}
    for name, src, obs, ref, cmp_ in CASES:
        d = _design(client, name)
        records.append(_record(name, d["sequence_rna"], d["response"]))
        notes[name] = (src, obs, ref, cmp_)
        print(f"{name}: level={records[-1]['level']} dominant={records[-1]['dominant_isoform_risk']}"
              f" fc={records[-1]['fold_change_bias_risk']}")
    base = _base_rates()
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"_about": ("In silico report of published 3' isomiR cases (not a pass/fail "
                              "validation); values from /api/design with backend defaults."),
                   "published": {n: {"source": s, "observation": o, "reference": r,
                                     "comparison": c}
                                 for n, (s, o, r, c) in notes.items()},
                   "base_rates": base,
                   "dominant_threshold_note": ("0.8 was chosen after miR-27b-3p and miR-107 had "
                                               "been seen in the Part 1 dry-run; the 6/9 is not "
                                               "an independent evaluation."),
                   "cases": records}, fh, indent=1, ensure_ascii=False)
    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_md(records, notes, base))
    print("wrote", OUT_JSON, "and", OUT_MD)


if __name__ == "__main__":
    main()
