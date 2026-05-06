"""
generate_data.py — Predictor DC+EV 2025/26
Descarga datos de football-data.co.uk y genera data.json
Ejecutado automaticamente cada noche por GitHub Actions.
"""
import pandas as pd, numpy as np, json, os, sys
from collections import defaultdict
from datetime import datetime

DATA_URL = "https://www.football-data.co.uk/mmz4281/2526/all-euro-data-2025-2026.xlsx"
OUT_FILE = "data.json"
N=12; DECAY=0.85; DC_RHO=-0.0288

SHEET_MAP = {
    'E0':'Premier League','E1':'Championship','E2':'League One','E3':'League Two',
    'SP1':'La Liga','SP2':'Segunda Division','D1':'Bundesliga','D2':'2. Bundesliga',
    'I1':'Serie A','I2':'Serie B','F1':'Ligue 1','F2':'Ligue 2',
    'B1':'Belgian Pro League','N1':'Eredivisie','P1':'Primeira Liga','SC0':'Scottish Prem'
}

def wm(lst,key,n=N):
    vals=[p[key] for p in lst[-n:] if key in p]
    if not vals: return 0.0
    w=[DECAY**(len(vals)-1-i) for i in range(len(vals))]
    return round(sum(v*wi for v,wi in zip(vals,w))/sum(w),2)

def pr(lst,key,n=N):
    last=lst[-n:]
    return round(sum(1 for p in last if p.get(key,False))/len(last),3) if last else 0.0

def scoring_streak(lst):
    ss=0;sn=0
    for p in reversed(lst[-10:]):
        if p.get('scored',False):
            if sn==0: ss+=1
            else: break
        else:
            if ss==0: sn+=1
            else: break
    return ss,sn

def nb_r(data):
    data=data[data>0]
    if len(data)<10: return 11.0
    mu=data.mean();var=data.var()
    return max(1.0,round(float(mu**2/max(0.01,var-mu)),2))

print(f"Descargando {DATA_URL}...")
try:
    xl=pd.ExcelFile(DATA_URL)
except Exception as e:
    print(f"ERROR: {e}")
    if os.path.exists(OUT_FILE): print("Usando existente"); sys.exit(0)
    sys.exit(1)

all_frames=[]; league_teams={}
for sheet,league in SHEET_MAP.items():
    if sheet not in xl.sheet_names: continue
    df=xl.parse(sheet).dropna(subset=['HomeTeam','FTHG','FTAG'])
    for col in ['FTHG','FTAG','HS','AS','HST','AST','HF','AF','HC','AC','HY','AY','HR','AR','HTHG','HTAG']:
        if col in df.columns: df[col]=pd.to_numeric(df[col],errors='coerce').fillna(0)
    try: df['Date']=pd.to_datetime(df['Date'],dayfirst=True,errors='coerce')
    except: pass
    df['Liga']=league; all_frames.append(df)
    league_teams[league]=sorted(set(df['HomeTeam'].tolist()+df['AwayTeam'].tolist()))
    print(f"  {league}: {len(df)} partidos")

big=pd.concat(all_frames,ignore_index=True)

ht_factors={}
for liga in SHEET_MAP.values():
    d=big[big['Liga']==liga]
    if not len(d): continue
    ft=d['FTHG'].mean()+d['FTAG'].mean()
    ht=(d['HTHG'].mean()+d['HTAG'].mean()) if 'HTHG' in d.columns else ft*0.44
    ht_factors[liga]=round(float(ht/ft) if ft>0 else 0.44,3)

league_avgs={}; league_ref_avgs={}
for liga in SHEET_MAP.values():
    d=big[big['Liga']==liga]
    if not len(d): continue
    league_avgs[liga]={'hg':float(d['FTHG'].mean()),'ag':float(d['FTAG'].mean()),
        'hc':float(d['HC'].mean()) if 'HC' in d.columns else 5.5,
        'ac':float(d['AC'].mean()) if 'AC' in d.columns else 4.5,
        'hy':float(d['HY'].mean()) if 'HY' in d.columns else 1.8,
        'ay':float(d['AY'].mean()) if 'AY' in d.columns else 2.0}
    league_ref_avgs[liga]={
        'avg_y':round(float(d['HY'].mean()+d['AY'].mean()),2) if 'HY' in d.columns else 3.8,
        'avg_r':round(float(d['HR'].mean()+d['AR'].mean()),3) if 'HR' in d.columns else 0.15}

