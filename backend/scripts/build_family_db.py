"""
build_family_db.py — Build mirbase_family_overhangs.json from miFam.dat + mature.fa

Steps:
  1. Download miFam.dat: https://www.mirbase.org/download/miFam.dat
  2. Download mature.fa multi-species
  3. Parse miFam.dat -> families with precursor IDs + names
  4. Parse mature.fa -> mature miRNA name -> sequence
  5. For each family: collect mature sequences for all members
  6. Compute 6-nt overhang (3' end) for each mature
  7. Build _mirna_to_family reverse index for O(1) lookup (fixes Limitation #4)
  8. Write mirbase_family_overhangs.json

Output JSON schema:
{
  "_meta": {"mirbase_version": "...", "build_date": "...", "family_count": N, "member_count": M},
  "_mirna_to_family": {"hsa-miR-21-5p": "mir-21", ...},
  "let-7": {
    "_overhang_nt": 6,
    "hsa-let-7a-5p": "UGAGGU",    <- 6-nt 3' overhang (RNA)
    "mmu-let-7a-5p": "UGAGGU",
    ...
  },
  ...
}

Usage:
  python scripts/build_family_db.py
  python scripts/build_family_db.py --mirbase-version 22.1
  python scripts/build_family_db.py --mifam miFam.dat --mature mature.fa --out custom_output.json
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime

MIFAM_URL  = "https://www.mirbase.org/download/miFam.dat"
MATURE_URL = "https://www.mirbase.org/download/mature.fa"

DEFAULT_OUT = os.path.join(
    os.path.dirname(__file__), "..", "data", "mirbase_family_overhangs.json"
)
OVERHANG_NT = 6  # [Chen05] stemloop RT primer binding length


# ── Parsing ───────────────────────────────────────────────────────

def parse_mifam(path: str) -> list[dict]:
    """
    Parse miFam.dat into list of families:
    [{"ac": "MIPF0000001", "id": "let-7",
      "members": [{"mi_id": "MI0000060", "name": "hsa-let-7a-1"}, ...]}, ...]
    """
    families = []
    current = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("AC"):
                current = {"ac": line.split()[-1], "id": "", "members": []}
            elif line.startswith("ID") and current is not None:
                current["id"] = line.split()[-1]
            elif line.startswith("MI") and current is not None:
                parts = line.split()
                if len(parts) >= 3:
                    current["members"].append({"mi_id": parts[1], "name": parts[2]})
            elif line.startswith("//") and current is not None:
                if current["members"]:
                    families.append(current)
                current = None
    return families


def parse_mature_fa(path: str) -> dict[str, str]:
    """
    Parse mature.fa → {name: sequence (RNA, uppercase)}.
    FASTA header: >hsa-miR-21-5p MIMAT0000076 Homo sapiens miR-21-5p
    """
    seqs = {}
    name = None
    buf  = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if name and buf:
                    seqs[name] = "".join(buf).upper()
                name = line[1:].split()[0]
                buf  = []
            elif line:
                buf.append(line)
    if name and buf:
        seqs[name] = "".join(buf).upper()
    return seqs


# ── Build JSON ────────────────────────────────────────────────────

def build_family_db(
    families: list[dict],
    mature_seqs: dict[str, str],
    overhang_nt: int = OVERHANG_NT,
    mirbase_version: str = "CURRENT",
) -> dict:
    """
    Combine miFam families + mature sequences into the output JSON structure.

    miFam.dat contains PRECURSOR IDs (e.g. hsa-let-7a-1).
    mature.fa contains MATURE names (e.g. hsa-let-7a-5p, hsa-let-7a-3p).
    We must map precursor -> mature names using name pattern matching:
      precursor "hsa-let-7a-1" -> matures "hsa-let-7a-5p", "hsa-let-7a-3p"
    Strategy: for each precursor name, find all mature names that start with
    the precursor name stripped of trailing "-1"/"-2"/"-3" suffix.
    """
    # Build prefix map: precursor base -> list of mature names
    # e.g. "hsa-let-7a" -> ["hsa-let-7a-5p", "hsa-let-7a-3p"]
    precursor_prefix_map: dict[str, list[str]] = {}
    for mature_name in mature_seqs:
        # Match species-mir-name pattern; mature always ends with -5p/-3p/-1
        # Strip -5p/-3p/-1/-2 to get common prefix with precursor
        base = re.sub(r"[-/]([35]p|[12])$", "", mature_name)
        precursor_prefix_map.setdefault(base, []).append(mature_name)

    result: dict = {}
    mirna_to_family: dict[str, str] = {}
    total_members = 0

    for fam in families:
        fam_id = fam["id"]
        fam_entry: dict = {"_overhang_nt": overhang_nt}

        for member in fam["members"]:
            precursor_name = member["name"]  # e.g. "hsa-let-7a-1"
            # Derive prefix: strip trailing -1/-2/-3 numeric suffix
            prefix = re.sub(r"-\d+$", "", precursor_name)

            # Look for mature sequences sharing this prefix
            mature_candidates = precursor_prefix_map.get(prefix, [])

            for mature_name in mature_candidates:
                seq = mature_seqs.get(mature_name, "")
                if len(seq) >= overhang_nt:
                    overhang = seq[-overhang_nt:].upper()
                    fam_entry[mature_name] = overhang
                    mirna_to_family[mature_name] = fam_id
                    total_members += 1

        if len(fam_entry) > 1:  # has at least 1 real member
            result[fam_id] = fam_entry

    result["_mirna_to_family"] = mirna_to_family
    result["_meta"] = {
        "mirbase_version": mirbase_version,
        "build_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "family_count": len(result) - 1,   # result has families + _mirna_to_family; _meta not yet added
        "member_count": total_members,
        "overhang_nt": overhang_nt,
        "source": "miFam.dat + mature.fa from miRBase",
    }

    return result


# ── Download helpers ──────────────────────────────────────────────

def download(url: str, dest: str):
    print(f"Downloading {url} -> {dest} ...", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"  Done ({os.path.getsize(dest):,} bytes)")


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build mirbase_family_overhangs.json")
    parser.add_argument("--mifam",            default=None, help="Path to miFam.dat (downloads if absent)")
    parser.add_argument("--mature",           default=None, help="Path to mature.fa (downloads if absent)")
    parser.add_argument("--out",              default=DEFAULT_OUT, help="Output JSON path")
    parser.add_argument("--mirbase-version",  default="CURRENT", help="miRBase version string for metadata")
    args = parser.parse_args()

    # Determine paths (download to tmp if not provided)
    tmp_dir = os.path.join(os.path.dirname(__file__), "..", "data", "_tmp_build")
    mifam_path  = args.mifam  or os.path.join(tmp_dir, "miFam.dat")
    mature_path = args.mature or os.path.join(tmp_dir, "mature.fa")

    if not os.path.exists(mifam_path):
        download(MIFAM_URL, mifam_path)
    if not os.path.exists(mature_path):
        download(MATURE_URL, mature_path)

    print("Parsing miFam.dat ...", flush=True)
    families = parse_mifam(mifam_path)
    print(f"  {len(families)} families found")

    print("Parsing mature.fa ...", flush=True)
    mature_seqs = parse_mature_fa(mature_path)
    print(f"  {len(mature_seqs):,} mature sequences found")

    print("Building family overhang DB ...", flush=True)
    db = build_family_db(families, mature_seqs, mirbase_version=args.mirbase_version)
    meta = db["_meta"]
    print(f"  {meta['family_count']} families, {meta['member_count']} members")

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    print(f"Written: {out_path} ({os.path.getsize(out_path):,} bytes)")


if __name__ == "__main__":
    main()
