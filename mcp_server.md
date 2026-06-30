# MCP-Server — Einrichtungsanleitung

> **Standard-Protokoll, ein Server, alle Clients.**
>
> Der MCP-Server macht den EAM QEA Analyzer für JEDES MCP-fähige LLM verfügbar —
> Open-WebUI, Claude Desktop, VS Code Continue und mehr.

---

## 🎯 Architektur

```
┌──────────────┐     MCP-Protokoll      ┌─────────────────┐
│  MCP-Client  │ ←────────────────────→ │  mcp_server.py   │
│  (OWUI,      │   JSON-RPC 2.0         │  (LOKAL)         │
│   Claude…)   │   stdio / SSE / HTTP   │                 │
└──────────────┘                        └────────┬────────┘
                                                  │
                                         ┌────────┴────────┐
                                         │  eam_qea_tool   │
                                         │  16 QEA-Tools    │
                                         └─────────────────┘
```

Der MCP-Server läuft als Hintergrundprozess. Er **meldet** seine 16 Tools beim Client an.
Das LLM entdeckt sie automatisch — kein manuelles Tool-Registrieren, kein Copy-Paste.

---

## Schnellstart

```bash
# 1. Abhängigkeiten installieren
pip install -r requirements-mcp.txt

# 2. MCP-Server starten
python mcp_server.py --sse --port 8765
# → Starting MCP server (SSE) on http://localhost:8765/sse

# 3. Client verbinden (siehe unten)
```

---

## Client-Konfiguration

### Open-WebUI

1. **Admin Panel → MCP Servers** öffnen
2. Auf **+ Add Server**
3. URL eintragen: `http://localhost:8765/sse`
4. Speichern — das LLM sieht die Tools sofort

> **Tipp:** Wenn Open-WebUI auf dem gleichen Rechner läuft, reicht `localhost`.
> Bei entferntem OWUI: Cloudflare Tunnel oder Tailscale nutzen.

### Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "eam-qea-analyzer": {
      "command": "python3",
      "args": ["/pfad/zu/eam-qea-tool/mcp_server.py"]
    }
  }
}
```

Claude Desktop startet den Server automatisch per stdio. Kein Port nötig.

### VS Code / Continue

In `.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "sse",
          "url": "http://localhost:8765/sse"
        }
      }
    ]
  }
}
```

---

## Transport-Modi

| Modus | Befehl | Wann? |
|-------|--------|-------|
| **stdio** | `python mcp_server.py` | Claude Desktop, lokale CLI-Clients |
| **SSE** | `python mcp_server.py --sse` | Open-WebUI, VS Code, Remote-Clients |
| **HTTP** | `python mcp_server.py --http` | Streamable HTTP (neuer Standard) |

```bash
# SSE mit eigenem Port
python mcp_server.py --sse --port 8765

# HTTP mit eigenem Port
python mcp_server.py --http --port 9000
```

---

## Verfügbare Tools (16 + Health)

| Kategorie | Tools |
|-----------|-------|
| **Discovery** | `list_available_qea_files`, `analyze_qea_statistics`, `get_qea_table_schema` |
| **Suche** | `find_elements_in_qea`, `search_qea_elements`, `find_elements_by_tagged_value` |
| **Detail** | `get_element_detail_from_qea`, `export_qea_element_report` |
| **Beziehungen** | `get_relationships_from_qea`, `get_package_tree_from_qea` |
| **Diagramme** | `get_qea_diagrams`, `get_naf_view_elements_from_qea` |
| **Prozesse** | `list_process_packages_and_activities`, `list_extracted_activity_graphs`, `get_activity_diagram_process_graph` |
| **Advanced** | `execute_qea_sql` |
| **Health** | `ping` |

> **Alle Tools:** Der Parameter `qea_path` ist immer OPTIONAL. Weglassen → Auto-Discovery der neuesten QEA-Datei.

---

## Erste Schritte nach Verbindung

```
Du: Welche Modelle sind verfügbar?
LLM: [ruft list_available_qea_files()] → 3 QEA-Dateien gefunden.

Du: Analysiere NAF_Architektur.qea
LLM: [ruft analyze_qea_statistics()] → 247 Elemente, 12 Capabilities, ...

Du: Zeig mir den Prozess aus Activity "Einsatzplanung"
LLM: [ruft get_activity_diagram_process_graph(activity_id=281)]
     → Prozessgraph mit 23 Knoten, 18 Kanten
```

---

## Vergleich mit anderen Modi

| | MCP-Server | Open-WebUI nativ | webui_api.py |
|---|---|---|---|
| **Clients** | Open-WebUI, Claude, VS Code… | Nur Open-WebUI | Nur Open-WebUI |
| **Protokoll** | Standard (MCP) | Proprietär (OWUI) | REST (OWUI-API) |
| **RAG / Knowledge Base** | ❌ | ✅ | ✅ |
| **Auto-Discovery** | ✅ (LLM sieht Tools automatisch) | ✅ | ❌ (manuell) |
| **Lokal testbar** | ✅ | ❌ (OWUI nötig) | ✅ |

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| `Connection refused` | Läuft der Server? `python mcp_server.py --sse` |
| `ModuleNotFoundError: networkx` | `pip install -r requirements-mcp.txt` |
| Tools erscheinen nicht | Client neustarten; Server log prüfen |
| `qea_path`-Fehler | QEA-Datei in `/app/backend/data/uploads` ablegen, oder expliziten Pfad angeben |

---

*Zurück zur [README](README.md) | Alternativ: [Open-WebUI native Integration](openwebui_integration.md) | [Lokaler Wrapper](local_wrapper.md)*
