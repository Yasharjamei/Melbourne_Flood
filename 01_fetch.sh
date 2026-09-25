#!/usr/bin/env bash
# Downloads all public inputs into data/raw. Run from repo root.
set -euo pipefail
mkdir -p data/raw data/raw/gcp && cd data/raw
# LGA boundaries (ASGS 2021) for Maribyrnong + Moonee Valley
curl -s "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/LGA/MapServer/0/query?where=lga_name_2021+in+('Maribyrnong','Moonee+Valley')+and+state_code_2021='2'&outFields=lga_code_2021,lga_name_2021&outSR=4326&f=geojson" -o lga.geojson
# SA1s intersecting the study bbox (filtered to LGAs in 02_build.py)
curl -s "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SA1/MapServer/0/query?geometry=144.835,-37.83,144.945,-37.705&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=sa1_code_2021,sa2_name_2021,sa3_name_2021,area_albers_sqkm&outSR=4326&f=geojson&resultRecordCount=2000" -o sa1_bbox.geojson
# Census 2021 GCP DataPack, SA1, Victoria (~100 MB)
curl -sL -A "Mozilla/5.0" "https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SA1_for_VIC_short-header.zip" -o gcp.zip
unzip -o -q -j gcp.zip "*G01_VIC_SA1.csv" "*G02_VIC_SA1.csv" "*G04A_VIC_SA1.csv" "*G04B_VIC_SA1.csv" "*G13E_VIC_SA1.csv" "*G18_VIC_SA1.csv" "*G20A_VIC_SA1.csv" "*G20B_VIC_SA1.csv" "*G34_VIC_SA1.csv" "*G36_VIC_SA1.csv" "*G46B_VIC_SA1.csv" -d gcp
# Planning scheme flood overlays (LSIO, FO, SBO), Vicmap Planning WFS
curl -s -G "https://opendata.maps.vic.gov.au/geoserver/wfs" --data-urlencode "service=WFS" --data-urlencode "version=2.0.0" --data-urlencode "request=GetFeature" --data-urlencode "typeNames=open-data-platform:plan_overlay" --data-urlencode "outputFormat=application/json" --data-urlencode "srsName=EPSG:4326" --data-urlencode "CQL_FILTER=scheme_code IN ('LSIO','FO','SBO') AND lga IN ('MARIBYRNONG','MOONEE VALLEY')" -o flood.geojson
echo "done"
