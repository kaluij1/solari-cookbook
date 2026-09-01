# BOM Sourcing Agent (Python)

Give it a small bill of materials (a CSV of part descriptions) and it checks
multiple industrial-parts suppliers — none of which expose a public shopping
API — and returns a price/lead-time/stock comparison so you know where to
buy each line item.

This is the problem most engineering teams still solve by hand: open three
supplier sites in three tabs, search the same part number on each, and copy
numbers into a spreadsheet. It doesn't scale past a handful of parts, and it's
exactly the kind of "software that was never built to talk to anything else"
that a cloud browser + an LLM can automate end to end.

## How it works

1. `parts.csv` lists the parts you're sourcing (a free-text description per
   line — "M4x12 socket head cap screw, stainless" — not a part number, since
   that's the realistic case).
2. For each part, the agent opens a Solari cloud browser session per
   supplier, runs the site's own search box, and grabs the results page.
3. The page text (noisy: ads, unrelated listings, inconsistent formatting) is
   handed to an LLM, which extracts a structured `{price, lead_time,
   in_stock, url}` guess for the best-matching listing, or `None` if nothing
   plausible is on the page.
4. Once every supplier has been checked for every part, `report.py` builds a
   comparison table and writes `bom_report.csv` — cheapest and fastest
   in-stock option per line item, plus every supplier's raw quote so you can
   sanity-check the agent's picks.

## Why a cloud browser instead of each supplier's own site scraper

- Real Chrome, not a headless bot fingerprint — these sites vary in how
  aggressively they gate automated traffic.
- No local Chromium/Playwright install or driver management; `solari.launch()`
  hands you a ready browser.
- Sessions are disposable — one per supplier per part, so a bad search never
  pollutes the next one with stale cookies or state.

## Setup

```bash
cd solari-cookbook/examples/bom-sourcing-agent-py
pip install -r requirements.txt
export SOLARI_API_KEY=slr_live_...     # console.getsolari.com
export ANTHROPIC_API_KEY=sk-ant-...    # console.anthropic.com
python main.py parts.csv
```

Output goes to `bom_report.csv` and a summary prints to the terminal.

## Files

| File | Role |
| --- | --- |
| `main.py` | CLI entry point — reads the BOM, runs the agent, writes the report |
| `suppliers.py` | Per-supplier search-URL templates and site quirks |
| `agent.py` | Drives one Solari browser session per (part, supplier) search |
| `extract.py` | LLM-based extraction of price/lead-time/stock from raw page text |
| `report.py` | Builds the comparison table and writes CSV output |
| `parts.csv` | Example BOM — swap in your own |

## Gotchas this example ran into

- Supplier search results pages are inconsistent even within one site —
  extraction is intentionally LLM-based rather than CSS-selector-based so it
  survives markup that differs by category.
- Some searches return zero good matches (typo'd description, discontinued
  part). The agent records `None` rather than guessing, so a human still
  makes the final call on ambiguous parts.
- Each `(part, supplier)` pair gets its own browser session — slower than
  reusing one session across searches, but avoids state bleeding across
  unrelated queries. See `browser-profiles-ts` in this cookbook if you want
  to explore session reuse.
