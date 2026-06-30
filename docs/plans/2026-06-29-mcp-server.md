# MCP-Server-Wrapper — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** MCP-Server bauen, der `eam_qea_tool.Tools` als standardisierte MCP-Tools bereitstellt — nutzbar aus Open-WebUI, Claude Desktop, VS Code.

**Architecture:** Ein File `mcp_server.py` wrappt die vorhandene `Tools`-Klasse mit der `FastMCP`-Library. Die `eam_qea_tool.py` bleibt unverändert. Transport: stdio (universell kompatibel), optional SSE für Remote-Zugriff.

**Tech Stack:** Python 3.10+, `mcp>=1.28.0` (FastMCP), `eam_qea_tool` (vorhanden), `pandas`, `networkx`

---

### Task 1: `mcp_server.py` Grundgerüst

**Objective:** Minimaler MCP-Server mit einem Tool, das startet und auf stdio antwortet.

**Files:**
- Create: `mcp_server.py`
- Create: `requirements-mcp.txt`

**Step 1: requirements-mcp.txt schreiben**

```txt
mcp>=1.28.0
pandas>=2.0
networkx>=3.0
```

**Step 2: mcp_server.py — Grundgerüst**

```python
#!/usr/bin/env python3
"""
MCP-Server for EAM QEA Analyzer.
Exposes all eam_qea_tool.Tools as standard MCP tools.

Usage:
    python mcp_server.py                    # stdio mode (Claude Desktop, etc.)
    python mcp_server.py --sse              # SSE mode (http://localhost:8000/sse)
    python mcp_server.py --sse --port 8765  # SSE on custom port
"""

import sys
import argparse
from mcp.server.fastmcp import FastMCP

from eam_qea_tool import Tools

# ── Init ────────────────────────────────────────
mcp = FastMCP(
    name="EAM QEA Analyzer",
    instructions="""
    You are an Enterprise Architecture assistant with access to Sparx EA .qea models.
    Use the provided tools to query the model. The qea_path parameter is OPTIONAL —
    if omitted, the tool auto-discovers the most recently uploaded .qea file.
    """,
)

tools = Tools()

# ── Tools ───────────────────────────────────────
@mcp.tool()
async def ping() -> str:
    """Health check — confirm server is alive."""
    return "pong"


# ── Main ────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EAM QEA MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run as SSE server instead of stdio")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE mode")
    args = parser.parse_args()

    if args.sse:
        print(f"Starting MCP server on http://localhost:{args.port}/sse")
        mcp.run(transport="sse", host="127.0.0.1", port=args.port)
    else:
        mcp.run(transport="stdio")
```

**Step 3: Test: Startet der Server?**

```bash
cd /tmp/eam-qea-tool
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' | timeout 5 python3 mcp_server.py 2>&1 || true
```

Erwartet: JSON-RPC-Response mit `serverInfo` und `name: "EAM QEA Analyzer"`.

**Step 4: Commit**

```bash
git add mcp_server.py requirements-mcp.txt
git commit -m "feat: MCP server skeleton with ping tool"
```

---

### Task 2: Alle 16 Tools als MCP-Tools wrappen

**Objective:** Jede `Tools`-Methode als `@mcp.tool()` registrieren, mit korrekten Type Hints und Descriptions.

**Files:**
- Modify: `mcp_server.py`

**Step 1: QEA-Datei-Discovery**

```python
@mcp.tool()
async def list_available_qea_files() -> str:
    """List all available QEA files in the upload directories."""
    return await tools.list_available_qea_files()


@mcp.tool()
async def analyze_qea_statistics(qea_path: str = None) -> str:
    """Get model statistics from a QEA file: element types, counts, stereotypes."""
    return await tools.analyze_qea_statistics(qea_path=qea_path)
```

**Step 2: Element-Suche & Detailanalyse (5 Tools)**

