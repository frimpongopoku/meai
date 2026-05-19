"""Chunking strategies for content embedding.

Each function returns a list of (chunk_index, chunk_text) tuples.
Chunks are designed to give separate semantic signals for different parts
of a record, improving retrieval precision over embedding the whole record
as a single blurry vector.
"""

from models import Action, Event, Testimonial

# Approximate max chars per chunk for long-form content.
# Voyage models handle far more, but smaller chunks give sharper retrieval.
MAX_CHUNK_CHARS = 2000


def chunk_action(action: Action) -> list[tuple[int, str]]:
    """Chunk an action by its semantic sections.

    Chunk 0: title + description (what this action is)
    Chunk 1: steps_to_take (how to do it)
    Chunk 2+: deep_dive sections (deeper context, may be split if very long)

    Each chunk is prefixed with [action: <title>] so the embedding model
    has consistent context even for steps/deep_dive chunks that don't
    include the title naturally.
    """
    chunks: list[tuple[int, str]] = []
    title = action.title
    prefix = f"[action: {title}]"

    # Chunk 0: what the action is
    intro = action.description_text or ""
    chunks.append((0, f"{prefix} {title}. {intro}".strip()))

    # Chunk 1: how to do it
    if action.steps_to_take_text:
        chunks.append((1, f"{prefix} Steps to take: {action.steps_to_take_text}"))

    # Chunk 2+: deep dive — split if very long, otherwise single chunk
    if action.deep_dive_text:
        deep_dive_chunks = _split_long_text(action.deep_dive_text, MAX_CHUNK_CHARS)
        for i, segment in enumerate(deep_dive_chunks):
            chunks.append((2 + i, f"{prefix} {segment}"))

    return chunks


def chunk_testimonial(
    testimonial: Testimonial, action_title: str | None
) -> list[tuple[int, str]]:
    """Chunk a testimonial.

    Testimonials are short — one chunk each. The related action's title
    is prepended as context so a testimonial like "We saved $200" becomes
    "[testimonial about Switch to a Heat Pump] We saved $200" — much
    better retrieval signal than the body alone.

    If the testimonial has no related action, falls back to generic prefix.
    """
    if action_title:
        prefix = f"[testimonial about {action_title}]"
    else:
        prefix = "[testimonial]"

    body = testimonial.body_text or ""
    return [(0, f"{prefix} {body}".strip())]


def chunk_event(event: Event) -> list[tuple[int, str]]:
    """Chunk an event.

    Events are short and time-bound — one chunk each. Includes venue
    so semantic queries like 'events at the library' work correctly.
    """
    parts = [f"[event] {event.title}."]
    if event.description_text:
        parts.append(event.description_text)
    if event.venue_name:
        parts.append(f"Venue: {event.venue_name}.")

    return [(0, " ".join(parts))]


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Split long text into chunks of ~max_chars, preferring paragraph boundaries.

    Used for deep_dive content that may exceed our preferred chunk size.
    Greedy: accumulates paragraphs until the next would exceed max_chars.
    Falls back to character-based split if a single paragraph is too long.
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            # A single paragraph is too long — hard-split it
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(para), max_chars):
                chunks.append(para[i : i + max_chars])
            continue

        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current)

    return chunks
