# NPC Endurance — Dashboard de Treinos

Dashboard de Bruno e Jean: uma "cópia" do TrainingPeaks com mais dados — plano macro até as
provas, limiares e zonas, e os testes de lactato com curva, métodos e arquivos.

Site: https://npc-dashboard-seven.vercel.app (também `/bruno` e `/jean`).
Atualizado automaticamente a cada 2 dias pela GitHub Action **Atualizar Dashboard NPC**.

## De onde vem cada dado

| Área | Fonte |
|------|-------|
| PMC (CTL/ATL/TSB), TSS diário, treinos planejados e realizados, wellness | TrainingPeaks (API) |
| Plano macro (fases, semanas, alvos), provas | Supabase (`macro_plans`, `macro_phases`, `macro_weeks`, `athlete_events`) |
| Limiares e zonas | Supabase (`physiological_passports`) |
| Testes de lactato | Supabase (`lactate_samples`) + arquivo .fit do treino no TP |

O PMC é o do **próprio TP** (endpoint de performance), que inclui atividades que não aparecem
na lista de treinos (ex.: força estruturada sincronizada pelo Garmin). O dia de hoje conta só o
que já foi feito; daí para frente a projeção usa o planejado no TP e, depois, os alvos do macro.

## Secrets (Settings → Secrets and variables → Actions)

| Nome | Valor |
|------|-------|
| `TP_COOKIE` | valor do cookie `Production_tpAuth` do TrainingPeaks |
| `SUPABASE_READER_PASSWORD` | senha do usuário só-leitura `dashboard_reader` do Supabase |

**TP_COOKIE**: em app.trainingpeaks.com (logado na conta do treinador), F12 → Application →
Cookies → `Production_tpAuth` → copiar o *Value*. O gerador troca esse cookie por um token novo
(válido ~1h) a cada execução. O cookie dura algumas semanas; quando expirar, a Action fica
vermelha, o GitHub manda e-mail e o site continua com a última versão boa.

**SUPABASE_READER_PASSWORD**: o usuário `dashboard_reader` só consegue LER as tabelas acima
(colunas mínimas de `athletes`; nada de e-mail, nascimento ou lesões) e não escreve em nada.
Para definir ou trocar a senha, no SQL Editor do Supabase:

```sql
alter role dashboard_reader with password 'SUA-SENHA-LONGA-AQUI';
```

e cole a mesma senha no secret. Se a conexão falhar por host, crie também o secret
`SUPABASE_POOLER_HOST` com o host do *Session pooler* (Supabase → Connect).

## Testes de lactato

Cada teste incremental gravado em `lactate_samples` aparece sozinho na aba **Lactato**, com
curva, degraus, LT1/LT2 por método (basal+0,5 e +1,0 mmol, log-log, Dmax Modificado, Dmax,
OBLA 4 mmol) e o valor oficial do passaporte.

**Regra NPC de LT1 (30/10/2026, bike e corrida):** LT1 = basal + 0,5 mmol na curva ajustada, com
basal = média do patamar (coleta de repouso pré-teste + degraus iniciais enquanto cada valor fica
≤ média acumulada + 0,3 mmol, que é a repetibilidade validada da técnica). Os arquivos ficam em
`files/lactato/<atleta>/<data>-<esporte>-<rodada>/`:

- `amostras.csv` — regenerado a cada execução a partir do Supabase;
- o `.fit` do treino — baixado do TP uma vez (pelo `tp_workout_id` das amostras);
- `folheto.html` — opcional; se existir na pasta, vira o botão "Folheto do teste".

## Forçar atualização

GitHub → **Actions → Atualizar Dashboard NPC → Run workflow**.

## Estrutura

```
generate.py          orquestra: lê TP + Supabase e gera index.html
npc/tp.py            cliente da API do TrainingPeaks (cookie → token)
npc/supa.py          leitura do Supabase com o usuário só-leitura
npc/lactate.py       cálculo dos limiares de lactato (Python puro)
template.html        página (Chart.js); recebe os dados em __NPC_DATA__
files/lactato/...    arquivos dos testes de lactato
```
