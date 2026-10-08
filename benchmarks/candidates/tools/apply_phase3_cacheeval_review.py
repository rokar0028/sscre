"""Apply Phase 3 human review to CacheEval candidate JSONL by ID range."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sscre.benchmark import BenchmarkRecord, load_benchmark_jsonl
from sscre.benchmark_build import assign_next_pair_id, validate_candidate_record, write_jsonl

# Batch 1 gap-fill payloads (run only with --batch 1).
GAP_FILL_BATCH1: list[dict] = [
    {
        "query_a": "Explain binary search in Python.",
        "query_b": "Explain binary search in Python.",
        "reusable": True,
        "compatibility_label": "compatible",
        "failure_category": "none",
        "coverage_category": "exact_duplicate",
        "freshness_class": "stable",
        "metadata": {
            "intent": "code_explanation",
            "domain": "programming",
            "entities": [],
            "constraints": {},
            "temporal_class": None,
            "output_format": "prose",
        },
        "reason": None,
    },
    {
        "query_a": "What is semantic caching?",
        "query_b": "What is semantic  caching?",
        "reusable": True,
        "compatibility_label": "compatible",
        "failure_category": "none",
        "coverage_category": "whitespace_variant",
        "freshness_class": "stable",
        "metadata": {"intent": "definition", "domain": "general", "entities": [], "constraints": {}},
        "reason": None,
    },
    {
        "query_a": "List three benefits of exercise as bullet points.",
        "query_b": "Return three benefits of exercise as a JSON array of strings.",
        "reusable": False,
        "compatibility_label": "incompatible",
        "failure_category": "format_mismatch",
        "coverage_category": "format_change",
        "freshness_class": "stable",
        "metadata": {"intent": "list_facts", "domain": "health", "entities": [], "constraints": {}},
        "reason": "Bullet list output differs from JSON array output.",
    },
    {
        "query_a": "How do I configure Wi-Fi on Ubuntu?",
        "query_b": "How do I season cast iron cookware?",
        "reusable": False,
        "compatibility_label": "incompatible",
        "failure_category": "domain_mismatch",
        "coverage_category": "domain_change",
        "freshness_class": "stable",
        "metadata": {"intent": "how_to", "domain": "computing", "entities": [], "constraints": {}},
        "reason": "Operating-system networking differs from kitchenware care.",
    },
    {
        "query_a": "What is the weather in Boston today?",
        "query_b": "What is the weather in Boston on July 4, 2019?",
        "reusable": False,
        "compatibility_label": "incompatible",
        "failure_category": "temporal_mismatch",
        "coverage_category": "temporal_freshness",
        "freshness_class": "dynamic",
        "metadata": {
            "intent": "factual_lookup",
            "domain": "weather",
            "entities": ["Boston"],
            "constraints": {},
            "temporal_class": "current_state",
        },
        "reason": "Live weather request differs from a fixed historical date.",
    },
    {
        "query_a": "Who won the latest Super Bowl?",
        "query_b": "Who won Super Bowl XXXVI?",
        "reusable": False,
        "compatibility_label": "incompatible",
        "failure_category": "temporal_mismatch",
        "coverage_category": "stale_answer",
        "freshness_class": "semi_dynamic",
        "metadata": {
            "intent": "factual_lookup",
            "domain": "sports",
            "entities": [],
            "constraints": {},
            "temporal_class": "time_sensitive",
        },
        "reason": "Latest-result query must not reuse an answer tied to one edition.",
    },
    {
        "query_a": "Book a table for two at a nice restaurant.",
        "query_b": "Book a table for two at a nice restaurant nearby.",
        "reusable": False,
        "compatibility_label": "uncertain",
        "failure_category": "ambiguity",
        "coverage_category": "ambiguity",
        "freshness_class": "stable",
        "metadata": {"intent": "reservation", "domain": "general", "entities": [], "constraints": {}},
        "reason": "Nearby is underspecified without location context.",
    },
    {
        "query_a": "Fix the API issue.",
        "query_b": "Fix the API issue on production.",
        "reusable": False,
        "compatibility_label": "uncertain",
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "freshness_class": "stable",
        "metadata": {"intent": "troubleshooting", "domain": "engineering", "entities": [], "constraints": {}},
        "reason": "Production scope may change remediation steps; evidence is incomplete.",
    },
]

BATCH1_OVERRIDES: dict[str, dict] = {
    "pair-0034": {"coverage_category": "paraphrase"},
    "pair-0036": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": (
            "Identical surface text 'incorrect' is anaphoric feedback; "
            "required dialog context is not stored in this benchmark row."
        ),
    },
    "pair-0038": {
        "coverage_category": "constraint_change",
        "reason": "JavaScript versus TypeScript changes the language constraint.",
    },
    "pair-0049": {"coverage_category": "paraphrase"},
    "pair-0059": {"coverage_category": "paraphrase"},
    "pair-0060": {"coverage_category": "paraphrase"},
}

BATCH2_OVERRIDES: dict[str, dict] = {
    "pair-0063": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Gratitude versus sarcastic rejection are different conversational intents.",
    },
    "pair-0064": {"coverage_category": "paraphrase"},
    "pair-0066": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'yeah' depends on unstored multi-turn dialog context.",
    },
    "pair-0068": {
        "coverage_category": "constraint_change",
        "reason": "Prisma versus Drizzle changes the ORM/library constraint.",
    },
    "pair-0069": {"coverage_category": "paraphrase"},
    "pair-0070": {"coverage_category": "paraphrase"},
    "pair-0074": {"coverage_category": "paraphrase"},
    "pair-0076": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "Capital city fact differs from national population fact.",
    },
    "pair-0079": {"coverage_category": "paraphrase"},
    "pair-0080": {"coverage_category": "paraphrase"},
    "pair-0084": {"coverage_category": "paraphrase"},
    "pair-0085": {"coverage_category": "paraphrase"},
    "pair-0088": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "Account closure differs from payment-card closure.",
    },
    "pair-0089": {"coverage_category": "paraphrase"},
    "pair-0090": {"coverage_category": "paraphrase"},
    "pair-0094": {"coverage_category": "paraphrase"},
    "pair-0095": {"coverage_category": "paraphrase"},
    "pair-0096": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'hmm' depends on unstored multi-turn dialog context.",
    },
    "pair-0098": {
        "coverage_category": "constraint_change",
        "reason": "React 17+ lifecycle guidance differs from legacy React behavior.",
    },
    "pair-0099": {"coverage_category": "paraphrase"},
    "pair-0100": {"coverage_category": "paraphrase"},
    "pair-0101": {
        "coverage_category": "constraint_change",
        "reason": "Python versus Node.js changes the runtime constraint.",
    },
    "pair-0104": {"coverage_category": "paraphrase"},
    "pair-0105": {"coverage_category": "paraphrase"},
    "pair-0109": {"coverage_category": "paraphrase"},
    "pair-0110": {"coverage_category": "paraphrase"},
}

BATCH3_OVERRIDES: dict[str, dict] = {
    "pair-0113": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "California versus New York changes the legal jurisdiction entity.",
    },
    "pair-0114": {"coverage_category": "paraphrase"},
    "pair-0115": {"coverage_category": "paraphrase"},
    "pair-0117": {
        "compatibility_label": "compatible",
        "expected_compatibility": "compatible",
        "reusable": True,
        "expected_reuse": True,
        "failure_category": "none",
        "coverage_category": "paraphrase",
        "reason": None,
    },
    "pair-0119": {"coverage_category": "paraphrase"},
    "pair-0121": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Meditation guidance differs from journaling guidance.",
    },
    "pair-0124": {"coverage_category": "paraphrase"},
    "pair-0125": {"coverage_category": "paraphrase"},
    "pair-0129": {"coverage_category": "paraphrase"},
    "pair-0134": {"coverage_category": "paraphrase"},
    "pair-0139": {"coverage_category": "paraphrase"},
    "pair-0141": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'perfect' depends on unstored multi-turn dialog context.",
    },
    "pair-0144": {"coverage_category": "paraphrase"},
    "pair-0146": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "Gold versus silver are different chemical elements.",
    },
    "pair-0149": {"coverage_category": "paraphrase"},
    "pair-0150": {"coverage_category": "paraphrase"},
    "pair-0154": {"coverage_category": "paraphrase"},
    "pair-0155": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "entity_mismatch",
        "coverage_category": "entity_change",
        "reason": "Bar Tartine and Tartine refer to different San Francisco venues.",
    },
    "pair-0159": {"coverage_category": "paraphrase"},
    "pair-0160": {"coverage_category": "paraphrase"},
    "pair-0161": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'elaborate' depends on unstored multi-turn dialog context.",
    },
}

BATCH4_OVERRIDES: dict[str, dict] = {
    "pair-0164": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": "Apple Watch top-up differs from Google Pay top-up.",
    },
    "pair-0165": {"coverage_category": "paraphrase"},
    "pair-0169": {"coverage_category": "paraphrase"},
    "pair-0170": {"coverage_category": "paraphrase"},
    "pair-0171": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'change that' depends on unstored multi-turn dialog context.",
    },
    "pair-0174": {"coverage_category": "paraphrase"},
    "pair-0175": {"coverage_category": "paraphrase"},
    "pair-0179": {"coverage_category": "paraphrase"},
    "pair-0180": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": "Restaurant marketing differs from yoga practice.",
    },
    "pair-0184": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "constraint_mismatch",
        "coverage_category": "high_similarity_incompatible",
        "reason": "Expression grouping changes order of operations and numeric result.",
    },
    "pair-0189": {"coverage_category": "paraphrase"},
    "pair-0190": {"coverage_category": "paraphrase"},
    "pair-0193": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Welcome greeting differs from goodbye closing.",
    },
    "pair-0194": {"coverage_category": "paraphrase"},
    "pair-0195": {"coverage_category": "paraphrase"},
    "pair-0196": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'shorter' depends on unstored multi-turn dialog context.",
    },
    "pair-0199": {"coverage_category": "paraphrase"},
    "pair-0200": {"coverage_category": "paraphrase"},
    "pair-0201": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "United States president differs from United Kingdom prime minister.",
    },
    "pair-0204": {"coverage_category": "paraphrase"},
    "pair-0205": {"coverage_category": "paraphrase"},
    "pair-0209": {"coverage_category": "paraphrase"},
    "pair-0210": {"coverage_category": "paraphrase"},
}

BATCH5_OVERRIDES: dict[str, dict] = {
    "pair-0216": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Thesis statement guidance differs from conclusion paragraph guidance.",
    },
    "pair-0221": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'tell me more' depends on unstored multi-turn dialog context.",
    },
    "pair-0226": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'rewrite it' depends on unstored multi-turn dialog context.",
    },
    "pair-0233": {
        "coverage_category": "constraint_change",
        "failure_category": "constraint_mismatch",
        "reason": "Python 2 versus current Python changes the runtime constraint.",
    },
    "pair-0236": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'how about that?' depends on unstored multi-turn dialog context.",
    },
    "pair-0246": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'what about it?' depends on unstored multi-turn dialog context.",
    },
    "pair-0251": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Baking bread differs from making sourdough starter.",
    },
}

BATCH6_OVERRIDES: dict[str, dict] = {
    "pair-0263": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Affirmative versus negative replies are different intents.",
    },
    "pair-0266": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Sharpening knives differs from storing knives.",
    },
    "pair-0276": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'that's wrong' depends on unstored multi-turn dialog context.",
    },
    "pair-0279": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": "Amex top-up support differs from listing all supported cards.",
    },
    "pair-0296": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'show me' depends on unstored multi-turn dialog context.",
    },
    "pair-0306": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Mutable-default review differs from top-k algorithm review.",
    },
    "pair-0311": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'okay' depends on unstored multi-turn dialog context.",
    },
}

BATCH7_OVERRIDES: dict[str, dict] = {
    "pair-0316": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'more' depends on unstored multi-turn dialog context.",
    },
    "pair-0329": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": "Asking why ID is required differs from refusing identity verification.",
    },
    "pair-0338": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Requesting help differs from requesting no help.",
    },
    "pair-0341": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Fibonacci performance review differs from top-k algorithm review.",
    },
    "pair-0344": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": "Employer transfer eligibility differs from GBP salary handling.",
    },
    "pair-0356": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'redo' depends on unstored multi-turn dialog context.",
    },
    "pair-0361": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'skip' depends on unstored multi-turn dialog context.",
    },
}

BATCH8_OVERRIDES: dict[str, dict] = {
    "pair-0371": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "String-build performance review differs from pandas aggregation review.",
    },
    "pair-0376": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'what about that?' depends on unstored multi-turn dialog context.",
    },
    "pair-0383": {
        "coverage_category": "constraint_change",
        "failure_category": "constraint_mismatch",
        "reason": "Python 2 versus current Python changes the runtime constraint.",
    },
    "pair-0391": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Procrastination advice differs from burnout recovery guidance.",
    },
    "pair-0411": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Public-speaking skill-building differs from stage-fright coping.",
    },
}

BATCH9_OVERRIDES: dict[str, dict] = {
    "pair-0413": {
        "coverage_category": "temporal_freshness",
        "failure_category": "temporal_mismatch",
        "freshness_class": "dynamic",
        "reason": "Current office holder differs from historical office holder.",
    },
    "pair-0416": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Latte art guidance differs from home espresso preparation.",
    },
    "pair-0418": {
        "coverage_category": "constraint_change",
        "failure_category": "constraint_mismatch",
        "reason": "Python 2 versus current Python changes the runtime constraint.",
    },
    "pair-0421": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Installing Python differs from uninstalling Python.",
    },
    "pair-0426": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Boiling an egg differs from poaching an egg.",
    },
    "pair-0431": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'translate it' depends on unstored multi-turn dialog context.",
    },
    "pair-0440": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "constraint_mismatch",
        "coverage_category": "high_similarity_incompatible",
        "reason": "Centimeters-to-inches differs from inches-to-centimeters conversion direction.",
    },
    "pair-0441": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'fix it' depends on unstored multi-turn dialog context.",
    },
    "pair-0456": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Haiku writing differs from sonnet writing.",
    },
    "pair-0461": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'wait' depends on unstored multi-turn dialog context.",
    },
}

BATCH10_OVERRIDES: dict[str, dict] = {
    "pair-0466": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "Telephone invention differs from radio invention.",
    },
    "pair-0471": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Homemade pizza differs from homemade pasta.",
    },
    "pair-0472": {
        "compatibility_label": "compatible",
        "expected_compatibility": "compatible",
        "reusable": True,
        "expected_reuse": True,
        "failure_category": "none",
        "coverage_category": "paraphrase",
        "reason": None,
    },
    "pair-0476": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Treating sunburn differs from preventing sunburn.",
    },
    "pair-0481": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'more detail' depends on unstored multi-turn dialog context.",
    },
    "pair-0486": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "Apple founding differs from Microsoft founding.",
    },
    "pair-0501": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "Smallest country differs from smallest continent.",
    },
    "pair-0503": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Greeting differs from farewell.",
    },
}

BATCH11_OVERRIDES: dict[str, dict] = {
    "pair-0518": {
        "coverage_category": "constraint_change",
        "failure_category": "constraint_mismatch",
        "reason": "TensorFlow 1.x placeholders differ from TensorFlow 2 APIs.",
    },
    "pair-0521": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "16th president differs from 26th president.",
    },
    "pair-0526": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Improving credit score differs from checking a credit report.",
    },
    "pair-0533": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Request to continue differs from request to stop.",
    },
    "pair-0536": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Writing a business plan differs from pitching one.",
    },
    "pair-0541": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'yes' depends on unstored multi-turn dialog context.",
    },
    "pair-0551": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "SQL JOIN guidance differs from SQL GROUP BY guidance.",
    },
    "pair-0556": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Filing taxes for free differs from filing a tax extension.",
    },
}

BATCH12_OVERRIDES: dict[str, dict] = {
    "pair-0566": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'undo' depends on unstored multi-turn dialog context.",
    },
    "pair-0571": {
        "coverage_category": "constraint_change",
        "failure_category": "constraint_mismatch",
        "reason": "Python versus JavaScript changes the language constraint.",
    },
    "pair-0578": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Accepting thanks differs from declining help.",
    },
    "pair-0581": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Top-k algorithm review differs from Fibonacci review.",
    },
    "pair-0586": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'expand on that' depends on unstored multi-turn dialog context.",
    },
    "pair-0591": {
        "coverage_category": "intent_change",
        "failure_category": "intent_mismatch",
        "reason": "Learning guitar differs from learning piano.",
    },
    "pair-0596": {
        "coverage_category": "entity_change",
        "failure_category": "entity_mismatch",
        "reason": "Tallest building worldwide differs from tallest building in NYC.",
    },
    "pair-0599": {
        "compatibility_label": "incompatible",
        "expected_compatibility": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": "Card quantity limits differ from virtual-card delivery timing.",
    },
    "pair-0601": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'next' depends on unstored multi-turn dialog context.",
    },
    "pair-0602": {
        "compatibility_label": "compatible",
        "expected_compatibility": "compatible",
        "reusable": True,
        "expected_reuse": True,
        "failure_category": "none",
        "coverage_category": "paraphrase",
        "reason": None,
    },
    "pair-0606": {
        "compatibility_label": "uncertain",
        "expected_compatibility": "uncertain",
        "reusable": False,
        "expected_reuse": False,
        "failure_category": "insufficient_evidence",
        "coverage_category": "insufficient_evidence",
        "reason": "Identical 'no' depends on unstored multi-turn dialog context.",
    },
}

RANGE_OVERRIDES: dict[tuple[str, str], dict[str, dict]] = {
    ("pair-0033", "pair-0062"): BATCH1_OVERRIDES,
    ("pair-0063", "pair-0112"): BATCH2_OVERRIDES,
    ("pair-0113", "pair-0162"): BATCH3_OVERRIDES,
    ("pair-0163", "pair-0212"): BATCH4_OVERRIDES,
    ("pair-0213", "pair-0262"): BATCH5_OVERRIDES,
    ("pair-0263", "pair-0312"): BATCH6_OVERRIDES,
    ("pair-0313", "pair-0362"): BATCH7_OVERRIDES,
    ("pair-0363", "pair-0412"): BATCH8_OVERRIDES,
    ("pair-0413", "pair-0462"): BATCH9_OVERRIDES,
    ("pair-0463", "pair-0512"): BATCH10_OVERRIDES,
    ("pair-0513", "pair-0562"): BATCH11_OVERRIDES,
    ("pair-0563", "pair-0607"): BATCH12_OVERRIDES,
}


@dataclass(frozen=True)
class ReviewBatch:
    id_start: str
    id_end: str
    overrides: dict[str, dict]
    gap_fill: list[dict] | None = None
    gap_source_group: str = "hand_reviewed_v2:phase3_batch1_gaps"


PRESET_BATCHES: dict[str, ReviewBatch] = {
    "1": ReviewBatch("pair-0033", "pair-0062", BATCH1_OVERRIDES, GAP_FILL_BATCH1),
    "2": ReviewBatch("pair-0063", "pair-0112", BATCH2_OVERRIDES, None),
    "3": ReviewBatch("pair-0113", "pair-0162", BATCH3_OVERRIDES, None),
    "4": ReviewBatch("pair-0163", "pair-0212", BATCH4_OVERRIDES, None),
    "5": ReviewBatch("pair-0213", "pair-0262", BATCH5_OVERRIDES, None),
    "6": ReviewBatch("pair-0263", "pair-0312", BATCH6_OVERRIDES, None),
    "7": ReviewBatch("pair-0313", "pair-0362", BATCH7_OVERRIDES, None),
    "8": ReviewBatch("pair-0363", "pair-0412", BATCH8_OVERRIDES, None),
    "9": ReviewBatch("pair-0413", "pair-0462", BATCH9_OVERRIDES, None),
    "10": ReviewBatch("pair-0463", "pair-0512", BATCH10_OVERRIDES, None),
    "11": ReviewBatch("pair-0513", "pair-0562", BATCH11_OVERRIDES, None),
    "12": ReviewBatch("pair-0563", "pair-0607", BATCH12_OVERRIDES, None),
}


def _in_range(record_id: str, start: str, end: str) -> bool:
    return start <= record_id <= end


def _apply_review(record: BenchmarkRecord, overrides: dict[str, dict]) -> BenchmarkRecord:
    payload = record.model_dump(mode="json")
    payload.update(overrides.get(record.id, {}))
    payload["review_status"] = "final"
    payload["annotation_source"] = "human_review"
    payload["expected_reuse"] = payload["reusable"]
    payload["expected_compatibility"] = payload["compatibility_label"]
    return BenchmarkRecord.model_validate(payload)


def _gap_fill_record(payload: dict, record_id: str, source_group: str) -> BenchmarkRecord:
    full = {
        "schema_version": "1.1",
        "id": record_id,
        "directionality": "ordered",
        "correctness_label": None,
        "answer_availability": "none",
        "review_status": "final",
        "annotation_source": "human_review",
        "source_group": source_group,
        **payload,
    }
    full["expected_reuse"] = full["reusable"]
    full["expected_compatibility"] = full["compatibility_label"]
    return BenchmarkRecord.model_validate(full)


def apply_review_batch(
    input_path: Path,
    output_path: Path,
    batch: ReviewBatch,
    *,
    only_draft: bool = True,
) -> dict:
    records = load_benchmark_jsonl(input_path)
    out: list[BenchmarkRecord] = []
    reviewed = 0
    skipped_final = 0

    for record in records:
        if _in_range(record.id, batch.id_start, batch.id_end):
            if only_draft and record.review_status == "final":
                out.append(record)
                skipped_final += 1
                continue
            updated = _apply_review(record, batch.overrides)
            validate_candidate_record(updated)
            out.append(updated)
            reviewed += 1
        else:
            out.append(record)

    gap_count = 0
    if batch.gap_fill:
        existing_gap_groups = {
            r.source_group for r in out if r.source_group and "phase3_batch1_gaps" in r.source_group
        }
        if not existing_gap_groups:
            used_ids = {record.id for record in out}
            for payload in batch.gap_fill:
                record_id = assign_next_pair_id(used_ids)
                used_ids.add(record_id)
                gap = _gap_fill_record(payload, record_id, batch.gap_source_group)
                validate_candidate_record(gap)
                out.append(gap)
                gap_count += 1

    write_jsonl(output_path, out)

    finals = [r for r in out if r.review_status == "final"]
    compat = Counter(r.compatibility_label for r in finals)
    reusable = Counter(r.reusable for r in finals)
    coverage = Counter(r.coverage_category for r in finals if r.coverage_category)
    freshness = Counter(r.freshness_class for r in finals)
    draft = sum(1 for r in out if r.review_status == "draft")
    disputed = sum(1 for r in out if r.review_status == "disputed")

    return {
        "batch_range": f"{batch.id_start}..{batch.id_end}",
        "output_path": str(output_path),
        "total_rows": len(out),
        "batch_reviewed_final": reviewed,
        "skipped_already_final": skipped_final,
        "gap_fill_added": gap_count,
        "draft_remaining": draft,
        "disputed": disputed,
        "all_finals_compatibility": dict(compat),
        "all_finals_reusable": {str(k): v for k, v in reusable.items()},
        "all_finals_coverage": dict(coverage),
        "all_finals_freshness": dict(freshness),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch",
        choices=sorted(PRESET_BATCHES),
        help="Preset batch (1=gap-fill from draft import, 2–3=review ranges on reviewed file).",
    )
    parser.add_argument("--id-start", help="Override range start (pair-XXXX).")
    parser.add_argument("--id-end", help="Override range end (pair-XXXX).")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl"),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-apply overrides even when review_status is already final.",
    )
    args = parser.parse_args()

    if not args.batch:
        parser.error("--batch is required (1 or 2)")

    preset = PRESET_BATCHES[args.batch]
    id_start = args.id_start or preset.id_start
    id_end = args.id_end or preset.id_end
    overrides = RANGE_OVERRIDES.get((id_start, id_end), preset.overrides)
    batch = ReviewBatch(
        id_start,
        id_end,
        overrides,
        preset.gap_fill if (id_start, id_end) == ("pair-0033", "pair-0062") else None,
        preset.gap_source_group,
    )

    summary = apply_review_batch(
        args.input,
        args.output,
        batch,
        only_draft=not args.force,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
