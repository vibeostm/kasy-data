import re
import time
import unicodedata

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 kasy-data (+https://github.com/vibeostm/kasy-data)"
DAYS = ("pn_pt", "sob", "nd_sw")

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "pl,en;q=0.5"})


def fetch(url, method="GET", data=None, headers=None, params=None, tries=3):
    last = None
    for attempt in range(tries):
        try:
            r = _session.request(method, url, data=data, headers=headers, params=params, timeout=60)
            r.raise_for_status()
            r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
            return r.text
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def slug(text):
    t = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def clean(text):
    text = (text or "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [l.strip(" |") for l in text.split("\n")]
    return "\n".join(l for l in lines if l)


def node_text(node):
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    return clean(node.get_text("\n"))


_PL = "a-ząćęłńóśźż"
_TIME = r"(\d{1,2})\s*[:.]\s*(\d{2})"
RANGE_RE = re.compile(rf"(?<![\d.]){_TIME}\s*(?:-|–|—|do)\s*{_TIME}(?![\d.]\d)")

_LABELS = [
    ("all", r"codziennie|7\s+dni\s+w\s+tygodniu|pon\w*\.?\s*[-–]\s*n(?:d|iedz\w*)\.?"),
    ("weekend", r"(?:w\s+)?weekend\w*(?:\s+i\s+święt\w*)?|sob\w*\.?\s*(?:,|-|–|i)\s*niedz\w*\.?(?:\s*(?:i|oraz)\s*(?:święt\w*|św\.?))?"),
    ("pn_pt", r"(?:w\s+)?dni\s+(?:robocze|powszednie)|pon\w*\.?\s*[-–]\s*(?:pt|pi\w+)\.?|pn\.?\s*[-–]\s*pt\.?"),
    ("sob", r"sob\w*\.?"),
    ("nd_sw", r"niedz\w*\.?(?:\s*(?:i|oraz)\s*(?:święt\w*|św\.?))?|święt\w*"),
    ("break", r"przerw\w*"),
    ("note", r"uwag\w*\s*!?"),
]
_LABEL_RE = re.compile(
    rf"(?<![{_PL}])(?:" + "|".join(f"(?P<{n}>{p})" for n, p in _LABELS) + r")",
    re.IGNORECASE,
)
_TARGETS = {"all": list(DAYS), "weekend": ["sob", "nd_sw"], "pn_pt": ["pn_pt"], "sob": ["sob"], "nd_sw": ["nd_sw"]}
_CLOSED_RE = re.compile(r"nieczynn|zamknię|brak\s+kasy|brak\s+dostępnej\s+kasy", re.IGNORECASE)
_TRIVIAL_RE = re.compile(r"^(?:godziny\s+otwarcia|w\s+godzinach|godz\.?|brak|czynn[ea]|od|w|i|oraz|-|–|:|\(|\)|\.|,|;|\s)*$", re.IGNORECASE)
_CLOSED_WORD_RE = re.compile(r"(?:kasa\s+)?(?:nieczynn\w*|zamknięt\w*)", re.IGNORECASE)


def norm_time(h, m):
    h, m = int(h), int(m)
    if h > 24 or m > 59:
        return None
    return f"{h:02d}:{m:02d}"


def find_ranges(text):
    out = []
    for m in RANGE_RE.finditer(text):
        a, b = norm_time(m.group(1), m.group(2)), norm_time(m.group(3), m.group(4))
        if a and b:
            out.append(f"{a}-{b}")
    return out


def parse_schedule(text, default=None, start_mode="open"):
    text = clean(text).replace("–", "-").replace("—", "-")
    segments = []
    pos = 0
    pending = None
    for m in _LABEL_RE.finditer(text):
        segments.append((pending, text[pos:m.start()]))
        pending = m.lastgroup
        pos = m.end()
    segments.append((pending, text[pos:]))

    open_r = {d: set() for d in DAYS}
    break_r = {d: set() for d in DAYS}
    closed = set()
    unknown_open = []
    break_all = set()
    notes = []
    break_count = sum(1 for l, _ in segments if l == "break")
    target = list(default) if default else None
    mode = start_mode
    day_labels_seen = 0
    label_since_break = False
    for label, seg in segments:
        if label in _TARGETS:
            target = _TARGETS[label]
            day_labels_seen += 1
            if mode == "break" and (start_mode == "break" or default):
                label_since_break = True
            else:
                mode = "open"
        elif label == "break":
            mode = "break"
            label_since_break = False
        elif label == "note":
            mode = "note"
        seg = seg.strip(" :\n,;")
        if not seg:
            continue
        if mode == "note":
            n = clean(seg)
            if n and not _TRIVIAL_RE.match(n):
                notes.append(n)
            continue
        ranges = find_ranges(seg)
        leftover = RANGE_RE.sub(" ", seg)
        if mode == "open":
            if ranges:
                if target:
                    for d in target:
                        open_r[d].update(ranges)
                else:
                    unknown_open.extend(ranges)
            elif _CLOSED_RE.search(seg):
                for d in target or []:
                    closed.add(d)
                if not target:
                    unknown_open.append("nieczynna")
        else:
            if label_since_break and target:
                dest = target
            elif start_mode == "break" or not target:
                dest = None
            elif break_count == 1 and day_labels_seen > 1:
                dest = None
            else:
                dest = target
            if dest:
                for d in dest:
                    break_r[d].update(ranges)
            else:
                break_all.update(ranges)
        rest = clean(leftover)
        core = _CLOSED_WORD_RE.sub(" ", rest)
        if rest and not _TRIVIAL_RE.match(core) and len(re.sub(rf"[^{_PL}]", "", core.lower())) >= 6:
            notes.append(rest)

    dni = {}
    for d in DAYS:
        if open_r[d]:
            dni[d] = {"godziny": sorted(open_r[d]), "przerwy": sorted(break_r[d] | break_all)}
        elif d in closed:
            dni[d] = "nieczynna"
        else:
            dni[d] = None
    pewne = all(dni[d] is not None for d in DAYS) and not unknown_open
    przerwy = {d: sorted(break_r[d] | break_all) for d in DAYS}
    return {"dni": dni, "uwagi": notes, "pewne": pewne, "bez_dnia": unknown_open, "przerwy": przerwy}


def merge_columns(parts):
    dni = {}
    uwagi = []
    for day, res in parts:
        dni[day] = res["dni"][day]
        for n in res["uwagi"]:
            if n not in uwagi:
                uwagi.append(n)
    return {"dni": dni, "uwagi": uwagi, "pewne": all(dni[d] is not None for d in DAYS)}


def make_kasa(carrier_id, carrier_name, nazwa, parsed, adres=None, miejscowosc=None, surowe="", zrodlo="", typ="kasa", suffix=None):
    kid = f"{carrier_id}:{slug(nazwa)}" + (f"-{slug(suffix)}" if suffix else "")
    return {
        "id": kid,
        "przewoznik_id": carrier_id,
        "przewoznik": carrier_name,
        "typ": typ,
        "nazwa": nazwa,
        "miejscowosc": miejscowosc or nazwa,
        "adres": adres,
        "dni": parsed["dni"] if parsed else {d: None for d in DAYS},
        "wyjatki": [],
        "uwagi": parsed["uwagi"] if parsed else [],
        "pewne": bool(parsed and parsed["pewne"]),
        "surowe": clean(surowe),
        "zrodlo": zrodlo,
        "tryb": "auto",
    }
