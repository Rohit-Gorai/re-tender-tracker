#!/usr/bin/env python3
"""
India Renewable Energy Tender Tracker
=====================================
Free, dependency-light daily tracker for renewable energy tenders published by
Indian central PSUs and agencies.

Outputs (in ./data):
    tenders.csv             master table, all tenders ever seen
    tenders_renewable.csv   filtered to RE-relevant tenders only
    tenders.xlsx            same, formatted, for Excel / Power BI
    changes.csv             append-only log of new / revised / closed tenders
    run_log.csv             per-source health log (rows fetched, errors)

Usage:
    python tender_tracker.py                 # normal daily run
    python tender_tracker.py --inspect URL   # dump tables/headers on a page
    python tender_tracker.py --selftest      # test the enrichment logic
    python tender_tracker.py --source SECI   # run one source only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import time
import traceback
from datetime import datetime, date, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).date()
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

# ---------------------------------------------------------------------------
# SOURCE CONFIGURATION
# ---------------------------------------------------------------------------
# parser = "table"  -> find the HTML <table> whose header row contains all of
#                      `header_must_contain`, then map columns by header text.
# parser = "blocks" -> split the page text on `block_split` and pull fields
#                      out with regexes.
#
# To add a source: run  python tender_tracker.py --inspect <url>
# and copy the header names it prints into a new config block.
# ---------------------------------------------------------------------------

SOURCES = [
    {
        "key": "SECI",
        "authority": "SECI",
        "url": "https://www.seci.co.in/tenders",
        "parser": "table",
        "header_must_contain": ["tender title", "bid submission date"],
        "map": {
            "ref": "tender ref no",
            "title": "tender title",
            "published": "publication date",
            "due": "bid submission date",
        },
        "enabled": True,
    },
    {
        "key": "NHPC",
        "authority": "NHPC",
        "url": "https://www.nhpcindia.com/welcome/tender",
        "parser": "blocks",
        "block_split": r"Tender Title\s*:",
        "field_regex": {
            "title": r"^\s*(.+?)(?:\n|NIT No\.|Location\s*:|View More|$)",
            "ref": r"NIT No\.\s*:\s*(.+?)(?:\n|Location\s*:|View More|$)",
            "state_hint": r"Location\s*:\s*(.+?)(?:\n|View More|$)",
        },
        "enabled": True,
    },
    {
        "key": "SJVN",
        "authority": "SJVN",
        "url": "https://sjvn.nic.in/tender-notice",
        "parser": "table",
        "header_must_contain": ["title"],
        "map": {"ref": "reference", "title": "title", "published": "published", "due": "closing"},
        "enabled": False,  # turn on after --inspect confirms the headers
    },
    {
        "key": "IREDA",
        "authority": "IREDA",
        "url": "https://www.ireda.in/tenders",
        "parser": "table",
        "header_must_contain": ["title"],
        "map": {"ref": "reference", "title": "title", "published": "published", "due": "last date"},
        "enabled": False,
    },
    {
        "key": "NTPC_GREEN",
        "authority": "NTPC Green Energy",
        "url": "https://www.ntpcgreenenergy.co.in/tenders",
        "parser": "table",
        "header_must_contain": ["title"],
        "map": {"ref": "reference", "title": "title", "published": "published", "due": "closing"},
        "enabled": False,
    },
]

# ---------------------------------------------------------------------------
# ENRICHMENT
# ---------------------------------------------------------------------------

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar", "A&N Islands", "Chandigarh", "Dadra and Nagar Haveli",
    "Daman and Diu", "Delhi", "New Delhi", "Jammu and Kashmir", "J&K", "Ladakh",
    "Lakshadweep", "Puducherry",
]
STATE_ALIASES = {
    "A&N Islands": "Andaman and Nicobar",
    "Andaman and Nicobar": "Andaman and Nicobar",
    "J&K": "Jammu and Kashmir",
    "New Delhi": "Delhi",
    "Orissa": "Odisha",
    "Pondicherry": "Puducherry",
}

# ordered: first match wins as the primary technology
TECH_RULES = [
    ("Green Hydrogen / Derivatives", r"green hydrogen|green ammonia|green methanol|rfnbo|electrolys"),
    ("Transmission / Evacuation",     r"transmission line|evacuation of power|power evacuation|"
                                      r"\bsubstation\b|pooling station|\bists\b transmission"),
    ("Pumped Storage",               r"pumped storage|\bpsp\b"),
    ("Hydro",                        r"\bhydro\b|hydroelectric|hydro power|micro hydro|small hydro"),
    ("Solar + Storage",              r"(solar|spv|photovoltaic).{0,60}(bess|battery|storage)|"
                                     r"(bess|battery|storage).{0,60}(solar|spv|photovoltaic)"),
    ("Wind-Solar Hybrid",            r"hybrid"),
    ("Energy Storage (BESS)",        r"\bbess\b|battery energy storage|standalone energy storage|"
                                     r"energy storage system"),
    ("Rooftop Solar",                r"rooftop|roof top|\brtspv\b|resco"),
    ("Floating Solar",               r"floating solar|\bfspv\b"),
    ("Solar",                        r"\bsolar\b|\bspv\b|photovoltaic|solar park"),
    ("Wind",                         r"\bwind\b|wind power|offshore wind"),
    ("Geothermal",                   r"geothermal"),
    ("Biomass / WtE",                r"biomass|waste to energy|bio-cng|biogas"),
    ("Round-the-Clock / CfD / Trading", r"round the clock|\brtc\b|\bcfd\b|peak supply|"
                                        r"power procurement|power trading|off-?taker"),
]

RE_SIGNAL = re.compile(
    r"solar|wind|hydro|renewable|\bre\b|bess|battery|storage|green hydrogen|green ammonia|"
    r"methanol|rfnbo|geothermal|biomass|photovoltaic|\bspv\b|rooftop|\bists\b|\brfs\b|"
    r"power project|power plant|electrolys|pumped storage|\bmw\b|\bmwh\b|\bgw\b|"
    r"evacuation|power procurement|discom|\bppa\b|\bcfd\b|energy",
    re.I,
)

NOISE_SIGNAL = re.compile(
    r"canteen|catering|housekeeping|horticulture|sanitation|security service|manpower|"
    r"stationery|furniture|uniform|liveries|vehicle hire|hiring of (car|taxi|bus)|"
    r"medical|dispensary|hospital|ambulance|guest house|colony|quarters|barrack|"
    r"painting|white ?wash|plumbing|carpentry|road repair|bituminous|park\b|plantation|"
    r"sap erp|hrms|\berp\b|printer|laptop|desktop|networking switch|\bups\b|"
    r"air condition|\bac\b unit|insurance polic|recruitment|internship|"
    r"audit|advertis|calendar|diary|souvenir|sports|training programme|"
    r"renting out|office space|tenant",
    re.I,
)

TENDER_TYPE_RULES = [
    ("RfS", r"\brfs\b|request for selection"),
    ("RfP", r"\brfp\b|request for proposal"),
    ("EOI", r"\beoi\b|expression of interest"),
    ("RfQ", r"\brfq\b|request for quotation"),
    ("NIT", r"\bnit\b|notice inviting tender"),
]

CAP_TOKEN = re.compile(
    r"(\d{1,4}(?:,\d{3})*(?:\.\d+)?)\s*(GWh|GWp|GW|MWh|MWp|MWac|MWdc|MW|kWp|kWh|kWac|kW)\b",
    re.I,
)


def extract_capacity_mw(text: str):
    """Return (capacity_mw, raw_match). Prefers MW over MWh over kW."""
    if not text:
        return None, ""
    matches = CAP_TOKEN.findall(text)
    if not matches:
        return None, ""
    buckets = {"mw": [], "gw": [], "kw": [], "mwh": [], "gwh": [], "kwh": []}
    for value, unit in matches:
        try:
            num = float(value.replace(",", ""))
        except ValueError:
            continue
        u = unit.lower()
        if u in ("mw", "mwp", "mwac", "mwdc"):
            buckets["mw"].append((num, f"{value} {unit}"))
        elif u in ("gw", "gwp"):
            buckets["gw"].append((num, f"{value} {unit}"))
        elif u in ("kw", "kwp", "kwac"):
            buckets["kw"].append((num, f"{value} {unit}"))
        elif u == "mwh":
            buckets["mwh"].append((num, f"{value} {unit}"))
        elif u == "gwh":
            buckets["gwh"].append((num, f"{value} {unit}"))
        elif u == "kwh":
            buckets["kwh"].append((num, f"{value} {unit}"))

    for key, factor in (("mw", 1.0), ("gw", 1000.0), ("kw", 0.001)):
        if buckets[key]:
            num, raw = buckets[key][0]
            return round(num * factor, 3), raw
    # energy-only tenders: report the energy figure but flag it in raw
    for key, factor in (("mwh", 1.0), ("gwh", 1000.0), ("kwh", 0.001)):
        if buckets[key]:
            num, raw = buckets[key][0]
            return None, raw + " (energy, not power)"
    return None, ""


def detect_technology(text: str) -> str:
    t = text or ""
    hits = [name for name, pat in TECH_RULES if re.search(pat, t, re.I)]
    if not hits:
        return "Unclassified"
    return hits[0]


def detect_state(*texts) -> str:
    blob = " ".join(x for x in texts if x)
    found = []
    for st in STATES:
        if re.search(r"\b" + re.escape(st).replace(r"\ ", r"\s+") + r"\b", blob, re.I):
            found.append(STATE_ALIASES.get(st, st))
    if not found:
        return ""
    # prefer a real state over Delhi (head-office noise)
    non_delhi = [s for s in found if s != "Delhi"]
    return (non_delhi or found)[0]


def detect_tender_type(text: str) -> str:
    for name, pat in TENDER_TYPE_RULES:
        if re.search(pat, text or "", re.I):
            return name
    return "Tender"


def is_renewable(text: str) -> bool:
    t = text or ""
    re_hit = bool(RE_SIGNAL.search(t))
    noise_hit = bool(NOISE_SIGNAL.search(t))
    strong_re = bool(re.search(
        r"solar|wind|\bbess\b|battery energy storage|green hydrogen|green ammonia|"
        r"photovoltaic|\bspv\b|renewable|pumped storage|hydroelectric|geothermal|"
        r"\brfs\b|\bists\b", t, re.I))
    if strong_re:
        return True
    if noise_hit:
        return False
    return re_hit


# ---------------------------------------------------------------------------
# DATE HANDLING
# ---------------------------------------------------------------------------

DATE_PATTERNS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%d-%B-%Y",
    "%d %B %Y", "%Y-%m-%d", "%d/%m/%y", "%b %d, %Y",
]


def parse_date(raw):
    if not raw:
        return None
    s = re.sub(r"\s+", " ", str(raw)).strip()
    s = re.split(r"\s+\d{1,2}:\d{2}", s)[0].strip()  # drop trailing time
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        d, mth, y = m.groups()
        y = int(y)
        y = y + 2000 if y < 100 else y
        try:
            return date(y, int(mth), int(d))
        except ValueError:
            return None
    return None


def derive_status(due):
    if due is None:
        return "Unknown"
    delta = (due - TODAY).days
    if delta < 0:
        return "Closed"
    if delta <= 7:
        return "Closing Soon"
    if delta <= 30:
        return "Open"
    return "Open"


# ---------------------------------------------------------------------------
# FETCH + PARSE
# ---------------------------------------------------------------------------

def fetch(url, retries=3, timeout=45):
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, verify=True)
            r.raise_for_status()
            return r.text
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last}")


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def _key(s):
    return _norm(s).lower().rstrip(".:").strip()


def pick_table(soup, must_contain):
    """Return (table, header_list) for the table whose header row matches."""
    best = None
    for table in soup.find_all("table"):
        header_cells = []
        head = table.find("thead")
        if head and head.find("tr"):
            header_cells = [_key(td.get_text(" ")) for td in head.find("tr").find_all(["th", "td"])]
        if not header_cells:
            first = table.find("tr")
            if first:
                header_cells = [_key(td.get_text(" ")) for td in first.find_all(["th", "td"])]
        if not header_cells:
            continue
        joined = " | ".join(header_cells)
        if all(any(m in h for h in header_cells) or m in joined for m in must_contain):
            best = (table, header_cells)
            break
    return best if best else (None, None)


def parse_table_source(html, cfg):
    soup = BeautifulSoup(html, "lxml")
    table, headers = pick_table(soup, [m.lower() for m in cfg["header_must_contain"]])
    if table is None:
        raise RuntimeError(
            f"[{cfg['key']}] no table matched {cfg['header_must_contain']}. "
            f"Run --inspect {cfg['url']} to see what changed."
        )

    def col_index(wanted):
        wanted = wanted.lower()
        for i, h in enumerate(headers):
            if wanted in h:
                return i
        return None

    idx = {field: col_index(label) for field, label in cfg["map"].items()}

    rows = []
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        texts = [_norm(c.get_text(" ")) for c in cells]
        if texts and all(_key(t) in headers for t in texts if t):
            continue  # header row repeated
        link = ""
        for c in cells:
            a = c.find("a", href=True)
            if a:
                link = urljoin(cfg["url"], a["href"])
                break

        def get(field):
            i = idx.get(field)
            if i is None or i >= len(texts):
                return ""
            return texts[i]

        title = get("title")
        if not title:
            continue
        rows.append({
            "ref": get("ref") or "",
            "title": title,
            "published": get("published") or "",
            "due": get("due") or "",
            "link": link or cfg["url"],
            "extra": " ".join(texts),
        })
    return rows


def parse_blocks_source(html, cfg):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"\n{2,}", "\n", text)
    chunks = re.split(cfg["block_split"], text)[1:]
    fr = cfg["field_regex"]
    rows = []
    for chunk in chunks:
        chunk = chunk.strip()[:1200]

        def grab(name):
            pat = fr.get(name)
            if not pat:
                return ""
            m = re.search(pat, chunk, re.I | re.M | re.S)
            return _norm(m.group(1)) if m else ""

        title = grab("title")
        if not title or len(title) < 8:
            continue
        rows.append({
            "ref": grab("ref"),
            "title": title,
            "published": grab("published"),
            "due": grab("due"),
            "link": cfg["url"],
            "extra": grab("state_hint"),
        })
    return rows


PARSERS = {"table": parse_table_source, "blocks": parse_blocks_source}


# ---------------------------------------------------------------------------
# RECORD BUILD
# ---------------------------------------------------------------------------

FIELDNAMES = [
    "TenderKey", "Authority", "Project Name", "Technology", "Capacity MW",
    "State", "Due Date", "Status", "Source URL",
    "Tender Ref No", "Tender Type", "Published Date", "Days Left",
    "Capacity Raw", "Is Renewable", "First Seen", "Last Seen", "Notes",
    "Winner", "Bids Received", "Award Status", "Award URL", "Award Date",
    "Award Source", "Award Headline",
]


def make_key(authority, ref, title):
    basis = f"{authority}|{ref}".strip("|") if ref else f"{authority}|{title[:120]}"
    return hashlib.md5(basis.lower().encode("utf-8")).hexdigest()[:12]


def build_record(raw, cfg):
    title = _norm(raw["title"])
    blob = f"{title} {raw.get('extra','')} {raw.get('ref','')}"
    cap, cap_raw = extract_capacity_mw(title)
    due = parse_date(raw.get("due"))
    pub = parse_date(raw.get("published"))
    return {
        "TenderKey": make_key(cfg["authority"], raw.get("ref", ""), title),
        "Authority": cfg["authority"],
        "Project Name": title,
        "Technology": detect_technology(blob),
        "Capacity MW": cap if cap is not None else "",
        "State": detect_state(blob),
        "Due Date": due.isoformat() if due else "",
        "Status": derive_status(due),
        "Source URL": raw.get("link") or cfg["url"],
        "Tender Ref No": _norm(raw.get("ref", "")),
        "Tender Type": detect_tender_type(blob),
        "Published Date": pub.isoformat() if pub else "",
        "Days Left": (due - TODAY).days if due else "",
        "Capacity Raw": cap_raw,
        "Is Renewable": "Yes" if is_renewable(blob) else "No",
        "First Seen": TODAY.isoformat(),
        "Last Seen": TODAY.isoformat(),
        "Notes": "",
        "Winner": "",
        "Bids Received": "",
        "Award Status": "",
        "Award URL": "",
        "Award Date": "",
        "Award Source": "",
        "Award Headline": "",
    }


# ---------------------------------------------------------------------------
# AWARD / WINNER TRACKING
# ---------------------------------------------------------------------------
# Award data is published far less consistently than tender notices. Strategy:
#   1. scrape whatever the authority publishes (SECI has a clean award table)
#   2. let the user override or fill gaps via manual_awards.csv in the repo root
# Manual entries always win, because a human reading Mercom or Saur Energy is
# more reliable than any parser.
# ---------------------------------------------------------------------------

AWARD_SOURCES = [
    {
        "key": "SECI",
        "url": "https://www.seci.co.in/Bidder/view/tender/results/all-award/list/bidder",
        "header_must_contain": ["tender ref no", "number of bids"],
        "map": {"ref": "tender ref no", "bids": "number of bids"},
        "enabled": True,
    },
]

WINNER_HEADER_HINTS = ("bidder", "company", "name of", "firm", "developer", "agency")
WINNER_NOISE = re.compile(r"^(s\.?\s*no|sr|serial|rank|l\d|view|download|n/?a|-)$", re.I)


def normalize_ref(ref: str) -> str:
    """Join key that survives 'RfP No. X' vs 'X' and stray whitespace."""
    if not ref:
        return ""
    r = re.sub(r"(?i)^\s*(rfp|rfs|nit|tender)\s*(no\.?|ref\.?)?\s*[:.]?\s*", "", str(ref))
    return re.sub(r"[^A-Z0-9/\-]", "", r.upper())


def extract_winners(url):
    """Best-effort pull of bidder names from an award detail page."""
    try:
        soup = BeautifulSoup(fetch(url, retries=2, timeout=30), "lxml")
    except Exception:
        return ""
    names = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [_key(c.get_text(" ")) for c in rows[0].find_all(["th", "td"])]
        col = next((i for i, h in enumerate(headers)
                    if any(hint in h for hint in WINNER_HEADER_HINTS)), None)
        if col is None:
            continue
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if col < len(cells):
                val = _norm(cells[col].get_text(" "))
                if val and len(val) > 3 and not WINNER_NOISE.match(val):
                    names.append(val)
    seen, out = set(), []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return "; ".join(out[:8])


def fetch_awards():
    """Return {normalized_ref: {...}} of everything the authorities have published."""
    awards = {}
    for cfg in AWARD_SOURCES:
        if not cfg.get("enabled", True):
            continue
        try:
            soup = BeautifulSoup(fetch(cfg["url"]), "lxml")
            table, headers = pick_table(soup, [m.lower() for m in cfg["header_must_contain"]])
            if table is None:
                print(f"  awards {cfg['key']:<8} no matching table", file=sys.stderr)
                continue

            def col_index(wanted):
                wanted = wanted.lower()
                return next((i for i, h in enumerate(headers) if wanted in h), None)

            idx = {f: col_index(lbl) for f, lbl in cfg["map"].items()}
            count = 0
            for tr in (table.find("tbody") or table).find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                texts = [_norm(c.get_text(" ")) for c in cells]
                if all(_key(t) in headers for t in texts if t):
                    continue  # header row
                ri = idx.get("ref")
                if ri is None or ri >= len(texts):
                    continue
                ref = normalize_ref(texts[ri])
                if not ref:
                    continue
                bi = idx.get("bids")
                a = tr.find("a", href=True)
                detail = urljoin(cfg["url"], a["href"]) if a else ""
                awards[ref] = {
                    "bids": texts[bi] if bi is not None and bi < len(texts) else "",
                    "url": detail or cfg["url"],
                    "winner": extract_winners(detail) if detail else "",
                    "source": cfg["key"],
                }
                count += 1
            print(f"  awards {cfg['key']:<8} {count:>4} results")
        except Exception as exc:  # noqa: BLE001
            print(f"  awards {cfg['key']:<8} FAILED: {exc}", file=sys.stderr)
    return awards


def read_manual_awards():
    """manual_awards.csv columns: TenderRefNo, Winner, AwardDate, AwardURL"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_awards.csv")
    out = {}
    for row in read_csv(path):
        ref = normalize_ref(row.get("TenderRefNo", ""))
        if ref:
            out[ref] = row
    return out


