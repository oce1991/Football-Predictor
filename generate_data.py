"""
generate_data.py
Descarga el xlsx de football-data.co.uk y genera data.json con todos los
estadísticos necesarios para el predictor.

Ejecutado automáticamente cada día a las 00:00 por GitHub Actions.
"""

import pandas as pd
import numpy as np
import json
import re
import unicodedata
import sys
import os
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────────────────────────
DATA_URL = "https://www.football-data.co.uk/mmz4281/2526/all-euro-data-2025-2026.xlsx"
OUT_FILE = "data.json"
N        = 12     # últimos N partidos para promedios ponderados
DECAY    = 0.85   # factor de decaimiento (partido reciente pesa más)
DC_RHO   = -0.0288  # Dixon-Coles rho calibrado

SHEET_MAP = {
    'E0':'Premier League','E1':'Championship','E2':'League One','E3':'League Two',
    'SP1':'La Liga','SP2':'Segunda División','D1':'Bundesliga','D2':'2. Bundesliga',
    'I1':'Serie A','I2':'Serie B','F1':'Ligue 1','F2':'Ligue 2',
    'B1':'Belgian Pro League','N1':'Eredivisie','P1':'Primeira Liga','SC0':'Scottish Prem'
}

STAT_COLS = ['HomeTeam','AwayTeam','FTR','FTHG','FTAG',
             'HS','AS','HST','AST','HF','AF','HC','AC',
             'HY','AY','HR','AR','HTHG','HTAG']

# ── HELPERS ───────────────────────────────────────────────────────────────────
def safe_name(s):
    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ascii','ignore').decode('ascii')
    return re.sub(r'[^A-Za-z0-9_]','_',s)

def weighted_avg(values, decay=DECAY):
    if not values: return 0.0
    n = len(values)
    weights = [decay**(n-1-i) for i in range(n)]
    total_w = sum(weights)
    return sum(v*w for v,w in zip(values,weights)) / total_w if total_w > 0 else 0.0

def w_mean(lst, key, n=N, decay=DECAY):
    vals = [p[key] for p in lst[-n:] if key in p]
    return round(weighted_avg(vals, decay), 2) if vals else 0.0

def pct_stat(lst, key, n=N):
    last = lst[-n:]
    if not last: return 0.0
    return round(sum(1 for p in last if p.get(key, False)) / len(last), 3)

# ── DOWNLOAD DATA ─────────────────────────────────────────────────────────────
print(f"Descargando datos de {DATA_URL}...")
try:
    all_frames = []
    league_teams = {}

    xl = pd.ExcelFile(DATA_URL)

    for sheet, league in SHEET_MAP.items():
        if sheet not in xl.sheet_names:
            print(f"  Hoja {sheet} no encontrada, saltando...")
            continue
        df = xl.parse(sheet).dropna(subset=['HomeTeam','FTHG','FTAG'])
        for col in STAT_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df['Liga'] = league
        avail = [c for c in STAT_COLS if c in df.columns] + ['Liga']
        all_frames.append(df[avail].copy())
        teams = sorted(set(df['HomeTeam'].tolist() + df['AwayTeam'].tolist()))
        league_teams[league] = teams
        print(f"  {league}: {len(df)} partidos, {len(teams)} equipos")

except Exception as e:
    print(f"Error descargando datos: {e}")
    # Si falla la descarga, intentar usar data.json existente
    if os.path.exists(OUT_FILE):
        print("Usando data.json existente")
        sys.exit(0)
    sys.exit(1)

big = pd.concat(all_frames, ignore_index=True)
print(f"\nTotal partidos: {len(big)}")

