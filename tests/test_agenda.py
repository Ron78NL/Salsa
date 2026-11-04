import json
from datetime import date

from latin_agenda.classify import bepaal_soort, herken_genres, past_in_regels, bereken_afstand
from latin_agenda.geo import vul_locatie
from latin_agenda.model import Event
from latin_agenda.pipeline import laad_config, ontdubbel, verrijk
from latin_agenda.sources import bandsintown, handmatig, jsonld, salsavida, ticketmaster

CFG = laad_config()
VANDAAG = date(2026, 11, 4)


def ev(**kw):
    e = Event(**{"titel": "x", "start": "2027-01-10", **kw})
    vul_locatie(e)
    bereken_afstand(e, CFG)
    return e


# ---------- regels ----------
def test_concert_belgie_en_nederland_ok_frankrijk_niet():
    assert past_in_regels(ev(soort="concert", stad="Antwerpen"), CFG, VANDAAG)[0]
    assert past_in_regels(ev(soort="concert", stad="Groningen"), CFG, VANDAAG)[0]
    assert not past_in_regels(ev(soort="concert", stad="Lille"), CFG, VANDAAG)[0]


def test_festival_noord_frankrijk_ok_ver_frankrijk_niet():
    assert past_in_regels(ev(soort="festival", stad="Lille"), CFG, VANDAAG)[0]
    assert past_in_regels(ev(soort="festival", stad="Amsterdam"), CFG, VANDAAG)[0]
    parijs = ev(soort="festival", stad="Parijs", land="FR", lat=48.8566, lon=2.3522)
    bereken_afstand(parijs, CFG)
    assert not past_in_regels(parijs, CFG, VANDAAG)[0]


def test_dansavond_alleen_binnen_50km_in_belgie():
    assert past_in_regels(ev(soort="dansavond", stad="Gent"), CFG, VANDAAG)[0]
    assert past_in_regels(ev(soort="dansavond", stad="Kortrijk"), CFG, VANDAAG)[0]
    assert not past_in_regels(ev(soort="dansavond", stad="Brussel"), CFG, VANDAAG)[0]
    assert not past_in_regels(ev(soort="dansavond", stad="Lille"), CFG, VANDAAG)[0]   # FR, 65 km
    assert not past_in_regels(ev(soort="dansavond", stad="Middelburg"), CFG, VANDAAG)[0]  # NL


def test_voorbij_en_te_ver_vooruit():
    assert not past_in_regels(ev(start="2026-10-01", stad="Gent", soort="concert"), CFG, VANDAAG)[0]
    assert not past_in_regels(ev(start="2028-03-01", stad="Gent", soort="concert"), CFG, VANDAAG)[0]
    # meerdaags festival dat al bezig is, telt nog mee
    assert past_in_regels(ev(start="2026-11-02", eind="2026-11-06", stad="Gent", soort="festival"),
                          CFG, VANDAAG)[0]


# ---------- herkenning ----------
def test_genres():
    w = CFG["latin_woorden"]
    assert herken_genres("Noche de Reggaetón & Bachata", w) == ["reggaeton", "bachata"]
    assert herken_genres("Latin Dreams Festival", w) == ["latin"]
    assert herken_genres("Platina jazz", w) == []


def test_soort():
    assert bepaal_soort(Event(titel="Brussels Salsa Marathon", start="2026-12-04")) == "festival"
    assert bepaal_soort(Event(titel="Rauw Alejandro", start="2027-06-01", artiesten=["Rauw"])) == "concert"


def test_jsonld_ruis_eruit_latin_erin():
    a = Event(titel="Metallica", start="2027-05-01", stad="Antwerpen", bron="example.be")
    b = Event(titel="Noche Latina met DJ Pepe", start="2027-05-02", stad="Antwerpen", bron="example.be")
    c = Event(titel="Tour 2027", artiesten=["Romeo Santos"], start="2027-05-03", stad="Antwerpen",
              bron="example.be")
    goed, _ = verrijk([a, b, c], CFG, ["Romeo Santos"], None, VANDAAG)
    assert [e.titel for e in goed] == ["Noche Latina met DJ Pepe", "Tour 2027"]


# ---------- bronnen ----------
TM = {
    "name": "Rauw Alejandro - Cosa Nuestra Tour", "url": "https://tm.be/x",
    "dates": {"start": {"localDate": "2027-06-27", "localTime": "20:00:00"}},
    "classifications": [{"segment": {"name": "Music"}, "genre": {"name": "Latin"},
                         "subGenre": {"name": "Reggaeton"}}],
    "priceRanges": [{"min": 59.5, "currency": "EUR"}],
    "_embedded": {"venues": [{"name": "Vorst Nationaal", "city": {"name": "Brussel"},
                              "country": {"countryCode": "BE"},
                              "location": {"latitude": "50.81", "longitude": "4.32"}}],
                  "attractions": [{"name": "Rauw Alejandro"}]},
}


def test_ticketmaster_parse():
    e = ticketmaster.parse_event(TM)
    assert e.start == "2027-06-27T20:00" and e.land == "BE" and e.artiesten == ["Rauw Alejandro"]
    assert e.genres == ["latin", "reggaeton"] and e.prijs == "vanaf €60"


def test_bandsintown_parse():
    e = bandsintown.parse_event({"datetime": "2027-03-01T20:00:00", "lineup": ["Juanes"],
                                 "venue": {"name": "Cirque Royal", "city": "Brussels",
                                           "country": "Belgium", "latitude": "50.85",
                                           "longitude": "4.36"},
                                 "offers": [{"type": "Tickets", "url": "https://t"}]}, "Juanes")
    assert e.land == "BE" and e.url == "https://t" and e.start == "2027-03-01T20:00"


