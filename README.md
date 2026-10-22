# kasy-data

Baza godzin otwarcia kolejowych kas biletowych w Polsce, zbierana automatycznie z oficjalnych stron przewoźników.

## Pliki dla aplikacji

| Plik | Do czego |
|---|---|
| `data/wersja.json` | mały plik: `wersja` (hash danych), data, liczba wpisów; aplikacja sprawdza go przed pobraniem całej bazy |
| `data/kasy.json` | pełna baza |

Adresy:

```
https://raw.githubusercontent.com/vibeostm/kasy-data/main/data/wersja.json
https://raw.githubusercontent.com/vibeostm/kasy-data/main/data/kasy.json
```

## Format `kasy.json`

```json
{
 "schemat": 1,
 "wersja": "a1b2c3d4e5f60718",
 "wygenerowano": "2026-10-25T22:20:00+00:00",
 "zrodla": {"polregio": {"ok": true, "liczba": 106, "pobrano": "..."}},
 "swieta": ["2026-01-01", "..."],
 "kasy": [
  {
   "id": "polregio:bialogard",
   "przewoznik_id": "polregio",
   "przewoznik": "POLREGIO",
   "typ": "kasa",
   "nazwa": "Białogard",
   "miejscowosc": "Białogard",
   "adres": "ul. Borzymowskiego 1, 78-200 Białogard",
   "dni": {
    "pn_pt": {"godziny": ["06:00-17:15"], "przerwy": ["10:40-11:00", "12:50-13:05"]},
    "sob": "nieczynna",
    "nd_sw": null
   },
   "wyjatki": [],
   "uwagi": ["w dniach 19-21.10.2026 kasa nieczynna"],
   "pewne": false,
   "surowe": "tekst ze strony przewoźnika",
   "zrodlo": "https://...",
   "tryb": "auto"
  }
 ]
}
```

- `dni.<dzień>`: obiekt z godzinami, `"nieczynna"` albo `null` = nie udało się odczytać (pokaż `surowe`).
- `nd_sw` obowiązuje w niedziele i w dni z listy `swieta`.
- `pewne: false` = parser nie był pewny przynajmniej jednego dnia.
- `uwagi` zawierają m.in. ogłoszenia o czasowym zamknięciu – parser ich nie interpretuje.
- `typ`: `kasa`, `nieczynna`, `brak_kasy`, `kasa_innego_przewoznika`, `biuro_obslugi`, `punkt_sprzedazy`, `biuro_podrozy`.
- Kasy IC mają dodatkowo: `operator` (`PKP Intercity` / `kasa agencyjna` / `Biuro podróży`), `sprzedaz_miedzynarodowa`, `platnosc_karta`, `pobrano`.
- `wyjatki` (tylko z ręcznych nadpisań): `{"od","do","dni":"nieczynna"}` albo `{"od","do","godziny":[..],"przerwy":[..]}`.

## Źródła

| Przewoźnik | Tryb |
|---|---|
| POLREGIO | auto |
| Koleje Mazowieckie | auto |
| Koleje Wielkopolskie | auto |
| Koleje Śląskie | auto |
| Koleje Dolnośląskie | auto |
| ŁKA | auto |
| Koleje Małopolskie | auto |
| SKM Trójmiasto | auto |
| PKP Intercity | przeglądarka – zbierane w przeglądarce w aplikacji Claude (`tools/IC_AKTUALIZACJA.md`), plik `przegladarka/pkp_intercity.json` |

## Aktualizacja

- Automatycznie co tydzień w nocy z soboty na niedzielę (GitHub Actions).
- Ręcznie: zakładka **Actions** → **Aktualizacja bazy kas** → **Run workflow**.
- Commit powstaje tylko, gdy dane się zmieniły.
- Jeśli źródło padnie, zostają jego ostatnie poprawne dane, a w `zrodla` jest `"ok": false`.

## Ręczne poprawki

- `manual/nadpisania.json` – zmiana godzin lub dodanie wyjątków dla istniejącej kasy (po `id`).
- `manual/dodatkowe.json` – kasy spoza scraperów (pełne obiekty w formacie jak wyżej).

Uruchomienie lokalnie:

```
pip install -r requirements.txt
python scraper/main.py
python scraper/main.py --only polregio skm
```
