# NPC Endurance — Dashboard de Treinos

Dashboard interativo de análise de treinos para os atletas Bruno, Jean e Gabriel.
Atualizado automaticamente a cada 2 dias via GitHub Actions + TrainingPeaks + Claude API.

---

## Configuração inicial (feita uma única vez)

### 1. Clonar e estruturar o repositório

```
npc-dashboard/
├── index.html                        ← gerado automaticamente
├── generate.py                       ← script de geração
├── .github/
│   └── workflows/
│       └── update.yml                ← agendamento automático
└── README.md
```

### 2. Extrair o cookie do TrainingPeaks

1. Acesse [app.trainingpeaks.com](https://app.trainingpeaks.com) e faça login
2. Abra o DevTools (F12) → aba **Application** → **Cookies**
3. Copie o valor do cookie chamado **`Production_tpAuth`**

> O cookie expira em ~2 semanas. Quando o workflow falhar por autenticação,
> repita este passo e atualize o secret `TP_COOKIE` no GitHub.

### 3. Obter a chave da API do Claude (Anthropic)

1. Acesse [console.anthropic.com](https://console.anthropic.com)
2. Vá em **API Keys → Create Key**
3. Copie a chave gerada (`sk-ant-...`)

### 4. Adicionar os secrets no GitHub

No repositório, vá em **Settings → Secrets and variables → Actions → New repository secret**:

| Nome               | Valor                          |
|--------------------|--------------------------------|
| `TP_COOKIE`        | valor do cookie `Production_tpAuth` |
| `ANTHROPIC_API_KEY`| sua chave `sk-ant-...`         |

### 5. Ativar o workflow

- Vá em **Actions → Atualizar Dashboard NPC → Enable workflow**
- Para testar imediatamente: clique em **Run workflow**

---

## Manutenção recorrente

### Cookie expirou (a cada ~2 semanas)

1. Repita o passo 2 acima para extrair o novo cookie
2. Atualize o secret `TP_COOKIE` no GitHub (**Settings → Secrets**)
3. Rode o workflow manualmente para confirmar que voltou a funcionar

### Forçar atualização manual

No GitHub: **Actions → Atualizar Dashboard NPC → Run workflow**

---

## Agendamento

O dashboard é atualizado automaticamente às **04h (horário de Curitiba)**
nos dias ímpares do mês (1, 3, 5, 7...).

Para alterar a frequência, edite a linha `cron` em `.github/workflows/update.yml`.
Exemplos:
- A cada 3 dias: `"0 7 */3 * *"`
- Toda segunda-feira: `"0 7 * * 1"`
- Todo dia: `"0 7 * * *"`

---

## Atletas

| Nome    | ID TrainingPeaks | Categoria |
|---------|-----------------|-----------|
| Bruno   | 6285028         | M40-44    |
| Jean    | 6286348         | M40-44    |
| Gabriel | 5775491         | M18-24    |
