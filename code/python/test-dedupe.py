# test_dedupe.py

from core.utils.dedupe_by_stub import dedupe_by_stub

# Build a few rows whose URLs share the same stub (“page”) but come from different domains
rows = [
    ["https://www.healthdirect.gov.au/circumcision", ""],
    ["https://www.pregnancybirthbaby.org.au/circumcision", ""],
    ["https://www.healthdirect.gov.au/pelvic-floor-exercises",""],
    ["https://www.pregnancybirthbaby.org.au/pelvic-floor-exercises", ""]
]

deduped = dedupe_by_stub(rows)

print("Input stubs:   ", [row[0] for row in rows])
print("Deduped stubs: ", [row[0] for row in deduped])
