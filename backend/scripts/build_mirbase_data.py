#!/usr/bin/env python3
"""
build_mirbase_data.py — One-time script to build backend/data/mirbase_family_overhangs.json
from miRBase CURRENT release (https://mirbase.org/download/mature.fa).

Note: miFam.dat was removed from miRBase CURRENT. This script uses seed-based
family grouping (positions 2-8, 1-indexed), which is the canonical functional
definition of miRNA families used in the literature.

Seed grouping:
  - miRNAs with identical seed (pos 2-8) belong to the same family.
  - Members of the same family share the seed but differ in 3' end —
    exactly the region the stemloop RT primer overhang must discriminate.
  - This covers let-7, miR-17 cluster members (those with same seed),
    miR-200/141/429, etc.

Output JSON format:
  {
    "_metadata":       {...},
    "_mirna_to_family": {"hsa-let-7a-5p": "let-7", ...},   ← O(1) lookup index
    "let-7":           {"hsa-let-7a-5p": "UGAGGU...", ...}, ← family members
    "miR-200":         {...},
    ...
  }

Usage (from backend/ directory):
    python scripts/build_mirbase_data.py               # human (hsa), default
    python scripts/build_mirbase_data.py --species mmu # mouse
    python scripts/build_mirbase_data.py --species all # all species
    python scripts/build_mirbase_data.py --no-download # use cached mature.fa
"""

import argparse
import gzip
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

MATURE_FA_URL = "https://mirbase.org/download/mature.fa"

_SCRIPTS_DIR = Path(__file__).parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
OUTPUT_PATH  = _BACKEND_DIR / "data" / "mirbase_family_overhangs.json"
CACHE_DIR    = _SCRIPTS_DIR / ".mirbase_cache"

# Seed positions (0-indexed: slice [1:8] gives positions 2-8, 1-indexed)
SEED_START = 1   # inclusive, 0-indexed
SEED_END   = 8   # exclusive, 0-indexed -> 7 nt seed
# A family must have >= 2 members to be included (singletons have no cross-reactivity)
MIN_FAMILY_MEMBERS = 2


# ── Download ──────────────────────────────────────────────────────


def _download(url: str, dest: Path, force: bool = False) -> Path:
    if dest.exists() and not force:
        size_kb = dest.stat().st_size // 1024
        print(f"  [cached]  {dest.name}  ({size_kb} KB)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {url} ...")
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    size_kb = dest.stat().st_size // 1024
    print(f"  Done -> {dest.name}  ({size_kb} KB)")
    return dest


# ── Parser ────────────────────────────────────────────────────────


def parse_mature_fa(path: Path, species: str) -> dict[str, str]:
    """
    Parse mature.fa (plain text or .gz) -> {miRNA_name: RNA_sequence}.

    Filters by species prefix (e.g. "hsa" for human, "all" for no filter).
    Header format: >hsa-miR-21-5p MIMAT0000076 Homo sapiens miR-21-5p
    """
    seqs: dict[str, str] = {}
    current_name: str | None = None

    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                name = line[1:].split()[0]
                keep = (species == "all") or name.startswith(f"{species}-")
                current_name = name if keep else None
            elif current_name:
                seqs[current_name] = line.upper()
                current_name = None

    return seqs


# ── Family name derivation ────────────────────────────────────────


def _derive_family_label(seed: str, member_names: list[str]) -> str:
    """
    Derive a human-readable family label from the member names in a seed group.

    Strategy: majority-vote on name prefix.
      1. Strip species prefix (hsa-, mmu-, etc.) and arm suffix (-5p, -3p).
      2. For each pair of stripped names, compute their common prefix.
      3. Pick the prefix that covers the MOST members (majority vote).
      4. Fall back to 'seed_{seed}' if no majority prefix is long enough.

    Examples:
      let-7 group (let-7a..i + miR-98 + miR-4458):
        majority prefix among let-7 members = "let-7"  (9 of 11 agree)
      miR-200 group (miR-200a, miR-200b, miR-141):
        longest prefix covering miR-200a and miR-200b = "miR-200"  (2 of 3)
      miR-21 group (miR-21-5p, miR-590-5p):
        no common prefix longer than "miR-" -> seed fallback
    """
    stripped = []
    for n in member_names:
        s = re.sub(r'^[a-z]{2,4}-', '', n)  # strip species prefix
        s = re.sub(r'-(5p|3p)$', '', s)      # strip arm suffix
        stripped.append(s)

    if not stripped:
        return f"seed_{seed}"

    # Build candidate prefixes: common prefix of every pair (i, j)
    prefix_votes: dict[str, int] = {}
    for i, a in enumerate(stripped):
        for b in stripped[i + 1:]:
            # common prefix of a and b
            common = ""
            for ca, cb in zip(a, b):
                if ca == cb:
                    common += ca
                else:
                    break
            common = common.rstrip('-.')
            if len(common) > 3:  # ignore trivially short prefixes
                prefix_votes[common] = prefix_votes.get(common, 0) + 1

    if not prefix_votes:
        return f"seed_{seed}"

    # Pick the prefix with the most votes; on tie prefer longer prefix
    best = max(prefix_votes, key=lambda p: (prefix_votes[p], len(p)))

    # Count how many members share this prefix (coverage check)
    coverage = sum(1 for s in stripped if s.startswith(best))
    if coverage < 2:
        return f"seed_{seed}"

    return best


