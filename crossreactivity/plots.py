"""
plots.py — family heatmaps and the R distribution of the cross-reactivity matrix.

Usage (repo root, after build_matrix):
    python -m crossreactivity.plots
Writes outputs/figures/heatmap_<family>.{png,svg} and outputs/figures/r_histogram.{png,svg}.

Heatmap: rows = assay (primer set #1 of that miRNA), columns = the miRNA it is read
against; one-hue sequential scale on log10 R (0.1 % … 100 %); NONE pairs (< 0.1 %)
are left blank and marked "·". The matrix is asymmetric, so read along rows.
"""

from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402

from crossreactivity.api import CrossReactivity  # noqa: E402

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(_ROOT, "outputs")

FAMILIES = {
    "let-7_miR-98": ["hsa-let-7a-5p", "hsa-let-7b-5p", "hsa-let-7c-5p", "hsa-let-7d-5p",
                     "hsa-let-7e-5p", "hsa-let-7f-5p", "hsa-let-7g-5p", "hsa-let-7i-5p",
                     "hsa-miR-98-5p"],
    "miR-200": ["hsa-miR-200a-3p", "hsa-miR-141-3p", "hsa-miR-200b-3p", "hsa-miR-200c-3p",
                "hsa-miR-429"],
    "miR-17-92": ["hsa-miR-17-5p", "hsa-miR-20a-5p", "hsa-miR-20b-5p", "hsa-miR-106a-5p",
                  "hsa-miR-106b-5p", "hsa-miR-93-5p"],
    "miR-30": ["hsa-miR-30a-5p", "hsa-miR-30b-5p", "hsa-miR-30c-5p", "hsa-miR-30d-5p",
               "hsa-miR-30e-5p"],
    "miR-29": ["hsa-miR-29a-3p", "hsa-miR-29b-3p", "hsa-miR-29c-3p"],
    "miR-181": ["hsa-miR-181a-5p", "hsa-miR-181b-5p", "hsa-miR-181c-5p", "hsa-miR-181d-5p"],
}

# One-hue sequential ramp (light → dark blue), reference palette steps 100–700.
_SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("seq_blue", _SEQ)
INK, INK_MUTED, GRID = "#1f1f1d", "#6b6b66", "#e4e3df"
R_MIN = 1e-3     # NONE cut-off: ΔCq ≥ 10 ⇔ R < 2^-10 ≈ 0.001


def _style(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=INK_MUTED, length=0, labelsize=9)


def _pct(r: float) -> str:
    p = 100 * r
    return f"{p:.0f}" if p >= 10 else (f"{p:.1f}" if p >= 1 else f"{p:.2f}")


def heatmap(xr: CrossReactivity, name: str, members: list[str], out_dir: str) -> list[str]:
    m = xr.submatrix(members)
    labels = [s.replace("hsa-", "") for s in members]
    vals = m.to_numpy()
    shown = np.where(vals >= R_MIN, vals, np.nan)

    n = len(members)
    fig, ax = plt.subplots(figsize=(1.0 + 0.62 * n, 0.8 + 0.55 * n), dpi=200)
    im = ax.imshow(shown, cmap=CMAP, norm=LogNorm(vmin=R_MIN, vmax=1.0))
    ax.set_xticks(range(n), labels, rotation=45, ha="right")
    ax.set_yticks(range(n), labels)
    ax.set_xlabel("miRNA measured (target)", color=INK_MUTED, fontsize=9)
    ax.set_ylabel("assay designed for", color=INK_MUTED, fontsize=9)
    # 2 px surface gap between cells
    ax.set_xticks(np.arange(-.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-.5, n, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    _style(ax)
    for i in range(n):
        for j in range(n):
            v = vals[i, j]
            if np.isnan(v):
                txt, col = "n/a", INK_MUTED
            elif v < R_MIN:
                txt, col = "·", INK_MUTED
            else:
                txt = _pct(v)
                col = "white" if v >= 0.03 else INK
            ax.text(j, i, txt, ha="center", va="center", fontsize=7.5, color=col)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("R = cross-signal vs own target (log scale)", color=INK_MUTED, fontsize=8)
    cb.set_ticks([1e-3, 1e-2, 1e-1, 1], labels=["0.1 %", "1 %", "10 %", "100 %"])
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=INK_MUTED, labelsize=8, length=0)
    ax.set_title(f"{name.replace('_', ' / ')} — assay cross-reactivity R(i, j) in %",
                 color=INK, fontsize=10, loc="left")
    fig.tight_layout()
    paths = []
    for ext in ("png", "svg"):
        p = os.path.join(out_dir, f"heatmap_{name}.{ext}")
        fig.savefig(p, facecolor="white")
        paths.append(p)
    plt.close(fig)
    return paths


def r_histogram(xr: CrossReactivity, meta: dict, out_dir: str) -> list[str]:
    off = xr.long[xr.long["assay_mirna"] != xr.long["target_mirna"]]
    r = off["R"].to_numpy()
    n_none = meta.get("pairs_by_level", {}).get("NONE")
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=200)
    bins = np.logspace(-3, 0, 31)
    ax.hist(r, bins=bins, color="#2a78d6", edgecolor="white", linewidth=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    top = ax.get_ylim()[1]
    # Labels at two heights, each on the outer side of its line, so they never collide.
    for x, lab, y, ha in ((2 ** -4.3, "PARTIAL ≥ 5 % ", top, "right"),
                          (2 ** -3.3, " CO-AMPLIFIED > 10 %", top / 6, "left")):
        ax.axvline(x, color=INK_MUTED, linewidth=1, linestyle=(0, (3, 3)))
        ax.text(x, y, lab, color=INK_MUTED, fontsize=8, va="top", ha=ha)
    # The spike just above 0.3 %: RT captures the miRNA, the forward primer does not —
    # ΔCq_FWD is capped at 8.3 ("no amplification", Stadhouders 2010) → R = 2^-8.3.
    cap = 2 ** -8.3
    ax.annotate("forward-axis cap\n(RT captures, forward fails)", xy=(cap * 1.08, top / 6),
                xytext=(cap * 1.6, top / 40), color=INK_MUTED, fontsize=7.5, ha="left",
                arrowprops={"arrowstyle": "-", "color": INK_MUTED, "linewidth": 0.8})
    ax.set_xticks([1e-3, 1e-2, 1e-1, 1], ["0.1 %", "1 %", "10 %", "100 %"])
    ax.set_xlabel("R (off-diagonal pairs above the NONE level)", color=INK_MUTED, fontsize=9)
    ax.set_ylabel("pairs (log scale)", color=INK_MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _style(ax)
    sub = f"{len(r):,} off-diagonal pairs with R ≥ 0.1 %"
    if n_none is not None:
        sub += f"; {n_none:,} pairs below 0.1 % (NONE) not shown"
    ax.set_title(f"Distribution of R over the {meta.get('species', '')} matrix\n{sub}",
                 color=INK, fontsize=10, loc="left")
    fig.tight_layout()
    paths = []
    for ext in ("png", "svg"):
        p = os.path.join(out_dir, f"r_histogram.{ext}")
        fig.savefig(p, facecolor="white")
        paths.append(p)
    plt.close(fig)
    return paths


def main() -> int:
    xr = CrossReactivity.load(os.path.join(OUT, "crossreactivity_long.parquet"))
    meta = xr.metadata
    fig_dir = os.path.join(OUT, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    for name, members in FAMILIES.items():
        heatmap(xr, name, members, fig_dir)
    r_histogram(xr, meta, fig_dir)
    print(f"figures written to {fig_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
