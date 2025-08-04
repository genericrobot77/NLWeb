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

def dedupe_by_stub(rows: List[List[str]]) -> List[List[str]]:
    """
    Collapse rows by URL‐path stub, keeping the row whose domain has
    the lowest index in _priority_map.
    """
    unique: Dict[str, Tuple[List[str], int]] = {}
    default_pr = max(_priority_map.values(), default=0) + 1

    for row in rows:
        url = row[0]
        p = urlparse(url)
        netloc = p.netloc.lower().split(":", 1)[0]
        priority = _priority_map.get(netloc, default_pr)

        # decode any %-encoding, strip trailing slash
        path = unquote(p.path).rstrip("/")
        if not path or path == "":
            stub = "/"  # root index stub
        else:
            # take final path segment, strip extension, lowercase
            basename = os.path.basename(path)
            name, _ext = os.path.splitext(basename)
            stub = name.lower()

        logger.debug(f"URL={url} → netloc={netloc}, pr={priority}, stub={stub!r}")

        # if new stub, or this row has higher priority, keep it
        existing = unique.get(stub)
        if existing is None or priority < existing[1]:
            unique[stub] = (row, priority)
            logger.debug(f"  → keeping row for stub {stub!r} (pr={priority})")

    deduped = [entry for entry, _ in unique.values()]
    logger.info(f"dedupe_by_stub: {len(rows)} → {len(deduped)} unique stubs")
    return deduped
