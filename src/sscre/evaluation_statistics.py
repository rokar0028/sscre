"""Versioned evaluation statistics schema and interval policy (Workstream 5)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from math import erfc, sqrt
from typing import Any, Literal, Mapping, Sequence

EVALUATION_STATISTICS_SCHEMA_VERSION = "evaluation-statistics-1.0"

IntervalMethod = Literal[
    "wilson",
    "clopper_pearson",
    "bootstrap_percentile",
    "unavailable",
]

PROPORTION_INTERVAL_METHODS: frozenset[str] = frozenset({"wilson", "clopper_pearson"})
DISTRIBUTION_INTERVAL_METHODS: frozenset[str] = frozenset({"bootstrap_percentile"})
ALLOWED_INTERVAL_METHODS: frozenset[str] = (
    PROPORTION_INTERVAL_METHODS | DISTRIBUTION_INTERVAL_METHODS | frozenset({"unavailable"})
)

DEFAULT_CONFIDENCE_LEVEL = 0.95
DEFAULT_BOOTSTRAP_SEED = 42
DEFAULT_BOOTSTRAP_ITERATIONS = 1000
MIN_BOOTSTRAP_ITERATIONS_FOR_TESTS = 1000
RECOMMENDED_BOOTSTRAP_ITERATIONS_HELD_OUT = 10000
DEFAULT_PROPORTION_INTERVAL_METHOD = "wilson"
DEFAULT_MINIMUM_N_PROPORTION = 1
DEFAULT_MINIMUM_N_BOOTSTRAP = 5
CLOPPER_PEARSON_MAX_N = 2048

# Documented policy: which method applies to each metric class in WS5 reports.
INTERVAL_METHOD_POLICY: dict[str, str] = {
    "proportion_metrics": DEFAULT_PROPORTION_INTERVAL_METHOD,
    "distribution_metrics": "bootstrap_percentile",
}

# Phase 2 upper bound: 500 pairs × 2 directions, plus headroom for sweeps.
MAX_BASELINE_REQUEST_SAMPLES = 2000

RequestDirection = Literal["a_to_b", "b_to_a"]


@dataclass(frozen=True)
class StatisticsConfig:
    confidence_level: float
    bootstrap_seed: int
    bootstrap_iterations: int
    proportion_interval_method: IntervalMethod
    minimum_n_proportion: int
    minimum_n_bootstrap: int

    def interval_methods_metadata(self) -> dict[str, str]:
        return {
            "proportion_metrics": self.proportion_interval_method,
            "distribution_metrics": "bootstrap_percentile",
        }

    def to_report_metadata(self) -> dict[str, Any]:
        return {
            "statistics_schema_version": EVALUATION_STATISTICS_SCHEMA_VERSION,
            "confidence_level": self.confidence_level,
            "random_seed": self.bootstrap_seed,
            "bootstrap_iterations": self.bootstrap_iterations,
            "interval_methods": self.interval_methods_metadata(),
            "minimum_n_proportion": self.minimum_n_proportion,
            "minimum_n_bootstrap": self.minimum_n_bootstrap,
        }


def apply_statistics_config_defaults(config: dict[str, Any]) -> None:
    """Validate and normalize statistics keys on an evaluation config dict."""
    confidence_level = config.get("confidence_level", DEFAULT_CONFIDENCE_LEVEL)
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not 0.0 < confidence_level < 1.0
    ):
        raise ValueError("confidence_level must be a finite number between 0 and 1")
    config["confidence_level"] = float(confidence_level)

    bootstrap_seed = config.get("bootstrap_seed", DEFAULT_BOOTSTRAP_SEED)
    if isinstance(bootstrap_seed, bool) or not isinstance(bootstrap_seed, int):
        raise ValueError("bootstrap_seed must be an integer")
    config["bootstrap_seed"] = bootstrap_seed

    bootstrap_iterations = config.get(
        "bootstrap_iterations", DEFAULT_BOOTSTRAP_ITERATIONS
    )
    if (
        isinstance(bootstrap_iterations, bool)
        or not isinstance(bootstrap_iterations, int)
        or bootstrap_iterations < MIN_BOOTSTRAP_ITERATIONS_FOR_TESTS
    ):
        raise ValueError(
            "bootstrap_iterations must be an integer "
            f">= {MIN_BOOTSTRAP_ITERATIONS_FOR_TESTS}"
        )
    config["bootstrap_iterations"] = bootstrap_iterations

    proportion_method = config.get(
        "proportion_interval_method", DEFAULT_PROPORTION_INTERVAL_METHOD
    )
    if proportion_method not in PROPORTION_INTERVAL_METHODS:
        raise ValueError(
            "proportion_interval_method must be one of "
            f"{sorted(PROPORTION_INTERVAL_METHODS)}"
        )
    config["proportion_interval_method"] = proportion_method

    minimum_n_proportion = config.get(
        "minimum_n_proportion", DEFAULT_MINIMUM_N_PROPORTION
    )
    if (
        isinstance(minimum_n_proportion, bool)
        or not isinstance(minimum_n_proportion, int)
        or minimum_n_proportion < 1
    ):
        raise ValueError("minimum_n_proportion must be a positive integer")
    config["minimum_n_proportion"] = minimum_n_proportion

    minimum_n_bootstrap = config.get("minimum_n_bootstrap", DEFAULT_MINIMUM_N_BOOTSTRAP)
    if (
        isinstance(minimum_n_bootstrap, bool)
        or not isinstance(minimum_n_bootstrap, int)
        or minimum_n_bootstrap < 2
    ):
        raise ValueError("minimum_n_bootstrap must be an integer >= 2")
    config["minimum_n_bootstrap"] = minimum_n_bootstrap


def statistics_config_from_mapping(config: Mapping[str, Any]) -> StatisticsConfig:
    merged = dict(config)
    apply_statistics_config_defaults(merged)
    return StatisticsConfig(
        confidence_level=merged["confidence_level"],
        bootstrap_seed=merged["bootstrap_seed"],
        bootstrap_iterations=merged["bootstrap_iterations"],
        proportion_interval_method=merged["proportion_interval_method"],
        minimum_n_proportion=merged["minimum_n_proportion"],
        minimum_n_bootstrap=merged["minimum_n_bootstrap"],
    )


def attach_evaluation_statistics_schema(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Attach schema version and validate an optional statistics block."""
    result = dict(payload)
    statistics = result.get("statistics")
    if statistics is not None:
        validate_statistics_block(statistics)
        result["statistics_schema_version"] = EVALUATION_STATISTICS_SCHEMA_VERSION
    return result


