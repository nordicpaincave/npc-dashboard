"""
NPC Endurance — Dashboard Generator v4
Busca dados do TrainingPeaks via cookie de sessão e injeta no template HTML.
Sem custo adicional — nenhuma API externa paga.

Variável de ambiente necessária:
  TP_COOKIE  — valor do cookie Production_tpAuth do TrainingPeaks
"""

import os, json
from datetime import datetime, timedelta
import requests

# ── Atletas ───────────────────────────────────────────────────────────
ATHLETES = {
    "bruno":   {"id": 6285028, "name": "Bruno Trevisan"},
    "jean":    {"id": 6286348, "name": "Jean Romano"},
    "gabriel": {"id": 5775491, "name": "Gabriel"},
}
TP_BASE = "https://tpapi.trainingpeaks.com"

# ── Mapeamento de esportes ────────────────────────────────────────────
SPORT_ID = {1:"swim",2:"bike",3:"run",4:"run",5:"strength",
            6:"strength",7:"strength",10:"bike",20:"swim"}
SPORT_LABEL = {"swim":"Natação","bike":"Bike","run":"Corrida","strength":"Força"}
SPORT_COLOR = {"swim":"#4a9eff","bike":"#f5a623","run":"#4db87a","strength":"#9b8fff"}
DAYS_PT = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]

