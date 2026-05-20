"""Lightweight playbook loader.

Playbooks are markdown files in /playbooks/*.md with YAML frontmatter.
They're loaded directly at generation time rather than embedded — we
have a small number of them and Claude's context window handles them
easily, so semantic retrieval would add complexity for no real benefit.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


PLAYBOOKS_DIR = Path(__file__).parent / "playbooks"

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


@dataclass
class Playbook:
    slug: str
    title: str
    tags: list[str]
    body_markdown: str


def load_playbook(slug: str) -> Playbook:
    """Load a single playbook by slug. Raises FileNotFoundError if missing."""
    path = PLAYBOOKS_DIR / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"Playbook not found: {slug}")
    return _parse_playbook_file(path)


def load_playbooks(slugs: list[str]) -> list[Playbook]:
    """Load multiple playbooks by slug, in order."""
    return [load_playbook(slug) for slug in slugs]


def list_available_playbooks() -> list[str]:
    """Return all playbook slugs available in the playbooks directory."""
    return sorted(p.stem for p in PLAYBOOKS_DIR.glob("*.md"))


def _parse_playbook_file(path: Path) -> Playbook:
    """Parse a markdown file with YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        raise ValueError(f"Playbook {path.name} missing YAML frontmatter")

    frontmatter = yaml.safe_load(match.group(1))
    body = match.group(2).strip()

    return Playbook(
        slug=frontmatter["slug"],
        title=frontmatter["title"],
        tags=frontmatter.get("tags", []),
        body_markdown=body,
    )