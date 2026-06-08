# EAM QEA Analyzer — Open WebUI Tool

> **Powered by AAroN** — [github.com/schmitze87/AAroN](https://github.com/schmitze87/AAroN) by [@schmitze87](https://github.com/schmitze87) (Markus Schmitz)
>
> Das gesamte Tabellenwissen in diesem Tool stammt aus AAroNs Java-Processors. Ohne AAroN gäbe es dieses Projekt nicht. 🙏


---

## Das Problem

Sparx Enterprise Architect speichert Modelle in proprietären `.qea`-Dateien (SQLite-Datenbanken mit bis zu 100 Tabellen). Die Tabellenstruktur ist komplex, schlecht dokumentiert und enthält:
- **PDATA-Felder**, die je nach `Object_Type` unterschiedliche GUID-Verweise enthalten
- **Implizite Beziehungen**, die NICHT in `t_connector` stehen, sondern aus Spalten wie `ParentID`, `Package_ID` und `PDATA1-3` abgeleitet werden
- **`t_xref`-Einträge**, die Stereotyp-Auflösungen und Conveyed Items enthalten

Ein LLM, das einfach SQLite-Queries brute-forced, findet diese Zusammenhänge nicht.

## Die Lösung

Dieses Tool extrahiert das Wissen aus **AAroN** — einem Neo4j-Plugin, das für NAF-Architekturen entwickelt wurde und die proprietäre QEA-Struktur vollständig versteht. AAroNs 15+ Java-Processors wurden analysiert und in eine Python-Toolbox für Open WebUI übersetzt.

### Was AAroN uns gelehrt hat

| Lesson Learned | Auswirkung |
|----------------|------------|
| **PDATA1-5** sind kontextabhängige GUID-Verweise | `INSTANCE_OF`, `BEHAVIOUR`, `REUSAGE` Beziehungen werden erkannt |
| **9 implizite Beziehungstypen** existieren außerhalb von `t_connector` | `CONTAINS`, `EMBEDS`, `HAS_PORT`, `HAS_PART` etc. |
| **`t_xref`** enthält FQ-Stereotypes & Conveyed Items | Informationsflüsse werden vollständig aufgelöst |
| **`ea_guid`** ist der universelle Join-Schlüssel | GUID-basierte Querverweise statt nur ID-basiert |
| **Verarbeitungsreihenfolge** ist kritisch | Packages → Diagrams → Objects → Properties → Connectors |

---

## Features

### 12 High-Level-Analysefunktionen

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
| `execute_qea_sql` | Read-only SQL für fortgeschrittene Analysen |
| `get_qea_table_schema` | Tabellenschema-Inspektion |
| `export_qea_element_report` | Komplettbericht für ein Element |

### NAF-Architektur-Support

- **NAF-2:** Operational Connectivity (OpNode, Needline, InformationExchange)
- **NAF-3:** Capabilities (Capability, CapabilityConfiguration)
- **NAF-4:** Organizational (OrganizationalResource, OrganizationRole)
- **NAF-5:** Functional (Function, Activity, OperationalActivity)
- **NAF-6:** System (SystemResource, ResourceInteraction)
- **NAF-7:** Technical Standards (Protocol, Standard, TechnicalStandard)

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
3. **Aktivieren** und dem EAM Analyst Model zuweisen

### 3. System Prompt setzen

Den Inhalt von [`system_prompt.md`](system_prompt.md) in das System-Feld des EAM Analysten einfügen.

### 4. QEA-Dateien verfügbar machen

```yaml
# In Open WebUI docker-compose.yml:
volumes:
  - /pfad/zu/qea-modellen:/data/qea-models:ro
```

### 5. Loslegen

```
"Analysiere /data/qea-models/mein_modell.qea"
"Zeige alle NAF-3 Capabilities"
"Detailanalyse für Element 12345"
"Finde alle VS-NfD klassifizierten Elemente"
```

---

## Sicherheit (Bw-tauglich)

- **Read-only:** Keine Schreibzugriffe auf QEA-Dateien
- **Lokal:** Alle Analysen laufen im Open WebUI Python-Prozess
- **Keine Exfiltration:** Keine externen API-Calls
- **On-Premise:** Funktioniert vollständig ohne Internetzugang

---

## Struktur

```
eam-qea-tool/
├── eam_qea_tool.py          # Das Tool (52 KB)
├── system_prompt.md          # System Prompt für Open WebUI
├── openwebui_integration.md  # Ausführliche Einrichtungsanleitung
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

> **Original-Repo:** [github.com/schmitze87/AAroN](https://github.com/schmitze87/AAroN) — ⭐ gebt Markus einen Star, er hat's verdient.

## Lizenz

Apache License 2.0 — gleiche Lizenz wie AAroN.

---

*Für die ausführliche Einrichtungsanleitung siehe [openwebui_integration.md](openwebui_integration.md)*
