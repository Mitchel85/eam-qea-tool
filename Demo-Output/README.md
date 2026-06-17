# Demo Output

Live-Demonstrationen des QEA-Analyzers am MASC-Architekturmodell (Multipurpose Armed Spacecraft).

## Dateien

| Datei | Beschreibung |
|---|---|
| `AAroN_Proof_MASC.pdf` | Nachweis aller 15 AAroN-proprietären QEA-Strukturen via QEAAnalyzer |
| `MASC_Operateur_Analyse.pdf` | Operateur-Perspektive: 28 Fähigkeiten + Einsatzbefehl-Prozesskette |
| `Musterarchitektur_MASC.qea` | Sparx EA Architekturmodell (1.652 Elemente, 1.746 Beziehungen) |

## Analyse-Methodik

Beide PDFs wurden mit dem QEAAnalyzer-Tool erstellt — direkte Funktionsaufrufe auf die QEA-Datenbank. Keine manuellen SQL-Hacks. Keine externen API-Calls. Read-Only, On-Premise.

## Enthaltene Analysen

- **AAroN Proof:** INSTANCE_OF (PDATA1), REUSAGE (PDATA3), HAS_PORT/PART/EMBEDS (ParentID), Conveyed Items (t_xref), InformationFlows (2-stage), Capability Hierarchy
- **Operateur:** Fähigkeitsbaum, Einsatzbefehl-Eingang → 6 Kernmaßnahmen → Zielbekämpfung, Constraints (2h-Bereitschaft, Bevollmächtigten-Freigabe)
