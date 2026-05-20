from dotenv import load_dotenv

load_dotenv()

from newsletter_context import gather_newsletter_context

ctx = gather_newsletter_context(
    site_id=22,
    community_name="Sustainable Medfield",
    theme="winter heating and energy savings",
)

print(f"Community: {ctx.community_name}")
print(f"Theme: {ctx.theme}\n")

print(f"Featured actions ({len(ctx.featured_actions)}):")
for a in ctx.featured_actions:
    print(f"  - {a.title}")

print(f"\nTheme-relevant actions ({len(ctx.theme_actions)}):")
for a in ctx.theme_actions:
    print(f"  - {a.title}")

print(
    f"\nTestimonials linked to chosen actions: {sum(len(v) for v in ctx.testimonials_by_action.values())}"
)
for action_id, tests in ctx.testimonials_by_action.items():
    for t in tests:
        print(f"  - {t.title} (about action {action_id[:8]}...)")

print(f"\nUpcoming events ({len(ctx.upcoming_events)}):")
for e in ctx.upcoming_events:
    print(f"  - {e.title} ({e.start_datetime_utc})")