def apply_awards(records):
    """Fill Winner / Bids / Award Status. Scraped first, manual overrides last."""
    scraped = fetch_awards()
    manual = read_manual_awards()
    filled = 0

    for rec in records.values():
        ref = normalize_ref(rec.get("Tender Ref No", ""))
        due = parse_date(rec.get("Due Date"))
        closed = rec.get("Status") in ("Closed", "Delisted") or (due and due < TODAY)

        hit = scraped.get(ref)
        if hit:
            rec["Bids Received"] = hit["bids"] or rec.get("Bids Received", "")
            rec["Award URL"] = hit["url"]
            if hit["winner"]:
                rec["Winner"] = hit["winner"]
            rec["Award Status"] = "Awarded" if hit["winner"] else "Awarded (see link)"
            rec["Award Source"] = "portal"
            filled += 1

        m = manual.get(ref)
        if m:
            rec["Winner"] = _norm(m.get("Winner", "")) or rec.get("Winner", "")
            rec["Award Date"] = _norm(m.get("AwardDate", "")) or rec.get("Award Date", "")
            rec["Award URL"] = _norm(m.get("AwardURL", "")) or rec.get("Award URL", "")
            rec["Award Status"] = "Awarded"
            rec["Award Source"] = "manual"
            filled += 1

        if not rec.get("Award Status"):
            rec["Award Status"] = "Under Evaluation" if closed else "Bidding Open"

    print(f"  awards matched to {filled} tender(s)")
    enrich_with_news(records)


