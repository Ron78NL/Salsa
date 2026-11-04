"""Latin Agenda — Streamlit-app.

Start lokaal met:  streamlit run app.py
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "events.json"

DAGEN = ["ma", "di", "wo", "do", "vr", "za", "zo"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"]
VLAG = {"BE": "🇧🇪", "NL": "🇳🇱", "FR": "🇫🇷"}
SOORT_LABEL = {"concert": "🎤 Concert", "festival": "🎪 Festival", "dansavond": "💃 Dansavond"}

st.set_page_config(page_title="Latin Agenda", page_icon="💃", layout="wide")

st.markdown("""
<style>
  .block-container {padding-top: 1.6rem; max-width: 1100px;}
  .maand {margin: 1.6rem 0 .4rem; font-size: 1.15rem; font-weight: 700;
          border-bottom: 2px solid #e4572e; padding-bottom: .2rem; text-transform: capitalize;}
  .kaart {display: flex; gap: 1rem; padding: .7rem .2rem; border-bottom: 1px solid rgba(128,128,128,.2);}
  .datum {min-width: 58px; text-align: center; line-height: 1.1;}
  .datum .d {font-size: 1.6rem; font-weight: 700;}
  .datum .w {font-size: .8rem; opacity: .7; text-transform: uppercase;}
  .titel {font-weight: 650; font-size: 1.05rem;}
  .meta {font-size: .88rem; opacity: .8;}
  .chip {display: inline-block; font-size: .72rem; padding: 1px 8px; margin: 3px 4px 0 0;
         border-radius: 10px; background: rgba(228,87,46,.13); color: #c0421d;}
  .soort-festival .chip.s {background: rgba(46,134,171,.15); color: #1f6f8f;}
  .soort-dansavond .chip.s {background: rgba(122,79,173,.15); color: #6a3fa0;}
  .chip.s {background: rgba(228,87,46,.18);}
  .opm {font-size: .8rem; opacity: .65; font-style: italic;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=600)
def laad(mtime: float) -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def rijtijd(km: float | None) -> str:
    if km is None:
        return ""
    minuten = km * 1.25 / 75 * 60  # wegafstand ≈ 1,25 × hemelsbreed, gemiddeld 75 km/u
    if minuten < 60:
        return f"± {int(round(minuten / 5) * 5) or 5} min rijden"
    return f"± {minuten / 60:.1f} u rijden".replace(".", ",")


def ics(e: dict) -> str:
    s = e["start"]
    if "T" in s:
        begin = datetime.fromisoformat(s)
        regel_start = f"DTSTART:{begin:%Y%m%dT%H%M00}"
        regel_eind = f"DTEND:{begin + timedelta(hours=4):%Y%m%dT%H%M00}"
    else:
        begin = date.fromisoformat(s[:10])
        eind = date.fromisoformat(e["eind"][:10]) if e.get("eind") else begin
        regel_start = f"DTSTART;VALUE=DATE:{begin:%Y%m%d}"
        regel_eind = f"DTEND;VALUE=DATE:{eind + timedelta(days=1):%Y%m%d}"
    plaats = ", ".join(x for x in (e.get("zaal"), e.get("adres"), e.get("stad")) if x)
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//latin-agenda//NL", "BEGIN:VEVENT",
        f"UID:{abs(hash(e['titel'] + e['start']))}@latin-agenda", regel_start, regel_eind,
        f"SUMMARY:{e['titel']}", f"LOCATION:{plaats}", f"URL:{e.get('url', '')}",
        f"DESCRIPTION:{e.get('url', '')}", "END:VEVENT", "END:VCALENDAR", ""])


if not DATA.exists():
    st.error("Nog geen data. Draai eerst `python ophalen.py` (of `python ophalen.py --offline`).")
    st.stop()

data = laad(DATA.stat().st_mtime)
df = pd.DataFrame(data["events"])
if df.empty:
    st.info("Geen events gevonden.")
    st.stop()
df["dag"] = pd.to_datetime(df["start"].str[:10])
df["eind_dag"] = pd.to_datetime(df["eind"].fillna(df["start"]).str[:10])
tekstvelden = ["eind", "zaal", "stad", "adres", "land", "prijs", "url", "opmerking", "bron"]
df[tekstvelden] = df[tekstvelden].fillna("")

# ---------------- Filters ----------------
with st.sidebar:
    st.header("Filters")
    soorten = st.multiselect("Soort", list(SOORT_LABEL), default=list(SOORT_LABEL),
                             format_func=lambda s: SOORT_LABEL[s])
    alle_genres = sorted({g for gs in df["genres"] for g in gs})
    genres = st.multiselect("Genre", alle_genres, placeholder="Alle genres")
    landen = st.multiselect("Land", sorted(df["land"].dropna().unique()),
                            default=sorted(df["land"].dropna().unique()),
                            format_func=lambda l: f"{VLAG.get(l, '')} {l}")
    max_km = int(df["afstand_km"].max() or 0) + 1
    km = st.slider("Max. afstand vanaf Brugge (km)", 0, max(max_km, 10), max(max_km, 10), step=5)
    eerste, laatste = df["dag"].min().date(), df["eind_dag"].max().date()
    periode = st.date_input("Periode", (max(eerste, date.today()), laatste),
                            min_value=min(eerste, date.today()), max_value=laatste, format="DD/MM/YYYY")
    zoek = st.text_input("Zoek (artiest, zaal, stad)")
    toon_herhaling = st.toggle("Wekelijkse dansavonden tonen", value=True,
                               help="Zet uit om een rustigere lijst te krijgen.")

f = df[df["soort"].isin(soorten) & df["land"].isin(landen)]
f = f[f["afstand_km"].isna() | (f["afstand_km"] <= km)]
if genres:
    f = f[f["genres"].apply(lambda gs: bool(set(gs) & set(genres)))]
if isinstance(periode, tuple) and len(periode) == 2:
    f = f[(f["eind_dag"].dt.date >= periode[0]) & (f["dag"].dt.date <= periode[1])]
if zoek:
    z = zoek.lower()
    f = f[f.apply(lambda r: z in " ".join([r["titel"], r["zaal"], r["stad"], *r["artiesten"]]).lower(),
                  axis=1)]
if not toon_herhaling:
    tellingen = f[f["soort"] == "dansavond"].groupby("titel")["titel"].transform("count")
    f = f.drop(tellingen[tellingen >= 20].index)  # ± wekelijks

# ---------------- Kop ----------------
st.title("💃 Latin Agenda")
bijgewerkt = datetime.fromisoformat(data["bijgewerkt"]).astimezone()
st.caption(f"Latin concerten, festivals en salsa/bachata-avonden · afstanden vanaf "
           f"{data.get('vertrekpunt', 'Brugge')} · bijgewerkt {bijgewerkt:%d/%m/%Y %H:%M}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Concerten", int((f["soort"] == "concert").sum()))
c2.metric("Festivals", int((f["soort"] == "festival").sum()))
c3.metric("Dansavonden", int((f["soort"] == "dansavond").sum()))
volgende = f[f["dag"].dt.date >= date.today()].head(1)
c4.metric("Eerstvolgende", volgende["dag"].dt.strftime("%d/%m").iloc[0] if len(volgende) else "–")

tab_lijst, tab_kaart, tab_tabel = st.tabs(["📅 Agenda", "🗺️ Kaart", "📋 Tabel"])

with tab_lijst:
    if f.empty:
        st.info("Niets gevonden met deze filters.")
    huidige_maand = None
    for i, (_, e) in enumerate(f.sort_values("start").iterrows()):
        d = e["dag"]
        maand = (d.year, d.month)
        if maand != huidige_maand:
            huidige_maand = maand
            st.markdown(f'<div class="maand">{MAANDEN[d.month - 1]} {d.year}</div>',
                        unsafe_allow_html=True)
        tijd = e["start"][11:16] if "T" in e["start"] else ""
        tot = ""
        if e.get("eind") and e["eind"][:10] > e["start"][:10]:
            ed = date.fromisoformat(e["eind"][:10])
            tot = f" t/m {DAGEN[ed.weekday()]} {ed.day} {MAANDEN[ed.month - 1][:3]}"
        plek = " · ".join(x for x in (e["zaal"], e["stad"]) if x)
        afstand = (f"{e['afstand_km']:.0f} km · {rijtijd(e['afstand_km'])}"
                   if pd.notna(e["afstand_km"]) else "")
        chips = f'<span class="chip s">{SOORT_LABEL[e["soort"]]}</span>' + "".join(
            f'<span class="chip">{g}</span>' for g in e["genres"])
        extra = " · ".join(x for x in (tijd and f"🕘 {tijd}", tot.strip(), e.get("prijs") or "") if x)
        opm = f'<div class="opm">{e["opmerking"]}</div>' if e.get("opmerking") else ""
        links, rechts = st.columns([6, 1.3])
        links.markdown(f"""
<div class="kaart soort-{e['soort']}">
  <div class="datum"><div class="w">{DAGEN[d.weekday()]}</div><div class="d">{d.day}</div></div>
  <div>
    <div class="titel">{e['titel']}</div>
    <div class="meta">{VLAG.get(e['land'], '')} {plek}{' · ' + afstand if afstand else ''}</div>
    <div class="meta">{extra}</div>
    <div>{chips}</div>{opm}
  </div>
</div>""", unsafe_allow_html=True)
        with rechts:
            if e.get("url"):
                st.link_button("Info / tickets", e["url"], width="stretch")
            st.download_button("📆 In agenda", ics(e), file_name="event.ics", mime="text/calendar",
                               key=f"ics{i}", width="stretch")

with tab_kaart:
    k = f.dropna(subset=["lat", "lon"]).copy()
    if k.empty:
        st.info("Geen events met locatie.")
    else:
        kleuren = {"concert": "#e4572e", "festival": "#2e86ab", "dansavond": "#7a4fad"}
        k["kleur"] = k["soort"].map(kleuren)
        st.map(k, latitude="lat", longitude="lon", color="kleur", size=900)
        st.caption("🟠 concert · 🔵 festival · 🟣 dansavond")

with tab_tabel:
    tabel = f[["start", "soort", "titel", "zaal", "stad", "land", "afstand_km", "genres", "prijs",
               "url", "bron"]].copy()
    tabel["genres"] = tabel["genres"].apply(", ".join)
    st.dataframe(tabel, hide_index=True, width="stretch",
                 column_config={"url": st.column_config.LinkColumn("link"),
                                "afstand_km": st.column_config.NumberColumn("km", format="%.0f")})
    st.download_button("Download als CSV", tabel.to_csv(index=False).encode("utf-8-sig"),
                       "latin-agenda.csv", "text/csv")

st.divider()
st.caption("Bronnen: Ticketmaster, Bandsintown, Salsa Vida (salsavida.com), Songkick en eigen invoer. "
           "Gegevens kunnen wijzigen: check altijd de link. Afstanden hemelsbreed, rijtijd is een schatting.")