# ── LEAGUE AVERAGES ───────────────────────────────────────────────────────────
league_avgs = {}
for liga in SHEET_MAP.values():
    d = big[big['Liga'] == liga]
    if len(d) == 0:
        continue
    league_avgs[liga] = {
        'hg':  float(d['FTHG'].mean()),
        'ag':  float(d['FTAG'].mean()),
        'hc':  float(d['HC'].mean())  if 'HC'  in d.columns else 5.5,
        'ac':  float(d['AC'].mean())  if 'AC'  in d.columns else 4.5,
        'hy':  float(d['HY'].mean())  if 'HY'  in d.columns else 1.8,
        'ay':  float(d['AY'].mean())  if 'AY'  in d.columns else 2.0,
        'hs':  float(d['HS'].mean())  if 'HS'  in d.columns else 13.0,
        'as_': float(d['AS'].mean())  if 'AS'  in d.columns else 10.5,
        'hst': float(d['HST'].mean()) if 'HST' in d.columns else 4.5,
        'ast': float(d['AST'].mean()) if 'AST' in d.columns else 3.5,
    }

# ── TEAM DATA ─────────────────────────────────────────────────────────────────
team_home = defaultdict(list)
team_away = defaultdict(list)
team_league_map = {}

for _, r in big.iterrows():
    h, a, liga = r['HomeTeam'], r['AwayTeam'], r['Liga']
    team_league_map[h] = liga
    team_league_map[a] = liga
    ftr  = str(r.get('FTR','')).strip()
    fhg  = float(r['FTHG']); fag = float(r['FTAG'])
    hhg  = float(r.get('HTHG', 0) or 0)
    hag  = float(r.get('HTAG', 0) or 0)
    hs   = float(r.get('HS',0) or 0); a_s = float(r.get('AS',0) or 0)
    hst  = float(r.get('HST',0) or 0); ast = float(r.get('AST',0) or 0)
    hc   = float(r.get('HC',0) or 0); ac  = float(r.get('AC',0) or 0)
    hy   = float(r.get('HY',0) or 0); ay  = float(r.get('AY',0) or 0)
    hr_  = float(r.get('HR',0) or 0); ar  = float(r.get('AR',0) or 0)
    hf   = float(r.get('HF',0) or 0); af  = float(r.get('AF',0) or 0)

    # xG proxy (shots on target × 0.33 + shots × 0.08)
    xg_h = hst*0.33 + hs*0.08
    xg_a = ast*0.33 + a_s*0.08

    team_home[h].append({
        'gf':fhg,'gc':fag,'xg':xg_h,'xga':xg_a,
        'ht_gf':hhg,'ht_gc':hag,
        'ht_win':hhg>hag,'ht_draw':hhg==hag,
        'clean_sheet':fag==0,'failed_score':fhg==0,
        'comeback':fhg>=fag and hhg<hag,
        'ht_over15':(hhg+hag)>=2,
        'goals_2h':(fhg-hhg)+(fag-hag),
        'shots':hs,'shotsT':hst,'corners':hc,'corners_a':ac,
        'yellow':hy,'yellow_a':ay,'red':hr_,'red_a':ar,'fouls':hf,'fouls_a':af,
        'result':'G' if ftr=='H' else ('E' if ftr=='D' else 'P'),
    })
    team_away[a].append({
        'gf':fag,'gc':fhg,'xg':xg_a,'xga':xg_h,
        'ht_gf':hag,'ht_gc':hhg,
        'ht_win':hag>hhg,'ht_draw':hag==hhg,
        'clean_sheet':fhg==0,'failed_score':fag==0,
        'comeback':fag>=fhg and hag<hhg,
        'ht_over15':(hhg+hag)>=2,
        'goals_2h':(fag-hag)+(fhg-hhg),
        'shots':a_s,'shotsT':ast,'corners':ac,'corners_a':hc,
        'yellow':ay,'yellow_a':hy,'red':ar,'red_a':hr_,'fouls':af,'fouls_a':hf,
        'result':'G' if ftr=='A' else ('E' if ftr=='D' else 'P'),
    })