# ── Dados de referência (fallback visual) ─────────────────────────────
PROTOTYPE = {
    "bruno": {
        "kpis":{"ctl":72,"atl":68,"tsb":4,"tss_week":412},
        "kpi_delta":{"ctl":"+3","atl":"+8","tsb":"-4","tss_week":"+31"},
        "pmc":{"labels":["S1","S2","S3","S4","S5","S6","S7","S8"],
               "ctl":[58,61,65,68,70,74,73,72],"atl":[62,70,75,72,65,78,74,68],"tsb":[-4,-9,-10,-4,5,-4,-1,4]},
        "zones":{"labels":["Natação","Bike","Corrida"],"z1":[72,68,65],"z2":[22,25,28],"z3":[6,7,7]},
        "vol":{"swim":2.1,"bike":5.8,"run":3.2,"strength":1.0},
        "hrv":{"labels":["1/4","2/4","3/4","4/4","5/4","6/4","7/4","8/4","9/4","10/4","11/4","12/4","13/4","14/4"],
               "vals":[56,54,57,59,55,53,58,60,57,54,55,58,59,60],"baseline":57},
        "adherence":[{"label":"Natação","done":2.1,"target":2.5,"color":"#4a9eff"},
                     {"label":"Bike","done":5.8,"target":6.0,"color":"#f5a623"},
                     {"label":"Corrida","done":3.2,"target":3.5,"color":"#4db87a"},
                     {"label":"Força","done":1.0,"target":1.0,"color":"#9b8fff"}],
        "alerts":[{"type":"ok","msg":"Forma positiva — TSB +4"},
                  {"type":"info","msg":"ATL elevada — monitorar recuperação"}],
        "sessions":[
            {"day":"Seg","sport":"run","desc":"Limiar duplo — 3×10min Z2 + 2×8min Z3","dur":"1h15","tss":82,"zones":"60/30/10"},
            {"day":"Ter","sport":"swim","desc":"Volume Z1 — 3.200m aeróbico","dur":"1h05","tss":48,"zones":"80/18/2"},
            {"day":"Qua","sport":"bike","desc":"Endurance Z1 — 90min fundo","dur":"1h30","tss":65,"zones":"75/22/3"},
            {"day":"Qui","sport":"run","desc":"Limiar duplo — 4×6min Z2 + 3×5min Z3","dur":"1h10","tss":78,"zones":"55/32/13"},
            {"day":"Sex","sport":"swim","desc":"CSS — 8×100m no limiar","dur":"55min","tss":55,"zones":"40/42/18"},
            {"day":"Sáb","sport":"bike","desc":"Longa Z1 — 3h base aeróbica","dur":"3h00","tss":95,"zones":"80/18/2"},
        ]
    },
    "jean": {
        "kpis":{"ctl":85,"atl":79,"tsb":6,"tss_week":498},
        "kpi_delta":{"ctl":"+5","atl":"+6","tsb":"+2","tss_week":"+44"},
        "pmc":{"labels":["S1","S2","S3","S4","S5","S6","S7","S8"],
               "ctl":[68,72,76,79,82,85,84,85],"atl":[70,78,82,80,76,88,82,79],"tsb":[-2,-6,-6,-1,6,-3,2,6]},
        "zones":{"labels":["Natação","Bike","Corrida"],"z1":[70,65,60],"z2":[24,28,32],"z3":[6,7,8]},
        "vol":{"swim":2.8,"bike":7.2,"run":4.5,"strength":1.0},
        "hrv":{"labels":["1/4","2/4","3/4","4/4","5/4","6/4","7/4","8/4","9/4","10/4","11/4","12/4","13/4","14/4"],
               "vals":[60,62,61,58,60,63,64,62,59,61,63,64,63,65],"baseline":62},
        "adherence":[{"label":"Natação","done":2.8,"target":3.0,"color":"#4a9eff"},
                     {"label":"Bike","done":7.2,"target":7.0,"color":"#f5a623"},
                     {"label":"Corrida","done":4.5,"target":4.5,"color":"#4db87a"},
                     {"label":"Força","done":1.0,"target":1.0,"color":"#9b8fff"}],
        "alerts":[{"type":"ok","msg":"Excelente aderência — 97% do plano executado"},
                  {"type":"info","msg":"Buenos Aires (70.3) em 25 semanas"}],
        "sessions":[
            {"day":"Seg","sport":"bike","desc":"Limiar duplo — 5×8min Z2 + 3×6min Z3","dur":"1h30","tss":95,"zones":"50/36/14"},
            {"day":"Ter","sport":"swim","desc":"Técnica + CSS — 3.600m","dur":"1h10","tss":58,"zones":"65/28/7"},
            {"day":"Qua","sport":"run","desc":"Volume Z1 — 12km fácil","dur":"1h15","tss":62,"zones":"78/20/2"},
            {"day":"Qui","sport":"bike","desc":"Limiar duplo — FTP intervals","dur":"1h20","tss":88,"zones":"45/38/17"},
            {"day":"Sex","sport":"swim","desc":"Endurance — 4.000m Z1/Z2","dur":"1h20","tss":65,"zones":"70/26/4"},
            {"day":"Sáb","sport":"run","desc":"Longa Z1/Z2 — 18km progressivo","dur":"1h45","tss":100,"zones":"65/28/7"},
        ]
    },
    "gabriel": {
        "kpis":{"ctl":58,"atl":72,"tsb":-14,"tss_week":380},
        "kpi_delta":{"ctl":"+2","atl":"+14","tsb":"-12","tss_week":"+55"},
        "pmc":{"labels":["S1","S2","S3","S4","S5","S6","S7","S8"],
               "ctl":[46,49,52,54,56,58,57,58],"atl":[50,55,60,58,52,65,70,72],"tsb":[-4,-6,-8,-4,4,-7,-13,-14]},
        "zones":{"labels":["Bike","Corrida"],"z1":[60,58],"z2":[28,30],"z3":[12,12]},
        "vol":{"swim":0,"bike":5.5,"run":4.2,"strength":1.5},
        "hrv":{"labels":["1/4","2/4","3/4","4/4","5/4","6/4","7/4","8/4","9/4","10/4","11/4","12/4","13/4","14/4"],
               "vals":[58,56,54,52,55,53,51,50,52,51,53,54,55,53],"baseline":55},
        "adherence":[{"label":"Bike","done":5.5,"target":5.0,"color":"#f5a623"},
                     {"label":"Corrida","done":4.2,"target":4.0,"color":"#4db87a"},
                     {"label":"Força","done":1.5,"target":1.5,"color":"#9b8fff"}],
        "alerts":[{"type":"danger","msg":"Risco de overtraining — TSB −14"},
                  {"type":"warn","msg":"HRV em queda há 7 dias"}],
        "sessions":[
            {"day":"Seg","sport":"run","desc":"Limiar — 3×10min Z2 pré-duatlon","dur":"1h00","tss":70,"zones":"55/33/12"},
            {"day":"Ter","sport":"bike","desc":"Específico duatlon — 3×8min Z3","dur":"1h10","tss":85,"zones":"40/38/22"},
            {"day":"Qua","sport":"strength","desc":"Alfredson + estabilização joelho","dur":"40min","tss":25,"zones":"—"},
            {"day":"Qui","sport":"run","desc":"Taper ativo — 6km Z1 leve","dur":"40min","tss":35,"zones":"85/13/2"},
            {"day":"Sex","sport":"bike","desc":"Ativação pré-prova — 30min Z1","dur":"30min","tss":22,"zones":"80/15/5"},
            {"day":"Sáb","sport":"run","desc":"PROVA — Duatlon 5/20/2.5km","dur":"~56min","tss":110,"zones":"20/35/45"},
        ]
    },
}

