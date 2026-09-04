"""Turn a noisy supplier results page into a structured quote.

Supplier search-results pages vary too much (across sites, and across
categories on the *same* site) for CSS selectors to hold up. Handing the
page's visible text to an LLM and asking for one best-matching listing is
more robust, at the cost of a network call per (part, supplier) pair.
"""

import json
import os
from dataclasses import dataclass

from anthropic import Anthropic

# Identity-linked Console API keys (the kind created while logged in via
# SSO/Google, scoped to a specific workspace) require the workspace to be
# named on every request. Plain organization-level keys don't need this, so
# the header is only added when ANTHROPIC_WORKSPACE_ID is actually set.
_workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
_extra_headers = {"anthropic-workspace-id": _workspace_id} if _workspace_id else {}

_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], default_headers=_extra_headers)
_SYSTEM_PROMPT = """\
You extract structured pricing data from a supplier's search-results page for \
one specific part a buyer is trying to source. You are given the part \
description the buyer wants, a note about how this supplier's site is laid \
out, and the visible text scraped from the results page.

Find the single listing that best matches the requested part. If nothing on \
the page plausibly matches, say so rather than guessing.

Respond with ONLY a JSON object, no other text, matching this shape:
{
  "matched": true or false,
  "product_name": "exact name of the matched listing, or null",
  "unit_price_usd": number or null,
  "lead_time_days": integer or null (estimate from stock/ship-date text if a
    specific number isn't stated; use 0 for "in stock, ships today"),
  "in_stock": true, false, or null if unknown,
  "confidence": "high", "medium", or "low"
}
"""


@dataclass
class Quote:
    supplier: str
    matched: bool
    product_name: str | None
    unit_price_usd: float | None
    lead_time_days: int | None
    in_stock: bool | None
    confidence: str


def extract_quote(
    *, supplier_name: str, supplier_notes: str, part_description: str, page_text: str
) -> Quote:
    """Ask the model to pull a structured quote out of raw page text."""

    # Results pages can be long; keep the prompt bounded rather than sending
    # the entire DOM's text content.
    trimmed_text = page_text[:8000]

    user_prompt = (
        f"Part the buyer wants: {part_description}\n\n"
        f"Supplier: {supplier_name}\n"
        f"Layout notes: {supplier_notes}\n\n"
        f"Visible page text:\n{trimmed_text}"
    )

    response = _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    # Models occasionally wrap JSON in a code fence despite instructions.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return Quote(
            supplier=supplier_name,
            matched=False,
            product_name=None,
            unit_price_usd=None,
            lead_time_days=None,
            in_stock=None,
            confidence="low",
        )

    return Quote(
        supplier=supplier_name,
        matched=data.get("matched", False),
        product_name=data.get("product_name"),
        unit_price_usd=data.get("unit_price_usd"),
        lead_time_days=data.get("lead_time_days"),
        in_stock=data.get("in_stock"),
        confidence=data.get("confidence", "low"),
    )
