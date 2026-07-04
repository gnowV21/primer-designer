"""
build_family_db.py — Build mirbase_family_overhangs.json (Phase 3 + Phase 7 PART B)

Phase 7 update: multi-source fallback chain for family classification data.
Priority order (stops at first success):
  1. miFam.dat via FTP  (ftp://mirbase.org/pub/mirbase/CURRENT/miFam.dat.gz)
  2. miFam.dat archived copy (raw.githubusercontent.com mirror — SHA-256 checksum verified)
  3. Seed-based grouping fallback (7-nt seed window, positions 2-8 of mature sequence)

SSRF guard: only whitelisted domains may be fetched (mirbase.org, raw.githubusercontent.com).
Timeout: 10 s per source attempt; fail-fast to next.

Output JSON schema (Phase 7):
{
  "_metadata": {
    "provenance": "mifam_ftp" | "mifam_archived" | "seed_based_fallback",
    "source_url": "...",
    "build_date": "YYYY-MM-DD",
    "families_count": N,
    "hsa_mirnas_count": N,
    "canonical": true | false,
    "verified": false          # set to true only after Vuong manual review
  },
  "families": {                # schema unchanged from Phase 3 — TIDAK ada perubahan
    "_meta": {...},
    "_mirna_to_family": {...},
    "let-7": { "_overhang_nt": 6, "hsa-let-7a-5p": "UGAGGU", ... },
    ...
  }
}

family_crossreactivity.py reads data.get("families", data) for backward-compat
with JSON files that have families at top-level (no "_metadata" wrapper).
"""

import argparse
import ftplib
import gzip
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime

# ── Constants ─────────────────────────────────────────────────────────────────

MIFAM_FTP_HOST = "mirbase.org"
MIFAM_FTP_PATH = "/pub/mirbase/CURRENT/miFam.dat.gz"
MATURE_URL      = "https://www.mirbase.org/download/mature.fa"

# Archived miFam.dat — VERIFY SHA-256 before production
# PLACEHOLDER: set this to the actual SHA-256 of the archived file before use.
MIFAM_ARCHIVED_URL      = None   # set to a raw.githubusercontent.com URL after verifying
MIFAM_ARCHIVED_SHA256   = None   # VERIFY before production — do NOT use None in prod

# Allowed fetch domains (SSRF guard)
_ALLOWED_HOSTS = frozenset([
    "mirbase.org", "www.mirbase.org",
    "raw.githubusercontent.com", "github.com",
    "mirgenedb.org", "www.mirgenedb.org",
])

DEFAULT_OUT = os.path.join(
    os.path.dirname(__file__), "..", "data", "mirbase_family_overhangs.json"
)
OVERHANG_NT = 6  # [Chen05] stemloop RT primer binding length


# ── Domain whitelist check ────────────────────────────────────────────────────

