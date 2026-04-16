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
SPORT_KEYS = {
    "swim": ["swim", "natacao", "natação", "pool", "openwater"],
    "bike": ["bike", "cycling", "cycle", "ciclismo", "ride", "virtualride"],
    "run":  ["run", "corrida", "trail", "treadmill"],
    "strength": ["strength", "forca", "força", "weight", "gym", "core"],
}


def map_sport(raw):
    raw = (raw or "").lower().replace(" ", "")
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
    zones    = {}  # sport → [z1_secs, z2_secs, z3_secs]

    for w in (raw or []):
        sport_raw = (
            w.get("athleteWorkoutTypeName")
            or w.get("workoutTypeName")
            or w.get("type", "")
        )
        sport = map_sport(sport_raw)
        if not sport:
            continue

        # Duração
        dur_secs = float(w.get("totalTime") or w.get("movingTime") or 0)
        dur_h    = dur_secs / 3600
        hh, mm   = int(dur_h), int((dur_h % 1) * 60)
        dur_str  = f"{hh}h{mm:02d}" if hh > 0 else f"{mm}min"

        # TSS
        tss = round(float(w.get("tss") or w.get("totalTrainingStressScore") or 0))

        # Dia da semana
        try:
            dt      = datetime.strptime(str(w.get("workoutDay", ""))[:10], "%Y-%m-%d")
            day_str = DAYS_PT[dt.weekday()]
        except Exception:
            day_str = "?"

        # Zonas de FC (TP usa 5 zonas — mapeamos para 3 NPC)
        hz = [float(w.get(f"hrZone{i}Duration") or 0) for i in range(1, 6)]
        z1 = hz[0] + hz[1]          # Z1+Z2 TP → Z1 NPC (aeróbico)
        z2 = hz[2] + hz[3]          # Z3+Z4 TP → Z2 NPC (limiar)
        z3 = hz[4]                   # Z5 TP    → Z3 NPC (VO2max)
        total_z = z1 + z2 + z3
        zones_str = (
            f"{round(z1/total_z*100)}/{round(z2/total_z*100)}/{round(z3/total_z*100)}"
            if total_z > 0 else "—"
        )

        # Acumula volumes e zonas
        vol[sport] = round(vol[sport] + dur_h, 2)
        if sport not in zones:
            zones[sport] = [0.0, 0.0, 0.0]
        zones[sport][0] += z1
        zones[sport][1] += z2
        zones[sport][2] += z3

        sessions.append({
            "day":    day_str,
            "sport":  sport,
            "desc":   w.get("title") or sport_raw or "Treino",
            "dur":    dur_str,
            "tss":    tss,
            "zones":  zones_str,
            "hrv":    0,
            "ht":     "nt",
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


# ── Montagem final do objeto DB ───────────────────────────────────────
def build_db():
    db = {}
    for key, cfg in ATHLETES.items():
        print(f"  [{key}] Buscando dados (id={cfg['id']})...")
        try:
            raw_w = get_workouts(cfg["id"], days=14)
            raw_f = get_fitness(cfg["id"],  weeks=8)
            raw_we = []
            try:
                raw_we = get_wellness(cfg["id"], days=14)
            except Exception as e:
                print(f"    HRV indisponível: {e}")

            sessions, vol, zones = process_workouts(raw_w)
            pmc       = process_fitness(raw_f, raw_w)
            kpis      = current_kpis(raw_f, raw_w)
            kpi_delta = kpi_deltas(raw_f, raw_w)
            hrv       = process_wellness(raw_we)
            adherence = compute_adherence(vol, sessions)
            alerts    = compute_alerts(kpis, hrv)

            db[key] = {
                "kpis":       kpis,
                "kpi_delta":  kpi_delta,
                "pmc":        pmc,
                "zones":      zones,
                "vol":        vol,
                "hrv":        hrv,
                "adherence":  adherence,
                "alerts":     alerts,
                "sessions":   sessions,
            }
            print(f"    CTL={kpis['ctl']} ATL={kpis['atl']} TSB={kpis['tsb']} sessions={len(sessions)}")

        except Exception as e:
            print(f"    ERRO: {e}")
            db[key] = {
                "kpis": {"ctl": 0, "atl": 0, "tsb": 0, "tss_week": 0},
                "kpi_delta": {"ctl": "—", "atl": "—", "tsb": "—", "tss_week": "—"},
                "pmc": {"labels": [], "ctl": [], "atl": [], "tsb": []},
                "zones": {"labels": [], "z1": [], "z2": [], "z3": []},
                "vol": {"swim": 0, "bike": 0, "run": 0, "strength": 0},
                "hrv": {"labels": [], "vals": [], "baseline": 0},
                "adherence": [],
                "alerts": [{"type": "warn", "msg": f"Erro ao buscar dados: {e}"}],
                "sessions": [],
            }

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
