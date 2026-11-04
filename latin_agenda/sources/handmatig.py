"""Zelf ingevoerde events en terugkerende dansavonden (data/handmatig.yaml)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from pathlib import Path

import yaml

from ..model import Event

DAGEN = {"ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6}


def datums_voor_herhaling(h: dict, van: date, tot: date) -> list[date]:
    dag = DAGEN[h["dag"]]
    uit = []
    if h["type"] == "wekelijks":
        d = van + timedelta(days=(dag - van.weekday()) % 7)
        while d <= tot:
            uit.append(d)
            d += timedelta(days=7)
    elif h["type"] == "maandelijks":
        week = int(h["week"])  # 1..4, of -1 voor de laatste
        jaar, maand = van.year, van.month
        while date(jaar, maand, 1) <= tot:
            dagen = [date(jaar, maand, n) for n in range(1, calendar.monthrange(jaar, maand)[1] + 1)
                     if date(jaar, maand, n).weekday() == dag]
            d = dagen[week - 1] if week > 0 else dagen[-1]
            if van <= d <= tot:
                uit.append(d)
            maand += 1
            if maand > 12:
                jaar, maand = jaar + 1, 1
    uitgesloten = {str(x) for x in h.get("behalve", [])}
    return [d for d in uit if d.isoformat() not in uitgesloten]


def laad(pad: Path, periode_dagen: int, vandaag: date | None = None) -> list[Event]:
    if not pad.exists():
        return []
    data = yaml.safe_load(pad.read_text(encoding="utf-8")) or {}
    vandaag = vandaag or date.today()
    tot = vandaag + timedelta(days=periode_dagen)
    events = []
    for item in data.get("events", []):
        item = dict(item)
        item.setdefault("bron", "Handmatig")
        item["start"] = str(item["start"])
        if item.get("eind"):
            item["eind"] = str(item["eind"])
        events.append(Event.from_dict(item))
    for item in data.get("terugkerend", []):
        h = item["herhaling"]
        tot_item = min(tot, date.fromisoformat(str(item["tot"]))) if item.get("tot") else tot
        for d in datums_voor_herhaling(h, vandaag, tot_item):
            basis = {k: v for k, v in item.items() if k not in ("herhaling", "tijd", "tot")}
            basis.setdefault("bron", "Handmatig")
            basis.setdefault("soort", "dansavond")
            basis.setdefault("opmerking", "Terugkerend event: check de datum bij de organisator")
            basis["start"] = d.isoformat() + (f"T{item['tijd']}" if item.get("tijd") else "")
            events.append(Event.from_dict(basis))
    return events
