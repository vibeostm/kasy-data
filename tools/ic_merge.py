import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "przegladarka" / "pkp_intercity.json"


def dump(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def h(s, n):
    return hashlib.sha256(s.encode()).hexdigest()[:n]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hashes")
    b = sub.add_parser("build")
    b.add_argument("--order", required=True, help="plik z listą hashy wierszy w kolejności z przeglądarki (spacje)")
    b.add_argument("--new", nargs="*", default=[], help="pliki JSON z nowymi wierszami")
    b.add_argument("--hash-all", required=True)
    b.add_argument("--miasta", type=int, required=True)
    args = ap.parse_args()

    cur = json.loads(TARGET.read_text(encoding="utf-8"))
    known = {h(dump(r), 8): r for r in cur["wiersze"]}

    if args.cmd == "hashes":
        print(" ".join(h(dump(r), 8) for r in cur["wiersze"]))
        return

    for f in args.new:
        for r in json.loads(pathlib.Path(f).read_text(encoding="utf-8")):
            known[h(dump(r), 8)] = r
    order = pathlib.Path(args.order).read_text(encoding="utf-8").split()
    missing = [x for x in order if x not in known]
    if missing:
        sys.exit("Brak wierszy dla hashy: " + " ".join(missing))
    rows = [known[x] for x in order]
    if h(dump(rows), 16) != args.hash_all:
        sys.exit("Suma kontrolna całości się nie zgadza – nic nie zapisano.")
    cur["wiersze"] = rows
    cur["miasta"] = args.miasta
    cur["pobrano"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    TARGET.write_text(json.dumps(cur, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK: {len(rows)} wierszy")


if __name__ == "__main__":
    main()
