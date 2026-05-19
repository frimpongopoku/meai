"""Repository for reading WordPress multisite content.

All queries are scoped by site_id (the multisite blog_id).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from wp_db import wp_cursor

# =========================================================
# Domain objects (clean Python representations)
# =========================================================


@dataclass
class WPAction:
    site_id: int
    wp_post_id: int
    title: str
    description_html: str
    description_text: str
    steps_to_take_html: Optional[str]
    steps_to_take_text: Optional[str]
    deep_dive_html: Optional[str]
    deep_dive_text: Optional[str]
    is_featured: bool
    display_order: Optional[int]
    classifications: list[str]
    url: str
    status: str
    modified_at: datetime


@dataclass
class WPTestimonial:
    site_id: int
    wp_post_id: int
    title: Optional[str]
    body_html: str
    body_text: str
    submitted_by: Optional[str]
    display_name: Optional[str]
    related_action_wp_post_id: Optional[int]
    display_order: Optional[int]
    status: str
    modified_at: datetime


@dataclass
class WPEvent:
    site_id: int
    wp_post_id: int
    title: str
    description_html: str
    description_text: str
    start_datetime_utc: Optional[datetime]
    end_datetime_utc: Optional[datetime]
    start_datetime_local: Optional[datetime]
    end_datetime_local: Optional[datetime]
    timezone: Optional[str]
    venue_name: Optional[str]
    venue_address: Optional[str]
    organizer_names: Optional[str]
    organizer_emails: Optional[str]
    event_url: Optional[str]
    cost: Optional[str]
    status: str
    modified_at: datetime


# =========================================================
# Helpers
# =========================================================


def _strip_html(html: Optional[str]) -> str:
    """Convert WYSIWYG HTML to plain text. Returns empty string if input is None."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _table(site_id: int, table: str) -> str:
    """Return the multisite-prefixed table name for a given site.

    Site 1 in WordPress multisite uses 'wp_posts', everything else uses 'wp_N_posts'.
    """
    if site_id == 1:
        return f"wp_{table}"
    return f"wp_{site_id}_{table}"


# =========================================================
# Public functions
# =========================================================


def get_actions(site_id: int) -> list[WPAction]:
    """Fetch all published actions for a given site, with classifications."""
    posts_table = _table(site_id, "posts")
    meta_table = _table(site_id, "postmeta")

    sql = f"""
    SELECT
        p.ID,
        p.post_title,
        p.post_name,
        p.post_content,
        p.post_status,
        p.post_modified,
        MAX(CASE WHEN pm.meta_key = 'Steps_to_take' THEN pm.meta_value END) AS steps_to_take,
        MAX(CASE WHEN pm.meta_key = 'deep_dive' THEN pm.meta_value END) AS deep_dive,
        MAX(CASE WHEN pm.meta_key = 'is_featured' THEN pm.meta_value END) AS is_featured,
        MAX(CASE WHEN pm.meta_key = 'display_order' THEN pm.meta_value END) AS display_order
    FROM {posts_table} p
    LEFT JOIN {meta_table} pm ON p.ID = pm.post_id
    WHERE p.post_type = 'actions'
      AND p.post_status = 'publish'
    GROUP BY p.ID, p.post_title, p.post_name, p.post_content, p.post_status, p.post_modified
    ORDER BY p.ID
"""

    with wp_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

        action_ids = [row["ID"] for row in rows]
        classifications_map = _fetch_classifications(cur, site_id, action_ids)
        site_domain = _get_site_domain(cur, site_id)

    return [
        WPAction(
            site_id=site_id,
            wp_post_id=row["ID"],
            title=row["post_title"],
            description_html=row["post_content"] or "",
            description_text=_strip_html(row["post_content"]),
            steps_to_take_html=row["steps_to_take"],
            steps_to_take_text=_strip_html(row["steps_to_take"]),
            deep_dive_html=row["deep_dive"],
            deep_dive_text=_strip_html(row["deep_dive"]),
            is_featured=row["is_featured"] == "1",
            display_order=int(row["display_order"]) if row["display_order"] else None,
            classifications=classifications_map.get(row["ID"], []),
            url=f"{site_domain}actions/{row['post_name']}",
            status=row["post_status"],
            modified_at=row["post_modified"],
        )
        for row in rows
    ]


