"""
scripts/dimer_dg_method_compare.py — the tool's dimer ΔG vs Kang 2017's method.

The hard filter (rule 1) rejects a forward primer whose self-dimer or forward ×
universal-reverse dimer has ΔG < −9 kcal/mol. The −9 comes from Kang 2017
(miPrimer, RNA 24:304), which computes ΔG with RNAcofold using DNA parameters
(Gruber et al. 2008) and confirms borderline cases with OligoAnalyzer 3.1.
This tool computes it with primer3 thal at the annealing temperature (60 °C,
Na⁺ 50 mM, Mg²⁺ 1.5 mM, dNTP 0.8 mM, primer 200 nM). This script measures how
far apart the two energy scales are on the primer set #1 designed for every hsa
miRNA by crossreactivity/design_all.py.

RNAcofold is run with ViennaRNA's DNA parameter set (Mathews 2004) and its
default conditions (37 °C, 1.021 M Na⁺). The excerpt of Kang's Methods we have
does not state the temperature or salt, so these defaults are an assumption.

Usage (repo root):
    python backend/scripts/dimer_dg_method_compare.py \
        [outputs/crossreactivity_cache/designs_hsa.jsonl] [benchmark/dimer_dg_method_compare.json]
"""
import json
import statistics as st
import sys
from pathlib import Path

import primer3
import RNA

URP = "CCAGTGCAGGGTCCGAGGTA"
P3 = dict(mv_conc=50, dv_conc=1.5, dntp_conc=0.8, dna_conc=200)
LIMIT = -9.0


def p3_dg(a: str, b: str, temp_c: float) -> float:
    if a == b:
        r = primer3.calc_homodimer(seq=a, temp_c=temp_c, **P3)
    else:
        r = primer3.calc_heterodimer(seq1=a, seq2=b, temp_c=temp_c, **P3)
    return round(r.dg / 1000, 2)


def cofold_dg(a: str, b: str, md) -> float:
    _, e = RNA.fold_compound(a + "&" + b, md).mfe_dimer()
    return round(e, 2)


def summarise(values: list[float]) -> dict:
    return {
        "median": st.median(values),
        "min": min(values),
        "below_-8": sum(v < -8 for v in values),
        "below_-9": sum(v < LIMIT for v in values),
        "below_-10": sum(v < -10 for v in values),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "outputs/crossreactivity_cache/designs_hsa.jsonl"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "benchmark/dimer_dg_method_compare.json"

    RNA.params_load_DNA_Mathews2004()
    md = RNA.md()

    rows = []
    for line in src.open(encoding="utf-8"):
        d = json.loads(line)
        if d.get("status") != "ok":
            continue
        f = d["forward_primer"]
        rows.append({
            "mirna": d["mirna"], "forward": f,
            "p3_60": min(p3_dg(f, f, 60), p3_dg(f, URP, 60)),
            "p3_37": min(p3_dg(f, f, 37), p3_dg(f, URP, 37)),
            "cofold": min(cofold_dg(f, f, md), cofold_dg(f, URP, md)),
        })

    n = len(rows)
    diff = sorted(r["cofold"] - r["p3_60"] for r in rows)
    out = {
        "source": str(src.relative_to(root)) if src.is_relative_to(root) else str(src),
        "n_forward_primers": n,
        "metric": "min(self-dimer ΔG, forward × universal-reverse ΔG), kcal/mol",
        "methods": {
            "p3_60": "primer3 thal, 60 °C, mv 50 mM, Mg 1.5 mM, dNTP 0.8 mM, 200 nM (the tool)",
            "p3_37": "primer3 thal, same salts, 37 °C",
            "cofold": f"RNAcofold, DNA Mathews 2004, {md.temperature} °C, Na {md.salt} M (ViennaRNA {RNA.__version__} defaults)",
        },
        "p3_60": summarise([r["p3_60"] for r in rows]),
        "p3_37": summarise([r["p3_37"] for r in rows]),
        "cofold": summarise([r["cofold"] for r in rows]),
        "cofold_minus_p3_60": {
            "median": round(st.median(diff), 2),
            "p10": round(diff[n // 10], 2),
            "p90": round(diff[9 * n // 10], 2),
        },
        "most_negative_cofold": sorted(
            ({"mirna": r["mirna"], "forward": r["forward"],
              "p3_60": r["p3_60"], "cofold": r["cofold"]} for r in rows),
            key=lambda x: x["cofold"])[:10],
    }
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{n} primers; below −9: tool {out['p3_60']['below_-9']}, "
          f"RNAcofold {out['cofold']['below_-9']} -> {dst}")


if __name__ == "__main__":
    main()
