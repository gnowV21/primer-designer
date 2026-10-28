#!/usr/bin/env python3
"""
build_overhang_index.py — build backend/data/mirbase_overhang_index.json (SPEC_week2 C3).

A FULL per-species mature-miRNA index used for primer-axis collision analysis
(overhang_collision.py). This is NOT a family/seed grouping: it stores every mature
sequence so the RT 3'-overhang and forward 5'-prefix buckets can be built in memory at
load time (one source of truth). Reuses parse_mature_fa() from build_mirbase_data.py.

Source: the SAME cached mature.fa the BLAST DB was built from (miRBase 22.1,
48,885 mature, 271 species — see data/blast_db/metadata.json), so the assay-level
screen and the BLAST search never disagree about which miRNAs exist. The build
refuses to run if the sequence count differs from the BLAST DB's.

Usage (from backend/ directory):
    python scripts/build_overhang_index.py                         # all species, cached 22.1
    python scripts/build_overhang_index.py --species hsa,mmu
    python scripts/build_overhang_index.py --out data/custom.json
"""

import argparse
import hashlib
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


def build_index(mature_by_name: dict, species_list: list[str] | None) -> dict:
    """Split a {name: RNA} map into per-species mature dicts, keyed by species prefix.
    species_list None = every prefix present."""
    if species_list is None:
        species_list = sorted({name.split("-", 1)[0] for name in mature_by_name})
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
    ap.add_argument("--species", default="all",
                    help="comma-separated miRBase prefixes, or 'all' (default)")
    ap.add_argument("--download-current", action="store_true",
                    help="Fetch miRBase CURRENT instead of the cached release the BLAST DB "
                         "uses (only for a deliberate release upgrade — rebuild BLAST too)")
    ap.add_argument("--out", default=str(OUTPUT_PATH))
    args = ap.parse_args()

    cached_txt = CACHE_DIR / "mature.fa"
    cached_gz = CACHE_DIR / "mature.fa.gz"

    if args.download_current:
        print("Step 1/2: Download mature.fa (miRBase CURRENT)")
        mature_path = _download(MATURE_FA_URL, cached_gz)
    else:
        mature_path = cached_txt if cached_txt.exists() else cached_gz
        if not mature_path.exists():
            print(f"ERROR: no cached file found in {CACHE_DIR}", file=sys.stderr)
            sys.exit(1)
        print(f"  [cached]  {mature_path.name}")

    print(f"Step 2/2: Parse mature.fa  (species={args.species})")
    mature_by_name = parse_mature_fa(mature_path, args.species)
    blast_meta = _blast_db_metadata()
    if args.species == "all" and not args.download_current:
        expected = (blast_meta.get("sequences_count") or {}).get("mirbase_multi")
        if expected and expected != len(mature_by_name):
            print(f"ERROR: mature.fa has {len(mature_by_name)} entries, the BLAST DB "
                  f"{expected} — not the same release; rebuild both together.", file=sys.stderr)
            sys.exit(1)
    mature = build_index(mature_by_name, _parse_species_arg(args.species))
    prefixes = sorted(mature)

    n_mirnas = {sp: len(m) for sp, m in mature.items()}
    out = {
        "_metadata": {
            "description": (
                "Full per-species mature miRNA index for primer-axis collision analysis "
                "(RT 3' overhang and forward 5' prefix). NOT a family/seed grouping."
            ),
            "source": f"miRBase mature.fa ({mature_path.name}, the file the BLAST DB was built from)",
            "mirbase_release": ("CURRENT (downloaded)" if args.download_current
                                else blast_meta.get("mirbase_version", "unknown")),
            "mature_fa_sha256": hashlib.sha256(mature_path.read_bytes()).hexdigest(),
            "build_date": date.today().isoformat(),
            "species": prefixes,
            "n_total": sum(n_mirnas.values()),
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
    print(f"\nWrote {args.out}  ({len(prefixes)} species, {sum(n_mirnas.values())} mature)")
    for sp in [p for p in ("hsa", "mmu", "rno") if p in mature]:
        rep = _bucket_report(mature[sp])
        print(f"  {sp}: {n_mirnas[sp]} mature | {rep.get('n_buckets', 0)} 3'-6mer buckets")
        if rep.get("largest_key"):
            print(f"      largest RT-collision bucket: {rep['largest_key']} with "
                  f"{rep['largest_size']} members across {rep['largest_distinct_seeds']} distinct seeds")


def _blast_db_metadata() -> dict:
    path = _BACKEND_DIR / "data" / "blast_db" / "metadata.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    main()
