import importlib.util
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1] / "benchmarks/candidates/tools"
_spec = importlib.util.spec_from_file_location(
    "convert_cacheeval_candidates",
    _TOOLS / "convert_cacheeval_candidates.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
map_cacheeval_row = _mod.map_cacheeval_row


def test_equiv_exact_duplicate_mapping() -> None:
    payload = map_cacheeval_row(
        {
            "id": "cb-qa-0001",
            "label": "EQUIV",
            "domain": "qa_factual",
            "subcategory": "test",
            "query_a": "What is caching?",
            "query_b": "What is caching?",
            "verification_method": "exact_match",
            "rationale": "same question",
        }
    )
    assert payload["reusable"] is True
    assert payload["coverage_category"] == "exact_duplicate"
    assert payload["failure_category"] == "none"
    assert payload["review_status"] == "draft"
    assert payload["source_group"] == "cacheeval_v1:filtered"


def test_adversarial_maps_to_high_similarity_incompatible() -> None:
    payload = map_cacheeval_row(
        {
            "id": "cb-qa-0099",
            "label": "ADVERSARIAL",
            "domain": "qa_factual",
            "subcategory": "capital_vs_population",
            "query_a": "Population of Paris?",
            "query_b": "Capital of France?",
            "verification_method": "exact_match",
            "rationale": "near duplicate unsafe",
        }
    )
    assert payload["compatibility_label"] == "incompatible"
    assert payload["coverage_category"] == "high_similarity_incompatible"


def test_policy_no_cache_creative_equiv() -> None:
    payload = map_cacheeval_row(
        {
            "id": "cb-creative-0001",
            "label": "EQUIV",
            "domain": "creative",
            "subcategory": "poem",
            "query_a": "Write a poem.",
            "query_b": "Write a poem.",
            "verification_method": "policy_no_cache",
            "rationale": "must regenerate",
        }
    )
    assert payload["reusable"] is False
    assert payload["coverage_category"] == "stale_answer"
    assert payload["failure_category"] == "stale_answer"
