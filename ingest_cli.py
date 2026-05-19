"""CLI entrypoint for running ingestion and embedding."""

import sys

from dotenv import load_dotenv

load_dotenv()

from ingest import ingest_actions, ingest_events, ingest_testimonials
from embed import embed_actions, embed_events, embed_testimonials


def print_ingest_stats(label: str, stats: dict) -> None:
    print(f"  {label}:")
    print(f"    In WP:      {stats['total_in_wp']}")
    print(f"    Inserted:   {stats['inserted']}")
    print(f"    Updated:    {stats['updated']}")
    print(f"    Unchanged:  {stats['unchanged']}")
    print(f"    Archived:   {stats['archived']}")
    print(f"    Unarchived: {stats['unarchived']}")


def print_embed_stats(label: str, stats: dict) -> None:
    key = next(k for k in stats if k.endswith("_embedded"))
    print(f"  {label} embedded: {stats[key]} ({stats['chunks_created']} chunks)")


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run ingest_cli.py <site_id> [site_id ...]")
        sys.exit(1)

    site_ids = [int(arg) for arg in sys.argv[1:]]

    for site_id in site_ids:
        print(f"\n=== Site {site_id}: ingestion ===")
        print_ingest_stats("Actions", ingest_actions(site_id))
        print_ingest_stats("Testimonials", ingest_testimonials(site_id))
        print_ingest_stats("Events", ingest_events(site_id))

        print(f"\n=== Site {site_id}: embeddings ===")
        print_embed_stats("Actions", embed_actions(site_id))
        print_embed_stats("Testimonials", embed_testimonials(site_id))
        print_embed_stats("Events", embed_events(site_id))


if __name__ == "__main__":
    main()