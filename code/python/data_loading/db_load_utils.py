"""
Utilities for working with vector databases and document processing.
Includes functions for document creation, transformation, and database operations.
"""

from __future__ import annotations

import os
import json
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union

from core.config import CONFIG
from core.utils.trim_schema_json import trim_schema_json

# Item type categorization (left as-is for compatibility)
SKIP_TYPES: List[str] = []
INCLUDE_TYPES: List[str] = []

# Path constants (can be overridden by config)
EMBEDDINGS_PATH_SMALL = "./data/embeddings/small/"
EMBEDDINGS_PATH_LARGE = "./data/embeddings/large/"
EMBEDDING_SIZE = "small"

# ---------- File and JSON helpers ----------

async def read_file_lines(file_path: str) -> List[str]:
    encodings = ['utf-8', 'latin-1', 'utf-16']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                return [line.strip() for line in file if line.strip()]
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            raise
    raise ValueError(f"Could not read file {file_path} with any of the attempted encodings")

def int64_hash(string: str) -> np.int64:
    return np.int64(hash(string))

def get_item_name(item: Dict[str, Any]) -> str:
    # Prefer explicit names; fall back to URL/@id only if nothing else exists
    for field in ("name", "headline", "title", "keywords"):
        v = item.get(field)
        if isinstance(v, str) and v.strip():
            return v.strip()

    url = item.get("url") or item.get("@id")
    return url if isinstance(url, str) and url.strip() else "Unnamed Item"

# ---------- NEW: JSON-LD merging primitives ----------

def _extract_nodes(schema_json: Union[Dict[str, Any], List[Any], None]) -> List[Dict[str, Any]]:
    if not schema_json:
        return []
    if isinstance(schema_json, list):
        return [n for n in schema_json if isinstance(n, dict)]
    if isinstance(schema_json, dict):
        if "@graph" in schema_json and isinstance(schema_json["@graph"], list):
            return [n for n in schema_json["@graph"] if isinstance(n, dict)]
        return [schema_json]
    return []

def _identifier(n: Dict[str, Any]) -> Optional[str]:
    return n.get("@id") or n.get("url")

def _merge_types(a: Any, b: Any) -> List[str]:
    a_list = a if isinstance(a, list) else ([a] if a else [])
    b_list = b if isinstance(b, list) else ([b] if b else [])
    seen, result = set(), []
    for t in a_list + b_list:
        if not t:
            continue
        t = str(t)
        if t not in seen:
            seen.add(t)
            result.append(t)
    if "MedicalOrganization" in seen:
        result = ["MedicalOrganization"] + [t for t in result if t != "MedicalOrganization"]
    return result

def _merge_lists(a: List[Any], b: List[Any]) -> List[Any]:
    def key_of(item: Any):
        if isinstance(item, dict):
            iid = item.get("@id") or item.get("url")
            if iid: return ("id", str(iid))
            nm = str(item.get("name") or "")
            tp = item.get("@type")
            tp = ",".join(tp) if isinstance(tp, list) else str(tp or "")
            return ("name_type", nm + "|" + tp)
        return ("scalar", repr(item))

    out: List[Any] = []
    idx: Dict[tuple, int] = {}

    def add(it: Any):
        k = key_of(it)
        if k in idx:
            i = idx[k]
            if isinstance(out[i], dict) and isinstance(it, dict):
                out[i] = _deep_merge_nodes(out[i], it)
        else:
            idx[k] = len(out)
            out.append(it)

    for it in a: add(it)
    for it in b: add(it)
    return out

