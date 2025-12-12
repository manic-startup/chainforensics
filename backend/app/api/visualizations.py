"""
ChainForensics - Visualizations API
Endpoints for generating visual representations of blockchain data.
"""
import logging
from typing import Optional
import json

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import HTMLResponse

from app.core.tracer import get_tracer
from app.core.timeline import get_timeline_generator
from app.core.bitcoin_rpc import get_rpc, BitcoinRPCError

logger = logging.getLogger("chainforensics.api.visualizations")

router = APIRouter()


@router.get("/timeline/ascii")
async def get_ascii_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30),
    width: int = Query(100, ge=60, le=200)
):
    """
    Generate ASCII timeline visualization.
    
    Returns a text-based timeline showing UTXO flow with:
    - Date markers
    - Value bars
    - CoinJoin indicators
    - Flow connections
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        ascii_timeline = timeline_gen.generate_ascii_timeline(trace.to_dict(), width)
        
        return Response(
            content=ascii_timeline,
            media_type="text/plain; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"Error generating ASCII timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/html")
async def get_html_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30)
):
    """
    Generate interactive HTML timeline with D3.js.
    
    Returns a standalone HTML page with:
    - Visual timeline bars
    - Hover details
    - CoinJoin highlighting
    - Responsive design
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        html = timeline_gen.generate_html_timeline(trace.to_dict())
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        logger.error(f"Error generating HTML timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/mermaid")
async def get_mermaid_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30)
):
    """
    Generate Mermaid.js timeline diagram.
    
    Returns Mermaid markdown that can be rendered by compatible tools.
    Claude can render these diagrams directly.
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        mermaid = timeline_gen.generate_mermaid_timeline(trace.to_dict())
        
        return {
            "txid": txid,
            "direction": direction,
            "format": "mermaid",
            "diagram": mermaid
        }
        
    except Exception as e:
        logger.error(f"Error generating Mermaid timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/json")
async def get_json_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30)
):
    """
    Generate timeline data as JSON.
    
    Returns structured data for custom visualization.
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        timeline = timeline_gen.generate_timeline(trace.to_dict())
        
        return timeline.to_dict()
        
    except Exception as e:
        logger.error(f"Error generating JSON timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flow-diagram/mermaid")
async def get_mermaid_flow_diagram(
    txid: str,
    depth: int = Query(3, ge=1, le=10),
    direction: str = Query("both", regex="^(forward|backward|both)$")
):
    """
    Generate Mermaid flow diagram showing UTXO connections.
    
    Creates a graph visualization with:
    - Transaction nodes
    - UTXO edges with values
    - CoinJoin highlighting
    """
    try:
        rpc = get_rpc()
        tracer = get_tracer()
        
        lines = ["```mermaid", "graph LR"]
        
        tx = await rpc.get_raw_transaction(txid, True)
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction not found: {txid}")
        
        # Style definitions
        lines.append("    classDef coinjoin fill:#f85149,stroke:#da3633")
        lines.append("    classDef unspent fill:#238636,stroke:#2ea043")
        lines.append("    classDef coinbase fill:#a371f7,stroke:#8957e5")
        
        visited_txids = set()
        
        async def add_transaction_to_graph(tx_data: dict, current_depth: int, direction_flag: str):
            if current_depth > depth:
                return
            
            current_txid = tx_data.get("txid", "")
            if current_txid in visited_txids:
                return
            visited_txids.add(current_txid)
            
            short_txid = current_txid[:8]
            
            # Check CoinJoin
            from app.core.coinjoin import get_detector
            detector = get_detector()
            cj_result = detector.analyze_transaction(tx_data)
            is_coinjoin = cj_result.score > 0.5
            
            # Node styling
            node_class = ""
            if is_coinjoin:
                node_class = ":::coinjoin"
            
            # Add node
            node_label = f"{short_txid}"
            if is_coinjoin:
                node_label = f"🔀 {short_txid}"
            
            lines.append(f'    TX_{short_txid}["{node_label}"]{node_class}')
            
            # Process based on direction
            if direction_flag in ["backward", "both"]:
                # Add inputs
                for vin in tx_data.get("vin", [])[:5]:
                    if "coinbase" in vin:
                        cb_id = f"CB_{current_txid[:6]}"
                        lines.append(f'    {cb_id}["⛏️ Coinbase"]:::coinbase --> TX_{short_txid}')
                    elif "txid" in vin:
                        prev_txid = vin["txid"]
                        prev_short = prev_txid[:8]
                        lines.append(f'    TX_{prev_short} --> TX_{short_txid}')
            
            if direction_flag in ["forward", "both"]:
                # Add outputs
                for vout_data in tx_data.get("vout", [])[:5]:
                    value = vout_data.get("value", 0)
                    vout_idx = vout_data.get("n", 0)
                    
                    # Check if spent
                    utxo_status = await rpc.get_tx_out(current_txid, vout_idx)
                    
                    out_id = f"OUT_{short_txid}_{vout_idx}"
                    if utxo_status:
                        lines.append(f'    TX_{short_txid} --> {out_id}["{value:.4f} BTC"]:::unspent')
                    else:
                        lines.append(f'    TX_{short_txid} --> {out_id}["{value:.4f} BTC"]')
        
        await add_transaction_to_graph(tx, 0, direction)
        
        lines.append("```")
        
        return {
            "txid": txid,
            "depth": depth,
            "direction": direction,
            "format": "mermaid",
            "diagram": "\n".join(lines)
        }
        
    except Exception as e:
        logger.error(f"Error generating flow diagram: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/json")
