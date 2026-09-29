import json
import time
from datetime import datetime
import os
import random

# Ten kod sam sprawdzi, w jakim folderze jest Twój skrypt
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# I sam stworzy podfolder "Drony_Input" dokładnie obok skryptu
OUTPUT_DIR = os.path.join(BASE_DIR, "Drony_Input")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print("=" * 50)
print(f"ZAPISUJĘ PLIKI DOKŁADNIE TUTAJ:\n{OUTPUT_DIR}")
print("=" * 50)

# MAGIA: Ten kawałek kodu sam otworzy Ci to okienko z folderem w Windowsie!
try:
    os.startfile(OUTPUT_DIR)
except AttributeError:
    pass  # Gdyby to nie był Windows

try:
    while True:
        current_time = datetime.now().isoformat()

        for shelter_id in [1, 2, 3]:
            if shelter_id == 1:
                thermal_count = random.randint(180, 200)
                is_incident = True
            else:
                thermal_count = random.randint(1, 30)
                is_incident = False

            data = {
                "timestamp": current_time,
                "shelter_id": shelter_id,
                "thermal_objects_count": thermal_count,
                "is_incident_active": is_incident
            }

            file_name = f"zwiad_{shelter_id}_{int(time.time() * 1000)}.json"
            file_path = os.path.join(OUTPUT_DIR, file_name)

            # Fizyczny zapis
            with open(file_path, "w") as json_file:
                json.dump(data, json_file)

        print(f"[{current_time}] Zapisano 3 nowe pliki do folderu.")
        time.sleep(3)

except KeyboardInterrupt:
    print("\nSymulacja przerwana.")