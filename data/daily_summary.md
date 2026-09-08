# Renewable tender tracker - 08 Sep 2026

- **0** new tenders
- **3** revised bid dates
- **8** closing within 7 days
- **133** award records across 95 tenders
- **79** financing targets

**Business scope: FY26 onward. Cutoff 1 April 2025.** 598 winner rows in scope; 517 pre-FY26 excluded (retained in tenders.csv).

Primary output: **data/renewable_tender_winners.csv** (one row per tender-award relationship).
- **571** high-severity data-quality flags

## Financing targets (top 10 by capacity)
| # | Winner | MW | Tech | COD | Confidence |
|---|---|---|---|---|---|
| 1 | Renew | 8600 | Solar + Storage | 2028-06-26 | Press report - verify |
| 2 | Adani Power; Renew | 2500 | Round-the-Clock / CfD / Trading | 2028-04-07 | Press report - verify |
| 3 | Adani Power | 2500 | Round-the-Clock / CfD / Trading | 2028-04-06 | Press report - verify |
| 4 | Engie | 2000 | Energy Storage (BESS) | 2027-05-18 | Press report - verify |
| 5 | SAEL | 2000 | Solar + Storage | 2027-11-08 | Press report - verify |
| 6 | Adani Power | 1600 | Unclassified | 2027-09-11 | Press report - verify |
| 7 | Adani Power | 1600 | Unclassified | 2027-09-11 | Press report - verify |
| 8 | Adani Power | 1600 | Unclassified | 2028-03-15 | Press report - verify |
| 9 | Adani Power | 1600 | Unclassified | 2028-03-16 | Press report - verify |
| 10 | Adani Power | 1600 | Unclassified | 2028-03-16 | Press report - verify |

## Needs manual verification
| Authority | Winner | TenderKey |
|---|---|---|
| SECI | Renew | T-f2ff6c795ea5 |
| SECI | Renew | f2ff6c795ea5 |
| SECI | ENGIE; NLC India; Rays Power | T-c99bd23af287 |
| SECI | ENGIE; NLC India; Rays Power | c99bd23af287 |
| SECI | Waaree; KP Energy; Vena Energy | T-519bbe8b1f67 |
| SECI | Waaree; KP Energy; Vena Energy | 519bbe8b1f67 |
| NTPC | Pace Digitek | T-ba290cae1701 |
| GUVNL | NLC India | T-70cc4438cd19 |
| GUVNL | NLC India | T-bd812b7761b5 |
| GUVNL | Juniper; Jakson | T-948bf847c4a1 |
| GUVNL | Juniper | T-82c8f8303a06 |
| GUVNL | Engie | T-0b5ee904fc8d |
| GUVNL | Jakson | T-add6b5846289 |
| KREDL | Pace Digitek | T-8c923602ce25 |
| MPPMCL | Ayana Renewable | T-8940327e293b |

## Sources that failed
| Source | Status | Error |
|---|---|---|
| SECI_AWARDED | FAILED | fetch failed for https://www.seci.co.in/Bidder/view/tender/results/all-award/lis |
| NHPC | EMPTY | - |

> Records from a failed source are preserved untouched, not marked delisted.

_Confidence: Portal and Manual are official. Press report and AI need the Award URL checked before use._