def get_testimonials(site_id: int) -> list[WPTestimonial]:
    """Fetch all published testimonials for a given site."""
    posts_table = _table(site_id, "posts")
    meta_table = _table(site_id, "postmeta")

    sql = f"""
        SELECT
            p.ID,
            p.post_title,
            p.post_content,
            p.post_status,
            p.post_modified,
            MAX(CASE WHEN pm.meta_key = 'submitted_by' THEN pm.meta_value END) AS submitted_by,
            MAX(CASE WHEN pm.meta_key = 'display_name' THEN pm.meta_value END) AS display_name,
            MAX(CASE WHEN pm.meta_key = 'related_action' THEN pm.meta_value END) AS related_action,
            MAX(CASE WHEN pm.meta_key = 'display_order' THEN pm.meta_value END) AS display_order
        FROM {posts_table} p
        LEFT JOIN {meta_table} pm ON p.ID = pm.post_id
        WHERE p.post_type = 'testimonials'
          AND p.post_status = 'publish'
        GROUP BY p.ID, p.post_title, p.post_content, p.post_status, p.post_modified
        ORDER BY p.ID
    """

    with wp_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    return [
        WPTestimonial(
            site_id=site_id,
            wp_post_id=row["ID"],
            title=row["post_title"],
            body_html=row["post_content"] or "",
            body_text=_strip_html(row["post_content"]),
            submitted_by=row["submitted_by"],
            display_name=row["display_name"],
            related_action_wp_post_id=(
                int(row["related_action"]) if row["related_action"] else None
            ),
            display_order=int(row["display_order"]) if row["display_order"] else None,
            status=row["post_status"],
            modified_at=row["post_modified"],
        )
        for row in rows
    ]


def get_events(site_id: int) -> list[WPEvent]:
    """Fetch all published events for a given site, with venue and organizers."""
    posts_table = _table(site_id, "posts")
    meta_table = _table(site_id, "postmeta")

    # Step 1: pull events + their single-value meta
    events_sql = f"""
        SELECT
            p.ID,
            p.post_title,
            p.post_content,
            p.post_status,
            p.post_modified,
            MAX(CASE WHEN pm.meta_key = '_EventStartDate' THEN pm.meta_value END) AS start_local,
            MAX(CASE WHEN pm.meta_key = '_EventEndDate' THEN pm.meta_value END) AS end_local,
            MAX(CASE WHEN pm.meta_key = '_EventStartDateUTC' THEN pm.meta_value END) AS start_utc,
            MAX(CASE WHEN pm.meta_key = '_EventEndDateUTC' THEN pm.meta_value END) AS end_utc,
            MAX(CASE WHEN pm.meta_key = '_EventTimezone' THEN pm.meta_value END) AS tz,
            MAX(CASE WHEN pm.meta_key = '_EventURL' THEN pm.meta_value END) AS event_url,
            MAX(CASE WHEN pm.meta_key = '_EventCost' THEN pm.meta_value END) AS cost,
            MAX(CASE WHEN pm.meta_key = '_EventVenueID' THEN pm.meta_value END) AS venue_id
        FROM {posts_table} p
        LEFT JOIN {meta_table} pm ON p.ID = pm.post_id
        WHERE p.post_type = 'tribe_events'
          AND p.post_status = 'publish'
        GROUP BY p.ID, p.post_title, p.post_content, p.post_status, p.post_modified
        ORDER BY p.ID
    """

    with wp_cursor() as cur:
        cur.execute(events_sql)
        event_rows = cur.fetchall()

        # Step 2: for each event, fetch ALL organizer IDs (multi-row meta)
        # We'll batch this rather than N+1 querying.
        event_ids = [r["ID"] for r in event_rows]
        organizer_map: dict[int, list[int]] = {eid: [] for eid in event_ids}

        if event_ids:
            placeholders = ",".join(["%s"] * len(event_ids))
            cur.execute(
                f"""
                SELECT post_id, meta_value
                FROM {meta_table}
                WHERE meta_key = '_EventOrganizerID'
                  AND post_id IN ({placeholders})
                """,
                event_ids,
            )
            for row in cur.fetchall():
                organizer_map[row["post_id"]].append(int(row["meta_value"]))

        # Step 3: collect all venue + organizer IDs we need to look up
        venue_ids = {int(r["venue_id"]) for r in event_rows if r["venue_id"]}
        all_organizer_ids = {oid for oids in organizer_map.values() for oid in oids}

        # Step 4: fetch venue details
        venues = _fetch_venues(cur, site_id, venue_ids)
        organizers = _fetch_organizers(cur, site_id, all_organizer_ids)

    # Step 5: assemble final event objects
    events = []
    for row in event_rows:
        venue_id = int(row["venue_id"]) if row["venue_id"] else None
        venue = venues.get(venue_id) if venue_id else None

        org_ids = organizer_map.get(row["ID"], [])
        orgs = [organizers[oid] for oid in org_ids if oid in organizers]

        events.append(
            WPEvent(
                site_id=site_id,
                wp_post_id=row["ID"],
                title=row["post_title"],
                description_html=row["post_content"] or "",
                description_text=_strip_html(row["post_content"]),
                start_datetime_utc=_parse_dt(row["start_utc"]),
                end_datetime_utc=_parse_dt(row["end_utc"]),
                start_datetime_local=_parse_dt(row["start_local"]),
                end_datetime_local=_parse_dt(row["end_local"]),
                timezone=row["tz"],
                venue_name=venue["name"] if venue else None,
                venue_address=venue["address"] if venue else None,
                organizer_names=", ".join(o["name"] for o in orgs) if orgs else None,
                organizer_emails=(
                    ", ".join(o["email"] for o in orgs if o["email"]) if orgs else None
                ),
                event_url=row["event_url"] or None,
                cost=row["cost"] or None,
                status=row["post_status"],
                modified_at=row["post_modified"],
            )
        )

    return events


