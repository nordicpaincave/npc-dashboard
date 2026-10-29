"""Leitura do Supabase com o usuário SÓ-LEITURA dashboard_reader (via pooler, IPv4)."""
import os
import psycopg
from psycopg.rows import dict_row

PROJECT = "espohjzpsxxmheiubgfv"
HOSTS = ["aws-0-us-east-2.pooler.supabase.com", "aws-1-us-east-2.pooler.supabase.com"]


class SupaError(RuntimeError):
    pass


def connect():
    pwd = os.environ.get("SUPABASE_READER_PASSWORD", "")
    if not pwd:
        raise SupaError("Secret SUPABASE_READER_PASSWORD ausente.")
    host_override = os.environ.get("SUPABASE_POOLER_HOST", "").strip()
    last = None
    for host in ([host_override] if host_override else HOSTS):
        try:
            return psycopg.connect(host=host, port=5432, dbname="postgres", user=f"dashboard_reader.{PROJECT}",
                                   password=pwd, sslmode="require", connect_timeout=15, row_factory=dict_row)
        except psycopg.OperationalError as e:
            last = e
            print(f"  supabase: {host} falhou — {str(e).splitlines()[0][:160]}")
    raise SupaError(f"Não conectou no Supabase: {last}")


def fetch(conn, athlete_tp_ids):
    q = lambda sql, *a: conn.execute(sql, a).fetchall()
    ath = q("select id, nome, apelido, tp_athlete_id from athletes where tp_athlete_id = any(%s)",
            [str(x) for x in athlete_tp_ids])
    ids = [a["id"] for a in ath]
    sports = {r["id"]: r for r in q("select id, name, slug from sports")}
    plans = q("""select id, athlete_id, name, start_date, end_date, total_weeks, target_ctl_peak
                 from macro_plans where active and deleted_at is null and athlete_id = any(%s)
                 order by start_date desc""", ids)
    pids = [p["id"] for p in plans]
    phases = q("""select macro_plan_id, phase_number, phase_type, name, start_week, end_week, focus, description
                  from macro_phases where macro_plan_id = any(%s) order by phase_number""", pids)
    weeks = q("""select macro_plan_id, phase_id, week_number, monday_date, week_type, target_tss, target_hours,
                        target_z1_pct, target_z2_pct, target_z3_pct, target_sessions, notes
                 from macro_weeks where macro_plan_id = any(%s) order by week_number""", pids)
    events = q("""select athlete_id, event_date, name, event_type, priority, ctl_target, description,
                         bike_course_type, run_course_type, bike_elevation_m, run_elevation_m
                  from athlete_events where athlete_id = any(%s) and event_date >= current_date - 120
                  order by event_date""", ids)
    passports = q("""select athlete_id, sport_id, version, effective_from, ftp_watts, lt1_watts, lt2_watts,
                            css_per100m, lt1_pace_min_km, lt2_pace_min_km, lt1_hr, lt2_hr, max_hr, vo2max,
                            test_protocol, notes, created_at
                     from physiological_passports where athlete_id = any(%s)
                     order by athlete_id, sport_id, version""", ids)
    lactate = q("""select athlete_id, sampled_at, purpose, sport, test_round, tp_workout_id, step_index,
                          interval_label, lactate_mmol, power_w, speed_kmh, pace_s_per_km, hr_bpm, cadence, rpe,
                          sample_site, error_code, notes
                   from lactate_samples where athlete_id = any(%s) order by sampled_at, step_index""", ids)
    # ciclos encerrados (histórico): planos que já terminaram, com as semanas-alvo
    cycles = q("""select id, athlete_id, name, start_date, end_date
                  from macro_plans where deleted_at is null and end_date < current_date and athlete_id = any(%s)
                  order by start_date""", ids)
    cycle_weeks = q("""select macro_plan_id, week_number, monday_date, week_type, target_tss, target_hours
                       from macro_weeks where macro_plan_id = any(%s) order by week_number""", [c["id"] for c in cycles])
    # análises geradas pelo Claude (diárias pós-treino e semanais)
    daily = q("""select athlete_id, log_date, summary_short, summary_technical, hrv_status, training_flag, workout_analysis
                 from daily_recommendations where athlete_id = any(%s) order by log_date""", ids)
    weekly = q("""select athlete_id, week_start, week_number, analyzed_at, ctl_snapshot, atl_snapshot, tsb_snapshot,
                         hrv_last, hrv_baseline, sleep_avg, tss_planned, tss_actual, adherence_pct, status_geral, resumo,
                         destaques, alertas, semana_descarga, antecipar_taper, revisar_zonas, reduzir_volume_pct,
                         observacoes_prescricao, bike_key_session_flags, run_key_session_flags, session_analysis_summary
                  from weekly_analyses where athlete_id = any(%s) order by week_start""", ids)
    return {"athletes": ath, "sports": sports, "plans": plans, "phases": phases, "weeks": weeks,
            "events": events, "passports": passports, "lactate": lactate,
            "cycles": cycles, "cycle_weeks": cycle_weeks, "daily": daily, "weekly": weekly}
