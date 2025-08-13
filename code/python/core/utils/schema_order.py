# core/utils/schema_order.py
from typing import Any, Dict

# Put top-level keys in this order; anything not listed comes after,
# and openingHoursSpecification is always last.
PREFERRED_TOP_ORDER = [
    "@context",
    "@type",
    "address",            # surfaced from location if present
    "location",
    "medicalSpecialty",
    "name",
    "@id",
    "url",
    "contactPoint",
    "additionalProperty",
]

def _reorder_location(loc: Dict[str, Any]) -> Dict[str, Any]:
    # Make address prominent inside location as well
    loc_order = ["@type", "address", "name", "geo", "hasMap"]
    out = {}
    for k in loc_order:
        if k in loc:
            out[k] = loc[k]
    for k, v in loc.items():
        if k not in out:
            out[k] = v
    return out

def reorder_schema_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(obj)

    # Surface address to top-level (copy, do not delete from location)
    if "address" not in d:
        loc = d.get("location")
        if isinstance(loc, dict) and "address" in loc:
            d["address"] = loc["address"]

    out: Dict[str, Any] = {}

    # Place preferred keys in order
    for k in PREFERRED_TOP_ORDER:
        if k in d:
            out[k] = d[k]

    # Add any remaining keys (except openingHoursSpecification)
    for k, v in d.items():
        if k not in out and k != "openingHoursSpecification":
            out[k] = v

    # Always put opening hours last
    if "openingHoursSpecification" in d:
        out["openingHoursSpecification"] = d["openingHoursSpecification"]

    # Tidy up nested location ordering
    if isinstance(out.get("location"), dict):
        out["location"] = _reorder_location(out["location"])

    return out
