"""Deterministic query metadata extraction for the safety engine."""

import re

from sscre.safety import MAX_METADATA_ENTITIES, QueryMetadata

_INTENT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("code", r"\b(code|program|script|implement|function|snippet)\b"),
    ("compare", r"\b(compare|comparison|versus|vs\.?|difference)\b"),
    ("summarize", r"\b(summarize|summary|outline|key points)\b"),
    ("explain", r"\b(explain|description|describe|how does|why does)\b"),
    ("factual", r"\b(what is|what are|who|when|where|which|how many|how much)\b"),
)
_FORMAT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("json", r"\bjson\b"),
    ("table", r"\b(table|tabular)\b"),
    ("list", r"\b(list|bullet points|bullets)\b"),
    ("code", r"\b(code|program|script|function|snippet|implement)\b"),
    ("prose", r"\b(prose|paragraph|plain text)\b"),
)
_LANGUAGE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("c++", r"(?<!\w)c\+\+(?!\w)"),
    ("c#", r"(?<!\w)c#(?!\w)"),
    ("javascript", r"\b(javascript|js)\b"),
    ("typescript", r"\btypescript\b"),
    ("python", r"\bpython\b"),
    ("java", r"\bjava\b"),
    ("sql", r"\bsql\b"),
    ("go", r"\bgo\b"),
    ("rust", r"\brust\b"),
    ("neutral", r"\b(language[- ]neutral|language agnostic)\b"),
)
_AUDIENCE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("beginner", r"\b(beginner|beginners|novice)\b"),
    ("expert", r"\b(expert|advanced|technical)\b"),
    ("children", r"\b(child|children|kids)\b"),
)
_PLATFORM_PATTERNS: tuple[tuple[str, str], ...] = (
    ("windows", r"\bwindows\b"),
    ("linux", r"\blinux\b"),
    ("macos", r"\b(mac\s?os|osx)\b"),
    ("android", r"\bandroid\b"),
    ("ios", r"\bios\b"),
    ("web", r"\b(web|browser)\b"),
)
_LIBRARY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("django", r"\bdjango\b"),
    ("fastapi", r"\bfastapi\b"),
    ("numpy", r"\bnumpy\b"),
    ("pandas", r"\bpandas\b"),
    ("react", r"\breact\b"),
)
_VERSION_PATTERN = r"\b(?:version|v)\s*(\d+(?:\.\d+){0,2})\b"
_DYNAMIC_TEMPORAL_PATTERN = (
    r"\b(now|today|current|latest|live|real[- ]time|right now|at present)\b"
)
_SEMI_DYNAMIC_TEMPORAL_PATTERN = (
    r"\b(recent|recently|this week|this month|this year|updated)\b"
)
_PROGRAMMING_DOMAIN_TERMS = (
    "algorithm",
    "api",
    "cache",
    "code",
    "database",
    "function",
    "program",
    "programming",
    "query",
)
_FINANCE_DOMAIN_TERMS = (
    "bank",
    "finance",
    "investment",
    "price",
    "revenue",
    "stock",
    "trading",
)
_KNOWN_ENTITIES = (
    "aws lambda",
    "azure functions",
    "binary search",
    "postgresql",
    "sqlite",
    "kubernetes",
    "docker",
)


def _classify_signal(
    text: str,
    patterns: tuple[tuple[str, str], ...],
) -> str:
    matches = {
        value for value, pattern in patterns if re.search(pattern, text)
    }
    if len(matches) == 1:
        return matches.pop()
    return "unknown"


def _extract_constraint(
    text: str,
    patterns: tuple[tuple[str, str], ...],
) -> str | None:
    return _classify_signal(text, patterns) if sum(
        bool(re.search(pattern, text)) for _, pattern in patterns
    ) == 1 else None


def _extract_version(text: str) -> str | None:
    versions = re.findall(_VERSION_PATTERN, text)
    return versions[0] if len(set(versions)) == 1 else None


def _classify_temporal(text: str) -> str:
    if re.search(_DYNAMIC_TEMPORAL_PATTERN, text):
        return "dynamic"
    if re.search(_SEMI_DYNAMIC_TEMPORAL_PATTERN, text):
        return "semi_dynamic"
    return "stable"


def _extract_entities(query: str) -> tuple[str, ...]:
    entities: list[str] = []
    lowered = query.casefold()
    for entity in _KNOWN_ENTITIES:
        if re.search(rf"\b{re.escape(entity)}\b", lowered):
            entities.append(entity)

    words = re.findall(r"\b[A-Z][A-Za-z0-9+#.-]{2,}\b", query)
    for index, word in enumerate(words):
        if index == 0 or word.isupper():
            continue
        candidate = word.casefold()
        if candidate not in {"json", "sql"} and candidate not in entities:
            entities.append(candidate)
    return tuple(dict.fromkeys(entities))[:MAX_METADATA_ENTITIES]


def _extract_domain(text: str, constraints: tuple[tuple[str, str], ...]) -> str:
    programming = any(
        value in text
        for value in (*_PROGRAMMING_DOMAIN_TERMS, "postgresql", "sqlite")
    ) or any(key == "language" for key, _ in constraints)
    finance = any(value in text for value in _FINANCE_DOMAIN_TERMS)
    if programming == finance:
        return "unknown"
    return "programming" if programming else "finance"


def extract_metadata(normalized_query: str) -> QueryMetadata:
    """Extract conservative metadata without an external model call.

    The extractor only records an explicit, unambiguous signal. Missing or
    conflicting signals remain ``unknown`` for later safety decisions.
    """
    if not normalized_query.strip():
        raise ValueError("normalized_query must not be empty")

    text = normalized_query.casefold()
    constraints: list[tuple[str, str]] = []
    language = _extract_constraint(text, _LANGUAGE_PATTERNS)
    audience = _extract_constraint(text, _AUDIENCE_PATTERNS)
    platform = _extract_constraint(text, _PLATFORM_PATTERNS)
    library = _extract_constraint(text, _LIBRARY_PATTERNS)
    version = _extract_version(text)
    if language is not None:
        constraints.append(("language", language))
    if audience is not None:
        constraints.append(("audience", audience))
    if platform is not None:
        constraints.append(("platform", platform))
    if library is not None:
        constraints.append(("library", library))
    if version is not None:
        constraints.append(("version", version))
    return QueryMetadata(
        intent=_classify_signal(text, _INTENT_PATTERNS),  # type: ignore[arg-type]
        domain=_extract_domain(text, tuple(constraints)),  # type: ignore[arg-type]
        entities=_extract_entities(normalized_query),
        constraints=tuple(constraints),
        temporal_class=_classify_temporal(text),  # type: ignore[arg-type]
        output_format=_classify_signal(text, _FORMAT_PATTERNS),  # type: ignore[arg-type]
    )
