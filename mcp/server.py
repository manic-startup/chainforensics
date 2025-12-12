#!/usr/bin/env python3
"""
ChainForensics MCP Server
Thin wrapper that exposes ChainForensics API to Claude Desktop via MCP protocol.

This server communicates with the ChainForensics API internally,
allowing Claude to perform blockchain analysis through natural conversation.
"""
import asyncio
import json
import logging
import sys
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    INTERNAL_ERROR,
    INVALID_PARAMS,
)
from pydantic import AnyUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("chainforensics-mcp")

# Configuration
API_BASE_URL = "http://localhost:3000/api/v1"
API_TIMEOUT = 120  # seconds

# Create MCP server
server = Server("chainforensics")


async def api_call(endpoint: str, params: dict = None) -> dict:
    """Make a call to the ChainForensics API."""
    url = f"{API_BASE_URL}{endpoint}"
    
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            if params:
                response = await client.get(url, params=params)
            else:
                response = await client.get(url)
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API error: {e}")
            return {"error": str(e), "status_code": e.response.status_code}
        except httpx.ConnectError:
            return {"error": "Cannot connect to ChainForensics API. Is the server running?"}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": str(e)}


async def api_post(endpoint: str, data: dict) -> dict:
    """Make a POST call to the ChainForensics API."""
    url = f"{API_BASE_URL}{endpoint}"
    
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            response = await client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            return {"error": str(e)}


def format_timeline_ascii(trace_data: dict) -> str:
    """Format trace data as ASCII timeline."""
    nodes = trace_data.get("nodes", [])
    if not nodes:
        return "No data to display in timeline."
    
    # Sort by block time
    sorted_nodes = sorted(
        [n for n in nodes if n.get("block_time")],
        key=lambda x: x.get("block_time", "")
    )
    
    if not sorted_nodes:
        return "No dated transactions in trace."
    
    # Find max value for scaling
    max_value = max((n.get("value_btc", 0) for n in sorted_nodes), default=1)
    bar_width = 30
    
    lines = []
    lines.append("=" * 80)
    lines.append("UTXO TIMELINE")
    lines.append(f"Start: {trace_data.get('start_txid', 'N/A')[:16]}...")
    lines.append("=" * 80)
    lines.append("")
    
    current_date = None
    
    for node in sorted_nodes:
        # Parse date
        block_time = node.get("block_time", "")
        if block_time:
            date_str = block_time[:10]
        else:
            date_str = "Unknown"
        
        # Date column
        if date_str != current_date:
            date_display = date_str
            current_date = date_str
        else:
            date_display = " " * 10
        
        # Value bar
        value = node.get("value_btc", 0)
        bar_length = int((value / max_value) * bar_width) if max_value > 0 else 1
        bar_length = max(1, bar_length)
        bar = "█" * bar_length
        
        # Value string
        if value >= 0.1:
            val_str = f"{value:.4f} BTC"
        elif value >= 0.001:
            val_str = f"{value:.6f} BTC"
        else:
            val_str = f"{int(value * 100_000_000)} sats"
        
        # Status/type indicator
        status = node.get("status", "")
        cj_score = node.get("coinjoin_score", 0)
        
        if cj_score > 0.7:
            indicator = f"🔀 CoinJoin ({cj_score*100:.0f}%)"
        elif status == "unspent":
            indicator = "💰 Unspent"
        elif status == "coinbase":
            indicator = "⛏️ Coinbase"
        else:
            indicator = "📤 Spent"
        
        # Build line
        line = f"{date_display} │ {bar:<{bar_width}} {val_str:<15} {indicator}"
        lines.append(line)
    
    # Add blank line between dates
    lines.append(" " * 10 + " │")
    
    # Summary
    lines.append("=" * 80)
    summary = trace_data.get("summary", {})
    lines.append(f"Unspent outputs: {summary.get('unspent_count', 'N/A')}")
    lines.append(f"CoinJoin transactions: {summary.get('coinjoin_count', 0)}")
    lines.append(f"Total nodes: {summary.get('total_nodes', len(nodes))}")
    lines.append("=" * 80)
    
    return "\n".join(lines)


