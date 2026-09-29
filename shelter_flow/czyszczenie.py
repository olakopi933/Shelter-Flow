import pandas as pd
import numpy as np

df = pd.read_csv('punkty_schronienia.csv', sep=',')

# 20 pierwszych wierszy
df = df.head(20)

# Zmiana nazw kolumn pod bazę SQL
df = df.rename(columns={
    'Identyfikator publiczny': 'ID_Schronu',
    'Adres': 'Nazwa',
    'Szerokosc geograficzna': 'Szerokosc_Geo',
    'Dlugosc geograficzna': 'Dlugosc_Geo'
})

# Generowanie sztucznej pojemności dla tych 20 schronów
df['Pojemnosc_Max'] = np.random.randint(50, 301, size=len(df))

# Wyciągnięcie tylko potrzebnych kolumn i zapis
df_clean = df[['ID_Schronu', 'Nazwa', 'Pojemnosc_Max', 'Szerokosc_Geo', 'Dlugosc_Geo']]
df_clean.to_csv('Dim_Schrony_Gotowe.csv', index=False)

print(f"Gotowe! Wygenerowano {len(df_clean)} schronów.")