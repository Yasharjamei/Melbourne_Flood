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
| `SLR00CM_ST_2009.zip` | N5IED9 | 1-in-100-year storm tide, 2009 sea level | 795 | 101.1 km² |
| `SLR20CM_ST_2040.zip` | HT9DOF | storm tide (surge +6%) + 20 cm, 2040 | 1,078 | 137.0 km² |
| `SLR47CM_ST_2070.zip` | ZKWZ5D | storm tide (surge +13%) + 47 cm, 2070 | 1,068 | 163.8 km² |
| `SLR82CM_ST_2100.zip` | JQ9CQI | storm tide (surge +19%) + 82 cm, 2100 | 980 | 243.3 km² |

All eight layers of the dataset are now here.

Area added beyond the 2009 baseline: 8.5 km² (2040), 18.0 km² (2070), 41.8 km² (2100). The layers do
not nest perfectly (1.13 km² of the 2009 extent lies outside the 2070 layer, from generalisation), so
each future extent is used as its union with the 2009 baseline. The storm-tide layers nest worse: 12.8 km² of the 2040
storm-tide extent lies outside the 2070 one, so each storm-tide extent is used as the union of itself and every earlier one
(and of the calm layer for the same year).

Limits (from the metadata): a "bathtub" model (no flow or drainage connectivity), generalised for
1:75,000 or coarser, "NOT suitable for assessments of potential risks at property level". Report
results for suburbs, SA2s or councils only. Shapefiles are in EPSG:7855 inside each zip under
`mga2020_55/esrishape/user_polygon/user_polygon-0/COASTS/`.
