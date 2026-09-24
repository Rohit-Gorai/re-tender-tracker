# Renewable tender tracker - 24 Sep 2026

- **2** new tenders
- **0** revised bid dates
- **13** closing within 7 days
- **202** award records across 142 tenders
- **112** financing targets

**Business scope: FY26 onward. Cutoff 1 April 2025.** 666 winner rows in scope; 520 pre-FY26 excluded (retained in tenders.csv).

Primary output: **data/renewable_tender_winners.csv** (one row per tender-award relationship).
- **571** high-severity data-quality flags

## New tenders
| Authority | Tender | Closes |
|---|---|---|
| SECI | RfS for Green Ammonia (Mode-2A-Tranche-II) | 2026-10-27 |
| NTPC | Hiring of 24 Hours Duty (Driver& VEHICLE) FOR NREL, Khavda RE Park, Site for a p | 2026-10-03 |

## Financing targets (top 10 by capacity)
| # | Winner | MW | Tech | COD | Confidence |
|---|---|---|---|---|---|
| 1 | Renew | 8600 | Solar + Storage | 2028-06-26 | Press report - verify |
| 2 | Adani Power; Renew | 2500 | Round-the-Clock / CfD / Trading | 2028-04-07 | Press report - verify |
| 3 | Adani Power | 2500 | Round-the-Clock / CfD / Trading | 2028-04-06 | Press report - verify |
| 4 | ReNew | 2000 | Solar | 2027-04-24 | Press report - verify |
| 5 | Engie | 2000 | Energy Storage (BESS) | 2027-05-18 | Press report - verify |
| 6 | SAEL | 2000 | Solar + Storage | 2027-11-08 | Press report - verify |
| 7 | Adani Power | 1600 | Unclassified | 2027-09-11 | Press report - verify |
| 8 | Adani Power | 1600 | Unclassified | 2027-09-11 | Press report - verify |
| 9 | Adani Power | 1600 | Unclassified | 2027-09-12 | Press report - verify |
| 10 | Adani Power | 1600 | Unclassified | 2027-09-11 | Press report - verify |

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
| SECI | Greenko; Torrent; Tata Power | T-2b32a0fbd349 |
| SECI | Greenko; Torrent; Tata Power | 2b32a0fbd349 |
| GUVNL | NLC India | T-70cc4438cd19 |
| GUVNL | NLC India | T-bd812b7761b5 |
| GUVNL | Juniper; Jakson | T-948bf847c4a1 |
| GUVNL | Juniper | T-82c8f8303a06 |
| GUVNL | Engie | T-0b5ee904fc8d |
| GUVNL | Jakson | T-add6b5846289 |

## Sources that failed
| Source | Status | Error |
|---|---|---|
| SECI_AWARDED | FAILED | fetch failed for https://www.seci.co.in/Bidder/view/tender/results/all-award/lis |
| NHPC | EMPTY | - |

> Records from a failed source are preserved untouched, not marked delisted.

_Confidence: Portal and Manual are official. Press report and AI need the Award URL checked before use._