# ---------------------------------------------------------------------------
# NEWS-BASED AWARD DISCOVERY  (Google News RSS, free, no API key)
# ---------------------------------------------------------------------------
# Only runs for tenders that have closed and have no winner yet. Results are
# labelled unverified and never override a portal or manual entry.
# ---------------------------------------------------------------------------

NEWS_ENABLED = True
MAX_NEWS_QUERIES = 20        # per run, keeps us polite and the job fast
NEWS_WINDOW_DAYS = 400       # stop chasing tenders older than this
NEWS_ENDPOINT = ("https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en")

# Developers and IPPs that actually win Indian RE tenders. Extend freely.
DEVELOPERS = [
    "Adani Green", "Adani Power", "ReNew", "Tata Power", "NTPC Green", "NTPC Renewable",
    "Greenko", "JSW Neo", "JSW Energy", "Juniper Green", "Hero Future", "Hero Solar",
    "ACME Solar", "ACME Cleantech", "Avaada", "Torrent Power", "Torrent Energy",
    "Serentica", "Sembcorp", "O2 Power", "Ampin Energy", "Amp Energy", "Vibrant Energy",
    "Waaree", "Hexa Climate", "Blupine", "Fortum", "EDF Renewables", "Engie",
    "Continuum Green", "Brookfield", "Mahindra Susten", "Radiance Renewables",
    "SAEL", "Oswal", "Shivalaya", "Purvah Green", "Banyan Insolation", "Pace Digitek",
    "SJVN Green", "NHPC", "SECI", "Azure Power", "Sprng Energy", "Ayana Renewable",
    "CleanMax", "Statkraft", "Enel Green", "Vena Energy", "Solarworld", "Gensol",
    "Sunsure", "Refex", "KP Energy", "Inox Wind", "Suzlon", "Envision", "Goldi Solar",
    "Premier Energies", "Vikram Solar", "Tata Renewable", "Rays Power", "Ostro",
    "Resolven", "Kengeri Prime", "Solarcraft", "Aditya Birla Renewables",
    "NLC India", "THDC", "Jakson", "Sunsource", "Clean Max", "Bikaner Solar",
    # bare surnames last so the longer forms above match first
    "Torrent", "Juniper", "Greenko", "Avaada", "Serentica", "Hexa",
]
DEV_RE = re.compile(r"(" + "|".join(re.escape(d) for d in DEVELOPERS) + r")", re.I)