def _deep_merge_nodes(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in set(a.keys()) | set(b.keys()):
        av, bv = a.get(k), b.get(k)
        if k == "@type":
            out["@type"] = _merge_types(av, bv)
        elif isinstance(av, dict) and isinstance(bv, dict):
            out[k] = _deep_merge_nodes(av, bv)
        elif isinstance(av, list) and isinstance(bv, list):
            out[k] = _merge_lists(av, bv)
        elif bv not in (None, "", [], {}):
            out[k] = bv
        else:
            out[k] = av
    return out

def _normalize_node(n: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure @type is list
    t = n.get("@type")
    if isinstance(t, str):
        n["@type"] = [t]
    elif isinstance(t, list):
        seen, ordered = set(), []
        for x in t:
            xs = str(x)
            if xs and xs not in seen:
                seen.add(xs); ordered.append(xs)
        n["@type"] = ordered
    else:
        n["@type"] = []

    # Ensure @id present if url exists
    if not n.get("@id") and n.get("url"):
        n["@id"] = n["url"]

    # Strip empty values
    for k in list(n.keys()):
        v = n[k]
        if v in (None, "", [], {}):
            del n[k]
    return n

def build_objects_from_schema(schema_json: Union[Dict[str, Any], List[Any]]) -> List[Dict[str, Any]]:
    """
    - Accepts dict with @graph, list of nodes, or single node
    - Returns merged objects, one per unique @id/url
    """
    nodes = _extract_nodes(schema_json)
    if not nodes:
        return []

    merged: Dict[str, Dict[str, Any]] = {}
    for raw in nodes:
        ident = _identifier(raw) or raw.get("url")
        node = dict(raw)
        if not ident and node.get("url"):
            ident = node["url"]; node["@id"] = ident
        if not ident:
            # fall back: keep as independent row
            ident = f"__synthetic__::{id(node)}"
        merged[ident] = _deep_merge_nodes(merged[ident], node) if ident in merged else node

    return [_normalize_node(n) for n in merged.values()]

# ---------- Document preparation (UPDATED) ----------

def prepare_documents_from_json(url: str, json_data: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Prepare documents from URL and JSON data.
    Produces ONE record per logical entity by merging nodes with the same @id/url.
    """
    try:
        json_obj = json.loads(json_data)

        # Keep your existing trimming rules
        trimmed = trim_schema_json(json_obj, site)
        if not trimmed:
            return [], []

        # Merge by @id/url BEFORE emitting documents
        merged_objects = build_objects_from_schema(trimmed)

        documents: List[Dict[str, Any]] = []
        texts: List[str] = []

        for obj in merged_objects:
            item_url = obj.get("@id") or obj.get("url") or url
            item_json = json.dumps(obj, ensure_ascii=False)

            doc = {
                "id": str(int64_hash(item_url)),
                "schema_json": item_json,
                "url": item_url,
                "name": get_item_name(obj),
                "site": site
            }
            documents.append(doc)
            texts.append(item_json)

        return documents, texts

    except Exception as e:
        print(f"Error preparing documents from JSON: {str(e)}")
        return [], []

def documents_from_csv_line(line: str, site: str) -> List[Dict[str, Any]]:
    """
    Parse a TSV line of: URL \t JSON \t [embedding]
    Produces ONE record per logical entity by merging nodes with the same @id/url.
    """
    try:
        url, json_data, embedding_str = line.strip().split('\t')
        embedding_str = embedding_str.replace("[", "").replace("]", "")
        embedding = [float(x) for x in embedding_str.split(',') if x.strip()]
        js = json.loads(json_data)
        js = trim_schema_json(js, site)
    except Exception as e:
        print(f"Error processing line: {str(e)}")
        return []

    if js is None:
        return []

    merged_objects = build_objects_from_schema(js)

    documents: List[Dict[str, Any]] = []
    for obj in merged_objects:
        item_url = obj.get("@id") or obj.get("url") or url  # <-- no #i suffix anymore
        name = get_item_name(obj)

        doc = {
            "id": str(int64_hash(item_url)),
            "embedding": embedding,
            "schema_json": json.dumps(obj, ensure_ascii=False),
            "url": item_url,
            "name": name or "Unnamed Item",
            "site": site or "unknown"
        }

        # Final None-safety
        for k, v in list(doc.items()):
            if v is None:
                doc[k] = [] if k == "embedding" else ""

        documents.append(doc)

    return documents

# ---------- DB client wrappers (unchanged) ----------

async def get_vector_client(endpoint_name=None):
    from core.retriever import get_vector_db_client
    client = get_vector_db_client(endpoint_name)
    return client, client.db_type

async def upload_batch_to_db(client, db_type, documents, batch_idx, total_batches, endpoint_name=None):
    if not documents:
        return
    try:
        print(f"Uploading batch {batch_idx+1} of {total_batches} ({len(documents)} documents)")
        uploaded_count = await client.upload_documents(documents)
        print(f"Successfully uploaded batch {batch_idx+1} ({uploaded_count} documents)")
    except Exception as e:
        print(f"Error uploading batch {batch_idx+1}: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"Continuing with next batch...")

def resolve_file_path(file_path: str, with_embeddings: bool = False) -> str:
    if os.path.isabs(file_path):
        return file_path
    if os.path.exists(file_path):
        return os.path.abspath(file_path)
    if hasattr(CONFIG, 'nlweb'):
        base_folder = CONFIG.nlweb.json_with_embeddings_folder if with_embeddings else CONFIG.nlweb.json_data_folder
        os.makedirs(base_folder, exist_ok=True)
        return os.path.join(base_folder, os.path.basename(file_path))
    return file_path
