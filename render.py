"""Render a newsletter draft as markdown or HTML preview.

The JSON output from generation is the source of truth. Renderers
just take it and shape it into something humans can review.
"""

from typing import Any


def render_markdown(draft: dict[str, Any]) -> str:
    """Render the structured draft as markdown.

    Best for terminal review, copy-paste into docs, or version-controlled
    drafts. Not what the recipient sees — that's the HTML version.
    """
    lines: list[str] = []

    # Subject line options at the top so the organizer can pick
    lines.append("# Subject line options\n")
    for sl in draft.get("subject_lines", []):
        lines.append(f"- {sl}")
    lines.append("")

    # Hero image
    hero = draft.get("hero_image_url")
    if hero:
        lines.append(f"![Hero image]({hero})")
        lines.append("")

    # Intro
    intro = draft.get("intro")
    if intro:
        lines.append(intro)
        lines.append("")

    # Featured actions
    for action in draft.get("featured_actions", []):
        lines.append(f"## {action['action_title']}")
        lines.append("")
        if action.get("image_url"):
            lines.append(f"![{action['action_title']}]({action['image_url']})")
            lines.append("")
        if action.get("body"):
            lines.append(action["body"])
            lines.append("")
        if action.get("call_to_action"):
            lines.append(f"**{action['call_to_action']}**")
            lines.append("")
        if action.get("action_url"):
            lines.append(f"[Learn more →]({action['action_url']})")
            lines.append("")

    # Testimonial highlight
    testimonial = draft.get("testimonial_highlight")
    if testimonial:
        lines.append("## From a neighbor")
        lines.append("")
        if testimonial.get("image_url"):
            lines.append(f"![{testimonial.get('attribution', '')}]({testimonial['image_url']})")
            lines.append("")
        lines.append(f"> {testimonial['quote']}")
        lines.append("")
        attribution = testimonial.get("attribution", "")
        related = testimonial.get("related_action_title", "")
        if attribution and related:
            lines.append(f"— **{attribution}**, on _{related}_")
        elif attribution:
            lines.append(f"— **{attribution}**")
        lines.append("")

    # Upcoming events
    events = draft.get("upcoming_events", [])
    if events:
        lines.append("## Upcoming events")
        lines.append("")
        for event in events:
            event_line = f"- **{event['title']}** — {event.get('when', '')}"
            where = event.get("where")
            if where:
                event_line += f" at {where}"
            lines.append(event_line)
            if event.get("blurb"):
                lines.append(f"  {event['blurb']}")
        lines.append("")

    # Closing
    closing = draft.get("closing")
    if closing:
        lines.append("---")
        lines.append("")
        lines.append(closing)
        lines.append("")

    return "\n".join(lines)