# ── Autenticação ──────────────────────────────────────────────────────
def hdrs():
    return {"Cookie": f"Production_tpAuth={os.environ['TP_COOKIE']}",
            "Accept": "application/json", "User-Agent": "Mozilla/5.0"}

def tp_get(path):
    r = requests.get(f"{TP_BASE}{path}", headers=hdrs(), timeout=20)
    r.raise_for_status()
    return r.json()

def to_list(data):
    if isinstance(data, list): return data
    if isinstance(data, dict):
        return data.get("Items") or data.get("items") or data.get("workouts") or []
    return []

# ── Busca workouts (com filtro de data no cliente) ────────────────────
def fetch_workouts(athlete_id, days=180):
    """Busca workouts dos últimos N dias. 180 dias = histórico suficiente para CTL convergir."""
    end, start = datetime.utcnow(), datetime.utcnow() - timedelta(days=days)
    raw = to_list(tp_get(
        f"/fitness/v6/athletes/{athlete_id}/workouts"
        f"/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
    ))
    cutoff = start.strftime("%Y-%m-%d")
    filtered = [w for w in raw if str(w.get("workoutDay",""))[:10] >= cutoff]
    print(f"    workouts: {len(filtered)} nos últimos {days} dias")
    return filtered

# ── Busca fitness/PMC ─────────────────────────────────────────────────
def fetch_fitness(athlete_id, weeks=8):
    end, start = datetime.utcnow(), datetime.utcnow() - timedelta(weeks=weeks)
    s, e = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    for path in [
        f"/fitness/v6/athletes/{athlete_id}/fitness/{s}/{e}",
        f"/fitness/v6/athletes/{athlete_id}/fitnesssummaries/{s}/{e}",
        f"/coaching/v6/athletes/{athlete_id}/fitness/{s}/{e}",
    ]:
        try:
            data = to_list(tp_get(path))
            if data:
                print(f"    fitness: {len(data)} registros")
                return data
        except Exception:
            continue
    print(f"    fitness: nenhum endpoint funcionou — PMC calculado dos workouts")
    return []

# ── Busca wellness/HRV ────────────────────────────────────────────────
def fetch_wellness(athlete_id, days=14):
    end, start = datetime.utcnow(), datetime.utcnow() - timedelta(days=days)
    s, e = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    for path in [
        f"/wellness/v6/athletes/{athlete_id}/{s}/{e}",
        f"/v6/athletes/{athlete_id}/wellness/{s}/{e}",
        f"/fitness/v6/athletes/{athlete_id}/wellness/{s}/{e}",
    ]:
        try:
            data = to_list(tp_get(path))
            if data:
                print(f"    wellness: {len(data)} registros")
                return data
        except Exception:
            continue
    print(f"    wellness: indisponível")
    return []

