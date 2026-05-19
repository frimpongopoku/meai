"""CLI entrypoint for running ingestion."""

import sys

from dotenv import load_dotenv

load_dotenv()

from ingest import ingest_actions


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run ingest_cli.py <site_id> [site_id ...]")
        sys.exit(1)

    site_ids = [int(arg) for arg in sys.argv[1:]]

    for site_id in site_ids:
        print(f"\n=== Ingesting actions for site {site_id} ===")
        stats = ingest_actions(site_id)
        print(f"  Total:     {stats['total']}")
        print(f"  Inserted:  {stats['inserted']}")
        print(f"  Updated:   {stats['updated']}")
        print(f"  Unchanged: {stats['unchanged']}")


if __name__ == "__main__":
    main()