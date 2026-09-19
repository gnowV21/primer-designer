"""
Build data/known_3prime_isomir_mirnas.json from isomiRdb (audit SCI-10).

Source: Aparicio-Puerta E, et al. isomiRdb: microRNA expression at isoform
resolution. Nucleic Acids Res 2023;51(D1):D179-D185. PMID 36243964,
doi:10.1093/nar/gkac884. https://ccb-compute.cs.uni-saarland.de/isomirdb/downloads

Inputs (download from the page above, keep gzipped):
  isomirs.tsv.gz      — isomiR repertoire: "sequence:matureName", isoLabel
  isomiR_RPM.tsv.gz   — RPM matrix, rows = samples (~42k), cols = 90,481 isomiRs

Metric, per mature human miRNA:
  3' fraction = RPM of isoforms whose 3' end differs from the canonical
                (isoLabel contains lv3p / mlv3p / nta) ÷ RPM of all isoforms.
  Reported as the median (and IQR) over samples where the miRNA is expressed
  (total ≥ MIN_RPM), plus the pooled fraction and the top 3' variants.
Why 3' only: the stem-loop RT primer pairs with the miRNA 3'-terminal 5–7 nt,
so any 3'-end variant is captured poorly (Nejad 2018, PMID 29263133).
5'-only variants (lv5p) and internal mismatches (mv/NucVar) are not counted.

Usage (from backend/):
  python scripts/build_isomir_3prime_index.py <dir-with-the-two-files>
"""
import gzip
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

MIN_RPM = 10.0        # a miRNA counts as expressed in a sample at ≥ 10 RPM
BINS = 200            # histogram resolution for median / IQR (0.5 % steps)
CHUNK = 256           # sample rows per chunk
MAX_ROWS = None       # set via argv[2] for a quick partial smoke run
OUT = Path(__file__).resolve().parent.parent / "data" / "known_3prime_isomir_mirnas.json"
THREE_PRIME_TAGS = ("lv3p", "mlv3p", "nta")


def is_3prime(label: str) -> bool:
    """True if any variant tag changes the 3' end (e.g. "lv3p|lv3pE|lv3p#1", "nta#A")."""
    return any(part.startswith(THREE_PRIME_TAGS) for part in label.split("|"))


def load_labels(path: Path) -> dict:
    labels = {}
    with gzip.open(path, "rt") as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            labels[parts[1]] = parts[2]
    return labels


def quantile(hist: np.ndarray, q: float) -> float:
    c = np.cumsum(hist)
    if c[-1] == 0:
        return float("nan")
    return (int(np.searchsorted(c, q * c[-1])) + 0.5) / BINS


def _accumulate(m, order, inv, starts, mask3, hist, pooled_iso) -> int:
    """Add one block of samples (rows) to the per-miRNA histograms and pooled sums."""
    m = np.nan_to_num(m[:, order], copy=False)
    pooled_iso += m.sum(axis=0, dtype=np.float64)[inv]
    tot = np.add.reduceat(m, starts, axis=1)
    t3 = np.add.reduceat(m * mask3, starts, axis=1)
    expressed = tot >= MIN_RPM
    frac = np.divide(t3, tot, out=np.zeros_like(t3), where=expressed)
    b = np.minimum((frac * BINS).astype(np.int64), BINS - 1)
    rows, cols = np.nonzero(expressed)
    np.add.at(hist, (cols, b[rows, cols]), 1)
    return m.shape[0]


