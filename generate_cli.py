"""Generate a newsletter draft and render it.

Usage:
  uv run generate_cli.py <site_id> "<community_name>" ["<theme>"] [--format=markdown|html|json]

Examples:
  uv run generate_cli.py 22 "Sustainable Medfield"
  uv run generate_cli.py 22 "Sustainable Medfield" "winter heating" --format=html
  uv run generate_cli.py 22 "Sustainable Medfield" --format=html > preview.html
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from generate import generate_newsletter
from render import render_html, render_markdown


def main():
    args = sys.argv[1:]
    fmt = "markdown"

    # Strip --format flag if present
    cleaned: list[str] = []
    for arg in args:
        if arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
        else:
            cleaned.append(arg)
    args = cleaned

    if len(args) < 2:
        print('Usage: uv run generate_cli.py <site_id> "<community_name>" ["<theme>"] [--format=markdown|html|json]')
        sys.exit(1)

    site_id = int(args[0])
    community_name = args[1]
    theme = args[2] if len(args) > 2 else None

    # Status info on stderr so it doesn't pollute piped output
    print(f"Generating newsletter for {community_name}...", file=sys.stderr)
    if theme:
        print(f"Theme: {theme}", file=sys.stderr)

    draft = generate_newsletter(
        site_id=site_id,
        community_name=community_name,
        theme=theme,
    )

    print(
        f"Model: {draft.model} | "
        f"Tokens: {draft.input_tokens} in, {draft.output_tokens} out",
        file=sys.stderr,
    )

    # Output the requested format to stdout
    if fmt == "json":
        print(json.dumps(draft.parsed, indent=2))
    elif fmt == "html":
        print(render_html(draft.parsed, community_name=community_name))
    elif fmt == "markdown":
        print(render_markdown(draft.parsed))
    else:
        print(f"Unknown format: {fmt}. Use markdown, html, or json.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()