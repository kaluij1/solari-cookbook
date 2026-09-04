"""Runs one Solari cloud-browser session per (part, supplier) search.

Each search gets its own session on purpose: a bad or blocked search never
leaves cookies/state that could skew the next one, and sessions are cheap
and fast to boot on Solari's infrastructure (see the cookbook's
browser-quickstart examples for the bare-bones version of this call).
"""

import asyncio
import os

from solari_browser import Solari

from extract import Quote, extract_quote
from suppliers import Supplier

PAGE_LOAD_TIMEOUT_MS = 20_000
LAUNCH_TIMEOUT_SECONDS = 30

# Free-tier Solari accounts cap concurrent sessions at 3 (see the
# ConcurrencyLimitExceeded error if you ever hit it). Stay comfortably under
# that so a slow-to-close session from a previous part doesn't cause a
# spurious 429 here. Raise this if your plan supports more.
MAX_CONCURRENT_SESSIONS = 2

_session_slots = asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)


def _failed_quote(supplier_name: str) -> Quote:
    return Quote(
        supplier=supplier_name,
        matched=False,
        product_name=None,
        unit_price_usd=None,
        lead_time_days=None,
        in_stock=None,
        confidence="low",
    )


async def fetch_quote(solari: Solari, supplier: Supplier, part_description: str) -> Quote:
    """Search one supplier for one part and return a structured quote."""

    url = supplier.search_url(part_description)

    async with _session_slots:
        try:
            # A hard timeout here is what actually prevents an indefinite
            # hang: without it, a session stuck negotiating a connection
            # (e.g. because the account is momentarily at its concurrency
            # cap) blocks forever rather than failing fast.
            browser = await asyncio.wait_for(
                solari.launch(stealth=True, proxy="us"), timeout=LAUNCH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            print(f"  [{supplier.name}] launch timed out after {LAUNCH_TIMEOUT_SECONDS}s")
            return _failed_quote(supplier.name)
        except Exception as exc:  # noqa: BLE001 - e.g. 429 ConcurrencyLimitExceeded
            print(f"  [{supplier.name}] launch failed: {exc}")
            return _failed_quote(supplier.name)

        try:
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS)
                # Give client-rendered result grids a moment to populate. A
                # fixed sleep is crude but keeps this example
                # dependency-free; a production version would wait on a
                # results-container selector per supplier instead.
                await asyncio.sleep(3)
                page_text = await page.locator("body").inner_text()
                
                # TEMP DEBUG: see what the browser actually loaded. Remove
                # once matching is working reliably.
                print(f"  [{supplier.name}] page text length: {len(page_text)}")
                print(f"  [{supplier.name}] first 300 chars: {page_text[:300]!r}")
            except Exception as exc:  # noqa: BLE001 - surface as a failed quote, not a crash
                print(f"  [{supplier.name}] page load failed: {exc}")
                return _failed_quote(supplier.name)
        finally:
            # `close()` also releases the session — skipping this leaves the
            # slot held until the plan's idle timeout for no reason.
            await browser.close()

    return extract_quote(
        supplier_name=supplier.name,
        supplier_notes=supplier.notes,
        part_description=part_description,
        page_text=page_text,
    )


async def fetch_all_quotes(
    part_description: str, suppliers: list[Supplier]
) -> list[Quote]:
    """Check every supplier for one part.

    Session creation is throttled by the semaphore in fetch_quote, so this
    still runs suppliers concurrently up to MAX_CONCURRENT_SESSIONS at a
    time rather than one at a time.
    """

    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    tasks = [fetch_quote(solari, supplier, part_description) for supplier in suppliers]
    return await asyncio.gather(*tasks)