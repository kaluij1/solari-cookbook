"""Build the price/lead-time comparison table and write it to CSV."""

import csv

from extract import Quote


def best_quote(quotes: list[Quote]) -> Quote | None:
    """Pick the cheapest in-stock, matched quote; fall back sensibly."""

    matched = [q for q in quotes if q.matched and q.unit_price_usd is not None]
    if not matched:
        return None

    in_stock = [q for q in matched if q.in_stock]
    pool = in_stock if in_stock else matched
    return min(pool, key=lambda q: q.unit_price_usd)


def write_report(
    path: str, part_quotes: list[tuple[str, int, list[Quote]]]
) -> None:
    """Write one row per (part, supplier) plus a 'best' row per part.

    `part_quotes` is a list of (description, quantity, quotes) tuples.
    """

    fieldnames = [
        "part_description",
        "quantity",
        "supplier",
        "matched",
        "product_name",
        "unit_price_usd",
        "extended_price_usd",
        "lead_time_days",
        "in_stock",
        "confidence",
        "is_best_pick",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for description, quantity, quotes in part_quotes:
            pick = best_quote(quotes)
            for quote in quotes:
                extended = (
                    round(quote.unit_price_usd * quantity, 2)
                    if quote.unit_price_usd is not None
                    else None
                )
                writer.writerow(
                    {
                        "part_description": description,
                        "quantity": quantity,
                        "supplier": quote.supplier,
                        "matched": quote.matched,
                        "product_name": quote.product_name,
                        "unit_price_usd": quote.unit_price_usd,
                        "extended_price_usd": extended,
                        "lead_time_days": quote.lead_time_days,
                        "in_stock": quote.in_stock,
                        "confidence": quote.confidence,
                        "is_best_pick": pick is not None and quote is pick,
                    }
                )


def print_summary(part_quotes: list[tuple[str, int, list[Quote]]]) -> None:
    """Print a short human-readable summary to the terminal."""

    print("\n=== BOM Sourcing Summary ===\n")
    for description, quantity, quotes in part_quotes:
        pick = best_quote(quotes)
        print(f"- {description}  (qty {quantity})")
        if pick is None:
            print("    no supplier returned a confident match")
            continue
        extended = round(pick.unit_price_usd * quantity, 2)
        lead = (
            f"{pick.lead_time_days}d lead time"
            if pick.lead_time_days is not None
            else "lead time unknown"
        )
        print(
            f"    best: {pick.supplier} — {pick.product_name} "
            f"— ${pick.unit_price_usd:.2f}/ea (${extended:.2f} total) — {lead}"
        )
    print()
