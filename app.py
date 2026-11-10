"""Latin Agenda — Streamlit-app.

Start lokaal met:  streamlit run app.py
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "events.json"

DAGEN = ["ma", "di", "wo", "do", "vr", "za", "zo"]
DAGEN_VOL = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"]
VLAG = {"BE": "🇧🇪", "NL": "🇳🇱", "FR": "🇫🇷"}
SOORT_NAAM = {"concert": "Concert", "festival": "Festival", "dansavond": "Dansavond"}
SOORT_MV = {"concert": "concerten", "festival": "festivals", "dansavond": "dansavonden"}
KLEUR = {"concert": "#DC2626", "festival": "#D97706", "dansavond": "#7C3AED"}


def svg(paden: str) -> str:
    """Lucide-icoon, kleurt mee met de tekst (licht én donker thema)."""
    return ('<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paden}</svg>')


IC = {
    "concert": svg('<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>'
                   '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/>'),
    "festival": svg('<path d="M3.5 21 14 3"/><path d="M20.5 21 10 3"/><path d="M15.5 21 12 15l-3.5 6"/>'
                    '<path d="M2 21h20"/>'),
    "dansavond": svg('<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>'),
    "plek": svg('<path d="M20 10c0 5-5.5 10.2-7.4 11.8a1 1 0 0 1-1.2 0C9.5 20.2 4 15 4 10a8 8 0 0 1 16 0"/>'
                '<circle cx="12" cy="10" r="3"/>'),
    "rit": svg('<polygon points="3 11 22 2 13 21 11 13 3 11"/>'),
    "tijd": svg('<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>'),
    "prijs": svg('<path d="M12.6 2.6A2 2 0 0 0 11.2 2H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.7 8.7a2.4 2.4 0 0 0 '
                 '3.4 0l6.6-6.6a2.4 2.4 0 0 0 0-3.4z"/><circle cx="7.5" cy="7.5" r="1"/>'),
    "periode": svg('<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>'),
    "herhaal": svg('<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/>'
                   '<path d="M21 13v1a4 4 0 0 1-4 4H3"/>'),
}

st.set_page_config(page_title="Latin Agenda", page_icon=":material/music_note:", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');
  .block-container {padding-top: 1.6rem; max-width: 1000px;}
  .kop {font-family: 'Bebas Neue', sans-serif; font-size: 3.2rem; line-height: 1; letter-spacing: .5px;
        margin: 0;}
  .kop span {color: #DC2626;}
  .sub {font-size: .95rem; opacity: .8; margin: .2rem 0 .8rem;}
  .tellers {display: flex; flex-wrap: wrap; gap: .3rem 1.2rem; margin: .2rem 0 .6rem; font-size: .92rem;}
  .tellers > span {white-space: nowrap;}
  .tellers b {font-size: 1.05rem;}
  .maand {font-family: 'Bebas Neue', sans-serif; font-size: 1.9rem; letter-spacing: .5px; line-height: 1;
          margin: 1.4rem 0 .5rem; text-transform: capitalize;
          border-bottom: 3px solid #DC2626; padding-bottom: .25rem;}
  .kaart {display: flex; gap: .9rem; border-left: 4px solid var(--c); padding: .15rem 0 .1rem .8rem;}
  .datum {min-width: 44px; text-align: center; line-height: 1.05;}
  .datum .d {font-family: 'Bebas Neue', sans-serif; font-size: 2.1rem;}
  .datum .w {font-size: .78rem; font-weight: 600; text-transform: uppercase; opacity: .85;}
  .titel {font-weight: 700; font-size: 1.08rem; line-height: 1.3;}
  .meta {font-size: .9rem; opacity: .85; display: flex; flex-wrap: wrap; gap: .15rem .9rem; margin-top: .15rem;}
  .meta > span {display: inline-flex; align-items: center; gap: .3rem;}
  .ic {width: 15px; height: 15px; flex: none;}
  .chips {display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .4rem;}
  .chip {display: inline-flex; align-items: center; gap: .3rem; font-size: .78rem; font-weight: 600;
         padding: 2px 9px; border-radius: 999px; color: inherit;
         background: color-mix(in srgb, var(--c) 16%, transparent);
         border: 1px solid color-mix(in srgb, var(--c) 55%, transparent);}
  .chip.g {--c: #888; font-weight: 500;}
  .chip .ic {width: 13px; height: 13px;}
  .opm {font-size: .85rem; opacity: .8; font-style: italic; margin-top: .3rem;}
  .legenda {display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; font-size: .9rem;}
  .stip {display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: .35rem;
         vertical-align: -1px;}
  @media (max-width: 640px) {
    .block-container {padding-left: .9rem; padding-right: .9rem;}
    .kop {font-size: 2.6rem;}
  }
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


# ---------------- Kop ----------------
bijgewerkt = datetime.fromisoformat(data["bijgewerkt"]).astimezone()
st.markdown(f'<h1 class="kop">Latin <span>Agenda</span></h1>'
            f'<p class="sub">Concerten, festivals en salsa/bachata-avonden · afstanden vanaf '
            f'{data.get("vertrekpunt", "Brugge")} · bijgewerkt {bijgewerkt:%d/%m/%Y %H:%M}</p>',
            unsafe_allow_html=True)

# ---------------- Filters (bovenaan, ook zichtbaar op de gsm) ----------------
vandaag = date.today()
soorten = st.pills("Soort", list(SOORT_NAAM), selection_mode="multi", default=list(SOORT_NAAM),
                   format_func=lambda s: SOORT_NAAM[s], label_visibility="collapsed") or list(SOORT_NAAM)
wanneer = st.segmented_control("Wanneer", ["Alles", "Dit weekend", "Komende 30 dagen"], default="Alles",
                               label_visibility="collapsed") or "Alles"
zoek = st.text_input("Zoek", placeholder="Zoek op artiest, zaal of stad", label_visibility="collapsed")

with st.expander("Meer filters", icon=":material/tune:"):
    k1, k2 = st.columns(2)
    alle_genres = sorted({g for gs in df["genres"] for g in gs})
    genres = k1.multiselect("Genre", alle_genres, placeholder="Alle genres")
    alle_landen = sorted(df["land"].dropna().unique())
    landen = k2.multiselect("Land", alle_landen, default=alle_landen,
                            format_func=lambda l: f"{VLAG.get(l, '')} {l}")
    max_km = max(int(df["afstand_km"].max() or 0) + 1, 10)
    km = k1.slider("Max. afstand vanaf Brugge (km)", 0, max_km, max_km, step=5)
    eerste, laatste = df["dag"].min().date(), df["eind_dag"].max().date()
    periode = k2.date_input("Periode", (max(eerste, vandaag), laatste), min_value=min(eerste, vandaag),
                            max_value=laatste, format="DD/MM/YYYY")
    samenvoegen = st.toggle("Wekelijkse en maandelijkse avonden samenvoegen", value=True,
                            help="Toont een terugkerende dansavond één keer, met de eerstvolgende datum.")

f = df[df["soort"].isin(soorten) & df["land"].isin(landen or alle_landen)]
f = f[f["afstand_km"].isna() | (f["afstand_km"] <= km)]
if genres:
    f = f[f["genres"].apply(lambda gs: bool(set(gs) & set(genres)))]
if isinstance(periode, tuple) and len(periode) == 2:
    f = f[(f["eind_dag"].dt.date >= periode[0]) & (f["dag"].dt.date <= periode[1])]
if wanneer == "Dit weekend":
    vr = vandaag + timedelta(days=(4 - vandaag.weekday()) % 7) if vandaag.weekday() < 4 else \
        vandaag - timedelta(days=vandaag.weekday() - 4)
    zo = vr + timedelta(days=2)
    f = f[(f["eind_dag"].dt.date >= max(vr, vandaag)) & (f["dag"].dt.date <= zo)]
elif wanneer == "Komende 30 dagen":
    f = f[(f["eind_dag"].dt.date >= vandaag) & (f["dag"].dt.date <= vandaag + timedelta(days=30))]
if zoek:
    z = zoek.lower()
    f = f[f.apply(lambda r: z in " ".join([r["titel"], r["zaal"], r["stad"], *r["artiesten"]]).lower(),
                  axis=1)]
f = f.sort_values("start")

# Terugkerende dansavonden: één regel met de eerstvolgende datum.
herhaling: dict[str, str] = {}
lijst = f
if samenvoegen:
    dans = f[f["soort"] == "dansavond"]
    aantallen = dans.groupby("titel")["titel"].count()
    for titel in aantallen[aantallen >= 3].index:
        rijen = dans[dans["titel"] == titel]
        dagen = set(rijen["dag"].dt.weekday)
        if len(dagen) == 1:
            wd = DAGEN_VOL[dagen.pop()]
            interval = (rijen["dag"].diff().dt.days.median() or 7)
            ritme = f"elke {wd}" if interval <= 8 else f"maandelijks op {wd}"
        else:
            ritme = "terugkerend"
        herhaling[titel] = f"{ritme} · {len(rijen)} data t/m {rijen['dag'].max():%d/%m}"
    lijst = f[~f["titel"].isin(herhaling) | ~f.duplicated("titel")]

n = {s: int((f["soort"] == s).sum()) for s in SOORT_NAAM}
volgende = f[f["eind_dag"].dt.date >= vandaag].head(1)
tellers = "".join(f"<span><b>{n[s]}</b> {SOORT_MV[s]}</span>" for s in SOORT_NAAM if s in soorten)
if len(volgende):
    d0 = volgende["dag"].iloc[0]
    tellers += f"<span>eerstvolgende <b>{DAGEN[d0.weekday()]} {d0.day}/{d0.month}</b></span>"
st.markdown(f'<div class="tellers">{tellers}</div>', unsafe_allow_html=True)

tab_lijst, tab_kaart, tab_tabel = st.tabs([":material/event: Agenda", ":material/map: Kaart",
                                          ":material/table_rows: Tabel"])

with tab_lijst:
    if lijst.empty:
        st.info("Niets gevonden met deze filters.")
    huidige_maand = None
    for i, (_, e) in enumerate(lijst.iterrows()):
        d = e["dag"]
        if (d.year, d.month) != huidige_maand:
            huidige_maand = (d.year, d.month)
            st.markdown(f'<div class="maand">{MAANDEN[d.month - 1]} {d.year}</div>', unsafe_allow_html=True)
        meta = []
        plek = " · ".join(html.escape(x) for x in (e["zaal"], e["stad"]) if x)
        if plek:
            meta.append(f'<span>{IC["plek"]}{VLAG.get(e["land"], "")} {plek}</span>')
        if pd.notna(e["afstand_km"]):
            meta.append(f'<span>{IC["rit"]}{e["afstand_km"]:.0f} km · {rijtijd(e["afstand_km"])}</span>')
        meta2 = []
        if "T" in e["start"]:
            meta2.append(f'<span>{IC["tijd"]}{e["start"][11:16]}</span>')
        if e.get("eind") and e["eind"][:10] > e["start"][:10]:
            ed = date.fromisoformat(e["eind"][:10])
            meta2.append(f'<span>{IC["periode"]}t/m {DAGEN[ed.weekday()]} {ed.day} '
                         f'{MAANDEN[ed.month - 1][:3]}</span>')
        if e.get("prijs"):
            meta2.append(f'<span>{IC["prijs"]}{html.escape(e["prijs"])}</span>')
        if e["titel"] in herhaling:
            meta2.append(f'<span>{IC["herhaal"]}{herhaling[e["titel"]]}</span>')
        chips = (f'<span class="chip">{IC[e["soort"]]}{SOORT_NAAM[e["soort"]]}</span>'
                 + "".join(f'<span class="chip g">{html.escape(g)}</span>' for g in e["genres"]))
        opm = f'<div class="opm">{html.escape(e["opmerking"])}</div>' if e.get("opmerking") else ""
        with st.container(border=True):
            st.markdown(f"""
