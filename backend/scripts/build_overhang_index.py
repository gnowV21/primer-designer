#!/usr/bin/env python3
"""
build_overhang_index.py — build backend/data/mirbase_overhang_index.json (SPEC_week2 C3).

A FULL per-species mature-miRNA index used for primer-axis collision analysis
(overhang_collision.py). This is NOT a family/seed grouping: it stores every mature
sequence so the RT 3'-overhang and forward 5'-prefix buckets can be built in memory at
load time (one source of truth). Reuses parse_mature_fa() from build_mirbase_data.py.

Usage (from backend/ directory):
    python scripts/build_overhang_index.py                         # hsa,mmu,rno (cached)
    python scripts/build_overhang_index.py --species hsa --no-download
    python scripts/build_overhang_index.py --out data/custom.json
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, timezone
from pathlib import Path

# Support both `python scripts/build_overhang_index.py` and `from scripts.build_overhang_index import ...`
try:  # package import (tests / from backend root)
    from scripts.build_mirbase_data import (
        parse_mature_fa, _parse_species_arg, _download, CACHE_DIR, MATURE_FA_URL,
    )
except ImportError:  # standalone (cwd inside scripts/)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_mirbase_data import (
        parse_mature_fa, _parse_species_arg, _download, CACHE_DIR, MATURE_FA_URL,
    )

_SCRIPTS_DIR = Path(__file__).parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
OUTPUT_PATH = _BACKEND_DIR / "data" / "mirbase_overhang_index.json"

OVERHANG_NT = 6          # Chen 2005 stem-loop RT binding length
SEED_START, SEED_END = 1, 8   # seed positions 2-8 (0-indexed slice), for context only


def _dna(rna: str) -> str:
    return rna.upper().replace("U", "T")


def build_index(mature_by_name: dict, species_list: list[str]) -> dict:
    """Split a {name: RNA} map into per-species mature dicts, keyed by species prefix."""
    mature = {sp: {} for sp in species_list}
    for name, seq in mature_by_name.items():
        prefix = name.split("-", 1)[0]
        if prefix in mature:
            mature[prefix][name] = seq.upper()
    return mature


def _bucket_report(mature_species: dict) -> dict:
    """RT 3'-overhang bucket stats for one species (evidence for the seed-vs-3' gap)."""
    buckets = defaultdict(list)
    for name, seq in mature_species.items():
        if len(seq) >= OVERHANG_NT:
            buckets[_dna(seq[-OVERHANG_NT:])].append((name, seq))
    if not buckets:
        return {"n_buckets": 0, "largest": None}
    key, members = max(buckets.items(), key=lambda kv: len(kv[1]))
    distinct_seeds = {s[SEED_START:SEED_END] for _, s in members}
    return {
        "n_buckets": len(buckets),
        "largest_key": key,
        "largest_size": len(members),
        "largest_distinct_seeds": len(distinct_seeds),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build mirbase_overhang_index.json from miRBase mature.fa.")
    ap.add_argument("--species", default="hsa,mmu,rno",
                    help="comma-separated miRBase prefixes (default: hsa,mmu,rno)")
    ap.add_argument("--no-download", action="store_true", help="Use cached mature.fa only")
    ap.add_argument("--out", default=str(OUTPUT_PATH))
    args = ap.parse_args()

    prefixes = _parse_species_arg(args.species) or []
    cached_txt = CACHE_DIR / "mature.fa"
    cached_gz = CACHE_DIR / "mature.fa.gz"

    if args.no_download:
        mature_path = cached_txt if cached_txt.exists() else cached_gz
        if not mature_path.exists():
            print(f"ERROR: no cached file found in {CACHE_DIR}", file=sys.stderr)
            sys.exit(1)
        print(f"  [cached]  {mature_path.name}")
    else:
        print("Step 1/2: Download mature.fa")
        mature_path = _download(MATURE_FA_URL, cached_gz)

    print(f"Step 2/2: Parse mature.fa  (species={args.species})")
    mature_by_name = parse_mature_fa(mature_path, args.species)
    mature = build_index(mature_by_name, prefixes)

    n_mirnas = {sp: len(m) for sp, m in mature.items()}
    out = {
        "_metadata": {
            "description": (
                "Full per-species mature miRNA index for primer-axis collision analysis "
                "(RT 3' overhang and forward 5' prefix). NOT a family/seed grouping."
            ),
            "source": "miRBase CURRENT - https://mirbase.org/download/mature.fa",
            "mirbase_release": "unknown",
            "build_date": date.today().isoformat(),
            "species": prefixes,
            "n_mirnas": n_mirnas,
            "axes": {
                "rt": "mature[-6:] (RNA). RT primer 3' segment = revcomp(dna(window)).",
                "fwd": "mature[0:L] (RNA), L = forward primer specific_length, resolved at runtime.",
            },
            "provenance": "generated",
            "warning": "Re-run scripts/build_overhang_index.py after every miRBase release update.",
        },
        "mature": mature,
    }

    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # Summary — the largest RT-collision bucket is direct evidence for the seed-vs-3' gap.
    print(f"\nWrote {args.out}")
    for sp in prefixes:
        rep = _bucket_report(mature[sp])
        print(f"  {sp}: {n_mirnas[sp]} mature | {rep.get('n_buckets', 0)} 3'-6mer buckets")
        if rep.get("largest_key"):
            print(f"      largest RT-collision bucket: {rep['largest_key']} with "
                  f"{rep['largest_size']} members across {rep['largest_distinct_seeds']} distinct seeds")


if __name__ == "__main__":
    main()