def validate_statistics_block(statistics: object) -> None:
    if not isinstance(statistics, Mapping):
        raise ValueError("statistics must be an object")
    _validate_interval_nodes(statistics)


def _validate_interval_nodes(node: object) -> None:
    if isinstance(node, Mapping):
        if _looks_like_interval(node):
            validate_interval_dict(node)
        for value in node.values():
            _validate_interval_nodes(value)
        return
    if isinstance(node, list):
        for item in node:
            _validate_interval_nodes(item)


def _looks_like_interval(node: Mapping[str, object]) -> bool:
    return "method" in node and "point" in node


def validate_interval_dict(interval: Mapping[str, Any]) -> None:
    method = interval.get("method")
    if method not in ALLOWED_INTERVAL_METHODS:
        raise ValueError(f"interval method must be one of {sorted(ALLOWED_INTERVAL_METHODS)}")

    confidence_level = interval.get("confidence_level")
    if confidence_level is not None:
        if (
            isinstance(confidence_level, bool)
            or not isinstance(confidence_level, (int, float))
            or not math.isfinite(confidence_level)
            or not 0.0 < confidence_level < 1.0
        ):
            raise ValueError("confidence_level must be between 0 and 1")

    n = interval.get("n")
    if n is not None and (
        isinstance(n, bool) or not isinstance(n, int) or n < 0
    ):
        raise ValueError("interval n must be a non-negative integer")

    point = interval.get("point")
    lower = interval.get("lower")
    upper = interval.get("upper")

    if method == "unavailable":
        if lower is not None or upper is not None:
            if lower is not None and (
                not isinstance(lower, (int, float)) or not math.isfinite(lower)
            ):
                raise ValueError("interval lower must be finite or null")
            if upper is not None and (
                not isinstance(upper, (int, float)) or not math.isfinite(upper)
            ):
                raise ValueError("interval upper must be finite or null")
        if point is not None and (
            isinstance(point, bool)
            or not isinstance(point, (int, float))
            or not math.isfinite(point)
        ):
            raise ValueError("interval point must be finite when present")
        return

    for name, value in (("point", point), ("lower", lower), ("upper", upper)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"interval {name} must be a finite number")
    if float(lower) > float(point) or float(point) > float(upper):
        raise ValueError("interval must satisfy lower <= point <= upper")
    if float(lower) > float(upper):
        raise ValueError("interval lower must not exceed upper")


