"""
Build data/known_3prime_isomir_mirnas.json from isomiRdb (audit SCI-10, SCI-11).

Source: Aparicio-Puerta E, et al. isomiRdb: microRNA expression at isoform
resolution. Nucleic Acids Res 2023;51(D1):D179-D185. PMID 36243964,
doi:10.1093/nar/gkac884. https://ccb-compute.cs.uni-saarland.de/isomirdb/downloads

Inputs (download from the page above, keep gzipped, same directory):
  isomirs.tsv.gz      — isomiR repertoire: "sequence:matureName", isoLabel
  isomiR_RPM.tsv.gz   — isomiR RPM matrix, rows = samples, cols = 90,481 isomiRs
  miRNA_RPM.tsv.gz    — per-miRNA RPM, rows = 2,655 miRNAs, cols = 42,494 samples
  metadata.tsv.gz     — sample annotation (tissue), used to report composition

Per mature human miRNA:
  3' fraction  = RPM of isoforms whose 3' end differs from the canonical
                 (isoLabel contains lv3p / mlv3p / nta) ÷ RPM of all its isoforms;
                 median + IQR over samples where the miRNA is expressed (≥ MIN_RPM).
                 Why 3' only: the stem-loop RT primer pairs with the miRNA 3'-terminal
                 5–7 nt, so 3'-end variants are captured poorly (Nejad 2018, PMID 29263133).
  abundance    = median RPM over ALL samples (miRNA_RPM) and its percentile rank
                 among all miRNAs — used for the contamination-risk flag.

The isomiR matrix download is cut by the server at ~1 GB (≈20.6k of 42.5k samples,
tested 4 times). Reading stops cleanly at the truncation and the sample count and
tissue composition actually used are written into the output metadata.

Usage (from backend/):
  python scripts/build_isomir_3prime_index.py <dir-with-the-files> [max_rows]
"""
import collections
import csv
import gzip
import json
import sys
import zlib
from datetime import date
from pathlib import Path

import numpy as np

MIN_RPM = 10.0        # a miRNA counts as expressed in a sample at ≥ 10 RPM
BINS = 200            # histogram resolution for the 3' fraction (0.5 % steps)
CHUNK = 256           # sample rows per block
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
    return (int(np.searchsorted(c, q * c[-1])) + 0.5) / BINS


def _rows(path: Path, max_rows: int | None):
    """Yield (row_id, float32 values) per complete line; stop cleanly at a truncated end."""
    with gzip.open(path, "rt") as f:
        next(f)
        n = 0
        try:
            for line in f:
                if not line.endswith("\n"):
                    return                                   # partial last line
                tab = line.index("\t")
                # "NA" = not detected in that sample → 0 RPM.
                vals = np.fromstring(line[tab + 1:].replace("NA", "0"), sep="\t", dtype=np.float32)
                yield line[:tab], vals
                n += 1
                if max_rows and n >= max_rows:
                    return
        except (EOFError, zlib.error, OSError):
            return                                           # truncated download


def abundance(src: Path) -> dict:
    """{miRNA: (median RPM over all samples, percentile rank among miRNAs)}."""
    med = {name: float(np.median(v)) for name, v in _rows(src / "miRNA_RPM.tsv.gz", None)}
    names = list(med)
    ranks = np.argsort(np.argsort([med[n] for n in names], kind="stable"), kind="stable")
    return {n: (med[n], 100.0 * (r + 1) / len(names)) for n, r in zip(names, ranks)}


def three_prime(src: Path, labels: dict, max_rows: int | None):
    """Per-miRNA 3'-fraction histograms + pooled isoform RPM, and the sample ids used."""
    with gzip.open(src / "isomiR_RPM.tsv.gz", "rt") as f:
        header = [h.strip('"') for h in f.readline().rstrip("\n").split("\t")[1:]]
    names = [h.split(":", 1)[1] for h in header]
    mirnas = sorted(set(names))
    idx = {m: i for i, m in enumerate(mirnas)}
    col_mir = np.array([idx[n] for n in names])
    col_3p = np.array([is_3prime(labels.get(h, "")) for h in header])

    order = np.argsort(col_mir, kind="stable")              # group columns by miRNA
    inv = np.argsort(order)
    starts = np.r_[0, np.flatnonzero(np.diff(col_mir[order])) + 1]
    mask3 = col_3p[order].astype(np.float32)
    hist = np.zeros((len(mirnas), BINS), dtype=np.int64)
    pooled = np.zeros(len(header), dtype=np.float64)
    used = []

    def add(block):
        m = np.nan_to_num(np.vstack(block)[:, order], copy=False)
        pooled[:] += m.sum(axis=0, dtype=np.float64)[inv]
        tot = np.add.reduceat(m, starts, axis=1)
        t3 = np.add.reduceat(m * mask3, starts, axis=1)
        ok = tot >= MIN_RPM
        frac = np.divide(t3, tot, out=np.zeros_like(t3), where=ok)
        b = np.minimum((frac * BINS).astype(np.int64), BINS - 1)
        r, c = np.nonzero(ok)
        np.add.at(hist, (c, b[r, c]), 1)

    block = []
    for sid, vals in _rows(src / "isomiR_RPM.tsv.gz", max_rows):
        if vals.size != len(header):
            break                                           # corrupt row at the cut
        block.append(vals)
        used.append(sid)
        if len(block) == CHUNK:
            add(block)
            block = []
            if len(used) % (CHUNK * 20) == 0:
                print(f"{len(used)} samples", file=sys.stderr)
    if block:
        add(block)
    return header, labels, idx, col_mir, col_3p, hist, pooled, used


