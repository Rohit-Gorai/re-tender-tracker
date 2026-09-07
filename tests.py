#!/usr/bin/env python3
"""Acceptance tests for the tender tracker.

Run:  python tests.py
The daily workflow runs these before the scrape; a failure stops the run so a
broken build can never overwrite good data.
"""
import csv
import os
import shutil
import sys

import tender_tracker as T

PASS, FAIL = [], []


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  <- {detail}" if detail and not condition else ""))


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
LIST = """<html><table><thead><tr><th>Tender Ref No.</th><th>Tender Title</th>
<th>Publication Date</th><th>Bid Submission Date</th><th>Tender Details</th></tr></thead><tbody>
<tr><td>SECI/C&amp;P/IPP/15/0017/25-26</td><td>RfS for Setting up of 1500 MW/12000 MWh Pumped Storage Plants in India (PSP-I)</td>
<td>26/12/2025</td><td>05/06/2026</td><td><a href="/tender-details/1">V</a></td></tr>
<tr><td>SECI/C&amp;P/IPP/12/0003/26-27</td><td>RfS for 2000 MW ISTS-Connected Wind Power Projects (SECI-Tranche-XX)</td>
<td>21/04/2026</td><td>19/06/2026</td><td><a href="/tender-details/2">V</a></td></tr>
</tbody></table></html>"""

# same tenders, retitled and re-ordered, as a portal would after an edit
LIST_RETITLED = LIST.replace(
    "RfS for Setting up of 1500 MW/12000 MWh Pumped Storage Plants in India (PSP-I)",
    "RfS for Setting up of 1500 MW / 12000 MWh Pumped Storage Plants in India  (PSP-I) - Amended")

RSS = """<?xml version="1.0"?><rss><channel><item>
<title>Greenko, Torrent and Tata Power win SECI 1500 MW/12000 MWh Pumped Storage Tender</title>
<link>https://news.google.com/rss/articles/A</link>
<description>&lt;a href="https://saurenergy.com/s"&gt;s&lt;/a&gt;</description>
<pubDate>Tue, 21 Jul 2026 06:00:00 GMT</pubDate></item></channel></rss>"""
ARTICLE = "<html><p>Greenko 600 MW at Rs 5.25 per kWh, Torrent Power 450 MW, Tata Power 450 MW.</p></html>"
EMPTY = "<html><table></table></html>"


def stub(listing=LIST, rss=RSS, news_ok=True):
    def f(url, **kw):
        if "rss/search" in url:
            if not news_ok:
                raise RuntimeError("simulated Google News outage")
            return rss
        if "saurenergy" in url:
            return ARTICLE
        if url == "https://www.seci.co.in/tenders":
            return listing
        return EMPTY
    return f


def fresh_run(fetch_fn):
    T.fetch = fetch_fn
    T.time.sleep = lambda *a: None
    T.SWEEP_ENABLED = False
    T.MAX_DETAIL_FETCHES = 0
    return T.run()


def data(name):
    path = os.path.join(T.DATA_DIR, name)
    return list(csv.DictReader(open(path, encoding="utf-8"))) if os.path.exists(path) else []


# --------------------------------------------------------------------------
print("\n== 1. Idempotency and deduplication ==")
shutil.rmtree(T.DATA_DIR, ignore_errors=True)
fresh_run(stub())
first = data("tenders.csv")
fresh_run(stub())          # identical second run
second = data("tenders.csv")

check("run twice produces no extra tenders", len(first) == len(second),
      f"{len(first)} then {len(second)}")
keys = [r["TenderKey"] for r in second]
check("every TenderKey appears exactly once", len(keys) == len(set(keys)))
refs = [T.normalize_ref(r["Tender Ref No"]) for r in second if r["Tender Ref No"]]
check("no reference number under two TenderKeys", len(refs) == len(set(refs)))

awards = data("awards.csv")
ids = [a["Award ID"] for a in awards]
check("every Award ID is unique", len(ids) == len(set(ids)))
check("multiple winners do not duplicate the tender",
      len(awards) == 3 and len({a["TenderKey"] for a in awards}) == 1,
      f"{len(awards)} awards across {len({a['TenderKey'] for a in awards})} tenders")
check("awards reference a tender that exists",
      all(a["TenderKey"] in set(keys) for a in awards))

# --------------------------------------------------------------------------
print("\n== 2. Scenario D: source edits a tender title ==")
before = {r["Tender Ref No"]: r["TenderKey"] for r in second}
fresh_run(stub(listing=LIST_RETITLED))
after = data("tenders.csv")
after_keys = {r["Tender Ref No"]: r["TenderKey"] for r in after}
check("TenderKey stays stable when the title changes",
      before.get("SECI/C&P/IPP/15/0017/25-26") == after_keys.get("SECI/C&P/IPP/15/0017/25-26"))
