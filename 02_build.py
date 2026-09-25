"""Build SA1 attributes, flood-overlay shares and a 50 m apportionment grid.
Run from repo root after pipeline/01_fetch.sh. Output: data/processed/data.json"""
import os
os.makedirs('data/interim',exist_ok=True); os.makedirs('data/processed',exist_ok=True)
import geopandas as _g
_lga=_g.read_file('data/raw/lga.geojson').to_crs(7855); _sa=_g.read_file('data/raw/sa1_bbox.geojson').to_crs(7855)
_p=_sa.copy(); _p['geometry']=_sa.representative_point()
_j=_g.sjoin(_p,_lga[['lga_name_2021','geometry']],predicate='within')
_k=_sa.loc[_j.index].copy(); _k['lga']=_j['lga_name_2021'].values
_k.to_crs(4326).to_file('data/interim/sa1_study.geojson',driver='GeoJSON')
import pandas as pd, geopandas as gpd, numpy as np, json
from shapely.geometry import box
from shapely.ops import unary_union
G=lambda t: pd.read_csv(f'data/raw/gcp/2021Census_{t}_VIC_SA1.csv',dtype={'SA1_CODE_2021':str}).set_index('SA1_CODE_2021')
sa=gpd.read_file('data/interim/sa1_study.geojson').to_crs(7855)
codes=sa.sa1_code_2021.tolist()
g4=G('G04A').join(G('G04B'),rsuffix='_b').loc[codes]
bands=['0_4','5_9','10_14','15_19','20_24','25_29','30_34','35_39','40_44','45_49','50_54','55_59','60_64','65_69','70_74','75_79','80_84']
def band(sx):
    cols=[g4[f'Age_yr_{b}_{sx}'] for b in bands]
    cols.append(g4[f'Age_yr_85_89_{sx}']+g4[f'Age_yr_90_94_{sx}']+g4[f'Age_yr_95_99_{sx}']+g4[f'Age_yr_100_yr_over_{sx}'])
    return np.stack(cols,1)
M,F=band('M'),band('F')
g1=G('G01').loc[codes]; g2=G('G02').loc[codes]; g18=G('G18').loc[codes]; g20=G('G20A').join(G('G20B'),rsuffix='_b').loc[codes]
g46=G('G46B').loc[codes]; g13=G('G13E').loc[codes]; g34=G('G34').loc[codes]; g36=G('G36').loc[codes]
print([c for c in g20.columns if c.startswith('P_1m_cond_Tot_Tot') or c=='P_Tot_Tot' or c.startswith('P_cond_NS_Tot')])
fl=gpd.read_file('data/raw/flood.geojson').to_crs(7855)
riv=unary_union(fl[fl.scheme_code.isin(['LSIO','FO'])].geometry); sbo=unary_union(fl[fl.scheme_code=='SBO'].geometry)
sa['area']=sa.area
sa['riv']=sa.geometry.intersection(riv).area/sa.area
sa['sbo']=sa.geometry.intersection(sbo).area/sa.area
recs=[]
for i,c in enumerate(codes):
    r=dict(id=c,sa2=sa.sa2_name_2021.iloc[i],lga=sa.lga.iloc[i],km2=round(sa.area.iloc[i]/1e6,4),
      M=M[i].astype(int).tolist(),F=F[i].astype(int).tolist(),
      pop=int(g1.loc[c,'Tot_P_P']),
      nfa=int(g18.loc[c,'P_Tot_Need_for_assistance']),nfa_d=int(g18.loc[c,'P_Tot_Tot']-g18.loc[c,'P_Tot_Need_for_assistance_ns']),
      ltc=int(g20.loc[c,'P_1m_cond_Tot_Tot']),ltc_d=int(g20.loc[c,'P_Tot_Tot']-g20.loc[c,'P_cond_NS_Tot']),
      emp=int(g46.loc[c,'P_Tot_Emp_Tot']),unemp=int(g46.loc[c,'P_Tot_Unemp_Tot']),lf=int(g46.loc[c,'P_Tot_LF_Tot']),
      eng=int(g13.loc[c,'P_Tot_UOLSE_NWorNAA']),eng_d=int(g13.loc[c,'P_Tot_Tot']-g13.loc[c,'P_Tot_NS']),
      car0=int(g34.loc[c,'Num_MVs_per_dweling_0_MVs']),car_d=int(g34.loc[c,'Num_MVs_per_dweling_Tot']),
      d_house=int(g36.loc[c,'OPDs_Separate_house_Dwellings']),d_semi=int(g36.loc[c,'OPDs_SD_r_t_h_th_Tot_Dwgs']),
      d_flatlow=int(g36.loc[c,'OPDs_F_ap_I_1or2_sty_blk_Ds']+g36.loc[c,'OPDs_F_ap_I_3_sty_blk_Dwgs']+g36.loc[c,'OPDs_Flt_apt_Att_house_Ds']),
      d_flathigh=int(g36.loc[c,'OPDs_F_ap_I_4to8_sty_blk_Ds']+g36.loc[c,'OPDs_F_ap_I_9_m_sty_blk_Ds']),
      d_other=int(g36.loc[c,'OPDs_Other_dwelling_Tot_Dwgs']),
      inc=int(g2.loc[c,'Median_tot_hhd_inc_weekly']),
      riv=round(float(sa.riv.iloc[i]),4),sbo=round(float(sa.sbo.iloc[i]),4))
    recs.append(r)