AWARD_VERB = re.compile(
    r"\baward|\bwins?\b|\bwon\b|\bbags?\b|\ballot|\bsecures?\b|\bL1\b|"
    r"\bemerges?\b|\bwinning bid|\bbaggs?\b|\bselected\b", re.I)

SCHEME_TAG = re.compile(
    r"\(([A-Za-z]{2,}[A-Za-z0-9]*(?:-[A-Za-z0-9]+){1,3})\)|"
    r"\b(SECI-[A-Z]+-[IVXL]+|Tranche-[IVXL]+|ISTS-[IVXL]+|FDRE-[IVXL]+)\b")


def scheme_tag(title):
    m = SCHEME_TAG.search(title or "")
    if not m:
        return ""
    tag = (m.group(1) or m.group(2) or "").strip()
    return tag if len(tag) >= 5 and re.search(r"[IVXL0-9]", tag) else ""


def build_news_query(rec):
    bits = [rec.get("Authority", "")]
    tag = scheme_tag(rec.get("Project Name", ""))
    if tag:
        bits.append(tag)
    cap = rec.get("Capacity MW")
    if cap not in ("", None):
        try:
            bits.append(f"{int(float(cap))} MW")
        except (TypeError, ValueError):
            pass
    tech = rec.get("Technology", "")
    if tech and tech != "Unclassified" and not tag:
        bits.append(tech.split("/")[0].split("(")[0].strip())
    bits.append("(awarded OR wins OR tariff)")
    return " ".join(b for b in bits if b)


