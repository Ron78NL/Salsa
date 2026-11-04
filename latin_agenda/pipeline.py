"""Alle bronnen ophalen, opschonen, ontdubbelen en wegschrijven naar data/events.json."""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml

from .classify import (bepaal_soort, bereken_afstand, herken_genres, is_watchlist_artiest,
                       past_in_regels)
from .geo import Geocoder, vul_locatie
from .model import Event, normaliseer
from .sources import bandsintown, handmatig, jsonld, salsavida, ticketmaster

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent

# Bronnen die alleen Latin-events leveren (geen extra genre-check nodig)
LATIN_BRONNEN = {"Ticketmaster", "Bandsintown", "Salsa Vida", "Handmatig"}
# Bij dubbele events: welke bron wint (laagste getal)
VOORRANG = {"Handmatig": 0, "Ticketmaster": 1, "Salsa Vida": 2, "Bandsintown": 3}


def laad_config(pad: Path | None = None) -> dict:
    return yaml.safe_load((pad or ROOT / "config.yaml").read_text(encoding="utf-8"))


def laad_watchlist(cfg: dict) -> list[str]:
    pad = ROOT / cfg.get("watchlist_bestand", "data/artiesten.txt")
    if not pad.exists():
        return []
    return [r.strip() for r in pad.read_text(encoding="utf-8").splitlines()
            if r.strip() and not r.startswith("#")]


def verrijk(events: list[Event], cfg: dict, watchlist: list[str],
            geocoder: Geocoder | None, vandaag: date | None = None):
    wl = {normaliseer(n) for n in watchlist}
    woorden = cfg.get("latin_woorden", {})
    goed, afgewezen = [], []
    for ev in events:
        tekst = " ".join([ev.titel, *ev.artiesten, *ev.genres, ev.opmerking])
        gevonden = herken_genres(tekst, woorden)
        op_watchlist = is_watchlist_artiest(ev, wl)
        if not (gevonden or op_watchlist or ev.bron in LATIN_BRONNEN):
            afgewezen.append((ev, "niet als Latin herkend"))
            continue
        ev.genres = gevonden or ["latin"]
        ev.soort = bepaal_soort(ev)
        vul_locatie(ev, geocoder)
        bereken_afstand(ev, cfg)
        ok, reden = past_in_regels(ev, cfg, vandaag)
        (goed if ok else afgewezen).append(ev if ok else (ev, reden))
    return goed, afgewezen


def ontdubbel(events: list[Event]) -> list[Event]:
    groepen: dict[str, list[Event]] = {}
    for ev in events:
        groepen.setdefault(ev.sleutel(), []).append(ev)
    uit = []
    for groep in groepen.values():
        groep.sort(key=lambda e: VOORRANG.get(e.bron, 5))
        hoofd = groep[0]
        bronnen = []
        for e in groep:
            if e.bron not in bronnen:
                bronnen.append(e.bron)
            for veld in ("url", "prijs", "adres", "zaal", "eind", "lat", "lon", "afstand_km"):
                if not getattr(hoofd, veld) and getattr(e, veld):
                    setattr(hoofd, veld, getattr(e, veld))
            hoofd.genres = list(dict.fromkeys(hoofd.genres + [g for g in e.genres if g != "latin"]))
            if len(hoofd.genres) > 1 and "latin" in hoofd.genres:
                hoofd.genres.remove("latin")
        hoofd.bron = " + ".join(bronnen)
        uit.append(hoofd)
    return sorted(uit, key=lambda e: (e.start, e.titel))


def draai(online: bool = True, vandaag: date | None = None) -> dict:
    cfg = laad_config()
    watchlist = laad_watchlist(cfg)
    sessie = requests.Session()
    ruw: list[Event] = []
    tellers = Counter()

    def voeg_toe(naam, lijst):
        tellers[naam] += len(lijst)
        ruw.extend(lijst)

    voeg_toe("Handmatig", handmatig.laad(ROOT / "data/handmatig.yaml", cfg.get("periode_dagen", 365),
                                         vandaag))
    if online:
        voeg_toe("Ticketmaster", ticketmaster.haal_op(cfg, os.getenv("TICKETMASTER_KEY", ""), sessie))
        landen = set(cfg["regels"]["concert"]["landen"]) | set(cfg["regels"]["festival"]["landen"])
        voeg_toe("Bandsintown", bandsintown.haal_op(watchlist, os.getenv("BANDSINTOWN_APP_ID", ""),
                                                    landen, sessie))
        voeg_toe("Salsa Vida", salsavida.haal_op(cfg, sessie))
        voeg_toe("Webpagina's", jsonld.haal_op(cfg.get("jsonld_paginas", []), sessie))

    geocoder = Geocoder(ROOT / "data/cache/geocode.json", online=online)
    goed, afgewezen = verrijk(ruw, cfg, watchlist, geocoder, vandaag)
    geocoder.bewaar()
    events = ontdubbel(goed)

    resultaat = {
        "bijgewerkt": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "vertrekpunt": cfg["vertrekpunt"]["naam"],
        "opgehaald_per_bron": dict(tellers),
        "aantal": len(events),
        "events": [e.to_dict() for e in events],
    }
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data/events.json").write_text(json.dumps(resultaat, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    (ROOT / "data/afgewezen.json").write_text(json.dumps(
        [{"titel": e.titel, "start": e.start, "stad": e.stad, "land": e.land, "bron": e.bron,
          "reden": r} for e, r in afgewezen if r not in ("voorbij",)],
        ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Klaar: %d events (%d afgewezen)", len(events), len(afgewezen))
    return resultaat
