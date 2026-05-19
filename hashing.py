"""Content hashing for change detection."""

import hashlib
import json
from typing import Any


def compute_content_hash(*fields: Any) -> str:
    """Compute a stable hash from any combination of field values.

    Lists, dicts, and primitives are all supported. Order matters
    (pass fields in the same order every time for the same record type).
    """
    # Normalize each field to a JSON-serializable form, then hash the JSON
    serialized = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()