```python
@mcp.tool()
async def find_elements_in_qea(
    qea_path: str = None,
    name: str = None,
    object_type: str = None,
    stereotype: str = None,
    package_id: int = None,
    limit: int = 50,
) -> str:
    """Find elements in a QEA file by name, type, stereotype, or package."""
    return await tools.find_elements_in_qea(
        qea_path=qea_path, name=name, object_type=object_type,
        stereotype=stereotype, package_id=package_id, limit=limit,
    )


@mcp.tool()
async def get_element_detail_from_qea(
    qea_path: str = None,
    element_id: int = None,
    element_name: str = None,
) -> str:
    """Get full detail for one element: properties, relationships, tagged values."""
    return await tools.get_element_detail_from_qea(
        qea_path=qea_path, element_id=element_id, element_name=element_name,
    )


@mcp.tool()
async def get_relationships_from_qea(
    qea_path: str = None,
    element_id: int = None,
    element_name: str = None,
    direction: str = "both",
) -> str:
    """Get relationships for an element with roles and cardinalities."""
    return await tools.get_relationships_from_qea(
        qea_path=qea_path, element_id=element_id,
        element_name=element_name, direction=direction,
    )


@mcp.tool()
async def search_qea_elements(
    qea_path: str = None, query: str = "", limit: int = 50
) -> str:
    """Full-text search across element names and notes."""
    return await tools.search_qea_elements(
        qea_path=qea_path, query=query, limit=limit,
    )


@mcp.tool()
async def get_package_tree_from_qea(qea_path: str = None) -> str:
    """Get the complete package hierarchy tree."""
    return await tools.get_package_tree_from_qea(qea_path=qea_path)
```

**Step 3: Tagged Values, Diagrams, NAF Views (3 Tools)**

```python
@mcp.tool()
async def find_elements_by_tagged_value(
    qea_path: str = None,
    tag_name: str = None,
    tag_value: str = None,
    limit: int = 50,
) -> str:
    """Find elements by their tagged value name and/or value."""
    return await tools.find_elements_by_tagged_value(
        qea_path=qea_path, tag_name=tag_name, tag_value=tag_value, limit=limit,
    )


@mcp.tool()
async def get_qea_diagrams(qea_path: str = None) -> str:
    """List all diagrams with element counts."""
    return await tools.get_qea_diagrams(qea_path=qea_path)


@mcp.tool()
async def get_naf_view_elements_from_qea(
    qea_path: str = None, naf_view: str = None
) -> str:
    """Get elements belonging to a specific NAF view."""
    return await tools.get_naf_view_elements_from_qea(
        qea_path=qea_path, naf_view=naf_view,
    )
```

**Step 4: Prozessextraktion (3 Tools)**

```python
@mcp.tool()
async def list_process_packages_and_activities(
    qea_path: str = None,
    package_path: str = None,
    include_subpackages: bool = True,
    include_empty_packages: bool = False,
) -> str:
    """Discover packages and activities available for process extraction."""
    return await tools.list_process_packages_and_activities(
        qea_path=qea_path, package_path=package_path,
        include_subpackages=include_subpackages,
        include_empty_packages=include_empty_packages,
    )


@mcp.tool()
async def list_extracted_activity_graphs(
    qea_path: str = None,
    package_path: str = None,
    include_subpackages: bool = True,
    max_nodes: int = 200,
    max_edges: int = 400,
) -> str:
    """Get compact overview of all extractable process graphs."""
    return await tools.list_extracted_activity_graphs(
        qea_path=qea_path, package_path=package_path,
        include_subpackages=include_subpackages,
        max_nodes=max_nodes, max_edges=max_edges,
    )


@mcp.tool()
async def get_activity_diagram_process_graph(
    activity_id: int,
    qea_path: str = None,
    package_path: str = None,
    include_subpackages: bool = True,
    max_nodes: int = 200,
    max_edges: int = 400,
) -> str:
    """Extract a detailed process graph for one activity diagram."""
    return await tools.get_activity_diagram_process_graph(
        qea_path=qea_path, activity_id=activity_id,
        package_path=package_path,
        include_subpackages=include_subpackages,
        max_nodes=max_nodes, max_edges=max_edges,
    )
```

**Step 5: SQL & Schema (3 Tools)**

```python
@mcp.tool()
async def execute_qea_sql(
    qea_path: str = None, sql: str = ""
) -> str:
    """Execute a read-only SQL query against the QEA database. Use for advanced analysis."""
    return await tools.execute_qea_sql(qea_path=qea_path, sql=sql)


@mcp.tool()
async def get_qea_table_schema(
    qea_path: str = None, table_name: str = None
) -> str:
    """Inspect the database schema: list tables or get columns for one table."""
    return await tools.get_qea_table_schema(
        qea_path=qea_path, table_name=table_name,
    )


@mcp.tool()
async def export_qea_element_report(
    qea_path: str = None,
    element_id: int = None,
    element_name: str = None,
) -> str:
    """Generate a comprehensive report for an element."""
    return await tools.export_qea_element_report(
        qea_path=qea_path, element_id=element_id,
        element_name=element_name,
    )
```