# ── Processamento de workouts ─────────────────────────────────────────
def process_workouts(raw, display_days=14):
    """Processa workouts. raw pode ter até 56 dias (para PMC);
    display_days controla quantas sessões aparecem na tabela."""
    sessions, vol, zones_acc = [], {"swim":0.0,"bike":0.0,"run":0.0,"strength":0.0}, {}
    cutoff_display = (datetime.utcnow() - timedelta(days=display_days)).strftime("%Y-%m-%d")

    for w in raw:
        # Sport pelo ID numérico
        sport = SPORT_ID.get(int(w.get("workoutTypeValueId") or 0))
        if not sport:
            name = (w.get("athleteWorkoutTypeName") or w.get("title") or "").lower()
            for k, kws in [("swim",["swim","pool"]),("bike",["bike","cycl","ride"]),
                           ("run",["run","corr"]),("strength",["strength","weight","gym"])]:
                if any(kw in name for kw in kws):
                    sport = k; break
        if not sport:
            continue

        # Duração — testa se totalTime está em horas ou dias
        # Se valor > 1.0, provavelmente está em horas (ex: 1.5h)
        # Se valor < 1.0 pequeno (ex: 0.083), pode ser horas (5min) ou dias (2h)
        # Heurística: se * 24 > 8h, usa como horas direto; senão multiplica por 24
        raw_time = float(w.get("totalTime") or 0)
        if raw_time == 0:
            continue
        dur_h_as_hours = raw_time                  # assume horas
        dur_h_as_days  = raw_time * 24             # assume dias
        # Usa "dias" só se o resultado em horas seria < 5 minutos E em dias seria razoável
        if dur_h_as_hours < 0.05 and 0.05 <= dur_h_as_days <= 8.0:
            dur_h = dur_h_as_days
        else:
            dur_h = min(dur_h_as_hours, 8.0)

        if dur_h < 0.05:
            continue

        # ── Filtra apenas treinos REALIZADOS ──────────────────────────
        # Planejados têm tssActual=null/0 mas totalTime>0 (tempo planejado)
        # Realizados têm tssActual>0 (dado gravado pelo dispositivo)
        tss_actual_raw = w.get("tssActual")
        tss = round(float(tss_actual_raw or 0))

        raw_time = float(w.get("totalTime") or 0)

        # Para força (sem potenciômetro/GPS): aceita se tem tempo real gravado
        # Para outros esportes: exige tssActual > 0
        if sport == "strength":
            if raw_time <= 0:
                continue   # planejado sem execução
        else:
            if tss <= 0:
                continue   # planejado ou sem dado real

        # Data
        workout_day = str(w.get("workoutDay",""))[:10]
        try:
            dt  = datetime.strptime(workout_day, "%Y-%m-%d")
            day = DAYS_PT[dt.weekday()]
        except Exception:
            day = "?"

        # Duração formatada
        hh, mm  = int(dur_h), int((dur_h % 1) * 60)
        dur_str = f"{hh}h{mm:02d}" if hh > 0 else f"{mm}min"

        # Zonas estimadas pelo TSS/h
        tss_h = tss / dur_h if dur_h > 0 else 0
        if tss_h > 80:   pz = (40, 35, 25)
        elif tss_h > 55: pz = (55, 35, 10)
        else:            pz = (75, 20,  5)

        # Título
        title = w.get("title") or SPORT_LABEL.get(sport, "Treino")
        if title.lower() in ("other", ""):
            title = SPORT_LABEL.get(sport, "Treino")

        # Volume acumulado (todos os 56 dias — para PMC)
        vol[sport] = round(vol[sport] + dur_h, 2)
        if sport not in zones_acc:
            zones_acc[sport] = [0.0, 0.0, 0.0]
        zones_acc[sport][0] += dur_h * pz[0] / 100
        zones_acc[sport][1] += dur_h * pz[1] / 100
        zones_acc[sport][2] += dur_h * pz[2] / 100

        # Sessões visíveis: apenas últimos 14 dias
        if workout_day >= cutoff_display:
            sessions.append({"day":day,"sport":sport,"desc":title,
                             "dur":dur_str,"tss":tss,"zones":f"{pz[0]}/{pz[1]}/{pz[2]}"})

    # Volume exibido: apenas últimos 14 dias, apenas treinos realizados
    vol_display = {"swim":0.0,"bike":0.0,"run":0.0,"strength":0.0}
    for w in raw:
        workout_day_w = str(w.get("workoutDay",""))[:10]
        if workout_day_w < cutoff_display:
            continue

        sport_w = SPORT_ID.get(int(w.get("workoutTypeValueId") or 0))
        if not sport_w:
            continue

        # Só conta realizados: tssActual > 0 para esportes com GPS/potenciômetro
        # Para força: aceita se tem totalTime E compliance > 0
        tss_a = float(w.get("tssActual") or 0)
        compliance = float(w.get("complianceDurationPercent") or 0)
        raw_time_w = float(w.get("totalTime") or 0)

        if sport_w == "strength":
            if raw_time_w <= 0 or (compliance == 0 and tss_a == 0):
                continue
        else:
            if tss_a <= 0:
                continue

        dur_h_w = raw_time_w
        if dur_h_w < 0.05 and raw_time_w * 24 <= 8.0:
            dur_h_w = raw_time_w * 24
        dur_h_w = min(dur_h_w, 8.0)

        if dur_h_w >= 0.05 and sport_w in vol_display:
            vol_display[sport_w] = round(vol_display[sport_w] + dur_h_w, 2)

    # Gráfico de zonas
    zl, z1l, z2l, z3l = [], [], [], []
    for sport in ["swim","bike","run"]:
        if sport in zones_acc:
            z1, z2, z3 = zones_acc[sport]; t = z1+z2+z3
            if t > 0:
                zl.append(SPORT_LABEL[sport])
                z1l.append(round(z1/t*100)); z2l.append(round(z2/t*100)); z3l.append(round(z3/t*100))

    return sessions, {k:round(v,1) for k,v in vol_display.items()}, {"labels":zl,"z1":z1l,"z2":z2l,"z3":z3l}

