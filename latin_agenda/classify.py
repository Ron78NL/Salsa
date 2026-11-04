"""Herkennen van Latin-events, soort bepalen en de regels van config.yaml toepassen."""
from __future__ import annotations

import re
from datetime import date, timedelta

from .geo import afstand_km
from .model import Event, normaliseer

FESTIVAL_WOORDEN = ("festival", "fest ", "fest ", "congress", "congres", "weekender",
                    "marathon", "open air", "festi")
DANS_WOORDEN = ("social", "dansavond", "dance night", "salsa night", "latin night", "fiesta",
                "party", "feest", "soirée", "soiree", "practica", "oefenavond", "bal ")
DANS_GENRES = {"salsa", "bachata", "kizomba", "merengue"}


def _bevat(tekst: str, woord: str) -> bool:
    # Woordgrens, zodat "latin" niet in "platina" matcht.
    return re.search(rf"(?<![a-z]){re.escape(woord)}(?![a-z])", tekst) is not None


def herken_genres(tekst: str, woorden: dict[str, list[str]]) -> list[str]:
    t = (tekst or "").lower()
    gevonden = []
    for genre, lijst in woorden.items():
        if any(_bevat(t, w.lower()) for w in lijst):
            gevonden.append(genre)
    # "latin" is een vangnet; weg als er een specifieker genre is
    if len(gevonden) > 1 and "latin" in gevonden:
        gevonden.remove("latin")
    return gevonden


def is_watchlist_artiest(ev: Event, watchlist: set[str]) -> bool:
    namen = [ev.titel, *ev.artiesten]
    for naam in namen:
        n = normaliseer(naam)
        if n in watchlist:
            return True
        if any(len(w) >= 5 and w in n for w in watchlist):
            return True
    return False


def bepaal_soort(ev: Event) -> str:
    t = f" {ev.titel.lower()} "
    meerdaags = bool(ev.eind and ev.eind[:10] > ev.start[:10])
    if any(w in t for w in FESTIVAL_WOORDEN) or (meerdaags and ev.soort != "concert"):
        return "festival"
    if ev.soort == "dansavond" or (any(w in t for w in DANS_WOORDEN) and
                                   set(ev.genres) & DANS_GENRES and not ev.artiesten):
        return "dansavond"
    return ev.soort or "concert"


def past_in_regels(ev: Event, cfg: dict, vandaag: date | None = None) -> tuple[bool, str]:
    """Geeft (ok, reden) terug."""
    vandaag = vandaag or date.today()
    eind = (ev.eind or ev.start)[:10]
    if eind < vandaag.isoformat():
        return False, "voorbij"
    if ev.start[:10] > (vandaag + timedelta(days=cfg.get("periode_dagen", 365))).isoformat():
        return False, "te ver vooruit"
    regel = cfg["regels"].get(ev.soort)
    if not regel:
        return False, "onbekende soort"
    if ev.land not in regel.get("landen", []):
        return False, f"land {ev.land or '?'} valt buiten de regels"
    grens = regel.get("max_km_per_land", {}).get(ev.land, regel.get("max_km"))
    if grens is not None:
        if ev.afstand_km is None:
            return False, "afstand onbekend"
        if ev.afstand_km > grens:
            return False, f"{ev.afstand_km:.0f} km > {grens} km"
    return True, ""


def bereken_afstand(ev: Event, cfg: dict) -> None:
    if ev.lat is not None and ev.lon is not None:
        vp = cfg["vertrekpunt"]
        ev.afstand_km = round(afstand_km(vp["lat"], vp["lon"], ev.lat, ev.lon), 1)
