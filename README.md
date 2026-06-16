# EAM QEA Analyzer — Open WebUI Tool (Experimental)

> **Stelle natürlichsprachliche Abfragen an ein Sparx-EA-Modell.**
>
> `.qea`-Datei in Open WebUI laden, Frage stellen, strukturierte Antwort erhalten.
> Das Tool übersetzt natürliche Sprache in präzise Datenbankabfragen, löst implizite Beziehungen auf
> und liefert vollständige Ergebnisse — ohne SQL-Kenntnisse oder Handbuch-Studium.

---

## Funktionsübersicht

| Analyseziel | Beispielabfrage |
|---|---|
| Capabilities in NAF-3 anzeigen | *„Zeig mir alle Capabilities"* |
| Element im Detail analysieren | *„Detailanalyse für den OperationalNode 'FüTrp XYZ'"* |
| Beziehungen auswerten | *„Welche Systeme sind mit dem Logistik-Service verbunden?"* |
| Prozesse extrahieren | *„Extrahiere den Prozessgraph aus dem Activity-Diagramm 'Einsatzvorbereitung'"* |
| Metadaten abfragen | *„Finde alle Elemente mit TaggedValue Sicherheitseinstufung=VS-NfD"* |
| Modellstatistik | *„Gib mir eine Statistik über alle Elementtypen im Modell"* |

Der **EAM QEA Analyzer** ist ein KI-gestützter Assistent für Enterprise-Architekten,
der das proprietäre Sparx-QEA-Format über eine natürlichsprachliche Schnittstelle
zugänglich macht. Das zugrundeliegende Tabellenwissen stammt aus **AAroN** —
einem Neo4j-Plugin, das die undokumentierte QEA-Struktur vollständig abbildet.

