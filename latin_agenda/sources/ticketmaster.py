"""Ticketmaster Discovery API (gratis sleutel via developer.ticketmaster.com)."""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import requests

from ..model import Event

log = logging.getLogger(__name__)
URL = "https://app.ticketmaster.com/discovery/v2/events.json"


def parse_event(e: dict) -> Event | None:
    dates = e.get("dates", {})
    start = dates.get("start", {})
    dag = start.get("localDate")
    if not dag:
        return None
    if start.get("localTime"):
        dag = f"{dag}T{start['localTime'][:5]}"
    emb = e.get("_embedded", {})
    venue = (emb.get("venues") or [{}])[0]
    loc = venue.get("location") or {}
    klassen = e.get("classifications") or [{}]
    genres = []
    for k in klassen:
        for veld in ("genre", "subGenre"):
            naam = (k.get(veld) or {}).get("name")
            if naam and naam.lower() not in ("undefined", "other") and naam not in genres:
                genres.append(naam)
    soort = "concert"
    for k in klassen:
        typ = " ".join(((k.get(v) or {}).get("name") or "") for v in ("type", "subType")).lower()
        if "festival" in typ:
            soort = "festival"
    prijs = ""
    pr = (e.get("priceRanges") or [{}])[0]
    if pr.get("min"):
        prijs = f"vanaf €{pr['min']:.0f}" if pr.get("currency", "EUR") == "EUR" else f"vanaf {pr['min']:.0f} {pr.get('currency')}"
    eind = (dates.get("end") or {}).get("localDate")
    try:
        lat = float(loc["latitude"]) if loc.get("latitude") else None
        lon = float(loc["longitude"]) if loc.get("longitude") else None
    except (TypeError, ValueError):
        lat = lon = None
    return Event(
        titel=e.get("name", "").strip(),
        start=dag,
        eind=eind,
        soort=soort,
        artiesten=[a.get("name", "") for a in emb.get("attractions", []) if a.get("name")],
        zaal=venue.get("name", ""),
        stad=(venue.get("city") or {}).get("name", ""),
        land=(venue.get("country") or {}).get("countryCode", ""),
        adres=(venue.get("address") or {}).get("line1", ""),
        lat=lat, lon=lon,
        genres=[g.lower() for g in genres],
        prijs=prijs,
        url=e.get("url", ""),
        bron="Ticketmaster",
    )


def haal_op(cfg: dict, api_key: str, sessie: requests.Session | None = None) -> list[Event]:
    if not api_key:
        log.info("Ticketmaster: geen API-sleutel, overgeslagen")
        return []
    s = sessie or requests.Session()
    tm = cfg.get("ticketmaster", {})
    van = date.today()
    tot = van + timedelta(days=cfg.get("periode_dagen", 365))
    basis = {
        "apikey": api_key,
        "classificationName": tm.get("classificatie", "Latin"),
        "startDateTime": f"{van.isoformat()}T00:00:00Z",
        "endDateTime": f"{tot.isoformat()}T23:59:59Z",
        "size": 200,
        "sort": "date,asc",
        "locale": "*",
    }
    zoekopdrachten = []
    for land in tm.get("landen", ["BE", "NL"]):
        p = dict(basis, countryCode=land)
        if land == "FR":
            vp = cfg["vertrekpunt"]
            p.update(latlong=f"{vp['lat']},{vp['lon']}", radius=tm.get("frankrijk_straal_km", 160),
                     unit="km")
        zoekopdrachten.append(p)

    events: list[Event] = []
    for p in zoekopdrachten:
        for pagina in range(5):  # Ticketmaster staat max. 1000 resultaten (5 x 200) toe
            try:
                r = s.get(URL, params=dict(p, page=pagina), timeout=30)
                if r.status_code == 429:
                    time.sleep(2)
                    r = s.get(URL, params=dict(p, page=pagina), timeout=30)
                r.raise_for_status()
                data = r.json()
            except (requests.RequestException, ValueError) as exc:
                log.warning("Ticketmaster %s pagina %s mislukt: %s", p.get("countryCode"), pagina, exc)
                break
            for e in data.get("_embedded", {}).get("events", []):
                ev = parse_event(e)
                if ev:
                    events.append(ev)
            totaal = data.get("page", {}).get("totalPages", 0)
            if pagina + 1 >= totaal:
                break
            time.sleep(0.25)  # max. 5 verzoeken per seconde
    log.info("Ticketmaster: %d events", len(events))
    return events
