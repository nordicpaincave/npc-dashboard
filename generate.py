"""
NPC Endurance — Dashboard Generator
Busca dados do TrainingPeaks via cookie de sessão e injeta no template HTML.
Sem custo adicional — nenhuma API externa paga.

Variáveis de ambiente necessárias:
  TP_COOKIE  — valor do cookie Production_tpAuth do TrainingPeaks
"""

import os
import json
import re
from datetime import datetime, timedelta

import requests

# ── Configuração dos atletas ──────────────────────────────────────────
ATHLETES = {
    "bruno":   {"id": 6285028, "name": "Bruno Trevisan"},
    "jean":    {"id": 6286348, "name": "Jean Romano"},
    "gabriel": {"id": 5775491, "name": "Gabriel"},
}

TP_BASE = "https://tpapi.trainingpeaks.com"


# ── Autenticação ──────────────────────────────────────────────────────
def headers():
    cookie = os.environ["TP_COOKIE"]
    return {
        "Cookie":     f"Production_tpAuth={cookie}",
        "Accept":     "application/json",
        "User-Agent": "Mozilla/5.0",
    }


def tp_get(path):
    url  = f"{TP_BASE}{path}"
    resp = requests.get(url, headers=headers(), timeout=20)
    resp.raise_for_status()
    return resp.json()


# ── Busca de dados ────────────────────────────────────────────────────
def get_workouts(athlete_id, days=14):
    end   = datetime.utcnow()
    start = end - timedelta(days=days)
    return tp_get(
        f"/fitness/v6/athletes/{athlete_id}/workouts"
        f"/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
    )


def get_fitness(athlete_id, weeks=8):
    """Tenta múltiplos endpoints para dados de fitness (CTL/ATL/TSB)."""
    end   = datetime.utcnow()
    start = end - timedelta(weeks=weeks)
    s, e  = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

    candidates = [
        f"/fitness/v6/athletes/{athlete_id}/fitness/{s}/{e}",
        f"/fitness/v6/athletes/{athlete_id}/fitnesssummaries/{s}/{e}",
        f"/fitness/v6/athletes/{athlete_id}/days/{s}/{e}",
        f"/coaching/v6/athletes/{athlete_id}/fitness/{s}/{e}",
    ]
    for path in candidates:
        try:
            data = tp_get(path)
            if data:
                print(f"    fitness endpoint OK: {path}")
                return data
        except Exception:
            continue

    print(f"    fitness endpoint: nenhum funcionou — CTL/ATL/TSB serão calculados dos workouts")
    return []


def get_wellness(athlete_id, days=14):
    end   = datetime.utcnow()
    start = end - timedelta(days=days)
    return tp_get(
        f"/wellness/v6/athletes/{athlete_id}"
        f"/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
    )


# ── Mapeamento de esportes ─────────────────────────────────────────────
# Mapeamento de IDs numéricos do TP → esporte NPC
SPORT_ID_MAP = {
    1:  "swim",   # Swim
    2:  "bike",   # Bike
    3:  "run",    # Run
    4:  "run",    # Run (trail)
    5:  "strength",# Strength
    6:  "strength",# Weight Training
    7:  "strength",# Core
    10: "bike",   # Virtual Ride
    13: None,     # Other — ignorado
    20: "swim",   # Open Water
}

SPORT_KEYS = {
    "swim": ["swim", "natacao", "natação", "pool", "openwater", "open water"],
    "bike": ["bike", "cycling", "cycle", "ciclismo", "ride", "virtualride", "virtual"],
    "run":  ["run", "corrida", "trail", "treadmill", "atletismo"],
    "strength": ["strength", "forca", "força", "weight", "gym", "core", "muscula"],
}


def map_sport(raw_type_id, raw_name=""):
    # Tenta pelo ID numérico primeiro
    if isinstance(raw_type_id, int) or (isinstance(raw_type_id, str) and raw_type_id.isdigit()):
        sport = SPORT_ID_MAP.get(int(raw_type_id))
        if sport:
            return sport

    # Fallback pelo nome
    raw = (raw_name or "").lower().replace(" ", "")
    for key, keywords in SPORT_KEYS.items():
        if any(k in raw for k in keywords):
            return key
    return None