nb_params={'r_corners_h':nb_r(big['HC'].values) if 'HC' in big.columns else 11.0,
           'r_corners_a':nb_r(big['AC'].values) if 'AC' in big.columns else 10.9,
           'r_cards':15.0}

ref_stats=defaultdict(lambda:{'n':0,'hy':0,'ay':0,'hr':0,'ar':0})
for _,r in big.iterrows():
    ref=str(r.get('Referee','')).strip()
    if not ref or ref=='nan': continue
    ref_stats[ref]['n']+=1
    for k,col in [('hy','HY'),('ay','AY'),('hr','HR'),('ar','AR')]:
        ref_stats[ref][k]+=float(r.get(col,0) or 0)
refs={ref:{'n':s['n'],'avg_y':round((s['hy']+s['ay'])/s['n'],2),
           'avg_r':round((s['hr']+s['ar'])/s['n'],3),
           'avg_y_h':round(s['hy']/s['n'],2),'avg_y_a':round(s['ay']/s['n'],2)}
      for ref,s in ref_stats.items() if s['n']>=3}

team_home=defaultdict(list); team_away=defaultdict(list); team_league={}
for _,r in big.iterrows():
    h,a,liga=r['HomeTeam'],r['AwayTeam'],r['Liga']
    team_league[h]=liga; team_league[a]=liga
    ftr=str(r.get('FTR','')).strip()
    fhg=float(r['FTHG']); fag=float(r['FTAG'])
    hhg=float(r.get('HTHG',0) or 0); hag=float(r.get('HTAG',0) or 0)
    hc=float(r.get('HC',0) or 0); ac=float(r.get('AC',0) or 0)
    hy=float(r.get('HY',0) or 0); ay=float(r.get('AY',0) or 0)
    hr=float(r.get('HR',0) or 0); ar=float(r.get('AR',0) or 0)
    base_h={'gf':fhg,'gc':fag,'ht_gf':hhg,'ht_gc':hag,'ht_win':hhg>hag,
        'clean_sheet':fag==0,'failed_score':fhg==0,'comeback':fhg>=fag and hhg<hag,
        'ht_over15':(hhg+hag)>=2,'goals_2h':(fhg-hhg)+(fag-hag),
        'shots':float(r.get('HS',0) or 0),'shotsT':float(r.get('HST',0) or 0),
        'corners':hc,'corners_a':ac,'yellow':hy,'yellow_a':ay,
        'red':hr,'red_a':ar,'fouls':float(r.get('HF',0) or 0),
        'fouls_a':float(r.get('AF',0) or 0),
        'result':'G' if ftr=='H' else('E' if ftr=='D' else 'P'),'scored':fhg>0}
    team_home[h].append(base_h)
    team_away[a].append({**base_h,'gf':fag,'gc':fhg,'ht_gf':hag,'ht_gc':hhg,
        'ht_win':hag>hhg,'clean_sheet':fhg==0,'failed_score':fag==0,
        'comeback':fag>=fhg and hag<hhg,'goals_2h':(fag-hag)+(fhg-hhg),
        'shots':float(r.get('AS',0) or 0),'shotsT':float(r.get('AST',0) or 0),
        'corners':ac,'corners_a':hc,'yellow':ay,'yellow_a':hy,
        'red':ar,'red_a':hr,'fouls':float(r.get('AF',0) or 0),
        'fouls_a':float(r.get('HF',0) or 0),
        'result':'G' if ftr=='A' else('E' if ftr=='D' else 'P'),'scored':fag>0})

