#!/bin/bash
# Ignored Build Step da Vercel (vercel.json → ignoreCommand).
# Convenção da Vercel: exit 0 = CANCELA o deploy · exit 1 = SEGUE com o deploy.
#
# Motivo (09/11/2026): a Vercel processou com atraso o deploy de um commit antigo
# (gerado 06:54) DEPOIS do commit mais novo (07:00) e devolveu a produção para a
# versão velha. Aqui o deploy só é descartado se a main JÁ TEM commit mais novo
# que este (compare: status "ahead").
# Não comparar por igualdade com o HEAD: a API do GitHub pode responder com o HEAD
# anterior em cache por alguns segundos, e aí o deploy do commit novo seria
# descartado por engano (aconteceu com o b737645 em 09/11). Com o compare, um HEAD
# em cache só aparece como "behind" (este commit é mais novo) e o deploy segue.
# Na dúvida (sem rede, limite da API, resposta inesperada), segue com o deploy.

[ "$VERCEL_GIT_COMMIT_REF" != "main" ] && exit 1
[ -z "$VERCEL_GIT_COMMIT_SHA" ] && exit 1

resp=$(curl -fsS -m 10 \
  "https://api.github.com/repos/nordicpaincave/npc-dashboard/compare/${VERCEL_GIT_COMMIT_SHA}...main") || exit 1
status=$(printf '%s' "$resp" | grep -o '"status": *"[a-z]*"' | head -1 | sed 's/.*"\([a-z]*\)"$/\1/')
ahead=$(printf '%s' "$resp" | grep -o '"ahead_by": *[0-9]*' | head -1 | grep -o '[0-9]*$')

if [ "$status" = "ahead" ] && [ "${ahead:-0}" -gt 0 ]; then
  echo "A main já tem $ahead commit(s) mais novo(s) que $VERCEL_GIT_COMMIT_SHA — deploy descartado."
  exit 0
fi
exit 1
