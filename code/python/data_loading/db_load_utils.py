"""
Utilities for working with vector databases and document processing.
Includes functions for document creation, transformation, and database operations.
"""

import os
import json
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from core.config import CONFIG
from core.utils.trim_schema_json import trim_schema_json

# Item type categorization
SKIP_TYPES = []

INCLUDE_TYPES = []

# Path constants (can be overridden by config)
EMBEDDINGS_PATH_SMALL = "./data/embeddings/small/"
EMBEDDINGS_PATH_LARGE = "./data/embeddings/large/"
EMBEDDING_SIZE = "small"


#-- TEST MERGE GRAPH ------
def merge_graph_nodes(graph):
    merged = {}
    for node in graph:
        node_id = node.get('@id') or node.get('url')
        if not node_id:
            continue

        if node_id not in merged:
            # ensure @type is always a list
            merged[node_id] = { **node, 
                "@type": ([node["@type"]] if isinstance(node.get("@type"), str) else node.get("@type") or []) 
            }
        else:
            for k, v in node.items():
                if k == "@type":
                    # normalize both to lists and merge uniquely
                    existing = merged[node_id].get("@type") or []
                    existing_list = existing if isinstance(existing, list) else [existing]
                    new_list = v if isinstance(v, list) else [v]
                    merged[node_id]["@type"] = list(dict.fromkeys(existing_list + new_list))
                elif k not in merged[node_id]:
                    merged[node_id][k] = v
                elif isinstance(v, list) and isinstance(merged[node_id][k], list):
                    merged[node_id][k] += [x for x in v if x not in merged[node_id][k]]
                elif isinstance(v, dict) and isinstance(merged[node_id][k], dict):
                    merged[node_id][k].update(v)
                else:
                    merged[node_id][k] = v

    return list(merged.values())


# -- END TEST ---

# ---------- File and JSON Processing Functions ----------

async def read_file_lines(file_path: str) -> List[str]:
    """
    Read lines from a file, handling different encodings.
    
    Args:
        file_path: Path to the file
        
    Returns:
        List of lines from the file
    """
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

def int64_hash(string):
    """
    Compute a hash value for a string, ensuring it fits within int64 range.
    
    Args:
        string: The string to hash
        
    Returns:
        int64 hash value
    """
    hash_value = hash(string)
    return np.int64(hash_value)

def should_include_item(js):
    """
    Check if an item should be included based on its type.
    
    Args:
        js: JSON object to check
        
    Returns:
        True if the item should be included, False otherwise
    """
    if "@type" in js:
        item_type = js["@type"]
        if isinstance(item_type, list):
            if any(t in INCLUDE_TYPES for t in item_type):
                return True
        if item_type in INCLUDE_TYPES:
            return True
    elif "@graph" in js:
        for item in js["@graph"]:
            if should_include_item(item):
                return True
    return False

def normalize_item_list(js):
    """
    Normalize a JSON item list into a flat list of items.
    If @graph is present, merge nodes with duplicate @id or url.
    """
    items = []

    if isinstance(js, list):
        # Flatten any nested lists and merge their graphs
        for item in js:
            if isinstance(item, list) and len(item) == 1:
                item = item[0]
            if "@graph" in item:
                items.extend(merge_graph_nodes(item["@graph"]))
            else:
                items.append(item)

    elif "@graph" in js:
        items.extend(merge_graph_nodes(js["@graph"]))

    else:
        items.append(js)

    return items


def get_item_name(item: Dict[str, Any]) -> str:
    """
    Extract name from a JSON item using various fields.
    
    Args:
        item: JSON item to extract name from
        
    Returns:
        Name string or empty string if no name found
    """
    if isinstance(item, list):
        for subitem in item:
            name = get_item_name(subitem)
            if name:
                return name
    
    name_fields = ["name", "headline", "title", "keywords"]
    
    for field in name_fields:
        if field in item and item[field] and not str(item[field]).startswith('http'):
            return item[field]
        
    # Try to extract from URL if name fields aren't present
    url = None
    if "url" in item:
        url = item["url"]
    elif "@id" in item:
        url = item["@id"]
    
    if url:
        # Just return the URL as the name
        return url
    
    # If no URL found either, return a default name
    return "Unnamed Item"

# ---------- Document Preparation Functions ----------

