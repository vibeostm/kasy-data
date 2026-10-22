import re
import time

from bs4 import BeautifulSoup

from common import DAYS, clean, fetch, make_kasa, merge_columns, node_text, parse_schedule

POSTCODE_RE = re.compile(r"\b\d{2}-\d{3}\b")


def soup(html):
    return BeautifulSoup(html, "lxml")


def city_from_address(adres):
    parts = [p.strip() for p in re.split(r"[,\n|]", adres) if p.strip()]
    for p in reversed(parts):
        c = POSTCODE_RE.sub("", p).strip()
        if c and not re.match(r"(?i)(ul\.|al\.|pl\.|plac)", c):
            return c
    return None


def polregio():
    url = "https://polregio.pl/pl/dla-podroznych/gdzie-kupic-bilet/kasy-biletowe/"
    html = fetch(
        "https://polregio.pl/umbraco/Surface/PolRegioTicketOffices/LoadMoreTicketOfficesBoxes",
        method="POST",
        data={"officeName": "", "skipCount": "0", "currentCulture": "pl", "displayCount": "500", "currentPageId": "1469"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    s = soup(f"<table>{html}</table>")
    out = []
    for tr in s.select("tr.js-list-item"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        nazwa = clean(tds[0].get_text(" "))
        adres_txt = node_text(tds[1])
        cols = [node_text(td) for td in tds[2:5]]
        parsed = merge_columns([(d, parse_schedule(t, default=[d])) for d, t in zip(DAYS, cols)])
        adres = None
        if len(adres_txt) < 120 and "zakup" not in adres_txt.lower():
            adres = adres_txt.replace("\n", ", ")
        elif adres_txt:
            parsed["uwagi"].insert(0, adres_txt.replace("\n", " "))
        link = tds[0].find("a")
        typ = "kasa"
        if not any(isinstance(parsed["dni"][d], dict) for d in DAYS):
            typ = "nieczynna"
            parsed["dni"] = {d: "nieczynna" for d in DAYS}
            parsed["pewne"] = True
        out.append(make_kasa(
            "polregio", "POLREGIO", nazwa, parsed, adres=adres,
            surowe=f"Pn-Pt: {cols[0]}\nSob: {cols[1]}\nNd i św.: {cols[2]}",
            zrodlo=link["href"].replace("http://", "https://") if link and link.get("href") else url,
            typ=typ,
        ))
    return out


def koleje_mazowieckie():
    base = "https://www.mazowieckie.com.pl/pl/strefa-podroznych/wyszukiwarka-kas-biletomatow"
    out = []
    for page in range(0, 60):
        s = soup(fetch(base, params={"page": page}))
        rows = s.select("table tbody tr")
        if not rows:
            break
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            nazwa = clean(tds[0].get_text(" "))
            adres = clean(tds[1].get_text(" "))
            cechy = clean(tds[2].get_text(" "))
            godz = node_text(tds[3])
            has_kasa = "kasa" in cechy.lower() and "brak kasy" not in adres.lower()
            parsed = parse_schedule(godz) if has_kasa else None
            link = tds[0].find("a")
            out.append(make_kasa(
                "koleje_mazowieckie", "KOLEJE MAZOWIECKIE", nazwa, parsed,
                adres=None if not has_kasa else adres,
                surowe=godz, typ="kasa" if has_kasa else "brak_kasy",
                zrodlo="https://www.mazowieckie.com.pl" + link["href"] if link and link.get("href", "").startswith("/") else base,
            ))
        nxt = s.select_one(f'a[href="?page={page + 1}"]')
        if not nxt:
            break
        time.sleep(0.7)
    return out


def koleje_wielkopolskie():
    url = "https://koleje-wielkopolskie.com.pl/dla-pasazera/pociag/kasy-biletowe/"
    s = soup(fetch(url))
    out = []
    for item in s.select(".accordion__item"):
        title = item.select_one(".accordion__title")
        body = item.select_one(".accordion__body")
        if not title or not body:
            continue
        nazwa = clean(title.get_text(" "))
        text = node_text(body)
        adres = None
        lines = []
        want_addr = False
        for line in text.split("\n"):
            m = re.match(r"(?i)adres\s*:\s*(.*)", line)
            if m:
                adres = m.group(1).strip() or None
                want_addr = not adres
            elif want_addr:
                adres = line.strip()
                want_addr = False
            elif not re.match(r"(?i)godziny otwarcia\s*:?$", line):
                lines.append(line)
        if not any(re.search(r"\d", l) or "nieczynn" in l.lower() for l in lines):
            continue
        body_txt = "\n".join(lines)
        parsed = parse_schedule(body_txt)
        out.append(make_kasa(
            "koleje_wielkopolskie", "KOLEJE WIELKOPOLSKIE", nazwa.title() if nazwa.isupper() else nazwa, parsed,
            adres=adres, miejscowosc=city_from_address(adres) if adres else None, surowe=body_txt, zrodlo=url,
        ))
    return out


def koleje_slaskie():
    url = "https://www.kolejeslaskie.pl/kup_bilet/na-dworcu/"
    s = soup(fetch(url))
    out = []
    for tr in s.select("#ksl-kasy-table tbody tr"):
        name_td = tr.find("td", attrs={"data-station-name": True})
        if not name_td:
            continue
        nazwa = name_td["data-station-name"].strip()
        g_td = tr.find("td", attrs={"data-label": "Godziny otwarcia kasy"})
        p_td = tr.find("td", attrs={"data-label": "Przerwy"})
        g = node_text(g_td)
        p = node_text(p_td)
        low = g.lower()
        if "brak dostępnej kasy" in low:
            out.append(make_kasa("koleje_slaskie", "KOLEJE ŚLĄSKIE", nazwa, None, surowe=g, zrodlo=url, typ="brak_kasy"))
            continue
        if "innego przewoźnika" in low:
            out.append(make_kasa("koleje_slaskie", "KOLEJE ŚLĄSKIE", nazwa, None, surowe=g, zrodlo=url, typ="kasa_innego_przewoznika"))
            continue
        parsed = parse_schedule(g)
        if p:
            br = parse_schedule(p, start_mode="break")
            for d in DAYS:
                if isinstance(parsed["dni"][d], dict):
                    parsed["dni"][d]["przerwy"] = sorted(set(parsed["dni"][d]["przerwy"]) | set(br["przerwy"][d]))
            parsed["uwagi"] += [n for n in br["uwagi"] if n not in parsed["uwagi"]]
        out.append(make_kasa(
            "koleje_slaskie", "KOLEJE ŚLĄSKIE", nazwa, parsed,
            surowe=g + (f"\nPrzerwy: {p}" if p else ""), zrodlo=url,
        ))
    return out


def koleje_dolnoslaskie():
    url = "https://kolejedolnoslaskie.pl/informacje-o-kanalach-sprzedazy/kasy-biletowe/"
    s = soup(fetch(url))
    out = []
    for table in s.find_all("table"):
        head = [clean(c.get_text(" ")).lower() for c in table.find_all("tr")[0].find_all(["td", "th"])] if table.find("tr") else []
        if not head or "adres" not in head[0]:
            continue
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            adres = clean(tds[0].get_text(" ")).replace(" ,", ",")
            g = node_text(tds[1])
            p = node_text(tds[2]) if len(tds) > 2 else ""
            miasto = city_from_address(adres) or adres
            prev = table.find_previous(["h2", "h3", "h4", "p", "strong"])
            opis = clean(prev.get_text(" ")) if prev else ""
            suffix = opis if re.search(r"(?i)kasa|biuro|hol", opis) and len(opis) < 120 else None
            parsed = parse_schedule(g)
            if p and p.strip("- "):
                br = parse_schedule(p, start_mode="break")
                for d in DAYS:
                    if isinstance(parsed["dni"][d], dict):
                        parsed["dni"][d]["przerwy"] = sorted(set(parsed["dni"][d]["przerwy"]) | set(br["przerwy"][d]))
            nazwa = miasto + (f" ({suffix})" if suffix else "")
            out.append(make_kasa(
                "koleje_dolnoslaskie", "KOLEJE DOLNOŚLĄSKIE", nazwa, parsed, adres=adres, miejscowosc=miasto,
                surowe=g + (f"\nPrzerwy: {p}" if p else ""), zrodlo=url,
                typ="biuro_obslugi" if suffix and "biuro" in suffix.lower() else "kasa",
            ))
    return out


def lka():
    url = "https://lka.lodzkie.pl/kasy-biletowe/"
    s = soup(fetch(url))
    lines = node_text(s.find("main") or s.body).split("\n")
    out = []
    starts = [i for i, l in enumerate(lines) if re.match(r"^Dworzec\s+\S", l)]
    for n, i in enumerate(starts):
        block = lines[i:starts[n + 1] if n + 1 < len(starts) else len(lines)]
        nazwa = re.sub(r"^Dworzec\s+", "", block[0]).strip()
        try:
            gi = next(k for k, l in enumerate(block) if l.lower().startswith("godziny otwarcia"))
        except StopIteration:
            continue
        end = next((k for k, l in enumerate(block) if k > gi and re.match(r"(?i)obsługa\s*:?", l)), len(block))
        lok = [l for l in block[1:gi] if not re.match(r"(?i)lokalizacja\s*:?$", l)]
        adres = next((l for l in lok if re.match(r"(?i)(ul\.|al\.|plac|pl\.)", l)), None)
        g = "\n".join(block[gi + 1:end])
        parsed = parse_schedule(g)
        parsed["uwagi"] = [l for l in lok if l != adres] + parsed["uwagi"]
        out.append(make_kasa("lka", "ŁÓDZKA KOLEJ AGLOMERACYJNA", nazwa, parsed, adres=adres, surowe=g, zrodlo=url))
    return out


def koleje_malopolskie():
    url = "https://www.kolejemalopolskie.com.pl/pl/dla-pasazera/gdzie-kupic-bilet-kolejowy"
    s = soup(fetch(url))
    lines = node_text(s.find("main") or s.body).split("\n")
    out = []
    starts = [i for i, l in enumerate(lines) if re.match(r"(?i)^na stacji\s*:?$", l)]
    for n, i in enumerate(starts):
        stop = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = lines[i:stop]
        if len(block) < 3:
            continue
        nazwa = block[1].strip()
        opis = lines[i - 1] if i > 0 else ""
        try:
            gi = next(k for k, l in enumerate(block) if l.lower().startswith("godziny otwarcia"))
        except StopIteration:
            continue
        end = next((k for k, l in enumerate(block) if k > gi and re.match(r"(?i)(płatność|regulamin|w kasach|w kasie|w punkcie)", l)), len(block))
        lok = [l for l in block[2:gi]]
        g = "\n".join(block[gi + 1:end])
        parsed = parse_schedule(g)
        parsed["uwagi"] = [l.strip("()") for l in lok] + parsed["uwagi"]
        typ = "biuro_obslugi" if "centrum obsługi" in opis.lower() else ("punkt_sprzedazy" if "punkt" in opis.lower() else "kasa")
        out.append(make_kasa("koleje_malopolskie", "KOLEJE MAŁOPOLSKIE", nazwa, parsed, surowe=g, zrodlo=url, typ=typ))
    return out


def skm():
    url = "https://www.skm.pkp.pl/dla-pasazera/taryfy-i-przepisy/wykaz-kas-i-automatow"
    s = soup(fetch(url))
    sel = s.find("select", attrs={"name": "tx_simskmapi_sales[station]"})
    options = [(o["value"], clean(o.get_text(" "))) for o in sel.find_all("option")] if sel else []
    out = []
    errors = 0
    for sid, sname in options:
        page = soup(fetch(url, params={"tx_simskmapi_sales[action]": "list", "tx_simskmapi_sales[station]": sid}))
        chosen = page.select_one('select[name="tx_simskmapi_sales[station]"] option[selected]')
        if chosen and chosen.get("value") != sid:
            errors += 1
            continue
        head = page.find(lambda t: t.name in ("h2", "h3") and "kasy biletowe" in t.get_text(" ").lower())
        if not head:
            time.sleep(0.5)
            continue
        lok = None
        n = 0
        for el in head.find_all_next():
            if el is not head and el.name == "h2":
                break
            if el.name == "h3":
                lok = clean(el.get_text(" ")).replace("Lokalizacja:", "").strip()
            if el.name == "table":
                rows = el.find_all("tr")
                if len(rows) < 2:
                    continue
                vals = [node_text(c) for c in rows[1].find_all(["td", "th"])]
                if len(vals) < 3 or not any(re.search(r"\d|nieczynn", v.lower()) for v in vals):
                    continue
                n += 1
                parsed = merge_columns([(d, parse_schedule(v, default=[d])) for d, v in zip(DAYS, vals)])
                if lok:
                    parsed["uwagi"].insert(0, lok)
                nazwa = sname.title() if sname.isupper() else sname
                out.append(make_kasa(
                    "skm", "SZYBKA KOLEJ MIEJSKA W TRÓJMIEŚCIE", nazwa, parsed,
                    surowe=f"Dni robocze: {vals[0]}\nSoboty: {vals[1]}\nNd i św.: {vals[2]}",
                    zrodlo=url, suffix=str(n) if n > 1 else None,
                ))
        time.sleep(0.5)
    if options and errors == len(options):
        raise RuntimeError("SKM: serwer zwraca zawsze tę samą stację")
    return out


SOURCES = {
    "polregio": polregio,
    "koleje_mazowieckie": koleje_mazowieckie,
    "koleje_wielkopolskie": koleje_wielkopolskie,
    "koleje_slaskie": koleje_slaskie,
    "koleje_dolnoslaskie": koleje_dolnoslaskie,
    "lka": lka,
    "koleje_malopolskie": koleje_malopolskie,
    "skm": skm,
}
