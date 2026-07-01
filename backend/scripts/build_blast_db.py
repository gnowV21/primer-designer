"""
build_blast_db.py — Build BLAST+ databases for /api/blast-check

Databases:
  1. miRBase multi-species (mature.fa) — ~2 MB index
  2. Ensembl human cDNA GRCh38 — ~360 MB index (or ~200 MB protein-coding-only)

Storage estimate (Railway free 1 GB OK):
  Full:               ~370 MB  [spec §9.5]
  --protein-coding:   ~200 MB  fallback if over limit

Steps:
  1. Download Ensembl cDNA FASTA (with checksum verify)
  2. Optionally filter to protein-coding transcripts only
  3. Download miRBase mature.fa
  4. Run makeblastdb for each
  5. Delete FASTA after indexing (keep only .nhr/.nin/.nsq/etc.)
  6. Write metadata.json
  7. Verify with blastdbcmd -info

Usage:
  python scripts/build_blast_db.py
  python scripts/build_blast_db.py --protein-coding-only
  python scripts/build_blast_db.py --ensembl-release 111 --out-dir backend/data/blast_db
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime

# ── Constants ────────────────────────────────────────────────────

ENSEMBL_DEFAULT_RELEASE = 111
ENSEMBL_CDNA_URL = (
    "https://ftp.ensembl.org/pub/release-{release}/fasta/homo_sapiens/cdna/"
    "Homo_sapiens.GRCh38.cdna.all.fa.gz"
)
ENSEMBL_CHECKSUM_URL = (
    "https://ftp.ensembl.org/pub/release-{release}/fasta/homo_sapiens/cdna/CHECKSUMS"
)
MIRBASE_MATURE_URL = "https://www.mirbase.org/download/mature.fa"

DEFAULT_OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "blast_db"
)
BLAST_DB_STALE_WARN_DAYS = 90


# ── Download helpers ──────────────────────────────────────────────

def download(url: str, dest: str):
    print(f"Downloading {url} ...", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    size_mb = os.path.getsize(dest) / 1024 / 1024
    print(f"  -> {dest} ({size_mb:.1f} MB)")


def verify_checksum_sum_format(fasta_path: str, checksum_path: str) -> bool:
    """
    Ensembl CHECKSUMS file uses BSD `sum` format (not MD5/SHA).
    Format per line: checksum  blocks  filename
    Verify by running `sum` if available; skip on Windows (no `sum` binary).
    """
    if sys.platform.startswith("win"):
        print("  Checksum verification skipped on Windows (no `sum` binary).")
        return True
    fname = os.path.basename(fasta_path)
    with open(checksum_path) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 3 and parts[2] == fname:
                expected_sum = parts[0]
                result = subprocess.run(
                    ["sum", fasta_path], capture_output=True, text=True
                )
                actual_sum = result.stdout.split()[0]
                if actual_sum == expected_sum:
                    print(f"  Checksum OK: {fname}")
                    return True
                else:
                    print(f"  Checksum MISMATCH: expected {expected_sum}, got {actual_sum}", file=sys.stderr)
                    return False
    print(f"  Checksum entry for {fname} not found — skipping.")
    return True


# ── Protein-coding filter ──────────────────────────────────────────

def filter_protein_coding(fasta_gz_path: str, out_fasta_path: str) -> int:
    """
    Filter Ensembl cDNA FASTA to protein_coding transcripts only.
    Header example:
      >ENST00000641515.2 cdna chromosome:GRCh38:1:65565:65573:1 gene:ENSG00000186092.7 ... transcript_biotype:protein_coding ...
    Returns count of sequences kept.
    """
    import gzip
    count = 0
    keep = False
    with gzip.open(fasta_gz_path, "rt") as fin, open(out_fasta_path, "w") as fout:
        for line in fin:
            if line.startswith(">"):
                keep = "transcript_biotype:protein_coding" in line
                if keep:
                    fout.write(line)
                    count += 1
            elif keep:
                fout.write(line)
    return count


def decompress_full(fasta_gz_path: str, out_fasta_path: str) -> int:
    """Decompress full Ensembl cDNA FASTA. Returns sequence count."""
    import gzip
    count = 0
    with gzip.open(fasta_gz_path, "rt") as fin, open(out_fasta_path, "w") as fout:
        for line in fin:
            if line.startswith(">"):
                count += 1
            fout.write(line)
    return count


# ── makeblastdb ───────────────────────────────────────────────────

def _win_short_path(path: str) -> str:
    """
    On Windows, convert a path with spaces to its 8.3 short form.
    makeblastdb on Windows rejects paths containing spaces even when quoted.
    GetShortPathNameW requires the path to exist; for DB output paths (just a
    prefix, not a real file) we shorten the parent directory and re-append the
    basename.
    No-op on non-Windows or if the path has no spaces.
    """
    if not sys.platform.startswith("win") or " " not in path:
        return path
    try:
        import ctypes
        get_short = ctypes.windll.kernel32.GetShortPathNameW

        # If path exists as-is (e.g. a .fa file), shorten directly.
        if os.path.exists(path):
            buf = ctypes.create_unicode_buffer(32767)
            get_short(path, buf, 32767)
            return buf.value or path

        # Otherwise shorten the nearest existing ancestor, then re-append the tail.
        head, tail_parts = path, []
        while head and not os.path.exists(head):
            head, part = os.path.split(head)
            tail_parts.insert(0, part)
        buf = ctypes.create_unicode_buffer(32767)
        get_short(head, buf, 32767)
        short_head = buf.value or head
        return os.path.join(short_head, *tail_parts)
    except Exception:
        return path


def run_makeblastdb(fasta_path: str, db_out: str, title: str) -> dict:
    """
    Run makeblastdb and return {ok, sequences_count, size_mb}.
    Raises CalledProcessError on failure.
    """
    cmd = [
        "makeblastdb",
        "-in", _win_short_path(fasta_path),
        "-dbtype", "nucl",
        "-out", _win_short_path(db_out),
        "-title", title,
        "-parse_seqids",
    ]
    print(f"  Running: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return verify_db_build(db_out)


def verify_db_build(db_path: str) -> dict:
    """
    Use blastdbcmd -info to verify the database was built correctly.
    Returns {ok, sequences_count, size_mb}.
    """
    try:
        result = subprocess.run(
            ["blastdbcmd", "-db", _win_short_path(db_path), "-info"],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        # Parse sequence count from output
        m = re.search(r"(\d[\d,]+)\s+sequences", output)
        seq_count = int(m.group(1).replace(",", "")) if m else 0
        # Parse size
        m2 = re.search(r"([\d.]+)\s*(MB|GB|KB)", output, re.IGNORECASE)
        size_mb = float(m2.group(1)) if m2 else 0.0
        if m2 and m2.group(2).upper() == "GB":
            size_mb *= 1024
        ok = seq_count > 0
        return {"ok": ok, "sequences_count": seq_count, "size_mb": size_mb}
    except Exception as e:
        return {"ok": False, "sequences_count": 0, "size_mb": 0.0, "error": str(e)}


# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build BLAST databases for primer off-target check")
    parser.add_argument("--ensembl-release",    type=int, default=ENSEMBL_DEFAULT_RELEASE)
    parser.add_argument("--out-dir",            default=DEFAULT_OUT_DIR)
    parser.add_argument("--protein-coding-only", action="store_true",
                        help="Filter Ensembl cDNA to protein_coding transcripts only (~200 MB)")
    parser.add_argument("--skip-ensembl",       action="store_true",
                        help="Skip Ensembl download/build (miRBase only)")
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    tmp_dir = os.path.join(out_dir, "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    metadata = {
        "ensembl_version": str(args.ensembl_release),
        "mirbase_version": "CURRENT",
        "build_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "protein_coding_only": args.protein_coding_only,
        "sequences_count": {},
        "makeblastdb_version": "",
    }

    # Detect makeblastdb version
    try:
        ver = subprocess.run(["makeblastdb", "-version"], capture_output=True, text=True)
        metadata["makeblastdb_version"] = ver.stdout.strip().splitlines()[0] if ver.stdout else "unknown"
    except FileNotFoundError:
        print("ERROR: makeblastdb not found. Install NCBI BLAST+.", file=sys.stderr)
        sys.exit(1)

    # ── 1. miRBase mature.fa ─────────────────────────────────────
    mirbase_fa = os.path.join(tmp_dir, "mature.fa")
    if not os.path.exists(mirbase_fa):
        download(MIRBASE_MATURE_URL, mirbase_fa)

    mirbase_db = os.path.join(out_dir, "mirbase_multi")
    print("Building miRBase BLAST db ...", flush=True)
    mb_info = run_makeblastdb(mirbase_fa, mirbase_db, "miRBase_mature_multi_species")
    metadata["sequences_count"]["mirbase_multi"] = mb_info["sequences_count"]
    print(f"  miRBase: {mb_info['sequences_count']:,} sequences, {mb_info['size_mb']:.1f} MB")

    # ── 2. Ensembl cDNA ──────────────────────────────────────────
    if not args.skip_ensembl:
        ensembl_gz = os.path.join(tmp_dir, f"ensembl_cdna_r{args.ensembl_release}.fa.gz")
        ensembl_url = ENSEMBL_CDNA_URL.format(release=args.ensembl_release)
        checksum_url = ENSEMBL_CHECKSUM_URL.format(release=args.ensembl_release)

        if not os.path.exists(ensembl_gz):
            download(ensembl_url, ensembl_gz)
            checksum_path = os.path.join(tmp_dir, "CHECKSUMS")
            try:
                download(checksum_url, checksum_path)
                verify_checksum_sum_format(ensembl_gz, checksum_path)
            except Exception as e:
                print(f"  Warning: checksum verification failed ({e}) — continuing.")

        ensembl_fa = os.path.join(tmp_dir, "ensembl_cdna.fa")
        if args.protein_coding_only:
            print("Filtering Ensembl to protein_coding only ...", flush=True)
            n = filter_protein_coding(ensembl_gz, ensembl_fa)
        else:
            print("Decompressing full Ensembl cDNA ...", flush=True)
            n = decompress_full(ensembl_gz, ensembl_fa)
        print(f"  {n:,} sequences")

        ensembl_db = os.path.join(out_dir, "ensembl_human_cdna")
        print("Building Ensembl BLAST db ...", flush=True)
        ens_info = run_makeblastdb(ensembl_fa, ensembl_db, f"Ensembl_GRCh38_cDNA_r{args.ensembl_release}")
        metadata["sequences_count"]["ensembl_human_cdna"] = ens_info["sequences_count"]
        metadata["ensembl_url"] = ensembl_url
        print(f"  Ensembl: {ens_info['sequences_count']:,} sequences, {ens_info['size_mb']:.1f} MB")

        # Delete FASTA after indexing — only keep BLAST index files
        os.remove(ensembl_fa)

    # Clean up tmp (keep gz for potential re-runs)
    os.remove(mirbase_fa) if os.path.exists(mirbase_fa) else None

    # ── 3. Write metadata.json ────────────────────────────────────
    metadata_path = os.path.join(out_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\nmetadata.json written: {metadata_path}")
    print(f"Build complete. Database dir: {out_dir}")


def check_db_freshness(metadata_path: str) -> dict:
    """
    Read metadata.json and return {age_days, outdated_warning, message}.
    Used by /api/blast-check to surface staleness warnings.
    """
    try:
        with open(metadata_path) as f:
            meta = json.load(f)
        build_date = datetime.strptime(meta["build_date"], "%Y-%m-%d")
        age_days = (datetime.utcnow() - build_date).days
        outdated = age_days > BLAST_DB_STALE_WARN_DAYS
        return {
            "age_days": age_days,
            "outdated_warning": outdated,
            "message": (
                f"BLAST database is {age_days} days old "
                f"(>{BLAST_DB_STALE_WARN_DAYS} days — consider rebuilding)."
            ) if outdated else f"BLAST database is {age_days} days old.",
            "build_date": meta.get("build_date"),
            "ensembl_version": meta.get("ensembl_version"),
            "mirbase_version": meta.get("mirbase_version"),
            "sequences_count": meta.get("sequences_count", {}),
        }
    except (FileNotFoundError, KeyError, ValueError) as e:
        return {
            "age_days": None,
            "outdated_warning": True,
            "message": f"BLAST database metadata missing or unreadable: {e}",
        }


if __name__ == "__main__":
    main()
