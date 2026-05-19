"""CLI entrypoint for running ingestion."""

import sys

from dotenv import load_dotenv

load_dotenv()

from ingest import ingest_actions, ingest_testimonials


def print_stats(label: str, stats: dict) -> None:
    print(f"  {label}:")
    print(f"    In WP:      {stats['total_in_wp']}")
    print(f"    Inserted:   {stats['inserted']}")
    print(f"    Updated:    {stats['updated']}")
    print(f"    Unchanged:  {stats['unchanged']}")
    print(f"    Archived:   {stats['archived']}")
    print(f"    Unarchived: {stats['unarchived']}")


from ingest import ingest_actions, ingest_events, ingest_testimonials


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run ingest_cli.py <site_id> [site_id ...]")
        sys.exit(1)

    site_ids = [int(arg) for arg in sys.argv[1:]]

    for site_id in site_ids:
        print(f"\n=== Site {site_id} ===")

        action_stats = ingest_actions(site_id)
        print_stats("Actions", action_stats)

        testimonial_stats = ingest_testimonials(site_id)
        print_stats("Testimonials", testimonial_stats)

        event_stats = ingest_events(site_id)
        print_stats("Events", event_stats)


if __name__ == "__main__":
    main()
