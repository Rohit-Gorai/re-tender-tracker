# Renewable tender tracker - 15 Oct 2026

- **349** new tenders
- **1** revised bid dates
- **8** closing within 7 days
- **227** award records across 165 tenders
- **130** financing targets

**Business scope: FY26 onward. Cutoff 1 April 2025.** 769 winner rows in scope; 796 pre-FY26 excluded (retained in tenders.csv).

Primary output: **data/renewable_tender_winners.csv** (one row per tender-award relationship).
- **571** high-severity data-quality flags

## New tenders
| Authority | Tender | Closes |
|---|---|---|
| NTPC | SUPPLY OF SOLAR PV MODULES FOR 2100MW SOLAR PV PROJECT OF NTPC REL AT FATEHGARH  | 2026-10-24 |
| NTPC | Hiring of One No. Vehicle for NTPC REL Anta 300 MW Solar PV Project. (opens in a | 2026-10-17 |
| NTPC | Hiring of 01 No. 4-Wheel Drive Vehicle for Block-VI (300MW) PV Project for 02 Ye | 2026-10-16 |
| NTPC | PROCUREMENT OF ISTS-CONNECTED PUMPED HYDRO ENERGY STORAGE OF 2,000 MW / 12,000 M | 2026-10-19 |
| NTPC | EPC WORKS OF 400KV EHV TRANSMISSION LINE FROM NTPC REL’S PROJECT POOLING SUB-STA | 2026-10-15 |
| NTPC | EPC PACKAGE FOR 2X500 MW GROUND MOUNTED SOLAR PV PROJECT AT KAMBADUR, ANANTAPUR, | 2026-10-30 |
| NTPC | Hiring of 24 Hours Duty (Driver& VEHICLE) FOR NREL, Khavda RE Park, Site for a p | 2026-10-03 |
| NTPC | 650 MVAR SVG PACKAGE FOR REACTIVE POWER COMPENSATION OF WIND PROJECTS IN KARNATA | 2026-10-02 |
| NTPC | SUPPLY AND INSTALLATION OF WIND TURBINE GENERATORS (WTG) FOR ISTS CONNECTED WIND | 2026-09-21 |
| NTPC | Hiring of 1 (One) No. 24 Hours Duty (Driver & Vehicle) for NREL, Khavda RE Park, | 2026-09-28 |
| NTPC | DEVELOPMENT OF WIND ENERGY PROJECT WITH 215MW CAPACITY AT STU SUBSTATION IN MADH | 2026-09-25 |
| NTPC | Hiring of ONE (01) no AC Vehicle (Latest model of Mahindra Scorpio - N or equiva | 2026-09-14 |
| NTPC | Hiring of Latest Model of Mahindra Scorpio (4 WD) or equivalent 4WD Not earlier  | 2026-09-07 |
| NTPC | Hiring of 01 No. 4 - Wheel Drive Vehicle for Block-VI (300MW) PV Project for 02  | 2026-07-25 |
| NTPC | BALANCE OF SYSTEM PACKAGE FOR 110 MW WIND ENERGY PROJECT AT KHAVDA, GUJARAT (ope | 2026-07-26 |
| NTPC | Hiring of Vehicle on Annual basis for 12 Months for 894.3MW Bellary Wind Project | 2026-07-20 |
| NTPC | 400KV SUB STATION PACKAGE FOR 900 MW SOLAR PROJECTS AT MANDSAUR MADHYA PRADESH ( | 2026-07-17 |
| NTPC | EPC PACKAGE FOR DEVELOPMENT OF 600MW (2x300MW) GRID CONNECTED SOLAR PV PROJECTS  | 2026-08-06 |
| NTPC | EPC PACKAGE FOR DEVELOPMENT OF 240 MW/ 960 MWH ISTS CONNECTED BESS AT NTPC REL D | 2026-07-08 |
| NTPC | EPC PACKAGE FOR DEVELOPMENT OF 550 MW/ 2200 MWH ISTS CONNECTED BESS AT NTPC REL  | 2026-06-29 |

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
| NHPC | FAILED | fetch failed for https://www.nhpcindia.com/welcome/tender: HTTPSConnectionPool(h |

> Records from a failed source are preserved untouched, not marked delisted.

_Confidence: Portal and Manual are official. Press report and AI need the Award URL checked before use._