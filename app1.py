from __future__ import annotations

import html
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DIM_FILE = APP_DIR / "Dim_Schrony_Gotowe.csv"
SNAPSHOT_FILE = APP_DIR / "current_shelter_status.csv"
LIVE_STATUS_FILE = APP_DIR / "runtime" / "current_shelter_status.csv"

st.set_page_config(
    page_title="Shelter-Flow · Centrum operacyjne",
    page_icon="⌂",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
      :root { color-scheme: dark; }
      .stApp { background: #0c1218; color: #e1e9e8; }
      [data-testid="stHeader"] { background: #0c1218; }
      [data-testid="stSidebar"] { background: #0e151c; border-right: 1px solid #1c2932; }
      [data-testid="stSidebar"] * { font-family: 'DM Sans', sans-serif; }
      h1, h2, h3 { font-family: 'Manrope', sans-serif !important; color: #e1e9e8 !important; }
      h1 { font-size: 1.8rem !important; letter-spacing: -.04em; }
      h2 { font-size: 1.08rem !important; }
      p, label, [data-testid="stMarkdownContainer"] { color: #a4b0b2; }
      [data-testid="stMetric"] { background: #111a22; border: 1px solid #22303a; border-radius: 7px; padding: 13px 15px; }
      [data-testid="stMetricLabel"] { color: #99a7aa; font-size: .78rem; }
      [data-testid="stMetricValue"] { color: #e5ecea; font-family: 'Manrope',sans-serif; }
      [data-testid="stDataFrame"] { border: 1px solid #22303a; border-radius: 6px; }
      .eyebrow { color: #82c99d; font: 500 .72rem 'DM Mono', monospace; letter-spacing: .09em; }
      .muted { color: #829198; font-size: .82rem; }
      .warning-box { background: #281e17; border: 1px solid #5b4430; padding: 12px 14px; border-radius: 6px; color: #e2bd83; font-size: .83rem; }
      .ok-box { background: #14241c; border: 1px solid #315541; padding: 12px 14px; border-radius: 6px; color: #9bd2ad; font-size: .83rem; }
      div.stButton > button[kind="primary"] { background: #286044; border-color: #39744f; }
      footer { visibility: hidden; }
</style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_dimension(csv_path: str, modified: float) -> pd.DataFrame:
    """Wczytanie rejestru schronów za pomocą pandas."""
    del modified
    frame = pd.read_csv(csv_path, encoding="utf-8-sig")

    # Mapowanie kolumn według kolejności w Dim_Schrony_Gotowe.csv
    if len(frame.columns) >= 6:
        frame.columns = ["ID_Schronu", "Typ", "Adres", "Pojemność", "Szerokość", "Długość"] + list(frame.columns[6:])

    for column in ("Pojemność", "Szerokość", "Długość"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["Pojemność", "Szerokość", "Długość"]).copy()
    frame["Pojemność"] = frame["Pojemność"].astype(int)
    frame["Adres"] = frame["Adres"].astype(str)
    frame["Miejscowość"] = frame["Adres"].str.rsplit(",", n=1).str[-1].str.strip()
    frame["ID_Schronu"] = frame["ID_Schronu"].astype(str).str.strip()
    frame = frame[frame["ID_Schronu"].ne("")].drop_duplicates("ID_Schronu", keep="last")
    return frame.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_status(csv_path: str, modified: float) -> pd.DataFrame:
    """Wczytanie snapshotu generowanego przez etl_processor.py."""
    del modified
    path = Path(csv_path)
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"ID_Schronu": "string"})
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=["ID_Schronu", "Timestamp", "Wykryte_Osoby", "Obłożenie %", "Status"])

    aliases = {
        "ID_Schronu": "ID_Schronu",
        "Timestamp": "Timestamp",
        "Wykryte_Osoby": "Wykryte_Osoby",
        "Zarejestrowane_Zapl": "Obłożenie %",
        "Status": "Status",
    }
    for source, target in aliases.items():
        if source not in frame.columns:
            frame[target] = pd.NA
    frame = frame.rename(columns={"Zarejestrowane_Zapl": "Obłożenie %"})
    frame["ID_Schronu"] = frame["ID_Schronu"].astype("string").str.strip()
    frame["Wykryte_Osoby"] = pd.to_numeric(frame["Wykryte_Osoby"], errors="coerce")
    frame["Obłożenie %"] = pd.to_numeric(
        frame["Obłożenie %"].astype("string").str.replace("%", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    frame["Status"] = frame["Status"].astype("string").str.strip().str.upper()
    frame = frame.dropna(subset=["ID_Schronu"]).drop_duplicates("ID_Schronu", keep="last")
    return frame[["ID_Schronu", "Timestamp", "Wykryte_Osoby", "Obłożenie %", "Status"]]


def status_source() -> Path | None:
    if LIVE_STATUS_FILE.exists() and LIVE_STATUS_FILE.stat().st_size:
        return LIVE_STATUS_FILE
    if SNAPSHOT_FILE.exists() and SNAPSHOT_FILE.stat().st_size:
        return SNAPSHOT_FILE
    return None


def status_color(status: object) -> list[int]:
    return {
        "CZERWONY": [236, 119, 117, 225],
        "POMARAŃCZOWY": [231, 187, 112, 225],
        "ZIELONY": [121, 198, 151, 215],
    }.get(str(status).upper(), [102, 117, 123, 200])


def render_map(frame: pd.DataFrame) -> None:
    map_data = pd.DataFrame(
        {
            "longitude": frame["Długość"],
            "latitude": frame["Szerokość"],
            "color": frame["Kolor"],
            "address": frame["Adres"].map(html.escape),
            "shelter_type": frame["Typ"].map(html.escape),
            "capacity": frame["Pojemność"],
            "id": frame["ID_Schronu"].map(html.escape),
            "people": frame["Wykryte_Osoby"],
            "occupancy": frame["Obłożenie %"],
        }
    )
    view = pdk.ViewState(
        latitude=float(frame["Szerokość"].mean()),
        longitude=float(frame["Długość"].mean()),
        zoom=7,
        pitch=0,
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,
        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_line_color=[230, 239, 236, 230],
        get_radius=900,
        line_width_min_pixels=1,
        stroked=True,
        filled=True,
        pickable=True,
        auto_highlight=True,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        tooltip={
            "html": "<b>{address}</b><br/>Typ: {shelter_type}<br/>Wykryte osoby: {people}<br/>"
                    "Pojemność: {capacity}<br/>Obłożenie: {occupancy}% · {id}",
            "style": {"backgroundColor": "#111a22", "color": "#e1e9e8"},
        },
    )
    st.pydeck_chart(deck, width="stretch", height=490)


with st.sidebar:
    st.markdown("## ⌂ Shelter-Flow")
    st.caption("CENTRUM ZARZĄDZANIA KRYZYSOWEGO")
    st.divider()
    st.markdown("<span class='eyebrow'>OBSZAR OPERACYJNY</span>", unsafe_allow_html=True)
    st.markdown("**Polska · rejestr schronów**")
    st.caption("Widok odświeża odczyty co 3 sekundy.")
    st.divider()
    st.markdown("**Źródło pomiarów**")
    st.caption("Symulator drona → plik JSONL → proces ETL → aktualny status CSV.")
    st.divider()
    st.markdown("**Prywatność**")
    st.caption("Symulator generuje tylko liczbę wykrytych obiektów. Obraz ani dane osobowe nie są przetwarzane.")

st.markdown("<div class='eyebrow'>MONITORING MIEJSC UKRYCIA &nbsp;·&nbsp; PANEL DYSPOZYTORA</div>",
            unsafe_allow_html=True)
st.title("Obraz sytuacji")
st.markdown("<div class='muted'>Lokalizacje pochodzą z wymiaru schronów, a obłożenie z procesu ETL.</div>",
            unsafe_allow_html=True)
st.write("")

shelters: pd.DataFrame | None = None

if not DIM_FILE.exists():
    st.error(
        f"Nie znaleziono pliku {DIM_FILE.name}. Upewnij się, że plik Dim_Schrony_Gotowe.csv znajduje się w folderze projektu.")
    st.stop()
    sys.exit(0)

try:
    shelters = load_dimension(str(DIM_FILE), DIM_FILE.stat().st_mtime)
except Exception as error:
    st.error(f"Nie udało się wczytać rejestru schronów: {error}")
    st.stop()
    sys.exit(0)


@st.fragment(run_every="3s")
def live_dashboard(dimension: pd.DataFrame) -> None:
    source = status_source()
    if source is None:
        status = pd.DataFrame(columns=["ID_Schronu", "Timestamp", "Wykryte_Osoby", "Obłożenie %", "Status"])
        source_name = "brak pliku statusów"
    else:
        try:
            status = load_status(str(source), source.stat().st_mtime)
            source_name = "symulacja na żywo" if source == LIVE_STATUS_FILE else "migawka statusów z repozytorium"
        except (OSError, pd.errors.ParserError, UnicodeDecodeError):
            status = pd.DataFrame(columns=["ID_Schronu", "Timestamp", "Wykryte_Osoby", "Obłożenie %", "Status"])
            source_name = "oczekiwanie na kompletny zapis ETL"

    view = dimension.merge(status, on="ID_Schronu", how="left")
    view["Wykryte_Osoby"] = pd.to_numeric(view["Wykryte_Osoby"], errors="coerce")
    calculated = (view["Wykryte_Osoby"] / view["Pojemność"] * 100).round(1)
    view["Obłożenie %"] = pd.to_numeric(view["Obłożenie %"], errors="coerce").fillna(calculated)
    view["Status"] = view["Status"].fillna("BRAK ODCZYTU").astype(str).str.upper()
    view["Status"] = view.apply(
        lambda row: row["Status"] if row["Status"] in {"CZERWONY", "POMARAŃCZOWY", "ZIELONY"} else (
            "CZERWONY" if pd.notna(row["Obłożenie %"]) and row["Obłożenie %"] > 100 else
            "POMARAŃCZOWY" if pd.notna(row["Obłożenie %"]) and row["Obłożenie %"] >= 80 else
            "ZIELONY" if pd.notna(row["Obłożenie %"]) else "BRAK ODCZYTU"
        ),
        axis=1,
    )
    view["Kolor"] = view["Status"].map(status_color)
    total_capacity = int(dimension["Pojemność"].sum())
    known = view[view["Wykryte_Osoby"].notna()]
    overloaded = int((view["Status"] == "CZERWONY").sum())
    active_count = int(view["Status"].isin(["CZERWONY", "POMARAŃCZOWY", "ZIELONY"]).sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Miejsca w katalogu", len(dimension))
    m2.metric("Łączna pojemność", f"{total_capacity:,}".replace(",", " "), "osób według rejestru")
    m3.metric("Odczyty schronów", f"{active_count} / {len(dimension)}", source_name)
    m4.metric("Schrony przepełnione", overloaded if active_count else "—",
              "według odczytu ETL" if active_count else "brak telemetrii")

    if active_count:
        most_recent = pd.to_datetime(known["Timestamp"], errors="coerce").max() if "Timestamp" in known else pd.NaT
        time_note = f" Ostatni zapis: {most_recent:%Y-%m-%d %H:%M:%S}." if pd.notna(most_recent) else ""
        st.markdown(
            f"<div class='warning-box'>Dane obłożenia pochodzą z <b>{html.escape(source_name)}</b>. "
            f"Pliki projektu generują przykładową telemetrię przez symulator drona; to nie są rzeczywiste pomiary z terenu.{html.escape(time_note)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='warning-box'>Brak odczytów telemetrycznych. Uruchom symulator i ETL, aby zobaczyć aktualne obłożenie. Dostępne są lokalizacje oraz pojemności ze słownika.</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    map_tab, list_tab, alert_tab = st.tabs(["Mapa schronów", "Rejestr schronów", "Komunikat dla mieszkańców"])

    with map_tab:
        left, right = st.columns([1.35, 1])
        with left:
            st.subheader("Rozmieszczenie i obłożenie")
            st.caption(
                "Kolor punktu odpowiada statusowi obliczonemu w procesie ETL. Wymaga połączenia internetowego do załadowania kafelków mapy.")
            render_map(view)
        with right:
            st.subheader("Schrony")
            city_options = ["Wszystkie miejscowości", *sorted(dimension["Miejscowość"].unique())]
            selected_city = st.selectbox("Miejscowość", city_options, label_visibility="collapsed")
            filtered = view if selected_city == "Wszystkie miejscowości" else view[view["Miejscowość"] == selected_city]
            severity = {"CZERWONY": 0, "POMARAŃCZOWY": 1, "ZIELONY": 2, "BRAK ODCZYTU": 3}
            filtered = filtered.assign(_severity=filtered["Status"].map(severity)).sort_values(
                ["_severity", "Obłożenie %"], ascending=[True, False])
            for _, shelter in filtered.iterrows():
                icon = {"CZERWONY": "🔴", "POMARAŃCZOWY": "🟠", "ZIELONY": "🟢", "BRAK ODCZYTU": "⚪"}[shelter["Status"]]
                if pd.notna(shelter["Wykryte_Osoby"]):
                    details = f"{int(shelter['Wykryte_Osoby'])} / {shelter['Pojemność']} osób · {shelter['Obłożenie %']:.1f}% · {shelter['Status']}"
                else:
                    details = f"Pojemność: {shelter['Pojemność']} osób · brak odczytu"
                with st.container(border=True):
                    st.markdown(f"{icon} **{shelter['Adres']}**")
                    st.caption(f"{shelter['Typ']} · {details}")

    with list_tab:
        st.subheader("Dane schronów i ostatnie odczyty")
        search = st.text_input("Szukaj po adresie, typie lub ID", placeholder="Wpisz miejscowość, ulicę lub ID")
        table = view.copy()
        if search:
            mask = table[["ID_Schronu", "Typ", "Adres", "Miejscowość"]].astype(str).apply(
                lambda column: column.str.contains(search, case=False, na=False)
            ).any(axis=1)
            table = table[mask]
        table = table.rename(
            columns={"ID_Schronu": "ID schronu", "Wykryte_Osoby": "Wykryte osoby", "Status": "Status ETL"})
        st.dataframe(
            table[
                ["ID schronu", "Typ", "Adres", "Miejscowość", "Pojemność", "Wykryte osoby", "Obłożenie %", "Status ETL",
                 "Timestamp"]],
            width="stretch",
            hide_index=True,
        )

    with alert_tab:
        st.subheader("Przygotuj szkic komunikatu")
        st.caption("Szkic generowany w panelu dyspozytora do dystrybucji przez stacje BTS.")
        red = view[view["Status"] == "CZERWONY"]
        green = view[view["Status"] == "ZIELONY"]
        if red.empty:
            st.info("Brak schronów oznaczonych na czerwono w aktualnym odczycie.")
        elif green.empty:
            st.warning(
                "Wykryto przepełnienie, ale brak schronu o statusie zielonym, który można wskazać jako alternatywę.")
        else:
            selected_id = st.selectbox(
                "Przepełniony schron",
                red["ID_Schronu"].tolist(),
                format_func=lambda shelter_id: str(view.loc[view["ID_Schronu"] == shelter_id, "Adres"].iloc[0]),
            )
            alternatives = green[green["ID_Schronu"] != selected_id]
            if alternatives.empty:
                st.warning("Brak alternatywnego schronu o statusie zielonym.")
            else:
                target_id = st.selectbox(
                    "Schron zastępczy",
                    alternatives["ID_Schronu"].tolist(),
                    format_func=lambda shelter_id: str(view.loc[view["ID_Schronu"] == shelter_id, "Adres"].iloc[0]),
                )
                source_shelter = view.loc[view["ID_Schronu"] == selected_id].iloc[0]
                target = view.loc[view["ID_Schronu"] == target_id].iloc[0]
                people = int(target["Wykryte_Osoby"]) if pd.notna(target["Wykryte_Osoby"]) else 0
                free = max(0, int(target["Pojemność"]) - people)
                draft = (
                    f"Miejsce ukrycia przy {source_shelter['Adres']} jest przepełnione. "
                    f"Skieruj się do {target['Adres']}. Pojemność: {target['Pojemność']} osób; "
                    f"szacowana liczba wolnych miejsc: {free}. Sprawdź oznakowanie i polecenia służb."
                )
                message = st.text_area("Treść szkicu", value=draft, height=110)
                if st.button("Zapisz szkic w tej sesji", type="primary"):
                    st.session_state["saved_alert_draft"] = message
                    st.success("Szkic zatwierdzony przez dyspozytora.")

    st.divider()
    st.caption(
        f"Status: {source_name} · {active_count} z {len(dimension)} schronów z odczytem · "
        "dane telemetryczne symulowane z modułu drona."
    )


if shelters is not None:
    live_dashboard(shelters)