def parse_news_items(xml_text):
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for it in soup.find_all("item")[:12]:
        items.append({
            "title": _norm(it.title.get_text() if it.title else ""),
            "link": _norm(it.link.get_text() if it.link else ""),
            "date": parse_date((it.pubDate.get_text()[5:16] if it.pubDate else "")),
            "source": _norm(it.source.get_text()) if it.source else "",
        })
    return items


def score_news_item(item, rec, tag):
    """Higher is better. Returns 0 when the item clearly is not about this tender."""
    title = item["title"]
    if not AWARD_VERB.search(title):
        return 0
    due = parse_date(rec.get("Due Date"))
    if due and item["date"] and item["date"] < due:
        return 0                      # published before bids even closed
    score = 1
    if tag and tag.lower() in title.lower():
        score += 3
    cap = rec.get("Capacity MW")
    if cap not in ("", None):
        try:
            if re.search(rf"\b{int(float(cap))}\s*(MW|MWh)", title, re.I):
                score += 3
        except (TypeError, ValueError):
            pass
    if rec.get("Authority", "").lower() in title.lower():
        score += 1
    if DEV_RE.search(title):
        score += 1
    return score


def search_award_news(rec):
    """Return dict with winner/headline/url, or None."""
    tag = scheme_tag(rec.get("Project Name", ""))
    query = build_news_query(rec)
    url = NEWS_ENDPOINT.format(q=requests.utils.quote(query))
    try:
        items = parse_news_items(fetch(url, retries=2, timeout=25))
    except Exception:
        return None
    best, best_score = None, 0
    for it in items:
        sc = score_news_item(it, rec, tag)
        if sc > best_score:
            best, best_score = it, sc
    if not best or best_score < 4:        # needs the tag or the capacity to match
        return None
    names = []
    for m in DEV_RE.finditer(best["title"]):
        n = m.group(1)
        if n.lower() not in [x.lower() for x in names] and n.lower() != rec.get(
                "Authority", "").lower():
            names.append(n)
    return {
        "winner": "; ".join(names[:6]),
        "headline": best["title"],
        "url": best["link"],
        "date": best["date"].isoformat() if best["date"] else "",
        "score": best_score,
    }


