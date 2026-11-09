#!/bin/bash
# Ignored Build Step da Vercel (vercel.json → ignoreCommand).
# Convenção da Vercel: exit 0 = CANCELA o deploy · exit 1 = SEGUE com o deploy.
#
# Motivo (09/11/2026): a Vercel processou com atraso o deploy de um commit antigo
# (gerado 06:54) DEPOIS do commit mais novo (07:00) e devolveu a produção para a
# versão velha. Aqui, todo deploy confere se o commit ainda é o HEAD da main;
# se já existe commit mais novo, este deploy é descartado.
# Na dúvida (sem rede, limite da API do GitHub), segue com o deploy: nunca travar.

[ "$VERCEL_GIT_COMMIT_REF" != "main" ] && exit 1
[ -z "$VERCEL_GIT_COMMIT_SHA" ] && exit 1

head=$(curl -fsS -m 10 -H 'Accept: application/vnd.github.sha' \
  https://api.github.com/repos/nordicpaincave/npc-dashboard/commits/main) || exit 1

if [ -n "$head" ] && [ "$head" != "$VERCEL_GIT_COMMIT_SHA" ]; then
  echo "Commit $VERCEL_GIT_COMMIT_SHA não é mais o HEAD da main ($head) — deploy descartado."
  exit 0
fi
exit 1
