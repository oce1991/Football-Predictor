"""
generate_data.py — Predictor DC+EV 2025/26
Descarga datos de football-data.co.uk y genera data.json
Ejecutado automaticamente cada noche por GitHub Actions.
CORREGIDO: usa goles reales para indices att/def (no xG proxy)
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
DATA_URL = "https://www.football-data.co.uk/mmz4281/2526/all-euro-data-2025-2026.xlsx"
OUT_FILE = "data.json"
N        = 12      # ultimos N partidos para promedios ponderados
DECAY    = 0.85    # factor de decaimiento temporal
DC_RHO   = -0.0288 # Dixon-Coles rho calibrado

SHEET_MAP = {
    'E0':'Premier League','E1':'Championship','E2':'League One','E3':'League Two',
    'SP1':'La Liga','SP2':'Segunda Division','D1':'Bundesliga','D2':'2. Bundesliga',
    'I1':'Serie A','I2':'Serie B','F1':'Ligue 1','F2':'Ligue 2',
    'B1':'Belgian Pro League','N1':'Eredivisie','P1':'Primeira Liga','SC0':'Scottish Prem'
}

# ── HELPERS ───────────────────────────────────────────────────────────────────
def wm(lst, key, n=N):
    """Promedio ponderado con decay - mas reciente pesa mas"""
    vals = [p[key] for p in lst[-n:] if key in p and p[key] is not None]
    if not vals: return 0.0
    w = [DECAY**(len(vals)-1-i) for i in range(len(vals))]
    return round(sum(v*wi for v,wi in zip(vals,w)) / sum(w), 2)

def pr(lst, key, n=N):
    """Porcentaje de partidos donde key es True"""
    last = lst[-n:]
    return round(sum(1 for p in last if p.get(key, False)) / len(last), 3) if last else 0.0

def scoring_streak(lst):
    """Racha actual marcando / sin marcar"""
    ss = 0; sn = 0
    for p in reversed(lst[-10:]):
        if p.get('scored', False):
            if sn == 0: ss += 1
            else: break
        else:
            if ss == 0: sn += 1
            else: break
    return ss, sn

# ── DOWNLOAD ──────────────────────────────────────────────────────────────────
print(f"Descargando {DATA_URL}...")
try:
    xl = pd.ExcelFile(DATA_URL)
except Exception as e:
    print(f"ERROR descargando datos: {e}")
    if os.path.exists(OUT_FILE):
        print("Usando data.json existente")
        sys.exit(0)
    sys.exit(1)

all_frames = []; league_teams = {}
for sheet, league in SHEET_MAP.items():
    if sheet not in xl.sheet_names:
        print(f"  Hoja {sheet} no encontrada")
        continue
    df = xl.parse(sheet).dropna(subset=['HomeTeam','FTHG','FTAG'])
    for col in ['FTHG','FTAG','HS','AS','HST','AST','HF','AF','HC','AC','HY','AY','HR','AR','HTHG','HTAG']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['Liga'] = league
    all_frames.append(df)
    league_teams[league] = sorted(set(df['HomeTeam'].tolist() + df['AwayTeam'].tolist()))
    print(f"  {league}: {len(df)} partidos")

big = pd.concat(all_frames, ignore_index=True)
print(f"Total: {len(big)} partidos\n")

# ── LEAGUE AVERAGES (goles reales) ────────────────────────────────────────────
league_avgs = {}
for liga in SHEET_MAP.values():
    d = big[big['Liga'] == liga]
    if not len(d): continue
    league_avgs[liga] = {
        'hg': float(d['FTHG'].mean()),
        'ag': float(d['FTAG'].mean()),
    }

# ── LEAGUE REF AVERAGES ───────────────────────────────────────────────────────
league_ref_avgs = {}
for liga in SHEET_MAP.values():
    d = big[big['Liga'] == liga]
    if not len(d): continue
    league_ref_avgs[liga] = {
        'avg_y': round(float(d['HY'].mean() + d['AY'].mean()), 2) if 'HY' in d.columns else 3.8,
        'avg_r': round(float(d['HR'].mean() + d['AR'].mean()), 3) if 'HR' in d.columns else 0.15,
    }

# ── REFEREE STATS ─────────────────────────────────────────────────────────────
ref_stats = defaultdict(lambda: {'n':0,'hy':0,'ay':0,'hr':0,'ar':0})
for _, r in big.iterrows():
    ref = str(r.get('Referee', '')).strip()
    if not ref or ref == 'nan': continue
    ref_stats[ref]['n']  += 1
    ref_stats[ref]['hy'] += float(r.get('HY', 0) or 0)
    ref_stats[ref]['ay'] += float(r.get('AY', 0) or 0)
    ref_stats[ref]['hr'] += float(r.get('HR', 0) or 0)
    ref_stats[ref]['ar'] += float(r.get('AR', 0) or 0)

refs = {}
for ref, s in ref_stats.items():
    if s['n'] < 3: continue
    refs[ref] = {
        'n':     s['n'],
        'avg_y': round((s['hy'] + s['ay']) / s['n'], 2),
        'avg_r': round((s['hr'] + s['ar']) / s['n'], 3),
        'avg_y_h': round(s['hy'] / s['n'], 2),
        'avg_y_a': round(s['ay'] / s['n'], 2),
    }

# ── TEAM DATA ─────────────────────────────────────────────────────────────────
team_home = defaultdict(list)
team_away = defaultdict(list)
team_league = {}

for _, r in big.iterrows():
    h, a, liga = r['HomeTeam'], r['AwayTeam'], r['Liga']
    team_league[h] = liga; team_league[a] = liga
    ftr  = str(r.get('FTR', '')).strip()
    fhg  = float(r['FTHG']); fag = float(r['FTAG'])
    hhg  = float(r.get('HTHG', 0) or 0)
    hag  = float(r.get('HTAG', 0) or 0)

    team_home[h].append({
        'gf': fhg, 'gc': fag,
        'ht_gf': hhg, 'ht_gc': hag,
        'ht_win': hhg > hag, 'clean_sheet': fag == 0,
        'failed_score': fhg == 0, 'comeback': fhg >= fag and hhg < hag,
        'ht_over15': (hhg+hag) >= 2, 'goals_2h': (fhg-hhg) + (fag-hag),
        'shots':    float(r.get('HS', 0) or 0),
        'shotsT':   float(r.get('HST', 0) or 0),
        'corners':  float(r.get('HC', 0) or 0),
        'corners_a':float(r.get('AC', 0) or 0),
        'yellow':   float(r.get('HY', 0) or 0),
        'yellow_a': float(r.get('AY', 0) or 0),
        'red':      float(r.get('HR', 0) or 0),
        'red_a':    float(r.get('AR', 0) or 0),
        'fouls':    float(r.get('HF', 0) or 0),
        'fouls_a':  float(r.get('AF', 0) or 0),
        'result': 'G' if ftr=='H' else ('E' if ftr=='D' else 'P'),
        'scored': fhg > 0,
    })
    team_away[a].append({
        'gf': fag, 'gc': fhg,
        'ht_gf': hag, 'ht_gc': hhg,
        'ht_win': hag > hhg, 'clean_sheet': fhg == 0,
        'failed_score': fag == 0, 'comeback': fag >= fhg and hag < hhg,
        'ht_over15': (hhg+hag) >= 2, 'goals_2h': (fag-hag) + (fhg-hhg),
        'shots':    float(r.get('AS', 0) or 0),
        'shotsT':   float(r.get('AST', 0) or 0),
        'corners':  float(r.get('AC', 0) or 0),
        'corners_a':float(r.get('HC', 0) or 0),
        'yellow':   float(r.get('AY', 0) or 0),
        'yellow_a': float(r.get('HY', 0) or 0),
        'red':      float(r.get('AR', 0) or 0),
        'red_a':    float(r.get('HR', 0) or 0),
        'fouls':    float(r.get('AF', 0) or 0),
        'fouls_a':  float(r.get('HF', 0) or 0),
        'result': 'G' if ftr=='A' else ('E' if ftr=='D' else 'P'),
        'scored': fag > 0,
    })

# ── TEAM STATS ────────────────────────────────────────────────────────────────
def calc_stats(team):
    liga  = team_league.get(team, '')
    la    = league_avgs.get(liga, {'hg': 1.4, 'ag': 1.1})
    casa  = team_home[team]
    fuera = team_away[team]

    # ── INDICES CON GOLES REALES (CRITICO: NO usar xG proxy) ──────────────
    gf_c = wm(casa,  'gf')   # goles marcados en casa (ponderado)
    gc_c = wm(casa,  'gc')   # goles encajados en casa
    gf_f = wm(fuera, 'gf')   # goles marcados fuera
    gc_f = wm(fuera, 'gc')   # goles encajados fuera

    # Indice = rendimiento equipo / media liga
    att_h = gf_c / la['hg'] if la['hg'] > 0 else 1.0
    def_h = gc_c / la['ag'] if la['ag'] > 0 else 1.0
    att_a = gf_f / la['ag'] if la['ag'] > 0 else 1.0
    def_a = gc_f / la['hg'] if la['hg'] > 0 else 1.0

    # Regresion a la media: 70% forma reciente + 30% media temporada completa
    all_gf_h = [p['gf'] for p in team_home[team]]
    all_gf_a = [p['gf'] for p in team_away[team]]
    all_gc_h = [p['gc'] for p in team_home[team]]
    all_gc_a = [p['gc'] for p in team_away[team]]

    if len(all_gf_h) > N:
        season_att_h = (sum(all_gf_h)/len(all_gf_h)) / la['hg'] if la['hg'] > 0 else 1.0
        att_h = att_h * 0.7 + season_att_h * 0.3
    if len(all_gf_a) > N:
        season_att_a = (sum(all_gf_a)/len(all_gf_a)) / la['ag'] if la['ag'] > 0 else 1.0
        att_a = att_a * 0.7 + season_att_a * 0.3
    if len(all_gc_h) > N:
        season_def_h = (sum(all_gc_h)/len(all_gc_h)) / la['ag'] if la['ag'] > 0 else 1.0
        def_h = def_h * 0.7 + season_def_h * 0.3
    if len(all_gc_a) > N:
        season_def_a = (sum(all_gc_a)/len(all_gc_a)) / la['hg'] if la['hg'] > 0 else 1.0
        def_a = def_a * 0.7 + season_def_a * 0.3

    # Factor racha (ultimos 6 partidos combinados)
    last5h = casa[-3:]; last5a = fuera[-3:]
    pts = sum(3 if p['result']=='G' else (1 if p['result']=='E' else 0)
              for p in last5h + last5a)
    mxp = len(last5h + last5a) * 3
    racha_f = 0.85 + 0.30 * (pts / mxp) if mxp > 0 else 1.0

    ss_h, sn_h = scoring_streak(casa)
    ss_a, sn_a = scoring_streak(fuera)

    return {
        'liga':  liga,
        'att_h': round(att_h, 3), 'def_h': round(def_h, 3),
        'att_a': round(att_a, 3), 'def_a': round(def_a, 3),
        'racha': round(racha_f, 3),
        'gf_c':  wm(casa, 'gf'),    'gc_c':  wm(casa, 'gc'),
        'gf_f':  wm(fuera, 'gf'),   'gc_f':  wm(fuera, 'gc'),
        'sh_c':  wm(casa, 'shots'), 'sh_f':  wm(fuera, 'shots'),
        'sht_c': wm(casa, 'shotsT'),'sht_f': wm(fuera, 'shotsT'),
        'co_c':  wm(casa, 'corners'),'co_f': wm(fuera, 'corners'),
        'coa_c': wm(casa, 'corners_a'),'coa_f':wm(fuera,'corners_a'),
        'yw_c':  wm(casa, 'yellow'), 'yw_f':  wm(fuera, 'yellow'),
        'ywa_c': wm(casa, 'yellow_a'),'ywa_f':wm(fuera,'yellow_a'),
        'rd_c':  wm(casa, 'red'),   'rd_f':  wm(fuera, 'red'),
        'rda_c': wm(casa, 'red_a'), 'rda_f': wm(fuera, 'red_a'),
        'fo_c':  wm(casa, 'fouls'), 'fo_f':  wm(fuera, 'fouls'),
        'foa_c': wm(casa, 'fouls_a'),'foa_f':wm(fuera,'fouls_a'),
        'sf_h':  pr(casa, 'result'), 'sf_a':  pr(fuera, 'result'),
        'cs_h':  pr(casa, 'clean_sheet'),'cs_a':pr(fuera,'clean_sheet'),
        'fts_h': pr(casa, 'failed_score'),'fts_a':pr(fuera,'failed_score'),
        'cb_h':  pr(casa, 'comeback'),'cb_a': pr(fuera, 'comeback'),
        'ht_w_h':pr(casa, 'ht_win'), 'ht_w_a':pr(fuera,'ht_win'),
        'hto_h': pr(casa, 'ht_over15'),'hto_a':pr(fuera,'ht_over15'),
        'ag2_h': wm(casa, 'goals_2h'),'ag2_a':wm(fuera,'goals_2h'),
        'ahtg_h':wm(casa, 'ht_gf'), 'ahtg_a':wm(fuera,'ht_gf'),
        'ss_h': ss_h, 'sn_h': sn_h,
        'ss_a': ss_a, 'sn_a': sn_a,
        'n_casa':  len(casa),
        'n_fuera': len(fuera),
    }

print("Calculando estadisticas...")
all_teams = sorted(team_league.keys())
stats = {t: calc_stats(t) for t in all_teams}

# ── H2H ──────────────────────────────────────────────────────────────────────
print("Construyendo H2H...")
h2h = defaultdict(list)
for _, r in big.iterrows():
    h, a = r['HomeTeam'], r['AwayTeam']
    key = tuple(sorted([h, a]))
    h2h[key].append([h, a, int(r['FTHG']), int(r['FTAG']),
                     str(r.get('Date', ''))[:7]])
h2h_data = {'|'.join(k): v[-6:] for k, v in h2h.items() if len(v) >= 2}

# ── RACHA (usa 'D' para empates, NO 'X') ─────────────────────────────────────
racha_data = {}
for t in all_teams:
    hr = [p['result'] for p in team_home[t]]
    ar = [p['result'] for p in team_away[t]]
    racha_data[t] = ''.join((hr[-4:] + ar[-3:])[-6:])

# ── STANDINGS ─────────────────────────────────────────────────────────────────
print("Calculando clasificaciones...")
standings = {}
for sheet, league in SHEET_MAP.items():
    d = big[big['Liga'] == league].copy()
    if not len(d): continue
    d['FTHG'] = d['FTHG'].astype(int); d['FTAG'] = d['FTAG'].astype(int)
    ts = set(d['HomeTeam'].tolist() + d['AwayTeam'].tolist())
    tb = {t: {'PJ':0,'G':0,'E':0,'P':0,'GF':0,'GC':0,'Pts':0} for t in ts}
    for _, r in d.iterrows():
        h, a = r['HomeTeam'], r['AwayTeam']
        hg, ag = int(r['FTHG']), int(r['FTAG'])
        ftr = str(r.get('FTR', '')).strip()
        tb[h]['PJ']+=1; tb[h]['GF']+=hg; tb[h]['GC']+=ag
        tb[a]['PJ']+=1; tb[a]['GF']+=ag; tb[a]['GC']+=hg
        if   ftr == 'H': tb[h]['G']+=1; tb[h]['Pts']+=3; tb[a]['P']+=1
        elif ftr == 'A': tb[a]['G']+=1; tb[a]['Pts']+=3; tb[h]['P']+=1
        else:            tb[h]['E']+=1; tb[h]['Pts']+=1; tb[a]['E']+=1; tb[a]['Pts']+=1
    st = sorted(tb.items(),
                key=lambda x: (-x[1]['Pts'], -(x[1]['GF']-x[1]['GC']), -x[1]['GF']))
    standings[league] = [
        [i+1, t, s['PJ'], s['G'], s['E'], s['P'],
         s['GF'], s['GC'], s['GF']-s['GC'], s['Pts']]
        for i, (t, s) in enumerate(st)
    ]

# ── OUTPUT ────────────────────────────────────────────────────────────────────
output = {
    'ligas':       list(SHEET_MAP.values()),
    'equipos':     league_teams,
    'stats':       stats,
    'league_avgs': league_avgs,
    'league_ref_avgs': league_ref_avgs,
    'refs':        refs,
    'h2h':         h2h_data,
    'racha':       racha_data,
    'standings':   standings,
    'gp': {
        t: {k: stats[t][k] for k in [
            'sf_h','sf_a','cs_h','cs_a','fts_h','fts_a',
            'cb_h','cb_a','ht_w_h','ht_w_a','hto_h','hto_a',
            'ag2_h','ag2_a','ahtg_h','ahtg_a','ss_h','sn_h','ss_a','sn_a'
        ]}
        for t in all_teams
    },
    'dc_rho':     DC_RHO,
    'updated':    datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    'n_partidos': len(big),
    'n_equipos':  len(all_teams),
}

out_str = json.dumps(output, ensure_ascii=False, separators=(',', ':'))
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write(out_str)

print(f"\n✅ {OUT_FILE} generado:")
print(f"   Equipos:  {len(all_teams)}")
print(f"   Partidos: {len(big)}")
print(f"   H2H:      {len(h2h_data)} pares")
print(f"   Arbitros: {len(refs)}")
print(f"   Tamano:   {len(out_str)//1024} KB")
print(f"   Updated:  {output['updated']}")

# Verificacion rapida
for team in ['Liverpool', 'Real Madrid', 'La Coruna', 'Leganes']:
    s = stats.get(team)
    if not s: continue
    la2 = league_avgs.get(s['liga'], {'hg':1.4,'ag':1.1})
    lH = s['att_h'] * 1.0 * la2['hg'] * s['racha']
    print(f"   {team}: att_h={s['att_h']} lH_vs_avg={lH:.2f}")
