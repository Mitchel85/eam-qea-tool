#!/usr/bin/env python3
"""
MCP-Server for EAM QEA Analyzer.
Exposes all eam_qea_tool.Tools as standard MCP tools via FastMCP.

Usage:
    python mcp_server.py                    # stdio mode (Claude Desktop, etc.)
    python mcp_server.py --sse              # SSE mode (http://localhost:8000/sse)
    python mcp_server.py --sse --port 8765  # SSE on custom port
    python mcp_server.py --http             # Streamable HTTP (http://localhost:8000/mcp)

Clients:
    Open-WebUI (Admin → MCP Servers → http://localhost:8000/sse)
    Claude Desktop (claude_desktop_config.json → stdio)
    VS Code Continue (.continue/config.json → sse or stdio)
"""

import argparse
import sys

from mcp.server.fastmcp import FastMCP

from eam_qea_tool import Tools

# ── Init ────────────────────────────────────────
mcp = FastMCP(
    name="EAM QEA Analyzer",
    instructions=(
        "You are an Enterprise Architecture assistant with access to Sparx EA .qea "
        "model files. Use the provided tools to query the model. The qea_path "
        "parameter is always OPTIONAL — when omitted, the tool auto-discovers "
        "the most recently uploaded .qea file.\n\n"
        "Workflow:\n"
        "1. Call analyze_qea_statistics() first for an overview.\n"
        "2. Use find_elements_in_qea() with stereotypes to find specific elements.\n"
        "3. Use get_element_detail_from_qea() for full relationships/properties.\n"
        "4. For processes: list_process_packages_and_activities() → "
        "get_activity_diagram_process_graph()"
    ),
)

tools = Tools()

# ── File Discovery ──────────────────────────────

@mcp.tool()
async def list_available_qea_files() -> str:
    """List all available QEA files found in upload directories."""
    return await tools.list_available_qea_files()


@mcp.tool()
async def analyze_qea_statistics(qea_path: str = "") -> str:
    """Get comprehensive model statistics: element types, stereotypes, counts."""
    return await tools.analyze_qea_statistics(qea_path=qea_path or None)


# ── Element Search & Detail ─────────────────────

@mcp.tool()
async def find_elements_in_qea(
    qea_path: str = "",
    name: str = "",
    object_type: str = "",
    stereotype: str = "",
    package_id: int = 0,
    limit: int = 50,
) -> str:
    """Find elements by name, type, stereotype, or package. All filters optional."""
    return await tools.find_elements_in_qea(
        qea_path=qea_path or None,
        name=name or None,
        object_type=object_type or None,
        stereotype=stereotype or None,
        package_id=package_id or None,
        limit=limit,
    )


@mcp.tool()
async def get_element_detail_from_qea(
    qea_path: str = "",
    element_id: int = 0,
) -> str:
    """Get full detail for one element: properties, relationships, tagged values, diagrams."""
    return await tools.get_element_detail_from_qea(
        qea_path=qea_path or None,
        element_id=element_id or None,
    )


@mcp.tool()
async def get_relationships_from_qea(
    qea_path: str = "",
    element_id: int = 0,
    connector_type: str = "",
    stereotype: str = "",
    limit: int = 100,
) -> str:
    """Get relationships/connectors, optionally filtered by element, type, or stereotype."""
    return await tools.get_relationships_from_qea(
        qea_path=qea_path or None,
        element_id=element_id or None,
        connector_type=connector_type or None,
        stereotype=stereotype or None,
        limit=limit,
    )


@mcp.tool()
async def search_qea_elements(
    qea_path: str = "",
    query: str = "",
    limit: int = 50,
) -> str:
    """Full-text search across element names and notes."""
    return await tools.search_qea_elements(
        qea_path=qea_path or None,
        query=query,
        limit=limit,
    )


@mcp.tool()
async def get_package_tree_from_qea(qea_path: str = "") -> str:
    """Get the complete package/folder hierarchy tree."""
    return await tools.get_package_tree_from_qea(qea_path=qea_path or None)


# ── Tagged Values, Diagrams, NAF ────────────────

@mcp.tool()
async def find_elements_by_tagged_value(
    qea_path: str = "",
    tag_name: str = "",
    tag_value: str = "",
    limit: int = 100,
) -> str:
    """Find elements by tagged value name and/or value. Essential for NAF metadata."""
    return await tools.find_elements_by_tagged_value(
        qea_path=qea_path or None,
        tag_name=tag_name,
        tag_value=tag_value or None,
        limit=limit,
    )


