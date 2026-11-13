"""Cliente mínimo da API do Intervals.icu para o dashboard (substitui npc/tp.py desde 16/11/2026).

Expõe as MESMAS funções de npc/tp.py (workouts, performance, metrics, workout_files,
download_file, access_token, TPAuthError) e devolve dicionários com as MESMAS chaves
do TrainingPeaks — assim o generate.py não muda a lógica, só a fonte.

Autenticação: Basic "API_KEY:<chave>" com a chave da conta NPC (treinadora do atleta),
no secret INTERVALS_API_KEY. O id do atleta (ex.: i793767) vem do ATHLETES do generate.py.
"""
import os
from datetime import date, timedelta

import requests

ICU_BASE = "https://intervals.icu/api/v1"


class TPAuthError(RuntimeError):
    """Credencial ausente ou recusada (nome mantido para o generate.py não mudar)."""


AuthError = TPAuthError

# Intervals type → id numérico de esporte que o generate.py já entende (SPORT)
_TYPE_ID = {
    "Ride": 2, "VirtualRide": 2, "GravelRide": 2, "MountainBikeRide": 2, "EBikeRide": 2, "TrackRide": 2,
    "Run": 3, "VirtualRun": 3, "TrailRun": 3, "Treadmill": 3,
    "Swim": 1, "OpenWaterSwim": 1,
    "WeightTraining": 9, "Workout": 9, "Yoga": 9, "Pilates": 9,
}

_s = None


def _session():
    global _s
    if _s is None:
        key = os.environ.get("INTERVALS_API_KEY", "").strip()
        if not key:
            raise TPAuthError("Secret INTERVALS_API_KEY ausente. Configure em Settings → Secrets and variables → Actions.")
        _s = requests.Session()
        _s.auth = ("API_KEY", key)
    return _s


def _get(path, params=None, raw=False):
    r = _session().get(f"{ICU_BASE}{path}", params=params, timeout=90)
    if r.status_code in (401, 403):
        raise TPAuthError(f"Intervals recusou a chave ({r.status_code}) em {path}. "
                          "Confira o secret INTERVALS_API_KEY e se a conta NPC é 'Coach' do atleta.")
    r.raise_for_status()
    return r if raw else r.json()


def access_token(force=False):
    """Valida a chave (o generate.py chama no início)."""
    _get("/athlete/0")
    return "ok"


def _num(id_):
    s = str(id_ or "").lstrip("iI")
    try:
        return int(s)
    except ValueError:
        return None


def _activities(athlete_id, start, end):
    return _get(f"/athlete/{athlete_id}/activities", {"oldest": f"{start:%Y-%m-%d}", "newest": f"{end:%Y-%m-%d}"}) or []


def _events(athlete_id, start, end):
    return _get(f"/athlete/{athlete_id}/events", {"oldest": f"{start:%Y-%m-%d}", "newest": f"{end:%Y-%m-%d}"}) or []


def _messages(activity_id):
    try:
        data = _get(f"/activity/{activity_id}/messages")
        return data if isinstance(data, list) else []
    except TPAuthError:
        raise
    except Exception:
        return []


def _plan_fields(ev):
    if not ev:
        return {}
    mt = ev.get("moving_time") or (ev.get("workout_doc") or {}).get("duration")
    return {"title": ev.get("name") or "", "description": ev.get("description") or "",
            "totalTimePlanned": (mt / 3600) if mt else None, "tssPlanned": ev.get("icu_training_load"),
            "distancePlanned": ev.get("distance"), "ifPlanned": None}


