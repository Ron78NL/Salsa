"""Salsa Vida via hun publieke MCP-dienst (gratis, alleen-lezen).

Bron: https://www.salsavida.com/developers/mcp/ — vermeld Salsa Vida als bron en link
naar het event. De exacte invoervelden van de tools haalt dit script zelf op
(tools/list), zodat kleine wijzigingen aan hun kant niets breken.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import requests

from ..geo import landcode
from ..model import Event

log = logging.getLogger(__name__)


class McpClient:
    def __init__(self, endpoint: str, sessie: requests.Session | None = None):
        self.endpoint = endpoint
        self.s = sessie or requests.Session()
        self.sessie_id = None
        self._id = 0
        self.tools: dict[str, dict] = {}

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False):
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.sessie_id:
            headers["Mcp-Session-Id"] = self.sessie_id
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            self._id += 1
            body["id"] = self._id
        r = self.s.post(self.endpoint, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        self.sessie_id = r.headers.get("Mcp-Session-Id", self.sessie_id)
        if notify or not r.content:
            return None
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            antwoord = None
            for regel in r.text.splitlines():
                if regel.startswith("data:"):
                    try:
                        msg = json.loads(regel[5:].strip())
                    except ValueError:
                        continue
                    if msg.get("id") == body.get("id"):
                        antwoord = msg
            msg = antwoord or {}
        else:
            msg = r.json()
        if "error" in msg:
            raise RuntimeError(f"MCP-fout bij {method}: {msg['error']}")
        return msg.get("result")

    def start(self):
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "latin-agenda", "version": "1.0"}})
        self._rpc("notifications/initialized", notify=True)
        res = self._rpc("tools/list", {}) or {}
        self.tools = {t["name"]: t for t in res.get("tools", [])}
        return self

    def velden(self, tool: str) -> set[str]:
        return set(((self.tools.get(tool) or {}).get("inputSchema") or {}).get("properties", {}))

    def call(self, tool: str, args: dict):
        res = self._rpc("tools/call", {"name": tool, "arguments": args}) or {}
        if res.get("structuredContent"):
            return res["structuredContent"]
        for c in res.get("content", []):
            if c.get("type") == "text":
                try:
                    return json.loads(c["text"])
                except ValueError:
                    return {"text": c["text"]}
        return {}


def _kies(velden: set[str], *kandidaten: str) -> str | None:
    for k in kandidaten:
        if k in velden:
            return k
    return None


def _lijst(data, *sleutels):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in sleutels:
            if isinstance(data.get(k), list):
                return data[k]
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


def _get(d: dict, *paden, default=None):
    for pad in paden:
        cur = d
        for deel in pad.split("."):
            cur = cur.get(deel) if isinstance(cur, dict) else None
            if cur is None:
                break
        if cur not in (None, "", []):
            return cur
    return default


def parse_item(it: dict) -> Event | None:
    titel = _get(it, "title", "name", "event.title")
    start = _get(it, "start_date", "startDate", "date", "occurrence.start_date", "start", "starts_at",
                 "dates.start")
    if not titel or not start:
        return None
    tijd = _get(it, "start_time", "startTime", "time", "occurrence.start_time")
    start = str(start)[:10] + (f"T{str(tijd)[:5]}" if tijd and "T" not in str(start) else str(start)[10:16])
    soort_tekst = " ".join(str(x) for x in (_get(it, "event_type", "type", "types", "classifications",
                                                  default="") or "",)).lower()
    soort = "festival" if ("festival" in soort_tekst or "congress" in soort_tekst) else "dansavond"
    dansen = _get(it, "dances", "dance", "styles", default=[]) or []
    if isinstance(dansen, str):
        dansen = [dansen]
    genres = [str(d).lower() for d in dansen] or ["salsa"]
    lat = _get(it, "venue.lat", "venue.latitude", "lat", "latitude", "location.lat", "geo.latitude")
    lon = _get(it, "venue.lng", "venue.lon", "venue.longitude", "lng", "lon", "longitude",
               "location.lng", "location.lon", "geo.longitude")
    try:
        lat, lon = (float(lat), float(lon)) if lat is not None and lon is not None else (None, None)
    except (TypeError, ValueError):
        lat = lon = None
    prijs = _get(it, "price", "prices", "price_text", default="")
    if isinstance(prijs, list):
        prijs = ", ".join(map(str, prijs))
    return Event(
        titel=str(titel).strip(), start=start,
        eind=str(_get(it, "end_date", "endDate", "occurrence.end_date", default="") or "")[:10] or None,
        soort=soort, zaal=str(_get(it, "venue.name", "venue_name", "location.name", default="")),
        stad=str(_get(it, "venue.city", "city", "location.city", "address.city", default="")),
        land=landcode(str(_get(it, "venue.country", "country", "venue.country_code", "country_code",
                               "address.country", default=""))),
        adres=str(_get(it, "venue.address", "address.street", "address", default="")
                  if not isinstance(_get(it, "address"), dict) else _get(it, "address.street", default="")),
        lat=lat, lon=lon, genres=genres, prijs=str(prijs or ""),
        url=str(_get(it, "canonical_url", "url", "link", "visit_url", default="")),
        bron="Salsa Vida",
        opmerking="Terugkerend event: check bij de organisator" if _get(it, "recurring", "is_recurring")
        else "",
    )


def haal_op(cfg: dict, sessie: requests.Session | None = None) -> list[Event]:
    sv = cfg.get("salsavida") or {}
    if not sv.get("endpoint"):
        return []
    try:
        mcp = McpClient(sv["endpoint"], sessie).start()
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        log.warning("Salsa Vida niet bereikbaar: %s", exc)
        return []
    ev_velden = mcp.velden("search_events")
    loc_velden = mcp.velden("search_locations")
    log.info("Salsa Vida tools: %s | search_events-velden: %s", sorted(mcp.tools), sorted(ev_velden))

    vandaag = date.today()
    eind = vandaag + timedelta(days=min(cfg.get("periode_dagen", 365), 364))
    events: list[Event] = []
    for gebied in sv.get("gebieden", []):
        q_veld = _kies(loc_velden, "query", "q", "name", "text", "location")
        try:
            locs = _lijst(mcp.call("search_locations", {q_veld or "query": gebied["zoek"]}),
                          "locations", "results", "items")
        except (requests.RequestException, RuntimeError) as exc:
            log.warning("Salsa Vida locatie %s mislukt: %s", gebied["zoek"], exc)
            continue
        if not locs:
            log.warning("Salsa Vida: locatie %s niet gevonden", gebied["zoek"])
            continue
        loc_id = _get(locs[0], "id", "location_id", "locationId")
        for soort in gebied.get("soorten", []):
            # Dansavonden per maand ophalen (veel resultaten), festivals in één keer.
            stappen = 12 if soort == "dansavond" else 1
            dagen = (eind - vandaag).days // stappen + 1
            for i in range(stappen):
                van = vandaag + timedelta(days=i * dagen)
                tot = min(eind, van + timedelta(days=dagen - 1))
                args = {}
                args[_kies(ev_velden, "location_id", "locationId", "location") or "location_id"] = loc_id
                args[_kies(ev_velden, "start_date", "date_from", "from", "startDate") or "start_date"] = van.isoformat()
                args[_kies(ev_velden, "end_date", "date_to", "to", "endDate") or "end_date"] = tot.isoformat()
                type_veld = _kies(ev_velden, "event_type", "event_types", "type", "types")
                if type_veld:
                    waarde = "festival" if soort == "festival" else "social"
                    args[type_veld] = [waarde] if type_veld.endswith("s") else waarde
                limit_veld = _kies(ev_velden, "limit", "page_size", "per_page")
                if limit_veld:
                    args[limit_veld] = 50
                page_veld = _kies(ev_velden, "page", "cursor")
                for pagina in range(1, 11):
                    if page_veld == "page":
                        args["page"] = pagina
                    try:
                        data = mcp.call("search_events", args)
                    except (requests.RequestException, RuntimeError) as exc:
                        log.warning("Salsa Vida zoeken mislukt: %s", exc)
                        break
                    items = _lijst(data, "events", "results", "items", "occurrences")
                    for it in items:
                        ev = parse_item(it)
                        if ev:
                            if soort == "festival":
                                ev.soort = "festival"
                            events.append(ev)
                    volgende = _get(data, "next_cursor", "nextCursor", "pagination.next_cursor") \
                        if isinstance(data, dict) else None
                    if page_veld == "cursor" and volgende:
                        args["cursor"] = volgende
                        continue
                    heeft_meer = _get(data, "has_more", "pagination.has_more", "truncated") \
                        if isinstance(data, dict) else False
                    if page_veld != "page" or not heeft_meer or len(items) == 0:
                        break
    log.info("Salsa Vida: %d events", len(events))
    return events
