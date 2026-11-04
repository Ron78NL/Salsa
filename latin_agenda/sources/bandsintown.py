"""Bandsintown: tourdata per artiest uit de watchlist (vereist een app_id)."""
from __future__ import annotations

import logging
import time
from urllib.parse import quote

import requests

from ..geo import landcode
from ..model import Event

log = logging.getLogger(__name__)


def parse_event(e: dict, artiest: str) -> Event | None:
    dt = e.get("datetime") or e.get("starts_at")
    if not dt:
        return None
    v = e.get("venue") or {}
    try:
        lat = float(v["latitude"]) if v.get("latitude") else None
        lon = float(v["longitude"]) if v.get("longitude") else None
    except (TypeError, ValueError):
        lat = lon = None
    lineup = e.get("lineup") or [artiest]
    titel = e.get("title") or " + ".join(lineup)
    url = e.get("url", "")
    for o in e.get("offers") or []:
        if o.get("type", "").lower() == "tickets" and o.get("url"):
            url = o["url"]
            break
    return Event(
        titel=titel, start=dt[:16], artiesten=lineup, zaal=v.get("name", ""),
        stad=v.get("city", ""), land=landcode(v.get("country")), lat=lat, lon=lon,
        url=url, bron="Bandsintown", genres=[],
    )


def haal_op(artiesten: list[str], app_id: str, landen: set[str],
            sessie: requests.Session | None = None) -> list[Event]:
    if not app_id:
        log.info("Bandsintown: geen app_id, overgeslagen")
        return []
    s = sessie or requests.Session()
    events = []
    for naam in artiesten:
        try:
            r = s.get(f"https://rest.bandsintown.com/artists/{quote(naam)}/events",
                      params={"app_id": app_id, "date": "upcoming"}, timeout=20)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as exc:
            log.warning("Bandsintown %s mislukt: %s", naam, exc)
            continue
        if not isinstance(data, list):
            continue
        for e in data:
            ev = parse_event(e, naam)
            if ev and ev.land in landen:
                events.append(ev)
        time.sleep(0.3)
    log.info("Bandsintown: %d events in %s", len(events), sorted(landen))
    return events
