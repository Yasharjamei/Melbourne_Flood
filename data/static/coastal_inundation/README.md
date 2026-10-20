# Victorian Coastal Inundation Dataset (sea-level rise)

DataShare orders, unchanged, clipped to the 31 study councils (`boundary.yml`, MGA2020 zone 55).
Owner: Department of Energy, Environment and Climate Action. Licence: CC BY 4.0 (in each zip).
Committed because DataShare delivery links expire, so CI cannot download them.

| File | Order | Scenario | Polygons | Area in study councils |
|---|---|---|---|---|
| `SLR20CM_2040.zip` | ICA0IN | +20 cm sea level, 2040 | 631 | 29.2 km² |
| `SLR47CM_2070.zip` | QBY4LJ | +47 cm sea level, 2070 | 657 | 37.7 km² |
| `SLR82CM_2100.zip` | K0XLIZ | +82 cm sea level, 2100 | 840 | 62.6 km² |

Still to order (same clip): `SLR00CM_2009` (present-day baseline) and the storm-tide layers
`SLR00CM_ST_2009`, `SLR20CM_ST_2040`, `SLR47CM_ST_2070`, `SLR82CM_ST_2100`.

Limits (from the metadata): a "bathtub" model (no flow or drainage connectivity), generalised for
1:75,000 or coarser, "NOT suitable for assessments of potential risks at property level". Report
results for suburbs, SA2s or councils only. Shapefiles are in EPSG:7855 inside each zip under
`mga2020_55/esrishape/user_polygon/user_polygon-0/COASTS/`.