def enrich_with_news(records):
    if not NEWS_ENABLED:
        return
    candidates = []
    for rec in records.values():
        if rec.get("Winner") or rec.get("Award Source") == "manual":
            continue
        if rec.get("Is Renewable") != "Yes":
            continue
        due = parse_date(rec.get("Due Date"))
        if not due or due >= TODAY:
            continue
        if (TODAY - due).days > NEWS_WINDOW_DAYS:
            continue
        candidates.append(rec)

    candidates.sort(key=lambda r: r.get("Due Date") or "", reverse=True)
    found = 0
    for rec in candidates[:MAX_NEWS_QUERIES]:
        hit = search_award_news(rec)
        time.sleep(1.5)
        if not hit:
            continue
        rec["Award Headline"] = hit["headline"]
        rec["Award URL"] = hit["url"] or rec.get("Award URL", "")
        rec["Award Date"] = hit["date"] or rec.get("Award Date", "")
        rec["Award Source"] = "news (unverified)"
        if hit["winner"]:
            rec["Winner"] = hit["winner"]
            rec["Award Status"] = "Awarded (news, unverified)"
        else:
            rec["Award Status"] = "Award reported (check link)"
        found += 1
    print(f"  news    checked {min(len(candidates), MAX_NEWS_QUERIES)}, "
          f"matched {found}")


# ---------------------------------------------------------------------------
# PERSISTENCE
# ---------------------------------------------------------------------------

def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, fieldnames=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else FIELDNAMES)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def append_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerows(rows)


def write_excel(path, master, renewable):
    try:
        import pandas as pd
    except ImportError:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        pd.DataFrame(renewable or [{k: "" for k in FIELDNAMES}]).to_excel(
            xl, sheet_name="Renewable Tenders", index=False)
        pd.DataFrame(master or [{k: "" for k in FIELDNAMES}]).to_excel(
            xl, sheet_name="All Tenders", index=False)


# ---------------------------------------------------------------------------
# MAIN RUN
# ---------------------------------------------------------------------------