async def get_graph_json(
    txid: str,
    direction: str = Query("both", regex="^(forward|backward|both)$"),
    max_depth: int = Query(5, ge=1, le=15)
):
    """
    Export UTXO graph as JSON for external visualization tools.
    
    Returns nodes and edges in a format compatible with:
    - D3.js force graphs
    - Gephi (convert to GraphML)
    - NetworkX
    """
    try:
        tracer = get_tracer()
        
        nodes = []
        edges = []
        node_ids = set()
        
        if direction in ["forward", "both"]:
            forward = await tracer.trace_forward(txid, 0, max_depth)
            for node in forward.nodes:
                if node.txid not in node_ids:
                    node_ids.add(node.txid)
                    nodes.append({
                        "id": node.txid,
                        "type": "transaction",
                        "value_btc": node.value_btc,
                        "status": node.status.value,
                        "coinjoin_score": node.coinjoin_score,
                        "block_height": node.block_height
                    })
            
            for edge in forward.edges:
                edges.append({
                    "source": edge.from_txid,
                    "target": edge.to_txid,
                    "value": edge.value_sats,
                    "vout": edge.from_vout,
                    "vin": edge.to_vin
                })
        
        if direction in ["backward", "both"]:
            backward = await tracer.trace_backward(txid, max_depth)
            for node in backward.nodes:
                if node.txid not in node_ids:
                    node_ids.add(node.txid)
                    nodes.append({
                        "id": node.txid,
                        "type": "coinbase" if node.status.value == "coinbase" else "transaction",
                        "value_btc": node.value_btc,
                        "status": node.status.value,
                        "coinjoin_score": node.coinjoin_score,
                        "block_height": node.block_height
                    })
            
            for edge in backward.edges:
                edge_id = f"{edge.from_txid}-{edge.to_txid}"
                if not any(f"{e['source']}-{e['target']}" == edge_id for e in edges):
                    edges.append({
                        "source": edge.from_txid,
                        "target": edge.to_txid,
                        "value": edge.value_sats,
                        "vout": edge.from_vout,
                        "vin": edge.to_vin
                    })
        
        return {
            "txid": txid,
            "direction": direction,
            "max_depth": max_depth,
            "graph": {
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating graph JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/html")
async def get_interactive_graph(
    txid: str,
    direction: str = Query("both", regex="^(forward|backward|both)$"),
    max_depth: int = Query(5, ge=1, le=10)
):
    """
    Generate interactive force-directed graph visualization.
    
    Returns standalone HTML with D3.js force graph.
    """
    try:
        # Get graph data
        graph_data = await get_graph_json(txid, direction, max_depth)
        graph_json = json.dumps(graph_data["graph"])
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChainForensics - UTXO Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        .node {{ cursor: pointer; }}
        .node circle {{ stroke: #fff; stroke-width: 1.5px; }}
        .node.coinjoin circle {{ fill: #f85149; }}
        .node.unspent circle {{ fill: #238636; }}
        .node.coinbase circle {{ fill: #a371f7; }}
        .node.default circle {{ fill: #58a6ff; }}
        .link {{ stroke: #30363d; stroke-opacity: 0.6; }}
        .node text {{
            fill: #c9d1d9;
            font-size: 10px;
            pointer-events: none;
        }}
        .tooltip {{
            position: absolute;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        .info-panel {{
            position: fixed;
            top: 10px;
            left: 10px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px;
            z-index: 100;
        }}
        .info-panel h2 {{ color: #58a6ff; margin-bottom: 10px; }}
        .legend {{ margin-top: 10px; }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="info-panel">
        <h2>🔗 UTXO Graph</h2>
        <p>TX: {txid[:16]}...</p>
        <p>Nodes: {graph_data["graph"]["node_count"]}</p>
        <p>Edges: {graph_data["graph"]["edge_count"]}</p>
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: #f85149;"></div>
                <span>CoinJoin</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #238636;"></div>
                <span>Unspent</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #a371f7;"></div>
                <span>Coinbase</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #58a6ff;"></div>
                <span>Transaction</span>
            </div>
        </div>
    </div>
    
    <div id="graph"></div>
    <div class="tooltip" id="tooltip"></div>
    
    <script>
        const data = {graph_json};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("#graph")
            .append("svg")
            .attr("width", width)
            .attr("height", height);
        
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.edges).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
        
        const link = svg.append("g")
            .selectAll("line")
            .data(data.edges)
            .join("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.max(1, Math.log10(d.value / 100000000) + 2));
        
        const node = svg.append("g")
            .selectAll("g")
            .data(data.nodes)
            .join("g")
            .attr("class", d => {{
                if (d.coinjoin_score > 0.5) return "node coinjoin";
                if (d.status === "unspent") return "node unspent";
                if (d.type === "coinbase") return "node coinbase";
                return "node default";
            }})
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        node.append("circle")
            .attr("r", d => Math.max(8, Math.log10(d.value_btc * 100000000) * 2));
        
        node.append("text")
            .attr("dx", 12)
            .attr("dy", 4)
            .text(d => d.id.substring(0, 8) + "...");
        
        const tooltip = d3.select("#tooltip");
        
        node.on("mouseover", (event, d) => {{
            tooltip.style("opacity", 1)
                .html(`
                    <strong>TXID:</strong> ${{d.id.substring(0, 24)}}...<br>
                    <strong>Value:</strong> ${{d.value_btc.toFixed(8)}} BTC<br>
                    <strong>Status:</strong> ${{d.status}}<br>
                    <strong>CoinJoin:</strong> ${{(d.coinjoin_score * 100).toFixed(0)}}%
                `)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px");
        }})
        .on("mouseout", () => {{
            tooltip.style("opacity", 0);
        }});
        
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});
        
        function dragstarted(event) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }}
        
        function dragged(event) {{
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }}
        
        function dragended(event) {{
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }}
    </script>
</body>
</html>'''
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        logger.error(f"Error generating interactive graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))
