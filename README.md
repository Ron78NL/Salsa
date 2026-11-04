# 💃 Latin Agenda

Overzicht van **Latin concerten, festivals en salsa/bachata-avonden**, met alle afstanden gerekend vanaf **Brugge**.

| Soort | Waar |
|---|---|
| 🎤 Concerten | heel België en Nederland |
| 🎪 Festivals | België, Nederland en Noord-Frankrijk (tot 160 km) |
| 💃 Dansavonden (salsa, bachata, kizomba) | België, binnen 50 km |

Deze regels pas je aan in `config.yaml`.

## Snel starten (op je eigen pc)

```bash
pip install -r requirements.txt
python ophalen.py --offline   # alleen de startdata uit data/handmatig.yaml
streamlit run app.py
```

Met internetbronnen erbij:

```bash
copy .env.voorbeeld .env      # (Mac/Linux: cp) en vul je sleutels in
python ophalen.py
```

## Bronnen

| Bron | Wat | Nodig |
|---|---|---|
| **Ticketmaster Discovery API** | grote en middelgrote concerten (genre "Latin") in BE, NL en rond Lille | gratis sleutel: maak een account op developer.ticketmaster.com → *My Apps* → *Consumer Key* |
| **Salsa Vida** | dansavonden en dansfestivals (BE, NL, Hauts-de-France) via hun gratis publieke MCP-dienst | niets |
| **Bandsintown** | tourdata van de artiesten in `data/artiesten.txt` | optioneel: app_id via Bandsintown (partnership-aanvraag) |
| **Webpagina's met eventdata (JSON-LD)** | Songkick Latin-pagina's, en elke zaalagenda die je toevoegt in `config.yaml` | niets |
| **data/handmatig.yaml** | je eigen events en terugkerende avonden | niets |

Zonder sleutels werkt de app ook: dan krijg je Salsa Vida, de webpagina's en je eigen lijst.

Events die geen Latin zijn (bijvoorbeeld van een zaalagenda) worden eruit gefilterd op basis van de woorden in `config.yaml` en de artiestenlijst. Wat eruit gefilterd werd, staat met reden in `data/afgewezen.json`.

## Elke dag automatisch bijwerken (GitHub + Streamlit Cloud)

1. Maak een nieuwe repo, bijvoorbeeld `Ron78NL/latin-agenda`, en zet deze map erin.
2. In de repo: **Settings → Secrets and variables → Actions → New repository secret**
   - `TICKETMASTER_KEY` (en eventueel `BANDSINTOWN_APP_ID`)
3. **Actions → Events ophalen → Run workflow** om het meteen een keer te draaien. Daarna gaat het elke ochtend vanzelf.
4. Op share.streamlit.io: **New app** → kies de repo → `app.py`.

De workflow zet de nieuwe `data/events.json` in de repo, en Streamlit Cloud laat die automatisch zien.

## Zelf events toevoegen

Open `data/handmatig.yaml`:

```yaml
events:
  - titel: Grupo Niche
    soort: concert
    start: 2027-05-14T20:00
    zaal: De Roma
    stad: Antwerpen
    land: BE
    url: https://...

terugkerend:
  - titel: Salsa-avond in café X
    herhaling: {type: maandelijks, week: 1, dag: vr}   # of {type: wekelijks, dag: wo}
    tijd: "21:00"
    stad: Oostende
    land: BE
```

## Een zaalagenda toevoegen

Voeg de URL toe onder `jsonld_paginas` in `config.yaml`. Dit werkt voor sites die schema.org-eventdata in hun pagina hebben, wat bij de meeste ticket- en zaalsites het geval is. Alleen de Latin-events blijven over.

## Tests

```bash
python -m pytest -q
```
