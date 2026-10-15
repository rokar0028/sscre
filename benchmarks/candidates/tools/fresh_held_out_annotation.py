"""Annotation-guide draft refinements for WS5 fresh held-out pairs."""

from __future__ import annotations

from typing import Any

from convert_cacheeval_candidates import map_cacheeval_row  # noqa: E402

_UNCERTAIN_SUBCATEGORY_TOKENS = ("anaphor", "deictic")


def sampling_bucket(row: dict, mapped: dict) -> str:
    """Draft mix bucket (targets only; labels stay provisional until human review)."""
    verification = row.get("verification_method") or ""
    if verification == "policy_no_cache":
        return "uncertain"
    label = row.get("label") or ""
    subcategory = (row.get("subcategory") or "").lower()
    query_a = (row.get("query_a") or "").strip()
    query_b = (row.get("query_b") or "").strip()
    if label == "RELATED_UNSAFE" and (
        query_a == query_b
        or any(token in subcategory for token in _UNCERTAIN_SUBCATEGORY_TOKENS)
    ):
        return "uncertain"
    if mapped.get("compatibility_label") == "compatible":
        return "compatible"
    return "incompatible"


def _anaphor_uncertain_reason(surface: str) -> str:
    return (
        f"Identical '{surface}' depends on unstored multi-turn dialog context."
    )


def refine_draft_payload(
    payload: dict[str, Any],
    cacheeval_row: dict[str, Any],
) -> dict[str, Any]:
    """Apply converter mapping, then ANNOTATION_GUIDE_v1 draft adjustments."""
    mapped = map_cacheeval_row(cacheeval_row)
    bucket = sampling_bucket(cacheeval_row, mapped)
    out = dict(payload)
    out["compatibility_label"] = mapped["compatibility_label"]
    out["reusable"] = mapped["reusable"]
    out["reason"] = mapped.get("reason")
    out["failure_category"] = mapped["failure_category"]
    out["coverage_category"] = mapped["coverage_category"]
    out["freshness_class"] = mapped["freshness_class"]

    if bucket == "uncertain":
        surface = (cacheeval_row.get("query_a") or "").strip()
        out["compatibility_label"] = "uncertain"
        out["reusable"] = False
        out["failure_category"] = "insufficient_evidence"
        out["coverage_category"] = "insufficient_evidence"
        out["reason"] = _anaphor_uncertain_reason(surface)

    out.pop("expected_compatibility", None)
    out.pop("expected_reuse", None)
    return out
