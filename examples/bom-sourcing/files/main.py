"""BOM Sourcing Agent — CLI entry point.

    python main.py parts.csv

Reads a bill of materials, checks each part against every configured
supplier using a Solari cloud browser, and writes a price/lead-time
comparison to bom_report.csv.
"""

import asyncio
import csv
import sys

from agent import fetch_all_quotes
from extract import Quote
from report import print_summary, write_report
from suppliers import SUPPLIERS


def read_parts(path: str) -> list[tuple[str, int]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return [(row["description"], int(row["quantity"])) for row in reader]


async def run(parts_path: str, report_path: str) -> None:
    parts = read_parts(parts_path)
    part_quotes: list[tuple[str, int, list[Quote]]] = []

    for description, quantity in parts:
        print(f"Sourcing: {description} (qty {quantity})")
        quotes = await fetch_all_quotes(description, SUPPLIERS)
        for quote in quotes:
            status = "matched" if quote.matched else "no match"
            print(f"  [{quote.supplier}] {status}")
        part_quotes.append((description, quantity, quotes))

    write_report(report_path, part_quotes)
    print_summary(part_quotes)
    print(f"Full comparison written to {report_path}")


def main() -> None:
    parts_path = sys.argv[1] if len(sys.argv) > 1 else "parts.csv"
    report_path = "bom_report.csv"
    asyncio.run(run(parts_path, report_path))


if __name__ == "__main__":
    main()
