# core/utils/dedupe_by_stub.py

from typing import List, Dict, Tuple
from urllib.parse import urlparse
import os
import logging

logger = logging.getLogger(__name__)
# Set to DEBUG while you’re debugging; you can raise this later
logger.setLevel(logging.INFO)

# Map netloc → integer priority
# Note: we include both www and non-www variants
_priority_map: Dict[str, int] = {
    "www.healthdirect.gov.au":       0,  # highest priority
    "healthdirect.gov.au":           0,
    "www.pregnancybirthbaby.org.au": 1,
    "pregnancybirthbaby.org.au":     1,
    # add more domains here…
}

def dedupe_by_stub(rows: List[List[str]]) -> List[List[str]]:
    """
    Collapse rows by URL-path stub, keeping the row whose domain has
    the lowest index in _priority_map (i.e. highest priority).
    """
    unique: Dict[str, Tuple[List[str], int]] = {}
    
    for row in rows:
        url = row[0]
        p = urlparse(url)
        # normalize domain
        netloc = p.netloc.lower().split(":")[0]
        priority = _priority_map.get(netloc, max(_priority_map.values(), default=0) + 1)
        
        # normalize path, strip trailing slash
        path = p.path.rstrip("/")
        # take the basename, then strip any extension
        basename = os.path.basename(path) or "/"
        stub = os.path.splitext(basename)[0] if basename != "/" else "/"
        
        # logging for debugging
        logger.debug(f"URL={url} → netloc={netloc}, priority={priority}, stub={stub}")
        
        if stub not in unique:
            unique[stub] = (row, priority)
            logger.debug(f"  → first occurrence of stub “{stub}” kept")
        else:
            _, existing_pr = unique[stub]
            if priority < existing_pr:
                unique[stub] = (row, priority)
                logger.debug(f"  → stub “{stub}” replaced by higher-priority domain {netloc}")
    
    # unpack only the rows, discarding stored priorities
    deduped = [entry for entry, _ in unique.values()]
    logger.info(f"dedupe_by_stub: reduced {len(rows)} rows to {len(deduped)} unique stubs")
    return deduped