def workouts(athlete_id, start, end):
    """Treinos planejados (eventos WORKOUT/descanso) e realizados (atividades), fundidos como o TP fazia:
    atividade casada com o planejado (paired_event_id ou mesmo dia + esporte) vira UM item."""
    acts = sorted(_activities(athlete_id, start, end), key=lambda a: a.get("start_date_local") or "")
    evs = [e for e in _events(athlete_id, start, end)
           if e.get("category") == "WORKOUT" or (e.get("category") == "NOTE" and (e.get("name") or "").lower().startswith("descanso"))]
    by_id = {e.get("id"): e for e in evs}
    used = set()
    out = []
    for a in acts:
        day = (a.get("start_date_local") or "")[:10]
        tid = _TYPE_ID.get(a.get("type"), 100)
        ev = by_id.get(a.get("paired_event_id"))
        if ev is None:
            ev = next((e for e in evs if e.get("id") not in used and e.get("category") == "WORKOUT"
                       and (e.get("start_date_local") or "")[:10] == day
                       and _TYPE_ID.get(e.get("type"), 100) == tid), None)
        if ev is not None:
            used.add(ev.get("id"))
        comments = []
        if (a.get("description") or "").strip():
            comments.append({"commenterName": "Atleta", "comment": a["description"]})
        for m in _messages(a.get("id")):
            if not m.get("deleted") and (m.get("content") or "").strip():
                comments.append({"commenterName": m.get("name") or "", "comment": m["content"]})
        item = {
            "workoutId": _num(a.get("id")), "workoutDay": day, "workoutTypeValueId": tid,
            "title": a.get("name") or "", "description": "",
            "totalTime": (a.get("moving_time") or 0) / 3600 or None,
            "tssActual": a.get("icu_training_load"), "distance": a.get("distance"),
            "if": (a.get("icu_intensity") or 0) / 100 or None,
            "normalizedPowerActual": a.get("icu_weighted_avg_watts"),
            "powerAverage": a.get("icu_average_watts") or a.get("average_watts"),
            "heartRateAverage": a.get("average_heartrate"), "heartRateMaximum": a.get("max_heartrate"),
            "cadenceAverage": a.get("average_cadence"), "velocityAverage": a.get("average_speed"),
            "elevationGain": a.get("total_elevation_gain"),
            "rpe": a.get("icu_rpe") or a.get("perceived_exertion"),
            # feel do Intervals 1 (forte) … 5 (fraco) → escala crua do TP 1–9 ímpar (1 = muito forte),
            # que é a que o template (feelIdx) entende
            "feeling": (2 * int(a["feel"]) - 1) if isinstance(a.get("feel"), (int, float)) and 1 <= a["feel"] <= 5 else None,
            "workoutComments": comments,
        }
        item.update({k: v for k, v in _plan_fields(ev).items() if v not in (None, "")})
        out.append(item)
    for e in evs:
        if e.get("id") in used:
            continue
        rest = e.get("category") == "NOTE"
        item = {"workoutId": e.get("id"), "workoutDay": (e.get("start_date_local") or "")[:10],
                "workoutTypeValueId": 7 if rest else _TYPE_ID.get(e.get("type"), 100),
                "totalTime": None, "tssActual": None, "workoutComments": []}
        item.update(_plan_fields(e))
        out.append(item)
    return out


def performance(athlete_id, start, end):
    """PMC do próprio Intervals (CTL/ATL do wellness) + carga diária somada das atividades."""
    well = _get(f"/athlete/{athlete_id}/wellness", {"oldest": f"{start:%Y-%m-%d}", "newest": f"{end:%Y-%m-%d}"}) or []
    load = {}
    for a in _activities(athlete_id, start, end):
        d = (a.get("start_date_local") or "")[:10]
        load[d] = load.get(d, 0.0) + float(a.get("icu_training_load") or 0)
    out = []
    for w in well:
        d = str(w.get("id") or "")[:10]
        ctl, atl = w.get("ctl"), w.get("atl")
        if not d or ctl is None:
            continue
        out.append({"workoutDay": d, "tssActual": round(load.get(d, 0.0), 1), "ctl": ctl, "atl": atl,
                    "tsb": (ctl - atl) if atl is not None else None})
    return out


def metrics(athlete_id, start, end):
    """Wellness no formato consolidatedtimedmetrics do TP (60 = VFC, 5 = FC repouso, 6 = sono h)."""
    well = _get(f"/athlete/{athlete_id}/wellness", {"oldest": f"{start:%Y-%m-%d}", "newest": f"{end:%Y-%m-%d}"}) or []
    out = []
    for w in well:
        det = []
        if w.get("hrv") is not None:
            det.append({"type": 60, "value": w["hrv"]})
        if w.get("restingHR") is not None:
            det.append({"type": 5, "value": w["restingHR"]})
        if w.get("sleepSecs"):
            det.append({"type": 6, "value": round(w["sleepSecs"] / 3600, 2)})
        if det:
            out.append({"timeStamp": str(w.get("id"))[:10], "details": det})
    return out


def workout_files(athlete_id, workout_id):
    """Intervals guarda o arquivo original na própria atividade: devolve um 'fileId' simbólico."""
    return [{"fileId": "original"}]


def download_file(athlete_id, workout_id, file_id):
    aid = f"i{_num(workout_id)}"
    r = _get(f"/activity/{aid}/file", raw=True)
    name = None
    cd = r.headers.get("Content-Disposition") or ""
    if "filename=" in cd:
        name = cd.split("filename=", 1)[1].split(";")[0].strip().strip('"')
    return name or f"{aid}.fit.gz", r.content
