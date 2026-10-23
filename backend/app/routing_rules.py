"""Deterministic, inspectable routing rules.

These rules exist for three jobs:
  * give every text-bearing record a baseline suggestion,
  * produce a clearly-labelled provisional suggestion when source text changes
    and no refreshed analysis exists yet,
  * provide a cross-check that is independent of the pre-generated analysis.

They are keyword- and structure-based, never a model call. Every suggestion
carries a trace so the manager can see exactly why it was made.
"""

from __future__ import annotations

import re

from .taxonomy import normalise_routes

ENGINE_VERSION = "rules-1.0"

# Phrases are matched case-insensitively on word boundaries.
SIGNALS: dict[str, list[tuple[str, str]]] = {
    "customer_success": [
        (r"\bnot working\b", "reports something not working"),
        (r"\bdoes not work\b", "reports functionality that does not work"),
        (r"\bcan(?:not|'t) (?:upload|select|edit|save|find|access)\b", "blocked action"),
        (r"\b(?:issue|issues|problem|problems|bug|error)\b", "reports a problem"),
        (r"\bworkaround\b", "discusses a workaround"),
        (r"\btoken (?:has )?expired\b", "expired access token"),
        (r"\bstuck\b", "workflow stuck"),
    ],
    "deal_next_steps": [
        (r"\bproposal\b", "proposal requested or discussed"),
        (r"\bpric(?:e|ing)\b", "pricing discussed"),
        (r"\bper (?:month|year|annum)\b|\bannual (?:charge|subscription)\b", "commercial terms"),
        (r"\bpilot\b", "pilot discussed"),
        (r"\bcontract\b", "contract discussed"),
        (r"\b(?:cfo|management) (?:approv|review|discuss)", "decision-maker review"),
        (r"\bminimum spend\b|\bfee\b", "fee structure"),
    ],
    "internal_vendor": [
        (r"\bpartner(?:ship|s)?\b", "partnership language"),
        (r"\breferral\b|\breferred\b", "referral arrangement"),
        (r"\bsupplier\b", "supplier relationship"),
        (r"\bcommission\b", "commission terms"),
        (r"\bcompliance (?:partners|team)\b", "compliance dependency"),
        (r"\bintegration\b", "integration dependency"),
        (r"\bmemorandum\b", "agreement to sign"),
    ],
    "customer_followup": [
        (r"\bsend (?:me|you|the|over|it|information|details|material)", "material promised"),
        (r"\bwill (?:send|revert|come back|confirm|check)\b", "follow-up promised"),
        (r"\bcall (?:me )?back\b", "callback requested"),
        (r"\bnext week\b|\bmon(?:day)?\b|\btues(?:day)?\b", "follow-up timing"),
        (r"\bemail\b", "email channel follow-up"),
    ],
    "sales_coaching": [
        (r"\bcold call\b", "self-identified cold outreach"),
        (r"\babout forty seconds\b", "scripted opener"),
        (r"\bwe already have\b", "existing solution claim"),
        (r"\bnot interested\b", "objection"),
        (r"\bwhy are you calling\b", "prospect challenged the approach"),
        (r"\bwhere did you (?:find|get) my\b", "source of contact questioned"),
    ],
    "no_action": [
        (r"\bwrong number\b", "wrong contact"),
        (r"\bvoicemail\b|\bleave a message\b", "message only"),
        (r"\bnot interested\b", "decline with no next step"),
        (r"\bno (?:need|requirement)\b", "no requirement stated"),
    ],
}

NEGATIVE_NEXT_STEP = re.compile(
    r"\b(?:no|not|don't|do not)\b.{0,40}\b(?:call|contact|follow[- ]?up|need)\b", re.I
)


