"""
NPC Endurance — Dashboard Generator
Busca dados do TrainingPeaks via cookie de sessão e gera o index.html
via Claude API.

Variáveis de ambiente necessárias:
  TP_COOKIE        — cookie de autenticação do TrainingPeaks
  ANTHROPIC_API_KEY — chave da API do Claude
"""

import os
import json
import requests
import anthropic
from datetime import datetime, timedelta

# ── Configurações ──────────────────────────────────────────────────────
ATHLETES = {
    "Bruno":   5285028,
    "Jean":    6286348,
    "Gabriel": 5775491,
}

TP_BASE  = "https://tpapi.trainingpeaks.com"
TP_COOKIE = os.environ["TP_COOKIE"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

HEADERS = {
    "Cookie": f"Production_tpAuth={TP_COOKIE}",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}

# ── Funções de busca ──────────────────────────────────────────────────

def get_workouts(athlete_id: int, days: int = 14) -> list:
    """Busca os treinos realizados dos últimos N dias."""
    end   = datetime.utcnow()
    start = end - timedelta(days=days)
    url = (
        f"{TP_BASE}/fitness/v6/athletes/{athlete_id}/workouts"
        f"/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_fitness(athlete_id: int) -> dict:
    """Busca CTL, ATL e TSB (PMC) do atleta."""
    end   = datetime.utcnow()
    start = end - timedelta(days=56)  # 8 semanas
    url = (
        f"{TP_BASE}/fitness/v6/athletes/{athlete_id}/fitness"
        f"/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def collect_all_data() -> dict:
    """Coleta dados de todos os atletas e retorna dict estruturado."""
    data = {}
    for name, athlete_id in ATHLETES.items():
        print(f"  Buscando dados de {name} (id={athlete_id})...")
        try:
            workouts = get_workouts(athlete_id, days=14)
            fitness  = get_fitness(athlete_id)
            data[name] = {
                "athlete_id": athlete_id,
                "workouts":   workouts,
                "fitness":    fitness,
            }
        except Exception as e:
            print(f"  ERRO ao buscar {name}: {e}")
            data[name] = {"athlete_id": athlete_id, "error": str(e)}
    return data


# ── Geração do HTML via Claude ─────────────────────────────────────────

SYSTEM_PROMPT = """
Você é um gerador de dashboards HTML para o NPC Endurance (método norueguês de triathlon).
Receberá dados brutos do TrainingPeaks (treinos realizados, CTL/ATL/TSB) de 3 atletas:
Bruno (M40-44, FTP ~281W), Jean (M40-44, FTP 304W) e Gabriel (M18-24).

Sua tarefa é gerar um arquivo HTML completo e autocontido (sem dependências externas além
do Chart.js via CDN) com o dashboard de análise de treinos.

O dashboard deve incluir:
1. Seletor de atleta, modalidade e semana
2. KPIs: CTL, ATL, TSB, TSS semanal, total de horas
3. Gráfico PMC (CTL/ATL/TSB — 8 semanas)
4. Distribuição de zonas Z1/Z2/Z3 por disciplina
5. Volume semanal por disciplina (natação, bike, corrida, força)
6. Tendência de HRV (14 dias) se disponível nos dados
7. Aderência ao plano (executado vs prescrito, se disponível)
8. Alertas automáticos de overtraining (TSB < -15), taper inadequado, HRV em queda
9. Aba comparativa entre os 3 atletas
10. Tabela de sessões da semana

Design: tema escuro, profissional, cores NPC (azul #4a9eff, laranja #ff7c3a, verde #4db87a).
Use Chart.js 4.4.1 via CDN. Retorne APENAS o HTML completo, sem explicações.

Inclua no rodapé a data de geração e que os dados vêm do TrainingPeaks.
"""


def generate_html(raw_data: dict) -> str:
    """Envia os dados ao Claude e recebe o HTML gerado."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_message = f"""
Gere o dashboard NPC Endurance com os seguintes dados do TrainingPeaks:

{json.dumps(raw_data, ensure_ascii=False, indent=2)}

Data de referência: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC

Retorne apenas o HTML completo.
"""

    print("  Chamando Claude API para gerar o dashboard...")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    html = message.content[0].text.strip()

    # Remove blocos de markdown caso o modelo os adicione
    if html.startswith("```html"):
        html = html[7:]
    if html.startswith("```"):
        html = html[3:]
    if html.endswith("```"):
        html = html[:-3]

    return html.strip()


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=== NPC Dashboard Generator ===")
    print(f"Data: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC\n")

    print("[1/3] Buscando dados do TrainingPeaks...")
    raw_data = collect_all_data()

    print("\n[2/3] Gerando HTML via Claude API...")
    html = generate_html(raw_data)

    print("\n[3/3] Salvando index.html...")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = len(html.encode()) // 1024
    print(f"\nConcluído! index.html gerado ({size_kb} KB)")


if __name__ == "__main__":
    main()
