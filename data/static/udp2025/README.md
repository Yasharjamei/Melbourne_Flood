# Urban Development Program 2025: per-SA2 summary (supplied by the licence holder)

**Source:** Urban Development Program 2025, Department of Transport and Planning, supplied through
DataShare by the Department of Energy, Environment and Climate Action (DEECA). Orders KR7TGF (Major
Residential Redevelopment Sites, MRS2025) and EQKZCF (Greenfield Residential Land, GF2025).

**Licence: DEECA Data Access Licence Agreement, not CC BY.** The raw UDP files are not in this
repository; they stay on the licence holder's computer in `data/private/udp/` (git-ignored). Whether
the derived summary below may be published is subject to that agreement; permission has been
requested from DEECA (gis.helpdesk@deeca.vic.gov.au).

`udp2025_pieces.csv`, if present, is made by `pipeline/forecast/udp_aggregate.py` from the raw files:

| Column | Meaning |
|---|---|
| `sa2_code_2021`, `lga_code` | The SA2 x council piece (`data/static/sa2_council_pieces_7855.geojson`) |
| `mrs_completed`, `mrs_under_construction`, `mrs_firm`, `mrs_likely`, `mrs_possible` | Dwellings in major redevelopment projects (10+ dwellings) by UDP status, each project at its representative point |
| `mrs_<status>_100`, `mrs_<status>_500` | The same, for projects of 100-499 and of 500+ dwellings only (added 2026-10-28; slower build-out of large apartment schemes) |
| `gf_titled`, `gf_proposed`, `gf_zoned`, `gf_unzoned` | Greenfield lots by development status, split by area where a parcel crosses a piece boundary |

`udp_transition_2017_2025.csv`, if present: the 2017 pipeline (MRS2017, CC BY) followed into UDP 2025, by 2017
status and project size: shares of dwellings completed, still unfinished, or no longer listed in 2025. Rows
covering fewer than 3 projects are left out.

Only per-piece and per-band totals are kept; no site, project or parcel detail. Where a piece holds a single
large project, its size band total equals that project's dwellings, as the status totals already can.
