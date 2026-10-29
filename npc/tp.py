"""Cliente mínimo da API do TrainingPeaks (mesmos endpoints do conector MCP).

Autenticação: o cookie Production_tpAuth (secret TP_COOKIE) é trocado em
/users/v3/token por um access token de ~1h a cada execução.
"""
import os, time
import requests

TP_BASE = "https://tpapi.trainingpeaks.com"


class TPAuthError(RuntimeError):
    """Credencial do TrainingPeaks ausente, expirada ou recusada."""


_token = {"value": None, "exp": 0.0}


def _cookie():
    cookie = os.environ.get("TP_COOKIE", "").strip().strip('"').strip("'")
    if cookie.startswith("Production_tpAuth="):
        cookie = cookie.split("=", 1)[1]
    if not cookie:
        raise TPAuthError("Secret TP_COOKIE ausente. Configure em Settings → Secrets and variables → Actions.")
    return cookie


def access_token(force=False):
    if not force and _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    r = requests.get(f"{TP_BASE}/users/v3/token",
                     headers={"Cookie": f"Production_tpAuth={_cookie()}", "Accept": "application/json"},
                     timeout=20)
    if r.status_code in (401, 403):
        raise TPAuthError(f"Cookie Production_tpAuth expirado ou inválido (HTTP {r.status_code}). Atualize o secret TP_COOKIE.")
    r.raise_for_status()
    data = r.json()
    tok = data.get("token") or {}
    if data.get("success") is False or not tok.get("access_token"):
        raise TPAuthError("Resposta inesperada de /users/v3/token — sem access_token.")
    _token["value"] = tok["access_token"]
    _token["exp"] = time.time() + float(tok.get("expires_in") or 3600)
    print(f"  token TP renovado (expira em {int(float(tok.get('expires_in') or 3600)) // 60} min)")
    return _token["value"]


def _req(method, path, json=None, raw=False):
    for attempt in (0, 1):
        h = {"Authorization": f"Bearer {access_token(force=attempt == 1)}", "Accept": "application/json"}
        if json is not None:
            h["Content-Type"] = "application/json"
        r = requests.request(method, f"{TP_BASE}{path}", headers=h, json=json, timeout=60)
        if r.status_code != 401:
            break
    if r.status_code == 401:
        raise TPAuthError(f"401 mesmo com token novo em {path}")
    r.raise_for_status()
    if raw:
        return r
    return r.json() if r.content else None


def get(path):
    return _req("GET", path)


def post(path, body):
    return _req("POST", path, json=body)


def get_raw(path):
    return _req("GET", path, raw=True)


# ── Chamadas usadas pelo dashboard ────────────────────────────────────
def workouts(athlete_id, start, end):
    """Treinos (planejados e realizados). A API limita a janela: busca em blocos de 80 dias."""
    from datetime import timedelta
    out, s = [], start
    while s <= end:
        e = min(s + timedelta(days=79), end)
        data = get(f"/fitness/v6/athletes/{athlete_id}/workouts/{s:%Y-%m-%d}/{e:%Y-%m-%d}") or []
        if isinstance(data, dict):
            data = data.get("Items") or data.get("items") or data.get("workouts") or []
        out.extend(data)
        s = e + timedelta(days=1)
    return out


def performance(athlete_id, start, end):
    """PMC do próprio TP (CTL/ATL/TSB e TSS diário, inclusive força que não aparece na lista)."""
    body = {"atlConstant": 7, "atlStart": 0, "ctlConstant": 42, "ctlStart": 0, "workoutTypes": []}
    return post(f"/fitness/v1/athletes/{athlete_id}/reporting/performancedata/{start:%Y-%m-%d}/{end:%Y-%m-%d}", body) or []


def metrics(athlete_id, start, end):
    data = get(f"/metrics/v3/athletes/{athlete_id}/consolidatedtimedmetrics/{start:%Y-%m-%d}/{end:%Y-%m-%d}") or []
    if isinstance(data, dict):
        data = data.get("Items") or data.get("items") or []
    return data


def workout_files(athlete_id, workout_id):
    d = get(f"/fitness/v6/athletes/{athlete_id}/workouts/{workout_id}/details") or {}
    return [f for f in (d.get("workoutDeviceFileInfos") or []) if isinstance(f, dict) and f.get("fileId") is not None]


def download_file(athlete_id, workout_id, file_id):
    r = get_raw(f"/fitness/v6/athletes/{athlete_id}/workouts/{workout_id}/rawfiledata/{file_id}")
    name = None
    cd = r.headers.get("Content-Disposition") or ""
    if "filename=" in cd:
        name = cd.split("filename=", 1)[1].split(";")[0].strip().strip('"')
    return name, r.content