# ── PMC ───────────────────────────────────────────────────────────────
def calc_pmc_from_workouts(raw_w):
    daily = {}
    for w in raw_w:
        day      = str(w.get("workoutDay",""))[:10]
        tss_val  = float(w.get("tssActual") or 0)
        has_time = float(w.get("totalTime") or 0) > 0
        # Só conta treinos realmente executados (ambos os campos preenchidos)
        if tss_val > 0 and has_time:
            daily[day] = daily.get(day, 0) + min(tss_val, 300)  # cap 300/sessão

    # Cap diário conservador
    for d in daily:
        daily[d] = min(daily[d], 500)
    end = datetime.utcnow()
    dates = [(end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(179,-1,-1)]
    ctl, atl = 0.0, 0.0  # começa em 0 — o histórico vai construir o valor correto
    kc, ka = 2/43, 2/8
    history = []
    for d in dates:
        tss = daily.get(d, 0)
        ctl = tss*kc + ctl*(1-kc); atl = tss*ka + atl*(1-ka)
        history.append({"date":d,"ctl":ctl,"atl":atl,"tsb":ctl-atl,"tss":tss})
    return history

def _past_workouts_with_ctl(raw_w):
    """Retorna workouts passados com CTL do TP. Retorna lista vazia se campo não existe."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return sorted(
        [w for w in raw_w
         if float(w.get("ctl") or 0) > 0
         and str(w.get("workoutDay",""))[:10] <= today],
        key=lambda x: str(x.get("workoutDay",""))
    )

def build_pmc(raw_f, raw_w):
    records = _past_workouts_with_ctl(raw_w)
    if not records:
        records = sorted(calc_pmc_from_workouts(raw_w), key=lambda x: x.get("date",""))
    sample = records[::max(1, len(records)//8)][-8:]
    labels, ctl_l, atl_l, tsb_l = [], [], [], []
    for r in sample:
        day_key = r.get("workoutDay") or r.get("date","")
        try: labels.append(datetime.strptime(str(day_key)[:10],"%Y-%m-%d").strftime("%d/%m"))
        except: labels.append("?")
        ctl_l.append(round(float(r.get("ctl") or 0)))
        atl_l.append(round(float(r.get("atl") or 0)))
        tsb_l.append(round(float(r.get("tsb") or 0)))
    return {"labels":labels,"ctl":ctl_l,"atl":atl_l,"tsb":tsb_l}

def build_kpis(raw_f, raw_w):
    today    = datetime.utcnow().strftime("%Y-%m-%d")
    with_ctl = _past_workouts_with_ctl(raw_w)

    if with_ctl:
        # CTL/ATL/TSB direto do TP
        latest = with_ctl[-1]
        ctl    = round(float(latest.get("ctl") or 0))
        atl    = round(float(latest.get("atl") or 0))
        tsb    = round(float(latest.get("tsb") or 0))
        print(f"    PMC via campo TP: CTL={ctl} ATL={atl} TSB={tsb}")
    else:
        # Campo ctl não disponível via cookie — calcula por EMA
        pmc_records = sorted(calc_pmc_from_workouts(raw_w),
                             key=lambda x: x.get("date",""))
        # Filtra apenas dias passados
        past = [r for r in pmc_records if r.get("date","") <= today]
        if past:
            latest = past[-1]
            ctl    = round(float(latest.get("ctl") or 0))
            atl    = round(float(latest.get("atl") or 0))
            tsb    = round(float(latest.get("tsb") or 0))
            print(f"    PMC via EMA: CTL={ctl} ATL={atl} TSB={tsb}")
        else:
            ctl, atl, tsb = 0, 0, 0

    # TSS semanal: só treinos realizados, últimos 7 dias
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    tss_week = round(sum(
        float(w.get("tssActual") or 0) for w in raw_w
        if today >= str(w.get("workoutDay",""))[:10] >= week_ago
        and float(w.get("tssActual") or 0) > 0
        and float(w.get("totalTime") or 0) > 0   # garante que foi executado
    ))

    # Cap realista: CTL triatleta de base raramente passa de 150
    ctl = min(ctl, 150)
    atl = min(atl, 200)

    print(f"    KPIs: CTL={ctl} ATL={atl} TSB={tsb} TSS7d={tss_week}")
    return {"ctl": ctl, "atl": atl, "tsb": tsb, "tss_week": tss_week}

def build_deltas(raw_f, raw_w):
    today     = datetime.utcnow().strftime("%Y-%m-%d")
    completed = _past_workouts_with_ctl(raw_w)
    if not completed:
        completed = [r for r in calc_pmc_from_workouts(raw_w)
                     if r.get("date","") <= today]
    if len(completed) < 8:
        return {"ctl":"—","atl":"—","tsb":"—","tss_week":"—"}
    c, p = completed[-1], completed[-8]
    def fmt(a, b):
        d = round(float(a or 0) - float(b or 0))
        return f"+{d}" if d >= 0 else str(d)
    return {"ctl": fmt(c.get("ctl"), p.get("ctl")),
            "atl": fmt(c.get("atl"), p.get("atl")),
            "tsb": fmt(c.get("tsb"), p.get("tsb")),
            "tss_week": "—"}

# ── HRV ───────────────────────────────────────────────────────────────
def build_hrv(raw_we):
    records = sorted(raw_we or [], key=lambda x: x.get("date",""))[-14:]
    labels, vals = [], []
    for r in records:
        try: labels.append(datetime.strptime(str(r["date"])[:10],"%Y-%m-%d").strftime("%d/%m"))
        except: labels.append("?")
        vals.append(round(float(r.get("hrv") or r.get("rmssd") or r.get("hrvScore") or 0)))
    valid = [v for v in vals if v > 0]
    return {"labels":labels,"vals":vals,"baseline":round(sum(valid)/len(valid)) if valid else 0}

# ── Alertas ───────────────────────────────────────────────────────────
def build_alerts(kpis, hrv):
    alerts = []
    tsb, atl, ctl = kpis["tsb"], kpis["atl"], max(kpis["ctl"], 1)
    if tsb < -15:
        alerts.append({"type":"danger","msg":f"Risco de overtraining — TSB {tsb}, ATL {round((atl/ctl-1)*100)}% acima da CTL"})
    elif tsb < -5:
        alerts.append({"type":"warn","msg":f"Fadiga acumulada — TSB {tsb}, monitorar recuperação"})
    elif tsb > 10:
        alerts.append({"type":"ok","msg":f"Forma positiva — TSB +{tsb}, bom momento para qualidade"})
    else:
        alerts.append({"type":"ok","msg":f"Carga equilibrada — TSB {tsb}"})
    vals = [v for v in hrv.get("vals",[]) if v > 0]
    if len(vals) >= 14 and sum(vals[-7:])/7 < sum(vals[-14:-7])/7 * 0.93:
        alerts.append({"type":"warn","msg":"HRV em queda nos últimos 7 dias — priorizar recuperação"})
    return alerts

def build_adherence(vol):
    return [{"label":SPORT_LABEL[k],"done":v,"target":round(v*1.1,1),"color":SPORT_COLOR[k]}
            for k, v in vol.items() if v > 0]

# ── Build DB ──────────────────────────────────────────────────────────
def build_db():
    db = {}
    for key, cfg in ATHLETES.items():
        print(f"\n  [{key.upper()}] id={cfg['id']}")
        try:
            raw_w  = fetch_workouts(cfg["id"], days=180)  # 180 dias para EMA preciso
            raw_f  = fetch_fitness(cfg["id"],  weeks=8)
            raw_we = fetch_wellness(cfg["id"],  days=14)

            sessions, vol, zones = process_workouts(raw_w, display_days=7)
            total_vol = sum(vol.values())
            print(f"    processado: {len(sessions)} sessões (7d), vol={total_vol:.1f}h (7d)")

            # Fallback se não chegaram dados reais
            if len(sessions) < 1 and total_vol < 0.5:
                print(f"    sem dados — usando protótipo")
                entry = json.loads(json.dumps(PROTOTYPE[key]))
                entry["alerts"] = [{"type":"warn","msg":"Dados em sincronização com o TrainingPeaks"}]
                db[key] = entry
                continue

            kpis      = build_kpis(raw_f, raw_w)
            kpi_delta = build_deltas(raw_f, raw_w)
            pmc       = build_pmc(raw_f, raw_w)
            hrv       = build_hrv(raw_we)
            alerts    = build_alerts(kpis, hrv)
            adherence = build_adherence(vol)

            print(f"    CTL={kpis['ctl']} ATL={kpis['atl']} TSB={kpis['tsb']} TSS={kpis['tss_week']}")
            db[key] = {"kpis":kpis,"kpi_delta":kpi_delta,"pmc":pmc,"zones":zones,
                       "vol":vol,"hrv":hrv,"adherence":adherence,"alerts":alerts,"sessions":sessions}

        except Exception as e:
            print(f"    ERRO: {e} — usando protótipo")
            entry = json.loads(json.dumps(PROTOTYPE[key]))
            entry["alerts"] = [{"type":"warn","msg":f"Erro ao buscar dados: {e}"}]
            db[key] = entry
    return db

# ── Injeta no template ────────────────────────────────────────────────
def inject(db):
    with open("template.html", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__NPC_DATA__",  json.dumps(db, ensure_ascii=False, indent=2))
    html = html.replace("__GENERATED__", datetime.utcnow().strftime("%d/%m/%Y %H:%M") + " UTC")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  index.html gerado ({len(html)//1024} KB)")

# ── Main ──────────────────────────────────────────────────────────────
def main():
    print("=== NPC Dashboard Generator v4 ===")
    print(f"Data: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
    print("\n[1/3] Buscando dados do TrainingPeaks...")
    db = build_db()
    print("\n[2/3] Injetando no template...")
    inject(db)
    print("[3/3] Concluído.")

if __name__ == "__main__":
    main()
