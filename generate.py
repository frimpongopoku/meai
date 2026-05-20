"""Newsletter generation: turn retrieved context into a structured draft via Claude."""

import json
import os
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from anthropic.types import TextBlock

from newsletter_context import NewsletterContext, gather_newsletter_context
from prompt_builder import build_system_prompt, build_user_prompt

# Claude Sonnet 4.6 is the workhorse for content generation — strong at
# voice/tone guidance, fast, reasonably priced. If output quality ever
# needs a bump, switch to Opus 4.7 by changing this constant.
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096


_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """Lazy-initialize the Anthropic client."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


@dataclass
class NewsletterDraft:
    """The structured draft Claude produces, parsed from JSON."""

    raw_response: str
    parsed: dict[str, Any]
    context: NewsletterContext
    model: str
    input_tokens: int
    output_tokens: int


def generate_newsletter(
    site_id: int,
    community_name: str,
    theme: str | None = None,
) -> NewsletterDraft:
    """Gather context, compose prompts, call Claude, return a parsed draft.

    This is the top-level entry point. Everything that comes before it
    (ingestion, embedding, retrieval, prompt building) feeds into here.
    """
    # Gather everything Claude needs
    ctx = gather_newsletter_context(
        site_id=site_id,
        community_name=community_name,
        theme=theme,
    )

    system = build_system_prompt()
    user = build_user_prompt(ctx)

    # Call Claude
    client = _get_client()
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    # Extract text from response
    raw_text = "".join(
        block.text for block in message.content if isinstance(block, TextBlock)
    )

    # Parse JSON. We told Claude no markdown fences but be defensive.
    parsed = _parse_json_response(raw_text)

    return NewsletterDraft(
        raw_response=raw_text,
        parsed=parsed,
        context=ctx,
        model=MODEL,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
    )


def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON from Claude's response, handling stray markdown fences.

    Claude is instructed to return pure JSON, but defensive parsing
    catches the occasional case where it wraps output in ```json fences.
    """
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Drop the opening fence line
        text = text.split("\n", 1)[1] if "\n" in text else text
        # Drop the closing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    return json.loads(text)