def main(src: Path) -> None:
    labels = load_labels(src / "isomirs.tsv.gz")
    rpm_path = src / "isomiR_RPM.tsv.gz"
    header = pd.read_csv(rpm_path, sep="\t", nrows=0).columns[1:]
    names = [h.split(":", 1)[1] for h in header]
    mirnas = sorted(set(names))
    idx = {m: i for i, m in enumerate(mirnas)}
    col_mir = np.array([idx[n] for n in names])
    col_3p = np.array([is_3prime(labels.get(h, "")) for h in header])
    unlabeled = sum(1 for h in header if h not in labels)

    # Sort columns by miRNA so per-miRNA sums are one reduceat per chunk.
    order = np.argsort(col_mir, kind="stable")
    starts = np.r_[0, np.flatnonzero(np.diff(col_mir[order])) + 1]
    mask3 = col_3p[order].astype(np.float32)

    n_mir = len(mirnas)
    hist = np.zeros((n_mir, BINS), dtype=np.int64)
    pooled_iso = np.zeros(len(header), dtype=np.float64)
    n_samples = 0

    # Line-by-line with np.fromstring: pandas' parser is ~50x slower on a
    # 90k-column table (per-column overhead).
    inv = np.argsort(order)
    with gzip.open(rpm_path, "rt") as f:
        next(f)                                     # header
        batch = []
        for line in f:
            # "NA" = not detected in that sample → 0 RPM.
            vals = line[line.index("\t") + 1:].replace("NA", "0")
            batch.append(np.fromstring(vals, sep="\t", dtype=np.float32))
            if len(batch) == CHUNK or (MAX_ROWS and n_samples + len(batch) >= MAX_ROWS):
                n_samples += _accumulate(np.vstack(batch), order, inv, starts, mask3, hist, pooled_iso)
                batch = []
                print(f"{n_samples} samples", end="", file=sys.stderr)
                if MAX_ROWS and n_samples >= MAX_ROWS:
                    break
        if batch:
            n_samples += _accumulate(np.vstack(batch), order, inv, starts, mask3, hist, pooled_iso)
    print(file=sys.stderr)

    entries = {}
    for mir, i in idx.items():
        n_expr = int(hist[i].sum())
        cols = np.flatnonzero(col_mir == i)
        pooled_tot = pooled_iso[cols].sum()
        if n_expr == 0 or pooled_tot == 0:
            continue
        cols3 = cols[col_3p[cols]]
        top = sorted(((pooled_iso[c] / pooled_tot, header[c].split(":")[0], labels.get(header[c], ""))
                      for c in cols3), reverse=True)[:3]
        entries[mir] = {
            "median_3prime_fraction": round(quantile(hist[i], 0.5), 3),
            "iqr_3prime_fraction": [round(quantile(hist[i], 0.25), 3), round(quantile(hist[i], 0.75), 3)],
            "pooled_3prime_fraction": round(float(pooled_iso[cols3].sum() / pooled_tot), 3),
            "n_samples_expressed": n_expr,
            "top_3prime_variants": [
                {"sequence_dna": s, "label": lab, "pooled_share": round(float(sh), 3)} for sh, s, lab in top
            ],
        }

    OUT.write_text(json.dumps({
        "_metadata": {
            "description": (
                "Per-miRNA share of reads from 3'-end isoforms (templated 3' extension/"
                "trimming and non-templated additions). The stem-loop RT primer pairs with the "
                "miRNA 3'-terminal 5–7 nt, so these isoforms are captured poorly."
            ),
            "version": "2.0.0",
            "built": date.today().isoformat(),
            "source": {
                "name": "isomiRdb",
                "citation": "Aparicio-Puerta E, et al. isomiRdb: microRNA expression at isoform "
                            "resolution. Nucleic Acids Res 2023;51(D1):D179-D185.",
                "pmid": "36243964",
                "doi": "10.1093/nar/gkac884",
                "files": ["isomirs.tsv.gz", "isomiR_RPM.tsv.gz"],
                "url": "https://ccb-compute.cs.uni-saarland.de/isomirdb/downloads",
            },
            "method": {
                "three_prime_labels": list(THREE_PRIME_TAGS),
                "expressed_threshold_rpm": MIN_RPM,
                "samples_processed": n_samples,
                "isomirs_in_matrix": len(header),
                "isomirs_without_label": unlabeled,
                "note": "isomiRdb's matrix holds only isomiRs >1 RPM in ≥1 % of samples; "
                        "rarer isoforms (of any type) are not counted.",
            },
            "species": "Homo sapiens only (isomiRdb is human). No data for mouse/rat.",
            "coverage_warning": "Human miRNAs in isomiRdb only. Absence of an entry means "
                                "no data, not absence of 3' isomiRs.",
        },
        **entries,
    }, indent=1), encoding="utf-8")
    print(f"wrote {len(entries)} miRNAs from {n_samples} samples -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        MAX_ROWS = int(sys.argv[2])
    main(Path(sys.argv[1]))
