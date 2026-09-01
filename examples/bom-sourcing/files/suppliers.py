"""Per-supplier search configuration.

Each supplier gets a `search_url(query)` function that builds a results-page
URL from a free-text query, plus a couple of notes for humans reading this
file. None of these sites expose a public shopping/pricing API — that's the
whole reason this example exists.

Add a supplier by adding an entry here; nothing else in the agent needs to
change.
"""

from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Supplier:
    name: str
    search_url: Callable[[str], str]
    # Rough hint passed to the extraction prompt about how this site
    # presents results, since layouts differ enough to matter.
    notes: str


SUPPLIERS: list[Supplier] = [
    Supplier(
        name="McMaster-Carr",
        search_url=lambda q: f"https://www.mcmaster.com/products/?q={quote_plus(q)}",
        notes=(
            "Fastener/hardware catalog. Results are a grid of product "
            "families; price and pack size are usually on the family page, "
            "not the search results page itself."
        ),
    ),
    Supplier(
        name="Grainger",
        search_url=lambda q: f"https://www.grainger.com/search?searchQuery={quote_plus(q)}",
        notes=(
            "Industrial supply. Search results list price and stock/lead "
            "time inline per item."
        ),
    ),
    Supplier(
        name="DigiKey",
        search_url=lambda q: f"https://www.digikey.com/en/products/result?keywords={quote_plus(q)}",
        notes=(
            "Electronic components. Best for the electrical parts on a BOM "
            "(motors, power supplies) rather than fasteners. Results table "
            "has price breaks by quantity and a stock count column."
        ),
    ),
]
