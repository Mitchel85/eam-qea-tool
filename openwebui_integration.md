# EAM QEA Analyzer — Open WebUI Integration Guide

> **Basierend auf AAroN** (github.com/schmitze87/AAroN) — Apache 2.0  
> AAroN ist ein Neo4j-Plugin für Sparx EA Architekturen, entwickelt für NAF-Modelle.

---

## Übersicht

Dieses Paket macht deinen Open WebUI EAM Analysten **zielgenau** — statt SQLite-Statements zu brute-forcen, nutzt es das tiefe Wissen von AAroN über die proprietäre QEA-Tabellenstruktur von Sparx Enterprise Architect.

### Warum ist das besser als euer aktueller Ansatz?

| Aktueller Ansatz | AAroN-informierter Ansatz |
|------------------|---------------------------|
| SQLite-Queries per Trial & Error | Gezielte Queries via dokumentierte Spalten |
| Kennt nur offensichtliche Tabellen | Kennt ALLE 15+ Core-Tabellen + ihre Beziehungen |
| Versteht implizite Beziehungen nicht | Erkennt 9 implizite Beziehungstypen |
| PDATA-Felder sind "Magic Numbers" | PDATA-Felder kontextabhängig interpretiert |
| Keine NAF-Struktur-Erkennung | NAF-Views & Stereotypen automatisch erkannt |
| Findet Tagged Values nur zufällig | Tagged Values als First-Class-Citizen |

### Was AAroN uns gelehrt hat (Lessons Learned)

1. **PDATA-Spalten sind der Schlüssel:** AAroNs ObjectProcessor zeigt, dass PDATA1-PDATA5 kontextabhängige GUID-Verweise enthalten — das ist das Geheimnis für INSTANCE_OF, BEHAVIOUR und REUSAGE Beziehungen
2. **Implizite Beziehungen existieren außerhalb von t_connector:** EMBEDS, HAS_PORT, HAS_PART werden aus ParentID + Object_Type abgeleitet
3. **t_xref enthält versteckte Metadaten:** Stereotype-FQN, Conveyed Items für Informationsflüsse
4. **Verarbeitungsreihenfolge ist kritisch:** Packages → Diagrams → Objects → Properties → Connectors → DiagramObjects
5. **ea_guid ist der universelle Join-Schlüssel** — nicht Object_ID allein

---

## Installation

### 1. Tool in Open WebUI einbinden

**Option A: Als Python-Tool (empfohlen für Open WebUI ≥ 0.3)**

Kopiere `eam_qea_tool.py` in das Open WebUI Tools-Verzeichnis:

```bash
# Pfad je nach Open WebUI Installation
cp eam_qea_tool.py /pfad/zu/open-webui/data/tools/
# oder bei Docker:
docker cp eam_qea_tool.py open-webui:/app/backend/data/tools/
```

Dann in Open WebUI:
1. **Admin Panel → Tools** öffnen
2. Tool `eam_qea_tool` sollte automatisch erscheinen
3. **Aktivieren** und dem EAM Analyst Model zuweisen

**Option B: Direktintegration (falls kein Tool-Support)**

Alternativ kann das Skript als Modul importiert werden:

```python
import sys
sys.path.insert(0, '/pfad/zu/eam-qea-tool')
from eam_qea_tool import QEAAnalyzer

analyzer = QEAAnalyzer('/pfad/zum/modell.qea')
stats = analyzer.get_model_statistics()
```

### 2. System Prompt konfigurieren

1. In Open WebUI: **Workspace → Models → EAM Analyst → Edit**
2. Den Inhalt von `system_prompt.md` in das System-Feld einfügen
3. **Optional:** Den bestehenden Prompt des EAM Analysten mit diesem Prompt **verschmelzen** (unten anfügen)

### 3. QEA-Datei-Zugriff sicherstellen

Das Tool braucht Lese-Zugriff auf die QEA-Dateien:

```bash
# Wenn QEA-Dateien auf einem Netzlaufwerk liegen:
# In Open WebUI docker-compose.yml das Volume mounten:
volumes:
  - /pfad/zu/qea-modellen:/data/qea-models:ro
```

Dann sind die Dateien unter `/data/qea-models/mein_modell.qea` erreichbar.

---

## Nutzung

### Grundlegende Abfragen

```
"Analysiere die Modellstatistik von /data/qea-models/mein_modell.qea"
→ Ruft analyze_qea_statistics auf

"Zeige mir alle Capabilities im Modell"
→ Ruft find_elements_in_qea(stereotype='Capability') auf

"Suche nach Elementen mit 'Einsatz' im Namen"
→ Ruft search_qea_elements(query='Einsatz') auf

"Zeige die Paketstruktur"
→ Ruft get_package_tree_from_qea auf
```

### NAF-Analysen

