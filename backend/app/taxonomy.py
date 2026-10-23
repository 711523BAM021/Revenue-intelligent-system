"""Routing taxonomy.

Seven destinations, deliberately small and mutually explainable. A record may
carry more than one route: one conversation can serve a deal conversation and
a coaching observation at the same time. `needs_review` is a real destination,
not an error state: it is where ambiguity is parked so a human resolves it.
"""

from __future__ import annotations

ROUTES: dict[str, dict[str, str]] = {
    "deal_next_steps": {
        "label": "Deal next steps",
        "slug": "deal-next-steps",
        "description": (
            "A live commercial conversation with a prospect or existing customer: "
            "evaluation, pricing, proposal, pilot or a stated decision path. "
            "Not used for product defects or pure information calls."
        ),
        "tone": "accent",
    },
    "customer_followup": {
        "label": "Customer follow-up",
        "slug": "customer-follow-up",
        "description": (
            "A promised or owed follow-up: material to send, a callback arranged, "
            "an internal check to report back. No confirmed evaluation yet."
        ),
        "tone": "info",
    },
    "sales_coaching": {
        "label": "Sales coaching",
        "slug": "sales-coaching",
        "description": (
            "Evidence about how the conversation was handled: discovery quality, "
            "talk balance, missed next step, unhandled objection. Aimed at the "
            "manager coaching the rep, never used to rank performance."
        ),
        "tone": "warning",
    },
    "customer_success": {
        "label": "Customer success / product issue",
        "slug": "customer-success",
        "description": (
            "An existing customer reports broken or blocked product behaviour, "
            "an access problem, or a workflow that needs a fix or workaround."
        ),
        "tone": "danger",
    },
    "internal_vendor": {
        "label": "Internal or vendor / partnership",
        "slug": "internal-vendor",
        "description": (
            "SpendNest talking to a partner, supplier or internal team: referral "
            "agreements, platform vendors, enablement sessions. No customer deal."
        ),
        "tone": "neutral",
    },
    "no_action": {
        "label": "No action / informational",
        "slug": "no-action",
        "description": (
            "Nothing owed by either side: a wrong number, a message left, a clear "
            "and polite decline with no follow-up agreed."
        ),
        "tone": "muted",
    },
    "needs_review": {
        "label": "Human review required",
        "slug": "needs-review",
        "description": (
            "Evidence is missing, contradictory or too thin for a substantive "
            "route. Parked for a person, with the reason shown."
        ),
        "tone": "warning",
    },
}

ROUTE_ORDER = list(ROUTES.keys())
ROUTE_LABELS = {k: v["label"] for k, v in ROUTES.items()}
ROUTE_SLUGS = {k: v["slug"] for k, v in ROUTES.items()}
SLUG_TO_KEY = {v["slug"]: k for k, v in ROUTES.items()}


def is_valid_route(key: str) -> bool:
    return key in ROUTES


def labels(keys: list[str]) -> list[str]:
    return [ROUTE_LABELS.get(k, k) for k in keys]


def normalise_routes(keys: list[str]) -> list[str]:
    """Deduplicate, drop unknown keys, keep taxonomy order."""
    seen = {k for k in keys if k in ROUTES}
    return [k for k in ROUTE_ORDER if k in seen]


REVIEW_STATES = [
    "unreviewed",
    "needs_review",
    "reviewed",
    "awaiting_text",
]

REVIEW_LABELS = {
    "unreviewed": "Not yet reviewed",
    "needs_review": "Needs review",
    "reviewed": "Reviewed",
    "awaiting_text": "Awaiting usable text",
}

PROCESSING_LABELS = {
    "complete": "Processed",
    "text_unavailable": "Text unavailable",
    "awaiting_transcript": "Awaiting transcript",
}
