"""Interactive retrieval testing CLI.

Usage:
  uv run search_cli.py <site_id> "your query here"
  uv run search_cli.py 22 "heat pump rebates"
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from retrieve import search


def truncate(text: str, n: int = 100) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= n:
        return text
    return text[:n] + "..."


def main():
    if len(sys.argv) < 3:
        print('Usage: uv run search_cli.py <site_id> "your query"')
        sys.exit(1)

    site_id = int(sys.argv[1])
    query = sys.argv[2]

    print(f'\nQuery: "{query}" (site {site_id})\n')

    results = search(site_id, query, k=5)

    for content_type, hits in results.items():
        print(f"=== {content_type.upper()}S ===")
        if not hits:
            print("  (no matches)\n")
            continue

        for i, hit in enumerate(hits, 1):
            title = getattr(hit.record, "title", "<no title>")
            print(f"  {i}. [{hit.distance:.4f}] {title}")
            print(f"     matched on: {truncate(hit.matched_chunk_text, 110)}")
        print()


if __name__ == "__main__":
    main()