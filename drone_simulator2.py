import time
import json
import random
from datetime import datetime

# Konfiguracja symulacji
SHELTER_IDS = [1, 2, 3]
INTERVAL_SECONDS = 3
INCIDENT_TRIGGER_TIME = 30
OUTPUT_FILE = "drone_telemetry.jsonl"  # Plik wyjściowy dla Osoby 1


def generate_normal_traffic(shelter_id):
    return random.randint(5, 40)


def generate_incident_traffic(shelter_id):
    if shelter_id == 1:
        return random.randint(180, 250)
    else:
        return random.randint(0, 15)


def main():
    print(f"🚀 Rozpoczynam symulację lotu drona. Dane trafiają do: {OUTPUT_FILE}")

    # Czyści zawartość pliku przy każdym nowym uruchomieniu skryptu
    open(OUTPUT_FILE, 'w').close()

    start_time = time.time()

    try:
        while True:
            elapsed_time = time.time() - start_time
            is_incident_active = elapsed_time > INCIDENT_TRIGGER_TIME

            for shelter_id in SHELTER_IDS:
                if is_incident_active:
                    thermal_count = generate_incident_traffic(shelter_id)
                else:
                    thermal_count = generate_normal_traffic(shelter_id)

                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "shelter_id": shelter_id,
                    "thermal_objects_count": thermal_count,
                    "is_incident_active": is_incident_active
                }

                json_data = json.dumps(payload)

                # Zapis do pliku w trybie append ('a' - dopisywanie na końcu)
                with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                    f.write(json_data + '\n')

                # Podgląd w konsoli
                print(f"[DRONE DATA] {json_data}")

            print("-" * 50)
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n🛑 Symulacja przerwana przez użytkownika.")


if __name__ == "__main__":
    main()
