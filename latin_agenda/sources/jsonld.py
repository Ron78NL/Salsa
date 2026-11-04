"""Events uit schema.org JSON-LD op gewone webpagina's (zaalagenda's, Songkick, Eventbrite ...)."""
from __future__ import annotations

import json
import logging
import re

import requests

from ..geo import landcode
from ..model import Event

log = logging.getLogger(__name__)
EVENT_TYPES = ("event", "musicevent", "festival", "danceevent", "socialevent")
SCRIPT_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                       re.S | re.I)


def _types(obj) -> list[str]:
    t = obj.get("@type", [])
    return [x.lower() for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)]


def _walk(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _walk(x)
    elif isinstance(obj, dict):
        if any(t in EVENT_TYPES for t in _types(obj)):
            yield obj
        for k, v in obj.items():
            if k in ("@graph", "itemListElement", "item", "subEvent", "event", "events"):
                yield from _walk(v)


def _tekst(x) -> str:
    if isinstance(x, dict):
        return x.get("name", "") or ""
    return x if isinstance(x, str) else ""


def parse_object(o: dict, bron: str) -> Event | None:
    start = o.get("startDate")
    naam = (o.get("name") or "").strip()
    if not start or not naam:
        return None
    loc = o.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    adres = loc.get("address") or {} if isinstance(loc, dict) else {}
    if isinstance(adres, str):
        adres = {"streetAddress": adres}
    geo = loc.get("geo") or {} if isinstance(loc, dict) else {}
    perf = o.get("performer") or []
    perf = perf if isinstance(perf, list) else [perf]
    artiesten, genres = [], []
    for p in perf:
        if isinstance(p, dict):
            if p.get("name"):
                artiesten.append(p["name"])
            g = p.get("genre") or []
            genres += [x.replace("_", " ").lower() for x in (g if isinstance(g, list) else [g])
                       if isinstance(x, str)]
        elif isinstance(p, str):
            artiesten.append(p)
    prijs = ""
    offers = o.get("offers") or {}
    offers = offers[0] if isinstance(offers, list) and offers else offers
    if isinstance(offers, dict) and offers.get("price") not in (None, "", 0, "0"):
        prijs = f"€{offers['price']}"
    try:
        lat = float(geo["latitude"]) if geo.get("latitude") else None
        lon = float(geo["longitude"]) if geo.get("longitude") else None
    except (TypeError, ValueError):
        lat = lon = None
    soort = "festival" if "festival" in _types(o) else "concert"
    eind = o.get("endDate")
    return Event(
        titel=naam, start=str(start)[:16], eind=str(eind)[:10] if eind else None,
        soort=soort, artiesten=artiesten, zaal=_tekst(loc),
        stad=adres.get("addressLocality", "") if isinstance(adres, dict) else "",
        land=landcode(_tekst(adres.get("addressCountry")) if isinstance(adres, dict) else ""),
        adres=adres.get("streetAddress", "") if isinstance(adres, dict) else "",
        lat=lat, lon=lon, genres=genres, prijs=prijs,
        url=o.get("url") or "", bron=bron,
        opmerking=(o.get("description") or "")[:200],
    )


def parse_html(html: str, bron: str) -> list[Event]:
    events = []
    for blok in SCRIPT_RE.findall(html):
        try:
            data = json.loads(blok.strip())
        except ValueError:
            continue
        for o in _walk(data):
            ev = parse_object(o, bron)
            if ev:
                events.append(ev)
    return events


def haal_op(paginas: list, sessie: requests.Session | None = None) -> list[Event]:
    s = sessie or requests.Session()
    events = []
    for item in paginas:
        url = item["url"] if isinstance(item, dict) else item
        altijd_latin = bool(item.get("latin")) if isinstance(item, dict) else "genre/latin" in url
        bron = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        try:
            r = s.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (latin-agenda)"})
            r.raise_for_status()
        except requests.RequestException as exc:
            log.warning("JSON-LD %s mislukt: %s", url, exc)
            continue
        gevonden = parse_html(r.text, bron)
        if altijd_latin:
            for ev in gevonden:
                if "latin" not in ev.genres:
                    ev.genres.append("latin")
        log.info("JSON-LD %s: %d events", url, len(gevonden))
        events += gevonden
    return events