def interval_to_dict(
    *,
    point: float,
    lower: float,
    upper: float,
    method: IntervalMethod,
    n: int,
    confidence_level: float,
    reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "point": point,
        "lower": lower,
        "upper": upper,
        "method": method,
        "n": n,
        "confidence_level": confidence_level,
    }
    if reason is not None:
        payload["reason"] = reason
    validate_interval_dict(payload)
    return payload


def unavailable_interval(
    *,
    point: float | None,
    n: int,
    confidence_level: float,
    reason: str,
) -> dict[str, Any]:
    if point is not None and (
        isinstance(point, bool)
        or not isinstance(point, (int, float))
        or not math.isfinite(point)
    ):
        raise ValueError("unavailable interval point must be finite or omitted")
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("unavailable interval n must be a non-negative integer")
    payload: dict[str, Any] = {
        "point": point,
        "lower": None,
        "upper": None,
        "method": "unavailable",
        "n": n,
        "confidence_level": confidence_level,
        "reason": reason,
    }
    validate_interval_dict(payload)
    return payload


def _z_critical(confidence_level: float) -> float:
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1")
    tail = 1.0 - confidence_level
    return _normal_ppf(1.0 - tail / 2.0)


def _normal_ppf(probability: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be between 0 and 1")
    low = -8.0
    high = 8.0
    for _ in range(64):
        mid = (low + high) / 2.0
        cdf = 0.5 * erfc(-mid / sqrt(2.0))
        if cdf < probability:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def wilson_score_interval(
    successes: int,
    n: int,
    *,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> tuple[float, float, float]:
    """Return (point, lower, upper) for a binomial proportion."""
    if isinstance(successes, bool) or not isinstance(successes, int) or successes < 0:
        raise ValueError("successes must be a non-negative integer")
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    if successes > n:
        raise ValueError("successes must not exceed n")
    if n == 0:
        raise ValueError("n must be positive for wilson_score_interval")

    point = successes / n
    if n == 1:
        return point, 0.0, 1.0

    z = _z_critical(confidence_level)
    z2 = z * z
    denominator = 1.0 + z2 / n
    center = (point + z2 / (2.0 * n)) / denominator
    margin = (
        z
        * sqrt((point * (1.0 - point) / n) + (z2 / (4.0 * n * n)))
        / denominator
    )
    lower = min(point, max(0.0, center - margin))
    upper = max(point, min(1.0, center + margin))
    if lower > upper:
        raise ValueError("computed wilson interval is inverted")
    return point, lower, upper


def proportion_interval(
    successes: int,
    n: int,
    settings: StatisticsConfig,
) -> dict[str, Any]:
    if n < settings.minimum_n_proportion:
        point = successes / n if n else 0.0
        return unavailable_interval(
            point=point if n else None,
            n=n,
            confidence_level=settings.confidence_level,
            reason="n_below_minimum_proportion",
        )
    if n == 0:
        return unavailable_interval(
            point=None,
            n=0,
            confidence_level=settings.confidence_level,
            reason="empty_sample",
        )
    if settings.proportion_interval_method == "clopper_pearson":
        point, lower, upper = clopper_pearson_interval(
            successes,
            n,
            confidence_level=settings.confidence_level,
        )
        method: IntervalMethod = "clopper_pearson"
    else:
        point, lower, upper = wilson_score_interval(
            successes,
            n,
            confidence_level=settings.confidence_level,
        )
        method = "wilson"
    return interval_to_dict(
        point=point,
        lower=lower,
        upper=upper,
        method=method,
        n=n,
        confidence_level=settings.confidence_level,
    )


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _beta_cdf(x: float, a: float, b: float, *, steps: int = 256) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    width = x / steps
    total = 0.0
    previous = 0.0
    for step in range(steps + 1):
        t = x * step / steps
        if t <= 0.0 or t >= 1.0:
            weight = 0.5 if step in (0, steps) else 1.0
            value = 0.0
        else:
            weight = 0.5 if step in (0, steps) else 1.0
            value = math.exp((a - 1) * math.log(t) + (b - 1) * math.log(1.0 - t) - _log_beta(a, b))
        total += weight * value
        previous = value
    _ = previous
    return total * width


def _beta_quantile(probability: float, a: float, b: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be between 0 and 1")
    lo = 0.0
    hi = 1.0
    for _ in range(64):
        mid = (lo + hi) / 2.0
        if _beta_cdf(mid, a, b) < probability:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def clopper_pearson_interval(
    successes: int,
    n: int,
    *,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> tuple[float, float, float]:
    """Exact binomial (Clopper–Pearson) interval via Beta quantiles."""
    if isinstance(successes, bool) or not isinstance(successes, int) or successes < 0:
        raise ValueError("successes must be a non-negative integer")
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError("n must be a positive integer")
    if successes > n:
        raise ValueError("successes must not exceed n")
    if n > CLOPPER_PEARSON_MAX_N:
        raise ValueError(
            f"n must be <= {CLOPPER_PEARSON_MAX_N} for exact clopper_pearson"
        )

    point = successes / n
    tail = 1.0 - confidence_level
    alpha_half = tail / 2.0

    if successes == 0:
        lower = 0.0
    else:
        lower = _beta_quantile(alpha_half, float(successes), float(n - successes + 1))

    if successes == n:
        upper = 1.0
    else:
        upper = _beta_quantile(
            1.0 - alpha_half,
            float(successes + 1),
            float(n - successes),
        )

    lower = max(0.0, min(1.0, lower))
    upper = max(0.0, min(1.0, upper))
    if lower > upper:
        raise ValueError("computed clopper_pearson interval is inverted")
    return point, lower, upper


def _percentile_of_values(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _validate_bootstrap_samples(samples: Sequence[float]) -> None:
    for value in samples:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("bootstrap samples must be finite numbers")


@dataclass
class BootstrapResampler:
    """Seeded bootstrap engine; one instance shares RNG state across metrics."""

    settings: StatisticsConfig

    def __post_init__(self) -> None:
        object.__setattr__(self, "_rng", random.Random(self.settings.bootstrap_seed))

    def percentile_interval(
        self,
        samples: Sequence[float],
        *,
        statistic: Literal["mean", "quantile"] = "mean",
        quantile: float = 0.5,
    ) -> dict[str, Any]:
        n = len(samples)
        if n < self.settings.minimum_n_bootstrap:
            point: float | None
            if statistic == "mean":
                point = sum(samples) / n if n else 0.0
            elif n:
                point = _percentile_of_values(samples, quantile)
            else:
                point = None
            return unavailable_interval(
                point=point,
                n=n,
                confidence_level=self.settings.confidence_level,
                reason="n_below_minimum_bootstrap",
            )
        _validate_bootstrap_samples(samples)

        indexed = [float(value) for value in samples]
        if statistic == "mean":
            point = sum(indexed) / n

            def resampled_statistic(draw: list[float]) -> float:
                return sum(draw) / len(draw)

        elif statistic == "quantile":
            if not 0.0 <= quantile <= 1.0:
                raise ValueError("quantile must be between 0 and 1")
            point = _percentile_of_values(indexed, quantile)

            def resampled_statistic(draw: list[float]) -> float:
                return _percentile_of_values(draw, quantile)

        else:
            raise ValueError("statistic must be mean or quantile")

        boot_stats: list[float] = []
        for _ in range(self.settings.bootstrap_iterations):
            draw = [indexed[self._rng.randrange(n)] for _ in range(n)]
            boot_stats.append(resampled_statistic(draw))
        boot_stats.sort()
        alpha = 1.0 - self.settings.confidence_level
        lower_index = int((alpha / 2.0) * self.settings.bootstrap_iterations)
        upper_index = int((1.0 - alpha / 2.0) * self.settings.bootstrap_iterations) - 1
        lower_index = max(0, min(lower_index, self.settings.bootstrap_iterations - 1))
        upper_index = max(0, min(upper_index, self.settings.bootstrap_iterations - 1))
        lower = min(boot_stats[lower_index], point)
        upper = max(boot_stats[upper_index], point)
        return interval_to_dict(
            point=point,
            lower=lower,
            upper=upper,
            method="bootstrap_percentile",
            n=n,
            confidence_level=self.settings.confidence_level,
        )


def bootstrap_percentile_interval(
    samples: Sequence[float],
    settings: StatisticsConfig,
    *,
    statistic: Literal["mean", "quantile"] = "mean",
    quantile: float = 0.5,
    resampler: BootstrapResampler | None = None,
) -> dict[str, Any]:
    engine = resampler or BootstrapResampler(settings)
    return engine.percentile_interval(
        samples,
        statistic=statistic,
        quantile=quantile,
    )


def _sample_indicator(values: Sequence[Mapping[str, object]], key: str) -> list[int]:
    indicators: list[int] = []
    for row in values:
        raw = row.get(key)
        if raw is None and key == "unlabeled_candidate_reuse":
            raw = 0
        if raw not in (0, 1):
            raise ValueError(f"sample field {key!r} must be 0 or 1")
        indicators.append(int(raw))
    return indicators


def _proportion_from_indicators(
    indicators: Sequence[int],
    settings: StatisticsConfig,
) -> dict[str, Any]:
    n = len(indicators)
    if n == 0:
        return unavailable_interval(
            point=None,
            n=0,
            confidence_level=settings.confidence_level,
            reason="empty_sample",
        )
    return proportion_interval(sum(indicators), n, settings)


def summarize_request_sample_statistics(
    samples: Sequence[Mapping[str, object]],
    settings: StatisticsConfig,
    *,
    resampler: BootstrapResampler | None = None,
    include_strata: bool = True,
) -> dict[str, Any]:
    """Compute proportion and distribution intervals from request_samples rows."""
    bootstrap = resampler or BootstrapResampler(settings)
    n = len(samples)
    metadata = settings.to_report_metadata()
    metadata["sample_unit"] = "directed_request"
    metadata["sample_count"] = n

    if n == 0:
        summary = {
            **metadata,
            "proportions": {},
            "distributions": {},
        }
        if include_strata:
            summary["strata"] = {
                "by_failure_category": {},
                "by_freshness_class": {},
            }
        return summary

    cache_hits = _sample_indicator(samples, "cache_hit")
    false_positives = _sample_indicator(samples, "false_positive")
    safe_reuse_hits = _sample_indicator(samples, "safe_reuse_hit")

    b_to_a_indices = [
        index
        for index, row in enumerate(samples)
        if row.get("direction") == "b_to_a"
    ]
    b_to_a_safe = [safe_reuse_hits[index] for index in b_to_a_indices]

    hit_total = sum(cache_hits)
    proportions: dict[str, Any] = {
        "hit_rate": _proportion_from_indicators(cache_hits, settings),
        "safe_reuse_coverage": (
            proportion_interval(sum(b_to_a_safe), len(b_to_a_indices), settings)
            if b_to_a_indices
            else unavailable_interval(
                point=None,
                n=0,
                confidence_level=settings.confidence_level,
                reason="no_b_to_a_samples",
            )
        ),
    }

    unlabeled_reuse = _sample_indicator(samples, "unlabeled_candidate_reuse")
    labeled_hit_indices = [
        index
        for index, hit in enumerate(cache_hits)
        if hit == 1 and unlabeled_reuse[index] == 0
    ]
    if labeled_hit_indices:
        fp_among_labeled_hits = [false_positives[index] for index in labeled_hit_indices]
        proportions["false_positive_rate"] = _proportion_from_indicators(
            fp_among_labeled_hits,
            settings,
        )
    elif hit_total > 0:
        proportions["false_positive_rate"] = unavailable_interval(
            point=None,
            n=0,
            confidence_level=settings.confidence_level,
            reason="no_labeled_reuse_hits",
        )
    if hit_total > 0:
        fp_among_hits = [
            false_positives[index]
            for index, hit in enumerate(cache_hits)
            if hit == 1
        ]
        proportions["false_positive_rate_among_all_hits"] = _proportion_from_indicators(
            fp_among_hits,
            settings,
        )
        safe_on_served = [
            safe_reuse_hits[index]
            for index, hit in enumerate(cache_hits)
            if hit == 1
        ]
        proportions["precision_of_served_reuse"] = _proportion_from_indicators(
            safe_on_served,
            settings,
        )

    decision_rows = [
        row
        for row in samples
        if isinstance(row.get("observed_decision"), str)
    ]
    if decision_rows:
        decision_n = len(decision_rows)
        for decision in ("SAFE", "UNSAFE", "UNCERTAIN"):
            count = sum(
                1 for row in decision_rows if row.get("observed_decision") == decision
            )
            proportions[f"decision_rate_{decision.lower()}"] = proportion_interval(
                count,
                decision_n,
                settings,
            )

    latencies = [float(row["latency_ms"]) for row in samples]
    costs = [float(row["estimated_cost_usd"]) for row in samples]
    token_totals = [
        float(
            int(row["embedding_tokens"])
            + int(row["generation_input_tokens"])
            + int(row["generation_output_tokens"])
        )
        for row in samples
    ]

    distributions: dict[str, Any] = {
        "latency_ms_mean": bootstrap.percentile_interval(
            latencies,
            statistic="mean",
        ),
        "latency_ms_p50": bootstrap.percentile_interval(
            latencies,
            statistic="quantile",
            quantile=0.5,
        ),
        "latency_ms_p95": bootstrap.percentile_interval(
            latencies,
            statistic="quantile",
            quantile=0.95,
        ),
        "latency_ms_p99": bootstrap.percentile_interval(
            latencies,
            statistic="quantile",
            quantile=0.99,
        ),
        "estimated_cost_usd_mean": bootstrap.percentile_interval(
            costs,
            statistic="mean",
        ),
        "request_tokens_mean": bootstrap.percentile_interval(
            token_totals,
            statistic="mean",
        ),
    }

    summary = {
        **metadata,
        "proportions": proportions,
        "distributions": distributions,
    }
    if include_strata:
        summary["strata"] = {
            "by_failure_category": _summarize_strata(
                samples,
                "failure_category",
                settings,
                bootstrap,
            ),
            "by_freshness_class": _summarize_strata(
                samples,
                "freshness_class",
                settings,
                bootstrap,
            ),
        }
    return summary


def _summarize_strata(
    samples: Sequence[Mapping[str, object]],
    field: str,
    settings: StatisticsConfig,
    resampler: BootstrapResampler,
) -> dict[str, dict[str, Any]]:
    """Summarize each observed benchmark stratum without fabricating empty rows."""
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for sample in samples:
        value = sample.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(f"sample field {field!r} must be a non-empty string")
        grouped.setdefault(value, []).append(sample)

    return {
        label: summarize_request_sample_statistics(
            rows,
            settings,
            resampler=resampler,
            include_strata=False,
        )
        for label, rows in grouped.items()
    }


def summarize_evaluation_label_metrics(
    report_payload: Mapping[str, object],
) -> dict[str, object]:
    """Summarize independent correctness and preference labels by answer path."""
    raw_rows = report_payload.get("observed_pair_records")
    if not isinstance(raw_rows, list):
        return {}

    correctness: dict[str, dict[str, int]] = {}
    for path in ("cached_answer", "generated_answer"):
        counts = {
            "correct": 0,
            "incorrect": 0,
            "uncertain": 0,
            "not_collected": 0,
        }
        for row in raw_rows:
            labels = row.get("evaluation_labels") if isinstance(row, Mapping) else None
            correctness_labels = (
                labels.get("correctness") if isinstance(labels, Mapping) else None
            )
            value = (
                correctness_labels.get(path)
                if isinstance(correctness_labels, Mapping)
                else None
            )
            bucket = value if isinstance(value, str) and value in counts else "not_collected"
            counts[bucket] += 1
        correctness[path] = counts

    preference_counts = {"cached": 0, "generated": 0, "tie": 0, "not_collected": 0}
    applicable_count = 0
    for row in raw_rows:
        labels = row.get("evaluation_labels") if isinstance(row, Mapping) else None
        preference = labels.get("preference") if isinstance(labels, Mapping) else None
        winner = preference.get("winner") if isinstance(preference, Mapping) else None
        bucket = (
            winner
            if isinstance(winner, str) and winner in preference_counts
            else "not_collected"
        )
        preference_counts[bucket] += 1
        if isinstance(preference, Mapping) and preference.get("applicable") is True:
            applicable_count += 1

    return {
        "sample_unit": "reviewed_pair",
        "sample_count": len(raw_rows),
        "correctness": correctness,
        "preference": {
            "winner_counts": preference_counts,
            "applicable_count": applicable_count,
        },
    }


@dataclass(frozen=True)
class RequestObservationSample:
    """One directed replay observation for bootstrap and proportion CIs."""

    pair_id: str
    direction: RequestDirection
    cache_hit: int
    generated: int
    false_positive: int
    safe_reuse_hit: int
    unlabeled_candidate_reuse: int
    latency_ms: float
    embedding_tokens: int
    generation_input_tokens: int
    generation_output_tokens: int
    estimated_cost_usd: float
    observed_decision: str | None = None
    failure_category: str | None = None
    freshness_class: str | None = None
    runtime_temporal_class: str | None = None
    served_candidate_provenance: dict[str, object] | None = None

    def __post_init__(self) -> None:
        for name in (
            "cache_hit",
            "generated",
            "false_positive",
            "safe_reuse_hit",
            "unlabeled_candidate_reuse",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or value not in (0, 1):
                raise ValueError(f"{name} must be 0 or 1")
        if not math.isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency_ms must be a finite non-negative number")
        for name in (
            "embedding_tokens",
            "generation_input_tokens",
            "generation_output_tokens",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            isinstance(self.estimated_cost_usd, bool)
            or not isinstance(self.estimated_cost_usd, (int, float))
            or not math.isfinite(self.estimated_cost_usd)
            or self.estimated_cost_usd < 0
        ):
            raise ValueError("estimated_cost_usd must be a finite non-negative number")
        if self.observed_decision is not None and self.observed_decision not in (
            "SAFE",
            "UNSAFE",
            "UNCERTAIN",
        ):
            raise ValueError("observed_decision must be SAFE, UNSAFE, UNCERTAIN, or null")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "pair_id": self.pair_id,
            "direction": self.direction,
            "cache_hit": self.cache_hit,
            "generated": self.generated,
            "false_positive": self.false_positive,
            "safe_reuse_hit": self.safe_reuse_hit,
            "unlabeled_candidate_reuse": self.unlabeled_candidate_reuse,
            "latency_ms": self.latency_ms,
            "embedding_tokens": self.embedding_tokens,
            "generation_input_tokens": self.generation_input_tokens,
            "generation_output_tokens": self.generation_output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }
        if self.observed_decision is not None:
            payload["observed_decision"] = self.observed_decision
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category
        if self.freshness_class is not None:
            payload["freshness_class"] = self.freshness_class
        if self.runtime_temporal_class is not None:
            payload["runtime_temporal_class"] = self.runtime_temporal_class
        if self.served_candidate_provenance is not None:
            payload["served_candidate_provenance"] = self.served_candidate_provenance
        return payload


class RequestSampleCollector:
    """Collect bounded request-level samples in deterministic replay order."""

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._samples: list[dict[str, object]] = []

    def __len__(self) -> int:
        return len(self._samples)

    def record(self, sample: RequestObservationSample) -> None:
        if not self._enabled:
            return
        if len(self._samples) >= MAX_BASELINE_REQUEST_SAMPLES:
            raise ValueError("request sample count exceeds the Phase 2 bound")
        self._samples.append(sample.to_dict())

    def as_tuple(self) -> tuple[dict[str, object], ...]:
        return tuple(self._samples)


def estimate_request_observation_cost_usd(
    *,
    generation_input_tokens: int,
    generation_output_tokens: int,
    embedding_tokens: int,
    input_cost_per_1k_tokens: float,
    output_cost_per_1k_tokens: float,
    embedding_cost_per_1k_tokens: float,
    cache_lookup_cost_usd: float,
    preprocessing_cost_usd: float,
) -> float:
    return round(
        generation_input_tokens * input_cost_per_1k_tokens / 1000.0
        + generation_output_tokens * output_cost_per_1k_tokens / 1000.0
        + embedding_tokens * embedding_cost_per_1k_tokens / 1000.0
        + cache_lookup_cost_usd
        + preprocessing_cost_usd,
        6,
    )


def enrich_evaluation_payload(
    payload: Mapping[str, object],
    evaluation_config: Mapping[str, Any] | None,
    *,
    attach_statistics: bool = True,
) -> dict[str, object]:
    """Attach synthetic-replay statistics to a single baseline report payload."""
    result = dict(payload)
    if not attach_statistics or evaluation_config is None:
        return result

    settings = statistics_config_from_mapping(dict(evaluation_config))
    result["measurement_environment"] = "synthetic_replay"
    baseline_name = result.get("baseline")
    if baseline_name == "embedding-cache-threshold-sweep":
        reports = result.get("reports")
        if not isinstance(reports, list):
            return result
        resampler = BootstrapResampler(settings)
        by_threshold: list[dict[str, object]] = []
        for entry in reports:
            if not isinstance(entry, Mapping):
                continue
            samples = entry.get("request_samples", ())
            if not isinstance(samples, (list, tuple)):
                continue
            by_threshold.append(
                {
                    "threshold": entry.get("threshold"),
                    "statistics": summarize_request_sample_statistics(
                        samples,
                        settings,
                        resampler=resampler,
                    ),
                }
            )
        result["statistics"] = {
            "statistics_schema_version": EVALUATION_STATISTICS_SCHEMA_VERSION,
            "sample_unit": "directed_request",
            "selection_rule": result.get("selection_rule"),
            "selected_threshold": result.get("selected_threshold"),
            "by_threshold": by_threshold,
        }
        return result

    samples = result.get("request_samples", ())
    if isinstance(samples, (list, tuple)) and samples:
        summary = summarize_request_sample_statistics(samples, settings)
        label_metrics = summarize_evaluation_label_metrics(result)
        if label_metrics:
            summary["label_metrics"] = label_metrics
        result["statistics"] = summary
    return result


def build_comparison_statistics(
    baseline_payloads: Mapping[str, Mapping[str, object]],
    evaluation_config: Mapping[str, Any],
    *,
    selected_threshold: float,
    selection_rule: str,
    max_false_positive_rate: float,
) -> dict[str, object]:
    """Build comparison-level statistics for `--baseline all` reports."""
    settings = statistics_config_from_mapping(dict(evaluation_config))
    resampler = BootstrapResampler(settings)
    by_baseline: dict[str, object] = {}
    for name, report_payload in baseline_payloads.items():
        samples = report_payload.get("request_samples", ())
        if not isinstance(samples, (list, tuple)):
            samples = ()
        by_baseline[name] = summarize_request_sample_statistics(
            samples,
            settings,
            resampler=resampler,
        )
        label_metrics = summarize_evaluation_label_metrics(report_payload)
        if label_metrics:
            by_baseline[name]["label_metrics"] = label_metrics
    overall = by_baseline.get("compatibility-cache", {})
    compatibility_payload = baseline_payloads.get("compatibility-cache", {})
    observed_false_positive_rate = compatibility_payload.get("false_positive_rate")
    unavailable_reason = compatibility_payload.get(
        "false_positive_rate_unavailable_reason"
    )
    if observed_false_positive_rate is None:
        if not isinstance(unavailable_reason, str) or not unavailable_reason:
            raise ValueError(
                "compatibility baseline requires false_positive_rate or "
                "false_positive_rate_unavailable_reason"
            )
        observed_for_constraint = math.inf
    elif (
        isinstance(observed_false_positive_rate, bool)
        or not isinstance(observed_false_positive_rate, (int, float))
        or not math.isfinite(observed_false_positive_rate)
    ):
        raise ValueError(
            "compatibility baseline requires a finite false_positive_rate"
        )
    else:
        observed_for_constraint = float(observed_false_positive_rate)
    return {
        "statistics_schema_version": EVALUATION_STATISTICS_SCHEMA_VERSION,
        "measurement_environment": "synthetic_replay",
        "sample_unit": "directed_request",
        "operating_point": {
            "baseline": "compatibility-cache",
            "selected_threshold": selected_threshold,
            "selection_rule": selection_rule,
            "max_false_positive_rate": max_false_positive_rate,
            "observed_false_positive_rate": observed_false_positive_rate,
            "observed_false_positive_rate_unavailable_reason": unavailable_reason,
            "constraint_satisfied": (
                observed_for_constraint <= max_false_positive_rate
            ),
        },
        "overall": overall,
        "by_baseline": by_baseline,
    }


def reuse_outcome_indicators(
    *,
    direction: RequestDirection,
    reusable: bool,
    served_reuse: bool,
) -> tuple[int, int]:
    """Legacy request-record reuse scoring.

    Baseline replay uses ``evaluation_attribution.attribute_served_reuse_outcome``.
    """
    if direction != "b_to_a" or not served_reuse:
        return 0, 0
    if reusable:
        return 0, 1
    return 1, 0
