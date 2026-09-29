import time
import json
import random
import pandas as pd
from datetime import datetime

# Wczytanie prawdziwych ID schronów z pliku wygenerowanego przez Osobę 1
df_shelters = pd.read_csv('Dim_Schrony_Gotowe.csv')
SHELTER_IDS = df_shelters['ID_Schronu'].tolist()

INTERVAL_SECONDS = 3    
INCIDENT_TRIGGER_TIME = 30
OUTPUT_FILE = "drone_telemetry.jsonl"
INCIDENT_SHELTER_ID = SHELTER_IDS[0] # Pierwszy schron na liście będzie miał "przepełnienie"

def generate_normal_traffic(shelter_id):
    return random.randint(5, 40)

def generate_incident_traffic(shelter_id):
    if shelter_id == INCIDENT_SHELTER_ID:
        return random.randint(180, 250)
    else:
        return random.randint(0, 15)

def main():
    print(f" Rozpoczynam symulację lotu drona dla {len(SHELTER_IDS)} schronów. Dane trafiają do: {OUTPUT_FILE}")
    
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
                
                with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                    f.write(json_data + '\n')
                
                print(f"[DRONE DATA] {json_data}")
            
            print("-" * 50)
            time.sleep(INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n Symulacja przerwana przez użytkownika.")

if __name__ == "__main__":
    main()
