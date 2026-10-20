# Victorian Coastal Inundation Dataset (sea-level rise)

DataShare orders, unchanged, clipped to the 31 study councils (`boundary.yml`, MGA2020 zone 55).
Owner: Department of Energy, Environment and Climate Action. Licence: CC BY 4.0 (in each zip).
Committed because DataShare delivery links expire, so CI cannot download them.

| File | Order | Scenario | Polygons | Area in study councils |
|---|---|---|---|---|
| `SLR00CM_2009.zip` | 21WL2D | present-day (2009) sea level, the baseline | 492 | 20.8 km² |
| `SLR20CM_2040.zip` | ICA0IN | +20 cm sea level, 2040 | 631 | 29.2 km² |
| `SLR47CM_2070.zip` | QBY4LJ | +47 cm sea level, 2070 | 657 | 37.7 km² |
| `SLR82CM_2100.zip` | K0XLIZ | +82 cm sea level, 2100 | 840 | 62.6 km² |

Still to order (same clip): the storm-tide layers
`SLR00CM_ST_2009`, `SLR20CM_ST_2040`, `SLR47CM_ST_2070`, `SLR82CM_ST_2100`.

Area added beyond the 2009 baseline: 8.5 km² (2040), 18.0 km² (2070), 41.8 km² (2100). The layers do
not nest perfectly (1.13 km² of the 2009 extent lies outside the 2070 layer, from generalisation), so
each future extent is used as its union with the 2009 baseline.

Limits (from the metadata): a "bathtub" model (no flow or drainage connectivity), generalised for
1:75,000 or coarser, "NOT suitable for assessments of potential risks at property level". Report
results for suburbs, SA2s or councils only. Shapefiles are in EPSG:7855 inside each zip under
`mga2020_55/esrishape/user_polygon/user_polygon-0/COASTS/`.
