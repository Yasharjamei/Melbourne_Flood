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
| `gf_titled`, `gf_proposed`, `gf_zoned`, `gf_unzoned` | Greenfield lots by development status, split by area where a parcel crosses a piece boundary |

Only per-piece totals are kept; no site, project or parcel detail.