print(len(recs), sum(r['pop'] for r in recs), sum(sum(r['M'])+sum(r['F']) for r in recs))
# grid 50 m
cell=50
xmin,ymin,xmax,ymax=sa.total_bounds
xs=np.arange(xmin+cell/2,xmax,cell); ys=np.arange(ymin+cell/2,ymax,cell)
X,Y=np.meshgrid(xs,ys); pts=gpd.GeoDataFrame(geometry=gpd.points_from_xy(X.ravel(),Y.ravel()),crs=7855)
sa=sa.reset_index(drop=True)
j=gpd.sjoin(pts,sa[['sa1_code_2021','geometry']],predicate='within'); print(j.columns.tolist())
j['riv']=j.geometry.intersects(riv).values
j['sbo']=j.geometry.intersects(sbo).values
cnt=j.groupby('index_right').size()
print('cells',len(j),'sa1 with 0 cells',len(set(range(len(sa)))-set(cnt.index)))
# store cells relative to origin in metres (int), sa1 idx, flags
cells=[[int(round(p.x-xmin)),int(round(p.y-ymin)),int(k),int(a)+2*int(b)] for p,k,a,b in zip(j.geometry,j.index_right,j.riv,j.sbo)]
# small SA1s with no cell: add centroid cell
missing=set(range(len(sa)))-set(cnt.index)
for k in missing:
    p=sa.geometry.iloc[k].representative_point(); cells.append([int(round(p.x-xmin)),int(round(p.y-ymin)),int(k),int(p.intersects(riv))+2*int(p.intersects(sbo))])
# geometry for drawing: simplify, to 4326
geo=sa[['geometry']].copy(); geo['geometry']=geo.simplify(4); geo=geo.to_crs(4326)
feat=[json.loads(gpd.GeoSeries([g]).to_json())['features'][0]['geometry'] for g in geo.geometry]
fgeo=gpd.GeoDataFrame(geometry=[riv.simplify(4),sbo.simplify(4)],crs=7855).to_crs(4326)
lga=gpd.read_file('data/raw/lga.geojson')
def rnd(o):
    if isinstance(o,list): return [rnd(x) for x in o]
    if isinstance(o,float): return round(o,5)
    return o
# cells stored as lon/lat for the browser
cp=gpd.GeoSeries(gpd.points_from_xy([c[0]+xmin for c in cells],[c[1]+ymin for c in cells]),crs=7855).to_crs(4326)
cells=[[round(q.x,5),round(q.y,5),c[2],c[3]] for q,c in zip(cp,cells)]
out=dict(cell=cell,sa1=recs,
  shapes=[{'type':g['type'],'coordinates':rnd(g['coordinates'])} for g in feat],
  riv=rnd(json.loads(fgeo.iloc[[0]].to_json())['features'][0]['geometry']),
  sbo=rnd(json.loads(fgeo.iloc[[1]].to_json())['features'][0]['geometry']),
  lga=[{'name':r.lga_name_2021,'g':rnd(json.loads(gpd.GeoSeries([r.geometry.simplify(0.00005)]).to_json())['features'][0]['geometry'])} for r in lga.itertuples()],
  cells=cells)
s=json.dumps(out,separators=(',',':'))
open('data/processed/data.json','w').write(s); print('bytes',len(s))
