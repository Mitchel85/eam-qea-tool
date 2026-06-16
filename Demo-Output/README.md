# Demo-Output

Live-Demonstration des QEA-Analyzers am MASC-Architekturmodell.

## Inhalt

| Datei | Beschreibung |
|-------|-------------|
| `AAroN_ADMBw_MASC_Analyse.pdf` | Vollständige 18-Dimensionen-Tiefenanalyse mit ADMBw-Validierung |
| `Musterarchitektur_MASC.qea` | Das analysierte Sparx-EA-Modell (1.652 Elemente, 1.746 Beziehungen) |

## Analyse-Methodik

Alle 18 Dimensionen wurden mittels direkter SQL-Abfragen auf die QEA-Datenbank ausgeführt — basierend auf AAroN-Domänenwissen (ObjectProcessor, ConnectorProcessor, XRefProcessor, InformationFlowProcessor). Keine Ergebnisse wurden geschätzt oder von externen Diensten bezogen.

## ADMBw-Validierung

1.413 Connectors wurden gegen die 117 Topologieregeln des ADMBw-NAFv4-Metamodells (ADMBw-Knowledge-Topology.md) abgeglichen.