<div class="kaart" style="--c:{KLEUR[e['soort']]}">
  <div class="datum"><div class="w">{DAGEN[d.weekday()]}</div><div class="d">{d.day}</div></div>
  <div>
    <div class="titel">{html.escape(e['titel'])}</div>
    <div class="meta">{''.join(meta)}</div>
    <div class="meta">{''.join(meta2)}</div>
    <div class="chips" style="--c:{KLEUR[e['soort']]}">{chips}</div>{opm}
  </div>
</div>""", unsafe_allow_html=True)
            with st.container(horizontal=True, gap="small"):
                if e.get("url"):
                    st.link_button("Info / tickets", e["url"], icon=":material/open_in_new:", type="primary")
                st.download_button("In agenda", ics(e), file_name="event.ics", mime="text/calendar",
                                   key=f"ics{i}", icon=":material/calendar_add_on:")

with tab_kaart:
    k = f.dropna(subset=["lat", "lon"]).copy()
    if k.empty:
        st.info("Geen events met locatie.")
    else:
        k["kleur"] = k["soort"].map(KLEUR)
        st.map(k, latitude="lat", longitude="lon", color="kleur", size=900)
        st.markdown('<div class="legenda">' + "".join(
            f'<span><span class="stip" style="background:{KLEUR[s]}"></span>{SOORT_NAAM[s]}</span>'
            for s in SOORT_NAAM) + "</div>", unsafe_allow_html=True)

with tab_tabel:
    tabel = f[["start", "soort", "titel", "zaal", "stad", "land", "afstand_km", "genres", "prijs",
               "url", "bron"]].copy()
    tabel["genres"] = tabel["genres"].apply(", ".join)
    st.dataframe(tabel, hide_index=True, width="stretch",
                 column_config={"url": st.column_config.LinkColumn("link"),
                                "afstand_km": st.column_config.NumberColumn("km", format="%.0f")})
    st.download_button("Download als CSV", tabel.to_csv(index=False).encode("utf-8-sig"),
                       "latin-agenda.csv", "text/csv", icon=":material/download:")

st.divider()
st.caption("Bronnen: Ticketmaster, Bandsintown, Salsa Vida (salsavida.com), Songkick en eigen invoer. "
           "Gegevens kunnen wijzigen: check altijd de link. Afstanden hemelsbreed, rijtijd is een schatting.")