def calc_stats(team):
    liga=team_league.get(team,'')
    la=league_avgs.get(liga,{'hg':1.4,'ag':1.1,'hc':5.5,'ac':4.5,'hy':1.8,'ay':2.0})
    casa=team_home[team]; fuera=team_away[team]
    gf_c=wm(casa,'gf');gc_c=wm(casa,'gc');gf_f=wm(fuera,'gf');gc_f=wm(fuera,'gc')
    att_h=gf_c/la['hg'] if la['hg']>0 else 1.0
    def_h=gc_c/la['ag'] if la['ag']>0 else 1.0
    att_a=gf_f/la['ag'] if la['ag']>0 else 1.0
    def_a=gc_f/la['hg'] if la['hg']>0 else 1.0
    all_h=[p['gf'] for p in team_home[team]];all_a=[p['gf'] for p in team_away[team]]
    all_gc_h=[p['gc'] for p in team_home[team]];all_gc_a=[p['gc'] for p in team_away[team]]
    if len(all_h)>N: att_h=att_h*0.7+(sum(all_h)/len(all_h)/la['hg'])*0.3
    if len(all_a)>N: att_a=att_a*0.7+(sum(all_a)/len(all_a)/la['ag'])*0.3
    if len(all_gc_h)>N: def_h=def_h*0.7+(sum(all_gc_h)/len(all_gc_h)/la['ag'])*0.3
    if len(all_gc_a)>N: def_a=def_a*0.7+(sum(all_gc_a)/len(all_gc_a)/la['hg'])*0.3
    co_c=wm(casa,'corners');co_f=wm(fuera,'corners')
    coa_c=wm(casa,'corners_a');coa_f=wm(fuera,'corners_a')
    att_co_h=co_c/la['hc'] if la['hc']>0 else 1.0
    def_co_h=coa_c/la['ac'] if la['ac']>0 else 1.0
    att_co_a=co_f/la['ac'] if la['ac']>0 else 1.0
    def_co_a=coa_f/la['hc'] if la['hc']>0 else 1.0
    yw_c=wm(casa,'yellow');yw_f=wm(fuera,'yellow')
    att_y_h=yw_c/la['hy'] if la['hy']>0 else 1.0
    att_y_a=yw_f/la['ay'] if la['ay']>0 else 1.0
    l5h=casa[-3:];l5a=fuera[-3:]
    pts=sum(3 if p['result']=='G' else(1 if p['result']=='E' else 0) for p in l5h+l5a)
    mxp=len(l5h+l5a)*3; rf=0.85+0.30*(pts/mxp) if mxp>0 else 1.0
    ss_h,sn_h=scoring_streak(casa); ss_a,sn_a=scoring_streak(fuera)
    return {'liga':liga,'att_h':round(att_h,3),'def_h':round(def_h,3),
        'att_a':round(att_a,3),'def_a':round(def_a,3),'racha':round(rf,3),
        'gf_c':gf_c,'gc_c':gc_c,'gf_f':gf_f,'gc_f':gc_f,
        'sh_c':wm(casa,'shots'),'sh_f':wm(fuera,'shots'),
        'sht_c':wm(casa,'shotsT'),'sht_f':wm(fuera,'shotsT'),
        'co_c':co_c,'co_f':co_f,'coa_c':coa_c,'coa_f':coa_f,
        'att_co_h':round(att_co_h,3),'def_co_h':round(def_co_h,3),
        'att_co_a':round(att_co_a,3),'def_co_a':round(def_co_a,3),
        'att_y_h':round(att_y_h,3),'att_y_a':round(att_y_a,3),
        'yw_c':yw_c,'yw_f':yw_f,
        'ywa_c':wm(casa,'yellow_a'),'ywa_f':wm(fuera,'yellow_a'),
        'rd_c':wm(casa,'red'),'rd_f':wm(fuera,'red'),
        'rda_c':wm(casa,'red_a'),'rda_f':wm(fuera,'red_a'),
        'fo_c':wm(casa,'fouls'),'fo_f':wm(fuera,'fouls'),
        'foa_c':wm(casa,'fouls_a'),'foa_f':wm(fuera,'fouls_a'),
        'sf_h':pr(casa,'result'),'sf_a':pr(fuera,'result'),
        'cs_h':pr(casa,'clean_sheet'),'cs_a':pr(fuera,'clean_sheet'),
        'fts_h':pr(casa,'failed_score'),'fts_a':pr(fuera,'failed_score'),
        'cb_h':pr(casa,'comeback'),'cb_a':pr(fuera,'comeback'),
        'ht_w_h':pr(casa,'ht_win'),'ht_w_a':pr(fuera,'ht_win'),
        'hto_h':pr(casa,'ht_over15'),'hto_a':pr(fuera,'ht_over15'),
        'ag2_h':wm(casa,'goals_2h'),'ag2_a':wm(fuera,'goals_2h'),
        'ahtg_h':wm(casa,'ht_gf'),'ahtg_a':wm(fuera,'ht_gf'),
        'ss_h':ss_h,'sn_h':sn_h,'ss_a':ss_a,'sn_a':sn_a,
        'n_casa':len(casa),'n_fuera':len(fuera)}