SPORT_LABEL = {"swim": "Natação", "bike": "Bike", "run": "Corrida", "strength": "Força"}
SPORT_COLOR = {"swim": "#4a9eff", "bike": "#f5a623", "run": "#4db87a", "strength": "#9b8fff"}
DAYS_PT     = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


# ── Processamento de workouts ─────────────────────────────────────────
def process_workouts(raw):
    sessions = []
    vol      = {"swim": 0.0, "bike": 0.0, "run": 0.0, "strength": 0.0}
    zones    = {}

    for w in (raw or []):
        # Sport: ID numérico + nome como fallback
        type_id   = w.get("workoutTypeValueId") or w.get("workoutSubTypeId")
        type_name = w.get("athleteWorkoutTypeName") or w.get("workoutTypeName") or w.get("title", "")
        sport     = map_sport(type_id, type_name)
        if not sport:
            continue

        # Duração — totalTime vem em DIAS no TP
        total_time_days = float(w.get("totalTime") or 0)
        dur_h = total_time_days * 24          # converte para horas
        if dur_h < 0.05:                      # ignora sessões < 3min
            continue
        hh, mm   = int(dur_h), int((dur_h % 1) * 60)
        dur_str  = f"{hh}h{mm:02d}" if hh > 0 else f"{mm}min"

        # TSS — campo correto é tssActual
        tss = round(float(w.get("tssActual") or w.get("tss") or
                          w.get("totalTrainingStressScore") or 0))

        # Dia da semana — workoutDay pode ter formato "2026-04-02T00:00:00"
        try:
            dt      = datetime.strptime(str(w.get("workoutDay", ""))[:10], "%Y-%m-%d")
            day_str = DAYS_PT[dt.weekday()]
        except Exception:
            day_str = "?"

        # Zonas — tenta campos HR zone; se não tiver, deixa "—"
        # TP não retorna hrZoneXDuration diretamente no resumo do workout
        z1 = float(w.get("hrZone1Duration") or w.get("heartRateZone1Duration") or 0)
        z2 = float(w.get("hrZone2Duration") or w.get("heartRateZone2Duration") or 0) + \
             float(w.get("hrZone3Duration") or w.get("heartRateZone3Duration") or 0)
        z3 = float(w.get("hrZone4Duration") or w.get("heartRateZone4Duration") or 0) + \
             float(w.get("hrZone5Duration") or w.get("heartRateZone5Duration") or 0)
        total_z   = z1 + z2 + z3
        zones_str = (
            f"{round(z1/total_z*100)}/{round(z2/total_z*100)}/{round(z3/total_z*100)}"
            if total_z > 0 else "—"
        )

        # Volume acumulado
        vol[sport] = round(vol[sport] + dur_h, 2)

        # Zonas por esporte (para gráfico)
        if total_z > 0:
            if sport not in zones:
                zones[sport] = [0.0, 0.0, 0.0]
            zones[sport][0] += z1
            zones[sport][1] += z2
            zones[sport][2] += z3

        # Título limpo
        title = w.get("title") or type_name or "Treino"
        if title.lower() in ("other", ""):
            title = SPORT_LABEL.get(sport, "Treino")

        sessions.append({
            "day":   day_str,
            "sport": sport,
            "desc":  title,
            "dur":   dur_str,
            "tss":   tss,
            "zones": zones_str,
            "hrv":   0,
            "ht":    "nt",
        })

    # Distribuição de zonas por esporte
    zone_labels, z1_list, z2_list, z3_list = [], [], [], []
    for sport in ["swim", "bike", "run"]:
        if sport in zones:
            z1, z2, z3 = zones[sport]
            total = z1 + z2 + z3
            if total > 0:
                zone_labels.append(SPORT_LABEL[sport])
                z1_list.append(round(z1 / total * 100))
                z2_list.append(round(z2 / total * 100))
                z3_list.append(round(z3 / total * 100))

    return (
        sessions,
        {k: round(v, 1) for k, v in vol.items()},
        {"labels": zone_labels, "z1": z1_list, "z2": z2_list, "z3": z3_list},
    )