def prepare_documents_from_json(url: str, json_data: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Prepare one merged document per outer URL.
    Collect all specialties and attach them as a 'specialties' array.
    """
    try:
        json_obj = json.loads(json_data)
        trimmed_json = trim_schema_json(json_obj, site)
        if not trimmed_json:
            return [], []

        # Start with empty merged_doc
        merged_doc = {}
        specialties = []

        # If trimmed_json is a list of nodes
        if isinstance(trimmed_json, list):
            for node in trimmed_json:
                # Add specialty info for pills
                specialty = node.get("medicalSpecialty")
                node_url = node.get("url") or node.get("@id")
                if specialty and node_url:
                    # Handle both single and list of specialties
                    specialty_names = []
                    if isinstance(specialty, list):
                        specialty_names = [
                            s.get("name") if isinstance(s, dict) else str(s)
                            for s in specialty
                        ]
                    else:
                        specialty_names = [specialty.get("name") if isinstance(specialty, dict) else str(specialty)]
                    for name in specialty_names:
                        if name and {"name": name, "url": node_url} not in specialties:
                            specialties.append({"name": name, "url": node_url})

                # Merge all node fields into merged_doc
                for k, v in node.items():
                    if k not in merged_doc:
                        merged_doc[k] = v
                    elif isinstance(v, list) and isinstance(merged_doc[k], list):
                        merged_doc[k] += [x for x in v if x not in merged_doc[k]]
                    elif isinstance(v, dict) and isinstance(merged_doc[k], dict):
                        merged_doc[k].update(v)
                    else:
                        merged_doc[k] = v

        else:
            merged_doc = trimmed_json

        # Attach specialties array
        if specialties:
            merged_doc["specialties"] = specialties

        # Fallbacks for URL and name
        item_url = merged_doc.get('@id') or merged_doc.get('url') or url
        if not item_url:
            print("WARNING: No URL found for merged document")
            return [], []

        item_name = get_item_name(merged_doc)
        if not item_name:
            print("WARNING: No name found for merged document")
            item_name = "Unnamed Item"

        item_json = json.dumps(merged_doc)

        doc = {
            "id": str(int64_hash(item_url)),
            "schema_json": item_json,
            "url": item_url,
            "name": item_name,
            "site": site
        }

        return [doc], [item_json]

    except Exception as e:
        print(f"Error preparing documents from JSON: {str(e)}")
        return [], []



def documents_from_csv_line(line, site):
    """
    Parse a line with URL, JSON, and embedding into document objects.
    
    Args:
        line: Tab-separated line with URL, JSON, and embedding
        site: Site identifier
        
    Returns:
        List of document objects
    """
    try:
        url, json_data, embedding_str = line.strip().split('\t')
        embedding_str = embedding_str.replace("[", "").replace("]", "") 
        embedding = [float(x) for x in embedding_str.split(',')]
        js = json.loads(json_data)
        js = trim_schema_json(js, site)
    except Exception as e:
        print(f"Error processing line: {str(e)}")
        return []
    
    # Skip if trim_schema_json returned None
    if js is None:
        return []
    
    documents = []
    if not isinstance(js, list):
        js = [js]
    
    for i, item in enumerate(js):
        # Skip None items in the list
        if item is None:
            continue
            
        # No longer filtering by should_include_item - trimming already handles this
        item_url = url if i == 0 else f"{url}#{i}"
        name = get_item_name(item)
        
        # Ensure no None values in the document
        doc = {
            "id": str(int64_hash(item_url)),
            "embedding": embedding,
            "schema_json": json.dumps(item),
            "url": item_url or "",
            "name": name or "Unnamed Item",
            "site": site or "unknown"
        }
        
        # Additional validation to ensure no None values
        for key, value in doc.items():
            if value is None:
                print(f"Warning: None value found for field '{key}' in document")
                if key == "embedding":
                    doc[key] = []
                else:
                    doc[key] = ""
        
        documents.append(doc)
    
    return documents

# ---------- Database Client Functions ----------

# Note: This function is maintained for backward compatibility
# In new code, import get_vector_db_client directly from retriever.py
async def get_vector_client(endpoint_name=None):
    """
    Get a client for the specified retrieval endpoint from config.
    This is a backward compatibility wrapper.
    For new code, import get_vector_db_client directly from retriever.py.
    
    Args:
        endpoint_name: Name of the endpoint to use (if None, uses preferred endpoint)
        
    Returns:
        Tuple of (client, db_type) for backward compatibility
    """
    # Dynamically import to avoid circular imports
    from core.retriever import get_vector_db_client
    
    # Get the client
    client = get_vector_db_client(endpoint_name)
    
    # Return both the client and the db_type for backward compatibility
    return client, client.db_type

# Note: This function is maintained for backward compatibility
async def upload_batch_to_db(client, db_type, documents, batch_idx, total_batches, endpoint_name=None):
    """
    Upload a batch of documents to the database using the client.
    This is a backward compatibility wrapper.
    For new code, use client.upload_documents() directly.
    
    Args:
        client: VectorDBClient instance
        db_type: Type of database (no longer used, kept for backward compatibility)
        documents: List of documents to upload
        batch_idx: Current batch index
        total_batches: Total number of batches
        endpoint_name: Name of the database endpoint to use (if None, uses preferred endpoint)
    """
    if not documents:
        return
    
    try:
        print(f"Uploading batch {batch_idx+1} of {total_batches} ({len(documents)} documents)")
        
        # Use the client's upload_documents method (db_type is ignored)
        uploaded_count = await client.upload_documents(documents)
            
        print(f"Successfully uploaded batch {batch_idx+1} ({uploaded_count} documents)")
    
    except Exception as e:
        print(f"Error uploading batch {batch_idx+1}: {str(e)}")
        import traceback
        traceback.print_exc()
        # Don't re-raise the exception to allow processing to continue with other batches
        print(f"Continuing with next batch...")

def resolve_file_path(file_path: str, with_embeddings: bool = False) -> str:
    """
    Resolve a file path, using config defaults for relative paths.
    
    Args:
        file_path: Original file path
        with_embeddings: Whether the file contains embeddings
        
    Returns:
        Resolved file path
    """
    # If path is absolute, return it as is
    if os.path.isabs(file_path):
        return file_path
    
    # If the file exists at the provided path, use it as is
    if os.path.exists(file_path):
        return os.path.abspath(file_path)
    
    # For relative paths, use the config
    if hasattr(CONFIG, 'nlweb'):
        if with_embeddings:
            base_folder = CONFIG.nlweb.json_with_embeddings_folder
        else:
            base_folder = CONFIG.nlweb.json_data_folder
            
        # Create the directory if it doesn't exist
        os.makedirs(base_folder, exist_ok=True)
        
        # Join the base folder with the provided file path
        # Make sure we're using the basename to avoid path duplication
        return os.path.join(base_folder, os.path.basename(file_path))
    
    # If config doesn't have nlweb settings, return the original path
    return file_path