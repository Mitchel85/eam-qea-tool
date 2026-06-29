# Lokaler Wrapper — Einrichtungsanleitung

> **webui_api.py** lässt dich das eam-qea-tool lokal betreiben und Open-WebUI nur noch als LLM-Dienstleister per API ansprechen.
> Keine Installation in Open-WebUI nötig — du entwickelst und testest direkt in PyCharm oder im Terminal.

---

## 🎯 Architektur

```
┌──────────────────┐       REST API        ┌───────────────────┐
│  webui_api.py    │ ──── Chat-Gespräch ─→ │  Open-WebUI        │
│  (LOKAL)         │ ←─── LLM-Antwort ──── │  (entfernt/Server) │
│                  │                       │                    │
│  importiert      │  Tool-Calls werden    │  Hostet LLMs       │
│  eam_qea_tool.py │  LOKAL ausgeführt!    │  + RAG-Files       │
└──────────────────┘                       └───────────────────┘
```

Du startest `webui_api.py` lokal. Es verbindet sich per API-Token zu deiner Open-WebUI-Instanz, sendet Chat-Anfragen mit Tool-Definitionen, **fängt Tool-Calls ab und führt sie lokal aus** — das LLM merkt keinen Unterschied.

---

## Voraussetzungen

- Python 3.10+
- Open-WebUI-Instanz mit API-Zugang (gleiches Netzwerk oder Cloudflare Tunnel)
- API-Token aus Open-WebUI
- `eam_qea_tool.py` im selben Verzeichnis
- Abhängigkeiten: `pandas`, `networkx`

```bash
pip install pandas networkx requests
```

---

## Einrichtung

### 1. API-Token aus Open-WebUI holen

1. Open-WebUI öffnen → **Account** (Profil-Icon rechts oben)
2. **Settings → Account** → **API Keys**
3. Neuen Key generieren oder vorhandenen kopieren

### 2. Config anpassen

In `webui_api.py` die Config-Variablen oben setzen:

```python
BASE_URL = "http://localhost:3000"         # URL deiner Open-WebUI-Instanz
TOKEN = "sk-..."                           # Dein API-Key
MODEL = "deepseek-r1:latest"               # Modellname (via get_model_list() prüfbar)
QEA_PATH = "/pfad/zum/modell.qea"          # Pfad zur QEA-Datei
SYSTEM_PROMPT = "You can call local QEA tools when needed."
MAX_TOOL_ROUNDS = 8                        # Max. Tool-Calls pro Frage
```

### 3. QEA-Datei bereitstellen

```bash
# Entweder lokal:
QEA_PATH = "/home/user/modelle/NAF_Architektur.qea"

# Oder per Volume-Mount (wenn Open-WebUI die Datei hat):
QEA_PATH = "/data/qea-models/NAF_Architektur.qea"
```

---

## Nutzung

```bash
cd eam-qea-tool/
python webui_api.py
```

Du landest in einem interaktiven Chat:

```
You> Zeig mir alle Capabilities
Tool> analyze_qea_statistics({'qea_path': '/data/modelle/NAF.qea'})
Assistant> Das Modell enthält 47 Capabilities, davon 12 im Viewpoint C3...

You> Extrahiere den Prozess aus Activity "Einsatzplanung"
Tool> get_activity_diagram_process_graph({'activity_id': 281, 'qea_path': '...'})
Assistant> Prozessgraph mit 23 Knoten und 18 Kanten extrahiert...
```

`exit` beendet den Chat.

---

## RAG: Dateien als Kontext mitgeben

Wenn du in Open-WebUI Dateien hochgeladen hast, kann das lokale Skript sie als Kontext nutzen:

```python
RAG_FILES = ["Dienstanweisung_EAM.pdf", "NAFv4_Viewpoints.md"]
FILES_MAX_PAGES = 5  # Wie viele Seiten Dateiliste durchsuchen
```

Das Skript sucht die Dateien per API in Open-WebUI und schickt die File-IDs im Chat-Payload mit.

---

## Vergleich: Lokal vs. Nativ

| Kriterium | Lokaler Wrapper | Open-WebUI (nativ) |
|-----------|----------------|-------------------|
| **Wo läuft das Tool?** | Dein Rechner | Open-WebUI-Server |
| **IDE-Unterstützung** | ✅ PyCharm, Debugger | ❌ Nur Logs |
| **API-Token nötig?** | ✅ Ja | ❌ Nein |
| **LLM-Abhängigkeit** | Beliebiges Open-WebUI-Modell | Vom Workspace-Modell |
| **RAG-Files** | ✅ (via API) | ✅ (nativ) |
| **ADMBw-Knowledge** | ❌ (nur Open-WebUI KB) | ✅ (Knowledge Base) |

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| `Connection refused` | `BASE_URL` prüfen. Läuft Open-WebUI? Port korrekt? |
| `401 Unauthorized` | API-Token prüfen. In Open-WebUI neu generieren. |
| `Model not found` | `MODEL`-Namen mit `get_model_list()` prüfen. |
| Tool-Calls werden ignoriert | System Prompt prüfen. LLM muss wissen, dass es Tools hat. |

---

*Zurück zur [README](README.md) | Alternativ: [Open-WebUI native Integration](openwebui_integration.md)*
