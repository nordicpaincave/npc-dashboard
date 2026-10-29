# NPC Endurance — Dashboard de Treinos

Dashboard interativo de análise de treinos para os atletas Bruno e Jean.
Atualizado automaticamente a cada 2 dias via GitHub Actions + TrainingPeaks.

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

> O `generate.py` troca esse cookie por um token de acesso novo (válido ~1h) a cada
> execução, então só o cookie precisa ficar no secret. O cookie em si dura algumas
> semanas. Quando expirar, o workflow **falha (fica vermelho)** e o GitHub manda
> e-mail — o site continua com a última versão boa. Aí é só repetir este passo e
> atualizar o secret `TP_COOKIE`.
>
> Não use mais o secret `TP_BEARER`: um Bearer fixo expira em ~1h.

### 3. Adicionar os secrets no GitHub

No repositório, vá em **Settings → Secrets and variables → Actions → New repository secret**:

| Nome               | Valor                          |
|--------------------|--------------------------------|
| `TP_COOKIE`        | valor do cookie `Production_tpAuth` |

### 4. Ativar o workflow

- Vá em **Actions → Atualizar Dashboard NPC → Enable workflow**
- Para testar imediatamente: clique em **Run workflow**

---

## Manutenção recorrente

### Cookie expirou (workflow vermelho com erro de autenticação)

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