# ============== Tool Definitions ==============

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available ChainForensics tools."""
    return [
        Tool(
            name="get_transaction",
            description="Get detailed information about a Bitcoin transaction by its txid. Returns inputs, outputs, fees, and confirmation status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "The transaction ID (64 character hex string)"
                    },
                    "resolve_inputs": {
                        "type": "boolean",
                        "description": "Whether to fetch input values from previous transactions",
                        "default": False
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="trace_utxo_forward",
            description="Trace a UTXO forward through the blockchain to find where the funds went. Shows all subsequent transactions until reaching unspent outputs or max depth.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Starting transaction ID"
                    },
                    "vout": {
                        "type": "integer",
                        "description": "Output index to trace (default: 0)",
                        "default": 0
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to trace (default: 10, max: 50)",
                        "default": 10
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="trace_utxo_backward",
            description="Trace a transaction's inputs backward to find the origin of funds. Continues until reaching coinbase (mining) transactions or max depth.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Transaction ID to trace backward from"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to trace (default: 10, max: 50)",
                        "default": 10
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="detect_coinjoin",
            description="Analyze a transaction for CoinJoin characteristics. Detects Whirlpool, Wasabi, JoinMarket, and other mixing patterns with confidence scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Transaction ID to analyze"
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="get_coinjoin_history",
            description="Check if any transaction in a UTXO's history involved CoinJoin mixing. Useful for understanding the privacy history of funds.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Transaction ID to check history for"
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["forward", "backward", "both"],
                        "description": "Direction to trace",
                        "default": "backward"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to trace",
                        "default": 10
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="calculate_privacy_score",
            description="Calculate a privacy score (0-100) for a UTXO based on its history, CoinJoin usage, age, and other factors. Includes recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Transaction ID"
                    },
                    "vout": {
                        "type": "integer",
                        "description": "Output index",
                        "default": 0
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="validate_address",
            description="Validate a Bitcoin address and identify its type (P2PKH, P2SH, P2WPKH, P2WSH, P2TR). Shows if it's a valid mainnet or testnet address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Bitcoin address to validate"
                    }
                },
                "required": ["address"]
            }
        ),
        Tool(
            name="get_timeline",
            description="Generate a visual ASCII timeline showing the flow of funds through transactions. Shows dates, amounts, CoinJoin events, and transaction types.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Starting transaction ID"
                    },
                    "vout": {
                        "type": "integer",
                        "description": "Output index (for forward trace)",
                        "default": 0
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["forward", "backward"],
                        "description": "Direction to trace",
                        "default": "forward"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth",
                        "default": 10
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="check_utxo_status",
            description="Check if a specific UTXO (txid:vout) is spent or unspent. Shows current value if unspent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Transaction ID"
                    },
                    "vout": {
                        "type": "integer",
                        "description": "Output index"
                    }
                },
                "required": ["txid", "vout"]
            }
        ),
        Tool(
            name="start_deep_analysis",
            description="Start a background analysis job for complex traces that may take a long time. Returns a job ID to check progress.",
            inputSchema={
                "type": "object",
                "properties": {
                    "txid": {
                        "type": "string",
                        "description": "Transaction ID to analyze"
                    },
                    "job_type": {
                        "type": "string",
                        "enum": ["trace_forward", "trace_backward", "full_analysis"],
                        "description": "Type of analysis",
                        "default": "full_analysis"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth for traces",
                        "default": 20
                    }
                },
                "required": ["txid"]
            }
        ),
        Tool(
            name="get_job_status",
            description="Check the status of a background analysis job. Shows progress and results when complete.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job ID returned from start_deep_analysis"
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="label_address",
            description="Add a label to an address for future reference. Categories: exchange, personal, merchant, mixer, other.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Bitcoin address"
                    },
                    "label": {
                        "type": "string",
                        "description": "Label for the address"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["exchange", "personal", "merchant", "mixer", "other"],
                        "description": "Address category",
                        "default": "other"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes"
                    }
                },
                "required": ["address", "label"]
            }
        ),
        Tool(
            name="health_check",
            description="Check if ChainForensics and Bitcoin Core are connected and working properly.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "get_transaction":
            txid = arguments.get("txid")
            resolve = arguments.get("resolve_inputs", False)
            result = await api_call(f"/transactions/{txid}", {"resolve_inputs": resolve})
            
        elif name == "trace_utxo_forward":
            txid = arguments.get("txid")
            vout = arguments.get("vout", 0)
            depth = arguments.get("max_depth", 10)
            result = await api_call("/analysis/trace/forward", {
                "txid": txid,
                "vout": vout,
                "max_depth": depth
            })
            
        elif name == "trace_utxo_backward":
            txid = arguments.get("txid")
            depth = arguments.get("max_depth", 10)
            result = await api_call("/analysis/trace/backward", {
                "txid": txid,
                "max_depth": depth
            })
            
        elif name == "detect_coinjoin":
            txid = arguments.get("txid")
            result = await api_call(f"/analysis/coinjoin/{txid}")
            
        elif name == "get_coinjoin_history":
            txid = arguments.get("txid")
            direction = arguments.get("direction", "backward")
            depth = arguments.get("max_depth", 10)
            result = await api_call(f"/analysis/coinjoin/history/{txid}", {
                "direction": direction,
                "max_depth": depth
            })
            
        elif name == "calculate_privacy_score":
            txid = arguments.get("txid")
            vout = arguments.get("vout", 0)
            result = await api_call("/analysis/privacy-score", {
                "txid": txid,
                "vout": vout
            })
            
        elif name == "validate_address":
            address = arguments.get("address")
            result = await api_call(f"/addresses/{address}/validate")
            
        elif name == "get_timeline":
            txid = arguments.get("txid")
            vout = arguments.get("vout", 0)
            direction = arguments.get("direction", "forward")
            depth = arguments.get("max_depth", 10)
            
            # Get trace data
            if direction == "forward":
                trace_result = await api_call("/analysis/trace/forward", {
                    "txid": txid,
                    "vout": vout,
                    "max_depth": depth
                })
            else:
                trace_result = await api_call("/analysis/trace/backward", {
                    "txid": txid,
                    "max_depth": depth
                })
            
            if "error" in trace_result:
                result = trace_result
            else:
                # Format as ASCII timeline
                timeline = format_timeline_ascii(trace_result)
                result = {"timeline": timeline, "raw_data": trace_result}
            
        elif name == "check_utxo_status":
            txid = arguments.get("txid")
            vout = arguments.get("vout")
            result = await api_call(f"/transactions/{txid}/utxo/{vout}")
            
        elif name == "start_deep_analysis":
            txid = arguments.get("txid")
            job_type = arguments.get("job_type", "full_analysis")
            depth = arguments.get("max_depth", 20)
            result = await api_post("/jobs/", {
                "job_type": job_type,
                "target_txid": txid,
                "parameters": {
                    "forward_depth": depth,
                    "backward_depth": depth
                }
            })
            
        elif name == "get_job_status":
            job_id = arguments.get("job_id")
            result = await api_call(f"/jobs/{job_id}")
            
        elif name == "label_address":
            result = await api_post("/addresses/labels", {
                "address": arguments.get("address"),
                "label": arguments.get("label"),
                "category": arguments.get("category", "other"),
                "notes": arguments.get("notes")
            })
            
        elif name == "health_check":
            result = await api_call("/health")
            
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        # Format output
        if "timeline" in result:
            output = result["timeline"]
        else:
            output = json.dumps(result, indent=2, default=str)
        
        return [TextContent(type="text", text=output)]
        
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ============== Resources ==============

@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri=AnyUrl("chainforensics://health"),
            name="System Health",
            description="Current system health and connection status",
            mimeType="application/json"
        ),
        Resource(
            uri=AnyUrl("chainforensics://jobs"),
            name="Active Jobs",
            description="List of active analysis jobs",
            mimeType="application/json"
        )
    ]


@server.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Read a resource."""
    uri_str = str(uri)
    
    if uri_str == "chainforensics://health":
        result = await api_call("/health")
        return json.dumps(result, indent=2)
    
    elif uri_str == "chainforensics://jobs":
        result = await api_call("/jobs/")
        return json.dumps(result, indent=2)
    
    return json.dumps({"error": "Unknown resource"})


async def main():
    """Main entry point."""
    logger.info("Starting ChainForensics MCP Server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
