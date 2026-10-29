"""
NPC Endurance — Dashboard Generator v6
Monta o dashboard a partir de DUAS fontes oficiais:

  TrainingPeaks (cookie → token, secret TP_COOKIE)
    · PMC do próprio TP (CTL/ATL/TSB e TSS diário — inclui a força que não sai na lista)
    · treinos planejados e realizados, com as métricas de cada um
    · wellness (HRV, FC de repouso, sono, body battery)
    · arquivo .fit dos testes de lactato

  Supabase (usuário SÓ-LEITURA dashboard_reader, secret SUPABASE_READER_PASSWORD)
    · plano macro ativo (fases e semanas com alvos)
    · provas (athlete_events)
    · passaportes fisiológicos (limiares por esporte, com histórico de versões)
    · amostras de lactato (testes incrementais e calibração de repouso)
    · análises diárias e semanais (daily_recommendations / weekly_analyses)
    · ciclos encerrados → files/historico/<atleta>/<ciclo>.json (treinos + análises)

Política de erro: se o TP ou o Supabase falhar, sai com código 1 e NÃO reescreve
o index.html (o site mantém a última versão boa; a Action fica vermelha e avisa
por e-mail). Falha ao baixar um .fit de teste só gera aviso.
"""

import csv, io, json, math, os, re, sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from npc import tp
from npc.lactate import analyze

TZ = ZoneInfo("America/Sao_Paulo")
TODAY = datetime.now(TZ).date()
FILES_DIR = "files"

# Atletas exibidos (chave da URL → id no TrainingPeaks)
ATHLETES = {
    "bruno": {"tp_id": 6285028, "name": "Bruno Trevisan Romero", "short": "Bruno"},
    "jean":  {"tp_id": 6286348, "name": "Jean Romano",           "short": "Jean"},
}

# IDs de tipo de treino do TP (tp_get_workout_types)
SPORT = {1: "swim", 2: "bike", 8: "bike", 3: "run", 4: "brick", 6: "race",
         9: "strength", 29: "strength", 7: "dayoff", 13: "other", 5: "other",
         10: "other", 11: "other", 12: "other", 100: "other"}


