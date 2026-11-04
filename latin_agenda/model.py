from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Optional

SOORTEN = ("concert", "festival", "dansavond")


@dataclass
class Event:
    titel: str
    start: str                      # ISO-datum of datum+tijd, bv. 2027-01-18 of 2027-01-18T20:00
    soort: str = "concert"          # concert | festival | dansavond
    eind: Optional[str] = None
    artiesten: list[str] = field(default_factory=list)
    zaal: str = ""
    stad: str = ""
    land: str = ""                  # ISO-code: BE, NL, FR
    adres: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    genres: list[str] = field(default_factory=list)
    prijs: str = ""
    url: str = ""
    bron: str = ""
    opmerking: str = ""
    afstand_km: Optional[float] = None

    @property
    def datum(self) -> str:
        return self.start[:10]

    def sleutel(self) -> str:
        """Sleutel om dubbele events uit verschillende bronnen samen te voegen."""
        stad = normaliseer(self.stad)[:12]
        if self.soort == "dansavond" and self.zaal:
            return f"dans|{normaliseer(self.zaal)[:10]}|{self.datum}|{stad}"
        if self.soort == "festival":
            naam = re.sub(r"\d+", "", normaliseer(self.titel))[:12]
            return f"fest|{naam}|{self.datum}"
        wie = self.artiesten[0] if self.artiesten else self.titel
        return f"{normaliseer(wie)[:24]}|{self.datum}|{stad}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        velden = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**velden)


def normaliseer(tekst: str) -> str:
    tekst = unicodedata.normalize("NFKD", tekst or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", tekst.lower())
