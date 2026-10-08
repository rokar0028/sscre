import importlib.util
from pathlib import Path

_FILTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/candidates/tools/filter_cacheeval_commercial.py"
)
_spec = importlib.util.spec_from_file_location(
    "filter_cacheeval_commercial", _FILTER_MODULE
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
commercial_exclusion_reason = _mod.commercial_exclusion_reason
filter_rows = _mod.filter_rows


def test_quora_qqp_source_is_excluded() -> None:
    row = {"id": "cb-qa-0001", "source": "Quora QQP (label=1 duplicates)"}
    assert commercial_exclusion_reason(row) == "quora_qqp_source"


def test_xlam_nc_source_is_excluded() -> None:
    row = {"id": "cb-tool-0001", "source": "xLAM-irrelevance-7.5k"}
    assert commercial_exclusion_reason(row) == "xlam_nc_source"


def test_triviaqa_nocontext_is_retained() -> None:
    row = {"id": "cb-qa-0002", "source": "TriviaQA rc.nocontext (random pair)"}
    assert commercial_exclusion_reason(row) is None


def test_filter_rows_partition() -> None:
    rows = [
        {"id": "a", "source": "curator"},
        {"id": "b", "source": "xLAM-irrelevance-7.5k"},
    ]
    kept, excluded = filter_rows(rows)
    assert [r["id"] for r in kept] == ["a"]
    assert excluded[0]["_exclusion_reason"] == "xlam_nc_source"