def render_html(draft: dict[str, Any], community_name: str = "") -> str:
    """Render the structured draft as a simple HTML preview.

    This is what gets opened in a browser to see the newsletter as it
    might actually look. Mailchimp will apply its own styling on top of
    the eventual paste, so we keep this minimal and clean.
    """
    parts: list[str] = []
    parts.append(_html_head(community_name))
    parts.append('<div class="newsletter">')

    # Subject lines at the top for organizer reference (would be cut before sending)
    parts.append('<div class="subject-lines">')
    parts.append("<strong>Subject line options (pick one before sending):</strong>")
    parts.append("<ul>")
    for sl in draft.get("subject_lines", []):
        parts.append(f"<li>{_escape(sl)}</li>")
    parts.append("</ul>")
    parts.append("</div>")

    parts.append('<hr class="divider">')

    # Hero image
    hero = draft.get("hero_image_url")
    if hero:
        parts.append(f'<img src="{_escape(hero)}" alt="" class="hero">')

    # Intro
    intro = draft.get("intro")
    if intro:
        parts.append(f'<p class="intro">{_escape(intro)}</p>')

    # Featured actions
    for action in draft.get("featured_actions", []):
        parts.append('<section class="action">')
        parts.append(f"<h2>{_escape(action['action_title'])}</h2>")
        if action.get("image_url"):
            parts.append(
                f'<img src="{_escape(action["image_url"])}" alt="{_escape(action["action_title"])}" class="action-image">'
            )
        if action.get("body"):
            parts.append(f"<p>{_escape(action['body'])}</p>")
        if action.get("call_to_action"):
            parts.append(f'<p class="cta"><strong>{_escape(action["call_to_action"])}</strong></p>')
        if action.get("action_url"):
            parts.append(
                f'<p><a href="{_escape(action["action_url"])}" class="link">Learn more →</a></p>'
            )
        parts.append("</section>")

    # Testimonial
    testimonial = draft.get("testimonial_highlight")
    if testimonial:
        parts.append('<section class="testimonial">')
        parts.append("<h2>From a neighbor</h2>")
        if testimonial.get("image_url"):
            parts.append(
                f'<img src="{_escape(testimonial["image_url"])}" alt="" class="testimonial-image">'
            )
        parts.append(f'<blockquote>{_escape(testimonial["quote"])}</blockquote>')
        attribution = testimonial.get("attribution", "")
        related = testimonial.get("related_action_title", "")
        if attribution:
            cite = f'<strong>{_escape(attribution)}</strong>'
            if related:
                cite += f", on <em>{_escape(related)}</em>"
            parts.append(f'<p class="attribution">— {cite}</p>')
        parts.append("</section>")

    # Events
    events = draft.get("upcoming_events", [])
    if events:
        parts.append('<section class="events">')
        parts.append("<h2>Upcoming events</h2>")
        parts.append("<ul>")
        for event in events:
            event_html = f"<li><strong>{_escape(event['title'])}</strong>"
            if event.get("when"):
                event_html += f" — {_escape(event['when'])}"
            if event.get("where"):
                event_html += f" at {_escape(event['where'])}"
            if event.get("blurb"):
                event_html += f"<br><span class='blurb'>{_escape(event['blurb'])}</span>"
            event_html += "</li>"
            parts.append(event_html)
        parts.append("</ul>")
        parts.append("</section>")

    # Closing
    closing = draft.get("closing")
    if closing:
        parts.append(f'<p class="closing">{_escape(closing)}</p>')

    parts.append("</div>")
    parts.append(_html_foot())

    return "\n".join(parts)


def _escape(text: str) -> str:
    """Minimal HTML escaping for user-facing strings."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_head(community_name: str) -> str:
    title = f"{community_name} Newsletter Preview" if community_name else "Newsletter Preview"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_escape(title)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    max-width: 640px;
    margin: 2rem auto;
    padding: 0 1rem;
    color: #1f2937;
    line-height: 1.6;
  }}
  .newsletter {{
    background: white;
  }}
  .subject-lines {{
    background: #fef3c7;
    padding: 1rem 1.25rem;
    border-radius: 6px;
    border-left: 4px solid #f59e0b;
    margin-bottom: 1.5rem;
    font-size: 0.9rem;
  }}
  .subject-lines ul {{
    margin: 0.5rem 0 0;
    padding-left: 1.25rem;
  }}
  .divider {{
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 1.5rem 0;
  }}
  .hero {{
    width: 100%;
    height: auto;
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }}
  .intro {{
    font-size: 1.05rem;
    margin-bottom: 2rem;
  }}
  section {{
    margin-bottom: 2.5rem;
  }}
  h2 {{
    font-size: 1.35rem;
    margin: 0 0 0.75rem;
    color: #111827;
  }}
  .action-image, .testimonial-image {{
    width: 100%;
    height: auto;
    border-radius: 8px;
    margin-bottom: 1rem;
  }}
  .cta {{
    color: #047857;
  }}
  .link {{
    color: #047857;
    text-decoration: none;
    font-weight: 500;
  }}
  blockquote {{
    margin: 0 0 0.5rem;
    padding: 1rem 1.25rem;
    background: #f9fafb;
    border-left: 4px solid #047857;
    font-style: italic;
    border-radius: 4px;
  }}
  .attribution {{
    margin: 0;
    color: #6b7280;
    font-size: 0.95rem;
  }}
  .events ul {{
    list-style: none;
    padding: 0;
  }}
  .events li {{
    padding: 0.75rem 0;
    border-bottom: 1px solid #e5e7eb;
  }}
  .events li:last-child {{
    border-bottom: none;
  }}
  .blurb {{
    color: #6b7280;
    font-size: 0.95rem;
  }}
  .closing {{
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid #e5e7eb;
    color: #4b5563;
  }}
</style>
</head>
<body>
"""


def _html_foot() -> str:
    return "</body>\n</html>"