def run(only_source=None):
    master_path = os.path.join(DATA_DIR, "tenders.csv")
    previous = {r["TenderKey"]: r for r in read_csv(master_path)}

    scraped, run_log = {}, []

    for cfg in SOURCES:
        if not cfg.get("enabled", True):
            continue
        if only_source and cfg["key"] != only_source:
            continue
        started = time.time()
        try:
            html = fetch(cfg["url"])
            raws = PARSERS[cfg["parser"]](html, cfg)
            for raw in raws:
                rec = build_record(raw, cfg)
                scraped[rec["TenderKey"]] = rec
            run_log.append({
                "run_date": TODAY.isoformat(), "source": cfg["key"],
                "status": "OK" if raws else "EMPTY", "rows": len(raws),
                "seconds": round(time.time() - started, 1), "error": "",
            })
            print(f"  {cfg['key']:<12} {len(raws):>4} rows")
        except Exception as exc:  # noqa: BLE001
            run_log.append({
                "run_date": TODAY.isoformat(), "source": cfg["key"],
                "status": "FAILED", "rows": 0,
                "seconds": round(time.time() - started, 1), "error": str(exc)[:300],
            })
            print(f"  {cfg['key']:<12} FAILED: {exc}", file=sys.stderr)

    # ---- merge against previous state -------------------------------------
    changes, merged = [], {}

    for key, rec in scraped.items():
        old = previous.get(key)
        if old is None:
            rec["Notes"] = "NEW"
            changes.append({"run_date": TODAY.isoformat(), "change": "NEW",
                            "Authority": rec["Authority"], "Project Name": rec["Project Name"],
                            "field": "", "old": "", "new": rec["Due Date"],
                            "Source URL": rec["Source URL"]})
        else:
            rec["First Seen"] = old.get("First Seen") or rec["First Seen"]
            if old.get("Due Date") and rec["Due Date"] and old["Due Date"] != rec["Due Date"]:
                rec["Notes"] = "DUE DATE REVISED"
                changes.append({"run_date": TODAY.isoformat(), "change": "DUE_DATE_REVISED",
                                "Authority": rec["Authority"], "Project Name": rec["Project Name"],
                                "field": "Due Date", "old": old["Due Date"], "new": rec["Due Date"],
                                "Source URL": rec["Source URL"]})
        merged[key] = rec

    # keep history for tenders that dropped off the live listing
    for key, old in previous.items():
        if key in merged:
            continue
        old = dict(old)
        due = parse_date(old.get("Due Date"))
        old["Status"] = "Closed" if (due and due < TODAY) else "Delisted"
        old["Days Left"] = (due - TODAY).days if due else ""
        old["Notes"] = ""
        merged[key] = old

    apply_awards(merged)

    rows = sorted(
        merged.values(),
        key=lambda r: (r.get("Due Date") or "9999-12-31", r.get("Authority", "")),
    )
    renewable = [r for r in rows if r.get("Is Renewable") == "Yes"
                 and r.get("Status") in ("Open", "Closing Soon", "Unknown")]

    write_csv(master_path, rows, FIELDNAMES)
    write_csv(os.path.join(DATA_DIR, "tenders_renewable.csv"), renewable, FIELDNAMES)
    write_excel(os.path.join(DATA_DIR, "tenders.xlsx"), rows, renewable)
    if changes:
        append_csv(os.path.join(DATA_DIR, "changes.csv"), changes,
                   ["run_date", "change", "Authority", "Project Name",
                    "field", "old", "new", "Source URL"])
    append_csv(os.path.join(DATA_DIR, "run_log.csv"), run_log,
               ["run_date", "source", "status", "rows", "seconds", "error"])

    live = [r for r in renewable if r["Status"] in ("Open", "Closing Soon")]
    print(f"\nMaster: {len(rows)} | Live RE: {len(live)} | Changes today: {len(changes)}")

    failures = [r for r in run_log if r["status"] in ("FAILED", "EMPTY")]
    if failures:
        print("Attention: " + ", ".join(f"{f['source']}={f['status']}" for f in failures))
    return rows, renewable, changes, run_log


# ---------------------------------------------------------------------------
# OPTIONAL EMAIL DIGEST  (set SMTP_USER / SMTP_PASS / EMAIL_TO env vars)
# ---------------------------------------------------------------------------