def _get_site_domain(cur, site_id: int) -> str:
    """Fetch the domain for a given multisite blog ID from wp_blogs."""
    cur.execute(
        "SELECT domain, path FROM wp_blogs WHERE blog_id = %s",
        (site_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"No site found with blog_id={site_id}")
    return f"https://{row['domain']}{row['path']}"


# =========================================================
# Internal helpers for events
# =========================================================


def _fetch_venues(cur, site_id: int, venue_ids: set[int]) -> dict[int, dict]:
    """Return {venue_post_id: {name, address}} for the requested venues."""
    if not venue_ids:
        return {}

    posts_table = _table(site_id, "posts")
    meta_table = _table(site_id, "postmeta")
    placeholders = ",".join(["%s"] * len(venue_ids))

    cur.execute(
        f"""
        SELECT
            p.ID,
            p.post_title,
            MAX(CASE WHEN pm.meta_key = '_VenueAddress' THEN pm.meta_value END) AS address,
            MAX(CASE WHEN pm.meta_key = '_VenueCity' THEN pm.meta_value END) AS city,
            MAX(CASE WHEN pm.meta_key = '_VenueState' THEN pm.meta_value END) AS state,
            MAX(CASE WHEN pm.meta_key = '_VenueZip' THEN pm.meta_value END) AS zip
        FROM {posts_table} p
        LEFT JOIN {meta_table} pm ON p.ID = pm.post_id
        WHERE p.ID IN ({placeholders})
        GROUP BY p.ID, p.post_title
        """,
        list(venue_ids),
    )

    result = {}
    for row in cur.fetchall():
        parts = [row["address"], row["city"], row["state"], row["zip"]]
        full_address = ", ".join(p for p in parts if p)
        result[row["ID"]] = {
            "name": row["post_title"],
            "address": full_address or None,
        }
    return result


def _fetch_organizers(cur, site_id: int, organizer_ids: set[int]) -> dict[int, dict]:
    """Return {organizer_post_id: {name, email}} for the requested organizers."""
    if not organizer_ids:
        return {}

    posts_table = _table(site_id, "posts")
    meta_table = _table(site_id, "postmeta")
    placeholders = ",".join(["%s"] * len(organizer_ids))

    cur.execute(
        f"""
        SELECT
            p.ID,
            p.post_title,
            MAX(CASE WHEN pm.meta_key = '_OrganizerEmail' THEN pm.meta_value END) AS email
        FROM {posts_table} p
        LEFT JOIN {meta_table} pm ON p.ID = pm.post_id
        WHERE p.ID IN ({placeholders})
        GROUP BY p.ID, p.post_title
        """,
        list(organizer_ids),
    )

    return {
        row["ID"]: {"name": row["post_title"], "email": row["email"]}
        for row in cur.fetchall()
    }


def _fetch_classifications(
    cur, site_id: int, action_ids: list[int]
) -> dict[int, list[str]]:
    """Return {action_post_id: [classification_slug, ...]} for the requested actions."""
    if not action_ids:
        return {}

    terms_table = _table(site_id, "terms")
    tt_table = _table(site_id, "term_taxonomy")
    tr_table = _table(site_id, "term_relationships")
    placeholders = ",".join(["%s"] * len(action_ids))

    cur.execute(
        f"""
        SELECT
            tr.object_id AS action_id,
            t.slug AS classification
        FROM {tr_table} tr
        JOIN {tt_table} tt ON tr.term_taxonomy_id = tt.term_taxonomy_id
        JOIN {terms_table} t ON tt.term_id = t.term_id
        WHERE tt.taxonomy = 'classifications'
          AND tr.object_id IN ({placeholders})
        """,
        action_ids,
    )

    result: dict[int, list[str]] = {aid: [] for aid in action_ids}
    for row in cur.fetchall():
        result[row["action_id"]].append(row["classification"])
    return result


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """Parse a MySQL datetime string. Returns None on empty/invalid input."""
    if not s or s == "0000-00-00 00:00:00":
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
