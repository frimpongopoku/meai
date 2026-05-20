from dotenv import load_dotenv

load_dotenv()
from __init__ import get_actions, get_testimonials, get_events

SITE_ID = 22  # Sustainable Medfield

print(f"\n=== Site {SITE_ID} ===\n")

actions = get_actions(SITE_ID)
print(f"Actions: {len(actions)}")
if actions:
    a = actions[0]
    print(f"  First: {a.title}")
    print(f"  Featured: {a.is_featured}, Order: {a.display_order}")
    print(f"  Image URL: {a.image_url}")
    print(f"  Classifications: {a.classifications}")
    print(f"  URL: {a.url}")
    print(f"  Desc preview: {a.description_text[:100]}...")

testimonials = get_testimonials(SITE_ID)
print(f"\nTestimonials: {len(testimonials)}")
if testimonials:
    t = testimonials[0]
    print(f"  First: {t.title}")
    print(f"  By: {t.submitted_by}")
    print(f"  Related action ID: {t.related_action_wp_post_id}")

events = get_events(SITE_ID)
print(f"\nEvents: {len(events)}")
if events:
    e = events[0]
    print(f"  First: {e.title}")
    print(f"  Starts: {e.start_datetime_utc}")
    print(f"  Venue: {e.venue_name}")
    print(f"  Organizers: {e.organizer_names}")
