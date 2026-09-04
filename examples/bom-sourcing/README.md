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
export SOLARI_API_KEY=slr_live_...          # console.getsolari.com
export ANTHROPIC_API_KEY=sk-ant-...         # console.anthropic.com
export ANTHROPIC_WORKSPACE_ID=wrkspc_...    # only needed for identity-linked
                                             # Console keys — see Gotchas below
python main.py parts.csv
```

Output goes to `bom_report.csv` and a summary prints to the terminal.

Stealth mode (`stealth=True` in `agent.py`) requires a paid Solari plan — see
Gotchas below for why it's necessary here.

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

These are the actual problems hit building this, not hypothetical ones —
worth reading if you're extending this or hitting similar errors.

- **All three suppliers show some form of bot detection.** DigiKey serves an
  explicit Cloudflare challenge page, Grainger returns a generic Akamai-style
  error page, and McMaster-Carr silently ignores the search entirely and
  returns its homepage. Plain `solari.launch()` sessions get blocked by all
  three; `solari.launch(stealth=True, proxy="us")` gets past DigiKey and
  Grainger. Stealth mode requires a paid Solari plan (`402
  FeatureRequiresPlan` on free), and `proxy`/`captcha` both require
  `stealth: true` to be set as well.
- **McMaster-Carr's search never actually triggers**, stealth or not. Their
  site is a heavy client-rendered SPA, and a plain URL query parameter
  doesn't drive their search the way it does on Grainger and DigiKey. Every
  run returns their generic category-browse homepage instead of results.
  The real fix is interacting with their search input directly (type +
  Enter) rather than relying on a URL pattern — not implemented here, but
  worth doing if you extend this.
- **Use `wait_until="domcontentloaded"`, not the default `"load"`, on
  `page.goto()`.** `"load"` waits for every resource on the page (trackers,
  ads, everything) and can simply never fire on a heavy site, especially
  through a proxy — this caused DigiKey requests to time out at 20s even
  when the page was otherwise fine.
- **A fixed sleep after page load is fragile.** Client-rendered product
  grids sometimes finish rendering within 3 seconds and sometimes don't —
  the same Grainger search returned full product listings in one run and
  only a "4 products" header with no listings in the next. Bumped to 6
  seconds here, but a selector-based wait (wait for a specific
  results-container element) would be the real fix.
- **Free-tier Solari accounts cap concurrent sessions at 3**
  (`ConcurrencyLimitExceeded`, 429). Launching one session per supplier per
  part with no throttling hits this immediately, especially if a previous
  run's sessions haven't fully closed yet. `agent.py` uses an
  `asyncio.Semaphore(2)` to stay under the cap, plus a 30s timeout on
  `solari.launch()` itself — without the timeout, a session stuck waiting
  for a free slot hangs forever instead of failing loudly.
- **Identity-linked Console API keys need an extra header.** An Anthropic
  API key created while logged in via SSO/Google (scoped to a specific
  workspace) fails with `anthropic-workspace-id is required...` unless that
  header is set on every request. `extract.py` only adds it when
  `ANTHROPIC_WORKSPACE_ID` is set, so plain organization-level keys are
  unaffected.
- **Supplier search results pages are inconsistent even within one site** —
  extraction is intentionally LLM-based rather than CSS-selector-based so it
  survives markup that differs by category.
- **The model correctly refuses to guess.** When Grainger's shaft-coupler
  page had "Loading..." placeholders instead of populated prices, the model
  reported no confident match rather than inventing a number — and when
  results existed but didn't actually match the spec (five-phase motors
  returned for a two-phase NEMA 17 request), it explained why rather than
  picking the closest-looking one. That's the `reasoning` field in
  `bom_report.csv` — worth reading on any row marked `no match`.
- **Each `(part, supplier)` pair gets its own browser session** — slower
  than reusing one session across searches, but avoids state bleeding
  across unrelated queries. See `browser-profiles-ts` in this cookbook if
  you want to explore session reuse.