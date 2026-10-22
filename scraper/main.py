import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys
import traceback

from sources import SOURCES

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANUAL = ROOT / "manual"
SCHEMA_VERSION = 1


def easter(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def holidays(year):
    e = easter(year)
    fixed = [(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 25), (12, 26)]
    if year >= 2025:
        fixed.append((12, 24))
    days = [dt.date(year, m, d) for m, d in fixed]
    days += [e, e + dt.timedelta(days=1), e + dt.timedelta(days=49), e + dt.timedelta(days=60)]
    return sorted(d.isoformat() for d in days)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def dedupe(kasy):
    seen = {}
    for k in kasy:
        base = k["id"]
        if base in seen:
            seen[base] += 1
            k["id"] = f"{base}-{seen[base]}"
        else:
            seen[base] = 1
    return kasy


def apply_manual(kasy):
    extra = load_json(MANUAL / "dodatkowe.json", [])
    for k in extra:
        k = dict(k)
        k.setdefault("tryb", "reczny")
        kasy = [x for x in kasy if x["id"] != k["id"]] + [k]
    overrides = load_json(MANUAL / "nadpisania.json", {})
    by_id = {k["id"]: k for k in kasy}
    missing = []
    for kid, patch in overrides.items():
        if kid.startswith("_"):
            continue
        if kid not in by_id:
            missing.append(kid)
            continue
        for key, val in patch.items():
            if key == "dni" and isinstance(val, dict):
                by_id[kid]["dni"] = {**by_id[kid]["dni"], **val}
            else:
                by_id[kid][key] = val
        by_id[kid]["nadpisane"] = True
    return kasy, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="uruchom tylko wybrane źródła")
    args = ap.parse_args()

    prev = load_json(DATA / "kasy.json", {})
    prev_kasy = prev.get("kasy", [])
    prev_status = prev.get("zrodla", {})
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    kasy = []
    status = {}
    for name, fn in SOURCES.items():
        if args.only and name not in args.only:
            kasy += [k for k in prev_kasy if k.get("przewoznik_id") == name and k.get("tryb") in ("auto", "przegladarka")]
            if name in prev_status:
                status[name] = prev_status[name]
            continue
        try:
            items = fn()
            if not items:
                raise RuntimeError("0 kas – możliwa zmiana strony")
            kasy += items
            status[name] = {"ok": True, "liczba": len(items), "pobrano": now}
            print(f"[OK]   {name}: {len(items)}")
        except Exception as e:
            old = [k for k in prev_kasy if k.get("przewoznik_id") == name and k.get("tryb") in ("auto", "przegladarka")]
            kasy += old
            last_ok = prev_status.get(name, {}).get("pobrano")
            status[name] = {"ok": False, "blad": f"{type(e).__name__}: {e}"[:300], "liczba": len(old), "pobrano": last_ok}
            print(f"[BŁĄD] {name}: {e} (zostawiam {len(old)} starych)", file=sys.stderr)
            traceback.print_exc()

    kasy = dedupe(kasy)
    kasy, missing = apply_manual(kasy)
    kasy.sort(key=lambda k: (k["przewoznik_id"], k["id"]))
    year = dt.date.today().year
    swieta = holidays(year) + holidays(year + 1)

    payload = {"swieta": swieta, "kasy": kasy}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

    if digest == prev.get("wersja") and not args.only:
        print("Bez zmian w danych.")
        changed = False
    else:
        changed = True
    out = {
        "schemat": SCHEMA_VERSION,
        "wersja": digest,
        "wygenerowano": now if changed else prev.get("wygenerowano", now),
        "liczba": len(kasy),
        "zrodla": status,
        "swieta": swieta,
        "kasy": kasy,
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "kasy.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "wersja.json").write_text(json.dumps({
        "schemat": SCHEMA_VERSION, "wersja": digest, "wygenerowano": out["wygenerowano"], "liczba": len(kasy),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if missing:
        print("Nadpisania dla nieistniejących ID: " + ", ".join(missing), file=sys.stderr)
    failed = [n for n, s in status.items() if not s["ok"]]
    if failed:
        print("Źródła z błędem: " + ", ".join(failed), file=sys.stderr)


if __name__ == "__main__":
    main()
