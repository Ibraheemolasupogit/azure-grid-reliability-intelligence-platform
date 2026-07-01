"""Deterministic query classification."""

from __future__ import annotations

import hashlib
import re

from grid_reliability.genai.models import QueryCategory, QueryClassification, QueryInput

ENTITY_PATTERN = re.compile(r"\b(?:FDR|SUB|GRID|AST)-[A-Z0-9\-]+\b")


def classify_query(query: QueryInput) -> QueryClassification:
    text = query.query_text.lower()
    restricted, reason = _restricted(text)
    unsupported_current = "real" in text and ("current" in text or "live" in text)
    category, components, classification_reason = _category(text)
    entities = tuple(sorted(set(ENTITY_PATTERN.findall(query.query_text.upper()))))
    if unsupported_current:
        category = QueryCategory.UNSUPPORTED.value
        reason = "UNSUPPORTED_REAL_WORLD_STATUS"
    confidence = 0.95 if category != QueryCategory.UNSUPPORTED.value else 0.2
    if restricted:
        confidence = 1.0
    return QueryClassification(
        query_id=query.query_id,
        query_text=query.query_text,
        query_category=category,
        entities_detected=entities,
        components_requested=components,
        time_scope="latest_repository_evidence" if "latest" in text else "repository_evidence",
        restricted_action_detected=restricted,
        unsupported_current_status=unsupported_current,
        confidence=confidence,
        classification_reason=classification_reason,
        safety_reason_code=reason,
    )


def query_id(text: str) -> str:
    return "QRY-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12].upper()


def _restricted(text: str) -> tuple[bool, str | None]:
    phrase_rules = (
        (
            (
                "open breaker",
                "open this breaker",
                "close breaker",
                "switch feeder",
                "switch this feeder",
            ),
            "RESTRICTED_OPERATIONAL_CONTROL",
        ),
        (
            ("override protection", "change protection", "protection setting"),
            "RESTRICTED_PROTECTION_CHANGE",
        ),
        (("dispatch crew", "send crew automatically"), "RESTRICTED_OPERATIONAL_CONTROL"),
        (("guarantee", "will definitely outage"), "RESTRICTED_REAL_TIME_TARGETING"),
    )
    for phrases, reason in phrase_rules:
        if any(phrase in text for phrase in phrases):
            return True, reason
    pattern_rules = (
        (r"\bsuppress\b.*\balerts?\b", "RESTRICTED_ALERT_SUPPRESSION"),
        (r"\bbypass\b.*\balarms?\b", "RESTRICTED_ALERT_SUPPRESSION"),
        (r"\bsilence\b.*\balarms?\b", "RESTRICTED_ALERT_SUPPRESSION"),
    )
    for pattern, reason in pattern_rules:
        if re.search(pattern, text):
            return True, reason
    return False, None


def _category(text: str) -> tuple[str, tuple[str, ...], str]:
    rules = (
        (("forecast", "demand", "load"), QueryCategory.FORECAST_SUMMARY.value, ("forecasting",)),
        (
            ("maintenance priority", "highest maintenance"),
            QueryCategory.MAINTENANCE_PRIORITY.value,
            ("asset_health",),
        ),
        (
            ("asset health", "health score", "asset"),
            QueryCategory.ASSET_HEALTH.value,
            ("asset_health",),
        ),
        (
            ("outage risk", "risk score", "elevated outage"),
            QueryCategory.OUTAGE_RISK.value,
            ("outage_prediction",),
        ),
        (
            ("reliability", "saifi", "saidi", "caidi", "asai"),
            QueryCategory.RELIABILITY_PERFORMANCE.value,
            ("reliability",),
        ),
        (("monitoring", "alert", "alerts"), QueryCategory.MONITORING_ALERTS.value, ("monitoring",)),
        (
            ("incident", "investigate", "why"),
            QueryCategory.INCIDENT_INVESTIGATION.value,
            ("monitoring", "reliability", "outage_prediction"),
        ),
        (
            ("executive", "summary", "status"),
            QueryCategory.EXECUTIVE_SUMMARY.value,
            ("monitoring", "reliability", "forecasting"),
        ),
        (
            ("methodology", "calculated", "how are", "limitations"),
            QueryCategory.METHODOLOGY.value,
            ("documentation",),
        ),
        (("grid status", "platform status"), QueryCategory.GRID_STATUS.value, ("monitoring",)),
    )
    for phrases, category, components in rules:
        if any(phrase in text for phrase in phrases):
            return category, components, f"matched keywords for {category}"
    return QueryCategory.UNSUPPORTED.value, (), "no supported category keywords matched"
