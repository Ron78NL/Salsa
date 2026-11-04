"""Haal alle events op en schrijf data/events.json.

Gebruik:
    python ophalen.py            # alle bronnen (internet nodig)
    python ophalen.py --offline  # alleen data/handmatig.yaml

Sleutels (optioneel) als omgevingsvariabelen of in een .env-bestand:
    TICKETMASTER_KEY=...
    BANDSINTOWN_APP_ID=...
"""
import argparse
import logging
import os
from pathlib import Path

from latin_agenda.pipeline import draai


def lees_env():
    pad = Path(__file__).with_name(".env")
    if pad.exists():
        for regel in pad.read_text(encoding="utf-8").splitlines():
            if "=" in regel and not regel.strip().startswith("#"):
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="geen internetbronnen")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    lees_env()
    res = draai(online=not args.offline)
    print(f"{res['aantal']} events opgeslagen in data/events.json")
    for bron, n in res["opgehaald_per_bron"].items():
        print(f"  {bron}: {n} opgehaald")
