# Aktualizacja kas PKP Intercity

Strona IC odrzuca serwery GitHuba, więc kasy IC zbiera Claude w przeglądarce w aplikacji Claude na komputerze właściciela repo, ze zwykłej, publicznej wyszukiwarki IC. Tempo: 1 zapytanie na 1,5 s, ok. 103 miasta, ok. 3 minuty.

## Kroki

1. Sklonuj repo `vibeostm/kasy-data`.
2. Otwórz w przeglądarce w aplikacji Claude stronę:
   `https://www.intercity.pl/pl/site/dla-pasazera/kup-bilet/wyszukiwarka-kas-i-biletomatow.html`
3. Wykonaj na stronie całą zawartość `tools/ic_collect.js` (zwraca `"started"`).
4. Co ok. 40 s sprawdzaj `window.__icStatus()` aż `finished: true`. Jeśli `errors` nie jest puste albo `rows` spadło o więcej niż 20% względem `przegladarka/pkp_intercity.json` – przerwij i zgłoś to właścicielowi zamiast zapisywać.
5. Pobierz z przeglądarki `window.__ic.hashes.join(" ")` i zapisz do pliku `order.txt` (w katalogu tymczasowym).
6. `python3 tools/ic_merge.py hashes` pokazuje hashe wierszy już zapisanych. Hashe z `order.txt`, których tam nie ma, to nowe lub zmienione wiersze: pobierz je przez `window.__icRowsByHash([...])` i zapisz do pliku JSON (w razie dużej liczby – w kilku częściach).
7. `python3 tools/ic_merge.py build --order order.txt --new nowe*.json --hash-all <window.__ic.hashAll> --miasta <total>`
   Skrypt zapisze plik tylko, jeśli suma kontrolna całości zgadza się z przeglądarką.
8. Jeśli plik się zmienił: commit `przegladarka/pkp_intercity.json` na `main` i uruchom workflow „Aktualizacja bazy kas” z polem źródeł `pkp_intercity`.
