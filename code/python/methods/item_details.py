# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Item Details Handler for extracting details about specific items.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from core.prompts import find_prompt, fill_prompt
from misc.logger.logging_config_helper import get_configured_logger
from core.utils.json_utils import trim_json
from core.retriever import search, search_by_url
from core.llm import ask_llm

logger = get_configured_logger("item_details")

FIND_ITEM_THRESHOLD = 70


class ItemDetailsHandler():
    """Handler for finding and extracting details about specific items."""

    @staticmethod
    def _flatten_to_string(datum: Any) -> str:
        """
        Always return a single string.
        Priority:
          1) If datum is already a str, strip and return it.
          2) If it's a dict containing 'openingHoursText', return that.
          3) If it's a dict with 'opening_times', build "Day: HH:MM–HH:MM" segments.
          4) Otherwise, JSON-dump the datum.
        """
        if isinstance(datum, str):
            return datum.strip()

        if isinstance(datum, dict):
            # Use any openingHoursText provided
            if "openingHoursText" in datum:
                return str(datum["openingHoursText"]).strip()

            # Fall back to structured opening_times array
            if "opening_times" in datum:
                parts = []
                for entry in datum["opening_times"]:
                    day    = entry.get("day",   "").strip()
                    opens  = entry.get("opens", "").strip()
                    closes = entry.get("closes","").strip()
                    parts.append(f"{day}: {opens}–{closes}")
                return "; ".join(parts)

        # Fallback: serialize whatever it is
        return json.dumps(datum)

    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.item_name = ""
        self.details_requested = ""
        self.item_url = ""
        self.found_items = []
        self.sent_message = False

    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            self.item_name = self.params.get('item_name', '')
            self.details_requested = self.params.get('details_requested', '')
            self.item_url = self.params.get('item_url', '')

            if not self.details_requested:
                logger.warning("No details_requested found in tool routing results")
                await self._send_no_items_found_message()
                return

            if self.item_url:
                logger.info(f"Using URL-based retrieval for: {self.item_url}")
                await self._get_item_by_url()
            else:
                if not self.item_name:
                    logger.warning("No item_name found in tool routing results")
                    await self._send_no_items_found_message()
                    return

                logger.info(f"Using vector search for item: {self.item_name}")
                await self.handler.send_message({
                    "message_type": "intermediate_message",
                    "message": f"Searching for {self.item_name}"
                })

                candidate_items = await search(
                    self.item_name,
                    self.handler.site,
                    query_params=self.handler.query_params
                )

                await self._find_matching_items(candidate_items, self.details_requested)

                if not self.found_items:
                    logger.warning(f"No matching items found for: {self.item_name}")
                    await self._send_no_items_found_message()
                    return

        except Exception as e:
            logger.error(f"Error in ItemDetailsHandler.do(): {e}")
            await self._send_no_items_found_message()

    async def _find_matching_items(self, candidate_items: List[Dict[str, Any]], details_requested: str):
        """Find items that match the requested item using parallel LLM calls."""
        logger.info(f"Evaluating {len(candidate_items)} candidate items for '{self.item_name} {details_requested}'")

        tasks = [
            asyncio.create_task(self._evaluate_item_match(item, details_requested))
            for item in candidate_items
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        if self.sent_message:
            return

        self.found_items = [r for r in self.found_items if r]
        self.found_items.sort(key=lambda x: x.get("score", 0), reverse=True)

        if self.found_items:
            await self.handler.send_message(self.found_items[0])
            self.sent_message = True

    async def _evaluate_item_match(self, item: Union[List[Any], Dict[str, Any]], details_requested: str) -> Optional[Dict[str, Any]]:
        """Evaluate if an item matches the requested item."""
        try:
            if isinstance(item, list) and len(item) >= 4:
                url, json_str, name, site = item[0], item[1], item[2], item[3]
            else:
                return

            description = trim_json(json_str)
            self.handler.item_name = self.item_name

            prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "ItemMatchingPrompt")
            if not prompt_str:
                logger.error("ItemMatchingPrompt not found")
                return {"score": 0, "explanation": "Prompt not found"}

            pr_dict = {
                "item.description": description,
                "request.details_requested": details_requested
            }
            prompt = fill_prompt(prompt_str, self.handler, pr_dict)

            response = await ask_llm(prompt, ans_struc, level="high", query_params=self.handler.query_params)
            if not response or "score" not in response:
                logger.warning("No valid response from ItemMatchingPrompt")
                return {"score": 0, "explanation": "No response from LLM"}

            score = int(response.get("score", 0))
            explanation = response.get("explanation", "")

            if score > FIND_ITEM_THRESHOLD:
                raw_det = response.get("item_details", "")
                details_str = self._flatten_to_string(raw_det)
                message = {
                    "message_type":  "item_details",
                    "name":          name,
                    "details":       details_str,
                    "score":         score,
                    "explanation":   explanation,
                    "url":           url,
                    "site":          site,
                    "schema_object": json.loads(json_str)
                }
                self.found_items.append(message)

                if score > 75:
                    await self.handler.send_message(message)
                    logger.info(f"Sent item details for: {self.item_name}")
                    self.sent_message = True

        except Exception as e:
            logger.error(f"Error evaluating item match: {e}")
            return {"score": 0, "explanation": f"Error: {str(e)}"}

    async def _get_item_by_url(self):
        """Get item details using URL-based retrieval."""
        try:
            results = await search_by_url(
                self.item_url,
                query_params=self.handler.query_params
            )

            if not results:
                logger.warning(f"No item found for URL: {self.item_url}")
                await self._send_no_items_found_message()
                return

            item = results[0]
            if not (isinstance(item, list) and len(item) >= 4):
                logger.error(f"Invalid item format from search_by_url: {item}")
                await self._send_no_items_found_message()
                return

            url, json_str, name, site = item[0], item[1], item[2], item[3]

            prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "ExtractItemDetailsPrompt")
            if not prompt_str:
                logger.error("ExtractItemDetailsPrompt not found")
                message = {
                    "message_type":  "item_details",
                    "name":          name,
                    "details":       trim_json(json_str),
                    "url":           url,
                    "site":          site,
                    "schema_object": json.loads(json_str)
                }
                await self.handler.send_message(message)
                return

            pr_dict = {
                "item.description":        trim_json(json_str),
                "request.details_requested": self.details_requested,
                "request.query":           self.handler.query
            }
            prompt = fill_prompt(prompt_str, self.handler, pr_dict)

            response = await ask_llm(prompt, ans_struc, level="high", query_params=self.handler.query_params)
            if not response:
                logger.error("No response from ExtractItemDetailsPrompt")
                await self._send_no_items_found_message()
                return

            raw_det = response.get("requested_details", "")
            details_str = self._flatten_to_string(raw_det)
            message = {
                "message_type":       "item_details",
                "name":               response.get("item_name", name),
                "details":            details_str,
                "additional_context": response.get("additional_context", ""),
                "url":                url,
                "site":               site,
                "schema_object":      json.loads(json_str)
            }
            await self.handler.send_message(message)
            logger.info(f"Sent item details for URL: {self.item_url}")

        except Exception as e:
            logger.error(f"Error in _get_item_by_url: {e}")
            await self._send_no_items_found_message()

    async def _send_no_items_found_message(self):
        """Send message when no matching items are found."""
        message = {
            "message_type": "item_details",
            "item_name":    self.item_name,
            "details":      f"Could not find any items matching '{self.item_name}' on {self.handler.site}.",
            "score":        0,
            "url":          "",
            "site":         self.handler.site
        }
        await self.handler.send_message(message)
