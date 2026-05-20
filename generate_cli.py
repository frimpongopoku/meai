"""Generate a newsletter draft.

Usage:
  uv run generate_cli.py <site_id> <community_name> [theme]

Examples:
  uv run generate_cli.py 22 "Sustainable Medfield"
  uv run generate_cli.py 22 "Sustainable Medfield" "winter heating and energy savings"
"""

import json
import sys

from dotenv import load_dotenv

load_dotenv()

from generate import generate_newsletter


def main():
    if len(sys.argv) < 3:
        print('Usage: uv run generate_cli.py <site_id> "<community_name>" ["<theme>"]')
        sys.exit(1)

    site_id = int(sys.argv[1])
    community_name = sys.argv[2]
    theme = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"\n=== Generating newsletter for {community_name} ===")
    if theme:
        print(f"Theme: {theme}")
    print()

    draft = generate_newsletter(
        site_id=site_id,
        community_name=community_name,
        theme=theme,
    )

    print(f"Model: {draft.model}")
    print(f"Tokens: {draft.input_tokens} in, {draft.output_tokens} out\n")
    print("=" * 80)
    print("DRAFT")
    print("=" * 80)
    print(json.dumps(draft.parsed, indent=2))


if __name__ == "__main__":
    main()