**Step 6: Entferne das ping()-Tool aus Task 1** (ersetzt durch echte Tools, aber ping kann bleiben für Healthchecks).

**Step 7: Test: Listet der Server alle Tools?**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' > /tmp/mcp_req.json
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' >> /tmp/mcp_req.json
cat /tmp/mcp_req.json | timeout 5 python3 mcp_server.py 2>&1 | grep -c '"name"' || true
```

Erwartet: `32` (16 Tools × 2 JSON-Einträge pro Tool im Response).

**Step 8: Commit**

```bash
git add mcp_server.py
git commit -m "feat: wrap all 16 Tools methods as MCP tools"
```

---

### Task 3: `mcp_server.md` — Einrichtungsanleitung

**Objective:** Nutzer-Doku für alle 3 Client-Typen.

**Files:**
- Create: `mcp_server.md`

**Step 1: Anleitung schreiben**

Drei Sektionen:
1. **Schnellstart** — `pip install -r requirements-mcp.txt`
2. **Client-Konfiguration:**
   - **Open-WebUI:** Admin → MCP Servers → `http://localhost:8000/sse`
   - **Claude Desktop:** `claude_desktop_config.json` → stdio-Eintrag
   - **VS Code / Continue:** Settings → MCP Server
3. **SSE vs. stdio** — Entscheidungstabelle (wann welcher Transport)

**Step 2: Commit**

```bash
git add mcp_server.md
git commit -m "docs: MCP server setup guide (Open-WebUI, Claude, VS Code)"
```

---

### Task 4: README aktualisieren

**Objective:** MCP-Modus in README aufnehmen.

**Files:**
- Modify: `README.md`

**Step 1: Betriebsmodi-Tabelle erweitern**

```markdown
| **🔌 Open-WebUI Tool** (nativ) | ... |
| **🖥️ Lokaler Wrapper** | ... |
| **🔗 MCP-Server** (neu v0.4) | Standardisiertes Protokoll. Nutzbar aus Open-WebUI, Claude Desktop, VS Code. |
```

**Step 2: Struktur-Sektion aktualisieren**

`mcp_server.py` und `mcp_server.md` hinzufügen.

**Step 3: Changelog ergänzen**

```markdown
| **v0.4** | 30.06.2026 | MCP-Server (`mcp_server.py`) — standardisiertes Tool-Protokoll |
```

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add MCP server to README (v0.4)"
```

---

### Task 5: Abschluss-Test

**Objective:** End-to-End-Test mit echter QEA-Datei über MCP.

**Step 1: Server starten (SSE-Modus)**

```bash
python3 mcp_server.py --sse --port 8765 &
sleep 2
```

**Step 2: Tool-Liste via HTTP prüfen**

```bash
curl -s http://localhost:8765/sse 2>&1 | head -5
```

**Step 3: Server stoppen**

```bash
kill %1
```

**Step 4: Commit + Push**

```bash
git add -A
git commit -m "chore: finalize MCP server integration"
git push origin main
```

---

## Datei-Struktur nach Umsetzung

```
eam-qea-tool/
├── eam_qea_tool.py              # Gemeinsame Codebasis (unverändert)
├── webui_api.py                 # OWUI-Client (fkraemer)
├── mcp_server.py                # NEU: MCP-Server
├── system_prompt.md
├── openwebui_integration.md     # Anleitung OWUI nativ
├── local_wrapper.md             # Anleitung webui_api.py
├── mcp_server.md                # NEU: Anleitung MCP
├── requirements-mcp.txt         # NEU: Dependencies
├── README.md
├── LICENSE
└── Demo-Output/
```

## Zusammenfassung

| # | Task | Dateien |
|---|------|---------|
| 1 | MCP-Grundgerüst | `mcp_server.py` (neu), `requirements-mcp.txt` (neu) |
| 2 | 16 Tools wrappen | `mcp_server.py` (ändern) |
| 3 | Einrichtungsanleitung | `mcp_server.md` (neu) |
| 4 | README-Update | `README.md` (ändern) |
| 5 | Abschluss-Test | — |

**Dauer:** ~30 Minuten. **Keine Änderung an `eam_qea_tool.py`.** Alle bestehenden Modi bleiben unangetastet.
