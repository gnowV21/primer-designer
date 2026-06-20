#!/usr/bin/env python3
"""
Fetch miRNAs from miRBase API and seed them into the local SQLite DB.
Use this when you want to add specific miRNAs without downloading the full release.

Usage:
  # Fetch a list of miRNA names or accessions from a text file (one per line):
  python scripts/fetch_and_seed.py --file my_mirnas.txt

  # Fetch inline:
  python scripts/fetch_and_seed.py hsa-miR-21-5p MIMAT0000076 hsa-miR-1-3p

  # Fetch all miRNAs from miRBase and seed (requires internet, ~38k entries):
  python scripts/fetch_and_seed.py --all

Requires internet access. Falls back to RNAcentral if miRBase is unreachable.
"""
import argparse
import sys
import os
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import local_db

MIRBASE_API    = "https://mirbase.org/api/mirna/"
RNACENTRAL_API = "https://rnacentral.org/api/v1/rna/"
MIRBASE_FA_URL = "https://mirbase.org/download/mature.fa.gz"

SPECIES_MAP = {
    "hsa": "Homo sapiens",
    "mmu": "Mus musculus",
    "rno": "Rattus norvegicus",
    "cel": "Caenorhabditis elegans",
    "dme": "Drosophila melanogaster",
    "gga": "Gallus gallus",
    "bta": "Bos taurus",
}

TIMEOUT = 15


def _parse_mirna_response(body: dict | list, mirna_id: str) -> dict | None:
    results = body.get("results", []) if isinstance(body, dict) else (body if isinstance(body, list) else [])
    if not results:
        return None
    hit = results[0]
    seq = hit.get("mature_sequence", hit.get("sequence", "")).upper()
    acc = hit.get("mature_acc", hit.get("accession", ""))
    prefix = mirna_id[:3].lower() if "-" in mirna_id else ""
    species = SPECIES_MAP.get(prefix, hit.get("organism", ""))
    return {
        "id":        mirna_id,
        "accession": acc,
        "sequence":  seq,
        "family":    hit.get("family", ""),
        "species":   species,
        "length":    len(seq),
    }


def fetch_one(mirna_id: str) -> dict | None:
    """Try miRBase API first, fall back to RNAcentral."""
    # Detect param type
    import re
    param = "accession" if re.match(r'^MIMAT\d+$', mirna_id, re.IGNORECASE) else "name"

    try:
        r = requests.get(MIRBASE_API, params={param: mirna_id}, timeout=TIMEOUT)
        if r.status_code == 200:
            result = _parse_mirna_response(r.json(), mirna_id)
            if result:
                result["_source"] = "mirbase"
                return result
    except Exception:
        pass

    # Fallback: RNAcentral
    try:
        r = requests.get(
            RNACENTRAL_API,
            params={"external_id": mirna_id, "format": "json"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                hit = results[0]
                seq = hit.get("sequence", "").upper().replace("T", "U")
                desc = hit.get("description", "")
                # RNAcentral descriptions: "Homo sapiens miRNA hsa-miR-21-5p"
                # or "ncRNA from Homo sapiens" / "miRNA from Homo sapiens"
                import re as _re
                _m = _re.search(r'\bfrom\s+([A-Z][a-z]+ [a-z]+)', desc)
                if _m:
                    species = _m.group(1)
                else:
                    parts = desc.split()
                    species = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else ""
                return {
                    "id":        mirna_id,
                    "accession": "",
                    "sequence":  seq,
                    "family":    "",
                    "species":   species,
                    "length":    len(seq),
                    "_source":   "rnacentral",
                }
    except Exception:
        pass

    return None


def fetch_all_from_mirbase() -> int:
    """
    Download the full mature.fa.gz from miRBase and seed all entries.
    Returns count of rows inserted.
    """
    import gzip

    print(f"Downloading {MIRBASE_FA_URL} ...", flush=True)
    try:
        r = requests.get(MIRBASE_FA_URL, timeout=120, stream=True)
        r.raise_for_status()
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        print(
            "Download manually: https://mirbase.org/download/mature.fa.gz\n"
            "Then run: python scripts/build_db.py mature.fa.gz",
            file=sys.stderr,
        )
        return 0

    gz_data = r.content
    print(f"Downloaded {len(gz_data):,} bytes. Parsing...", flush=True)

    text = gzip.decompress(gz_data).decode("utf-8")
    count = 0
    header, parts = None, []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(">"):
            if header and parts:
                _seed_fasta_entry(header, "".join(parts))
                count += 1
            header, parts = line[1:], []
        elif line:
            parts.append(line)
    if header and parts:
        _seed_fasta_entry(header, "".join(parts))
        count += 1

    return count


def _seed_fasta_entry(header: str, seq: str):
    tokens = header.split()
    name = tokens[0] if tokens else ""
    accession = tokens[1] if len(tokens) > 1 else ""
    if len(tokens) >= 4:
        species = f"{tokens[2]} {tokens[3]}"
    else:
        prefix = name[:3].lower() if "-" in name else ""
        species = SPECIES_MAP.get(prefix, "")
    seq = seq.upper().replace("T", "U")
    local_db.upsert({
        "id":        name,
        "accession": accession,
        "sequence":  seq,
        "family":    "",
        "species":   species,
        "length":    len(seq),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="miRNA names or accessions to fetch")
    parser.add_argument("--file", "-f", help="Text file with one miRNA name/accession per line")
    parser.add_argument("--all", action="store_true", help="Download full miRBase mature.fa and seed all ~38k entries")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls in seconds (default 0.5)")
    args = parser.parse_args()

    local_db.init_schema()

    if args.all:
        count = fetch_all_from_mirbase()
        print(f"\nDone — {count:,} miRNAs seeded.")
        return

    # Collect IDs
    ids = list(args.ids)
    if args.file:
        with open(args.file) as f:
            ids += [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not ids:
        parser.print_help()
        sys.exit(1)

    ok, fail = 0, []
    for i, mirna_id in enumerate(ids):
        print(f"[{i+1}/{len(ids)}] {mirna_id} ... ", end="", flush=True)
        result = fetch_one(mirna_id)
        if result:
            source = result.pop("_source", "?")
            local_db.upsert(result)
            print(f"OK ({source}) — {result['sequence'][:16]}... {result['species']}")
            ok += 1
        else:
            print("NOT FOUND")
            fail.append(mirna_id)
        if i < len(ids) - 1:
            time.sleep(args.delay)

    print(f"\nDone — {ok} seeded, {len(fail)} failed.")
    if fail:
        print("Failed:", ", ".join(fail))


if __name__ == "__main__":
    main()