> **Powered by AAroN (ArAMIS)** — [github.com/schmitze87/AAroN](https://github.com/schmitze87/AAroN) by [@schmitze87](https://github.com/schmitze87) (Markus Schmitz)
>
> Das gesamte Tabellenwissen in diesem Tool stammt aus AAroNs Java-Processors. Ohne AAroN gäbe es dieses Projekt nicht. 🙏


---

## Das Problem

Sparx Enterprise Architect speichert Modelle in proprietären `.qea`-Dateien (SQLite-Datenbanken mit bis zu 100 Tabellen). Die Tabellenstruktur ist komplex, schlecht dokumentiert und enthält:
- **PDATA-Felder**, die je nach `Object_Type` unterschiedliche GUID-Verweise enthalten
- **Implizite Beziehungen**, die NICHT in `t_connector` stehen, sondern aus Spalten wie `ParentID`, `Package_ID` und `PDATA1-3` abgeleitet werden
- **`t_xref`-Einträge**, die Stereotyp-Auflösungen und Conveyed Items enthalten

Ein LLM, das ohne Domänenwissen SQLite-Queries auf die QEA-Datenbank anwendet, findet diese Zusammenhänge nicht.

## Die Lösung

Dieses Tool extrahiert das Wissen aus **AAroN** — einem Neo4j-Plugin, das für NAF-Architekturen entwickelt wurde und die proprietäre QEA-Struktur vollständig versteht. AAroNs 15+ Java-Processors wurden analysiert und in eine Python-Toolbox für Open WebUI übersetzt.

### AAroN: Erkenntnisse zur QEA-Struktur

| Erkenntnis | Auswirkung |
|----------------|------------|
| **PDATA1-5** sind kontextabhängige GUID-Verweise | `INSTANCE_OF`, `BEHAVIOUR`, `REUSAGE` Beziehungen werden erkannt |
| **9 implizite Beziehungstypen** existieren außerhalb von `t_connector` | `CONTAINS`, `EMBEDS`, `HAS_PORT`, `HAS_PART` etc. |
| **`t_xref`** enthält FQ-Stereotypes & Conveyed Items | Informationsflüsse werden vollständig aufgelöst |
| **`ea_guid`** ist der universelle Join-Schlüssel | GUID-basierte Querverweise statt nur ID-basiert |
| **Verarbeitungsreihenfolge** ist kritisch | Packages → Diagrams → Objects → Properties → Connectors |

---

## Features

### High-Level-Analysefunktionen

| Funktion | Beschreibung |
|----------|-------------|
| `analyze_qea_statistics` | Modell-Statistiken (Elementtypen, Stereotypen) |
| `find_elements_in_qea` | Elemente nach Name/Typ/Stereotyp/Paket suchen |
| `get_element_detail_from_qea` | **Komplettanalyse** inkl. impliziter Beziehungen |
| `get_relationships_from_qea` | Beziehungen mit Rollen & Kardinalitäten |
| `search_qea_elements` | Volltextsuche in Namen & Notizen |
| `get_package_tree_from_qea` | Paket-Hierarchie |
| `find_elements_by_tagged_value` | Tagged-Value-Suche (NAF-Metadaten!) |
| `get_qea_diagrams` | Alle Diagramme mit Element-Zählung |
| `get_naf_view_elements_from_qea` | NAF Views |
| `list_process_packages_and_activities` | Pakete & Activities für Prozessanalyse finden |
| `list_extracted_activity_graphs` | Kompakte Prozessgraph-Übersicht (alle Activities) |
| `get_activity_diagram_process_graph` | Detaillierter Prozessgraph einer Activity |
| `list_available_qea_files` | Alle verfügbaren QEA-Dateien auflisten |
| `execute_qea_sql` | Read-only SQL für fortgeschrittene Analysen |
| `get_qea_table_schema` | Tabellenschema-Inspektion |
| `export_qea_element_report` | Komplettbericht für ein Element |

### Prozessanalyse (L4 — Diagramm-basiert)

Neu ab v2.0: Extrahiert BPMN-artige Prozessgraphen direkt aus Activity-Diagrammen.

| Schritt | Funktion |
|---------|----------|
| 1. Discovery | `list_process_packages_and_activities` — findet alle Pakete & Activities |
| 2. Übersicht | `list_extracted_activity_graphs` — kompakte Liste aller Prozessgraphen |
| 3. Detail | `get_activity_diagram_process_graph(activity_id=...)` — voller Graph mit Nodes & Edges |

**Arbeitsweise:** Liest `t_diagram` + `t_diagramobjects` + `t_diagramlinks`, filtert gezielt ControlFlow/StateFlow/Transition-Kanten, erkennt Lanes, löst Gateways auf.

**Abhängigkeiten:** `pandas`, `networkx` (werden beim Laden des Tools in Open WebUI automatisch installiert).

---

## Schnellstart

### 1. Tool in Open WebUI einbinden

```bash
# Tool kopieren
cp eam_qea_tool.py /pfad/zu/open-webui/data/tools/
```

### 2. In Open WebUI aktivieren

1. **Admin Panel → Tools** öffnen
2. `eam_qea_tool` erscheint automatisch
3. **Aktivieren** und dem gewünschten Modell zuweisen

### 3. System Prompt setzen

Den Inhalt von [`system_prompt.md`](system_prompt.md) in das System-Feld des Modells einfügen.

### 4. QEA-Dateien verfügbar machen

```yaml
# In Open WebUI docker-compose.yml:
volumes:
  - /pfad/zu/qea-modellen:/data/qea-models:ro
```

---

## Struktur

```
eam-qea-tool/
├── eam_qea_tool.py          # Das Tool (~95 KB)
├── system_prompt.md          # System Prompt für Open WebUI
├── openwebui_integration.md  # Ausführliche Einrichtungsanleitung
├── requirements.txt          # pandas, networkx
├── LICENSE                   # Apache 2.0
└── README.md                 # Diese Datei
```

---

## Credits

**Dieses Projekt wäre ohne AAroN nicht möglich gewesen.**

| Wer | Was |
|-----|-----|
| [@schmitze87](https://github.com/schmitze87) (Markus Schmitz) | **AAroN** — Die gesamte Wissensbasis. 15+ Java-Processors, die die proprietäre QEA-Tabellenstruktur von Sparx EA dokumentieren. |
|  Michael Estel (mit KI-Agent) | Analyse der AAroN-Processors, Extraktion des Tabellenwissens, Python-Portierung & Open WebUI Integration |

> **Original-Repo:** [github.com/schmitze87/AAroN](https://github.com/schmitze87/AAroN) — ⭐ Empfehlung: gebt Markus einen Star für seine Arbeit an AAroN.

## Lizenz

Apache License 2.0 

---

*Für die ausführliche Einrichtungsanleitung siehe [openwebui_integration.md](openwebui_integration.md)*