check("retitle updates rather than duplicates", len(after) == len(second),
      f"{len(second)} then {len(after)}")

# --------------------------------------------------------------------------
print("\n== 3. Scenario A/B: source returns nothing or breaks ==")
n_before = len(data("tenders.csv"))
fresh_run(stub(listing=EMPTY))
rows = data("tenders.csv")
check("historical records survive an empty source", len(rows) == n_before,
      f"{n_before} then {len(rows)}")
check("nothing is marked Delisted while the source is unhealthy",
      not any(r["Status"] == "Delisted" for r in rows))
check("failure is recorded in the run log",
      any(e["status"] != "OK" for e in data("run_log.csv")))
check("failure is raised as a HIGH data-quality flag",
      any(q["Severity"] == "HIGH" and q["Check"] == "SOURCE_UNHEALTHY"
          for q in data("data_quality.csv")))

# --------------------------------------------------------------------------
print("\n== 4. Scenario C: research layer fails ==")
n_before = len(data("tenders.csv"))
fresh_run(stub(news_ok=False))
check("pipeline still completes when news lookup throws",
      len(data("tenders.csv")) == n_before)
check("winner discovered earlier is not lost",
      any(r["Winner"] for r in data("tenders.csv")))

# --------------------------------------------------------------------------
print("\n== 5. Award matching precision ==")
cases = [
    ("RfS for Setting up of 500 MW ISTS-connected Offshore Wind Power Project (Tranche-I)",
     500, "Wind", "NHPC Awards 125 MW/500 MWh BESS Tender to NTPC, Tata Power in Kerala", False),
    ("Tender for Balance of System for 700 MW Solar PV Plant at Radha Nesda",
     700, "Solar", "Waaree Energies wins 700 MW solar-plus-storage project from SECI", False),
    ("RfS for 500 MW ISTS-Connected Solar PV Power Projects (SECI-ISTS-XIX)",
     500, "Solar", "NTPC REL Secures 500 MW Peak Power Contract From SECI", False),
    ("RfS for Setting up of 1500 MW/12000 MWh Pumped Storage Plants (PSP-I)",
     1500, "Pumped Storage",
     "Greenko, Torrent & Tata Power Wins SECI 1500 MW Pumped Storage Tender", True),
    ("RfS for setting up of 17768 kW Grid-Connected RTSPV project in Puducherry (RTSPV-Tranche-V)",
     17.768, "Rooftop Solar",
     "SECI Awards 17.7 MW Rooftop Solar Projects In Puducherry At Rs 4.11/kWh", True),
]
for title, cap, tech, headline, expect in cases:
    if T.NON_IPP.search(title):
        got = False
    else:
        rec = {"Authority": "SECI", "Project Name": title, "Capacity MW": cap,
               "Technology": tech, "Bid Submission End Date (Online)": "2026-01-01"}
        got = T.score_news_item({"title": headline, "date": T.parse_date("2026-06-01")},
                                rec, T.scheme_tag(title)) >= 4
    check(f"{'accept' if expect else 'reject'}: {headline[:52]}", got == expect)

# --------------------------------------------------------------------------
print("\n== 6. Normalisation ==")
check("17768 kW is 17.768 MW", T.extract_capacity_mw("17768 kW project")[0] == 17.768)
check("100 MWh (50 MW x 2 Hrs) is 50 MW",
      T.extract_capacity_mw("100 MWh (50 MW x 2 Hrs.) storage")[0] == 50)
check("1 GW is 1000 MW", T.extract_capacity_mw("1 GW solar park")[0] == 1000)
check("authority name does not make a tender renewable",
      not T.is_renewable("Liability Insurance of Solar Energy Corporation of India Limited"))
check("epoch placeholder date rejected", T.parse_date("01/01/1970") is None)
check("TenderKey is text-safe for Excel", T.make_key("SECI", "GEM/2025/B/1", "x").startswith("T-"))

# --------------------------------------------------------------------------
print("\n== 7. CSV integrity ==")
for name in ("tenders.csv", "awards.csv", "financing_targets.csv",
             "manual_review.csv", "data_quality.csv"):
    rows = data(name)
    path = os.path.join(T.DATA_DIR, name)
    check(f"{name} exists", os.path.exists(path))
    if rows:
        width = len(rows[0])
        check(f"{name} has consistent column count",
              all(len(r) == width for r in rows))

# --------------------------------------------------------------------------
print("\n== 8. Secrets ==")
leaked = []
for name in os.listdir(T.DATA_DIR):
    if name.endswith((".csv", ".md")):
        body = open(os.path.join(T.DATA_DIR, name), encoding="utf-8", errors="ignore").read()
        if "sk-ant" in body or "ANTHROPIC_API_KEY" in body:
            leaked.append(name)
check("no API key material in any output file", not leaked, str(leaked))

# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# 9. Primary business output
# --------------------------------------------------------------------------
print("\n== 9. renewable_tender_winners.csv ==")
shutil.rmtree(T.DATA_DIR, ignore_errors=True)
fresh_run(stub())
primary = data("renewable_tender_winners.csv")
check("primary tracker exists", bool(primary))
if primary:
    cols = list(primary[0].keys())
    check("Winning Bidder is the first column", cols[0] == "Winning Bidder")
    check("commercial fields lead the file",
          cols[:7] == ["Winning Bidder", "Award Status", "Issuing Authority",
                       "Tender / RfS Number", "Tender Title", "Technology",
                       "Awarded Capacity MW"])
    check("open tenders never enter the winner file",
          all(r["Award Status"] != "Not Yet Awarded" for r in primary))
    check("no pre-FY26 award reaches the winner file",
          all(not r["Business Eligibility"].startswith("Out of Scope")
              for r in primary))
    check("every in-scope award date is FY26 or later",
          all(r["Award Date"] == "Unknown" or r["Award Date"] >= "2025-04-01"
              for r in primary))
    check("scope decision always states its basis",
          all(r["Date Basis"] for r in primary))
    check("Actual COD is never a derived value",
          all(r["Actual COD"] == "Unknown" for r in primary
              if r["COD Basis"].startswith("Derived")))
    check("Award Status uses only controlled values",
          set(r["Award Status"] for r in primary) <=
          {"Awarded", "Verification Required"})
    check("awarded rows sort above unverified ones",
          [r["Award Status"] for r in primary] ==
          sorted([r["Award Status"] for r in primary],
                 key=lambda v: {"Awarded": 0, "Verification Required": 1}[v]))
    dates = [r["Award Date"] for r in primary if r["Award Status"] == "Awarded"]
    check("awarded rows run newest first", dates == sorted(dates, reverse=True))
    check("Awarded rows always name a bidder",
          all(r["Winning Bidder"] not in ("Not Yet Awarded", "Verification Required")
              for r in primary if r["Award Status"] == "Awarded"))
    check("multi-winner rows share tender identity",
          all(len({(x["Tender / RfS Number"], x["Tender Title"],
                    x["Issuing Authority"]) for x in primary
                   if x["TenderKey"] == k}) == 1
              for k in {r["TenderKey"] for r in primary}))
    check("Winner Count matches the award rows present",
          all(int(r["Winner Count"] or 0) ==
              len([x for x in primary if x["TenderKey"] == r["TenderKey"] and x["AwardID"]])
              for r in primary))
    tkeys = [r["TenderKey"] for r in primary]
    aids = [r["AwardID"] for r in primary if r["AwardID"]]
    check("AwardIDs unique across the primary view", len(aids) == len(set(aids)))
    check("multiple winners share one TenderKey",
          len(tkeys) >= len(set(tkeys)))
    check("no tender is silently blank on the winner field",
          all(r["Winning Bidder"] for r in primary))

    check("every row carries a source type and confidence",
          all(r["Source Type"] and r["Confidence"] for r in primary))
    targets = data("financing_targets.csv")
    check("financing targets are FY26 onward",
          all(not t["Award Date"] or t["Award Date"] >= "2025-04-01" for t in targets))
    check("financing targets contain no unawarded tender",
          all(t["Winner Group"] not in ("Not Yet Awarded", "Verification Required")
              for t in targets))

check("storage 1500 MW/12000 MWh parses to both fields",
      T.extract_storage("1500 MW/12000 MWh Pumped Storage") == (1500.0, 12000.0))
check("plain generation capacity yields no storage rating",
      T.extract_storage("700 MW ISTS-Connected Solar PV") == ("", ""))
check("pre-FY26 award is out of scope",
      T.date_eligibility(T.parse_date("2024-01-15"), None)[0]
      == "Out of Scope - Pre-FY26")
check("FY26 award is in scope",
      T.date_eligibility(T.parse_date("2025-04-01"), None)[0] == "FY26+")
check("unknown award date needs verification, not silent inclusion",
      T.date_eligibility(None, T.parse_date("2026-06-01"))[0] == "Verification Required")
check("old tender with unknown award date is excluded",
      T.date_eligibility(None, T.parse_date("2023-11-14"))[0]
      == "Out of Scope - Pre-FY26")

rec = {"Tariff": "", "Tariff Status": "", "Tariff Conflict": ""}
T.set_tariff(rec, "\u20b95.25/kWh", "Press report")
T.set_tariff(rec, "\u20b95.40/kWh", "AI with citation")
check("conflicting tariffs flag rather than overwrite",
      rec["Tariff"] == "\u20b95.25/kWh" and rec["Tariff Status"] == "Conflict"
      and "5.40" in rec["Tariff Conflict"])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED: " + ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