def send_digest(renewable, changes, run_log):
    to = os.environ.get("EMAIL_TO")
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    if not (to and user and pwd):
        return
    import smtplib
    from email.mime.text import MIMEText

    new = [c for c in changes if c["change"] == "NEW"]
    revised = [c for c in changes if c["change"] == "DUE_DATE_REVISED"]
    soon = [r for r in renewable if r["Status"] == "Closing Soon"]
    fails = [r for r in run_log if r["status"] in ("FAILED", "EMPTY")]

    def table(rows):
        out = ["<table border=1 cellpadding=6 cellspacing=0 "
               "style='border-collapse:collapse;font:13px Arial'>",
               "<tr style='background:#eee'><th>Authority</th><th>Project</th><th>Tech</th>"
               "<th>MW</th><th>State</th><th>Due</th><th>Status</th></tr>"]
        for r in rows:
            out.append(
                f"<tr><td>{r['Authority']}</td>"
                f"<td><a href='{r['Source URL']}'>{r['Project Name'][:110]}</a></td>"
                f"<td>{r['Technology']}</td><td align=right>{r['Capacity MW']}</td>"
                f"<td>{r['State']}</td><td>{r['Due Date']}</td><td>{r['Status']}</td></tr>")
        out.append("</table>")
        return "".join(out)

    keys = {c["Project Name"] for c in new}
    new_rows = [r for r in renewable if r["Project Name"] in keys]

    html = [f"<h3>Renewable tender digest — {TODAY:%d %b %Y}</h3>"]
    html.append(f"<p><b>{len(new_rows)}</b> new &middot; <b>{len(revised)}</b> date revisions "
                f"&middot; <b>{len(soon)}</b> closing within 7 days</p>")
    if new_rows:
        html.append("<h4>New</h4>" + table(new_rows))
    if revised:
        html.append("<h4>Due date revised</h4><ul>" + "".join(
            f"<li>{c['Authority']}: {c['Project Name'][:110]} &mdash; "
            f"{c['old']} &rarr; {c['new']}</li>" for c in revised) + "</ul>")
    if soon:
        html.append("<h4>Closing within 7 days</h4>" + table(soon))
    if fails:
        html.append("<p style='color:#b00'><b>Source health:</b> " + ", ".join(
            f"{f['source']}={f['status']}" for f in fails) + "</p>")

    msg = MIMEText("".join(html), "html", "utf-8")
    msg["Subject"] = (f"RE Tenders {TODAY:%d-%b}: {len(new_rows)} new, "
                      f"{len(soon)} closing soon")
    msg["From"] = user
    msg["To"] = to
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port) as srv:
        srv.login(user, pwd)
        srv.sendmail(user, [x.strip() for x in to.split(",")], msg.as_string())
    print(f"Digest emailed to {to}")


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def inspect(url):
    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    print(f"{len(tables)} table(s) found on {url}\n")
    for i, t in enumerate(tables):
        first = t.find("tr")
        if not first:
            continue
        headers = [_norm(c.get_text(" ")) for c in first.find_all(["th", "td"])]
        body_rows = t.find_all("tr")[1:4]
        print(f"--- table[{i}] rows={len(t.find_all('tr'))}")
        print(f"    headers: {headers}")
        for r in body_rows:
            print(f"    sample : {[_norm(c.get_text(' '))[:60] for c in r.find_all('td')]}")
        print()


def selftest():
    samples = [
        "700 MW ISTS-Connected Solar PV Power Projects in India under TBCB (C&I-1)",
        "RfS for Utilization of 100 MWh (50 MW x 2 Hrs.) Standalone Energy Storage System "
        "on Short-Term Basis under Tariff-Based Competitive Bidding",
        "Tender for Design, Engineering, Supply, Construction, Erection, Testing, "
        "Commissioning and Maintenance of 70 MW ISTS Connected Solar PV Power Project "
        "paired with 25MW/ 50MWh BESS at Ramagiri, Sri Sathya Sai District, Andhra Pradesh",
        "Setting up of grid-connected 45.6 MW Wind Power Project (Package 2: Wind)",
        "Request for Proposals for Selection of Project Developer for setting up of Grid "
        "connected 922.635 kW Rooftop Solar PV Power Project in CAPEX mode",
        "RfS for assured Peak Supply of 1000 MWh (500 MW x 2 Hrs.) under CfD Mechanism "
        "from ISTS-Connected RE Projects (SECI-CfD-I)",
        "EOI for Identification and Capability Assessment of Agencies for Geothermal "
        "Resource Assessment in UT of A&N Islands",
        "Development of Transmission Line (400kV) 80kM approx. for evacuation of Power "
        "generated from 1200 MW Solar Power park in District Jalaun, Uttar Pradesh",
        "SAP ERP Landscape (ERP 2.0)",
        "Selection of Tenant(s) for Renting out the Office space(s) of SECI at NBCC Complex, "
        "East Kidwai Nagar, New Delhi",
        "Repair & Painting of IRBN Barrack at Left Bank of Teesta-V Power Station, Balutar",
        "Development of Micro Hydro Power Project (2X82KW) utilizing mandatory environmental "
        "flow at Parbati-III through PAT technology",
    ]
    print(f"{'RE?':<4} {'MW':>9}  {'Technology':<32} {'State':<20} Title")
    print("-" * 130)
    for s in samples:
        cap, raw = extract_capacity_mw(s)
        print(f"{('Y' if is_renewable(s) else 'n'):<4} "
              f"{(cap if cap is not None else '-'):>9}  "
              f"{detect_technology(s):<32} {detect_state(s) or '-':<20} {s[:58]}")
    print("\nDate parsing:", [str(parse_date(x)) for x in
                              ["03/09/2026", "28-Aug-2026", "2026-09-05", "13 Jul 2026", ""]])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", metavar="URL")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--source", metavar="KEY")
    args = ap.parse_args()

    if args.inspect:
        inspect(args.inspect)
    elif args.selftest:
        selftest()
    else:
        print(f"Run {datetime.now(IST):%Y-%m-%d %H:%M} IST")
        try:
            _, ren, ch, log = run(only_source=args.source)
            send_digest(ren, ch, log)
        except Exception:
            traceback.print_exc()
            sys.exit(1)
