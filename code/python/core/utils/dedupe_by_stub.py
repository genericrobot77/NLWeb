from typing import List, Dict
from urllib.parse import urlparse

# Map each domain (netloc) to an integer priority.
# Lower numbers = higher priority. Unknown domains default to lowest priority.
_priority_map: Dict[str, int] = {
    "www.healthdirect.gov.au":      0,  # highest priority
    "www.pregnancybirthbaby.org.au": 1,
    # add more domains here in priority order…
}

def dedupe_by_stub(rows: List[List[str]]) -> List[List[str]]:
    """
    Collapse rows by URL‐path stub, keeping the row whose domain has
    the lowest index in _priority_map (i.e. highest priority).
    
    Args:
        rows: List of rows, each row is a List[str] where the first element
              is expected to be a URL.
    
    Returns:
        A filtered list of rows, one per unique URL stub. If multiple rows
        share the same path stub, the row from the domain with the higher
        priority (lower index) is kept.
    """
    # Will hold the winning row for each stub
    unique: Dict[str, List[str]] = {}
    
    for row in rows:
        url = row[0]
        p = urlparse(url)
        
        # Normalize the path by stripping any trailing slash
        #stub = p.path.rstrip("/")
        path = p.path.rstrip("/")
        segments = [seg for seg in path.split("/") if seg]
        stub = segments[-1] if segments else "/"
        
        # Look up this domain’s priority, defaulting to lowest if unknown
        priority = _priority_map.get(p.netloc, len(_priority_map))
        
        if stub not in unique:
            # First time we see this stub – keep it
            unique[stub] = row
        else:
            # Compare against the existing winner for this stub
            existing_url = unique[stub][0]
            existing_p   = urlparse(existing_url)
            existing_pr  = _priority_map.get(existing_p.netloc, len(_priority_map))
            
            # If this row’s domain outranks the existing one, replace it
            if priority < existing_pr:
                unique[stub] = row
    
    # Return only the chosen (deduped) rows
    return list(unique.values())
