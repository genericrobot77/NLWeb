from typing import List, Dict, Tuple
from urllib.parse import urlparse, unquote
import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Map each domain to its priority (lower = higher priority)
_priority_map: Dict[str, int] = {
    "www.healthdirect.gov.au":       0,
    "healthdirect.gov.au":           0,
    "www.pregnancybirthbaby.org.au": 1,
    "pregnancybirthbaby.org.au":     1,
    # …add others here
}

EXCLUDE_PREFIX = "https://www.healthdirect.gov.au/australian-health-services/healthcare-service"

def dedupe_by_stub(rows: List[List[str]]) -> List[List[str]]:
    """
    Collapse rows by URL‐path stub, keeping the row whose domain has
    the lowest index in _priority_map—but only for URLs with exactly one
    path segment after the domain (and not matching our exclude prefix).
    All other rows are returned unchanged.

    **New**: If the returned rows do *not* contain at least one
    healthdirect.gov.au *and* one pregnancybirthbaby.org.au URL,
    we skip all deduplication and return `rows` immediately.
    """
    # --- 0) Quick domain check: bail if we don't need dedupe at all ---
    netlocs = { urlparse(r[0]).netloc.lower() for r in rows }
    has_hd  = any("healthdirect.gov.au"    in nl for nl in netlocs)
    has_pbb = any("pregnancybirthbaby.org.au" in nl for nl in netlocs)
    if not (has_hd and has_pbb):
        logger.debug("Skipping dedupe_by_stub: need both HD and PBB domains, only found %r", netlocs)
        return rows

    # --- 1) Split into passthrough vs candidates for stub‐dedupe ---
    passthrough: List[List[str]] = []
    to_dedupe:   List[List[str]] = []

    for row in rows:
        url = row[0]

        # Exclude our special prefix URLs entirely
        if EXCLUDE_PREFIX in url:
            logger.debug(f"Skipping (exclude prefix): {url}")
            passthrough.append(row)
            continue

        p = urlparse(url)
        path = unquote(p.path).strip("/")
        segments = [seg for seg in path.split("/") if seg]

        # Only dedupe single-segment paths
        if len(segments) == 1:
            to_dedupe.append(row)
        else:
            logger.debug(f"Skipping (multi‐segment): {url}")
            passthrough.append(row)

    # --- 2) Perform stub dedupe on our selected rows ---
    unique: Dict[str, Tuple[List[str], int]] = {}
    default_pr = max(_priority_map.values(), default=0) + 1

    for row in to_dedupe:
        url = row[0]
        p = urlparse(url)
        netloc = p.netloc.lower().split(":", 1)[0]
        priority = _priority_map.get(netloc, default_pr)

        # stub = final path segment sans extension
        path = unquote(p.path).rstrip("/")
        basename = os.path.basename(path)
        name, _ext = os.path.splitext(basename)
        stub = name.lower() or "/"

        logger.debug(f"URL={url} → netloc={netloc}, pr={priority}, stub={stub!r}")

        existing = unique.get(stub)
        if existing is None or priority < existing[1]:
            unique[stub] = (row, priority)
            logger.debug(f"  → keeping row for stub {stub!r} (pr={priority})")

    deduped = [entry for entry, _ in unique.values()]

    # --- 3) Merge back passthrough rows and return ---
    result = deduped + passthrough
    logger.info(f"dedupe_by_stub: {len(rows)} → {len(result)} rows (deduped {len(to_dedupe)} targets)")
    return result