def composition(src: Path, sample_ids: list[str]) -> dict:
    tissue = {}
    with gzip.open(src / "metadata.tsv.gz", "rt") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tissue[row["id"]] = row.get("isomiRdb_tissue") or "unknown"
    total = collections.Counter(tissue.values())
    used = collections.Counter(tissue.get(s, "unknown") for s in sample_ids)
    return {t: {"used": used.get(t, 0), "available": n} for t, n in total.most_common(15)}


def main(src: Path, max_rows: int | None = None) -> None:
    labels = load_labels(src / "isomirs.tsv.gz")
    header, labels, idx, col_mir, col_3p, hist, pooled, used = three_prime(src, labels, max_rows)
    abund = abundance(src)

    entries = {}
    for mir, (med_rpm, pct) in abund.items():
        e = {"median_total_rpm": round(med_rpm, 1), "abundance_percentile": round(pct, 1)}
        i = idx.get(mir)
        if i is not None and hist[i].sum() > 0:
            cols = np.flatnonzero(col_mir == i)
            cols3 = cols[col_3p[cols]]
            tot = pooled[cols].sum()
            top = sorted(((pooled[c] / tot, header[c].split(":")[0], labels.get(header[c], ""))
                          for c in cols3), reverse=True)[:3]
            e.update({
                "median_3prime_fraction": round(quantile(hist[i], 0.5), 3),
                "iqr_3prime_fraction": [round(quantile(hist[i], 0.25), 3),
                                        round(quantile(hist[i], 0.75), 3)],
                "pooled_3prime_fraction": round(float(pooled[cols3].sum() / tot), 3),
                "n_samples_expressed": int(hist[i].sum()),
                "top_3prime_variants": [{"sequence_dna": s, "label": lab, "pooled_share": round(float(sh), 3)}
                                        for sh, s, lab in top],
            })
        entries[mir] = e

    n_3p = sum(1 for e in entries.values() if "median_3prime_fraction" in e)
    OUT.write_text(json.dumps({
        "_metadata": {
            "description": (
                "Per-miRNA share of reads from 3'-end isoforms (stem-loop RT captures these "
                "poorly) and per-miRNA abundance (contamination-risk flag)."
            ),
            "version": "2.0.0",
            "built": date.today().isoformat(),
            "source": {
                "name": "isomiRdb",
                "citation": "Aparicio-Puerta E, et al. isomiRdb: microRNA expression at isoform "
                            "resolution. Nucleic Acids Res 2023;51(D1):D179-D185.",
                "pmid": "36243964",
                "doi": "10.1093/nar/gkac884",
                "url": "https://ccb-compute.cs.uni-saarland.de/isomirdb/downloads",
            },
            "method": {
                "three_prime_labels": list(THREE_PRIME_TAGS),
                "expressed_threshold_rpm": MIN_RPM,
                "three_prime_samples_used": len(used),
                "three_prime_samples_note": (
                    "isomiR_RPM.tsv.gz is cut by the server at ~1 GB; the 3' fractions use the "
                    "complete rows before the cut. Body fluids (serum, plasma, blood) are "
                    "under-represented — see sample_composition."
                ),
                "sample_composition": composition(src, used),
                "abundance": "median RPM over all samples of miRNA_RPM.tsv.gz (complete, "
                             f"{len(abund)} miRNAs); percentile = rank among them.",
                "note": "isomiRdb's isomiR matrix holds only isomiRs >1 RPM in ≥1 % of samples.",
            },
            "species": "Homo sapiens only (isomiRdb is human). No data for mouse/rat.",
            "coverage_warning": "Human miRNAs in isomiRdb only. Absence of an entry means "
                                "no data, not absence of 3' isomiRs.",
        },
        **entries,
    }, indent=1), encoding="utf-8")
    print(f"wrote {len(entries)} miRNAs ({n_3p} with 3' data from {len(used)} samples) -> {OUT}",
          file=sys.stderr)


if __name__ == "__main__":
    main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else None)