print("Calculando estadisticas...")
all_teams=sorted(team_league.keys())
stats={t:calc_stats(t) for t in all_teams}

h2h=defaultdict(list)
for _,r in big.iterrows():
    h,a=r['HomeTeam'],r['AwayTeam']
    key=tuple(sorted([h,a]))
    h2h[key].append([h,a,int(r['FTHG']),int(r['FTAG']),str(r.get('Date',''))[:7]])
h2h_data={'|'.join(k):v[-6:] for k,v in h2h.items() if len(v)>=2}

racha_data={}
for t in all_teams:
    hr=[p['result'] for p in team_home[t]]; ar=[p['result'] for p in team_away[t]]
    racha_data[t]=''.join((hr[-4:]+ar[-3:])[-6:])

standings={}
for sheet,league in SHEET_MAP.items():
    d=big[big['Liga']==league].copy()
    if not len(d): continue
    d['FTHG']=d['FTHG'].astype(int); d['FTAG']=d['FTAG'].astype(int)
    ts=set(d['HomeTeam'].tolist()+d['AwayTeam'].tolist())
    tb={t:{'PJ':0,'G':0,'E':0,'P':0,'GF':0,'GC':0,'Pts':0} for t in ts}
    for _,r in d.iterrows():
        h,a,hg,ag=r['HomeTeam'],r['AwayTeam'],int(r['FTHG']),int(r['FTAG'])
        ftr=str(r.get('FTR','')).strip()
        tb[h]['PJ']+=1;tb[h]['GF']+=hg;tb[h]['GC']+=ag
        tb[a]['PJ']+=1;tb[a]['GF']+=ag;tb[a]['GC']+=hg
        if ftr=='H': tb[h]['G']+=1;tb[h]['Pts']+=3;tb[a]['P']+=1
        elif ftr=='A': tb[a]['G']+=1;tb[a]['Pts']+=3;tb[h]['P']+=1
        else: tb[h]['E']+=1;tb[h]['Pts']+=1;tb[a]['E']+=1;tb[a]['Pts']+=1
    st=sorted(tb.items(),key=lambda x:(-x[1]['Pts'],-(x[1]['GF']-x[1]['GC']),-x[1]['GF']))
    standings[league]=[[i+1,t,s['PJ'],s['G'],s['E'],s['P'],s['GF'],s['GC'],s['GF']-s['GC'],s['Pts']] for i,(t,s) in enumerate(st)]

output={'ligas':list(SHEET_MAP.values()),'equipos':league_teams,'stats':stats,
    'league_avgs':league_avgs,'league_ref_avgs':league_ref_avgs,'refs':refs,
    'h2h':h2h_data,'racha':racha_data,'standings':standings,
    'ht_factors':ht_factors,'nb_params':nb_params,
    'gp':{t:{k:stats[t][k] for k in ['sf_h','sf_a','cs_h','cs_a','fts_h','fts_a',
        'cb_h','cb_a','ht_w_h','ht_w_a','hto_h','hto_a','ag2_h','ag2_a',
        'ahtg_h','ahtg_a','ss_h','sn_h','ss_a','sn_a',
        'att_co_h','def_co_h','att_co_a','def_co_a','att_y_h','att_y_a']}
        for t in all_teams},
    'dc_rho':DC_RHO,'updated':datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    'n_partidos':len(big),'n_equipos':len(all_teams)}

out=json.dumps(output,ensure_ascii=False,separators=(',',':'))
with open(OUT_FILE,'w',encoding='utf-8') as f: f.write(out)
print(f"\n✅ {OUT_FILE}: {len(all_teams)} equipos | {len(big)} partidos | {len(out)//1024}KB")
