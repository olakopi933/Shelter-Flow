import time
import json
import pandas as pd
import os

# Konfiguracja
TELEMETRY_FILE = "drone_telemetry.jsonl"
SHELTERS_DB_FILE = "Dim_Schrony_Gotowe.csv"
OUTPUT_DASHBOARD_FILE = "current_shelter_status.csv"

# Wczytanie statycznej bazy schronów
print("Wczytywanie bazy schronów...")
df_shelters = pd.read_csv(SHELTERS_DB_FILE)
# Optymalizacja: stworzenie słownika z ID jako kluczem i pojemnością jako wartością
shelter_capacities = dict(zip(df_shelters['ID_Schronu'], df_shelters['Pojemnosc_Max']))

# Słownik przechowujący najnowszy stan każdego schronu
current_status = {}


def determine_status(percentage):
    """Reguły biznesowe flagowania (Issue #7)"""
    if percentage < 80:
        return "ZIELONY"
    elif percentage <= 100:
        return "POMARAŃCZOWY"
    else:
        return "CZERWONY"


def process_telemetry_line(line):
    """Przetwarza pojedynczą paczkę danych z drona."""
    try:
        data = json.loads(line)
        shelter_id = data['shelter_id']
        thermal_count = data['thermal_objects_count']
        timestamp = data['timestamp']

        # Pobranie pojemności maksymalnej
        max_capacity = shelter_capacities.get(shelter_id)

        if max_capacity:
            # Wyliczenie procentowego zapełnienia (Issue #6)
            fill_percentage = round((thermal_count / max_capacity) * 100, 1)
            status_color = determine_status(fill_percentage)

            # Aktualizacja najnowszego stanu
            current_status[shelter_id] = {
                "Timestamp": timestamp,
                "ID_Schronu": shelter_id,
                "Wykryte_Osoby": thermal_count,
                "Pojemnosc_Max": max_capacity,
                "Zarejestrowane_Zapl": f"{fill_percentage}%",
                "Status": status_color
            }

            # Zapisz zagregowane dane do pliku dla Dashboardu
            save_to_dashboard()

    except json.JSONDecodeError:
        pass  # Ignoruj błędy parsowania (np. puste linie)


def save_to_dashboard():
    """Zapisuje zaktualizowany stan do pliku CSV, który czyta Power BI / Streamlit."""
    if not current_status:
        return

    # Łączenie najnowszego stanu z danymi geograficznymi i nazwami
    df_current = pd.DataFrame.from_dict(current_status, orient='index')
    df_final = pd.merge(df_shelters, df_current, on="ID_Schronu", how="inner")

    # Zapis (nadpisywanie pliku, by dashboard miał zawsze najświeższy stan)
    df_final.to_csv(OUTPUT_DASHBOARD_FILE, index=False)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Zaktualizowano dane dla Dashboardu ({OUTPUT_DASHBOARD_FILE})")


def main():
    print(f"Uruchamianie procesu ETL. Nasłuchiwanie pliku {TELEMETRY_FILE}...")

    # Upewnienie się, że plik telemetryczny istnieje
    if not os.path.exists(TELEMETRY_FILE):
        open(TELEMETRY_FILE, 'w').close()

    with open(TELEMETRY_FILE, 'r', encoding='utf-8') as f:
        # Przejdź na koniec pliku, aby czytać tylko nowe dane
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)  # Czekaj na nowe dane od symulatora
                continue

            process_telemetry_line(line)


if __name__ == "__main__":
    from datetime import datetime

    main()