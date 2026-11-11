"""Cache invalidation: designs and matrix blocks are tied to the algorithm version."""
import json

from crossreactivity.build_matrix import block_filename
from crossreactivity.design_all import compact, read_done, select_todo

MATURE = {"hsa-a": "ACGT", "hsa-b": "CCGG", "hsa-c": "TTAA"}


def test_select_todo_redesigns_other_versions():
    done = {
        "hsa-a": {"mirna": "hsa-a", "status": "ok", "algorithm_version": "3.6.0"},
        "hsa-b": {"mirna": "hsa-b", "status": "ok", "algorithm_version": "3.5.0"},
        # failed records written before 3.6.0 carry no version
        "hsa-c": {"mirna": "hsa-c", "status": "failed"},
    }
    todo = select_todo(MATURE, done, "3.6.0")
    assert [n for n, _ in todo] == ["hsa-b", "hsa-c"]


def test_select_todo_new_mirnas():
    assert [n for n, _ in select_todo(MATURE, {}, "3.6.0")] == ["hsa-a", "hsa-b", "hsa-c"]


def test_compact_keeps_latest_record(tmp_path):
    p = tmp_path / "designs_hsa.jsonl"
    lines = [
        {"mirna": "hsa-b", "status": "ok", "algorithm_version": "3.5.0", "forward_primer": "OLD"},
        {"mirna": "hsa-a", "status": "ok", "algorithm_version": "3.6.0"},
        {"mirna": "hsa-b", "status": "ok", "algorithm_version": "3.6.0", "forward_primer": "NEW"},
    ]
    p.write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
    compact(str(p))
    assert len(p.read_text(encoding="utf-8").splitlines()) == 2
    assert read_done(str(p))["hsa-b"]["forward_primer"] == "NEW"


def _assay(fwd="ACGTACGTACGT"):
    return {"mirna": "hsa-a", "sequence": "ACGT", "rt_primer": "RT", "forward_primer": fwd,
            "fwd_specific_len": 12}


def test_block_filename_changes_with_version_and_content():
    base = block_filename(0, [_assay()], "3.6.0")
    assert base == block_filename(0, [_assay()], "3.6.0")
    assert base != block_filename(0, [_assay()], "3.5.0")
    assert base != block_filename(0, [_assay("ACGTACGTACGA")], "3.6.0")
    assert base.startswith("block_0000_") and base.endswith(".jsonl")