# ── CALCULATE TEAM STATS ──────────────────────────────────────────────────────
def calc_team_stats(team):
    liga  = team_league_map.get(team, '')
    la    = league_avgs.get(liga, list(league_avgs.values())[0] if league_avgs else {'hg':1.4,'ag':1.1})
    casa  = team_home[team]
    fuera = team_away[team]

    # xG-based attack/defense indices
    xg_c  = w_mean(casa,  'xg')
    xg_f  = w_mean(fuera, 'xg')
    xga_c = w_mean(casa,  'xga')
    xga_f = w_mean(fuera, 'xga')

    att_h = xg_c  / la['hg'] if la['hg'] > 0 else 1.0
    def_h = xga_c / la['ag'] if la['ag'] > 0 else 1.0
    att_a = xg_f  / la['ag'] if la['ag'] > 0 else 1.0
    def_a = xga_f / la['hg'] if la['hg'] > 0 else 1.0

    # Racha factor from last 5 combined
    last5_h = casa[-3:]  if len(casa)>=3  else casa
    last5_a = fuera[-3:] if len(fuera)>=3 else fuera
    pts = sum(3 if p['result']=='G' else (1 if p['result']=='E' else 0)
              for p in last5_h + last5_a)
    max_pts = len(last5_h + last5_a) * 3
    racha_f = 0.85 + 0.30 * (pts / max_pts) if max_pts > 0 else 1.0

    return {
        'liga': liga,
        'att_h': round(att_h,3), 'def_h': round(def_h,3),
        'att_a': round(att_a,3), 'def_a': round(def_a,3),
        'racha': round(racha_f,3),
        # Weighted stats (casa/fuera separados)
        'gf_c':  w_mean(casa,'gf'),    'gc_c':  w_mean(casa,'gc'),
        'gf_f':  w_mean(fuera,'gf'),   'gc_f':  w_mean(fuera,'gc'),
        'xg_c':  round(xg_c,2),        'xg_f':  round(xg_f,2),
        'sh_c':  w_mean(casa,'shots'),  'sh_f':  w_mean(fuera,'shots'),
        'sht_c': w_mean(casa,'shotsT'), 'sht_f': w_mean(fuera,'shotsT'),
        'co_c':  w_mean(casa,'corners'),'co_f':  w_mean(fuera,'corners'),
        'coa_c': w_mean(casa,'corners_a'),'coa_f':w_mean(fuera,'corners_a'),
        'yw_c':  w_mean(casa,'yellow'), 'yw_f':  w_mean(fuera,'yellow'),
        'ywa_c': w_mean(casa,'yellow_a'),'ywa_f':w_mean(fuera,'yellow_a'),
        'rd_c':  w_mean(casa,'red'),    'rd_f':  w_mean(fuera,'red'),
        'rda_c': w_mean(casa,'red_a'),  'rda_f': w_mean(fuera,'red_a'),
        'fo_c':  w_mean(casa,'fouls'),  'fo_f':  w_mean(fuera,'fouls'),
        'foa_c': w_mean(casa,'fouls_a'),'foa_f': w_mean(fuera,'fouls_a'),
        # Goal patterns
        'sf_h':   pct_stat(casa,'result'),  # scored first (win proxy)
        'sf_a':   pct_stat(fuera,'result'),
        'cs_h':   pct_stat(casa,'clean_sheet'),
        'cs_a':   pct_stat(fuera,'clean_sheet'),
        'fts_h':  pct_stat(casa,'failed_score'),
        'fts_a':  pct_stat(fuera,'failed_score'),
        'cb_h':   pct_stat(casa,'comeback'),
        'cb_a':   pct_stat(fuera,'comeback'),
        'ht_w_h': pct_stat(casa,'ht_win'),
        'ht_w_a': pct_stat(fuera,'ht_win'),
        'hto_h':  pct_stat(casa,'ht_over15'),
        'hto_a':  pct_stat(fuera,'ht_over15'),
        'ag2_h':  w_mean(casa,'goals_2h'),
        'ag2_a':  w_mean(fuera,'goals_2h'),
        'ahtg_h': w_mean(casa,'ht_gf'),
        'ahtg_a': w_mean(fuera,'ht_gf'),
        'n_casa':  len(casa),
        'n_fuera': len(fuera),
    }

print("Calculando estadísticas por equipo...")
all_teams = sorted(team_league_map.keys())
stats = {t: calc_team_stats(t) for t in all_teams}