# ── Processamento de PMC (fitness) ────────────────────────────────────
def calc_pmc_from_workouts(raw_workouts, weeks=8):
    """
    Calcula CTL/ATL/TSB a partir dos workouts quando o endpoint de fitness falha.
    CTL = EMA 42 dias do TSS diário
    ATL = EMA 7 dias do TSS diário
    TSB = CTL - ATL
    """
    # Monta dicionário de TSS diário
    daily = {}
    for w in (raw_workouts or []):
        day = str(w.get("workoutDay", ""))[:10]
        if not day:
            continue
        tss = float(w.get("tss") or w.get("totalTrainingStressScore") or 0)
        daily[day] = daily.get(day, 0) + tss

    # Gera série de datas (56 dias = 8 semanas)
    end   = datetime.utcnow()
    dates = [(end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(55, -1, -1)]

    ctl, atl = 50.0, 50.0  # valores iniciais típicos
    k_ctl, k_atl = 2/(42+1), 2/(7+1)

    history = []
    for d in dates:
        tss   = daily.get(d, 0)
        ctl   = tss * k_ctl + ctl * (1 - k_ctl)
        atl   = tss * k_atl + atl * (1 - k_atl)
        tsb   = ctl - atl
        history.append({"date": d, "ctl": ctl, "atl": atl, "tsb": tsb,
                         "tss": tss})

    return history


def process_fitness(raw, raw_workouts=None):
    # Se não há dados do endpoint, calcula dos workouts
    if not raw:
        raw = calc_pmc_from_workouts(raw_workouts or [])

    records = sorted(raw, key=lambda x: x.get("date", ""))

    # Amostragem semanal (8 pontos)
    n      = len(records)
    step   = max(1, n // 8)
    sample = records[::step][-8:]

    labels, ctl_l, atl_l, tsb_l = [], [], [], []
    for r in sample:
        try:
            dt = datetime.strptime(str(r["date"])[:10], "%Y-%m-%d")
            labels.append(dt.strftime("%d/%m"))
        except Exception:
            labels.append("?")
        ctl_l.append(round(float(r.get("ctl") or 0)))
        atl_l.append(round(float(r.get("atl") or 0)))
        tsb_l.append(round(float(r.get("tsb") or 0)))

    return {"labels": labels, "ctl": ctl_l, "atl": atl_l, "tsb": tsb_l}


def current_kpis(raw_fitness, raw_workouts):
    if not raw_fitness:
        raw_fitness = calc_pmc_from_workouts(raw_workouts or [])

    records  = sorted(raw_fitness, key=lambda x: x.get("date", ""))
    latest   = records[-1] if records else {}

    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    tss_week = sum(
        round(float(r.get("tss") or 0))
        for r in records
        if str(r.get("date", ""))[:10] >= week_ago
    )

    return {
        "ctl":      round(float(latest.get("ctl") or 0)),
        "atl":      round(float(latest.get("atl") or 0)),
        "tsb":      round(float(latest.get("tsb") or 0)),
        "tss_week": tss_week,
    }


def kpi_deltas(raw_fitness, raw_workouts):
    if not raw_fitness:
        raw_fitness = calc_pmc_from_workouts(raw_workouts or [])

    if not raw_fitness or len(raw_fitness) < 8:
        return {"ctl": "—", "atl": "—", "tsb": "—", "tss_week": "—"}

    records = sorted(raw_fitness, key=lambda x: x.get("date", ""))
    curr    = records[-1]
    prev    = records[-8]

    def fmt(a, b):
        d = round(float(a or 0) - float(b or 0))
        return f"+{d}" if d >= 0 else str(d)

    return {
        "ctl":      fmt(curr.get("ctl"),  prev.get("ctl")),
        "atl":      fmt(curr.get("atl"),  prev.get("atl")),
        "tsb":      fmt(curr.get("tsb"),  prev.get("tsb")),
        "tss_week": "—",
    }


# ── Processamento de HRV / wellness ──────────────────────────────────
def process_wellness(raw):
    if not raw:
        return {"labels": [], "vals": [], "baseline": 0}

    records = sorted(raw, key=lambda x: x.get("date", ""))[-14:]

    labels, vals = [], []
    for r in records:
        try:
            dt = datetime.strptime(str(r["date"])[:10], "%Y-%m-%d")
            labels.append(dt.strftime("%d/%m"))
        except Exception:
            labels.append("?")
        hrv = float(r.get("hrv") or r.get("rmssd") or r.get("hrvScore") or 0)
        vals.append(round(hrv))

    valid    = [v for v in vals if v > 0]
    baseline = round(sum(valid) / len(valid)) if valid else 0

    return {"labels": labels, "vals": vals, "baseline": baseline}


# ── Aderência ─────────────────────────────────────────────────────────
def compute_adherence(vol, sessions):
    """
    Sem acesso a treinos planejados via cookie (requer OAuth),
    estimamos a meta com base no volume atual + 10% como referência.
    """
    result = []
    for sport in ["swim", "bike", "run", "strength"]:
        done = vol.get(sport, 0)
        if done > 0:
            target = round(done * 1.1, 1)   # meta estimada
            result.append({
                "label":  SPORT_LABEL[sport],
                "done":   done,
                "target": target,
                "color":  SPORT_COLOR[sport],
            })
    return result


# ── Alertas automáticos ───────────────────────────────────────────────
def compute_alerts(kpis, hrv_data):
    alerts = []
    tsb = kpis.get("tsb", 0)
    atl = kpis.get("atl", 0)
    ctl = kpis.get("ctl", 1) or 1

    # Overtraining
    if tsb < -15:
        excess = round((atl / ctl - 1) * 100)
        alerts.append({"type": "danger",
                        "msg": f"Risco de overtraining — TSB {tsb}, ATL {excess}% acima da CTL"})
    elif tsb < -5:
        alerts.append({"type": "warn",
                        "msg": f"Fadiga acumulada — TSB {tsb}, monitorar recuperação"})
    elif tsb > 10:
        alerts.append({"type": "ok",
                        "msg": f"Forma positiva — TSB +{tsb}, bom momento para treinos de qualidade"})
    else:
        alerts.append({"type": "ok",
                        "msg": f"Carga equilibrada — TSB {tsb}"})

    # HRV
    vals = [v for v in hrv_data.get("vals", []) if v > 0]
    if len(vals) >= 7:
        recent = vals[-7:]
        older  = vals[-14:-7] if len(vals) >= 14 else []
        if older:
            avg_r = sum(recent) / len(recent)
            avg_o = sum(older)  / len(older)
            if avg_r < avg_o * 0.93:
                alerts.append({"type": "warn",
                                "msg": "HRV em queda nos últimos 7 dias — priorizar sono e recuperação"})

    return alerts


# ── Dados de referência (protótipo) — usados como fallback visual ─────
PROTOTYPE_DB = {
    "bruno": {
        "kpis": {"ctl": 72, "atl": 68, "tsb": 4, "tss_week": 412},
        "kpi_delta": {"ctl": "+3", "atl": "+8", "tsb": "-4", "tss_week": "+31"},
        "pmc": {"labels": ["S1","S2","S3","S4","S5","S6","S7","S8"],
                "ctl": [58,61,65,68,70,74,73,72], "atl": [62,70,75,72,65,78,74,68], "tsb": [-4,-9,-10,-4,5,-4,-1,4]},
        "zones": {"labels": ["Natação","Bike","Corrida"], "z1": [72,68,65], "z2": [22,25,28], "z3": [6,7,7]},
        "vol": {"swim": 2.1, "bike": 5.8, "run": 3.2, "strength": 1.0},
        "hrv": {"labels": ["1/4","2/4","3/4","4/4","5/4","6/4","7/4","8/4","9/4","10/4","11/4","12/4","13/4","14/4"],
                "vals": [56,54,57,59,55,53,58,60,57,54,55,58,59,60], "baseline": 57},
        "adherence": [{"label":"Natação","done":2.1,"target":2.5,"color":"#4a9eff"},{"label":"Bike","done":5.8,"target":6.0,"color":"#f5a623"},{"label":"Corrida","done":3.2,"target":3.5,"color":"#4db87a"},{"label":"Força","done":1.0,"target":1.0,"color":"#9b8fff"}],
        "alerts": [{"type":"ok","msg":"Forma positiva — TSB +4, bom momento para treinos de qualidade"},{"type":"info","msg":"ATL elevada — monitorar recuperação nos próximos 3 dias"}],
        "sessions": [
            {"day":"Seg","sport":"run","desc":"Limiar duplo — 3×10min Z2 + 2×8min Z3","dur":"1h15","tss":82,"zones":"60/30/10","hrv":58,"ht":"up"},
            {"day":"Ter","sport":"swim","desc":"Volume Z1 — 3.200m aeróbico","dur":"1h05","tss":48,"zones":"80/18/2","hrv":55,"ht":"dn"},
            {"day":"Qua","sport":"bike","desc":"Endurance Z1 — 90min fundo","dur":"1h30","tss":65,"zones":"75/22/3","hrv":54,"ht":"nt"},
            {"day":"Qui","sport":"run","desc":"Limiar duplo — 4×6min Z2 + 3×5min Z3","dur":"1h10","tss":78,"zones":"55/32/13","hrv":56,"ht":"up"},
            {"day":"Sex","sport":"swim","desc":"CSS — 8×100m no limiar","dur":"55min","tss":55,"zones":"40/42/18","hrv":57,"ht":"up"},
            {"day":"Sáb","sport":"bike","desc":"Longa Z1 — 3h base aeróbica","dur":"3h00","tss":95,"zones":"80/18/2","hrv":59,"ht":"up"},
        ]
    },
    "jean": {
        "kpis": {"ctl": 85, "atl": 79, "tsb": 6, "tss_week": 498},
        "kpi_delta": {"ctl": "+5", "atl": "+6", "tsb": "+2", "tss_week": "+44"},
        "pmc": {"labels": ["S1","S2","S3","S4","S5","S6","S7","S8"],
                "ctl": [68,72,76,79,82,85,84,85], "atl": [70,78,82,80,76,88,82,79], "tsb": [-2,-6,-6,-1,6,-3,2,6]},
        "zones": {"labels": ["Natação","Bike","Corrida"], "z1": [70,65,60], "z2": [24,28,32], "z3": [6,7,8]},
        "vol": {"swim": 2.8, "bike": 7.2, "run": 4.5, "strength": 1.0},
        "hrv": {"labels": ["1/4","2/4","3/4","4/4","5/4","6/4","7/4","8/4","9/4","10/4","11/4","12/4","13/4","14/4"],
                "vals": [60,62,61,58,60,63,64,62,59,61,63,64,63,65], "baseline": 62},
        "adherence": [{"label":"Natação","done":2.8,"target":3.0,"color":"#4a9eff"},{"label":"Bike","done":7.2,"target":7.0,"color":"#f5a623"},{"label":"Corrida","done":4.5,"target":4.5,"color":"#4db87a"},{"label":"Força","done":1.0,"target":1.0,"color":"#9b8fff"}],
        "alerts": [{"type":"ok","msg":"Excelente aderência — 97% do plano executado esta semana"},{"type":"info","msg":"Buenos Aires (70.3) em 25 semanas — momento de base aeróbica"}],
        "sessions": [
            {"day":"Seg","sport":"bike","desc":"Limiar duplo — 5×8min Z2 + 3×6min Z3","dur":"1h30","tss":95,"zones":"50/36/14","hrv":62,"ht":"up"},
            {"day":"Ter","sport":"swim","desc":"Técnica + CSS — 3.600m","dur":"1h10","tss":58,"zones":"65/28/7","hrv":60,"ht":"nt"},
            {"day":"Qua","sport":"run","desc":"Volume Z1 — 12km fácil","dur":"1h15","tss":62,"zones":"78/20/2","hrv":61,"ht":"up"},
            {"day":"Qui","sport":"bike","desc":"Limiar duplo — FTP intervals","dur":"1h20","tss":88,"zones":"45/38/17","hrv":59,"ht":"dn"},
            {"day":"Sex","sport":"swim","desc":"Endurance — 4.000m Z1/Z2","dur":"1h20","tss":65,"zones":"70/26/4","hrv":62,"ht":"up"},
            {"day":"Sáb","sport":"run","desc":"Longa Z1/Z2 — 18km progressivo","dur":"1h45","tss":100,"zones":"65/28/7","hrv":64,"ht":"up"},
        ]
    },
    "gabriel": {
        "kpis": {"ctl": 58, "atl": 72, "tsb": -14, "tss_week": 380},
        "kpi_delta": {"ctl": "+2", "atl": "+14", "tsb": "-12", "tss_week": "+55"},
        "pmc": {"labels": ["S1","S2","S3","S4","S5","S6","S7","S8"],
                "ctl": [46,49,52,54,56,58,57,58], "atl": [50,55,60,58,52,65,70,72], "tsb": [-4,-6,-8,-4,4,-7,-13,-14]},
        "zones": {"labels": ["Bike","Corrida"], "z1": [60,58], "z2": [28,30], "z3": [12,12]},
        "vol": {"swim": 0, "bike": 5.5, "run": 4.2, "strength": 1.5},
        "hrv": {"labels": ["1/4","2/4","3/4","4/4","5/4","6/4","7/4","8/4","9/4","10/4","11/4","12/4","13/4","14/4"],
                "vals": [58,56,54,52,55,53,51,50,52,51,53,54,55,53], "baseline": 55},
        "adherence": [{"label":"Bike","done":5.5,"target":5.0,"color":"#f5a623"},{"label":"Corrida","done":4.2,"target":4.0,"color":"#4db87a"},{"label":"Força","done":1.5,"target":1.5,"color":"#9b8fff"}],
        "alerts": [{"type":"danger","msg":"Risco de overtraining — TSB −14, ATL 24% acima da CTL"},{"type":"warn","msg":"HRV em queda há 7 dias — priorizar sono e recuperação"}],
        "sessions": [
            {"day":"Seg","sport":"run","desc":"Limiar — 3×10min Z2 pré-duatlon","dur":"1h00","tss":70,"zones":"55/33/12","hrv":52,"ht":"dn"},
            {"day":"Ter","sport":"bike","desc":"Específico duatlon — 3×8min Z3","dur":"1h10","tss":85,"zones":"40/38/22","hrv":50,"ht":"dn"},
            {"day":"Qua","sport":"strength","desc":"Alfredson + estabilização joelho","dur":"40min","tss":25,"zones":"—","hrv":51,"ht":"nt"},
            {"day":"Qui","sport":"run","desc":"Taper ativo — 6km Z1 leve","dur":"40min","tss":35,"zones":"85/13/2","hrv":54,"ht":"up"},
            {"day":"Sex","sport":"bike","desc":"Ativação pré-prova — 30min Z1+strides","dur":"30min","tss":22,"zones":"80/15/5","hrv":55,"ht":"up"},
            {"day":"Sáb","sport":"run","desc":"PROVA — Duatlon 5/20/2.5km (meta sub-56)","dur":"~56min","tss":110,"zones":"20/35/45","hrv":53,"ht":"nt"},
        ]
    },
}


def debug_workout_fields(raw_w, athlete_key):
    """Imprime os campos do primeiro workout para diagnóstico."""
    if not raw_w:
        print(f"    DEBUG [{athlete_key}]: nenhum workout retornado")
        return
    first = raw_w[0] if isinstance(raw_w, list) else raw_w
    print(f"    DEBUG [{athlete_key}]: {len(raw_w)} workouts — campos do 1º: {list(first.keys())}")
    # Campos relevantes
    for f in ["workoutDay","title","athleteWorkoutTypeName","workoutTypeName","type",
              "totalTime","movingTime","tss","totalTrainingStressScore","tssActual",
              "hrZone1Duration","heartRateZone1Duration"]:
        if f in first:
            print(f"      {f}: {first[f]}")


# ── Montagem final do objeto DB ───────────────────────────────────────
def build_db():
    db = {}
    first_athlete = True

    for key, cfg in ATHLETES.items():
        print(f"  [{key}] Buscando dados (id={cfg['id']})...")
        try:
            raw_w  = get_workouts(cfg["id"], days=14)
            raw_f  = get_fitness(cfg["id"],  weeks=8)
            raw_we = []
            try:
                raw_we = get_wellness(cfg["id"], days=14)
            except Exception as e:
                print(f"    HRV indisponível: {e}")

            # Diagnóstico na primeira execução
            if first_athlete:
                debug_workout_fields(raw_w, key)
                first_athlete = False

            sessions, vol, zones = process_workouts(raw_w)
            pmc       = process_fitness(raw_f, raw_w)
            kpis      = current_kpis(raw_f, raw_w)
            kpi_delta = kpi_deltas(raw_f, raw_w)
            hrv       = process_wellness(raw_we)
            adherence = compute_adherence(vol, sessions)
            alerts    = compute_alerts(kpis, hrv)

            # Fallback: usa protótipo se dados reais estiverem vazios
            dados_ok = len(sessions) > 0 or sum(vol.values()) > 0
            if not dados_ok:
                print(f"    dados reais vazios — usando protótipo como fallback visual")
                db[key] = PROTOTYPE_DB[key].copy()
                db[key]["alerts"] = [{"type": "warn",
                    "msg": "Dados em sincronização com o TrainingPeaks — exibindo última referência"}]
            else:
                db[key] = {
                    "kpis": kpis, "kpi_delta": kpi_delta, "pmc": pmc,
                    "zones": zones, "vol": vol, "hrv": hrv,
                    "adherence": adherence, "alerts": alerts, "sessions": sessions,
                }
                print(f"    CTL={kpis['ctl']} ATL={kpis['atl']} TSB={kpis['tsb']} "
                      f"vol={sum(vol.values()):.1f}h sessions={len(sessions)}")

        except Exception as e:
            print(f"    ERRO: {e} — usando protótipo como fallback")
            db[key] = PROTOTYPE_DB[key].copy()
            db[key]["alerts"] = [{"type": "warn", "msg": f"Erro ao buscar dados: {e}"}]

    return db


# ── Injeção no template ───────────────────────────────────────────────
def inject(db):
    with open("template.html", encoding="utf-8") as f:
        html = f.read()

    data_js  = json.dumps(db, ensure_ascii=False, indent=2)
    now_str  = datetime.utcnow().strftime("%d/%m/%Y %H:%M") + " UTC"
    html     = html.replace("__NPC_DATA__",  data_js)
    html     = html.replace("__GENERATED__", now_str)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  index.html gerado ({len(html)//1024} KB)")


# ── Main ──────────────────────────────────────────────────────────────
def main():
    print("=== NPC Dashboard Generator ===")
    print(f"Data: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC\n")

    print("[1/3] Buscando dados do TrainingPeaks...")
    db = build_db()

    print("\n[2/3] Injetando dados no template...")
    inject(db)

    print("\n[3/3] Concluído.")


if __name__ == "__main__":
    main()
