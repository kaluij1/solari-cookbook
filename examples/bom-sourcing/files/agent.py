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


async def fetch_quote(solari: Solari, supplier: Supplier, part_description: str) -> Quote:
    """Search one supplier for one part and return a structured quote."""

    url = supplier.search_url(part_description)
    browser = await solari.launch()
    try:
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS)
            # Give client-rendered result grids a moment to populate. A fixed
            # sleep is crude but keeps this example dependency-free; a
            # production version would wait on a results-container selector
            # per supplier instead.
            await asyncio.sleep(3)
            page_text = await page.locator("body").inner_text()
        except Exception as exc:  # noqa: BLE001 - surface as a failed quote, not a crash
            print(f"  [{supplier.name}] page load failed: {exc}")
            return Quote(
                supplier=supplier.name,
                matched=False,
                product_name=None,
                unit_price_usd=None,
                lead_time_days=None,
                in_stock=None,
                confidence="low",
            )
    finally:
        # `close()` also releases the session — skipping this leaves the slot
        # held until the plan's idle timeout for no reason.
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
    """Check every supplier for one part, concurrently."""

    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    tasks = [fetch_quote(solari, supplier, part_description) for supplier in suppliers]
    return await asyncio.gather(*tasks)