# ── H2H ──────────────────────────────────────────────────────────────────────
print("Construyendo H2H...")
h2h = defaultdict(list)
for _, r in big.iterrows():
    h, a = r['HomeTeam'], r['AwayTeam']
    key = tuple(sorted([h, a]))
    h2h[key].append([h, a, int(r['FTHG']), int(r['FTAG']),
                     str(r.get('Date',''))[:7]])
h2h_data = {'|'.join(k): v[-6:] for k,v in h2h.items() if len(v)>=2}

# ── RACHA ─────────────────────────────────────────────────────────────────────
racha_data = {}
for t in all_teams:
    h_res = [p['result'] for p in team_home[t]]
    a_res = [p['result'] for p in team_away[t]]
    combined = (h_res[-4:] + a_res[-3:])
    racha_data[t] = ''.join(combined[-6:])

# ── STANDINGS ────────────────────────────────────────────────────────────────
print("Calculando clasificaciones...")
standings = {}
for sheet, league in SHEET_MAP.items():
    d = big[big['Liga']==league].copy()
    if len(d) == 0: continue
    d['FTHG'] = d['FTHG'].astype(int); d['FTAG'] = d['FTAG'].astype(int)
    teams_set = set(d['HomeTeam'].tolist()+d['AwayTeam'].tolist())
    tb = {t:{'PJ':0,'G':0,'E':0,'P':0,'GF':0,'GC':0,'Pts':0} for t in teams_set}
    for _, r in d.iterrows():
        h,a,hg,ag = r['HomeTeam'],r['AwayTeam'],int(r['FTHG']),int(r['FTAG'])
        ftr = str(r.get('FTR','')).strip()
        tb[h]['PJ']+=1; tb[h]['GF']+=hg; tb[h]['GC']+=ag
        tb[a]['PJ']+=1; tb[a]['GF']+=ag; tb[a]['GC']+=hg
        if ftr=='H':   tb[h]['G']+=1; tb[h]['Pts']+=3; tb[a]['P']+=1
        elif ftr=='A': tb[a]['G']+=1; tb[a]['Pts']+=3; tb[h]['P']+=1
        else:          tb[h]['E']+=1; tb[h]['Pts']+=1; tb[a]['E']+=1; tb[a]['Pts']+=1
    sorted_tb = sorted(tb.items(),
                       key=lambda x:(-x[1]['Pts'], -(x[1]['GF']-x[1]['GC']), -x[1]['GF']))
    standings[league] = [[pos+1,t,s['PJ'],s['G'],s['E'],s['P'],
                          s['GF'],s['GC'],s['GF']-s['GC'],s['Pts']]
                         for pos,(t,s) in enumerate(sorted_tb)]

# ── OUTPUT ────────────────────────────────────────────────────────────────────
from datetime import datetime
output = {
    'ligas':       list(SHEET_MAP.values()),
    'equipos':     league_teams,
    'stats':       stats,
    'league_avgs': league_avgs,
    'h2h':         h2h_data,
    'racha':       racha_data,
    'standings':   standings,
    'gp': {t: {k: stats[t][k] for k in [
        'sf_h','sf_a','cs_h','cs_a','fts_h','fts_a',
        'cb_h','cb_a','ht_w_h','ht_w_a','hto_h','hto_a',
        'ag2_h','ag2_a','ahtg_h','ahtg_a'
    ]} for t in all_teams},
    'dc_rho':  DC_RHO,
    'updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    'n_partidos': len(big),
    'n_equipos':  len(all_teams),
}

out_str = json.dumps(output, ensure_ascii=False, separators=(',',':'))
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write(out_str)

print(f"\n✅ {OUT_FILE} generado:")
print(f"   Equipos: {len(all_teams)}")
print(f"   Partidos: {len(big)}")
print(f"   H2H pares: {len(h2h_data)}")
print(f"   Tamaño: {len(out_str)//1024} KB")
print(f"   Actualizado: {output['updated']}")
