"""Afstanden vanaf het vertrekpunt en opzoeken van coördinaten."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import requests

from .model import normaliseer

# Bekende plaatsen, zodat we niet voor alles een geocoder nodig hebben.
STEDEN = {
    # België
    "brugge": (51.2093, 3.2247, "BE"), "bruges": (51.2093, 3.2247, "BE"),
    "oostende": (51.2154, 2.9286, "BE"), "ostend": (51.2154, 2.9286, "BE"),
    "snaaskerke": (51.1726, 2.9339, "BE"), "gistel": (51.1567, 2.9706, "BE"),
    "ruddervoorde": (51.0960, 3.2070, "BE"), "torhout": (51.0650, 3.1010, "BE"),
    "roeselare": (50.9465, 3.1227, "BE"), "kortrijk": (50.8279, 3.2649, "BE"),
    "gent": (51.0543, 3.7174, "BE"), "ghent": (51.0543, 3.7174, "BE"),
    "aalst": (50.9378, 4.0403, "BE"), "knokke": (51.3500, 3.2870, "BE"),
    "blankenberge": (51.3130, 3.1320, "BE"), "eeklo": (51.1850, 3.5640, "BE"),
    "tielt": (50.9990, 3.3270, "BE"), "ieper": (50.8503, 2.8850, "BE"),
    "antwerpen": (51.2194, 4.4025, "BE"), "antwerp": (51.2194, 4.4025, "BE"),
    "merksem": (51.2453, 4.4450, "BE"), "borgerhout": (51.2120, 4.4400, "BE"),
    "brussel": (50.8503, 4.3517, "BE"), "brussels": (50.8503, 4.3517, "BE"),
    "bruxelles": (50.8503, 4.3517, "BE"), "vorst": (50.8100, 4.3170, "BE"),
    "forest": (50.8100, 4.3170, "BE"), "leuven": (50.8798, 4.7005, "BE"),
    "mechelen": (51.0259, 4.4776, "BE"), "hasselt": (50.9307, 5.3325, "BE"),
    "genk": (50.9650, 5.5000, "BE"), "luik": (50.6326, 5.5797, "BE"),
    "liege": (50.6326, 5.5797, "BE"), "charleroi": (50.4108, 4.4446, "BE"),
    "mons": (50.4542, 3.9567, "BE"), "bergen": (50.4542, 3.9567, "BE"),
    "namur": (50.4674, 4.8720, "BE"), "moeskroen": (50.7440, 3.2140, "BE"),
    "mouscron": (50.7440, 3.2140, "BE"),
    # Nederland
    "amsterdam": (52.3676, 4.9041, "NL"), "rotterdam": (51.9244, 4.4777, "NL"),
    "utrecht": (52.0907, 5.1214, "NL"), "den haag": (52.0705, 4.3007, "NL"),
    "the hague": (52.0705, 4.3007, "NL"), "eindhoven": (51.4416, 5.4697, "NL"),
    "tilburg": (51.5555, 5.0913, "NL"), "breda": (51.5719, 4.7683, "NL"),
    "middelburg": (51.4988, 3.6136, "NL"), "vlissingen": (51.4425, 3.5736, "NL"),
    "nijmegen": (51.8126, 5.8372, "NL"), "arnhem": (51.9851, 5.8987, "NL"),
    "groningen": (53.2194, 6.5665, "NL"), "maastricht": (50.8514, 5.6910, "NL"),
    # Noord-Frankrijk
    "lille": (50.6292, 3.0573, "FR"), "villeneuve-d'ascq": (50.6233, 3.1450, "FR"),
    "villeneuve d'ascq": (50.6233, 3.1450, "FR"), "lesquin": (50.5890, 3.1110, "FR"),
    "roubaix": (50.6942, 3.1746, "FR"), "tourcoing": (50.7239, 3.1612, "FR"),
    "dunkerque": (51.0343, 2.3768, "FR"), "duinkerke": (51.0343, 2.3768, "FR"),
    "calais": (50.9513, 1.8587, "FR"), "arras": (50.2910, 2.7775, "FR"),
    "lens": (50.4320, 2.8330, "FR"), "valenciennes": (50.3570, 3.5230, "FR"),
    "amiens": (49.8941, 2.2958, "FR"), "boulogne-sur-mer": (50.7264, 1.6147, "FR"),
}

LANDNAMEN = {
    "belgium": "BE", "belgie": "BE", "belgique": "BE", "be": "BE",
    "netherlands": "NL", "nederland": "NL", "the netherlands": "NL", "pays-bas": "NL", "nl": "NL",
    "france": "FR", "frankrijk": "FR", "fr": "FR",
}


def landcode(tekst: str | None) -> str:
    if not tekst:
        return ""
    t = tekst.strip().lower()
    t = t.replace("ë", "e")
    return LANDNAMEN.get(t, t.upper() if len(t) == 2 else "")


def afstand_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def stad_opzoeken(stad: str):
    key = (stad or "").strip().lower()
    if key in STEDEN:
        return STEDEN[key]
    n = normaliseer(stad)
    for naam, waarde in STEDEN.items():
        if normaliseer(naam) == n:
            return waarde
    return None


class Geocoder:
    """OpenStreetMap Nominatim met cache (max. 1 verzoek per seconde)."""

    def __init__(self, cache_pad: Path, online: bool = True):
        self.pad = cache_pad
        self.online = online
        self._laatste = 0.0
        try:
            self.cache = json.loads(cache_pad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}

    def zoek(self, tekst: str):
        if not tekst:
            return None
        if tekst in self.cache:
            return self.cache[tekst]
        if not self.online:
            return None
        wacht = 1.1 - (time.time() - self._laatste)
        if wacht > 0:
            time.sleep(wacht)
        self._laatste = time.time()
        try:
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": tekst, "format": "json", "limit": 1, "countrycodes": "be,nl,fr",
                        "addressdetails": 1},
                headers={"User-Agent": "latin-agenda/1.0 (persoonlijk project)"},
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json()
        except (requests.RequestException, ValueError):
            return None
        res = None
        if hits:
            h = hits[0]
            res = [float(h["lat"]), float(h["lon"]),
                   (h.get("address", {}).get("country_code") or "").upper()]
        self.cache[tekst] = res
        return res

    def bewaar(self):
        self.pad.parent.mkdir(parents=True, exist_ok=True)
        self.pad.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")


def vul_locatie(ev, geocoder: Geocoder | None = None) -> None:
    """Zorg dat een event coördinaten en een landcode heeft."""
    if ev.lat is None or ev.lon is None:
        hit = stad_opzoeken(ev.stad)
        if hit:
            ev.lat, ev.lon = hit[0], hit[1]
            ev.land = ev.land or hit[2]
        elif geocoder:
            for q in (", ".join(x for x in (ev.adres, ev.stad) if x),
                      ", ".join(x for x in (ev.zaal, ev.stad) if x), ev.stad):
                res = geocoder.zoek(q) if q else None
                if res:
                    ev.lat, ev.lon = res[0], res[1]
                    ev.land = ev.land or res[2]
                    break
    if not ev.land:
        hit = stad_opzoeken(ev.stad)
        if hit:
            ev.land = hit[2]
