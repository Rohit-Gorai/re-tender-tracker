# India Renewable Tender Tracker

Runs every day at 10:30 IST on GitHub Actions (free), scrapes public tender pages,
extracts Authority / Project Name / Technology / Capacity MW / State / Due Date /
Status / Source URL, and commits `data/tenders.xlsx` + CSVs back to the repo.

No servers, no licences, no laptop needs to be switched on.

---

## 1. Setup (about 15 minutes)

1. Create a **private** GitHub repo, e.g. `re-tender-tracker`.
2. Upload these four files, keeping the folder structure:

```
re-tender-tracker/
├── tender_tracker.py
├── requirements.txt
├── README.md
└── .github/workflows/daily-tenders.yml
```

3. Repo → **Settings → Actions → General → Workflow permissions** →
   select **Read and write permissions**. Without this the bot cannot commit results.
4. Repo → **Actions** tab → enable workflows → pick *Daily Renewable Tender Tracker*
   → **Run workflow** to test immediately.
5. Check that `data/tenders.xlsx` appears in the repo.

The cron is `0 5 * * *` (05:00 UTC = 10:30 IST). GitHub's shared scheduler can be
5–15 minutes late; if you need a hard 10:30, set the cron to `45 4 * * *` and treat
10:30 as the deadline rather than the start.

### Optional: daily email digest

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `EMAIL_TO` | your address (comma-separate for several) |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASS` | a Gmail **App Password**, not your login password |

Leave these unset and the script simply skips the email.

---

## 2. What it produces (`data/`)

| File | Contents |
|---|---|
| `tenders.csv` | master table, every tender ever seen, with first/last seen dates |
| `tenders_renewable.csv` | live RE-relevant tenders only, noise filtered out |
| `tenders.xlsx` | two sheets: *Renewable Tenders*, *All Tenders* |
| `changes.csv` | append-only log: NEW tenders and DUE_DATE_REVISED events |
| `run_log.csv` | per-source health: rows fetched, seconds, errors |

Extra columns beyond the eight you asked for: Tender Ref No, Tender Type
(RfS/RfP/EOI/NIT), Published Date, Days Left, Capacity Raw (the exact text the MW
figure came from, so you can audit it), Is Renewable, First Seen, Last Seen, Notes.

**`run_log.csv` is the one to watch.** If a source shows `EMPTY` or `FAILED` two days
running, the site's HTML changed and that source is silently missing tenders. Nothing
else in the pipeline will tell you.

---

## 3. Adding a source

Two are enabled and verified: **SECI** (clean HTML table) and **NHPC** (text blocks).
Three more are stubbed with `"enabled": False` because their exact column headers
need confirming: SJVN, IREDA, NTPC Green Energy.

To wire one up:

```bash
python tender_tracker.py --inspect https://sjvn.nic.in/tender-notice
```

It prints every table on the page with its headers and three sample rows. Copy the
header text into the `map` block of that source in `SOURCES`, set
`header_must_contain` to two distinctive headers, flip `enabled` to `True`, and test:

```bash
python tender_tracker.py --source SJVN
```

Good candidates to add: NTPC Green Energy, NLC India, THDC, SJVN Green Energy,
IREDA, MNRE, NVVN, and state agencies (GUVNL, MSEDCL, RUVNL, TANGEDCO, NTPC REL).

---

## 4. What this cannot reach, and what to do about it

**GeM and the GePNIC portals (NTPC's `eprocurentpc.nic.in`, the CPPP search pages)
require a CAPTCHA before they will list anything.** That is deliberate, it is in
their terms of use, and no scraper should get around it. Two legitimate free routes:

- **Portal email alerts.** Register the tracker's mailbox on GeM and on each PSU
  portal for category alerts, and on a free aggregator tier (BidAssist, TenderDetail).
  Everything lands in one inbox with no scraping at all.
- **Organisation websites.** NTPC, NHPC and SJVN each publish a tender summary on
  their own `.co.in` / `.nic.in` site, which is what this script uses. It is less
  complete than the e-procurement portal but it is open and stable.

Between SECI's own page, the PSU corporate sites, and email alerts you will catch
essentially every large RE tender that matters to a project-advisory desk. What you
will not get automatically is the small works and supply tenders, which you do not want.

---

## 5. Dashboard options (all free)

**Excel, simplest.** Open Excel → Data → From Web → paste the raw CSV URL:

```
https://raw.githubusercontent.com/<user>/<repo>/main/data/tenders_renewable.csv
```

For a private repo, use a personal access token in the URL, or make the repo public
with no sensitive content in it. Then Query Properties → *Refresh data when opening
the file*. Every time you open the workbook it pulls the latest.

**Power BI Desktop, free.** Get Data → Web → same URL. Build the visuals you want:
closing-in-7-days table, capacity by technology, pipeline by state, authority split.
Refresh on open. Publishing to the Power BI Service with scheduled refresh needs a
Pro licence, which is the only paid step in the whole design and is entirely optional.

**Looker Studio, free and auto-refreshing.** If you want a live dashboard with no
licence at all: have the script also write to a Google Sheet (add `gspread` and a
free service account), then connect Looker Studio to that sheet. Refreshes on its own,
shareable by link.

---

## 6. Known limits

- **Capacity MW is parsed from the tender title.** Where the title says "100 MWh
  (50 MW × 2 Hrs.)" it correctly reports 50 MW; where the title carries no figure it
  is blank rather than guessed. The real number often lives inside the RfS PDF.
  Check `Capacity Raw` before quoting any MW figure externally.
- **State is only detected when the title or location field names it.** Pan-India
  ISTS tenders legitimately have no state.
- **NHPC's listing page has no bid due date**, so those rows show Status = Unknown.
  Open the source URL for the date.
- **Nothing here is authoritative.** It is a monitoring layer that guarantees you see
  what was published. Confirm every due date on the portal before it drives a decision.

---

## 7. Running locally

```bash
pip install -r requirements.txt
python tender_tracker.py --selftest        # check the extraction logic
python tender_tracker.py                   # full run, writes ./data
python tender_tracker.py --source SECI     # one source
python tender_tracker.py --inspect <url>   # explore a new site
```
