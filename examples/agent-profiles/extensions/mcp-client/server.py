"""Tiny owned MCP server used only to prove the example integration."""

from __future__ import annotations

import json
import sys
from typing import Any

CATALOG = {
    "widget": "Widget: a small example component.",
    "gadget": "Gadget: a larger example component.",
}


def response(request_id: Any, result: dict[str, Any]) -> None:
    print(
        json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}),
        flush=True,
    )


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        response(
            request_id,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "pi-agent-bench-example-catalog",
                    "version": "1.0.0",
                },
            },
        )
    elif method == "tools/list":
        response(
            request_id,
            {
                "tools": [
                    {
                        "name": "example_catalog_lookup",
                        "description": "Look up an item in the example catalog.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Catalog item name.",
                                }
                            },
                            "required": ["query"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        )
    elif method == "tools/call":
        params = message.get("params") or {}
        arguments = params.get("arguments") or {}
        query = str(arguments.get("query", "")).strip().lower()
        text = CATALOG.get(query, f"No catalog item named {query!r}.")
        response(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": f"BENCHMARK_MCP_MARKER\n{text}",
                    }
                ],
                "isError": query not in CATALOG,
            },
        )


def main() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict):
            handle(message)


if __name__ == "__main__":
    main()