def _check_host(url: str) -> None:
    """Raise ValueError if the URL's host is not whitelisted (SSRF guard)."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if host not in _ALLOWED_HOSTS:
        raise ValueError(f"Fetch refused: host '{host}' not in SSRF whitelist.")


# ── FTP fetch (source 1) ──────────────────────────────────────────────────────

def fetch_mifam_ftp(dest: str, timeout: int = 10) -> bool:
    """Download miFam.dat.gz via FTP, decompress, write plain text to dest."""
    try:
        print(f"  Trying FTP: ftp://{MIFAM_FTP_HOST}{MIFAM_FTP_PATH}", flush=True)
        ftp = ftplib.FTP(MIFAM_FTP_HOST, timeout=timeout)
        ftp.login()
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {MIFAM_FTP_PATH}", buf.write)
        ftp.quit()
        buf.seek(0)
        with gzip.open(buf, "rt", encoding="utf-8") as gz:
            content = gz.read()
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  FTP download OK ({len(content):,} chars)", flush=True)
        return True
    except Exception as exc:
        print(f"  FTP failed: {exc}", file=sys.stderr)
        return False


# ── Archived copy fetch (source 2) ────────────────────────────────────────────

def fetch_mifam_archived(dest: str, timeout: int = 10) -> bool:
    """Download miFam.dat from archived URL, verify SHA-256, write to dest."""
    if not MIFAM_ARCHIVED_URL or not MIFAM_ARCHIVED_SHA256:
        print("  Archived miFam: URL/checksum not configured — skipping.", file=sys.stderr)
        return False
    try:
        _check_host(MIFAM_ARCHIVED_URL)
        print(f"  Trying archived: {MIFAM_ARCHIVED_URL}", flush=True)
        req = urllib.request.Request(MIFAM_ARCHIVED_URL, headers={"User-Agent": "build_family_db/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        # Verify checksum — VERIFY before production
        actual = hashlib.sha256(data).hexdigest()
        if actual.lower() != MIFAM_ARCHIVED_SHA256.lower():
            print(
                f"  Checksum mismatch: expected {MIFAM_ARCHIVED_SHA256}, got {actual}. Skipping.",
                file=sys.stderr,
            )
            return False
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        # Detect gzip
        content = gzip.decompress(data).decode("utf-8") if data[:2] == b"\x1f\x8b" else data.decode("utf-8")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Archived download OK, checksum verified.", flush=True)
        return True
    except Exception as exc:
        print(f"  Archived fetch failed: {exc}", file=sys.stderr)
        return False


# ── miFam.dat parsing ─────────────────────────────────────────────────────────

def parse_mifam(path: str) -> list:
    """Parse miFam.dat into list of family dicts."""
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


# ── mature.fa parsing ─────────────────────────────────────────────────────────

def parse_mature_fa(path: str) -> dict:
    """Parse mature.fa → {name: sequence (RNA, uppercase)}."""
    seqs = {}
    name = None
    buf = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if name and buf:
                    seqs[name] = "".join(buf).upper()
                name = line[1:].split()[0]
                buf = []
            elif line:
                buf.append(line)
    if name and buf:
        seqs[name] = "".join(buf).upper()
    return seqs


# ── Build from miFam + mature.fa ─────────────────────────────────────────────

def build_family_db(
    families: list,
    mature_seqs: dict,
    overhang_nt: int = OVERHANG_NT,
    mirbase_version: str = "CURRENT",
) -> dict:
    """Combine miFam families + mature sequences into the families dict structure."""
    precursor_prefix_map: dict = {}
    for mature_name in mature_seqs:
        base = re.sub(r"[-/]([35]p|[12])$", "", mature_name)
        precursor_prefix_map.setdefault(base, []).append(mature_name)

    result: dict = {}
    mirna_to_family: dict = {}
    total_members = 0

    for fam in families:
        fam_id = fam["id"]
        fam_entry: dict = {"_overhang_nt": overhang_nt}

        for member in fam["members"]:
            precursor_name = member["name"]
            prefix = re.sub(r"-\d+$", "", precursor_name)
            mature_candidates = precursor_prefix_map.get(prefix, [])

            for mature_name in mature_candidates:
                seq = mature_seqs.get(mature_name, "")
                if len(seq) >= overhang_nt:
                    overhang = seq[-overhang_nt:].upper()
                    fam_entry[mature_name] = overhang
                    mirna_to_family[mature_name] = fam_id
                    total_members += 1

        if len(fam_entry) > 1:
            result[fam_id] = fam_entry

    result["_mirna_to_family"] = mirna_to_family
    result["_meta"] = {
        "mirbase_version": mirbase_version,
        "build_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "family_count": len(result) - 1,
        "member_count": total_members,
        "overhang_nt": overhang_nt,
        "source": "miFam.dat + mature.fa from miRBase",
    }
    return result


# ── Seed-based fallback (source 3) ────────────────────────────────────────────

def build_seed_based_families(mature_seqs: dict, overhang_nt: int = OVERHANG_NT) -> dict:
    """
    Group mature miRNAs by 7-nt seed (positions 2–8, 0-indexed 1:8) as fallback.
    Functional but not canonical — provenance = seed_based_fallback.
    """
    groups: dict = defaultdict(list)
    for name, seq in mature_seqs.items():
        if len(seq) >= 8:
            seed = seq[1:8].upper()
            groups[seed].append(name)

    result: dict = {}
    mirna_to_family: dict = {}
    total_members = 0

    for seed, members in groups.items():
        if len(members) < 2:
            continue  # skip singletons
        fam_id = f"seed_{seed}"
        fam_entry: dict = {"_overhang_nt": overhang_nt}
        for name in members:
            seq = mature_seqs[name]
            if len(seq) >= overhang_nt:
                overhang = seq[-overhang_nt:].upper()
                fam_entry[name] = overhang
                mirna_to_family[name] = fam_id
                total_members += 1
        if len(fam_entry) > 1:
            result[fam_id] = fam_entry

    result["_mirna_to_family"] = mirna_to_family
    result["_meta"] = {
        "build_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "family_count": len(result) - 1,
        "member_count": total_members,
        "overhang_nt": overhang_nt,
        "source": "seed-based grouping (positions 2-8 of mature sequence)",
    }
    return result


# ── Download helper ───────────────────────────────────────────────────────────

def download(url: str, dest: str, timeout: int = 10):
    _check_host(url)
    print(f"  Downloading {url} -> {dest} ...", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"  Done ({os.path.getsize(dest):,} bytes)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build mirbase_family_overhangs.json (Phase 7 multi-source)")
    parser.add_argument("--mifam",           default=None)
    parser.add_argument("--mature",          default=None)
    parser.add_argument("--out",             default=DEFAULT_OUT)
    parser.add_argument("--mirbase-version", default="CURRENT")
    args = parser.parse_args()

    tmp_dir = os.path.join(os.path.dirname(__file__), "..", "data", "_tmp_build")
    mifam_path  = args.mifam  or os.path.join(tmp_dir, "miFam.dat")
    mature_path = args.mature or os.path.join(tmp_dir, "mature.fa")

    # ── mature.fa (always needed) ─────────────────────────────────
    if not os.path.exists(mature_path):
        download(MATURE_URL, mature_path)

    print("Parsing mature.fa ...", flush=True)
    mature_seqs = parse_mature_fa(mature_path)
    print(f"  {len(mature_seqs):,} mature sequences found")

    # Count hsa- sequences for metadata
    hsa_count = sum(1 for n in mature_seqs if n.startswith("hsa-"))

    # ── miFam.dat — try source chain ──────────────────────────────
    provenance = None
    source_url = None
    families_data = None
    canonical = False

    # Source 1: miFam.dat FTP
    if args.mifam and os.path.exists(args.mifam):
        # Pre-supplied local file — treat as mifam_ftp provenance
        provenance = "mifam_local"
        source_url = f"file://{os.path.abspath(args.mifam)}"
    elif not os.path.exists(mifam_path):
        if fetch_mifam_ftp(mifam_path):
            provenance = "mifam_ftp"
            source_url = f"ftp://{MIFAM_FTP_HOST}{MIFAM_FTP_PATH}"
        elif fetch_mifam_archived(mifam_path):
            provenance = "mifam_archived"
            source_url = MIFAM_ARCHIVED_URL

    elif os.path.exists(mifam_path):
        provenance = "mifam_local"
        source_url = f"file://{os.path.abspath(mifam_path)}"

    if provenance and provenance != "seed_based_fallback":
        try:
            print("Parsing miFam.dat ...", flush=True)
            fam_list = parse_mifam(mifam_path)
            print(f"  {len(fam_list)} families found")
            print("Building family overhang DB (miFam canonical) ...", flush=True)
            families_data = build_family_db(fam_list, mature_seqs, mirbase_version=args.mirbase_version)
            canonical = True
        except Exception as exc:
            print(f"  miFam parse/build failed: {exc} — falling back to seed-based.", file=sys.stderr)
            families_data = None
            provenance = None

    # Source 3: seed-based fallback
    if families_data is None:
        print("Building family overhang DB (seed-based fallback) ...", flush=True)
        families_data = build_seed_based_families(mature_seqs)
        provenance = "seed_based_fallback"
        source_url = "mature.fa (seed positions 2-8)"
        canonical = False

    meta = families_data.get("_meta", {})
    print(f"  {meta.get('family_count', '?')} families, {meta.get('member_count', '?')} members")
    print(f"  Provenance: {provenance} | Canonical: {canonical}")

    # ── Wrap in Phase 7 schema ────────────────────────────────────
    output = {
        "_metadata": {
            "provenance": provenance,
            "source_url": source_url,
            "build_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "families_count": meta.get("family_count", 0),
            "hsa_mirnas_count": hsa_count,
            "canonical": canonical,
            "verified": False,   # VERIFY before production — Vuong review required
        },
        "families": families_data,
    }

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {out_path} ({os.path.getsize(out_path):,} bytes)")
    if not canonical:
        print(
            "  WARNING: provenance = seed_based_fallback (not canonical). "
            "Run with FTP access to get miFam.dat for canonical family data.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
