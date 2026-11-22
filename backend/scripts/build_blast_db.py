"""
build_blast_db.py — Build BLAST+ database for /api/blast-check and the design BLAST

Database:
  miRBase multi-species (mature.fa) — ~2 MB index

Ensembl human cDNA is excluded: DNase treatment prior to RT removes all
genomic DNA. The only off-target risk remaining is miRNA family cross-
reactivity, which is fully covered by miRBase multi-species.

Input is the PINNED mature.fa of miRBase 22.1 (backend/data/mirbase_22.1/
mature.fa.gz, sha256 in SHA256 — scripts/mirbase_pin.py): the overhang and family
indexes were built from that file, so the BLAST DB must be too. The sha256 is
checked before anything is built; a different file exits with code 2.

Steps:
  1. Read the pinned mature.fa (or --fasta FILE, or --download), check its sha256
  2. Run makeblastdb (in a temporary directory, then move the volumes into place)
  3. Check the DB holds as many sequences as the FASTA
  4. Write metadata.json (release, mature_fa_sha256, counts, makeblastdb version)

Usage:
  python scripts/build_blast_db.py                      # pinned file
  python scripts/build_blast_db.py --fasta mature.fa    # another copy, same sha256
  python scripts/build_blast_db.py --download           # miRBase archive copy of 22.1
  python scripts/build_blast_db.py --out-dir backend/data/blast_db
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from scripts import mirbase_pin as pin  # noqa: E402

# ── Constants ────────────────────────────────────────────────────

# Never build from miRBase CURRENT (23.1 since 2026-09; the indexes are 22.1):
# --download fetches the archive copy of 22.1 (pin.ARCHIVE_URL) and checks it too.
DEFAULT_OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "blast_db"
)
DB_NAME = "mirbase_multi"
BLAST_DB_STALE_WARN_DAYS = 90


# ── makeblastdb ───────────────────────────────────────────────────

def _blast_env(**extra: str) -> dict:
    """os.environ + `extra`, NCBI usage report off unless already set — the same rule
    as algorithm/specificity_check/blast_offtarget.blast_subprocess_env (this script
    stays free of engine imports)."""
    env = dict(os.environ, **extra)
    env.setdefault("BLAST_USAGE_REPORT", "false")
    return env


def run_makeblastdb(fasta_path: str, db_out: str, title: str) -> dict:
    """
    Run makeblastdb and return {ok, sequences_count, size_mb}.
    Raises CalledProcessError on failure.

    BLAST+ splits -in and -out on spaces (both accept lists), so a path such as
    'D:\\Users\\TIEN VUONG\\...' breaks them, and 8.3 short names are disabled on
    non-system volumes by default. Run inside the output directory and pass bare
    file names instead; -in is given relative to that directory.
    """
    out_dir = os.path.dirname(os.path.abspath(db_out))
    cmd = [
        "makeblastdb",
        "-in", os.path.relpath(os.path.abspath(fasta_path), out_dir),
        "-dbtype", "nucl",
        "-out", os.path.basename(db_out),
        "-title", title,
        "-parse_seqids",
    ]
    print(f"  Running (in {out_dir}): {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=out_dir, env=_blast_env())
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
        # BLASTDB locates the directory (spaces allowed); -db gets the bare name.
        env = _blast_env(BLASTDB=os.path.dirname(os.path.abspath(db_path)))
        result = subprocess.run(
            ["blastdbcmd", "-db", os.path.basename(db_path), "-info"],
            capture_output=True, text=True, timeout=30, env=env,
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

def main(argv=None):
    parser = argparse.ArgumentParser(description="Build miRBase BLAST database for primer off-target check")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--fasta", default=None,
                        help=f"local mature.fa or mature.fa.gz (default: {pin.PINNED_FASTA})")
    parser.add_argument("--download", action="store_true",
                        help="fetch mature.fa from --url instead of reading a local file")
    parser.add_argument("--url", default=pin.ARCHIVE_URL)
    parser.add_argument("--sha256", default=None,
                        help="expected sha256 of the uncompressed file (default: the pinned one)")
    args = parser.parse_args(argv)

    out_dir = os.path.abspath(args.out_dir)

    metadata = {
        "mirbase_version": "",
        "build_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sequences_count": {},
        "makeblastdb_version": "",
    }

    # ── 1. mature.fa, sha256 checked before anything is built ────
    try:
        data, sha = pin.load_mature_fa(args.fasta,
                                       download_url=args.url if args.download else None,
                                       expected_sha256=args.sha256)
    except pin.PinMismatch as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"ERROR: cannot read mature.fa: {e}", file=sys.stderr)
        sys.exit(2)
    # Detect makeblastdb version
    try:
        ver = subprocess.run(["makeblastdb", "-version"], capture_output=True, text=True,
                             env=_blast_env())
        metadata["makeblastdb_version"] = ver.stdout.strip().splitlines()[0] if ver.stdout else "unknown"
    except FileNotFoundError:
        print("ERROR: makeblastdb not found. Install NCBI BLAST+.", file=sys.stderr)
        sys.exit(1)

    n_fasta = pin.count_entries(data)
    metadata["mirbase_version"] = pin.PINNED_RELEASE if sha == pin.pinned_sha256() else "unknown"
    metadata["mature_fa_sha256"] = sha
    if args.download:
        metadata["mature_fa_source"] = args.url
    else:
        src = os.path.abspath(args.fasta or pin.PINNED_FASTA)
        try:
            src = os.path.relpath(src, _BACKEND_DIR)
        except ValueError:   # another drive (Windows)
            pass
        metadata["mature_fa_source"] = src.replace(os.sep, "/")

    # ── 2. makeblastdb in a temporary directory, then move the volumes ──
    # The system temp directory, not out_dir: makeblastdb 2.17 with -parse_seqids
    # fails when its working directory contains a space (it re-opens the new DB by a
    # path it splits on spaces), e.g. a Windows user folder "C:\Users\First Last"; Windows gives the
    # temp directory as an 8.3 short path. metadata.json goes last: a build that stops
    # half-way leaves no metadata, so bootstrap_blast_db sees the DB as missing.
    os.makedirs(out_dir, exist_ok=True)
    meta_path = os.path.join(out_dir, "metadata.json")
    if os.path.exists(meta_path):
        os.remove(meta_path)
    tmp_dir = tempfile.mkdtemp(prefix="blastdb_build_")
    try:
        mirbase_fa = os.path.join(tmp_dir, "mature.fa")
        with open(mirbase_fa, "wb") as f:
            f.write(data)

        print("Building miRBase BLAST db ...", flush=True)
        mb_info = run_makeblastdb(mirbase_fa, os.path.join(tmp_dir, DB_NAME),
                                  "miRBase_mature_multi_species")
        if mb_info["sequences_count"] != n_fasta:
            print(f"ERROR: BLAST DB holds {mb_info['sequences_count']:,} sequences, "
                  f"mature.fa {n_fasta:,}.", file=sys.stderr)
            sys.exit(3)
        for old in glob.glob(os.path.join(out_dir, DB_NAME + ".*")):
            os.remove(old)
        for vol in glob.glob(os.path.join(tmp_dir, DB_NAME + ".*")):
            shutil.move(vol, os.path.join(out_dir, os.path.basename(vol)))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    metadata["sequences_count"][DB_NAME] = mb_info["sequences_count"]
    print(f"  miRBase: {mb_info['sequences_count']:,} sequences, {mb_info['size_mb']:.1f} MB")

    # ── 3. Write metadata.json ────────────────────────────────────
    with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")
    print(f"\nmetadata.json written: {meta_path}")
    print(f"Build complete. Database dir: {out_dir}")
    return 0


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
