"""Compose the prompts that Claude will use to draft a newsletter.

We separate this from generation so prompts can be inspected, tested,
and iterated on independently from the LLM call.
"""

from newsletter_context import NewsletterContext
from playbooks import load_playbook

# The output schema lives in code so both the prompt and the parser
# stay in sync. Change here, and both sides update together.
OUTPUT_SCHEMA = """{
  "subject_lines": ["string (6-9 words each, 3-5 options)"],
  "intro": "string (2-3 sentences, conversational tone)",
  "hero_image_url": "string or null (the most newsletter-worthy image from input)",
  "featured_actions": [
    {
      "action_title": "string (exact title from input)",
      "action_url": "string (exact URL from input)",
      "image_url": "string or null (exact image URL from input, if provided)",
      "body": "string (2-3 sentences in MassEnergize voice)",
      "call_to_action": "string (specific next step)"
    }
  ],
  "testimonial_highlight": {
    "related_action_title": "string",
    "image_url": "string or null (exact image URL from input, if provided)",
    "quote": "string (lightly edited if needed for clarity)",
    "attribution": "string (name of person who submitted)"
  },
  "upcoming_events": [
    {
      "title": "string",
      "image_url": "string or null (exact image URL from input, if provided)",
      "when": "string (human-readable date and time)",
      "where": "string (venue name, or 'Online')",
      "blurb": "string (one sentence)"
    }
  ],
  "closing": "string (2-3 sentences)"
}"""


def build_system_prompt() -> str:
    """The system prompt — voice, mission, schema, and the playbook."""
    playbook = load_playbook("newsletter-best-practices")

    return f"""You are drafting a newsletter for a MassEnergize community climate action team. \
MassEnergize is a nonprofit that supports local climate organizing across Massachusetts. \
Each community is run by volunteer organizers who send newsletters to their neighbors.

Your job: produce a warm, specific, neighborly newsletter draft that the organizer can \
review, lightly edit, and send via Mailchimp.

# Voice guide

{playbook.body_markdown}

# Output format

Respond with valid JSON only — no markdown code fences, no commentary. Match this schema exactly:

{OUTPUT_SCHEMA}

# Important rules

# Important rules

- Never invent actions, events, vendors, or testimonials. Use only what's provided in the user message.
- Pass through `action_url`, `action_title`, and `image_url` exactly as given — never modify them.
- For `hero_image_url`, pick the most visually engaging image from the featured actions or events you chose to include. If none feel newsletter-worthy, set it to null.
- If an action, event, or testimonial has no image in the input, set its `image_url` to null in the output.
- If no testimonial is appropriate or available, omit the `testimonial_highlight` field entirely (set it to null).
- If there are no upcoming events, set `upcoming_events` to an empty array.
- Don't include every action you're given — pick 2-3 that work best together for the newsletter."""


def build_user_prompt(ctx: NewsletterContext) -> str:
    """The user prompt — community data plus generation directive."""

    sections: list[str] = [
        f"# Community: {ctx.community_name}",
        "",
    ]

    if ctx.theme:
        sections.extend(
            [
                f"## Theme for this newsletter",
                ctx.theme,
                "",
            ]
        )

    # Featured actions
    if ctx.featured_actions:
        sections.append("## Featured actions (the community has elevated these)")
        sections.append("")
        for a in ctx.featured_actions:
            sections.extend(_format_action(a, ctx.testimonials_by_action))

    # Theme-relevant actions
    if ctx.theme_actions:
        if ctx.theme:
            sections.append("## Actions matching the theme")
        else:
            sections.append("## Other available actions")
        sections.append("")
        for a in ctx.theme_actions:
            sections.extend(_format_action(a, ctx.testimonials_by_action))

    # Upcoming events
    if ctx.upcoming_events:
        sections.append("## Upcoming events")
        sections.append("")
        for e in ctx.upcoming_events:
            sections.extend(_format_event(e))

    # Generation directive
    sections.extend(
        [
            "---",
            "",
            "Draft the newsletter as JSON following the schema in the system prompt.",
            "Pick 2-3 of the actions above that work best together.",
            "Pick at most one testimonial to highlight.",
            "Include all upcoming events in the events section.",
        ]
    )

    return "\n".join(sections)


def _format_action(action, testimonials_by_action: dict) -> list[str]:
    """Format one action and any linked testimonials for the prompt."""
    lines = [
        f"### {action.title}",
        f"- URL: {action.url}",
    ]
    if action.image_url:
        lines.append(f"- Image URL: {action.image_url}")
    if action.classifications:
        lines.append(f"- Classifications: {', '.join(action.classifications)}")

    if action.description_text:
        lines.extend(["", "Description:", action.description_text, ""])

    if action.steps_to_take_text:
        lines.extend(["Steps to take:", action.steps_to_take_text, ""])

    # Include linked testimonials inline so Claude sees the relationship
    linked = testimonials_by_action.get(str(action.id), [])
    if linked:
        lines.append("Linked testimonials:")
        for t in linked:
            attribution = t.display_name or t.submitted_by or "Anonymous"
            image_note = f" [image: {t.image_url}]" if t.image_url else ""
            lines.append(f'- "{t.body_text}" — {attribution}')
        lines.append("")

    lines.append("")
    return lines


def _format_event(event) -> list[str]:
    """Format one event for the prompt."""
    lines = [f"### {event.title}"]

    if event.image_url:
        lines.append(f"- Image URL: {event.image_url}")

    if event.start_datetime_local:
        # Use local time for the prompt — easier for Claude to format naturally
        lines.append(
            f"- When: {event.start_datetime_local.strftime('%A, %B %d at %I:%M %p')}"
        )

    if event.venue_name:
        location = event.venue_name
        if event.venue_address:
            location += f" ({event.venue_address})"
        lines.append(f"- Where: {location}")
    else:
        lines.append("- Where: Online or TBD")

    if event.event_url:
        lines.append(f"- URL: {event.event_url}")

    if event.description_text:
        # Truncate long event descriptions in the prompt
        desc = event.description_text[:500]
        if len(event.description_text) > 500:
            desc += "..."
        lines.extend(["", desc])

    lines.append("")
    return lines
