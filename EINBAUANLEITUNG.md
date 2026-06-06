# EAM QEA Analyzer — Einbauanleitung für Open WebUI (On-Premise)

> **Was es ist:** Ein **Open WebUI Tool** (Python) + **System Prompt** (Textbaustein)  
> **NICHT:** Eine eigene App, kein Docker-Image, kein Plugin  
> **Ergebnis:** Dein bestehendes Open WebUI lernt, QEA-Dateien zielgerichtet zu analysieren

---

## Schritt 1: Tool-Datei besorgen

```bash
# Auf dem Open WebUI Server:
cd /pfad/zu/open-webui/data/tools/
wget https://raw.githubusercontent.com/Mitchel85/eam-qea-tool/main/eam_qea_tool.py
```

**Alternativ (wenn kein Internet):** Die Datei `eam_qea_tool.py` vom GitHub-Release herunterladen und per USB/Netzlaufwerk rüberkopieren.

---

## Schritt 2: Tool aktivieren

1. Open WebUI öffnen → **Admin Panel** (Zahnrad oben rechts)
2. Links auf **Tools** klicken
3. `eam_qea_tool` erscheint in der Liste → **Schalter auf ON**
4. Ggf. dem gewünschten Modell zuweisen (Häkchen setzen)

⚠️ Falls das Tool NICHT erscheint: Open WebUI einmal neustarten (`docker restart open-webui`).

---

## Schritt 3: System Prompt einbauen

1. **Workspace** → **Models** → deinen EAM-Analysten auswählen (oder neuen erstellen)
2. **System Prompt**-Feld öffnen
3. Inhalt von **[system_prompt.md](https://raw.githubusercontent.com/Mitchel85/eam-qea-tool/main/system_prompt.md)** reinkopieren
4. **Speichern**

> Optional: Du kannst den Prompt auch mit deinem bestehenden EAM-Analyst-Prompt kombinieren — einfach untendrunter anfügen.

---

## Schritt 4: QEA-Dateien verfügbar machen

Das Tool braucht einen **Dateipfad**. Drei Wege:

| Weg | Vorgehen | Pfad-Beispiel |
|-----|----------|--------------|
| **A: Volume-Mount** | QEA-Ordner in docker-compose.yml mounten | `/data/models/architektur.qea` |
| **B: Container-Kopie** | `docker cp modell.qea open-webui:/app/backend/data/models/` | `/app/backend/data/models/modell.qea` |
| **C: Netzlaufwerk** | QEA-Ordner per NFS/SMB mounten, dann in Container durchreichen | `/mnt/qea/modell.qea` |

---

## Schritt 5: Testen

In Open WebUI diesen Prompt eingeben:

```
Analysiere /app/backend/data/models/mein_modell.qea
```

Das Modell sollte jetzt das Tool aufrufen (`analyze_qea_statistics`) und eine Übersicht liefern.

Dann weitermachen mit:

```
Welche Capabilities gibt es?
Zeig mir die Paketstruktur.
Finde alle Elemente mit Stereotype "OperationalPerformer".
```

---

## Kurzfassung (für die Wand)

```
1. eam_qea_tool.py → data/tools/
2. Admin → Tools → aktivieren
3. System Prompt aus system_prompt.md → ins Modell kopieren
4. QEA-Datei in Container bringen
5. "Analysiere /pfad/zur/datei.qea" eintippen
```

---

## Was passiert technisch?

```
Nutzer: "Welche Capabilities hat das Modell?"
   ↓
Open WebUI schickt Prompt + System Prompt an LLM
   ↓
LLM (dank System Prompt): "Ah, Capabilities = Stereotype-Filter auf t_object"
   ↓
LLM ruft Tool auf: find_elements_in_qea(stereotype="Capability")
   ↓
Tool öffnet QEA per SQLite, führt AAroN-informierte Query aus
   ↓
Ergebnis (JSON) → LLM formuliert Antwort in natürlicher Sprache
   ↓
Nutzer sieht: "3 Capabilities gefunden: Führungsfähigkeit, ..."
```

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Tool erscheint nicht | `docker restart open-webui`, dann Admin → Tools prüfen |
| "File not found" | Absoluten Pfad prüfen, Container-Neustart? |
| Tool gibt leere Ergebnisse | QEA-Datei ist gültig? SQLite-kompatibel? |
| LLM ruft Tool nicht auf | System Prompt korrekt eingefügt? Modell hat Tool-Zugriff? |
| QEA-Upload wird abgewiesen | `.qea` ist kein erlaubter Upload-Typ → Weg B oder C nutzen |