# ── Utilidades ────────────────────────────────────────────────────────
def d(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def num(v, nd=None):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    if nd == 0:
        return int(round(f))
    return round(f, nd) if nd is not None else f


def monday(x):
    return x - timedelta(days=x.weekday())


def jsonable(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if hasattr(o, "__float__"):
        return float(o)
    return str(o)


# ── Treinos ───────────────────────────────────────────────────────────
def norm_workout(w):
    tid = int(w.get("workoutTypeValueId") or 0)
    dur_a = num(w.get("totalTime"))
    tss_a = num(w.get("tssActual"))
    done = bool((dur_a or 0) > 0 or (tss_a or 0) > 0)
    vel = num(w.get("velocityAverage"))
    sport = SPORT.get(tid, "other")
    pace = None
    if done and vel and vel > 0:
        pace = round(1000 / vel) if sport == "run" else (round(100 / vel) if sport == "swim" else None)
    comments = []
    for c in (w.get("workoutComments") or []):
        if isinstance(c, dict) and (c.get("comment") or "").strip():
            comments.append({"who": c.get("commenterName") or "", "text": c["comment"].strip()[:800]})
    desc = (w.get("description") or "").strip()
    return {
        "id": w.get("workoutId"),
        "date": str(w.get("workoutDay", ""))[:10],
        "sport": sport,
        "title": (w.get("title") or "").strip() or sport,
        "desc": desc[:2500],
        "done": done,
        "plan": {"h": num(w.get("totalTimePlanned"), 3), "tss": num(w.get("tssPlanned"), 1),
                 "km": num((w.get("distancePlanned") or 0) / 1000, 2) if w.get("distancePlanned") else None,
                 "if": num(w.get("ifPlanned"), 2)},
        "act": {"h": num(dur_a, 3), "tss": num(tss_a, 1),
                "km": num((w.get("distance") or 0) / 1000, 2) if w.get("distance") else None,
                "if": num(w.get("if"), 2), "np": num(w.get("normalizedPowerActual"), 0),
                "pw": num(w.get("powerAverage"), 0), "hr": num(w.get("heartRateAverage"), 0),
                "hrmax": num(w.get("heartRateMaximum"), 0), "cad": num(w.get("cadenceAverage"), 0),
                "pace": pace, "elev": num(w.get("elevationGain"), 0),
                "rpe": num(w.get("rpe"), 0), "feel": num(w.get("feeling"), 0)} if done else None,
        "comments": comments,
    }


# ── Wellness ──────────────────────────────────────────────────────────
def norm_wellness(raw):
    out = {}
    for r in raw:
        day = str(r.get("timeStamp") or r.get("date") or "")[:10]
        if not day:
            continue
        e = out.setdefault(day, {"d": day})
        for det in (r.get("details") or []):
            t, v = det.get("type"), det.get("value")
            if v is None:
                continue
            if t == 60:   e["hrv"] = num(v, 0)
            elif t == 5:  e["rhr"] = num(v, 0)
            elif t == 6:  e["sleep"] = num(v, 2)
            elif t == 64 and isinstance(v, list) and len(v) >= 3 and v[2] is not None:
                e["bb"] = num(v[2], 0)
    return [out[k] for k in sorted(out)]


# ── PMC + projeção ────────────────────────────────────────────────────
def norm_pmc(raw, workouts):
    """PMC do TP até ONTEM. O endpoint soma o TSS PLANEJADO do dia corrente (e futuros), então
    hoje é recalculado só com o que já foi feito, a partir do CTL/ATL de ontem."""
    rows = []
    for r in raw:
        day = str(r.get("workoutDay", ""))[:10]
        if day and day < TODAY.isoformat():
            rows.append({"d": day, "tss": num(r.get("tssActual"), 1) or 0,
                         "ctl": num(r.get("ctl"), 1), "atl": num(r.get("atl"), 1), "tsb": num(r.get("tsb"), 1)})
    rows.sort(key=lambda x: x["d"])
    if rows:
        y = rows[-1]
        tss = sum((w["act"]["tss"] or 0) for w in workouts if w["done"] and w["date"] == TODAY.isoformat())
        kc, ka = 1 - math.exp(-1 / 42), 1 - math.exp(-1 / 7)
        ctl = y["ctl"] + (tss - y["ctl"]) * kc
        atl = y["atl"] + (tss - y["atl"]) * ka
        rows.append({"d": TODAY.isoformat(), "tss": round(tss, 1), "ctl": round(ctl, 1), "atl": round(atl, 1),
                     "tsb": round(y["ctl"] - y["atl"], 1), "partial": True})
    return rows


def projection(pmc, workouts, plan):
    """CTL/ATL projetados até o fim do macro: TSS planejado no TP onde existe, senão alvo semanal ÷ 7."""
    if not pmc or not plan:
        return []
    last = pmc[-1]
    ctl, atl = last["ctl"] or 0, last["atl"] or 0
    planned = {}
    for w in workouts:
        if w["date"] > last["d"] and w["plan"]["tss"]:
            planned[w["date"]] = planned.get(w["date"], 0) + w["plan"]["tss"]
    last_planned = max(planned) if planned else last["d"]
    weeks = {wk["mon"]: wk for wk in plan["weeks"]}
    kc, ka = 1 - math.exp(-1 / 42), 1 - math.exp(-1 / 7)
    out, day, end = [], d(last["d"]) + timedelta(days=1), d(plan["end"])
    while day <= end:
        ds = day.isoformat()
        if ds <= last_planned:
            tss, src = planned.get(ds, 0), "tp"
        else:
            wk = weeks.get(monday(day).isoformat())
            tss, src = ((wk["tss"] or 0) / 7 if wk else 0), "macro"
        tsb = ctl - atl                       # forma do dia = CTL − ATL de ontem (convenção do TP)
        ctl += (tss - ctl) * kc
        atl += (tss - atl) * ka
        out.append({"d": ds, "tss": round(tss, 1), "ctl": round(ctl, 1), "atl": round(atl, 1), "tsb": round(tsb, 1), "src": src})
        day += timedelta(days=1)
    return out


# ── Semanas (alvo do macro × planejado no TP × realizado) ─────────────
def week_rows(pmc, workouts, plan, first_monday, last_monday):
    tss_by_day = {r["d"]: r["tss"] for r in pmc}
    weeks = {wk["mon"]: wk for wk in (plan["weeks"] if plan else [])}
    out, m = [], first_monday
    while m <= last_monday:
        days = [(m + timedelta(days=i)).isoformat() for i in range(7)]
        ws = [w for w in workouts if w["date"] in days]
        sport_h = {}
        for w in ws:
            if w["done"] and w["act"]["h"]:
                sport_h[w["sport"]] = round(sport_h.get(w["sport"], 0) + w["act"]["h"], 2)
        wk = weeks.get(m.isoformat())
        out.append({
            "mon": m.isoformat(),
            "week": wk["w"] if wk else None, "type": wk["type"] if wk else None,
            "target_tss": wk["tss"] if wk else None, "target_h": wk["h"] if wk else None,
            "planned_tss": round(sum(w["plan"]["tss"] or 0 for w in ws), 0),
            "planned_h": round(sum(w["plan"]["h"] or 0 for w in ws), 2),
            "tss": round(sum(tss_by_day.get(x, 0) for x in days if x <= TODAY.isoformat()), 0) if days[0] <= TODAY.isoformat() else None,
            "h": round(sum(sport_h.values()), 2) if days[0] <= TODAY.isoformat() else None,
            "sport_h": sport_h,
            "n_done": sum(1 for w in ws if w["done"]),
            "n_planned": sum(1 for w in ws if w["plan"]["tss"] or w["plan"]["h"]),
        })
        m += timedelta(days=7)
    return out


# ── Supabase → estruturas do dashboard ────────────────────────────────
def build_plan(sb, athlete_uuid):
    plans = [p for p in sb["plans"] if p["athlete_id"] == athlete_uuid]
    if not plans:
        return None
    p = plans[0]
    phases = [ph for ph in sb["phases"] if ph["macro_plan_id"] == p["id"]]
    weeks = [w for w in sb["weeks"] if w["macro_plan_id"] == p["id"]]
    return {
        "name": p["name"], "start": str(p["start_date"]), "end": str(p["end_date"]),
        "total_weeks": p["total_weeks"], "ctl_peak": num(p["target_ctl_peak"], 0),
        "phases": [{"n": ph["phase_number"], "type": ph["phase_type"], "name": ph["name"],
                    "s": ph["start_week"], "e": ph["end_week"],
                    "focus": list(ph["focus"] or []) if not isinstance(ph["focus"], str) else [ph["focus"]],
                    "desc": ph["description"]} for ph in phases],
        "weeks": [{"w": w["week_number"], "mon": str(w["monday_date"]), "type": w["week_type"],
                   "tss": num(w["target_tss"], 0), "h": num(w["target_hours"], 2),
                   "z": [num(w["target_z1_pct"], 0), num(w["target_z2_pct"], 0), num(w["target_z3_pct"], 0)],
                   "sessions": w["target_sessions"], "notes": w["notes"]} for w in weeks],
    }


def build_passports(sb, athlete_uuid):
    by_sport = {}
    for p in sb["passports"]:
        if p["athlete_id"] != athlete_uuid:
            continue
        sp = sb["sports"].get(p["sport_id"], {})
        slug = (sp.get("slug") or sp.get("name") or "").lower()
        key = "bike" if "bik" in slug or "cicl" in slug else "run" if "run" in slug or "corr" in slug else "swim" if "swim" in slug or "nat" in slug else slug
        proto = p["test_protocol"] or ""
        m = re.search(r"\[LT_SOURCE:\s*([^\]]+)\]", proto)
        by_sport.setdefault(key, []).append({
            "v": p["version"], "from": str(p["effective_from"]) if p["effective_from"] else None,
            "ftp": num(p["ftp_watts"], 0), "lt1_w": num(p["lt1_watts"], 0), "lt2_w": num(p["lt2_watts"], 0),
            "lt1_hr": num(p["lt1_hr"], 0), "lt2_hr": num(p["lt2_hr"], 0), "max_hr": num(p["max_hr"], 0),
            "lt1_pace": round(float(p["lt1_pace_min_km"]) * 60) if p["lt1_pace_min_km"] else None,
            "lt2_pace": round(float(p["lt2_pace_min_km"]) * 60) if p["lt2_pace_min_km"] else None,
            "css": num(p["css_per100m"], 0), "vo2max": num(p["vo2max"], 1),
            "source": m.group(1).strip() if m else None,
            "protocol": re.sub(r"\[LT_SOURCE:[^\]]+\]\s*", "", proto).strip(),
            "notes": (p["notes"] or "").strip(),
        })
    for k in by_sport:
        by_sport[k].sort(key=lambda x: x["v"])
    return by_sport


def thr(p, n, is_run):
    """Limiar do passaporte na unidade do teste: W na bike, km/h na corrida (convertido do pace)."""
    if not p:
        return None
    if is_run:
        pace = p.get(f"lt{n}_pace")
        return round(3600 / pace, 2) if pace else None
    return p.get(f"lt{n}_w")


def build_lactate(sb, athlete_uuid, athlete_key, tp_id, passports, warnings):
    rows = [r for r in sb["lactate"] if r["athlete_id"] == athlete_uuid]
    tests, rest = {}, []
    for r in rows:
        if r["purpose"] == "incremental_test":
            day = r["sampled_at"].astimezone(TZ).date().isoformat()
            k = (day, r["sport"] or "?", r["test_round"] or "")
            tests.setdefault(k, []).append(r)
        else:
            rest.append({"t": r["sampled_at"].astimezone(TZ).strftime("%Y-%m-%d %H:%M"), "purpose": r["purpose"],
                         "mmol": num(r["lactate_mmol"], 1), "site": r["sample_site"], "err": r["error_code"],
                         "notes": r["notes"]})
    out = []
    for (day, sport, rnd), samples in sorted(tests.items()):
        samples.sort(key=lambda s: (s["step_index"] if s["step_index"] is not None else -1))
        is_run = sport == "run"
        steps, base = [], None
        for s in samples:
            load = num(s["speed_kmh"], 2) if is_run else num(s["power_w"], 0)
            row = {"i": s["step_index"], "label": s["interval_label"], "mmol": num(s["lactate_mmol"], 1),
                   "load": load, "pace": s["pace_s_per_km"], "hr": num(s["hr_bpm"], 0), "cad": num(s["cadence"], 0),
                   "rpe": num(s["rpe"], 0), "err": s["error_code"], "notes": s["notes"]}
            steps.append(row)
            if (s["step_index"] == 0 or load is None) and row["mmol"] is not None and base is None:
                base = row["mmol"]
        valid = [s for s in steps if s["load"] is not None and s["mmol"] is not None and not s["err"] and (s["i"] or 0) > 0]
        res = analyze(base, [s["load"] for s in valid], [s["mmol"] for s in valid]) if len(valid) >= 4 else None
        slug = f"{day}-{sport}-{rnd or 'teste'}"
        folder = os.path.join(FILES_DIR, "lactato", athlete_key, slug)
        os.makedirs(folder, exist_ok=True)
        # CSV com as amostras (sempre regenerado)
        buf = io.StringIO()
        wcsv = csv.writer(buf)
        wcsv.writerow(["degrau", "rotulo", "lactato_mmol", "km_h" if is_run else "potencia_w", "fc_bpm", "cadencia", "rpe", "erro", "observacoes"])
        for s in steps:
            wcsv.writerow([s["i"], s["label"], s["mmol"], s["load"], s["hr"], s["cad"], s["rpe"], s["err"] or "", s["notes"] or ""])
        with open(os.path.join(folder, "amostras.csv"), "w", encoding="utf-8-sig", newline="") as f:
            f.write(buf.getvalue())
        # .fit do treino (baixa uma vez; fica versionado no repositório)
        wid = next((s["tp_workout_id"] for s in samples if s["tp_workout_id"]), None)
        if wid and not any(n.lower().endswith((".fit", ".fit.gz", ".gz", ".zip", ".tcx")) for n in os.listdir(folder)):
            try:
                files = tp.workout_files(tp_id, wid)
                if files:
                    name, content = tp.download_file(tp_id, wid, files[0]["fileId"])
                    name = re.sub(r"[^A-Za-z0-9._-]", "_", name or f"treino_{wid}.fit.gz")
                    with open(os.path.join(folder, name), "wb") as f:
                        f.write(content)
                    print(f"    lactato {slug}: arquivo {name} salvo ({len(content)//1024} KB)")
                else:
                    warnings.append(f"{athlete_key} {slug}: treino {wid} sem arquivo de dispositivo no TP")
            except tp.TPAuthError:
                raise
            except Exception as e:
                warnings.append(f"{athlete_key} {slug}: não baixou o .fit ({e})")
        files = sorted(os.listdir(folder))
        pp = passports.get(sport, [])
        # passaporte oficial deste teste = a versão MAIS RECENTE cuja origem cita este teste (ex.: v5 só watts, v6 também FC);
        # sem isso, a versão criada no dia do teste; "antes" = última versão anterior ao dia do teste
        cites = [p for p in pp if "lactate" in (p["source"] or "") and day in (p["source"] or "")]
        after = cites[-1] if cites else (next((p for p in pp if p["from"] == day), None) or next((p for p in reversed(pp) if p["from"] and p["from"] <= day and "lactate" in (p["source"] or "")), None))
        before = None
        if after:
            prev = [p for p in pp if p["v"] < after["v"] and (p["from"] or "") < day]
            before = prev[-1] if prev else None
        out.append({
            "slug": slug, "date": day, "sport": sport, "round": rnd, "tp_workout_id": wid,
            "baseline": base, "steps": steps, "analysis": res,
            "official": {"lt1": thr(after, 1, is_run), "lt2": thr(after, 2, is_run),
                         "v": after["v"], "protocol": after["protocol"], "notes": after["notes"],
                         **({"hr1": after["lt1_hr"], "hr2": after["lt2_hr"]} if "hr=measured_lactate" in (after["source"] or "") else {})} if after else None,
            "before": {"lt1": thr(before, 1, is_run), "lt2": thr(before, 2, is_run), "v": before["v"], "source": before["source"]} if before else None,
            "files": [{"name": n, "path": f"/{folder}/{n}".replace(os.sep, "/")} for n in files],
        })
    return {"tests": out, "rest": rest}


# ── Análises (Supabase) e histórico de ciclos ─────────────────────────
def _first(dct, *keys):
    for k in keys:
        v = dct.get(k)
        if v not in (None, "", []):
            return v
    return None


def norm_daily(r):
    items = []
    wa = r["workout_analysis"]
    if isinstance(wa, dict):
        wa = [wa]
    for it in (wa or []):
        if not isinstance(it, dict):
            continue
        flags = it.get("flags") or it.get("flag") or []
        if isinstance(flags, str):
            flags = [flags]
        wid = _first(it, "tp_workout_id", "executed_workout_id", "workout_id")
        items.append({
            "sport": (_first(it, "sport", "esporte") or "").lower(),
            "title": _first(it, "title", "titulo", "workout"),
            "summary": _first(it, "summary", "technical_detail", "obs"),
            "status": _first(it, "execution_status", "status", "executado"),
            "flags": [str(f) for f in flags if f][:12],
            "tss": num(_first(it, "tss_executed", "tss", "tss_real"), 0),
            "wid": int(wid) if isinstance(wid, (int, float)) or (isinstance(wid, str) and wid.isdigit()) else None,
        })
    return {"d": str(r["log_date"]), "short": r["summary_short"], "tech": r["summary_technical"],
            "hrv": r["hrv_status"], "flag": r["training_flag"], "items": items}


def norm_weekly(r):
    return {"mon": str(r["week_start"]), "w": r["week_number"], "at": str(r["analyzed_at"])[:10] if r["analyzed_at"] else None,
            "ctl": num(r["ctl_snapshot"], 1), "atl": num(r["atl_snapshot"], 1), "tsb": num(r["tsb_snapshot"], 1),
            "hrv": num(r["hrv_last"], 1), "hrv_base": num(r["hrv_baseline"], 1), "sleep": num(r["sleep_avg"], 1),
            "tss_plan": r["tss_planned"], "tss": r["tss_actual"], "adh": r["adherence_pct"],
            "status": r["status_geral"], "resumo": r["resumo"], "destaques": list(r["destaques"] or []),
            "alertas": list(r["alertas"] or []), "descarga": r["semana_descarga"], "taper": r["antecipar_taper"],
            "rev_zonas": r["revisar_zonas"], "red_vol": r["reduzir_volume_pct"], "prescricao": r["observacoes_prescricao"],
            "bike_flags": list(r["bike_key_session_flags"] or []), "run_flags": list(r["run_key_session_flags"] or []),
            "sessoes": r["session_analysis_summary"]}


def slug(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s.split(" — ")[0]).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "ciclo"


def build_history(key, tp_id, a_uuid, sb):
    """Ciclos encerrados: grava um JSON por ciclo (treinos do TP + análises) e devolve só o índice."""
    out = []
    for c in [c for c in sb["cycles"] if c["athlete_id"] == a_uuid]:
        s, e = c["start_date"], c["end_date"]
        ws = sorted((norm_workout(w) for w in tp.workouts(tp_id, s, e)), key=lambda w: (w["date"], w["id"] or 0))
        ws = [w for w in ws if w["sport"] != "dayoff"]
        daily = [norm_daily(r) for r in sb["daily"] if r["athlete_id"] == a_uuid and s <= r["log_date"] <= e]
        weekly = [norm_weekly(r) for r in sb["weekly"] if r["athlete_id"] == a_uuid and s - timedelta(days=6) <= r["week_start"] <= e]
        targets = [{"w": w["week_number"], "mon": str(w["monday_date"]), "type": w["week_type"],
                    "tss": num(w["target_tss"], 0), "h": num(w["target_hours"], 2)}
                   for w in sb["cycle_weeks"] if w["macro_plan_id"] == c["id"]]
        name = c["name"].split(" — ")[0].strip()
        rel = f"{FILES_DIR}/historico/{key}/{slug(c['name'])}.json"
        os.makedirs(os.path.dirname(rel), exist_ok=True)
        payload = {"name": name, "start": str(s), "end": str(e), "workouts": ws, "daily": daily,
                   "weekly": weekly, "targets": targets}
        with open(rel, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=jsonable, separators=(",", ":"))
        n_done = sum(1 for w in ws if w["done"])
        print(f"    histórico {name}: {n_done} treinos feitos · {len(daily)} análises diárias · {len(weekly)} semanais")
        out.append({"name": name, "start": str(s), "end": str(e), "file": "/" + rel,
                    "n_done": n_done, "n_daily": len(daily), "n_weekly": len(weekly)})
    return sorted(out, key=lambda x: x["start"], reverse=True)


# ── Montagem por atleta ───────────────────────────────────────────────
def build_athlete(key, cfg, sb, warnings):
    tp_id = cfg["tp_id"]
    a_uuid = next((a["id"] for a in sb["athletes"] if str(a["tp_athlete_id"]) == str(tp_id)), None)
    plan = build_plan(sb, a_uuid) if a_uuid else None
    start = min(TODAY - timedelta(days=63), d(plan["start"]) if plan else TODAY)
    end = TODAY + timedelta(days=35)
    print(f"    treinos {start} → {end}")
    workouts = sorted((norm_workout(w) for w in tp.workouts(tp_id, start, end)), key=lambda w: (w["date"], w["id"] or 0))
    pmc = norm_pmc(tp.performance(tp_id, TODAY - timedelta(days=400), TODAY), workouts)
    if not pmc:
        raise RuntimeError("PMC vazio no TP")
    wellness = norm_wellness(tp.metrics(tp_id, TODAY - timedelta(days=60), TODAY))
    print(f"    {len(workouts)} treinos · PMC {len(pmc)} dias (CTL {pmc[-1]['ctl']}) · wellness {len(wellness)} dias")
    passports = build_passports(sb, a_uuid) if a_uuid else {}
    events = [{"date": str(e["event_date"]), "name": e["name"], "type": e["event_type"], "priority": e["priority"],
               "ctl_target": num(e["ctl_target"], 0), "desc": e["description"],
               "bike_course": e["bike_course_type"], "run_course": e["run_course_type"],
               "bike_elev": num(e["bike_elevation_m"], 0), "run_elev": num(e["run_elevation_m"], 0)}
              for e in sb["events"] if e["athlete_id"] == a_uuid]
    first_m = monday(min(d(plan["start"]) if plan else TODAY, TODAY - timedelta(days=56)))
    last_m = monday(max(d(plan["end"]) if plan else TODAY, end))
    weeks = week_rows(pmc, workouts, plan, first_m, last_m)
    lactate = build_lactate(sb, a_uuid, key, tp_id, passports, warnings) if a_uuid else {"tests": [], "rest": []}
    history = build_history(key, tp_id, a_uuid, sb) if a_uuid else []
    daily = {r["log_date"].isoformat(): norm_daily(r) for r in sb["daily"]
             if r["athlete_id"] == a_uuid and r["log_date"] >= start}
    weekly = {str(r["week_start"]): norm_weekly(r) for r in sb["weekly"]
              if r["athlete_id"] == a_uuid and r["week_start"] >= start - timedelta(days=6)}
    return {
        "name": cfg["name"], "short": cfg["short"], "tp_id": tp_id,
        "pmc": pmc[-400:], "projection": projection(pmc, workouts, plan),
        "workouts": workouts, "wellness": wellness, "weeks": weeks,
        "plan": plan, "events": events, "passports": passports, "lactate": lactate,
        "daily": daily, "weekly_an": weekly, "history": history,
    }


def inject(db):
    with open("template.html", encoding="utf-8") as f:
        html = f.read()
    data = json.dumps(db, ensure_ascii=False, default=jsonable, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("__NPC_DATA__", data).replace("__GENERATED__", datetime.now(TZ).strftime("%d/%m/%Y %H:%M") + " (Brasília)")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  index.html gerado ({len(html)//1024} KB)")


def main():
    from npc import supa
    print("=== NPC Dashboard Generator v6 ===")
    print(f"Hoje (Brasília): {TODAY}")
    warnings = []
    try:
        tp.access_token()
        print("\n[1/3] Supabase (só-leitura)...")
        with supa.connect() as conn:
            sb = supa.fetch(conn, [c["tp_id"] for c in ATHLETES.values()])
        print(f"  {len(sb['plans'])} planos · {len(sb['weeks'])} semanas · {len(sb['events'])} provas · "
              f"{len(sb['passports'])} passaportes · {len(sb['lactate'])} amostras de lactato · "
              f"{len(sb['daily'])} análises diárias · {len(sb['weekly'])} semanais · {len(sb['cycles'])} ciclos encerrados")
        print("\n[2/3] TrainingPeaks...")
        db = {"today": TODAY.isoformat(), "athletes": {}}
        for key, cfg in ATHLETES.items():
            print(f"\n  [{key.upper()}] TP {cfg['tp_id']}")
            db["athletes"][key] = build_athlete(key, cfg, sb, warnings)
    except tp.TPAuthError as e:
        print(f"\n::error title=TrainingPeaks — autenticação::{e}")
        print("index.html NÃO foi alterado.")
        sys.exit(1)
    except supa.SupaError as e:
        print(f"\n::error title=Supabase::{e}")
        print("index.html NÃO foi alterado.")
        sys.exit(1)
    except Exception as e:
        print(f"\n::error title=Falha ao montar o dashboard::{type(e).__name__}: {e}")
        print("index.html NÃO foi alterado.")
        raise
    for w in warnings:
        print(f"::warning title=Arquivos de lactato::{w}")
    db["warnings"] = warnings
    print("\n[3/3] Gerando página...")
    inject(db)


if __name__ == "__main__":
    main()
