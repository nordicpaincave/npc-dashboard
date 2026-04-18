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
    "rafael":  {"id": None,    "name": "Rafael Lemos"},
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
    "rafael": {
        "kpis":{"ctl":0,"atl":0,"tsb":0,"tss_week":0},
        "kpi_delta":{"ctl":"—","atl":"—","tsb":"—","tss_week":"—"},
        "pmc":{"labels":["S1","S2","S3","S4","S5","S6","S7","S8"],
               "ctl":[0,0,0,0,0,0,0,0],"atl":[0,0,0,0,0,0,0,0],"tsb":[0,0,0,0,0,0,0,0]},
        "zones":{"labels":["Natação","Bike","Corrida"],"z1":[80,80,80],"z2":[15,15,15],"z3":[5,5,5]},
        "vol":{"swim":0,"bike":0,"run":0,"strength":0},
        "hrv":{"labels":[],"vals":[],"baseline":0,"sleep":[],"resting_hr":[],"body_battery":[]},
        "adherence":[],
        "alerts":[{"type":"info","msg":"TP ID pendente — dados disponíveis após integração"}],
        "sessions":[],"planned":{},"week_notes":{}
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
    # TP migrou para Bearer token — usa TP_BEARER se disponível, senão tenta TP_COOKIE
    bearer = os.environ.get("TP_BEARER", "")
    cookie = os.environ.get("TP_COOKIE", "")
    if bearer:
        return {
            "Authorization": f"Bearer {bearer}",
            "Accept":        "application/json, text/javascript, */*; q=0.01",
            "Content-Type":  "application/json",
            "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin":        "https://app.trainingpeaks.com",
            "Referer":       "https://app.trainingpeaks.com/",
        }
    elif cookie:
        return {
            "Cookie":     f"Production_tpAuth={cookie}",
            "Accept":     "application/json",
            "User-Agent": "Mozilla/5.0",
        }
    else:
        raise ValueError("Nenhuma credencial do TP encontrada. Configure TP_BEARER ou TP_COOKIE nos secrets do GitHub.")

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
    """Busca métricas diárias (HRV, sono, FC repouso) via endpoint consolidatedtimedmetrics."""
    end   = datetime.utcnow()
    start = end - timedelta(days=days)
    s, e  = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    try:
        data = tp_get(f"/metrics/v3/athletes/{athlete_id}/consolidatedtimedmetrics/{s}/{e}")
        if data:
            if isinstance(data, dict):
                data = data.get("Items") or data.get("items") or []
            print(f"    metrics: {len(data)} registros")
            return data
    except Exception as ex:
        print(f"    metrics: erro — {ex}")
    return []

# ── Busca notas semanais do calendário ───────────────────────────────
def fetch_calendar_notes(athlete_id):
    """Busca as notas de planejamento semanal do coach (aparecem nas segundas no TP)."""
    # Busca do início do plano (março 2026) até a prova (outubro 2026)
    s = "2026-03-01"
    e = "2026-10-05"
    try:
        data = tp_get(f"/fitness/v1/athletes/{athlete_id}/calendarNote/{s}/{e}")
        notes = data if isinstance(data, list) else []
        print(f"    calendar notes: {len(notes)} notas")
        return notes
    except Exception as ex:
        print(f"    calendar notes: erro — {ex}")
        return []

def process_calendar_notes(raw_notes):
    """Converte notas do TP em dict {week_num: {title, body, date}}."""
    if not raw_notes:
        return {}

    # Debug: mostra campos da primeira nota para diagnóstico
    first = raw_notes[0] if raw_notes else {}
    debug_keys = {k: str(v)[:60] for k, v in first.items()
                  if v and k not in ('athleteId','id')}
    print(f"    DEBUG note fields: {debug_keys}")

    result = {}
    for note in raw_notes:
        # Data da nota — tenta vários campos
        date_str = str(
            note.get("date") or note.get("startDate") or
            note.get("noteDate") or note.get("timeStamp") or ""
        )[:10]
        if not date_str or date_str < "2026-01-01":
            continue

        # Título e corpo separados no TP
        title_raw = (note.get("title") or note.get("subject") or
                     note.get("name") or "").strip()
        body_raw  = (note.get("description") or note.get("text") or
                     note.get("coachNote") or note.get("body") or
                     note.get("note") or "").strip()

        # Combina tudo: título + corpo
        if title_raw and body_raw:
            full_text = f"{title_raw}\n\n{body_raw}"
        else:
            full_text = title_raw or body_raw
        if not full_text:
            continue

        # Número da semana no plano (semana 1 = 16/mar/2026)
        try:
            dt         = datetime.strptime(date_str, "%Y-%m-%d")
            week1_start = datetime(2026, 3, 16)
            week_num   = int((dt - week1_start).days / 7) + 1
            if 1 <= week_num <= 29:
                result[week_num] = {
                    "date":  date_str,
                    "title": title_raw or full_text[:60],
                    "body":  full_text,
                }
        except Exception:
            continue

    print(f"    notas processadas: {len(result)} semanas com conteúdo")
    return result


METRIC_TYPES = {
    60: "hrv",          # HRV
    6:  "sleep_h",      # Sleep Hours
    46: "deep_sleep",   # Deep Sleep
    47: "rem_sleep",    # REM Sleep
    48: "light_sleep",  # Light Sleep
    5:  "resting_hr",   # Pulse/FC repouso
    64: "body_battery", # Body Battery [min, max, avg]
    62: "stress",       # Stress Level [?, max, avg]
}

# ── Processamento de workouts ─────────────────────────────────────────
def process_workouts(raw, display_days=7):
    """Processa workouts. raw pode ter até 75 dias (para PMC);
    O volume e sessões exibidos são da semana calendário atual (seg a hoje)."""
    sessions, vol, zones_acc = [], {"swim":0.0,"bike":0.0,"run":0.0,"strength":0.0}, {}

    # Semana calendário atual: de segunda-feira até hoje
    today    = datetime.utcnow()
    monday   = today - timedelta(days=today.weekday())
    cutoff_display = monday.strftime("%Y-%m-%d")
    print(f"    janela de exibição: {cutoff_display} → {today.strftime('%Y-%m-%d')}")

    for w in raw:
        # Sport pelo ID numérico
        sport = SPORT_ID.get(int(w.get("workoutTypeValueId") or 0))
        if not sport:
            name = (w.get("athleteWorkoutTypeName") or w.get("title") or "").lower()
            for k, kws in [
                ("swim",     ["swim","pool","natação","natacao","open water"]),
                ("bike",     ["bike","cycl","ride","ciclismo","bicicleta","pedal","zwift"]),
                ("run",      ["run","corr","trail","treadmill","atletismo"]),
                ("strength", ["strength","weight","gym","força","forca","musculação",
                              "musculacao","muscula","funcional","mobilidade","core",
                              "unilateral","bilateral","hipertrofia","alfredson"]),
            ]:
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
        tss_actual = float(w.get("tssActual") or 0)
        hr_tss     = float(w.get("hrTss")     or w.get("hrTSS") or 0)
        s_tss      = float(w.get("sTss")      or w.get("sTSS")  or 0)

        # TSS real: usa tssActual, senão hrTSS, senão sTSS
        tss = round(tss_actual or hr_tss or s_tss)

        # Todos os esportes: exige pelo menos um TSS > 0 (sinal de execução real)
        # tssActual → bike/corrida via potenciômetro ou pace
        # hrTSS     → força e cardio via FC
        # sTSS      → natação
        if tss_actual <= 0 and hr_tss <= 0 and s_tss <= 0:
            continue  # planejado sem execução

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

        # Sessões visíveis: apenas últimos 7 dias (display_days)
        if workout_day >= cutoff_display:
            sessions.append({"day":day,"sport":sport,"desc":title,
                             "dur":dur_str,"tss":tss,"zones":f"{pz[0]}/{pz[1]}/{pz[2]}",
                             "date":workout_day})

    # Treinos planejados (próximas 4 semanas) para o calendário
    today_str  = datetime.utcnow().strftime("%Y-%m-%d")
    future_cut = (datetime.utcnow() + timedelta(days=28)).strftime("%Y-%m-%d")
    planned = []
    for w in raw:
        wd = str(w.get("workoutDay",""))[:10]
        if wd < today_str or wd > future_cut:
            continue
        tss_a = float(w.get("tssActual") or 0)
        if tss_a > 0:
            continue  # já foi executado
        sport_p = SPORT_ID.get(int(w.get("workoutTypeValueId") or 0))
        if not sport_p:
            continue
        tss_p = round(float(w.get("tssPlanned") or 0))
        try:
            dt_p  = datetime.strptime(wd, "%Y-%m-%d")
            day_p = DAYS_PT[dt_p.weekday()]
        except Exception:
            day_p = "?"
        title_p = w.get("title") or SPORT_LABEL.get(sport_p, "Treino")
        planned.append({"day":day_p,"sport":sport_p,"desc":title_p,"tss":tss_p,"date":wd})

    # Volume exibido: apenas últimos 14 dias, apenas treinos realizados
    vol_display = {"swim":0.0,"bike":0.0,"run":0.0,"strength":0.0}
    for w in raw:
        workout_day_w = str(w.get("workoutDay",""))[:10]
        if workout_day_w < cutoff_display:
            continue

        sport_w = SPORT_ID.get(int(w.get("workoutTypeValueId") or 0))
        if not sport_w:
            name_w = (w.get("athleteWorkoutTypeName") or w.get("title") or "").lower()
            for k, kws in [
                ("swim",     ["swim","pool","natação","natacao"]),
                ("bike",     ["bike","cycl","ride","ciclismo","pedal"]),
                ("run",      ["run","corr","trail"]),
                ("strength", ["strength","weight","gym","força","forca","musculação",
                              "musculacao","muscula","funcional","mobilidade","core",
                              "unilateral","bilateral","alfredson"]),
            ]:
                if any(kw in name_w for kw in kws):
                    sport_w = k; break
        if not sport_w:
            continue

        tss_a      = float(w.get("tssActual") or 0)
        hr_tss_w   = float(w.get("hrTss") or w.get("hrTSS") or 0)
        s_tss_w    = float(w.get("sTss")  or w.get("sTSS")  or 0)

        # Qualquer TSS > 0 = treino executado (mesmo critério para todos os esportes)
        if tss_a <= 0 and hr_tss_w <= 0 and s_tss_w <= 0:
            continue

        raw_time_w = float(w.get("totalTime") or 0)

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

    return sessions, planned, {k:round(v,1) for k,v in vol_display.items()}, {"labels":zl,"z1":z1l,"z2":z2l,"z3":z3l}

# ── PMC ───────────────────────────────────────────────────────────────
def calc_pmc_from_workouts(raw_w):
    """
    Fórmula exata do TrainingPeaks (Bannister):
    CTL_t = CTL_{t-1} + (TSS_t - CTL_{t-1}) * (1 - e^(-1/42))
    ATL_t = ATL_{t-1} + (TSS_t - ATL_{t-1}) * (1 - e^(-1/7))
    """
    import math
    kc = 1 - math.exp(-1 / 42)   # ≈ 0.02353 — igual ao TP
    ka = 1 - math.exp(-1 / 7)    # ≈ 0.13212 — igual ao TP

    daily = {}
    for w in raw_w:
        day     = str(w.get("workoutDay",""))[:10]
        tss_val = (float(w.get("tssActual") or 0) or
                   float(w.get("hrTss") or w.get("hrTSS") or 0) or
                   float(w.get("sTss")  or w.get("sTSS")  or 0))
        has_time = float(w.get("totalTime") or 0) > 0
        if tss_val > 0 and has_time:
            daily[day] = daily.get(day, 0) + min(tss_val, 300)
    for d in daily:
        daily[d] = min(daily[d], 500)  # cap diário

    end   = datetime.utcnow()
    dates = [(end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(74, -1, -1)]
    ctl, atl = 0.0, 0.0
    history  = []
    for d in dates:
        tss = daily.get(d, 0)
        ctl = ctl + (tss - ctl) * kc
        atl = atl + (tss - atl) * ka
        history.append({"date": d, "ctl": ctl, "atl": atl, "tsb": ctl - atl, "tss": tss})
    return history


def _past_workouts_with_ctl(raw_w):
    """Retorna workouts passados com CTL calculado pelo TP (campo ctl > 0)."""
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

    # TSS semanal: semana calendário atual (segunda a hoje)
    today_dt = datetime.utcnow()
    monday   = (today_dt - timedelta(days=today_dt.weekday())).strftime("%Y-%m-%d")
    tss_week = round(sum(
        float(w.get("tssActual") or 0) +
        float(w.get("hrTss") or w.get("hrTSS") or 0) +
        float(w.get("sTss")  or w.get("sTSS")  or 0)
        for w in raw_w
        if today >= str(w.get("workoutDay",""))[:10] >= monday
        and (float(w.get("tssActual") or 0) > 0 or
             float(w.get("hrTss") or w.get("hrTSS") or 0) > 0 or
             float(w.get("sTss")  or w.get("sTSS")  or 0) > 0)
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
    """Extrai HRV, sono e FC repouso dos dados de métricas consolidadas do TP."""
    if not raw_we:
        return {
            "labels": [], "vals": [], "baseline": 0,
            "sleep": [], "resting_hr": [], "body_battery": []
        }

    records = sorted(raw_we, key=lambda x: str(x.get("timeStamp", x.get("date", ""))))

    labels, hrv_vals, sleep_vals, hr_vals, battery_vals = [], [], [], [], []

    for r in records:
        # Data
        ts = str(r.get("timeStamp") or r.get("date",""))[:10]
        try:
            labels.append(datetime.strptime(ts, "%Y-%m-%d").strftime("%d/%m"))
        except Exception:
            labels.append("?")

        # Extrai métricas dos details
        hrv = sleep = hr = battery = None
        for detail in (r.get("details") or []):
            t = detail.get("type")
            v = detail.get("value")
            if t == 60 and v is not None:    hrv     = round(float(v))
            elif t == 6 and v is not None:   sleep   = round(float(v), 1)
            elif t == 5 and v is not None:   hr      = round(float(v))
            elif t == 64 and isinstance(v, list) and len(v) >= 3:
                battery = round(float(v[2])) if v[2] is not None else None

        hrv_vals.append(hrv or 0)
        sleep_vals.append(sleep or 0)
        hr_vals.append(hr or 0)
        battery_vals.append(battery or 0)

    valid_hrv = [v for v in hrv_vals if v > 0]
    baseline  = round(sum(valid_hrv) / len(valid_hrv)) if valid_hrv else 0

    return {
        "labels":       labels,
        "vals":         hrv_vals,
        "baseline":     baseline,
        "sleep":        sleep_vals,
        "resting_hr":   hr_vals,
        "body_battery": battery_vals,
    }

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
    result = []
    for k, color in [("swim","#4a9eff"),("bike","#f5a623"),("run","#4db87a"),("strength","#9b8fff")]:
        done = vol.get(k, 0)
        # Força sempre aparece — target estimado em 1.5h se não foi feito nada
        if k == "strength":
            target = max(round(done * 1.1, 1), 1.5) if done > 0 else 1.5
            result.append({"label": SPORT_LABEL[k], "done": done, "target": target, "color": color})
        elif done > 0:
            result.append({"label": SPORT_LABEL[k], "done": done, "target": round(done * 1.1, 1), "color": color})
    return result

# ── Build DB ──────────────────────────────────────────────────────────
def build_db():
    db = {}
    for key, cfg in ATHLETES.items():
        print(f"\n  [{key.upper()}] id={cfg['id']}")
        if cfg.get("id") is None:
            print(f"    sem TP ID — usando protótipo vazio")
            db[key] = json.loads(json.dumps(PROTOTYPE[key]))
            continue
        try:
            raw_w  = fetch_workouts(cfg["id"], days=75)
            raw_f  = fetch_fitness(cfg["id"],  weeks=8)
            raw_we = fetch_wellness(cfg["id"],  days=14)
            raw_cn = fetch_calendar_notes(cfg["id"])

            sessions, planned, vol, zones = process_workouts(raw_w, display_days=7)
            total_vol = sum(vol.values())
            week_notes = process_calendar_notes(raw_cn)
            print(f"    processado: {len(sessions)} sessões, vol={total_vol:.1f}h, {len(week_notes)} notas semanais")

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
                       "vol":vol,"hrv":hrv,"adherence":adherence,"alerts":alerts,
                       "sessions":sessions,"planned":planned,"week_notes":week_notes}

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