```
"Welche NAF-3 Capabilities gibt es?"
→ Ruft get_naf_view_elements_from_qea(view_type='NAF-3') auf

"Finde alle Elemente mit Tagged Value 'SecurityClassification' = 'VS-NfD'"
→ Ruft find_elements_by_tagged_value(tag_name='SecurityClassification', tag_value='VS-NfD') auf

"Welche Tagged Values gibt es im Modell überhaupt?"
→ execute_qea_sql zu t_objectproperties GROUP BY Property
```

### Detaileinsichten

```
"Detailanalyse für Element mit ID 12345"
→ Ruft get_element_detail_from_qea(element_id=12345) auf
→ Liefert: Attribute, Operationen, eingehende/ausgehende Beziehungen,
           implizite Beziehungen, Tagged Values, Diagramme, Cross-Referenzen

"Welche Beziehungen hat das Element 'Einsatzsystem XY'?"
→ Ruft export_qea_element_report(element_name='Einsatzsystem XY') auf
```

### Fortgeschrittene SQL-Analysen

```
"Zeige mir alle Elemente mit ihren impliziten INSTANCE_OF-Beziehungen"
→ execute_qea_sql mit AAroN-informiertem JOIN

"Finde alle Informationsflüsse mit ihren conveyed items"
→ execute_qea_sql mit t_connector JOIN t_xref
```

---

## Deployment in Bw-Umgebung

### Sicherheitshinweise für dienstliche Nutzung

1. **QEA-Dateien enthalten VS-relevante Architekturdaten!**  
   → QEA-Dateien NUR auf dem dienstlichen Server halten, NICHT in Cloud-Umgebungen hochladen
   → Open WebUI läuft on-premise — korrekt so

2. **SQL ist read-only:** Das Tool erlaubt NUR SELECT-Queries via `execute_qea_sql`
   → Keine Schreibzugriffe auf die QEA-Datei möglich

3. **Keine Datenexfiltration:** Das Tool sendet keine Daten nach extern
   → Alle Analysen laufen lokal im Open WebUI Python-Prozess

### Performance-Tipps

- **Große Modelle (>50 MB QEA):** `get_element_detail` kann bei vielen Beziehungen langsam sein — im Zweifel gezielt nach Namen filtern statt alle Elemente zu scannen
- **SQLite-Caching:** Das Tool cached nichts zwischen Aufrufen — jeder Aufruf öffnet eine frische Connection
- **LIMIT immer setzen:** Bei `execute_qea_sql` wird automatisch LIMIT 200 angehängt wenn nicht vorhanden

---

## Erweiterung / Customizing

### Neue NAF-View-Typen hinzufügen

In `eam_qea_tool.py` die `NAF_VIEW_STEREOTYPES` Map erweitern:

```python
NAF_VIEW_STEREOTYPES = {
    "NAF-8": ["Sv-8", "CapabilityConfiguration", "EvolutionTimeline"],
    # ... eigene Views
}
```

### Eigene High-Level-Funktionen

Neue Methoden in der `Tools`-Klasse anlegen:

```python
async def meine_spezialanalyse(self, qea_path: str, parameter: str) -> str:
    analyzer = QEAAnalyzer(qea_path)
    # ... eigene Analyse-Logik mit analyzer._query()
    result = analyzer._query("SELECT ...")
    analyzer.close()
    return json.dumps(result, indent=2, ensure_ascii=False)
```

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| "QEA file not found" | Absoluten Pfad verwenden, Volume-Mount prüfen |
| Tool erscheint nicht in Open WebUI | Tool-Datei im richtigen Verzeichnis? Open WebUI neustarten |
| SQL-Fehler bei execute_qea_sql | Nur SELECT erlaubt; Tabellennamen prüfen |
| Keine Tagged Values gefunden | Manche Modelle nutzen t_objectproperties nicht — prüfe mit `list_all_tag_names()` via SQL |
| Langsame Antworten bei großen Modellen | LIMIT reduzieren, gezielter filtern |

---

## Technische Referenz: AAroN Processor → QEA Tabellen

| AAroN Processor | QEA Tabelle | Open WebUI Funktion |
|-----------------|-------------|---------------------|
| PackageProcessor | t_package | get_package_tree_from_qea |
| ObjectProcessor | t_object | find_elements_in_qea, get_element_detail_from_qea |
| ConnectorProcessor | t_connector | get_relationships_from_qea |
| TaggedValueHelper | t_objectproperties, t_connectortag, t_attributetag | find_elements_by_tagged_value |
| DiagramProcessor | t_diagram, t_diagramobjects, t_diagramlinks | get_qea_diagrams |
| AttributeProcessor | t_attribute | get_element_detail_from_qea (attributes) |
| OperationProcessor | t_operation | get_element_detail_from_qea (operations) |
| XRefProcessor | t_xref | get_element_detail_from_qea (cross_references) |

---

*Erstellt: 06.06.2026 | Clawdia 🦞 | Basierend auf AAroN v2026.01.4*
