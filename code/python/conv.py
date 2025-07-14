#!/usr/bin/env python3
"""
conv.py  –  Convert NLWeb JSONL into  <url>\t{json}  TSV.
Now VERBOSE: you’ll see why lines are kept or skipped.
"""

import json, sys, pathlib, collections, logging

logging.basicConfig(
    level=logging.INFO,   # change to DEBUG for even more detail
    format="%(levelname)s: %(message)s"
)

def reorder(jld: dict) -> dict:
    ordered = collections.OrderedDict()
    for key in ("@context", "@type"):
        if key in jld:
            ordered[key] = jld[key]
    if "name" in jld:
        ordered["name"] = jld["name"]
    for k, v in jld.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def convert_line(raw: str, n: int) -> str | None:
    try:
        obj = json.loads(raw)
        url     = obj.get("url")
        jsonlds = obj.get("jsonld", [])

        if not url:
            logging.warning(f"[line {n}] skipped – missing top-level 'url'")
            return None
        if not jsonlds:
            logging.warning(f"[line {n}] skipped – 'jsonld' empty")
            return None

        # keep only first jsonld object
        first = jsonlds[0] if isinstance(jsonlds, list) else jsonlds
        fixed = reorder(first)
        return f"{url}\t{json.dumps(fixed, ensure_ascii=False)}"

    except json.JSONDecodeError as e:
        logging.error(f"[line {n}] JSON parse error: {e}")
    except Exception as e:
        logging.error(f"[line {n}] unexpected error: {e}")
    return None


def main(src: pathlib.Path, dst: pathlib.Path):
    total = written = 0
    with src.open(encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
        for total, line in enumerate(fin, 1):
            out = convert_line(line, total)
            if out:
                fout.write(out + "\n")
                written += 1

    logging.info(f"Processed {total} lines → wrote {written} good lines to {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python conv.py input.jsonl output.tsv")
    main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