# ── Family DB builder ─────────────────────────────────────────────


def build_family_db(mature_seqs: dict[str, str], species: str) -> dict:
    """
    Build family -> {mature_name: sequence} using seed sequence grouping.

    Groups miRNAs by their seed (positions 2-8, 1-indexed).
    Assigns a human-readable family label from common name prefix.
    Families with < MIN_FAMILY_MEMBERS members are excluded.
    """
    # Group by seed sequence
    seed_groups: dict[str, list[str]] = defaultdict(list)
    skipped_short = 0
    for name, seq in mature_seqs.items():
        if len(seq) < SEED_END:
            skipped_short += 1
            continue
        seed = seq[SEED_START:SEED_END]
        seed_groups[seed].append(name)

    if skipped_short:
        print(f"  Skipped {skipped_short} sequences too short for seed extraction (<{SEED_END} nt)")

    # Build output structures
    family_members: dict[str, dict[str, str]] = {}
    mirna_to_family: dict[str, str]            = {}
    singleton_count = 0

    for seed, members in seed_groups.items():
        if len(members) < MIN_FAMILY_MEMBERS:
            singleton_count += 1
            continue

        label = _derive_family_label(seed, members)

        # Avoid label collisions: if label already exists, append seed suffix
        final_label = label
        collision_n = 1
        while final_label in family_members:
            collision_n += 1
            final_label = f"{label}_{seed}"

        family_members[final_label] = {n: mature_seqs[n] for n in members}
        for n in members:
            mirna_to_family[n] = final_label

    n_families = len(family_members)
    n_indexed  = len(mirna_to_family)
    print(f"  Seed groups total:     {len(seed_groups)}")
    print(f"  Singletons (excluded): {singleton_count}")
    print(f"  Families (>=2 members): {n_families}  covering {n_indexed} miRNAs")

    species_note = (
        f"human ({species})" if species in ("hsa",)
        else f"mouse ({species})" if species == "mmu"
        else species if species != "all"
        else "all species"
    )

    return {
        "_metadata": {
            "description": (
                f"Mature miRNA family sequences ({species_note}) built from miRBase CURRENT. "
                "Family grouping by seed sequence (positions 2-8, canonical functional definition)."
            ),
            "warning": (
                "Generated by scripts/build_mirbase_data.py from miRBase CURRENT. "
                "Re-run after each miRBase release update."
            ),
            "species": species,
            "source": "miRBase — https://mirbase.org",
            "family_grouping": (
                "Seed sequence positions 2-8 (canonical miRNA family definition). "
                "Members sharing the same seed are cross-reactivity candidates for "
                "the stemloop RT primer overhang region."
            ),
            "n_families": n_families,
            "n_mirnas_indexed": n_indexed,
            "seed_positions": "2-8 (1-indexed), i.e. seq[1:8] in Python",
            "min_family_size": MIN_FAMILY_MEMBERS,
        },
        "_mirna_to_family": mirna_to_family,
        **family_members,
    }


# ── Main ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build mirbase_family_overhangs.json from miRBase mature.fa."
    )
    parser.add_argument(
        "--species", default="hsa",
        help="Species prefix to include (default: hsa; 'all' for all species)",
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Use cached mature.fa only — skip download",
    )
    parser.add_argument(
        "--force-download", action="store_true",
        help="Re-download even if cached file exists",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("miRBase family data builder  (seed-based grouping)")
    print(f"  Species:  {args.species}")
    print(f"  Output:   {OUTPUT_PATH}")
    print("=" * 60)

    # ── Download / cache ─────────────────────────────────────────
    cached_gz  = CACHE_DIR / "mature.fa.gz"
    cached_txt = CACHE_DIR / "mature.fa"

    if args.no_download:
        mature_path = cached_gz if cached_gz.exists() else cached_txt
        if not mature_path.exists():
            print(f"ERROR: no cached file found in {CACHE_DIR}", file=sys.stderr)
            sys.exit(1)
        print(f"  [--no-download] Using cached: {mature_path.name}")
    else:
        print("Step 1/3: Download mature.fa")
        # Try .gz first, fall back to plain text
        try:
            mature_path = _download(MATURE_FA_URL + ".gz", cached_gz, force=args.force_download)
        except SystemExit:
            # .gz not available — try plain text
            mature_path = _download(MATURE_FA_URL, cached_txt, force=args.force_download)

    # ── Parse ─────────────────────────────────────────────────────
    print(f"\nStep 2/3: Parse mature.fa  (species={args.species})")
    mature_seqs = parse_mature_fa(mature_path, args.species)
    print(f"  -> {len(mature_seqs)} mature miRNAs")

    # ── Build ─────────────────────────────────────────────────────
    print("\nStep 3/3: Build family database (seed positions 2-8)")
    db = build_family_db(mature_seqs, args.species)

    # ── Write ─────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    size_kb = OUTPUT_PATH.stat().st_size // 1024

    print(f"\nOK Written -> {OUTPUT_PATH}  ({size_kb} KB)")
    print("  Re-run after each miRBase release update.")


if __name__ == "__main__":
    main()