HTML = """<html><script type="application/ld+json">[{"@context":"http://schema.org","@type":"MusicEvent",
"name":"Mon Laferte @ Cirque Royal","startDate":"2027-01-18T20:00:00","endDate":"2027-01-18",
"url":"https://www.songkick.com/concerts/1","location":{"@type":"Place","name":"Cirque Royal",
"address":{"addressLocality":"Brussels","addressCountry":"Belgium","streetAddress":"Rue de l'Enseignement 81"},
"geo":{"latitude":50.849,"longitude":4.364}},"performer":[{"name":"Mon Laferte","genre":["indie_alternative","latin"]}]}]
</script><script type="application/ld+json">{"@type":"Organization","name":"x"}</script></html>"""


def test_jsonld_parse():
    [e] = jsonld.parse_html(HTML, "songkick.com")
    assert e.zaal == "Cirque Royal" and e.land == "BE" and "latin" in e.genres
    assert e.artiesten == ["Mon Laferte"] and e.start == "2027-01-18T20:00"


def test_salsavida_item_parse():
    e = salsavida.parse_item({"title": "B-Salsa Monthly Party", "start_date": "2026-11-14",
                              "start_time": "21:00", "event_type": "social",
                              "venue": {"name": "Azúcar Dansateljée", "city": "Brugge",
                                        "country": "Belgium", "lat": 51.2, "lng": 3.22},
                              "dances": ["salsa", "bachata"], "price": "€5",
                              "canonical_url": "https://www.salsavida.com/event/x/"})
    assert e.start == "2026-11-14T21:00" and e.soort == "dansavond" and e.land == "BE"
    assert e.genres == ["salsa", "bachata"] and e.url.endswith("/event/x/")


class NepAntwoord:
    def __init__(self, body, sse=False, sid=None):
        self._body = body
        self.headers = {"Content-Type": "text/event-stream" if sse else "application/json"}
        if sid:
            self.headers["Mcp-Session-Id"] = sid
        self.content = b"x" if body is not None else b""
        self.text = f"event: message\ndata: {json.dumps(body)}\n\n" if sse else json.dumps(body)

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


class NepSessie:
    def __init__(self):
        self.verzoeken = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.verzoeken.append((json, headers))
        m, i = json["method"], json.get("id")
        if m == "initialize":
            return NepAntwoord({"jsonrpc": "2.0", "id": i, "result": {}}, sse=True, sid="abc")
        if m == "notifications/initialized":
            return NepAntwoord(None)
        if m == "tools/list":
            return NepAntwoord({"jsonrpc": "2.0", "id": i, "result": {"tools": [
                {"name": "search_locations", "inputSchema": {"properties": {"query": {}}}},
                {"name": "search_events", "inputSchema": {"properties": {
                    "location_id": {}, "start_date": {}, "end_date": {}, "event_type": {}}}}]}},
                sse=True)
        naam = json["params"]["name"]
        if naam == "search_locations":
            res = {"locations": [{"id": "loc-be", "name": "Belgium"}]}
        else:
            a = json["params"]["arguments"]
            assert a["location_id"] == "loc-be"
            res = {"events": [{"title": f"Fest {a['event_type']}", "start_date": a["start_date"],
                               "venue": {"city": "Gent", "country": "Belgium"}}]} \
                if a["event_type"] == "festival" else {"events": []}
        return NepAntwoord({"jsonrpc": "2.0", "id": i, "result": {
            "content": [{"type": "text", "text": __import__("json").dumps(res)}]}}, sse=True)


def test_salsavida_mcp_flow():
    s = NepSessie()
    cfg = dict(CFG, salsavida={"endpoint": "https://x/mcp",
                               "gebieden": [{"zoek": "Belgium", "soorten": ["festival"]}]})
    events = salsavida.haal_op(cfg, s)
    assert len(events) == 1 and events[0].soort == "festival" and events[0].land == "BE"
    # sessie-ID wordt na initialize meegestuurd
    assert s.verzoeken[-1][1]["Mcp-Session-Id"] == "abc"


# ---------- handmatig + ontdubbelen ----------
def test_herhaling():
    d = handmatig.datums_voor_herhaling({"type": "maandelijks", "week": 2, "dag": "za"},
                                       date(2026, 11, 4), date(2027, 1, 31))
    assert [x.isoformat() for x in d] == ["2026-11-14", "2026-12-12", "2027-01-09"]
    w = handmatig.datums_voor_herhaling({"type": "wekelijks", "dag": "wo", "behalve": ["2026-11-11"]},
                                       date(2026, 11, 4), date(2026, 11, 20))
    assert [x.isoformat() for x in w] == ["2026-11-04", "2026-11-18"]


def test_ontdubbelen_vult_aan():
    a = Event(titel="Rauw Alejandro", artiesten=["Rauw Alejandro"], start="2027-06-27T20:00",
              stad="Brussel", bron="Bandsintown", url="https://bit")
    b = Event(titel="Rauw Alejandro - Cosa Nuestra", artiesten=["Rauw Alejandro"], start="2027-06-27",
              stad="Brussel", bron="Ticketmaster", prijs="vanaf €60", genres=["reggaeton"])
    [e] = ontdubbel([a, b])
    assert e.bron == "Ticketmaster + Bandsintown" and e.prijs == "vanaf €60"