def extract_signals(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for route, patterns in SIGNALS.items():
        hits = []
        for pattern, label in patterns:
            if re.search(pattern, text, re.I):
                hits.append(label)
        if hits:
            found[route] = hits
    return found


def suggest_routes(
    *,
    source_type: str,
    text: str | None,
    has_usable_text: bool,
    source_outcome: str | None = None,
    is_connected: bool | None = None,
) -> dict:
    """Return {routes, method, rationale, trace} for one record."""
    if not has_usable_text or not text:
        return {
            "routes": ["needs_review"],
            "method": "deterministic_rules",
            "rationale": (
                "No usable supplied conversation text, so no substantive route is "
                "assigned. The record is parked for intake review."
            ),
            "trace": [
                {
                    "rule": "no_usable_text",
                    "outcome": "needs_review",
                    "detail": "Blank or absent conversation text; nothing to analyse.",
                }
            ],
        }

    signals = extract_signals(text)
    routes: list[str] = []
    trace: list[dict] = []

    customer_issue = "customer_success" in signals
    commercial = "deal_next_steps" in signals
    partner = "internal_vendor" in signals

    if customer_issue:
        routes.append("customer_success")
        trace.append(
            {
                "rule": "product_issue_language",
                "outcome": "customer_success",
                "detail": "; ".join(signals["customer_success"][:4]),
            }
        )
        # A support conversation can still carry a deal/coaching angle, but not
        # automatically: only add commercial when explicit commercial terms appear.
        if commercial:
            routes.append("deal_next_steps")
            trace.append(
                {
                    "rule": "commercial_terms_alongside_issue",
                    "outcome": "deal_next_steps",
                    "detail": "; ".join(signals["deal_next_steps"][:3]),
                }
            )
    elif partner:
        routes.append("internal_vendor")
        trace.append(
            {
                "rule": "partner_or_vendor_language",
                "outcome": "internal_vendor",
                "detail": "; ".join(signals["internal_vendor"][:4]),
            }
        )
        if commercial:
            routes.append("deal_next_steps")
            trace.append(
                {
                    "rule": "commercial_terms_in_partner_call",
                    "outcome": "deal_next_steps",
                    "detail": "Partner call also contains commercial/onboarding terms.",
                }
            )
    elif commercial:
        routes.append("deal_next_steps")
        trace.append(
            {
                "rule": "commercial_terms",
                "outcome": "deal_next_steps",
                "detail": "; ".join(signals["deal_next_steps"][:4]),
            }
        )

    if "customer_followup" in signals and not customer_issue:
        routes.append("customer_followup")
        trace.append(
            {
                "rule": "follow_up_promised",
                "outcome": "customer_followup",
                "detail": "; ".join(signals["customer_followup"][:3]),
            }
        )

    if source_type == "call" and "sales_coaching" in signals:
        routes.append("sales_coaching")
        trace.append(
            {
                "rule": "call_handling_signal",
                "outcome": "sales_coaching",
                "detail": "; ".join(signals["sales_coaching"][:3]),
            }
        )

    if "no_action" in signals and not routes:
        routes.append("no_action")
        trace.append(
            {
                "rule": "no_obligation_language",
                "outcome": "no_action",
                "detail": "; ".join(signals["no_action"][:3]),
            }
        )

    if not routes:
        routes = ["needs_review"]
        trace.append(
            {
                "rule": "no_rule_matched",
                "outcome": "needs_review",
                "detail": "Text present but no routing signal cleared the threshold.",
            }
        )

    # Guardrail: a stated source outcome of "not interested" plus no follow-up
    # obligation is informational, not a live deal.
    if (
        source_outcome
        and "not_interested" in source_outcome.lower()
        and "deal_next_steps" in routes
        and "customer_followup" not in routes
    ):
        routes = [r for r in routes if r != "deal_next_steps"] + ["no_action"]
        trace.append(
            {
                "rule": "source_outcome_guardrail",
                "outcome": "no_action",
                "detail": "Source-reported outcome indicates no interest; deal route removed.",
            }
        )

    routes = normalise_routes(routes)
    rationale = "Rules matched: " + ", ".join(
        f"{t['outcome']} ({t['rule']})" for t in trace
    )
    return {
        "routes": routes,
        "method": "deterministic_rules",
        "rationale": rationale,
        "trace": trace,
    }