@mcp.tool()
async def get_qea_diagrams(qea_path: str = "") -> str:
    """List all diagrams with their element counts."""
    return await tools.get_qea_diagrams(qea_path=qea_path or None)


@mcp.tool()
async def get_naf_view_elements_from_qea(
    qea_path: str = "",
    view_type: str = "NAF-3",
) -> str:
    """Get elements belonging to a NAF view (NAF-2 through NAF-7)."""
    return await tools.get_naf_view_elements_from_qea(
        qea_path=qea_path or None,
        view_type=view_type,
    )


# ── Process Extraction ──────────────────────────

@mcp.tool()
async def list_process_packages_and_activities(
    qea_path: str = "",
    package_path: str = "",
    include_subpackages: bool = True,
    include_empty_packages: bool = True,
) -> str:
    """Discover packages and Activity elements for process extraction. Call before extracting."""
    return await tools.list_process_packages_and_activities(
        qea_path=qea_path or None,
        package_path=package_path,
        include_subpackages=include_subpackages,
        include_empty_packages=include_empty_packages,
    )


@mcp.tool()
async def list_extracted_activity_graphs(
    qea_path: str = "",
    package_path: str = "",
    include_subpackages: bool = True,
    max_items: int = 200,
) -> str:
    """Get compact summaries of all extractable process graphs from Activity diagrams."""
    return await tools.list_extracted_activity_graphs(
        qea_path=qea_path or None,
        package_path=package_path,
        include_subpackages=include_subpackages,
        max_items=max_items,
    )


@mcp.tool()
async def get_activity_diagram_process_graph(
    activity_id: int = 0,
    qea_path: str = "",
    package_path: str = "",
    include_subpackages: bool = True,
    max_nodes: int = 500,
    max_edges: int = 1000,
) -> str:
    """Extract a detailed BPMN-like process graph for one Activity diagram. Requires activity_id."""
    return await tools.get_activity_diagram_process_graph(
        qea_path=qea_path or None,
        activity_id=activity_id if activity_id else None,
        package_path=package_path,
        include_subpackages=include_subpackages,
        max_nodes=max_nodes,
        max_edges=max_edges,
    )


# ── SQL & Schema ────────────────────────────────

@mcp.tool()
async def execute_qea_sql(
    qea_path: str = "",
    sql: str = "",
    limit: int = 100,
) -> str:
    """Execute a read-only SQL query against the QEA database. Only SELECT allowed."""
    return await tools.execute_qea_sql(
        qea_path=qea_path or None,
        sql=sql,
        limit=limit,
    )


@mcp.tool()
async def get_qea_table_schema(
    qea_path: str = "",
    table_name: str = "",
) -> str:
    """Inspect database schema: list all tables, or get columns for a specific table."""
    return await tools.get_qea_table_schema(
        qea_path=qea_path or None,
        table_name=table_name or None,
    )


@mcp.tool()
async def export_qea_element_report(
    qea_path: str = "",
    element_name: str = "",
) -> str:
    """Generate a comprehensive report for a named element."""
    return await tools.export_qea_element_report(
        qea_path=qea_path or None,
        element_name=element_name,
    )


# ── Health ──────────────────────────────────────

@mcp.tool()
async def ping() -> str:
    """Health check — returns 'pong' to confirm the server is alive."""
    return "pong"


# ── Main ────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="EAM QEA Analyzer — MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python mcp_server.py                     # stdio (Claude Desktop)\n"
            "  python mcp_server.py --sse               # SSE on :8000\n"
            "  python mcp_server.py --sse --port 8765   # SSE on :8765\n"
            "  python mcp_server.py --http              # Streamable HTTP on :8000"
        ),
    )
    parser.add_argument(
        "--sse", action="store_true",
        help="Run as SSE server (for Open-WebUI, remote clients)",
    )
    parser.add_argument(
        "--http", action="store_true",
        help="Run as Streamable HTTP server",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for SSE/HTTP mode (default: 8000)",
    )
    args = parser.parse_args()

    if args.http:
        print(f"Starting MCP server (Streamable HTTP) on http://localhost:{args.port}/mcp")
        mcp.run(transport="streamable-http", host="127.0.0.1", port=args.port)
    elif args.sse:
        print(f"Starting MCP server (SSE) on http://localhost:{args.port}/sse")
        mcp.run(transport="sse", host="127.0.0.1", port=args.port)
    else:
        mcp.run(transport="stdio")
